#!/usr/bin/env python3
"""src/kernel/registration.py —— spec/ 与运行时之间的唯一通道（KS-7.2 / VER-2）。
管线五步（顺序即管线，任一步失败即整体失败，fail-closed / P-3）：
 1. load       读 spec/ 全部声明（objects/links/actions/contexts/aggregates/
               mappings/processes/invariants/governance）—— 九类样例即骨架的承重测试
 2. compile    SC 两段式编译（KS-7.1 / VER-18）：structural → Check AST；
               conditional → BooleanFunctionRef（R10，运行时由受限解释器求值）
 3. validate   LinkPattern 三项（P-4/INV-2/VER-21）· 求值预算 ≤ R8（P-2）·
               修复绑定存在（INV-3）· 上下文 steward 必填（P-3/VER-12）·
               语义损耗声明（KS-4）· provenance 义务（KS-8.2）
 4. register   生成能力清单 generated 段（创世内建 + 编译通过的业务 Action），
               每条携带 provenance
 5. reconcile  与 config/capabilities.yaml generated 段逐条比对，
               不一致即失败 —— declared == registered（INV-13）
单写者原则（P-5）：本模块是 capabilities.yaml generated 段的唯一写者。
调用点三处：内核启动（失败=不发布能力清单=不启动）· aos verify（静态核对）·
治理 Action 生效后重跑（GOV-4）。
"""
import json, sys
from pathlib import Path
try:
    import yaml
except ImportError:                                   # spec/ 声明解析依赖
    yaml = None
