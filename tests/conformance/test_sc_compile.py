"""tests/conformance/test_sc_compile.py —— VER-18：SC 两段式编译（KS-7.1）。
判据：真实 spec/ 声明编译通过；非法算子 / 非法条件源 = 注册期编译失败。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.sc_compiler import compile_action
from kernel.errors import RegistrationFailed
def test_real_spec_compiles():
    """八类 spec/ 声明样例中的 Action 编译为 CompiledAction。"""
    actions = compile_all()
    assert "ApproveContract" in actions
    act = actions["ApproveContract"]
    assert act.aggregate == "ContractAggregate"
    assert act.provenance == "SPEC-2026-014"                   # KS-8.2 治理出处
    assert act.conditional and act.conditional.startswith("snapshot.")
    assert {c.op for c in act.structural} <= {"exists", "max_len"}   # 死算子 references 已清除
    assert act.stream == "domain:ContractAggregate"                  # 流名取声明，非硬编码
def test_invalid_structural_op_rejected():
    with pytest.raises(RegistrationFailed, match="SC-COMPILE-FAIL"):
        compile_action({"action_type": "X", "aggregate": "A",
                        "submission_criteria": {"structural": ["frobnicate x"]}}, "genesis")
    # `references` 曾在 AST 白名单却无执行点 —— 注册期拒绝优于运行时静默跳过
    with pytest.raises(RegistrationFailed, match="SC-COMPILE-FAIL"):
        compile_action({"action_type": "X", "aggregate": "A",
                        "submission_criteria": {"structural": ["references x"]}}, "genesis")
def test_dryrun_obligation_requires_audit():
    """P-12：dry_run=required 必须配 audit=required，否则演练结果无留痕。"""
    with pytest.raises(RegistrationFailed, match="P-12"):
        compile_action({"action_type": "X", "aggregate": "A", "dry_run": "required"},
                       "genesis")
    assert compile_action({"action_type": "X", "aggregate": "A",
                           "dry_run": "required", "audit": "required"}, "genesis").dry_run
def test_conditional_source_restricted():
    """R2：条件表达式必须起于 snapshot./principal.（宿主时钟/任意名禁止）。"""
    with pytest.raises(RegistrationFailed, match="R2"):
        compile_action({"action_type": "X", "aggregate": "A",
                        "submission_criteria": {"conditional": {
                            "expression": "time.time() > 0"}}}, "genesis")
