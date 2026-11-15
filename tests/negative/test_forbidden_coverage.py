"""tests/negative/test_forbidden_coverage.py —— P-10 双射断言（元测试）。
断言一：forbidden 每项恰好一个负向用例（无遗漏、无多余）。
断言二：tests/negative/ 下每个测试映射到 forbidden 条目或 VER 条目——
        负向测试套件自身因此无未治理条目。
"""
import re
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
NEG = ROOT / "tests/negative"

def _forbidden_from_caps() -> list[str]:
    text = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8")
    m = re.search(r"^forbidden:\n((?:  - .*\n)+)", text, re.M)
    return [l.strip()[2:].strip() for l in m.group(1).splitlines()]

def _mapping() -> dict:
    """从 test_forbidden.py 提取 FORBIDDEN_TESTS 映射（避免重复维护两份清单）。"""
    src = (NEG / "test_forbidden.py").read_text(encoding="utf-8")
    m = re.search(r"FORBIDDEN_TESTS\s*=\s*\{(.*?)\}", src, re.S)
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', m.group(1)))

def test_forbidden_bijection():
    """forbidden（capabilities.yaml）↔ 负向用例 双射。"""
    mapping = _mapping()
    forbidden = _forbidden_from_caps()
    assert sorted(mapping) == sorted(forbidden), \
        f"双射破坏: forbidden={sorted(forbidden)} vs mapped={sorted(mapping)}"
    test_src = (NEG / "test_forbidden.py").read_text(encoding="utf-8")
    for item, fn in mapping.items():
        assert re.search(rf"^def {fn}\(", test_src, re.M), f"映射指向不存在的用例: {item} → {fn}"

def test_negative_tests_all_governed():
    """negative/ 每个测试模块必须携带治理映射（FORBIDDEN_TESTS 或 VER 引用）。"""
    ver_ids = set(re.findall(r"VER-\d+",
                  (ROOT / "config/verification.yaml").read_text(encoding="utf-8")))
    for py in NEG.glob("test_*.py"):
        src = py.read_text(encoding="utf-8")
        governed = ("FORBIDDEN_TESTS" in src
                    or set(re.findall(r"VER-\d+", src)) & ver_ids)
        assert governed, f"未治理负向测试模块: {py.name}（须映射 forbidden 或 VER 条目）"
