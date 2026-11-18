"""tests/conformance/test_wiring_coverage.py —— 测试文件全量在册守卫（INTEGRITY-42）。

tests/README.md 纪律："新增测试文件若不在布线里，等于不存在"。INTEGRITY-29 之前的
漏登教训（N4）：发布闸门只执行 wiring.wired_paths()，12 个测试文件（含 4 个直接
守卫前几轮修复成果的文件）长期不在闸门内，裸 pytest 的绿掩盖了闸门盲区。

本守卫锁住双向集合相等：tests/**/test_*.py 与布线表（ver + integrity_paths）
必须一一对应 —— 漏登即红，幽灵条目（布线指向不存在/非测试文件）也红。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import wiring  # noqa: E402
def test_all_test_files_are_wired_and_no_ghosts():
    wired = {p for _, p in wiring.wired_paths()}
    discovered = {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").rglob("test_*.py")}
    missing = sorted(discovered - wired)
    ghosts = sorted(wired - discovered)
    assert not missing, f"测试文件未布线（发布闸门不会执行）: {missing}"
    assert not ghosts, f"布线表幽灵条目（指向不存在或非测试文件）: {ghosts}"
