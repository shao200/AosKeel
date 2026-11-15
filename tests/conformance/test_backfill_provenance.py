"""tests/conformance/test_backfill_provenance.py —— VER-17 / KS-6.3：
每条事件可溯源至能力清单（action_id ∈ write_actions；GOV-2.2 的运行时形态），
内核生成的违规对象与决策事件同样携带出处。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.projection import Projection
from kernel.detector import Detector
VT = "2026-01-01T00:00:00+00:00"
def _registered_action_ids():
    from kernel.registration import load_caps
    return {a["id"] for a in load_caps()["write_actions"]}
def test_committed_events_carry_capability_provenance():
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    ev = store.streams["domain:ContractAggregate"][0]
    assert ev.action_id in _registered_action_ids()              # 出处 = 能力（GOV-2.2）
def test_violation_events_traceable():
    """探测器写违规对象 → action_id = RaiseInvariantViolation（能力清单内建）。"""
    store = EventStore()
    proj = Projection(store, "contract", lambda s, e: {**(s or {}), e.payload["contract_id"]: "voided"},
                      streams=["domain:ContractAggregate"])
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    det = Detector(store)
    det.register("INV-CONTRACT-VOIDED", lambda state, now: False, proj, repair="GOV-3")
    det.run()
    ev = store.streams["domain:invariant"][-1]
    assert ev.action_id == "RaiseInvariantViolation" and ev.action_id in _registered_action_ids()