import os                                                 # ADR-001: kernel 包在 site-packages 时需外部注入模板根
# 未设 AOSKEEL_ROOT 时逐字回退原锚点 Path(__file__).parents[2]（零回归）；
# 设置后指向 template 根，使 aoskeel-kernel wheel 真正可读 config/spec。
ROOT = Path(os.environ.get("AOSKEEL_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import RegistrationFailed
from kernel.sc_compiler import compile_action, CompiledAction
SPEC_DIR = ROOT / "spec"
CAPS = ROOT / "config/capabilities.yaml"
META_SCHEMA = ROOT / "spec/meta/declaration-schema.yaml"   # 九类声明骨架的声明化元 schema
R8_BUDGET_LIMIT = 10 ** 5                             # R8 缺省求值预算上限
GENESIS_BUILTINS = {                                  # BOOT-0 基线（KS-8.3 / VER-31）
    "write_actions": [
        {"id": "RecordDecision", "class": "decision_stream",
         "gated_by": "sc_structural_only", "provenance": "genesis"},
        {"id": "RaiseInvariantViolation", "class": "domain",
         "gated_by": "detector_only", "provenance": "genesis"},
        {"id": "DeclareIdentityMerge", "class": "domain",
         "gated_by": "merge_only", "provenance": "genesis"},
    ],
    "channel_writes": [
        {"id": "SessionAppend", "stream": "session",
         "principal_required": "true", "provenance": "genesis"},
    ],
}
def _norm(v) -> str:
    return str(v).lower() if isinstance(v, bool) else str(v)
def load_caps() -> dict:
    """能力清单的唯一读取点（承重件）。

    用 pyyaml 解析（项目已声明依赖）。此前手写的"受限 YAML 子集"解析器按
    逗号切分 flow mapping：值内含逗号或引号时会把一条声明拆成两个键，
    静默改变 declared == registered 的对账输入 —— 承重件不能带这种隐式限制。
    """
    if not CAPS.exists():
        raise RegistrationFailed(f"STRUCTURAL-FAIL: 缺少 {CAPS.name}")
    if yaml is None:
        raise RegistrationFailed("DEPENDENCY: 能力清单解析需要 pyyaml（pip install pyyaml）")
    data = yaml.safe_load(CAPS.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RegistrationFailed("STRUCTURAL-FAIL: capabilities.yaml 顶层须为映射")
    return data
def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RegistrationFailed("DEPENDENCY: spec/ 声明解析需要 pyyaml（pip install pyyaml）")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
# ---------- 步骤 2：SC 编译（KS-7.1 / VER-18） ----------
def _load_actions() -> dict[str, CompiledAction]:
    actions = {}
    adir = SPEC_DIR / "ontology" / "actions"
    for p in sorted(adir.glob("*.yaml")) if adir.exists() else []:
        decl = _load_yaml(p)
        actions[decl["action_type"]] = compile_action(decl, decl.get("provenance", "genesis"))
    return actions
def compile_all() -> dict[str, CompiledAction]:
    """对外编译入口（内核启动与管线消费）。"""
    return _load_actions()
# ---------- 步骤 3：结构化校验 ----------
def validate_link(link: dict) -> list[str]:
    """LinkPattern 三项（P-4 / INV-2 / VER-21）。"""
    failures, lt = [], link.get("link_type", "?")
    checks = link.get("checks") or {}
    if not checks.get("attributes_empty"):
        failures.append(f"LINK-PATTERN: {lt} 属性集非空（P-4）")
    if not checks.get("traversal_transparent"):
        failures.append(f"LINK-PATTERN: {lt} 无遍历透明标记（P-4）")
    if link.get("action_binding"):
        failures.append(f"LINK-PATTERN: {lt} 绑定了 ActionType 写入（P-4/INV-2）")
    return failures
def validate_context(ctx: dict) -> list[str]:
    """上下文声明校验（P-3 所有权 / P-16 延迟预算 / VER-12）。"""
    failures = []
    name = ctx.get("context", "?")
    if not ctx.get("steward"):
        failures.append(f"CONTEXT-STEWARD-MISSING: {name}（P-3 / VER-12）")
    if ctx.get("projection_delay_budget_ms") is None:
        failures.append(f"CONTEXT-PROJECTION-BUDGET-MISSING: {name}（P-16）")
    return failures
# ---------- 元 schema 骨架校验（声明化；专用语义校验保持原位） ----------
_TYPE_CHECKS = {
    "str": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "dict": lambda v: isinstance(v, dict),
    "list": lambda v: isinstance(v, list),
}

def validate_meta_schema(meta: dict, spec_dir: Path) -> list[str]:
    """按 spec/meta/declaration-schema.yaml 对九类声明做通用骨架校验。

    元 schema 是声明而非硬编码规则：增删 required 字段即改变注册期判据，
    且该文件随 spec/ 摘要域进入第四道比对（改规则必须走治理变更通道）。
    """
    failures: list[str] = []
    classes = meta.get("classes") or {}
    if not classes:
        return ["META-SCHEMA-EMPTY: 元 schema 无 classes —— 骨架约束不可为空"]
    for cname, cfg in classes.items():
        rel = (cfg or {}).get("directory")
        if not rel:
            failures.append(f"META-CLASS-NO-DIRECTORY: {cname} 缺 directory"); continue
        d = spec_dir / rel
        files = sorted(d.glob("*.yaml")) if d.is_dir() else []
        if not files:
            failures.append(f"META-CLASS-EMPTY: {cname} 目录 {rel} 无 *.yaml "
                            f"—— 声明类别不可空转")
        required = (cfg or {}).get("required") or {}
        for p in files:
            doc = _load_yaml(p)
            short = p.relative_to(spec_dir).as_posix()
            for field, want in required.items():
                check = _TYPE_CHECKS.get(want)
                if check is None:
                    failures.append(f"META-TYPE-UNKNOWN: {cname}.{field} → {want!r}")
                elif field not in doc:
                    failures.append(f"META-REQUIRED-MISSING: {short} 缺 {field} "
                                    f"（元 schema {cname}）")
                elif not check(doc[field]):
                    failures.append(f"META-TYPE-MISMATCH: {short}.{field} 期望 {want} "
                                    f"实得 {type(doc[field]).__name__}")
    return failures

def _validate_meta_schema() -> list[str]:
    if not META_SCHEMA.exists():
        return ["META-SCHEMA-MISSING: spec/meta/declaration-schema.yaml 缺失 —— "
                "九类声明骨架不可无声明（GOV-2.3-DECL 第四道覆盖域）"]
    return validate_meta_schema(_load_yaml(META_SCHEMA), SPEC_DIR)

def _validate_spec() -> list[str]:
    failures: list[str] = []
    for p in sorted((SPEC_DIR / "ontology" / "links").glob("*.yaml")) if (SPEC_DIR / "ontology" / "links").exists() else []:
        failures += validate_link(_load_yaml(p))
    for p in sorted((SPEC_DIR / "contexts").glob("*.yaml")) if (SPEC_DIR / "contexts").exists() else []:
        failures += validate_context(_load_yaml(p))
    for p in sorted((SPEC_DIR / "aggregates").glob("*.yaml")) if (SPEC_DIR / "aggregates").exists() else []:
        d = _load_yaml(p)
        budget = d.get("evaluation_budget")
        if budget is None or int(budget) > R8_BUDGET_LIMIT:
            failures.append(f"BUDGET-EXCEEDED: {d.get('aggregate', p.name)} "
                            f"求值预算 {budget} 缺失或 > R8 上限 {R8_BUDGET_LIMIT}（P-2）")
    for p in sorted((SPEC_DIR / "invariants").glob("*.yaml")) if (SPEC_DIR / "invariants").exists() else []:
        d = _load_yaml(p)
        if not d.get("repair_binding"):
            failures.append(f"REPAIR-BINDING-MISSING: {d.get('invariant', p.name)}（INV-3 / P-6）")
    for p in sorted((SPEC_DIR / "mappings").glob("*.yaml")) if (SPEC_DIR / "mappings").exists() else []:
        d = _load_yaml(p)
        if not d.get("semantic_loss_declared"):
            failures.append(f"SEMANTIC-LOSS-UNDECLARED: {d.get('mapping', p.name)}（KS-4）")
    for p in sorted((SPEC_DIR / "processes").glob("*.yaml")) if (SPEC_DIR / "processes").exists() else []:
        d = _load_yaml(p)
        for c in d.get("compensations", []) or []:
            if not c.get("action"):
                failures.append(f"COMPENSATION-INCOMPLETE: {d.get('process', p.name)}（P-9）")
    failures += _validate_governance()
    failures += _validate_effects()
    failures += _validate_context_refs()
    failures += _validate_meta_schema()
    return failures
def _load_action_types(spec_dir: Path) -> set[str]:
    adir = spec_dir / "ontology" / "actions"
    return {(_load_yaml(p) or {}).get("action_type", p.stem)
            for p in sorted(adir.glob("*.yaml"))} if adir.exists() else set()
def validate_governance(gov: dict, known_actions: set[str]) -> list[str]:
    """治理面结构校验（图1 职责授权矩阵 / L3·L4 锚点）：
    steward 必填（P-3）· 职责项绑定岗位与组织锚点 · 授权引用必须指向已声明 Action
    （声明完整性）· SLA 必须引用在场职责项。"""
    failures, name = [], gov.get("governance", "?")
    if not gov.get("steward"):
        failures.append(f"GOVERNANCE-STEWARD-MISSING: {name}（P-3）")
    duties, seen = gov.get("duties") or [], set()
    if not duties:
        failures.append(f"GOVERNANCE-DUTIES-EMPTY: {name} —— 治理面声明存在但无职责项")
    for d in duties:
        dn = d.get("duty") or "?"
        if dn == "?" or not d.get("duty"):
            failures.append(f"GOVERNANCE-DUTY-UNNAMED: {name} 中存在无名职责项")
        elif dn in seen:
            failures.append(f"GOVERNANCE-DUTY-DUPLICATE: {dn}（职责项名须唯一）")
        seen.add(dn)
        if not d.get("position"):
            failures.append(f"GOVERNANCE-POSITION-MISSING: {dn}（岗位锚点缺失）")
        if not d.get("org_unit"):
            failures.append(f"GOVERNANCE-ORG-UNIT-MISSING: {dn}（组织锚点缺失）")
        authz = d.get("authorizes") or []
        if not authz:
            failures.append(f"GOVERNANCE-AUTHORIZES-EMPTY: {dn} —— 职责项无授权对象（空转）")
        for a in authz:
            if a not in known_actions:
                failures.append(f"GOVERNANCE-ACTION-UNKNOWN: {dn} → {a}（声明完整性）")
    for s in gov.get("sla") or []:
        if s.get("duty") not in seen:
            failures.append(f"GOVERNANCE-SLA-DUTY-UNKNOWN: {s.get('duty', '?')}")
    return failures
def _validate_governance(spec_dir: Path | None = None) -> list[str]:
    """治理面校验 + 角色-职责对账（fail-closed）：
    带 roles 的 Action MUST 被某条职责项授权，且该职责项的岗位 ∈ Action 角色
    ——权限不再是无源之水，每个角色证据都有图1 治理链背书（L3/L4 锚点对账）。"""
    spec_dir = spec_dir or SPEC_DIR
    failures: list[str] = []
    known_actions = _load_action_types(spec_dir)
    gdir = spec_dir / "governance"
    authorized: dict[str, set[str]] = {}
    for p in sorted(gdir.glob("*.yaml")) if gdir.exists() else []:
        gov = _load_yaml(p)
        failures += validate_governance(gov, known_actions)
        for d in gov.get("duties") or []:
            for a in d.get("authorizes") or []:
                authorized.setdefault(a, set()).add(d.get("position") or "")
    adir = spec_dir / "ontology" / "actions"
    for p in sorted(adir.glob("*.yaml")) if adir.exists() else []:
        d = _load_yaml(p)
        roles = set((d.get("permissions") or {}).get("roles") or [])
        if roles and not (roles & authorized.get(d.get("action_type", p.name), set())):
            failures.append(
                f"GOVERNANCE-AUTHORIZATION-MISSING: {d.get('action_type', p.name)} "
                f"要求角色 {sorted(roles)} 但治理面无对应职责授权（L3/L4 锚点对账）")
    return failures
def _validate_effects() -> list[str]:
    """T24 副作用执行点的声明校验（注册期拒绝优于运行时拒绝）：
    effects 键 MUST 是聚合根 object 的声明属性（identity 除外——标识不可被效果改写），
    枚举类型的效果值 MUST 落在声明值域内。"""
    failures: list[str] = []
    objects: dict[str, dict] = {}
    for p in sorted((SPEC_DIR / "ontology" / "objects").glob("*.yaml")):
        d = _load_yaml(p)
        objects[d.get("object_type", p.name)] = d
    roots = {}
    for p in sorted((SPEC_DIR / "aggregates").glob("*.yaml")):
        d = _load_yaml(p)
        roots[d.get("aggregate", p.name)] = d.get("root")
    adir = SPEC_DIR / "ontology" / "actions"
    for p in sorted(adir.glob("*.yaml")) if adir.exists() else []:
        d = _load_yaml(p)
        effects = d.get("effects") or {}
        if not effects:
            continue
        aid = d.get("action_type", p.name)
        obj = objects.get(roots.get(d.get("aggregate", ""), "")) or {}
        props = obj.get("properties", {}) or {}
        identity = obj.get("identity")
        for key, val in effects.items():
            if key == identity:
                failures.append(f"EFFECTS-ILLEGAL-TARGET: {aid} 效果键 {key} 是实例标识（不可改写）")
            elif key not in props:
                failures.append(f"EFFECTS-UNDECLARED-PROP: {aid} 效果键 {key} 不在聚合根 "
                                f"{obj.get('object_type', '?')} 的声明属性内（T24 / AX-5）")
            elif (props[key] or {}).get("type") == "enum" \
                    and val not in (props[key] or {}).get("values", []):
                failures.append(f"EFFECTS-VALUE-OUT-OF-DOMAIN: {aid} 效果值 {val!r} "
                                f"不在 {key} 的声明枚举值域内")
    return failures
def _validate_context_refs() -> list[str]:
    """P-10 上下文引用完整性（声明引用 MUST 解析到 spec/contexts/ 正典）。
    此前 permissions.contexts 只被编译进 CompiledAction、无任何消费者：
    拼错上下文名也能通过五步管线。这里把"空引用"变成注册期失败。"""
    known: set[str] = set()
    for p in sorted((SPEC_DIR / "contexts").glob("*.yaml")):
        known.add((_load_yaml(p) or {}).get("context"))
    failures: list[str] = []
    adir = SPEC_DIR / "ontology" / "actions"
    for p in sorted(adir.glob("*.yaml")) if adir.exists() else []:
        d = _load_yaml(p) or {}
        aid = d.get("action_type", p.name)
        for c in (d.get("permissions") or {}).get("contexts") or []:
            if c not in known:
                failures.append(f"CONTEXT-REF-UNDECLARED: {aid} 引用上下文 {c} "
                                f"无 spec/contexts/ 声明（P-10）")
    return failures
# ---------- 步骤 4+5：生成 + 对账 ----------
def _compute_generated() -> dict:
    """validate + compile + register 三步（不落盘、不对账）。失败即抛。"""
    failures = _validate_spec()                                     # 3 validate
    if failures:
        raise RegistrationFailed("SPEC-INVALID: " + "; ".join(failures))
    actions = _load_actions()                                       # 2 compile
    generated = {                                                   # 4 register（内建 + 业务）
        "write_actions": [dict(x) for x in GENESIS_BUILTINS["write_actions"]],
        "channel_writes": [dict(x) for x in GENESIS_BUILTINS["channel_writes"]],
    }
    for aid, act in actions.items():
        generated["write_actions"].append({"id": aid, "class": "domain",
                                           "gated_by": "sc_full",
                                           "provenance": act.provenance})
    return generated
def apply_generated() -> dict:
    """P-5 单写者的落盘动作：计算 generated 段并重写 capabilities.yaml 的
    生成部分；其前所有行（固定段，手工维护 / INV-6）逐行原样保留 —— 本函数
    从不构造、从不修改固定段内容（P-5 只辖生成段）。生成段固定位于文件尾部。
    """
    generated = _compute_generated()
    old = CAPS.read_text(encoding="utf-8").splitlines()
    gen_headers = ("write_actions:", "channel_writes:")
    idx = next(i for i, l in enumerate(old)
               if l.startswith(gen_headers) or l.rstrip() in gen_headers)
    lines = old[:idx]                                               # 固定段逐行原样保留
    for seg, entries in (("write_actions", generated["write_actions"]),
                         ("channel_writes", generated["channel_writes"])):
        lines.append(f"{seg}:")
        for e in entries:
            inner = ", ".join(f"{k}: {v}" for k, v in e.items())
            lines.append(f"  - {{ {inner} }}")
    CAPS.write_bytes(("\n".join(lines) + "\n").encode("utf-8"))   # 字节精确（* -text）
    return generated
def run_pipeline() -> dict:
    """KS-7.2 五步管线；返回 generated 段。不一致即抛 RegistrationFailed。"""
    generated = _compute_generated()
    caps = load_caps()                                              # 5 reconcile（INV-13）
    for seg in ("write_actions", "channel_writes"):
        declared = [{k: _norm(v) for k, v in e.items()} for e in generated[seg]]
        registered = [{k: _norm(v) for k, v in e.items()} for e in caps.get(seg, [])]
        if json.dumps(declared, sort_keys=True) != json.dumps(registered, sort_keys=True):
            raise RegistrationFailed(
                f"RECONCILE-FAILED: {seg} 段 declared != registered\n"
                f"  declared   = {json.dumps(declared, ensure_ascii=False)}\n"
                f"  registered = {json.dumps(registered, ensure_ascii=False)}")
    return generated
