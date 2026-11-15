"""tests/genesis/test_genesis_ttl.py —— VER-32 / KS-8.5：
TTL 到期 → 冻结（可逆，须创制任命主体再授权）；治理闭环 → 熄灭（不可逆，
凭据重放必拒）；时间戳三项在案（KS-8.4）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.genesis import GenesisWindow, GenesisFrozen, GenesisExtinguished
APPT = "APPT-2026-001"
def test_ttl_expiry_freezes_then_reactivation_with_owner():
    w = GenesisWindow(APPT, ttl_seconds=10, now_fn=lambda: 0)
    w._now = lambda: 11                                          # TTL 到期
    assert w.predicate() is False
    w.reactivate(APPT)                                           # 创制任命主体再授权
    assert w.predicate() is True
    assert any(a["kind"] == "genesis-reactivated" for a in w.audit)   # 记为新审计事件
def test_reactivation_with_wrong_credentials_refused():
    w = GenesisWindow(APPT, ttl_seconds=10, now_fn=lambda: 0)
    w._now = lambda: 11
    with pytest.raises(PermissionError, match="创制任命主体不符"):
        w.reactivate("APPT-FAKE")
def test_credential_replay_after_extinguish_refused():
    """熄灭后凭据重放必拒 —— 类上无重启用路径（KS-8.2 / INV-11 / VER-28 item4）。"""
    w = GenesisWindow(APPT, ttl_seconds=10)
    w.close_governance_cycle()
    with pytest.raises(GenesisExtinguished, match="EXTINGUISH-OVERRIDE-FORBIDDEN"):
        w.reactivate(APPT)                                       # 正确凭据也无效
    assert not hasattr(GenesisWindow, "revive") and not hasattr(GenesisWindow, "reopen")
def test_three_timestamps_recorded():
    """开放/冻结/熄灭时间戳三项在案（KS-8.4 / VER-20 判据基）。"""
    w = GenesisWindow(APPT, ttl_seconds=10, now_fn=lambda: 0)
    w._now = lambda: 11
    w.reactivate(APPT)
    w.close_governance_cycle()
    assert {"opened", "frozen", "extinguished"} <= set(w.timestamps)
