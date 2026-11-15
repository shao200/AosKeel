"""tests/conformance/test_stream_separation.py —— VER-4 / KS-2.1：
各流版本链独立；跨流的过期版本号必拒；一流的追加不影响他流预期版本。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, VersionConflict
VT = "2026-01-01T00:00:00+00:00"
def test_streams_have_independent_version_chains():
    store = EventStore()
    p = {"valid_time": VT, "contract_id": "c-1"}
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1", p, "svc")
    store.commit("VoidContract", "domain:IdentityAggregate", 0, "VoidContract@1", p, "svc")
    assert len(store.streams["domain:ContractAggregate"]) == 1
    assert len(store.streams["domain:IdentityAggregate"]) == 1
    # 各流版本自 0 起独立计数
    store.commit("VoidContract", "domain:ContractAggregate", 1, "VoidContract@1", p, "svc")
    assert len(store.streams["domain:ContractAggregate"]) == 2
def test_cross_stream_stale_version_rejected():
    """流 B 的版本号误用于流 A → 冲突必拒（流间无共享计数器）。"""
    store = EventStore()
    p = {"valid_time": VT, "contract_id": "c-1"}
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1", p, "svc")
    store.commit("VoidContract", "domain:ContractAggregate", 1, "VoidContract@1", p, "svc")
    with pytest.raises(VersionConflict):
        store.commit("VoidContract", "domain:IdentityAggregate", 2, "VoidContract@1", p, "svc")
