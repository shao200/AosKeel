"""tests/conformance/test_init_root_completeness.py —— aos init 实例根层完整性。

实测缺口：init 只复制目录白名单，实例缺 .gitattributes / .gitignore /
pyproject.toml / README —— 其中 `* -text` 是 GOV-2.3 字节精确防线的组成部分，
Windows 实例上换行转换可破坏冻结哈希与骨架字节检查。
判据全部可计算：存在性、字节一致、关键行在场、设计性排除项仍在排除位。
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from cli.main import cmd_init

ROOT_FILES = (".gitattributes", ".gitignore", "pyproject.toml", "README.md")


def _init(tmp_path) -> Path:
    dst = tmp_path / "myorgsystem"
    assert cmd_init(str(dst)) == 0
    return dst


def test_root_files_present(tmp_path):
    dst = _init(tmp_path)
    for f in ROOT_FILES:
        assert (dst / f).is_file(), f"实例缺根文件 {f}"


def test_gitattributes_byte_exact_rule_carried(tmp_path):
    """`* -text` 逐字节来自模板 —— 哈希锁定防线不可在实例侧退化。"""
    dst = _init(tmp_path)
    a = (dst / ".gitattributes").read_bytes()
    b = (ROOT / ".gitattributes").read_bytes()
    assert a == b, "实例 .gitattributes 与模板字节不一致"
    assert b"* -text" in a


def test_pyproject_carries_dependencies(tmp_path):
    dst = _init(tmp_path)
    text = (dst / "pyproject.toml").read_text(encoding="utf-8")
    for dep in ("pyyaml", "pytest", "[tool.pytest.ini_options]"):
        assert dep in text, f"实例 pyproject 缺 {dep}"


def test_generated_readme_points_to_boot0(tmp_path):
    dst = _init(tmp_path)
    text = (dst / "README.md").read_text(encoding="utf-8")
    assert "bootstrap --stage 0" in text
    assert "python src/cli/main.py" in text


def test_registry_still_excluded(tmp_path):
    """设计性排除不变：实例自行登记（GOV-2.3 / BOOT-0）。"""
    dst = _init(tmp_path)
    assert not (dst / "docs/ARTIFACT-REGISTRY.md").exists()
    assert (dst / "docs/TEMPLATE-LOCK.md").is_file()


def test_domain_manual_generated_in_instance(tmp_path):
    """领域说明书由 init 生成（派生件，真源 = 实例自身 spec/）。"""
    dst = _init(tmp_path)
    manuals = [p for p in (dst / "docs").rglob("DOMAIN-MANUAL.md")]
    assert len(manuals) == 1, f"说明书应恰有一份且位于 docs/ 顶层: {manuals}"
    text = manuals[0].read_text(encoding="utf-8")
    for anchor in ("上下文", "动作", "不变量"):
        assert anchor in text, f"说明书缺章节锚点 {anchor}"


def test_author_local_docs_not_carried(tmp_path):
    """REVIEW-* 作者本地评审文档不得进入实例。"""
    dst = _init(tmp_path)
    leaked = [p.name for p in (dst / "docs").rglob("REVIEW-*") if p.is_file()]
    assert not leaked, f"作者本地文档泄漏进实例: {leaked}"


def test_structure_guide_carried(tmp_path):
    """09 结构与轨迹指南随 init 到位 —— 实例用户第一眼的项目地图。"""
    dst = _init(tmp_path)
    assert (dst / "docs/guide/09-structure-and-trajectory.md").is_file()
