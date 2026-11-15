"""tests/conformance/test_link_pattern.py —— VER-21：LinkPattern 三项（P-4 / INV-2）。
结构性链接：属性集为空、遍历透明、无 Action 绑定 —— 任一违反 = 校验失败。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
from kernel.registration import validate_link
def _base():
    return {"link_type": "same_as",
            "checks": {"attributes_empty": True, "traversal_transparent": True},
            "action_binding": None}
def test_real_link_valid():
    for p in sorted((ROOT / "spec/ontology/links").glob("*.yaml")):
        assert validate_link(yaml.safe_load(p.read_text(encoding="utf-8"))) == []
def test_non_empty_attributes_rejected():
    link = _base(); link["checks"]["attributes_empty"] = False
    assert any("属性集非空" in f for f in validate_link(link))     # P-4 之一
def test_non_transparent_traversal_rejected():
    link = _base(); link["checks"]["traversal_transparent"] = False
    assert any("遍历透明" in f for f in validate_link(link))
def test_action_binding_rejected():
    """INV-2：链接不授予权限、不承载写入 —— 绑定 Action 即拒。"""
    link = _base(); link["action_binding"] = "ApproveContract"
    assert any("ActionType" in f for f in validate_link(link))
