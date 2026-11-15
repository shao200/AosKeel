#!/usr/bin/env python3
"""src/kernel/pipeline.py —— 内核提交管线（KS-7.2 运行时 / VER-2 / VER-3）。
submit：能力核查 → 结构（Check AST）→ 条件（受限解释器，快照一次捕获 R2）→
追加（VersionConflict → 完整重求值整条管线，重试有界防爆炸）。
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
                           DecisionRefIncomplete, VersionConflict, BudgetExceeded)
from kernel.sc_compiler import run_structural
from interpreter.boolean_profile import eval_boolean
from interpreter.audit import record_evaluation
MAX_REEVAL = 3
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class Kernel:
    def __init__(self, store, session, compiled: dict):
        self.store, self.session, self.compiled = store, session, compiled
        self.interpreter_audit: list[dict] = []        # KS-3.3：评估审计留档
    def submit(self, action_type: str, params: dict, principal: str):
        act = self.compiled.get(action_type)
        if act is None:
            raise UnregisteredAction(f"{action_type} 未注册 —— 不注册即不可执行（INV-1 / P-1）")
        try:
            run_structural(act.structural, params)     # 1 结构（KS-7.1 第一段）
        except ValueError as e:
            raise StructuralRejected(str(e)) from e
        if act.conditional:                            # 2 条件（快照一次捕获，R2）
            snap_keys = [k for k in act.snapshot_inputs if not k.startswith("principal")]
            env = {"snapshot": {k: params.get(k) for k in snap_keys},
                   "principal": {"role": principal}}
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
        stream = act.stream                            # 3 追加；版本冲突 → 完整重求值
        payload = dict(params)
        payload.setdefault("valid_time", _now())
        for _ in range(MAX_REEVAL):
            try:
                return self.store.commit(action_type, stream,
                                         len(self.store.streams.get(stream, [])),
                                         f"{action_type}@1", payload, principal)
            except VersionConflict:
                continue                               # KS-1.4：重求值而非仅重试
        raise BudgetExceeded(f"重求值超过 {MAX_REEVAL} 次 —— 竞争过热，fail-closed（R8）")
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
