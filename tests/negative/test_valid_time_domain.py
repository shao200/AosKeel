"""tests/negative/test_valid_time_domain.py —— VER-16 / KS-6.1：
valid_time ≤ transaction_time 域约束；缺 valid_time 即 SCHEMA-FAIL（KS-1.2 八字段）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.errors import ValidTimeViolation, StoreRejection
def test_valid_time_after_transaction_time_rejected():
    store = EventStore()
    with pytest.raises(ValidTimeViolation, match="VALID-TIME-DOMAIN"):
        store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                     {"valid_time": "2999-01-01T00:00:00+00:00",       # 远超事务时间
                      "contract_id": "c-1"}, "svc")
def test_missing_valid_time_is_schema_fail():
    store = EventStore()
    with pytest.raises(StoreRejection, match="SCHEMA-FAIL"):
        store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                     {"contract_id": "c-1"}, "svc")             # 八字段缺一（KS-1.2）
def test_valid_boundary_accepted():
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": "2026-01-01T00:00:00+00:00", "contract_id": "c-1"}, "svc")
    assert len(store.streams["domain:ContractAggregate"]) == 1
