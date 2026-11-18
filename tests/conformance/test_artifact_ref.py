"""tests/conformance/test_artifact_ref.py —— VER-30：工件引用与版本通道（GOV-2/3）。
判据：capabilities spec_ref 指向登记条目（GOV-2.2）；漂移拒绝（GOV-2.5）；
GOV-3 版本通道 = 新登记条目取代 + append-only（旧行不改写）+ 提案引用强制。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import tools.hash_spec as hs
CANON = {"docs/aos-spec.md": "# 规范 v1\n正文", "docs/SPEC-FINGERPRINT.md": "# 指纹"}
def _sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    monkeypatch.setattr(hs, "REGISTRY", tmp_path / "docs/ARTIFACT-REGISTRY.md")
    monkeypatch.setattr(hs, "CAPS", tmp_path / "config/capabilities.yaml")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/capabilities.yaml").write_text("spec_ref: AOS-ART-000\n",
                                                       encoding="utf-8")
    for rel, text in CANON.items():
        p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
def test_real_spec_ref_points_to_registry():
    """GOV-2.2：capabilities spec_ref 是登记条目 ID，非内联哈希。"""
    caps = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8")
    import re
    m = re.search(r"spec_ref:\s*(AOS-ART-\d+)", caps)
    assert m, "spec_ref 缺失（GOV-2.2）"
    art_id = m.group(1)
    registry = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    assert f"| {art_id} |" in registry                              # 引用可解析（INV-4 同型）
def test_register_verify_idempotent(tmp_path, monkeypatch):
    _sandbox(tmp_path, monkeypatch)
    assert hs.register("v1") == 0
    assert hs.verify() == 0
    assert hs.register("v1") == 0                                   # 同哈希幂等
    rows = hs._entries()
    assert len(rows) == 1                                           # 幂等不重复登记
def test_drift_refused_and_gov3_channel(tmp_path, monkeypatch):
    """GOV-2.5 漂移拒绝 → GOV-3 通道以新条目取代，旧行不改写（append-only P-15）。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1")
    first_row = hs._entries()[0]
    (tmp_path / "docs/aos-spec.md").write_text("# 规范 v2\n新正文", encoding="utf-8")
    assert hs.verify() == 1                                         # 漂移 → 密码学层 MISMATCH
    with pytest.raises(SystemExit, match="FROZEN-TEXT-MUTATED"):
        hs.register("v1")                                           # 就地登记被拒（GOV-2.5）
    assert hs.supersede("v2", "SPEC-2026-014") == 0                 # GOV-3 通道
    rows = hs._entries()
    assert rows[0] == first_row                                     # 旧行逐字未动（P-15）
    assert len(rows) == 2 and "v2" in rows[1]
    assert hs.verify() == 0                                         # 新哈希通过
    log = (tmp_path / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    assert "superseded-via: SPEC-2026-014" in log                   # 提案回溯在案
def test_supersede_row_lands_in_art_table_before_decl_section(tmp_path, monkeypatch):
    """E-1：GOV-3 新登记行 MUST 插在 ART 表尾（DECL 区之前），不得 EOF 追加。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1")
    # 模拟登记表已含 DECL 区（历史 bug：旧实现会把新 ART 行写到文件末尾）
    reg = hs.REGISTRY
    with reg.open("ab") as f:
        f.write(("\n" + hs.DECL_SECTION.strip() + "\n"
                 "| AOS-DECL-001 | v1 | sha256:abc | now | registered |\n").encode("utf-8"))
    before = reg.read_text(encoding="utf-8")
    (tmp_path / "docs/aos-spec.md").write_text("# 规范 v2\n新正文", encoding="utf-8")
    assert hs.supersede("v2", "SPEC-2026-014") == 0
    after = reg.read_text(encoding="utf-8")
    art_line = next(l for l in after.splitlines() if l.startswith("| AOS-ART-002 |"))
    decl_at = after.index("## 声明摘要登记")
    assert after.index(art_line) < decl_at, "新 ART 行落到 DECL 区之后（E-1 回归）"
    assert "| AOS-ART-001 |" in before and "| AOS-ART-001 |" in after  # 旧行逐字保留


def test_supersede_requires_proposal_ref(tmp_path, monkeypatch):
    """护栏：无治理提案引用 → 拒绝（GOV-1 精神：CLI 只记录，不合成版本）。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1")
    (tmp_path / "docs/aos-spec.md").write_text("# 规范 v3", encoding="utf-8")
    with pytest.raises(SystemExit, match="REFUSED"):
        hs.supersede("v2", None)
def test_registry_crlf_working_copy_keeps_old_row_bytes(tmp_path, monkeypatch):
    """P-15 字节保真：登记表被编辑器存成 CRLF 时，旧行字节（含 \r）原样保留，
    新行随既有换行风格；spec_ref 回填同样不剥 \r。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1")
    reg, caps = hs.REGISTRY, hs.CAPS
    old_line = next(l for l in reg.read_bytes().split(b"\n")
                    if l.startswith(b"| AOS-ART-001 |"))
    reg.write_bytes(reg.read_bytes().replace(b"\n", b"\r\n"))     # 模拟编辑器 CRLF
    caps.write_bytes(caps.read_bytes().replace(b"\n", b"\r\n"))
    (tmp_path / "docs/aos-spec.md").write_text("# 规范 v2\n新正文", encoding="utf-8")
    assert hs.supersede("v2", "SPEC-2026-014") == 0
    raw = reg.read_bytes()
    assert old_line + b"\r" in raw                                # 旧行 \r 未被剥掉
    assert raw.replace(b"\r\n", b"\n").count(b"| AOS-ART-001 |") == 1
    new_line = next(l for l in raw.split(b"\r\n") if l.startswith(b"| AOS-ART-002 |"))
    assert new_line == next(l for l in hs._entries() if "AOS-ART-002" in l).encode("utf-8")
    assert caps.read_bytes().startswith(b"spec_ref: AOS-ART-002") # 回填正确
    assert caps.read_bytes().endswith(b"\r\n")                    # CRLF 风格未被改写
def test_latest_spec_version_follows_registry_then_canonical(tmp_path, monkeypatch):
    """E-2：版本真源 = 登记表最新条目版本列；登记表为空时回落正典头部
    （不再硬编码），跃迁自动跟随。"""
    import cli.main as cm
    _sandbox(tmp_path, monkeypatch)
    monkeypatch.setattr(cm, "ROOT", tmp_path)
    (tmp_path / "docs/aos-spec.md").write_text("《AOS》\nv2.1.1 · Frozen\n正文",
                                               encoding="utf-8")
    assert cm._latest_spec_version() == "v2.1.1"                  # 空 → 正典头部回落
    hs.register("v9.9.9")
    assert cm._latest_spec_version() == "v9.9.9"                  # 登记后跟随最新条目
