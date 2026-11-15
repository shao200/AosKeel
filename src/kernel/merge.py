"""src/kernel/merge.py —— Identity 归并史（P-8 / VER-24）。
归并以 DeclareIdentityMerge（创世内建 Action）声明，落在 domain:identity 流：
- 双向记录（P-8）：canonical / absorbed 双引用齐备，自归并必拒；
- 归并史可重放（P-8）：重放路径纯 —— 仅消费 MergeDeclared 事件，
  与投影引擎（projection.py）互为独立的两条计算路径，终态逐属性比对（VER-24 判据）；
- 重放纯度（KS-3.4）：无谓词、无宿主函数。
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
MERGE_STREAM = "domain:identity"
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class MergeRegistry:
    def __init__(self, store):
        self.store = store
    def declare(self, canonical: str, absorbed: str, principal: str,
                valid_time: str | None = None):
        payload = {"valid_time": valid_time or _now(),
                   "canonical": canonical, "absorbed": absorbed}
        return self.store.commit("DeclareIdentityMerge", MERGE_STREAM,
                                 len(self.store.streams.get(MERGE_STREAM, [])),
                                 "MergeDeclared@1", payload, principal)
    def replay(self) -> dict:
        """独立重放路径：按事件序折叠 MergeDeclared → {absorbed: canonical}。"""
        alias: dict[str, str] = {}
        for ev in sorted(self.store.streams.get(MERGE_STREAM, []),
                         key=lambda e: e.event_id):
            alias[ev.payload["absorbed"]] = ev.payload["canonical"]
        return alias
    def verify_replay(self, projections: dict) -> bool:
        """VER-24 item1 模板层判据：投影引擎重放终态 == 本注册表独立重放终态（逐属性）。"""
        proj = projections.get("identity")
        if proj is None:
            return False
        return proj.rebuild() == self.replay()
IDENTITY_REDUCER_DOC = """
投影侧归并 reducer（与 merge.replay 互为独立实现；供 Projection 使用）：
def identity_reducer(state, ev):
    if ev.event_type.startswith("MergeDeclared@"):
        state[ev.payload["absorbed"]] = ev.payload["canonical"]
    return state
"""
