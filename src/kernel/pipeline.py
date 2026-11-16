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
                           PermissionDenied)
from kernel.sc_compiler import run_structural
from interpreter.boolean_profile import eval_boolean
from interpreter.audit import record_evaluation
MAX_REEVAL = 3
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def materialize(store, act, params: dict) -> tuple[dict, dict | None]:
    """条件快照的物化投影半边（P-16 / KS-1.4）：每次评估在当轮版本视图上
    重放聚合流折叠权威状态，改口（谎报）在此拦截而非带入解释器。
    返回 (snapshot, contradiction)：
    - 实体未投影 → 回退 params 作初始观测（首次观测无权威可对照）；
    - 实体已投影：k∈ent 且 k∈claims 且不等 → contradiction；k∈ent 未 claim → 权威值。
    无 reducer / 无 identity 的域（模板层未生成物）整体回退 params。"""
    try:
        from generated import reducers as _g
    except ImportError:
        _g = None
    reduce = getattr(_g, "REDUCERS", {}).get(act.aggregate) if _g else None
    ident = getattr(_g, "IDENTITIES", {}).get(act.aggregate) if _g else None
    if reduce is None or not ident or ident not in params:
        return {k: params.get(k) for k in act.snapshot_keys}, None
    state: dict = {}
    for ev in store.streams.get(act.stream) or []:
        state = reduce(state, ev)
    ent = state.get(params[ident]) or {}
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
    def __init__(self, store, session, compiled: dict):
        self.store, self.session, self.compiled = store, session, compiled
        self.interpreter_audit: list[dict] = []        # KS-3.3：评估审计留档
    def submit(self, action_type: str, params: dict, principal: str,
               roles: tuple[str, ...] = ()):
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
            self._evaluate(act, params, principal)     # 1+2 每轮重跑（KS-1.4 / VER-3）
            try:
                return self.store.commit(action_type, stream,
                                         len(self.store.streams.get(stream, [])),
                                         f"{action_type}@1", payload, principal)
            except VersionConflict:
                continue                               # 下轮以新版本视图重新求值
        raise BudgetExceeded(f"重求值超过 {MAX_REEVAL} 次 —— 竞争过热，fail-closed（R8）")
    def _evaluate(self, act, params: dict, principal: str):
        """一次完整评估：结构 → 条件。版本冲突时由 submit 重新调用本方法，
        而非仅以新 expected_version 重试追加（KS-1.4 / VER-3）。每轮都留
        KS-3.3 评估审计；条件快照经 materialize() 物化投影求值（P-16），
        调用方自报字段与权威投影矛盾 → SNAPSHOT-CONTRADICTION 拒绝。"""
        try:
            run_structural(act.structural, params)     # 1 结构（KS-7.1 第一段）
        except ValueError as e:
            raise StructuralRejected(str(e)) from e
        if act.conditional:                            # 2 条件（快照一次捕获，R2）
            snap, contra = materialize(self.store, act, params)
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
            env = {"snapshot": snap, "principal": {"role": principal}}
            try:
                ok = eval_boolean(act.conditional, env)
            except Exception as e:                     # 求值失败也是评估 —— 照记审计（KS-3.3）
                self.interpreter_audit.append(
                    {**record_evaluation(act.conditional, env, False), "error": str(e)})
                raise
            self.interpreter_audit.append(record_evaluation(act.conditional, env, ok))
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
