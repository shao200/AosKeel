"""tests/conformance/test_pipeline_order.py —— VER-2 / VER-3：提交管线顺序与冲突重求值。
判据：结构失败先于条件失败（评估顺序即管线，KS-7.2）；条件失败不追加；
版本冲突触发完整重求值而非仅重试（KS-1.4）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.store import EventStore, VersionConflict
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import StructuralRejected, ConditionalRejected, UnregisteredAction
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _kernel():
    store = EventStore()
    return Kernel(store, SessionChannel(), compile_all()), store
def test_structural_before_conditional():
    """VER-2：结构失败即停，不触达条件评估。"""
    k, store = _kernel()
    with pytest.raises(StructuralRejected):
        k.submit("ApproveContract", {"status": "pending"}, "contract_steward", roles=("contract_steward",))  # 缺 contract_id
    assert "domain:ContractAggregate" not in store.streams
def test_conditional_failure_appends_nothing():
    """VER-2：条件失败 → 不追加任何事件。"""
    k, store = _kernel()
    with pytest.raises(ConditionalRejected):
        k.submit("ApproveContract", dict(PARAMS, status="void"), "contract_steward", roles=("contract_steward",))
    assert "domain:ContractAggregate" not in store.streams
    assert k.interpreter_audit[-1]["result"] is False          # KS-3.3：评估留档
def test_happy_path_appends_via_capability():
    k, store = _kernel()
    ev = k.submit("ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))
    assert ev.stream_id == "domain:ContractAggregate"
    assert ev.action_id == "ApproveContract"
    assert ev.payload["valid_time"] <= ev.transaction_time     # KS-6.1
def test_unregistered_action_rejected():
    k, _ = _kernel()
    with pytest.raises(UnregisteredAction):
        k.submit("NukeEverything", {}, "agent")                # INV-1：不注册即不可执行
def test_version_conflict_full_reeval():
    """VER-3：版本冲突必须完整重求值（KS-1.4）—— 管线自动以新版本重试成功。"""
    k, store = _kernel()
    store.commit("ApproveContract", "domain:ContractAggregate", 0, "ApproveContract@1",
                 dict(PARAMS, valid_time="2026-01-01T00:00:00+00:00"), "other")   # 抢先写入
    ev = k.submit("ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))   # 管线重算版本 → 成功
    assert ev.expected_version == 1
def test_stale_expected_version_rejected():
    """VER-3：绕过管线以陈旧版本直写 → 版本冲突必拒。"""
    k, store = _kernel()
    k.submit("ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))
    with pytest.raises(VersionConflict):
        store.commit("ApproveContract", "domain:ContractAggregate", 0, "ApproveContract@1",
                     dict(PARAMS, valid_time="2026-01-01T00:00:00+00:00"), "agent-2")
