"""tests/conformance/test_release_gate.py —— 智能体发布闸门（VER-27 前置，fail-closed）。
判据：全绿才出制品 + RELEASE-MANIFEST 随制品落档；
任一关失败（reconcile / 骨架漂移）→ 不出制品。
"""
import json
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import release_gate, codegen
from kernel import registration
from kernel.errors import RegistrationFailed
from tools.codegen import CodegenDrift
def test_gate_passes_and_writes_manifest(tmp_path):
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=lambda: "stub")
    assert report["ok"] is True
    manifest = json.loads((tmp_path / "RELEASE-MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["spec_ref"].startswith("AOS-ART-")            # 溯源（GOV-2.2）
    assert manifest["digest"].startswith("sha256:")               # 密码学层锚（GOV-2.3）
    assert manifest["registry_entry"] != "NONE"                   # 登记在案
    names = [s["step"] for s in manifest["steps"]]
    assert names == ["structural", "cryptographic", "registered", "tests", "codegen"]
def test_gate_blocked_on_reconcile_failure(tmp_path, monkeypatch):
    """注册层失败 → 不出制品、不写清单（fail-closed）。"""
    monkeypatch.setattr(release_gate.registration, "run_pipeline",
                        lambda: (_ for _ in ()).throw(RegistrationFailed("RECONCILE-FAILED")))
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=lambda: "stub")
    assert report["ok"] is False
    assert not (tmp_path / "RELEASE-MANIFEST.json").exists()      # 无制品清单
    assert any(s["step"] == "registered" and not s["ok"] for s in report["steps"])
def test_gate_blocked_on_codegen_drift(tmp_path, monkeypatch):
    """声明与骨架不一致 → 拒绝发布（KS-4.3：转换不得丢声明）。"""
    def drift():
        raise CodegenDrift("生成物被手改")
    monkeypatch.setattr(release_gate.codegen, "generate", drift)
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=lambda: "stub")
    assert report["ok"] is False
    assert not (tmp_path / "RELEASE-MANIFEST.json").exists()
    assert report["steps"][-1]["step"] == "codegen" and not report["steps"][-1]["ok"]
def test_real_gate_end_to_end(tmp_path):
    """真实闸门（真实测试套件）——发布侧 VER-27 前置的完整演练。"""
    report = release_gate.run_gate(out_dir=tmp_path)              # 不注入 stub
    assert report["ok"] is True
    detail = next(s["detail"] for s in report["steps"] if s["step"] == "tests")
    assert "全部通过" in detail
