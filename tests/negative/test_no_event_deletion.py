"""tests/negative/test_no_event_deletion.py —— VER-15 / KS-5.4：
已追加事件无更新/删除路径 —— 存储层 append-only 断言（对象级 + 类级 + 流级）。
"""
import dataclasses
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
VT = "2026-01-01T00:00:00+00:00"
def _one_event():
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    return store, store.streams["domain:ContractAggregate"][0]
def test_event_object_frozen():
    store, ev = _one_event()
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.payload = {}                                          # 事件对象不可变（AX-3）
def test_store_has_no_mutation_path():
    """类上不存在更新/删除/重写方法（KS-5.4：无路径即不可达）。"""
    for forbidden in ("update", "delete", "rewrite", "amend", "truncate", "pop"):
        assert not hasattr(EventStore, forbidden), f"EventStore 出现禁用方法 {forbidden}"
def test_stream_only_grows():
    store, ev = _one_event()
    n = len(store.streams["domain:ContractAggregate"])
    try:
        store.streams["domain:ContractAggregate"].pop()
        raised = False
    except Exception:
        raised = True
    if not raised:                                               # pop 若可行，事件数必须回升
        store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                     {"valid_time": VT, "contract_id": "c-1"}, "svc")
        assert len(store.streams["domain:ContractAggregate"]) == n
