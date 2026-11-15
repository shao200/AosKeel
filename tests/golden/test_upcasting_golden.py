"""tests/golden/test_upcasting_golden.py —— VER-14：升级链输出被 golden 锚定（KS-5.3）。
golden 数据内嵌本文件（KS-5.3：交付契约以固定样例锚定升级输出结构）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.upcasting import register_upcaster, upcast, reset_registry, CURRENT
GOLDEN_INPUT = {"qty": 3, "memo": "first order"}            # KS-5.3 golden 输入
GOLDEN_EXPECTED = {"qty": 3, "memo": "first order",          # KS-5.3 golden 输出（固定）
                   "amount": 3, "currency": "CNY", "origin": "upcast"}
@pytest.fixture(scope="module", autouse=True)
def _chain():
    reset_registry()                                       # 链锚定前清场（注册表只增）
    CURRENT["Order"] = 4                                   # 本场景声明当前交付版本 = v4（KS-5.1）
    register_upcaster("Order", 1, lambda p: {**p, "amount": p["qty"]})
    register_upcaster("Order", 2, lambda p: {**p, "currency": "CNY"})
    register_upcaster("Order", 3, lambda p: {**p, "origin": "upcast"})
    yield
    CURRENT["Order"] = 3; reset_registry()
def test_golden_chain_output():
    v, data = upcast("Order", 1, dict(GOLDEN_INPUT))
    assert data == GOLDEN_EXPECTED                          # 逐属性一致（KS-5.3 交付契约）
def test_golden_from_any_link_in_chain():
    """从链上任一环节读入，输出 = golden ∖ （早于该环节的段所添加的字段）。"""
    fields_by_link = {1: {"amount"}, 2: {"currency"}, 3: {"origin"}}
    for start in (1, 2, 3):
        _, data = upcast("Order", start, dict(GOLDEN_INPUT))
        expected_keys = set(GOLDEN_INPUT) | set().union(
            *(fields_by_link[i] for i in range(start, 4)))
        assert set(data) == expected_keys
        assert all(data.get(k) == GOLDEN_EXPECTED.get(k)
                   for k in expected_keys & set(GOLDEN_EXPECTED))
