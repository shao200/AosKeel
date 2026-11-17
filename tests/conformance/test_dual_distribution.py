"""ADR-001 增量双分发守卫：aoskeel-kernel / aoskeel-template 的边界与注入语义。

同 test_installability 风格：结构/元数据断言为主，wheel 真构建一条；
不声称 kernel 在 site-packages 无需数据目录即可用（诚实边界，见 ADR）。
"""
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_adr_present_and_accepted():
    adr = ROOT / "docs/adr/ADR-001-dual-distribution.md"
    assert adr.exists()
    txt = adr.read_text(encoding="utf-8")
    assert "Accepted" in txt
    assert "e6884aed" in txt and "91ffe5a1" in txt       # 冻结承诺在案


def test_root_injection_is_zero_regression():
    """两处 ROOT 均为 env-or-原锚点；未设 env 时逐字回退 parents[2]。"""
    for rel in ("src/kernel/registration.py", "src/kernel/session.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "AOSKEEL_ROOT" in src
        assert 'os.environ.get("AOSKEEL_ROOT") or Path(__file__).resolve().parents[2]' in src


def test_injection_actually_reads_config(tmp_path):
    """设 AOSKEEL_ROOT 指向真模板根 → registration 能 load_caps（非空壳）。"""
    code = (
        "import os,sys;"
        f"sys.path.insert(0,{str(ROOT / 'src')!r});"
        "import kernel.registration as r;"
        "print(r.ROOT); print(r.CAPS.exists()); print(sorted(r.load_caps().keys()))"
    )
    env = dict(os.environ, AOSKEEL_ROOT=str(ROOT))
    p = subprocess.run([sys.executable, "-c", code], cwd=str(tmp_path),
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "True" in p.stdout
    assert "write_actions" in p.stdout


def test_template_sdist_build_and_selfcheck(tmp_path):
    out = tmp_path / "aoskeel-template-0.3.0.tar.gz"
    p = subprocess.run([sys.executable, str(ROOT / "packages/template/build_sdist.py"),
                        "--out", str(out)], cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "SDIST-OK" in p.stdout
    with tarfile.open(out, "r:gz") as tf:
        names = set(tf.getnames())
    base = "aoskeel-template-0.3.0/"
    for req in ("docs/aos-spec.md", "spec/profile.yaml",
                "config/capabilities.yaml", "src/cli/main.py"):
        assert base + req in names
    assert not any("/packages/" in n for n in names)   # 不递归自包含


def test_kernel_wheel_boundary(tmp_path):
    """kernel wheel 真构建；只含四逻辑包，不含 docs/spec/config/tools/cli。"""
    out = tmp_path / "whl"
    p = subprocess.run([sys.executable, "-m", "pip", "wheel",
                        str(ROOT / "packages/kernel"), "--no-deps", "-w", str(out)],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    wheels = list(out.glob("aoskeel_kernel-*.whl"))
    assert len(wheels) == 1
    with zipfile.ZipFile(wheels[0]) as z:
        names = z.namelist()
        assert "kernel/registration.py" in names
        assert "interpreter/audit.py" in names
        assert "generated/actions.py" in names
        assert "agents/runtime.py" in names
        assert not any(n.startswith(("docs/", "spec/", "config/", "tools/", "src/cli/"))
                       for n in names)
        assert "AOSKEEL_ROOT" in z.read("kernel/registration.py").decode("utf-8")


def test_root_wheel_contract_unchanged():
    """ADR-001 是增量：根 wheel 边界守卫仍在（不推翻 test_installability）。"""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "aos-keel"' in pyproject
    assert 'aos = "src.cli.main:main"' in pyproject
    assert (ROOT / "tests/conformance/test_installability.py").exists()
