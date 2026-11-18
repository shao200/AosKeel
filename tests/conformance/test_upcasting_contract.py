"""tests/conformance/test_upcasting_contract.py —— VER-13：升级路径 fail-closed（KS-5.2/5.4）。
判据：未注册的升级路径 = 读失败；升级不改写日志、是纯映射（AX-3 / R11）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.upcasting import register_upcaster, upcast, CURRENT, reset_registry
from kernel.errors import UpcastingFailed
@pytest.fixture(autouse=True)
def _clean():
    reset_registry(); yield; reset_registry()              # 注册表只增；测试间隔离
def test_unregistered_path_fails_closed():
    register_upcaster("Order", 2, lambda p: p)             # 只有 2→3 一段
    with pytest.raises(UpcastingFailed, match="UPCAST-PATH-MISSING"):
        upcast("Order", 1, {"qty": 1})                     # @1 无路径 → 读失败（KS-5.2）
def test_chain_completes_to_delivered_version():
    register_upcaster("Order", 1, lambda p: {**p, "amount": p["qty"]})
    register_upcaster("Order", 2, lambda p: {**p, "currency": "CNY"})
    v, data = upcast("Order", 1, {"qty": 3})
    assert v == CURRENT["Order"] and data["amount"] == 3 and data["currency"] == "CNY"

def test_current_covers_example_domain():
    """示例域 Contract 与 Order 同在 CURRENT 登记；无链仍 fail-closed。"""
    assert CURRENT.get("Contract") == 1
    assert upcast("Contract", 1, {"status": "draft"}) == (1, {"status": "draft"})
    with pytest.raises(UpcastingFailed, match="UPCAST-PATH-MISSING"):
        upcast("Contract", 0, {"status": "draft"})
def test_upcast_is_pure_no_input_mutation():
    register_upcaster("Order", 2, lambda p: {**p, "currency": "CNY"})
    src = {"qty": 3}
    upcast("Order", 2, src)
    assert src == {"qty": 3}                               # 不改写入参（AX-3 读时升级）
def test_deterministic():
    register_upcaster("Order", 2, lambda p: {**p, "currency": "CNY"})
    assert upcast("Order", 2, {"qty": 3}) == upcast("Order", 2, {"qty": 3})
