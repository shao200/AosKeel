"""tests/replay/test_merge_replay.py —— VER-24：归并史可重放（P-8）。
判据：≥3 组归并声明 → 两条独立计算路径（投影引擎 vs 归并注册表重放）
终态逐属性一致；重放路径纯（无谓词、无宿主函数）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, StoreRejection
from kernel.projection import Projection
from kernel.merge import MergeRegistry, MERGE_STREAM
def identity_reducer(state, ev):
    if ev.event_type.startswith("MergeDeclared@"):
        state[ev.payload["absorbed"]] = ev.payload["canonical"]    # 纯映射（R11）
    return state
def _registry_with_merges(n=3):
    store = EventStore()
    reg = MergeRegistry(store)
    for i in range(n):
        reg.declare(f"ident-canonical", f"ident-old-{i}", "identity-steward")
    return store, reg
def test_double_path_replay_matches():
    """VER-24 item1 模板层判据：两条独立路径终态逐属性一致。"""
    store, reg = _registry_with_merges()
    proj = Projection(store, "identity", identity_reducer)
    assert reg.verify_replay({"identity": proj}) is True
    assert reg.replay() == {"ident-old-0": "ident-canonical",
                            "ident-old-1": "ident-canonical",
                            "ident-old-2": "ident-canonical"}
def test_replay_deterministic():
    store, reg = _registry_with_merges()
    assert reg.replay() == reg.replay()
def test_self_merge_forbidden():
    store = EventStore()
    reg = MergeRegistry(store)
    with pytest.raises(StoreRejection, match="SELF-MERGE-FORBIDDEN"):
        reg.declare("ident-a", "ident-a", "identity-steward")   # P-8：自归并必拒
def test_merge_type_guard():
    """INV-13：归并声明仅可经 DeclareIdentityMerge 写入。"""
    store = EventStore()
    with pytest.raises(StoreRejection, match="INV-13"):
        store.commit("RecordDecision", MERGE_STREAM, 0, "MergeDeclared@1",
                     {"valid_time": "2026-01-01T00:00:00+00:00",
                      "canonical": "a", "absorbed": "b"}, "agent-1")
