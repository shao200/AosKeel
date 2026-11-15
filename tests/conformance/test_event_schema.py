"""tests/conformance/test_event_schema.py —— VER-1：事件 schema 八字段完备（KS-1.2）。
判据：任何事件缺字段即拒绝追加。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, StoreRejection
FIELDS = {"event_id", "stream_id", "expected_version", "event_type",
          "payload", "transaction_time", "action_id", "principal"}
def _commit(store, **kw):
    kw.setdefault("action_id", "RecordDecision")
    kw.setdefault("stream_id", "decision")
    kw.setdefault("expected_version", 0)
    kw.setdefault("event_type", "Decision@1")
    kw.setdefault("payload", {"valid_time": "2026-01-01T00:00:00+00:00",
                              "projection_ref": "proj-1", "session_ref": "sess-1"})
    kw.setdefault("principal", "steward")
    return store.commit(**kw)
def test_event_has_eight_fields():
    store = EventStore()
    ev = _commit(store)
    assert FIELDS <= set(vars(ev)), f"缺字段: {FIELDS - set(vars(ev))}"
def test_missing_valid_time_rejected():
    store = EventStore()
    payload = {"projection_ref": "p", "session_ref": "s"}      # 无 valid_time
    with pytest.raises(StoreRejection):
        _commit(store, payload=payload)
    assert store.streams.get("decision") is None
def test_event_type_requires_schema_version():
    store = EventStore()
    with pytest.raises(StoreRejection):
        _commit(store, event_type="Decision")                  # 无 @1
def test_valid_time_not_in_future():
    store = EventStore()
    with pytest.raises(StoreRejection):
        _commit(store, payload={"valid_time": "2999-01-01T00:00:00+00:00",
                                "projection_ref": "p", "session_ref": "s"})
