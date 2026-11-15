"""tests/conformance/test_source_declaration.py —— VER-12：上下文声明完备（P-3 / P-16）。
判据：steward 必填（所有权），projection_delay_budget_ms 必填（投影延迟预算）；
真实 spec/contexts 通过；篡改（缺 steward）= 注册拒绝。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
from kernel.registration import validate_context, _validate_spec
from kernel.errors import RegistrationFailed
def test_real_contexts_validate():
    for p in sorted((ROOT / "spec/contexts").glob("*.yaml")):
        assert validate_context(yaml.safe_load(p.read_text(encoding="utf-8"))) == []
def test_missing_steward_rejected():
    failures = validate_context({"context": "X", "projection_delay_budget_ms": 500})
    assert any("STEWARD-MISSING" in f for f in failures)       # P-3：所有权必填
def test_missing_projection_budget_rejected():
    failures = validate_context({"context": "X", "steward": "s"})
    assert any("PROJECTION-BUDGET" in f for f in failures)     # P-16：延迟预算必填
def test_spec_wide_validation_passes():
    """八类声明全量校验 = 注册管线第三步通过。"""
    assert _validate_spec() == []
def test_pipeline_reconcile_with_real_spec():
    from kernel.registration import run_pipeline
    gen = run_pipeline()                                       # declared == registered（INV-13）
    ids = {a["id"] for a in gen["write_actions"]}
    assert {"RecordDecision", "RaiseInvariantViolation", "ApproveContract"} <= ids
