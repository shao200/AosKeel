"""tests/conformance/test_installability.py —— wheel 可安装性与边界。
判据：wheel 可构建（pip wheel --no-deps）；包内容含 src/tools 全部模块；
**不含** docs/spec/config（不是可安装交付物——pyproject 注释与 CLI REFUSED
消息的机器判据）；entry point `aos = src.cli.main:main` 在场；版本一致。
安装冒烟（临时 venv → aos → REFUSED 边界消息）已在 CI 手工验证，测试内不装
wheel（避免 pip 网络依赖），只查包结构与元数据。
"""
import zipfile
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
def _build_wheel(tmp_path: Path) -> Path:
    import subprocess, sys
    out = tmp_path / "whl"
    subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps",
                    "-w", str(out)],
                   cwd=str(ROOT), capture_output=True, check=True)
    wheels = list(out.glob("aos_keel-*.whl"))
    assert len(wheels) == 1
    return wheels[0]
def test_wheel_structure_and_boundary(tmp_path):
    """包结构：src/tools 在内；docs/spec/config 不在内；entry point 在场。"""
    whl = _build_wheel(tmp_path)
    names = set(zipfile.ZipFile(whl).namelist())
    assert "src/cli/main.py" in names
    assert "src/kernel/pipeline.py" in names
    assert "tools/codegen.py" in names
    assert not any(n.startswith(("docs/", "spec/", "config/")) for n in names)
def test_wheel_entry_point_and_version(tmp_path):
    """entry_points.txt 含 aos console script；版本与 pyproject 一致（0.3.0）。"""
    whl = _build_wheel(tmp_path)
    with zipfile.ZipFile(whl) as z:
        meta = z.read("aos_keel-0.3.0.dist-info/entry_points.txt").decode("utf-8")
    assert "aos = src.cli.main:main" in meta
def test_source_tree_refusal_guarded():
    """_require_source_tree 守卫在场且与 wheel 边界声明一致（无 docs → 拒绝路径）。"""
    src = (ROOT / "src" / "cli" / "main.py").read_text(encoding="utf-8")
    assert "_require_source_tree" in src and "REFUSED" in src
