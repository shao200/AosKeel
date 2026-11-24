"""tests/conformance/test_saga_compensation.py —— P-9：Process 唯一合法出口 + 补偿 = Action。
判据：编排仅消费已注册 Action；步失败 → 已完成步逆序补偿 → 原异常继续抛出；
补偿本身是 Action（幂等声明）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.saga import SagaRunner
from kernel.errors import SagaInvalid, StructuralRejected
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _saga():
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    return k, SagaRunner.from_spec(k, ROOT / "spec")
def test_process_validated_against_compiled():
    k, saga = _saga()
    assert "ContractRenewal" in saga.processes
    with pytest.raises(SagaInvalid, match="未注册"):           # 编排仅消费已编译 Action
        SagaRunner(k, {"Bad": {"steps": [{"action": "GhostStep"}]}})
    with pytest.raises(SagaInvalid, match="补偿"):             # 补偿本身必须是已注册 Action
        SagaRunner(k, {"Bad": {"steps": [{"action": "ApproveContract"}],
                               "compensations": [{"for": "ApproveContract",
                                                  "action": "GhostUndo"}]}})
def test_unknown_process_rejected():
    _, saga = _saga()
    with pytest.raises(SagaInvalid, match="PROCESS-UNKNOWN"):
        saga.run("NotDeclared", {}, "agent")                   # P-9：出口 = Process 声明
def test_step_failure_triggers_compensation():
    """步失败 → 已完成步逆序补偿（补偿本身是 Action）→ 原异常继续抛出。"""
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    k.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000},
             "contract_steward", roles=("contract_steward",))   # 实体须先进入权威投影
    saga = SagaRunner(k, {"TwoStep": {
        "steps": [{"action": "ApproveContract"}, {"action": "ApproveContract"}],
        "compensations": [{"for": "ApproveContract", "action": "VoidContract",
                           "idempotent": True}]}})
    calls = {"n": 0}
    real_submit = k.submit
    def flaky(action_type, params, principal, roles=()):
        calls["n"] += 1
        if calls["n"] == 2:
            return real_submit(action_type, dict(params, contract_id=None), principal, roles=roles)
        return real_submit(action_type, params, principal, roles=roles)     # 第二步结构失败
    k.submit = flaky
    with pytest.raises(StructuralRejected):
        saga.run("TwoStep", PARAMS, "contract_steward", roles=("contract_steward",))
    assert [c["action"] for c in saga.compensation_log] == ["VoidContract"]  # 补偿已执行
    assert k.store.streams["domain:ContractAggregate"][-1].action_id == "VoidContract"
def test_compensation_is_registered_action():
    """补偿本身是 Action：VoidContract 走同一管线（INV-1），带幂等声明（P-9）。"""
    k, _ = _saga()
    act = k.compiled["VoidContract"]
    assert act.provenance == "SPEC-2026-014"
    import yaml
    decl = yaml.safe_load((ROOT / "spec/ontology/actions/VoidContract.action.yaml")
                          .read_text(encoding="utf-8"))
    assert decl["compensation"] is True and decl["idempotent"] is True
