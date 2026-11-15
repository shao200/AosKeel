"""tests/genesis/test_genesis_scope.py —— VER-31 / P-4/8/11：
创世写仅在治理上下文内建对象的窗口内发生；范围外（窗口关闭后）一律拒绝。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.genesis import GenesisWindow, GenesisFrozen, GenesisExtinguished
APPT = "APPT-2026-001"
def test_genesis_write_scoped_to_window():
    w = GenesisWindow(APPT, ttl_seconds=3600)
    ref1 = w.genesis_write({"Contract": {}, "Identity": {}})
    ref2 = w.genesis_write({"Order": {}})
    assert ref1 != ref2                                          # 每批次独立留档（P-15）
    kinds = [a["kind"] for a in w.audit]
    assert kinds.count("genesis-write") == 2
def test_genesis_write_denied_after_freeze():
    w = GenesisWindow(APPT, ttl_seconds=3600, now_fn=lambda: 0)
    w._now = lambda: 10_000                                      # TTL 过期 → frozen
    with pytest.raises(GenesisFrozen):
        w.genesis_write({"Contract": {}})
def test_genesis_write_denied_after_extinguish():
    w = GenesisWindow(APPT, ttl_seconds=3600)
    w.close_governance_cycle()
    with pytest.raises(GenesisExtinguished):
        w.genesis_write({"Contract": {}})
def test_genesis_refuses_synthetic_appointment():
    """创制任命凭据引用必填 —— 模板不合成创制任命（GOV-1 / 护栏一）。"""
    with pytest.raises(ValueError, match="GOV-1"):
        GenesisWindow("", ttl_seconds=3600)
