#!/usr/bin/env python3
"""src/kernel/detector.py —— 探测器（T25 / P-6 / T13 / INV-10）。
对时间限定不变量在投影上周期求值：真假取决于时间流逝，不进追加门控（KS-1.3）。
违规对象经内置 ActionType RaiseInvariantViolation 写入（P-7 / INV-10 / VER-23）——
探测器绝不直写；写路径必经 Action（INV-1）。
求值预算 ≤ R8（P-2）：探测器路径超限 → 产生预算超限类违规对象，禁止静默降级（R8 释义）。
修复绑定强制（INV-3 / P-6）：无 repair 的不变量注册即拒。
生命周期（P-7）：检测 → 分类 → 提案 → 修复 → 关闭；
同一不变量存在未关闭违规时不重复开启。
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import R8_BUDGET_LIMIT
from kernel.projection import Projection
VIOLATION_STREAM = "domain:invariant"
OPEN_STATUSES = {"detected", "classified", "repair_proposed", "repairing"}
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class Detector:
    def __init__(self, store, budget: int = R8_BUDGET_LIMIT):
        self.store = store
        self.budget = budget
        self.invariants: dict[str, dict] = {}
    def register(self, invariant_id: str, fn, projection: Projection,
                 repair: str, classification: str = "time_qualified"):
        """INV-3：不变量 MUST 以三元组声明（声明 + 违规语义 + 修复绑定）。"""
        if not repair:
            raise ValueError(f"REPAIR-BINDING-MISSING: {invariant_id} 无修复绑定（INV-3 / P-6）")
        self.invariants[invariant_id] = {"fn": fn, "projection": projection,
                                         "repair": repair, "classification": classification}
    def _open_violation_exists(self, invariant_id: str) -> bool:
        events = self.store.streams.get(VIOLATION_STREAM, [])
        latest = [ev for ev in events if ev.payload.get("invariant_ref") == invariant_id]
        if not latest:
            return False
        return latest[-1].payload.get("status") in OPEN_STATUSES   # P-7 生命周期
    def _raise(self, invariant_id: str, classification: str, violated_on: dict) -> object:
        payload = {"valid_time": _now(), "invariant_ref": invariant_id,
                   "classification": classification, "status": "detected",   # P-7 生命周期起点
                   "violated_on": violated_on,                    # 双引用半边（KS-2.5 / INV-8）
                   "repair": self.invariants[invariant_id]["repair"]}
        return self.store.commit("RaiseInvariantViolation", VIOLATION_STREAM,
                                 len(self.store.streams.get(VIOLATION_STREAM, [])),
                                 "InvariantViolation@1", payload, "detector")
    def run(self) -> list:
        """周期求值入口：返回本轮新写入的违规对象事件列表。"""
        raised = []
        now = _now()
        for iid, inv in self.invariants.items():
            proj = inv["projection"]
            if proj.materialized is None:
                proj.rebuild()
            state = proj.snapshot()
            if len(state) > self.budget:                       # R8 释义：fail-visible
                raised.append(self._raise(iid, "budget_exceeded",
                                          {"reason": f"投影规模 {len(state)} > 求值预算 {self.budget}（R8）"}))
                continue
            ok = inv["fn"](state, now)
            if not ok and not self._open_violation_exists(iid):
                raised.append(self._raise(iid, inv["classification"],
                                          proj.decision_ref()))
        return raised
