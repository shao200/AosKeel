"""tests/conformance/test_decision_stream.py —— VER-33 / VER-7 / VER-4 / VER-5：
决策事件仅经 RecordDecision 出现于决策流（KS-2.6），双引用完整（KS-2.5），
会话通道物理分离且强制主体（KS-2.2 / KS-2.3 / INV-8）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import (EventStore, StoreRejection, StreamRuleViolation,
                          UnknownAction, DECISION_STREAM)
from kernel.session import SessionChannel
from kernel.errors import PrincipalRequired
DECISION_PAYLOAD = {"valid_time": "2026-01-01T00:00:00+00:00",
                    "projection_ref": "proj-1", "session_ref": "sess-1"}
def test_decision_event_requires_double_reference():
    store = EventStore()
    bad = {k: v for k, v in DECISION_PAYLOAD.items() if k != "session_ref"}
    with pytest.raises(StoreRejection, match="DECISION-REFS-MISSING"):
        store.commit("RecordDecision", DECISION_STREAM, 0, "Decision@1", bad, "agent-1")
    store.commit("RecordDecision", DECISION_STREAM, 0, "Decision@1", DECISION_PAYLOAD, "agent-1")
    ev = store.streams[DECISION_STREAM][0]
    assert ev.payload["projection_ref"] and ev.payload["session_ref"]
def test_decision_stream_only_via_recorddecision():
    store = EventStore()
    with pytest.raises(UnknownAction):
        store.commit("DirectUpsert", DECISION_STREAM, 0, "X@1", DECISION_PAYLOAD, "agent-1")
def test_stream_separation():
    store = EventStore()
    with pytest.raises(StreamRuleViolation):
        store.commit("RecordDecision", "domain:orders", 0, "Decision@1", DECISION_PAYLOAD, "agent-1")
    with pytest.raises(StreamRuleViolation):
        store.commit("RecordDecision", "session", 0, "Decision@1", DECISION_PAYLOAD, "agent-1")
def test_session_channel_principal_required():
    """KS-2.3 / INV-8：会话事件逐条强制主体归属。"""
    ch = SessionChannel()
    with pytest.raises(PrincipalRequired):
        ch.append("", {"observed": "x"})
    ch.append("agent-1", {"observed": "x"})
    assert ch.read_all()[0]["principal"] == "agent-1"
def test_session_channel_physically_separate():
    """VER-4 / KS-2.2：另一对象 = 另一存储 —— 无任何共享结构。"""
    store, ch = EventStore(), SessionChannel()
    ch.append("agent-1", {"observed": "x"})
    assert "session" not in store.streams          # 会话不入本体日志
    assert ch._log is not store.audit              # 两个独立存储对象
