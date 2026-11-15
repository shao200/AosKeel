#!/usr/bin/env python3
"""src/kernel/registration.py —— spec/ 与运行时之间的唯一通道（KS-7.2 / VER-2）。
管线五步（顺序即管线，任一步失败即整体失败，fail-closed / P-3）：
 1. load       读 spec/ 全部声明（objects/links/actions/contexts/aggregates/
               mappings/processes/invariants）—— 八类样例即骨架的承重测试
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
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import RegistrationFailed
from kernel.sc_compiler import compile_action, CompiledAction
SPEC_DIR = ROOT / "spec"
CAPS = ROOT / "config/capabilities.yaml"
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
def _flow_dict(s: str) -> dict:
    body = s.strip().strip("{}")
    d = {}
    for part in body.split(","):
        k, _, v = part.partition(":")
        d[k.strip()] = v.strip()
    return d
def _parse_subset(text: str) -> dict:
    """受限 YAML 子集解析（capabilities.yaml 的全部形态；无第三方依赖）。"""
    data, cur = {}, None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent, s = len(raw) - len(raw.lstrip()), line.strip()
        if indent == 0 and s.endswith(":"):
            cur = s[:-1]; data[cur] = []
        elif indent == 0 and ":" in s:
            k, _, v = s.partition(":")
            data[k.strip()] = v.split(" #")[0].strip()
            cur = None
        elif s.startswith("- {") and cur is not None:
            data[cur].append(_flow_dict(s[2:]))
        elif s.startswith("- ") and cur is not None:
            data[cur].append(s[2:].strip())
    return data
def load_caps() -> dict:
    if not CAPS.exists():
        raise RegistrationFailed(f"STRUCTURAL-FAIL: 缺少 {CAPS.name}")
    return _parse_subset(CAPS.read_text(encoding="utf-8"))
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
    CAPS.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
