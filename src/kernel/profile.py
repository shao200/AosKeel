#!/usr/bin/env python3
"""src/kernel/profile.py —— Feature Profile 解析器（能力选择 → 依赖展开 → 生成序）。
用户以最小代价声明能力意图（spec/profile.yaml），脚手架据此：
 1. 展开依赖：勾选项隐含的前置能力自动补齐（如 auth.oauth2_1 → governance.duty_matrix）；
 2. 拓扑排序：输出模块生成顺序（治理面在前——它是 auth/后端写路径的语义来源）；
 3. 锚点核对：治理面/聚合/映射的 spec/ 声明必须在场，缺失即 fail-closed 拒绝
    ——勾选不是意图，声明在场才是可生成的依据。
未知能力名/未知值域一律拒绝（fail-closed：拼写错误不得静默忽略）。
本模块只出"生成计划"，不生成代码（诚实边界）；生成器按计划逐模块接入。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
try:
    import yaml
except ImportError:                                   # 与 registration 同源依赖
    yaml = None
# 依赖图：能力 id → 前置能力 id（无环；核义：治理面是一切授权/审计的根）
DEPENDENCIES: dict[str, list[str]] = {
    "governance.duty_matrix":   [],
    "governance.audit_trail":   ["backend.event_sourcing"],   # 审计走事件溯源
    "backend.cqrs":             ["governance.duty_matrix"],   # 写端授权有治理背书
    "backend.event_sourcing":   ["backend.cqrs"],
    "backend.projections":      ["backend.event_sourcing"],   # 读端投影依赖事件流
    "frontend.admin_console":   ["backend.cqrs"],
    "frontend.form_generation": ["frontend.admin_console"],
    "auth.oauth2_1":            ["governance.duty_matrix"],   # claims 语义来自治理面
    "auth.pkce":                ["auth.oauth2_1"],
    "auth.token_binding":       ["auth.oauth2_1"],            # 值 none 视为未选
    "workflow.enabled":         ["backend.cqrs"],
}
VALUE_DOMAINS: dict[str, set[str]] = {
    "auth.token_binding": {"dpop", "mTLS", "none"},
}
# 深度预设（向导的唯一参数化点）：广度由 capabilities 表达，深度 = 分层完整度起点。
# minimal = 只铺治理面（L3 锚点先行）；standard = 最小可运行闭环；
# full = 全模块。--cap/--no-cap 在预设之上增删（依赖展开仍由解析器兜底）。
DEPTH_PRESETS: dict[str, dict] = {
    "minimal":  {"governance.duty_matrix": True},
    "standard": {"governance.duty_matrix": True, "governance.audit_trail": True,
                 "backend.cqrs": True, "auth.oauth2_1": True,
                 "auth.token_binding": "dpop"},
    "full":     {"governance.duty_matrix": True, "governance.audit_trail": True,
                 "backend.cqrs": True, "backend.projections": True,
                 "auth.oauth2_1": True, "auth.pkce": True,
                 "auth.token_binding": "dpop",
                 "frontend.admin_console": True, "frontend.form_generation": True,
                 "workflow.enabled": True},
}
# 能力 → spec/ 锚点目录（勾选了就必须有声明在场，否则拒绝）
ANCHORS: dict[str, str] = {
    "governance.duty_matrix":   "governance",
    "backend.cqrs":             "aggregates",
    "frontend.admin_console":   "mappings",
}
class ProfileError(Exception):
    """Profile 声明非法（未知能力/非法值/结构错误）—— 一律明确拒绝。"""
def _enabled(v) -> bool:
    """选择语义：bool True / 非空列表 / 非 none 字符串 = 已选。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, list):
        return len(v) > 0
    if isinstance(v, str):
        return v.strip().lower() != "none"
    raise ProfileError(f"PROFILE-VALUE-ILLEGAL: 不支持的值类型 {type(v).__name__}")
