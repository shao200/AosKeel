"""tests/conformance/test_repair_binding.py —— VER-22 / P-6 / INV-3：
修复绑定注册即强制；违规对象携带 repair 引用；生命周期 detected → … → closed。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.projection import Projection
from kernel.detector import Detector, VIOLATION_STREAM
VT = "2026-01-01T00:00:00+00:00"
def _proj(store):
    return Projection(store, "contract",
                      lambda s, e: {**(s or {}), e.payload["contract_id"]: "voided"},
                      entity_key="contract_id", streams=["domain:ContractAggregate"])
def test_registration_without_repair_refused():
    det = Detector(EventStore())
    with pytest.raises(ValueError, match="REPAIR-BINDING-MISSING"):
        det.register("INV-X", lambda state, now: True, _proj(EventStore()), repair="")
def test_violation_carries_repair_ref_and_lifecycle():
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    det = Detector(store)
    det.register("INV-CONTRACT-VOIDED", lambda state, now: False, _proj(store), repair="GOV-3")
    raised = det.run()
    assert len(raised) == 1
    ev = store.streams[VIOLATION_STREAM][0]
    assert ev.payload["repair"] == "GOV-3"                       # 修复绑定入违规对象（INV-3）
    assert ev.payload["status"] == "detected"                    # P-7 生命周期起点
def test_no_duplicate_open_violation():
    """同一不变量存在未关闭违规时不重复开启（P-7）。"""
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    det = Detector(store)
    det.register("INV-CONTRACT-VOIDED", lambda state, now: False, _proj(store), repair="GOV-3")
    det.run(); n = len(store.streams[VIOLATION_STREAM])
    det.run()
    assert len(store.streams[VIOLATION_STREAM]) == n             # 未关闭 → 不重复开启
