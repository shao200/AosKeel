"""tests/conformance/test_declaration_digest.py —— GOV-2.3-DECL 第四道比对。
判据：spec/ 业务声明（条件阈值/权限/副作用）入独立摘要域，冻结正典与
e6884aed… 历史封存行不改写；摘要漂移 = verify 失败；未登记/无声明显式
SKIP（不把"没有基线"伪装成 PASS）；spec/drafts/ 是工作区，不入摘要域。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import tools.hash_spec as hs

CANON = {"docs/aos-spec.md": "# 规范 v1\n正文", "docs/SPEC-FINGERPRINT.md": "# 指纹"}
DECLS = {
    "spec/ontology/actions/Approve.action.yaml": "expression: amount < 10**6\n",
    "spec/aggregates/A.aggregate.yaml": "stream: domain:ContractAggregate\n",
    "spec/contexts/C.context.yaml": "context: ContractContext\n",
}

def _sandbox(tmp_path, monkeypatch, with_decls=True):
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    monkeypatch.setattr(hs, "REGISTRY", tmp_path / "docs/ARTIFACT-REGISTRY.md")
    monkeypatch.setattr(hs, "CAPS", tmp_path / "config/capabilities.yaml")
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/capabilities.yaml").write_text("spec_ref: AOS-ART-000\n",
                                                       encoding="utf-8")
    for rel, text in CANON.items():
        p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    if with_decls:
        for rel, text in DECLS.items():
            p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

def test_declaration_tamper_refused_without_touching_frozen_digest(tmp_path, monkeypatch):
    """核心判据：改业务条件阈值 → 第四道 MISMATCH；正典哈希仍不变。"""
    _sandbox(tmp_path, monkeypatch)
    canon_before = hs.canonical_digest()
    assert hs.register("v1") == 0
    assert hs.register_declarations("v1") == 0
    assert hs.verify() == 0
    p = tmp_path / "spec/ontology/actions/Approve.action.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("10**6", "10**9"), encoding="utf-8")
    assert hs.canonical_digest() == canon_before        # 冻结正典未被触碰
    assert hs.verify() == 1                             # 业务声明漂移被拒

def test_drafts_not_in_digest_domain(tmp_path, monkeypatch):
    """spec/drafts/ 是工作区草案，改动不得触发第四道漂移。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1"); hs.register_declarations("v1")
    before = hs.declaration_digest()
    d = tmp_path / "spec/drafts/Scratch.yaml"; d.parent.mkdir()
    d.write_text("draft: scratch\n", encoding="utf-8")
    assert hs.declaration_digest() == before
    assert hs.verify() == 0

def test_in_place_re_registration_refused(tmp_path, monkeypatch):
    """声明漂移后就地重登记被拒；append-only 语义与正典同源。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1"); hs.register_declarations("v1")
    p = tmp_path / "spec/aggregates/A.aggregate.yaml"
    p.write_text("stream: domain:Other\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="DECL-FROZEN-MUTATED"):
        hs.register_declarations("v1")

def test_decl_supersede_requires_proposal(tmp_path, monkeypatch):
    """声明合法变更走治理提案 + 新条目（旧行不改写，P-15）。"""
    _sandbox(tmp_path, monkeypatch)
    hs.register("v1"); hs.register_declarations("v1")
    p = tmp_path / "spec/aggregates/A.aggregate.yaml"
    p.write_text("stream: domain:Other\n", encoding="utf-8")
    assert hs.register_declarations("v2", "SPEC-2026-014") == 0
    log = hs.REGISTRY.read_text(encoding="utf-8")
    assert "decl-superseded-via: SPEC-2026-014" in log
    assert len(hs._decl_entries()) == 2
    assert hs.verify() == 0

def test_skip_when_no_declarations(tmp_path, monkeypatch):
    """无 spec 声明 → 显式 SKIP，不把缺失基线当作校验通过。"""
    _sandbox(tmp_path, monkeypatch, with_decls=False)
    hs.register("v1")
    assert hs.verify_declarations() == 0
    assert hs.verify() == 0

def test_skip_when_declarations_not_registered(tmp_path, monkeypatch):
    """有声明但未登记（如 aos init 实例）→ 显式 SKIP。"""
    _sandbox(tmp_path, monkeypatch, with_decls=True)
    hs.register("v1")
    assert hs.verify_declarations() == 0

def test_skip_flag_is_exposed_not_disguised(tmp_path, monkeypatch):
    """N3：SKIP 时 verify() 仍返回 0（三关绿），但旗标置位——出制品决策可见。"""
    _sandbox(tmp_path, monkeypatch, with_decls=True)
    hs.register("v1")
    assert hs.verify() == 0
    assert hs.decl_digest_skip() is True               # 未登记：三关绿 ≠ 四道比对过
    hs.register_declarations("v1")
    assert hs.verify() == 0
    assert hs.decl_digest_skip() is False              # 登记后第四道真实比对

def test_gate_refuses_artifacts_on_decl_skip(tmp_path, monkeypatch):
    """N3：release gate 对 SKIP 实例拒出制品——篡改不可检测的形态不配出库。"""
    from tools import release_gate
    monkeypatch.setattr(release_gate, "hs_verify", lambda: 0)
    monkeypatch.setattr(release_gate, "decl_digest_skip", lambda: True)
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=lambda: "stub")
    assert report["ok"] is False
    assert not (tmp_path / "RELEASE-MANIFEST.json").exists()
    crypto = next(s for s in report["steps"] if s["step"] == "cryptographic")
    assert not crypto["ok"] and "SKIP" in crypto["detail"]

def test_real_registry_declaration_is_current():
    """真实仓库：声明摘要已登记且当前一致；v2.0.0 封存登记行逐字保留。"""
    registry = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    old = registry.splitlines()
    assert any(l.startswith("| AOS-ART-001 |") and "e6884aed" in l for l in old)
    rows = hs._decl_entries()
    assert rows and hs.declaration_digest() in rows[-1]
    assert hs.verify_declarations() == 0
