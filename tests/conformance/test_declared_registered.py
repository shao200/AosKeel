"""tests/conformance/test_declared_registered.py —— 持续一致性核对（INV-13 / KS-7.2 第 5 步）。
declared == registered：spec/ 声明（含内建）经五步管线后与 capabilities.yaml
generated 段逐条一致；生成段每条携带 provenance（2.4 / KS-8.2）；
固定段在位（INV-6 / INV-11）；spec_ref 指向登记表最新条目（GOV-2.2）。
"""
import re
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import RegistrationFailed
from kernel.registration import run_pipeline, load_caps, GENESIS_BUILTINS, reconcile_bijection

def test_pipeline_reconciles():
    """五步管线跑通 = declared == registered（任一步失败抛 RegistrationFailed）。"""
    gen = run_pipeline()
    assert gen["write_actions"] and gen["channel_writes"]

def test_reconcile_is_explicit_bijection():
    """双射判据：顺序无关；重复 id / 任一侧缺项 / 同 id 内容漂移均 fail-closed。"""
    a = [{"id": "A", "v": True}, {"id": "B", "v": "x"}]
    reconcile_bijection(a, list(reversed(a)), "write_actions")     # 顺序不敏感

    cases = [
        ([{"id": "A"}, {"id": "A"}], a, "重复 id"),                # registered 侧重复
        (a, [{"id": "A"}, {"id": "A"}], "重复 id"),                # declared 侧重复
        (a, [{"id": "A", "v": True}], "missing"),                  # 缺项
        (a, [{"id": "A", "v": False}, {"id": "B", "v": "x"}], "drift"),  # 同 id 内容漂移
    ]
    for declared, registered, needle in cases:
        with pytest.raises(RegistrationFailed, match="RECONCILE-FAILED") as exc:
            reconcile_bijection(declared, registered, "write_actions")
        assert needle in str(exc.value)

def test_generated_entries_have_provenance():
    caps = load_caps()
    for seg in ("write_actions", "channel_writes"):
        for e in caps.get(seg, []):
            assert "provenance" in e, f"{seg}/{e.get('id')} 缺 provenance（KS-8.2）"
            assert e["provenance"] in ("genesis",) or re.match(r"SPEC-\d{4}-\d+", e["provenance"]), \
                f"{seg}/{e.get('id')} provenance 非法: {e['provenance']}"

def test_fixed_sections_in_place():
    caps = load_caps()
    assert caps.get("foundation") == ["audit_append_only", "perimeter_integrity",
                                      "breakglass_resonant"], "INV-6 基座仅三项"
    assert sorted(caps.get("forbidden", [])) == sorted(
        ["modify_foundation", "direct_event_write", "history_rewrite",
         "extinguish_override"]), "INV-11 forbidden 四项在位"

def test_spec_ref_points_to_registry():
    registry = ROOT / "docs/ARTIFACT-REGISTRY.md"
    caps = load_caps()
    if not registry.exists():
        assert caps.get("spec_ref") == "PENDING"   # 未登记：占位符合 GOV-2.3
        return
    rows = [l for l in registry.read_text(encoding="utf-8").splitlines()
            if l.startswith("| AOS-ART-")]
    assert rows, "登记表存在但无条目"
    latest = rows[-1].split("|")[1].strip()
    assert caps.get("spec_ref") == latest, \
        f"GOV-2.2: spec_ref {caps.get('spec_ref')} ≠ 登记表最新条目 {latest}"