def _selected_ids(caps: dict) -> tuple[dict[str, str], dict[str, str]]:
    """展平声明 → ({能力id: "declared"}, {能力id: 原始值})。
    未知家族/能力/值 → 拒绝。"""
    sel: dict[str, str] = {}
    vals: dict[str, str] = {}
    for fam, body in (caps or {}).items():
        if fam not in {i.split(".", 1)[0] for i in DEPENDENCIES}:
            raise ProfileError(f"PROFILE-FAMILY-UNKNOWN: 能力家族 {fam!r} 不在声明集内"
                               f"（{sorted({i.split('.', 1)[0] for i in DEPENDENCIES})}）")
        if not isinstance(body, dict):
            raise ProfileError(f"PROFILE-STRUCT-INVALID: {fam} 段须为映射")
        for k, v in body.items():
            cid = f"{fam}.{k}"
            if cid not in DEPENDENCIES:
                raise ProfileError(f"PROFILE-CAPABILITY-UNKNOWN: {cid} 不在能力集内"
                                   "—— fail-closed，拼写错误不得静默忽略")
            if cid in VALUE_DOMAINS and str(v).strip().lower() not in VALUE_DOMAINS[cid]:
                raise ProfileError(f"PROFILE-VALUE-ILLEGAL: {cid}={v!r} "
                                   f"不在值域 {sorted(VALUE_DOMAINS[cid])} 内")
            if _enabled(v):
                sel[cid] = "declared"
                vals[cid] = v if isinstance(v, str) else True
    return sel, vals
def _expand(sel: dict[str, str]) -> dict[str, str]:
    """依赖展开至不动点：隐含前置标记为 implied。"""
    changed = True
    while changed:
        changed = False
        for cid in list(sel):
            for pre in DEPENDENCIES[cid]:
                if pre not in sel:
                    sel[pre] = "implied"; changed = True
    return sel
def _topo(sel: dict[str, str]) -> list[str]:
    """Kahn 拓扑序（前置在前）；出现环 → 拒绝（依赖图无环是硬约束）。"""
    indeg = {c: 0 for c in sel}
    rev: dict[str, list[str]] = {}
    for c in sel:
        for pre in DEPENDENCIES[c]:
            if pre in sel:
                indeg[c] += 1
                rev.setdefault(pre, []).append(c)
    ready = sorted(c for c, d in indeg.items() if d == 0)
    order: list[str] = []
    while ready:
        c = ready.pop(0)
        order.append(c)
        for nxt in sorted(rev.get(c, [])):
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                ready.append(nxt)
        ready.sort()
    if len(order) != len(sel):
        raise ProfileError(f"PROFILE-CYCLE: 依赖图出现环（selected={sorted(sel)}）")
    return order
def _anchor_failures(sel: dict[str, str], spec_dir: Path) -> list[str]:
    out: list[str] = []
    for cid, sub in ANCHORS.items():
        if cid not in sel:
            continue
        d = spec_dir / sub
        if not d.exists() or not any(d.glob("*.yaml")):
            out.append(f"PROFILE-ANCHOR-MISSING: {cid} 需要 spec/{sub}/ 至少一条声明"
                       "（勾选不是意图，声明在场才是可生成依据）")
    return out
