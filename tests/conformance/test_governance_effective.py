"""tests/conformance/test_governance_effective.py —— GOV-4 / KV-4：生效重跑。
判据：治理 Action 生效 MUST 通过注册管线重跑；失败 = 生效阻断 + governance 类
违规对象（经 RaiseInvariantViolation 写入，P-7 / INV-10，repair 绑定 GOV-3 通道）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.governance import GovernanceLedger
from kernel import registration
from kernel.errors import RegistrationFailed
VIOLATION_STREAM = "domain:invariant"
def test_effective_rerun_passes():
    store = EventStore()
    rec = GovernanceLedger(store).record_effective(
        "GOV-2026-001", "SPEC-2026-014", "steward")
    assert rec["rerun"] == "passed"
    assert rec["capabilities"] >= 4                                # 创世内建 + 业务 Action
def test_effective_blocked_on_reconcile_failure(monkeypatch):
    """reconcile 失败 → 生效阻断 + governance 类违规对象落日志（P-7 / INV-10）。"""
    store = EventStore()
    ledger = GovernanceLedger(store)
    caps = registration.load_caps()
    broken = {"write_actions": caps["write_actions"][:2],          # 丢掉 ApproveContract/VoidContract
              "channel_writes": caps.get("channel_writes", [])}
    monkeypatch.setattr(registration, "load_caps", lambda: broken)
    with pytest.raises(RegistrationFailed, match="RECONCILE-FAILED"):
        ledger.record_effective("GOV-2026-002", "SPEC-2026-015", "steward")
    violations = store.streams[VIOLATION_STREAM]
    assert violations[-1].action_id == "RaiseInvariantViolation"   # 违规即对象（INV-10）
    assert violations[-1].payload["classification"] == "governance"
    assert violations[-1].payload["invariant_ref"] == "GOV-4-effective-rerun"
    assert violations[-1].payload["repair"] == "GOV-3-version-channel"   # INV-3 修复绑定
    assert violations[-1].payload["violated_on"]["action_ref"] == "GOV-2026-002"
def test_refs_required():
    store = EventStore()
    with pytest.raises(RegistrationFailed, match="REFS-REQUIRED"):
        GovernanceLedger(store).record_effective("", "", "steward")
    assert VIOLATION_STREAM not in store.streams                   # 拒绝在先，无违规对象
