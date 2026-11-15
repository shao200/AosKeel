"""tests/genesis/test_genesis_predicate.py —— VER-19 / KS-8.2：
创世谓词先于每次 GenesisWrite 求值；冻结/熄灭态谓词为假。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.genesis import GenesisWindow, GenesisFrozen, GenesisExtinguished
APPT = "APPT-2026-001"
def test_predicate_true_while_open():
    w = GenesisWindow(APPT, ttl_seconds=3600)
    assert w.predicate() is True
    assert w.genesis_write({"Contract": {}})                     # 先于写求值 → 通过
def test_predicate_false_when_frozen():
    w = GenesisWindow(APPT, ttl_seconds=3600, now_fn=lambda: 0)
    w._now = lambda: 10_000                                      # TTL 过期
    assert w.predicate() is False                                # 冻结态谓词为假
    with pytest.raises(GenesisFrozen):
        w.genesis_write({"Contract": {}})
def test_predicate_permanently_false_when_extinguished():
    w = GenesisWindow(APPT, ttl_seconds=3600)
    w.close_governance_cycle()                                   # KS-8.4 闭环 → 熄灭
    assert w.predicate() is False
    with pytest.raises(GenesisExtinguished):
        w.genesis_write({"Contract": {}})