def resolve(root: Path | None = None) -> dict:
    """解析 spec/profile.yaml → {project, selected, order, failures}。
    failures 非空 = 计划不可执行（锚点缺失）；ProfileError = 声明本身非法。"""
    root = root or ROOT
    spec_dir = root / "spec"
    prof_path = spec_dir / "profile.yaml"
    if yaml is None:
        raise ProfileError("DEPENDENCY: Profile 解析需要 pyyaml（pip install pyyaml）")
    if not prof_path.exists():
        raise ProfileError(f"PROFILE-MISSING: 缺少 {prof_path} —— "
                           "先声明能力意图（capabilities 段）再解析")
    data = yaml.safe_load(prof_path.read_text(encoding="utf-8")) or {}
    prof = data.get("profile")
    if not isinstance(prof, dict):
        raise ProfileError("PROFILE-STRUCT-INVALID: 顶层须为 profile: 映射")
    depth = prof.get("depth")
    if depth is not None and depth not in DEPTH_PRESETS:
        raise ProfileError(f"PROFILE-DEPTH-ILLEGAL: {depth!r} 不在 {sorted(DEPTH_PRESETS)} 内")
    sel, vals = _selected_ids(prof.get("capabilities"))
    sel = _expand(sel)
    order = _topo(sel)
    return {"project": prof.get("project", "?"), "depth": depth,
            "selected": sel, "order": order, "values": vals,
            "failures": _anchor_failures(sel, spec_dir)}
_INIT_HEADER = (
    "# spec/profile.yaml —— Feature Profile（由 aos init 生成；唯一真源，可手工修订）\n"
    "# 解析计划: aos profile ｜ 生成落地: aos generate ｜ 深度语义见 kernel.profile.DEPTH_PRESETS\n")
def validate_init_args(name: str | None, depth: str | None, add: tuple = (),
                       remove: tuple = ()) -> tuple[str, str]:
    """init 参数前置校验（cmd_init 在实例化**之前**调用 —— fail-fast，
    非法参数不得浪费一次完整复制）。返回 (name, depth)。"""
    if not name:
        raise ProfileError("INIT-NAME-REQUIRED: 项目名（--name）必填")
    if depth not in DEPTH_PRESETS:
        raise ProfileError(f"INIT-DEPTH-ILLEGAL: {depth!r} 不在 {sorted(DEPTH_PRESETS)} 内")
    for cid in (*add, *remove):
        if cid not in DEPENDENCIES:
            raise ProfileError(f"INIT-CAP-UNKNOWN: {cid} 不在能力集内"
                               "—— fail-closed，拼写错误不得静默忽略")
    return name, depth
def init_profile(name: str, depth: str = "standard", add: tuple = (),
                 remove: tuple = (), root: Path | None = None,
                 force: bool = False) -> dict:
    """向导内核：depth 预设 ± 能力增删 → spec/profile.yaml（init 自校验）。
    纪律：已初始化须 --force（append-only）；产出即时走同一解析器自校验
    （不可解析/展开的意图不落盘）；锚点缺失不阻断 init（新项目本来没有声明）
    —— failures 作为"待声明 roadmap"返回，交给调用方呈现。"""
    root = root or ROOT
    spec_dir = root / "spec"
    prof_path = spec_dir / "profile.yaml"
    if prof_path.exists() and not force:
        raise ProfileError(f"INIT-EXISTS: {prof_path} 已存在 —— 项目已初始化；"
                           "修订请直接编辑 profile.yaml；重铺须显式 --force")
    name, depth = validate_init_args(name, depth, add, remove)
    caps = dict(DEPTH_PRESETS[depth])
    for cid in add:
        caps[cid] = True
    for cid in remove:
        caps.pop(cid, None)
    caps_yaml: dict[str, dict] = {}
    for cid, v in caps.items():
        fam, key = cid.split(".", 1)
        caps_yaml.setdefault(fam, {})[key] = v
    sel, vals = _selected_ids(caps_yaml)          # 值域校验（如 token_binding）
    sel = _expand(sel)
    order = _topo(sel)
    prof = {"profile": {"project": name, "depth": depth, "capabilities": caps_yaml}}
    spec_dir.mkdir(parents=True, exist_ok=True)
    prof_path.write_text(_INIT_HEADER +
                         yaml.safe_dump(prof, sort_keys=False, allow_unicode=True),
                         encoding="utf-8")
    return {"path": prof_path, "depth": depth, "selected": sel, "values": vals,
            "order": order, "failures": _anchor_failures(sel, spec_dir)}
