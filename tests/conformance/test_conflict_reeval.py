"""tests/conformance/test_conflict_reeval.py —— VER-3 / KS-1.4：
版本冲突必拒并触发完整重求值（非仅重试）；重求值有界（R8），超限 fail-closed。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, VersionConflict
from kernel.session import SessionChannel
from kernel.pipeline import Kernel, MAX_REEVAL
from kernel.errors import BudgetExceeded
from kernel.registration import compile_all
def _kernel():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_conflict_rejected_at_store_level():
    """同 expected_version 两次提交 → 第二次 VersionConflict（KS-1.4 第一半）。"""
    store = EventStore()
    p = {"valid_time": "2026-01-01T00:00:00+00:00", "order_id": "o1"}
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1", p, "svc")
    with pytest.raises(VersionConflict):
        store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1", p, "svc")
def test_kernel_reevals_on_conflict():
    """提交中途并发写入 → 内核完整重求值后成功（KS-1.4 第二半：重求值而非仅重试）。"""
    k = _kernel()
    real_commit = k.store.commit
    calls = {"n": 0}
    def racing(action_id, stream, expected_version, event_type, payload, principal,
               initiator=None):
        calls["n"] += 1
        if calls["n"] == 1:
            real_commit(action_id, stream, expected_version, event_type, payload,
                        principal, initiator)
            raise VersionConflict("并发写入（模拟）")            # 快照过期
        return real_commit(action_id, stream, expected_version, event_type, payload,
                           principal, initiator)
    k.store.commit = racing
    ev = k.submit("VoidContract", {"contract_id": "c-1"}, "svc", roles=("contract_steward",))
    assert calls["n"] >= 2 and ev is not None                   # 重求值后成功
def test_reeval_bounded_fail_closed():
    """竞争过热 → BudgetExceeded，不无限重试（R8 fail-closed）。"""
    k = _kernel()
    def always_conflict(*a, **kw):
        raise VersionConflict("永久冲突（模拟）")
    k.store.commit = always_conflict
    with pytest.raises(BudgetExceeded):
        k.submit("VoidContract", {"contract_id": "c-1"}, "svc", roles=("contract_steward",))
