"""src/kernel/sc_compiler.py —— SC 两段式编译器（KS-7.1 / VER-18）。
structural：声明式子语言 → Check AST（注册期编译，编译失败 = 注册失败）；
conditional：受限布尔表达式 → BooleanFunctionRef（仅引用，运行时由受限解释器求值）。
不编译宿主函数、不注册谓词性代码（P-1：不注册谓词性代码，注册数据）。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from kernel.errors import RegistrationFailed
# 只保留有运行时执行点的算子：`references` 曾在 AST 白名单内但 run_structural
# 无分支（静默跳过），已移除 —— 无执行点的算子不得留在声明式语言里（fail-closed）。
STRUCTURAL_OPS = {"exists", "max_len"}
@dataclass(frozen=True)
class Check:
    op: str          # STRUCTURAL_OPS 之一
    target: str
    arg: str = ""
@dataclass(frozen=True)
class CompiledAction:
    action_type: str
    aggregate: str
    structural: tuple[Check, ...]
    conditional: str | None          # BooleanFunctionRef（R10 引用）
    snapshot_inputs: tuple[str, ...] # R2：快照输入声明（原样，含 principal.* 声明位）
    snapshot_keys: tuple[str, ...]   # R2 来源在编译期定死：环境快照输入（不含 principal.*）
    permissions: dict
    stream: str
    provenance: str
    dry_run: bool
    effects: dict = field(default_factory=dict)  # T24 副作用：内核书写进事件载荷的状态效果
    creates: bool = False            # 创建型动作：唯一允许在实体未投影时以 params 作初始观测
def _compile_structural(rules: list, action_type: str) -> tuple[Check, ...]:
    checks = []
    for rule in rules or []:
        parts = str(rule).split()
        if len(parts) < 2 or parts[0] not in STRUCTURAL_OPS:
            raise RegistrationFailed(
                f"SC-COMPILE-FAIL: {action_type} 结构规则非法 '{rule}'"
                f"（合法算子 {sorted(STRUCTURAL_OPS)}）")
        checks.append(Check(parts[0], parts[1], parts[2] if len(parts) > 2 else ""))
    return tuple(checks)
def compile_action(decl: dict, provenance: str) -> CompiledAction:
    """声明 → 编译产物（CompiledAction）。任何不合法 = RegistrationFailed。"""
    action_type = decl.get("action_type")
    aggregate = decl.get("aggregate")
    if not action_type or not aggregate:
        raise RegistrationFailed(f"SC-COMPILE-FAIL: 缺 action_type/aggregate（P-1）")
    sc = decl.get("submission_criteria") or {}
    structural = _compile_structural(sc.get("structural"), action_type)
    cond = sc.get("conditional") or {}
    expr = cond.get("expression") if isinstance(cond, dict) else cond
    if expr is not None:
        first = str(expr).split(".", 1)[0].split()[0].split("(", 1)[0]
        if first not in ("snapshot", "principal"):      # R2：快照与主体角色，仅此二源
            raise RegistrationFailed(
                f"SC-COMPILE-FAIL: {action_type} 条件表达式必须起于 "
                f"snapshot./principal.（R2），实得 '{first}'")
    agg = str(aggregate)
    effects = decl.get("effects") or {}
    if not isinstance(effects, dict):
        raise RegistrationFailed(
            f"SC-COMPILE-FAIL: {action_type} effects 须为映射（T24 副作用声明）")
    clash = set(effects) & set(decl.get("params") or {})
    if clash:
        raise RegistrationFailed(
            f"SC-COMPILE-FAIL: {action_type} effects 与 params 同字段重名 {sorted(clash)} "
            f"—— 状态效果只能由内核书写，不得同时接受调用方自报（双事实源）")
    # P-12：`dry_run: required` 是演练义务， MUST 有审计位承接，否则演练结果
    # 无从留痕 —— 声明字段从"注释"变为注册期可拒绝的一致性约束。
    if decl.get("dry_run") == "required" and decl.get("audit") != "required":
        raise RegistrationFailed(
            f"SC-COMPILE-FAIL: {action_type} dry_run=required 但 audit != required "
            f"—— 高风险 Action 的演练义务须可审计（P-12）")
    # 流名以声明为权威源；聚合名仅在声明缺省时兜底（不再硬编码覆盖声明）。
    stream = decl.get("stream") or f"domain:{agg}"
    declared_inputs = tuple(cond.get("snapshot_inputs", []) or [])
    return CompiledAction(
        action_type=action_type, aggregate=agg,
        structural=structural, conditional=expr,
        snapshot_inputs=declared_inputs,
        snapshot_keys=tuple(k for k in declared_inputs
                            if k.split(".", 1)[0] != "principal"),
        permissions=decl.get("permissions") or {},
        stream=stream,
        provenance=provenance,
        dry_run=bool((decl.get("dry_run") == "required")),
        effects=dict(effects))
def run_structural(checks: tuple[Check, ...], params: dict) -> None:
    """结构校验执行（内核提交时；KS-7.1 第一段）。"""
    for c in checks:
        val = params.get(c.target)
        if c.op == "exists" and (val is None or val == ""):
            raise ValueError(f"STRUCTURAL-FAIL: {c.target} 必填（exists）")
        if c.op == "max_len" and val is not None and len(str(val)) > int(c.arg):
            raise ValueError(f"STRUCTURAL-FAIL: {c.target} 长度 {len(str(val))} > {c.arg}")
