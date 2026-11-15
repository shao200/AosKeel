"""tests/conformance/test_decision_refs.py —— VER-7 / KS-2.5 / INV-4：
决策三引用强制齐备；会话半边必须可解析（闭合域内可核对）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, DECISION_STREAM
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import DecisionRefIncomplete
from kernel.registration import compile_all
def _kernel():
    store, session = EventStore(), SessionChannel()
    return Kernel(store, session, compile_all())
def test_decision_missing_ref_rejected():
    store, session = EventStore(), SessionChannel()
    k = Kernel(store, session, {})
    with pytest.raises(DecisionRefIncomplete, match="三引用缺失"):
        k.record_decision("proj-1", "2026-01-01T00:00:00+00:00", "", "agent-1")
def test_unresolvable_session_ref_rejected():
    store, session = EventStore(), SessionChannel()
    k = Kernel(store, session, {})
    with pytest.raises(DecisionRefIncomplete, match="不可解析"):
        k.record_decision("proj-1", "2026-01-01T00:00:00+00:00", "sess-nope", "agent-1")
def test_valid_decision_writes_all_three_refs():
    store, session = EventStore(), SessionChannel()
    k = Kernel(store, session, {})
    ref = session.append("agent-1", {"text": "决议依据"})["ts"]
    k.record_decision("proj-1", "2026-01-01T00:00:00+00:00", ref, "agent-1")
    ev = store.streams[DECISION_STREAM][-1]
    assert ev.payload["projection_ref"] == "proj-1"
    assert ev.payload["transaction_time"] and ev.payload["session_ref"] == ref
