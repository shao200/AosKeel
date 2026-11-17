"""tests/conformance/test_declaration_execution.py —— P1 声明执行点回归。
判据：编译接受的字段必须有消费者（或注册期拒绝）。覆盖 principal.role
真实来源、contexts 证据可达条件、stream 声明权威、上下文引用完整性。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import ConditionalRejected
from kernel.pipeline import Kernel
from kernel.sc_compiler import compile_action
from kernel.store import EventStore
from kernel.session import SessionChannel

def _compiled(expr: str):
    return compile_action({"action_type": "Probe", "aggregate": "A",
        "submission_criteria": {"conditional": {
            "expression": expr, "snapshot_inputs": []}}}, "genesis")

def test_principal_role_comes_from_kernel_evidence_not_claim():
    """旧实现把主体名填进 principal.role —— 主体自称 'steward' 即可绕过条件。
    新实现取 roles 参数：同名主体未持角色仍被条件拒绝。"""
    act = _compiled("principal.role == 'steward'")
    k = Kernel(EventStore(), SessionChannel(), {"Probe": act})
    k.store._actions.add("Probe")                      # 临时 Action 入能力面
    k.submit("Probe", {}, "steward", roles=("steward",))
    with pytest.raises(ConditionalRejected):
        k.submit("Probe", {}, "steward", roles=())

def test_context_evidence_reaches_condition():
    """permissions.contexts 声明位在求值环境中可引用，且缺省为空（fail-closed）。"""
    act = _compiled("principal.contexts == ('ContractContext',)")
    k = Kernel(EventStore(), SessionChannel(), {"Probe": act})
    k.store._actions.add("Probe")
    k.submit("Probe", {}, "svc", contexts=("ContractContext",))
    with pytest.raises(ConditionalRejected):
        k.submit("Probe", {}, "svc")

def test_stream_declaration_is_authoritative():
    """流名不再是 f'domain:{aggregate}' 硬编码 —— 声明值是权威源。"""
    act = compile_action({"action_type": "X", "aggregate": "A",
                          "stream": "domain:Custom"}, "genesis")
    assert act.stream == "domain:Custom"
    from kernel.registration import compile_all
    assert compile_all()["ApproveContract"].stream == "domain:ContractAggregate"

def test_context_reference_must_resolve(tmp_path, monkeypatch):
    """contexts 空引用（拼错/未声明）在注册期失败，不再静默通过五步管线。"""
    import kernel.registration as reg
    (tmp_path / "contexts").mkdir(parents=True)
    (tmp_path / "ontology/actions").mkdir(parents=True)
    (tmp_path / "contexts/Known.context.yaml").write_text(
        "context: Known\nsteward: s\nprojection_delay_budget_ms: 1\n", encoding="utf-8")
    (tmp_path / "ontology/actions/Act.action.yaml").write_text(
        "action_type: Act\naggregate: A\npermissions: { contexts: [Ghost] }\n", encoding="utf-8")
    monkeypatch.setattr(reg, "SPEC_DIR", tmp_path)
    failures = reg._validate_spec()
    assert any("CONTEXT-REF-UNDECLARED" in f and "Ghost" in f for f in failures)
