"""tests/negative/test_closure_no_session.py —— VER-6 / KS-2.4：
闭合域不含会话流 —— 决策流/会话流对常规写动作封闭（INV-5）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, StreamRuleViolation, DECISION_STREAM
VT = "2026-01-01T00:00:00+00:00"
def test_domain_action_cannot_write_decision_stream():
    store = EventStore()
    with pytest.raises(StreamRuleViolation):
        store.commit("VoidContract", DECISION_STREAM, 0, "VoidContract@1",
                     {"valid_time": VT, "contract_id": "c-1"}, "svc")
def test_domain_action_cannot_write_session_stream():
    store = EventStore()
    with pytest.raises(StreamRuleViolation):
        store.commit("VoidContract", "session:agent-1", 0, "VoidContract@1",
                     {"valid_time": VT, "contract_id": "c-1"}, "svc")
def test_closure_unconditional():
    """封闭不因 payload 伪装而打开（KS-2.4：流归属由 Action 类型决定，不可参数化）。"""
    store = EventStore()
    with pytest.raises(StreamRuleViolation):
        store.commit("VoidContract", DECISION_STREAM, 0, "VoidContract@1",
                     {"valid_time": VT, "contract_id": "c-1", "decision_like": True}, "svc")
