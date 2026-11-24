#!/usr/bin/env python3
"""src/kernel/pipeline.py —— 内核提交管线（KS-7.2 运行时 / VER-2 / VER-3）。
submit：能力核查 → 结构（Check AST）→ 条件（物化投影快照 + 受限解释器，
快照一次捕获 R2）→ 追加（VersionConflict → 重新执行上述整条评估管线再追加，重试有界防爆炸）。
"完整重求值"是 KS-1.4 / VER-3 的硬要求：冲突后不得只换 expected_version
重试追加，结构与条件必须在新的版本视图上重新评估（每轮各留 KS-3.3 审计）。
条件失败不追加（VER-2 顺序判据）；结构失败先于条件失败（评估顺序即管线）。
record_decision：决策三引用（投影标识, transaction_time, session_ref）→
会话半边可解析（KS-2.5 / INV-4）→ RecordDecision。
探测器路径求值预算见 detector.py（R8；超限 fail-visible）。
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import (UnregisteredAction, StructuralRejected, ConditionalRejected,
                           DecisionRefIncomplete, VersionConflict, BudgetExceeded,
                           PermissionDenied, SnapshotUnavailable, SnapshotIdentityMissing,
                           SnapshotEntityMissing)
from kernel.sc_compiler import run_structural
from interpreter.boolean_profile import eval_boolean
from interpreter.audit import record_evaluation
MAX_REEVAL = 3
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def materialize(store, act, params: dict) -> tuple[dict, dict | None]:
    """条件快照的物化投影半边（P-16 / KS-1.4）：每次评估在当轮版本视图上
    重放聚合流折叠权威状态，改口（谎报）在此拦截而非带入解释器。
    返回 (snapshot, contradiction)，三条回退路径必须分开（fail-closed）：
    - 模板层未生成 reducer / 未声明 identity → 回退 params（无权威可对照，已披露边界）；
    - 已声明身份但调用方未提供 → SNAPSHOT-IDENTITY-MISSING（不得用自报值冒充权威）；
    - 实体未投影 → 仅创建型动作（act.creates）可按 params 作初始观测，
      其余动作 SNAPSHOT-ENTITY-MISSING（禁止在未注册实体上直接审批/流转）；
    - 实体已投影：k∈ent 且 k∈claims 且不等 → contradiction；k∈ent 未 claim → 权威值。"""
    try:
        from generated import reducers as _g
    except ImportError:
        _g = None
    reduce = getattr(_g, "REDUCERS", {}).get(act.aggregate) if _g else None
    ident = getattr(_g, "IDENTITIES", {}).get(act.aggregate) if _g else None
    if reduce is None or not ident:
        return {k: params.get(k) for k in act.snapshot_keys}, None
    if ident not in params:
        raise SnapshotIdentityMissing(
            f"SNAPSHOT-IDENTITY-MISSING: {act.action_type} 未提供聚合标识 {ident} —— "
            f"身份是定位权威快照的唯一键，不得回退自报值（P-16 / KS-1.4）")
    state: dict = {}
    for ev in store.streams.get(act.stream) or []:
        state = reduce(state, ev)
    try:
        ent = state.get(params[ident])
    except TypeError as e:
        raise SnapshotIdentityMissing(
            f"SNAPSHOT-IDENTITY-MISSING: {ident} 不可哈希"
            f"（{type(params[ident]).__name__}）—— 无法定位权威快照（P-16）") from e
    if ent is None:
        if not act.creates:
            raise SnapshotEntityMissing(
                f"SNAPSHOT-ENTITY-MISSING: {act.action_type} 的目标实体 "
                f"{params[ident]!r} 在 {act.stream} 无权威投影 —— 非创建型动作不得以"
                f"自报值作为初始观测（P-16 / KS-1.4）；不追加（VER-2）")
        ent = {}
    contradiction = None
    snap: dict = {}
    for k in act.snapshot_keys:
        if k in ent:
            if k in params and params[k] != ent[k] and contradiction is None:
                contradiction = {"key": k, "claim": params[k], "authority": ent[k]}
            snap[k] = ent[k]                      # 权威值优先（谎报被拒后仍进审计 env）
        else:
            snap[k] = params.get(k)
    return snap, contradiction
class Kernel:
    """单一提交点。校验强度档位（kernel/assurance.py）只标注建议复核强度，
    不进入本类任何判定 —— 提交行为与档位声明无关（advisory，fail-closed 不变）。"""

    def __init__(self, store, session, compiled: dict):
        self.store, self.session, self.compiled = store, session, compiled
        self.interpreter_audit: list[dict] = []        # KS-3.3：评估审计留档
    def submit(self, action_type: str, params: dict, principal: str,
               roles: tuple[str, ...] = (), contexts: tuple[str, ...] = (),
               initiator: str | None = None):
        act = self.compiled.get(action_type)
        if act is None:
            raise UnregisteredAction(f"{action_type} 未注册 —— 不注册即不可执行（INV-1 / P-1）")
        required = set(act.permissions.get("roles", []))
        if required and not (required & set(roles)):
            # P-10/INV-4 单一写路径强制：声明了角色的 Action，角色证据缺失即拒
            # （fail-closed：未提供 == 无权，不默认放行）。主体→角色映射属平台
            # authN（T03 在本体之外），由调用方（如 AgentRuntime）出示。
            raise PermissionDenied(
                f"{action_type} 要求角色 {sorted(required)}，出示 {sorted(set(roles)) or '∅'}"
                " —— 权限在触达存储与评估之前拒绝（P-10 / INV-4 / VER-2 顺序）")
        stream = act.stream                            # 3 追加；版本冲突 → 完整重求值
        payload = dict(params)
        payload.setdefault("valid_time", _now())
        payload.update(act.effects)   # T24 副作用：状态效果由声明书写，非调用方自报
        for _ in range(MAX_REEVAL):
            self._evaluate(act, params, principal, roles, contexts)  # 1+2 每轮重跑（KS-1.4 / VER-3）
            try:
                return self.store.commit(action_type, stream,
                                         len(self.store.streams.get(stream, [])),
                                         f"{action_type}@1", payload, principal,
                                         initiator)
            except VersionConflict:
                continue                               # 下轮以新版本视图重新求值
        raise BudgetExceeded(f"重求值超过 {MAX_REEVAL} 次 —— 竞争过热，fail-closed（R8）")
    def _evaluate(self, act, params: dict, principal: str,
                  roles: tuple[str, ...], contexts: tuple[str, ...]):
        """一次完整评估：结构 → 条件。版本冲突时由 submit 重新调用本方法，
        而非仅以新 expected_version 重试追加（KS-1.4 / VER-3）。每轮都留
        KS-3.3 评估审计；条件快照经 materialize() 物化投影求值（P-16），
        调用方自报字段与权威投影矛盾 → SNAPSHOT-CONTRADICTION 拒绝。
        principal.* 来源为内核调用参数（平台 authN 出示），不取 params 自报：
        `principal.role` 兑现声明位，单角色退化为字符串以兼容既有表达式。"""
        try:
            run_structural(act.structural, params)     # 1 结构（KS-7.1 第一段）
        except ValueError as e:
            raise StructuralRejected(str(e)) from e
        if act.conditional:                            # 2 条件（快照一次捕获，R2）
            try:
                snap, contra = materialize(self.store, act, params)
            except SnapshotUnavailable as e:
                self.interpreter_audit.append(          # KS-3.3：物化失败也是评估
                    {**record_evaluation(act.conditional,
                                         {"snapshot": {"error": str(e)}}, False),
                     "expression": act.conditional, "snapshot": {},
                     "tx": _now(), "error": str(e)})
                raise
            if contra is not None:
                self.interpreter_audit.append({
                    "kind": "snapshot-contradiction",
                    "expression": act.conditional,
                    "snapshot": snap, "result": False, "tx": _now(),
                    **contra})                          # KS-3.3：拒绝也要留评估痕迹
                raise ConditionalRejected(
                    f"SNAPSHOT-CONTRADICTION: {contra['key']} 自报 {contra['claim']} ≠ "
                    f"权威投影 {contra['authority']} —— 条件对物化投影求值，"
                    f"改口无效（P-16 / KS-1.4）；不追加（VER-2）")
            principal_env = {
                "name": principal,
                "roles": tuple(roles),
                "role": roles[0] if len(roles) == 1 else tuple(roles),
                "contexts": tuple(contexts),
            }
            env = {"snapshot": {**snap, "principal": principal_env},
                   "principal": principal_env}
            try:
                ok = eval_boolean(act.conditional, env)
            except Exception as e:                     # 求值失败也是评估 —— 照记审计（KS-3.3）
                self.interpreter_audit.append(
                    {**record_evaluation(act.conditional, env, False),
                     "expression": act.conditional, "snapshot": snap,
                     "tx": _now(), "error": str(e)})
                raise
            self.interpreter_audit.append(
                {**record_evaluation(act.conditional, env, ok),
                 "expression": act.conditional, "snapshot": snap,
                 "tx": _now()})
            if not ok:
                raise ConditionalRejected(
                    f"条件校验未通过（KS-7.1 第二段）：{act.conditional}；不追加（VER-2）")
    def record_decision(self, projection_ref: str, transaction_time: str,
                        session_ref: str, principal: str, payload: dict | None = None):
        """决策记录：三引用齐备 + 会话半边可解析（KS-2.5 / P-16 / INV-4）。"""
        missing = [n for n, v in (("projection_ref", projection_ref),
                                  ("transaction_time", transaction_time),
                                  ("session_ref", session_ref)) if not v]
        if missing:
            raise DecisionRefIncomplete(f"决策三引用缺失: {missing}（KS-2.5 / P-16）")
        if not self.session.exists(session_ref):
            raise DecisionRefIncomplete(
                f"session_ref {session_ref} 不可解析 —— 会话通道无此引用（KS-2.5 / INV-4）")
        payload = dict(payload or {})
        payload.setdefault("valid_time", _now())
        payload.update({"projection_ref": projection_ref, "session_ref": session_ref,
                        "transaction_time": transaction_time})
        return self.store.commit("RecordDecision", "decision",
                                 len(self.store.streams.get("decision", [])),
                                 "Decision@1", payload, principal)
