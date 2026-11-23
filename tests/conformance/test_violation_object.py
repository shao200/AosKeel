"""tests/conformance/test_violation_object.py —— VER-23：InvariantViolation 对象化（P-7 / INV-10）。
判据：探测器写路径必经 Action；违规对象落在 domain:invariant 流；
生命周期起点 detected + 修复绑定在案；同不变量不重复开启；预算超限 fail-visible（R8）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, StreamRuleViolation, UnknownAction
from kernel.projection import Projection, resolve_decision_ref
from kernel.detector import Detector, VIOLATION_STREAM
DECISION_PAYLOAD = lambda status: {"valid_time": "2026-01-01T00:00:00+00:00",
                                   "projection_ref": "proj-1", "session_ref": "sess-1",
                                   "status": status}
def reducer(state, ev):
    state.setdefault("decisions", []).append({"status": ev.payload.get("status")})
    return state
def _setup(store, statuses=("open",)):
    for i, s in enumerate(statuses):
        store.commit("RecordDecision", "decision", i, "Decision@1", DECISION_PAYLOAD(s), "agent-1")
    proj = Projection(store, "decisions", reducer, entity_key="projection_ref")
    proj.rebuild()
    return proj
def test_violation_objectized_via_action():
    store = EventStore()
    proj = _setup(store)
    det = Detector(store)
    det.register("INV-STALE", lambda state, now: False, proj, repair="RepairStale")
    raised = det.run()
    assert len(raised) == 1
    ev = store.streams[VIOLATION_STREAM][0]
    assert ev.action_id == "RaiseInvariantViolation"          # 写路径必经 Action（INV-1/VER-23）
    assert ev.payload["status"] == "detected"                 # P-7 生命周期起点
    assert ev.payload["invariant_ref"] == "INV-STALE"
    assert ev.payload["repair"] == "RepairStale"              # INV-3 修复绑定
def test_violation_double_reference_resolvable():
    store = EventStore()
    proj = _setup(store)
    det = Detector(store)
    det.register("INV-STALE", lambda state, now: False, proj, repair="RepairStale")
    det.run()
    ev = store.streams[VIOLATION_STREAM][0]
    assert resolve_decision_ref(store, ev.payload["violated_on"], {"decisions": proj})
    assert not resolve_decision_ref(store, {"projection": "ghost", "transaction_time": "x"},
                                    {"decisions": proj})
def test_no_duplicate_open_violations():
    store = EventStore()
    proj = _setup(store)
    det = Detector(store)
    det.register("INV-STALE", lambda state, now: False, proj, repair="RepairStale")
    det.run(); det.run()
    assert len(store.streams[VIOLATION_STREAM]) == 1          # P-7：不重复开启
def test_violation_type_guard():
    """INV-10：违规对象仅可经 RaiseInvariantViolation 写入。"""
    store = EventStore()
    with pytest.raises(StreamRuleViolation):
        store.commit("RecordDecision", VIOLATION_STREAM, 0, "InvariantViolation@1",
                     {"valid_time": "2026-01-01T00:00:00+00:00", "invariant_ref": "X",
                      "status": "detected"}, "agent-1")
def test_budget_exceeded_fail_visible():
    """R8 释义：探测器路径超限 → 预算超限类违规对象，禁止静默降级。"""
    store = EventStore()
    proj = _setup(store, statuses=("open", "open"))
    det = Detector(store, budget=0)
    det.register("INV-BIG", lambda state, now: True, proj, repair="RepairBig")
    raised = det.run()
    assert raised[0].payload["classification"] == "budget_exceeded"
    assert "R8" in raised[0].payload["violated_on"]["reason"]
