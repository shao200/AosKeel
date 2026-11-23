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
_UNSET = object()   # entity_key 未声明哨兵：构造期即 fail-closed（ENTITY-KEY-MISSING）
class Projection:
    def __init__(self, store, name: str, reducer, streams: list[str] | None = None,
                 event_types: set[str] | None = None, entity_key=_UNSET):
        self.store, self.name = store, name
        self.reducer = reducer                  # 纯函数 state, event -> state（KS-3.4）
        self.streams = set(streams) if streams else None
        self.event_types = set(event_types) if event_types else None
        # 显式实体归属：payload 中的标识字段名（声明驱动：聚合 identity / 域画像 entity_key）。
        # 必填 —— 禁止"payload 值匹配"的隐式归属（fail-closed）。
        if not isinstance(entity_key, str) or not entity_key.strip():
            raise ProjectionViolation(
                "ENTITY-KEY-MISSING: 投影必须声明实体标识属性（禁止隐式归属）")
        self.entity_key = entity_key
        self.materialized: dict | None = None   # None = 未物化 / 已删除
        self._last_tx: str | None = None
        self._watermark: int | None = None      # 物化时的源流推进水位（最大 event_id）
        if self.streams and any(s == "session" or s.startswith("session") for s in self.streams):
            raise ProjectionViolation("KS-2.2/2.4: 会话流禁止进入投影源")
    def _scanned_events(self) -> list:
        """投影源事件（按全局 event_id 序，KS-1.2）：会话流无条件排除（KS-2.2）。"""
        events = [ev for stream, evs in self.store.streams.items()
                  if self.streams is None or stream in self.streams
                  for ev in evs
                  if not (ev.stream_id == "session"
                          or ev.stream_id.startswith("session"))
                  and (self.event_types is None
                       or ev.event_type in self.event_types)]
        events.sort(key=lambda e: e.event_id)   # 全局单调序（KS-1.2）
        return events
    def head(self) -> int:
        """源流当前推进水位（最大 event_id；0 = 无事件）。"""
        events = self._scanned_events()
        return events[-1].event_id if events else 0
    def entity_head(self, entity) -> int:
        """该实体当前水位（最近一次触及它的事件 event_id；0 = 从未触及）。

        归属只认声明标识字段（entity_key）：其它字段即便持有相同值也不制造水位，
        防止同名字段造成误归属。不做缓存，每次读源，因此不会因为"未 rebuild"而漏报推进。
        """
        target = str(entity)
        for ev in reversed(self._scanned_events()):
            if str(ev.payload.get(self.entity_key)) == target:
                return ev.event_id
        return 0
    def rebuild(self) -> dict:
        """VER-26：删除物化 → 从本体事件日志全量重放 → 确定性恢复。"""
        scanned = self._scanned_events()
        state: dict = {}
        for ev in scanned:
            state = self.reducer(state, ev)
        self.materialized = state
        self._last_tx = scanned[-1].transaction_time if scanned else None
        self._watermark = scanned[-1].event_id if scanned else 0
        return state
    def discard(self):
        """删除物化（VER-26 item1 的模板层执行点）。"""
        self.materialized, self._last_tx, self._watermark = None, None, None
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
    def stamp(self, entity=None) -> dict:
        """渲染时戳：决策引用 + 物化水位；给定实体时附该实体的独立水位。

        实体水位与流级水位并存：选择守卫用实体水位（跨实体推进不误伤），
        整体新鲜度仍用流级水位（P-16 重建以整条流为单位）。
        """
        if self.materialized is None:
            raise ProjectionNotMaterialized(f"投影 {self.name} 未物化，无法产生渲染时戳")
        stamp = {"projection": self.name, "transaction_time": self._last_tx,
                 "watermark": self._watermark}
        if entity is not None:
            stamp["entity_watermark"] = self.entity_head(entity)
        return stamp
    def is_fresh(self) -> bool:
        """物化水位是否仍等于源流当前水位（False = 源流已推进，需 rebuild）。"""
        return self.materialized is not None and self._watermark == self.head()
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
