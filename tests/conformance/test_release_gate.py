"""tests/conformance/test_release_gate.py —— 智能体发布闸门（VER-27 前置，fail-closed）。
判据：全绿才出制品 + RELEASE-MANIFEST 随制品落档；
任一关失败（reconcile / 骨架漂移）→ 不出制品。

自嵌套豁免：test_real_gate_end_to_end 会真实执行发布闸门（内嵌全套布线 pytest）。
该文件随 INTEGRITY-34 补登进布线后，若闸门内照跑 e2e，将形成
gate → e2e → gate → e2e 的无限递归（第五轮评审实施中实测：140+ 进程爆炸、
并发 DECL 摘要瞬时漂移）。因此闸门子进程注入 AOS_IN_GATE=1，e2e 据此自跳——
文件仍在布线表内（N4 纪律：布线或显式豁免），豁免记录于此。
"""
import json
import os
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
@pytest.mark.skipif(os.environ.get("AOS_IN_GATE") == "1",
                    reason="闸门内自嵌套：e2e 会再启动全套布线 pytest（见模块 docstring）")
def test_real_gate_end_to_end(tmp_path):
    """真实闸门（真实测试套件）——发布侧 VER-27 前置的完整演练。"""
    report = release_gate.run_gate(out_dir=tmp_path)              # 不注入 stub
    assert report["ok"] is True, [(s["step"], s["ok"], s.get("detail", ""))
                                  for s in report["steps"]]       # 失败可诊断（N5 精神）
    detail = next(s["detail"] for s in report["steps"] if s["step"] == "tests")
    assert "全部通过" in detail

def test_gate_test_failure_detail_includes_output_tail(tmp_path, monkeypatch):
    """N5：嵌套 pytest 失败时 stdout/stderr 尾段进 detail，且 basetemp 固定在
    仓库外隔离目录——失败可诊断，"绿"不再依赖宿主临时目录策略。"""
    class _R:
        returncode = 1
        stdout = "....F\nFAILED tests/x.py::test_y - boom"
        stderr = "SAFE_DELETE_BULK_CONFIRM_REQUIRED count=2332"
    seen: dict = {}
    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return _R()
    monkeypatch.setattr(release_gate.subprocess, "run", fake_run)
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=release_gate._default_tests)
    tests = next(s for s in report["steps"] if s["step"] == "tests")
    assert not tests["ok"]
    assert "FAILED tests/x.py::test_y" in tests["detail"]        # 尾段可诊断
    assert "SAFE_DELETE" in tests["detail"]                      # stderr 同样保留
    assert any(str(c).startswith("--basetemp=") for c in seen["cmd"])  # basetemp 已固定
