#!/usr/bin/env python3
"""src/kernel/projection.py —— 投影与决策输入（P-16 / KS-2.2 / KS-2.5 / VER-26）。
投影 = 本体事件的只读物化视图（T17）：禁止做权威状态判断；
MUST 可重建 —— 删除物化后从本体事件日志全量重放（P-16 / VER-26）。
决策输入记录形式 =（投影标识, transaction_time）双引用的投影半边（KS-2.5 / P-16）。
重放纯度（KS-3.4）：reducer 须为纯函数 —— 实例侧 MUST 走受限解释器映射型 profile；
模板层 reducer 由调用方注册，本模块仅保证重放确定性（同事件序列 → 同状态）。
会话流禁止进入投影源（KS-2.2：不参与任何投影的权威重建；KS-2.4：闭包禁读会话内容）。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
class ProjectionViolation(Exception):
    """投影声明违规（P-16 fail-closed）。"""
class ProjectionNotMaterialized(ProjectionViolation):
    """物化不存在 —— 调用 rebuild() 重建（P-16：投影 MUST 可重建）。"""
class Projection:
    def __init__(self, store, name: str, reducer, streams: list[str] | None = None,
                 event_types: set[str] | None = None):
        self.store, self.name = store, name
        self.reducer = reducer                  # 纯函数 state, event -> state（KS-3.4）
        self.streams = set(streams) if streams else None
        self.event_types = set(event_types) if event_types else None
        self.materialized: dict | None = None   # None = 未物化 / 已删除
        self._last_tx: str | None = None
        if self.streams and any(s == "session" or s.startswith("session") for s in self.streams):
            raise ProjectionViolation("KS-2.2/2.4: 会话流禁止进入投影源")
    def rebuild(self) -> dict:
        """VER-26：删除物化 → 从本体事件日志全量重放 → 确定性恢复。"""
        events = [ev for stream in self.store.streams.values() for ev in stream]
        events.sort(key=lambda e: e.event_id)   # 全局单调序（KS-1.2）
        state: dict = {}
        last_tx = None
        for ev in events:
            if ev.stream_id == "session" or ev.stream_id.startswith("session"):
                continue                  # KS-2.2：会话流无条件排除（默认源亦不例外）
            if self.streams is not None and ev.stream_id not in self.streams:
                continue
            if self.event_types is not None and ev.event_type not in self.event_types:
                continue
            state = self.reducer(state, ev)
            last_tx = ev.transaction_time
        self.materialized = state
        self._last_tx = last_tx
        return state
    def discard(self):
        """删除物化（VER-26 item1 的模板层执行点）。"""
        self.materialized, self._last_tx = None, None
    def snapshot(self) -> dict:
        if self.materialized is None:
            raise ProjectionNotMaterialized(
                f"投影 {self.name} 未物化 —— 调用 rebuild()（P-16 / VER-26）")
        return self.materialized
    def decision_ref(self) -> dict:
        """（投影标识, transaction_time）双引用的投影半边（KS-2.5 / P-16 / INV-8）。"""
        if self.materialized is None:
            raise ProjectionNotMaterialized(f"投影 {self.name} 未物化，无法产生决策引用")
        return {"projection": self.name, "transaction_time": self._last_tx}
def resolve_decision_ref(store, ref: dict, projections: dict[str, "Projection"]) -> bool:
    """INV-4 双引用可解析（VER-26 item3）：投影标识在册 + transaction_time 可锚定日志。"""
    proj = projections.get(ref.get("projection"))
    if proj is None:
        return False
    tx = ref.get("transaction_time")
    if not tx:
        return False
    return any(ev.transaction_time == tx
               for stream in store.streams.values() for ev in stream)
