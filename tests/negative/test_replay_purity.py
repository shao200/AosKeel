"""tests/negative/test_replay_purity.py —— VER-10 / KS-3.4 / R11：
重放纯性 —— 投影重建确定性（同事件流同终态），且不修改事件流本身。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.projection import Projection
VT = "2026-01-01T00:00:00+00:00"
def _void(state, ev):
    return {**(state or {}), ev.payload["contract_id"]: "voided"}
def _store_with_events():
    store = EventStore()
    for i, cid in enumerate(["c-1", "c-2"]):
        store.commit("VoidContract", "domain:ContractAggregate", i, "VoidContract@1",
                     {"valid_time": VT, "contract_id": cid}, "svc")
    return store
def test_rebuild_deterministic():
    store = _store_with_events()
    p = Projection(store, "contract", _void, entity_key="contract_id",
                   streams=["domain:ContractAggregate"])
    p.rebuild(); s1 = p.snapshot()
    p.discard(); p.rebuild(); s2 = p.snapshot()
    assert s1 == s2                                              # 同流同终态（确定性）
def test_replay_does_not_mutate_stream():
    store = _store_with_events()
    events = store.streams["domain:ContractAggregate"]
    before = [(e.stream_id, e.event_id, e.transaction_time, dict(e.payload)) for e in events]
    p = Projection(store, "contract", _void, entity_key="contract_id",
                   streams=["domain:ContractAggregate"])
    p.rebuild()
    after = [(e.stream_id, e.event_id, e.transaction_time, dict(e.payload)) for e in events]
    assert before == after                                       # 重放不修改事件流（R11 纯性）
