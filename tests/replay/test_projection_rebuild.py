"""tests/replay/test_projection_rebuild.py —— VER-26：投影可重建（P-16 / KS-2.2 / INV-4）。
判据：删除物化 → 全量重放 → 状态确定性恢复；会话通道（物理分离存储）不参与
权威重建；（投影标识, transaction_time）双引用全部可解析。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.projection import (Projection, ProjectionNotMaterialized,
                               resolve_decision_ref, ProjectionViolation)
def reducer(state, ev):
    state.setdefault("decisions", []).append(
        {"status": ev.payload.get("status"), "tx": ev.transaction_time})
    return state
def _store_with_events(n=3):
    store = EventStore()
    for i in range(n):
        store.commit("RecordDecision", "decision", i, "Decision@1",
                     {"valid_time": "2026-01-01T00:00:00+00:00",
                      "projection_ref": "proj-1", "session_ref": f"sess-{i}",
                      "status": "open" if i < 2 else "closed"}, "agent-1")
    return store
def test_rebuild_deterministic():
    store = _store_with_events()
    proj = Projection(store, "decisions", reducer)
    s1 = proj.rebuild()
    s2 = proj.rebuild()
    assert s1 == s2 and len(s1["decisions"]) == 3
    assert [d["status"] for d in s1["decisions"]] == ["open", "open", "closed"]
def test_discard_then_rebuild_restores_state():
    """VER-26 item1-2：删除任一物化 → 全量重放 → 逐属性一致。"""
    store = _store_with_events()
    proj = Projection(store, "decisions", reducer)
    before = proj.rebuild()
    proj.discard()
    with pytest.raises(ProjectionNotMaterialized):
        proj.snapshot()
    after = proj.rebuild()
    assert after == before                                     # 全量重放恢复，逐属性一致
def test_session_channel_does_not_reach_projection():
    """KS-2.2：会话通道是独立存储 —— 追加会话事件不影响任何投影。"""
    store = _store_with_events(2)
    ch = SessionChannel()
    ch.append("agent-1", {"observed": "noise"})
    proj = Projection(store, "decisions", reducer)
    state = proj.rebuild()
    assert len(state["decisions"]) == 2                        # 会话事件未进入投影
    assert proj.decision_ref()["transaction_time"] == \
        store.streams["decision"][-1].transaction_time         # 双引用锚定本体半边（KS-2.5）
def test_session_stream_rejected_as_source():
    store = _store_with_events()
    with pytest.raises(ProjectionViolation):
        Projection(store, "leaky", reducer, streams=["session"])   # KS-2.4 闭包禁读会话（防御纵深）
def test_double_references_resolvable():
    """VER-26 item3 / INV-4：决策事件双引用全部可解析。"""
    store = _store_with_events()
    proj = Projection(store, "decisions", reducer)
    proj.rebuild()
    assert resolve_decision_ref(store, proj.decision_ref(), {"decisions": proj})
    for ev in store.streams["decision"]:
        assert ev.payload["projection_ref"] and ev.payload["session_ref"]   # KS-2.5
