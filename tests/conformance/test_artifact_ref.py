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
def test_supersede_requires_proposal_ref(tmp_path, monkeypatch):
    """护栏：无治理提案引用 → 拒绝（GOV-1 精神：CLI 只记录，不合成版本）。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1")
    (tmp_path / "docs/aos-spec.md").write_text("# 规范 v3", encoding="utf-8")
    with pytest.raises(SystemExit, match="REFUSED"):
        hs.supersede("v2", None)
