"""tests/conformance/test_profile.py —— Feature Profile 解析器（依赖展开/生成序/锚点）。
判据：勾选即意图，展开即依赖（auth.oauth2_1 → governance.duty_matrix 等）；
拓扑序治理面在前（授权/审计的语义根）；未知能力/非法值/环/锚点缺失一律 fail-closed。
"""
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.profile import resolve, ProfileError, DEPENDENCIES, _topo
def test_real_profile_resolves():
    r = resolve()
    assert r["failures"] == []
    assert r["order"][0] == "governance.duty_matrix"          # 治理面是语义根，排在最前
    sel = r["selected"]
    assert sel["auth.oauth2_1"] == "declared"
    assert sel["backend.cqrs"] in ("declared", "implied")
def test_dependency_expansion():
    """只勾 frontend.admin_console → 自动补齐 backend.cqrs → governance.duty_matrix。"""
    sel = {"frontend.admin_console": "declared"}
    from kernel.profile import _expand
    sel = _expand(sel)
    assert sel["backend.cqrs"] == "implied"
    assert sel["governance.duty_matrix"] == "implied"
    assert _topo(sel)[0] == "governance.duty_matrix"
def test_token_binding_none_not_selected():
    """token_binding: none = 未选，不触发 oauth2_1 依赖。"""
    from kernel.profile import _selected_ids
    sel = _selected_ids({"auth": {"token_binding": "none"}})
    assert "auth.token_binding" not in sel
def test_illegal_token_binding_refused():
    from kernel.profile import _selected_ids
    with pytest.raises(ProfileError, match="VALUE-ILLEGAL"):
        _selected_ids({"auth": {"token_binding": "implicit"}})   # OAuth 2.1 已废除 implicit
def test_unknown_capability_refused():
    from kernel.profile import _selected_ids
    with pytest.raises(ProfileError, match="CAPABILITY-UNKNOWN"):
        _selected_ids({"backend": {"cqrs_typo": True}})
def test_unknown_family_refused():
    from kernel.profile import _selected_ids
    with pytest.raises(ProfileError, match="FAMILY-UNKNOWN"):
        _selected_ids({"blockchain": {"enabled": True}})
def test_dependency_graph_acyclic():
    """依赖图无环是硬约束：每个能力的前置不回指自身后代。"""
    seen: set[str] = set()
    def visit(cid: str, path: tuple[str, ...]):
        assert cid not in path, f"依赖环: {path + (cid,)}"
        for pre in DEPENDENCIES[cid]:
            visit(pre, path + (cid,))
    for cid in DEPENDENCIES:
        visit(cid, ())
def test_missing_profile_refused(tmp_path):
    with pytest.raises(ProfileError, match="PROFILE-MISSING"):
        resolve(root=tmp_path)
def test_anchor_missing_refused(tmp_path):
    """勾选了治理面但 spec/governance/ 无声明 → 拒绝（声明在场才是可生成依据）。"""
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "profile.yaml").write_text(yaml.safe_dump(
        {"profile": {"project": "t",
                     "capabilities": {"governance": {"duty_matrix": True}}}}),
        encoding="utf-8")
    r = resolve(root=tmp_path)
    assert any("ANCHOR-MISSING" in f and "governance" in f for f in r["failures"])
def test_anchor_present_passes(tmp_path):
    spec = tmp_path / "spec"
    spec.mkdir()
    (spec / "profile.yaml").write_text(yaml.safe_dump(
        {"profile": {"project": "t",
                     "capabilities": {"governance": {"duty_matrix": True}}}}),
        encoding="utf-8")
    (spec / "governance").mkdir()
    (spec / "governance" / "G.governance.yaml").write_text(
        "governance: G\nsteward: s\nduties:\n  - duty: d1\n", encoding="utf-8")
    r = resolve(root=tmp_path)
    assert r["failures"] == []
    assert r["order"] == ["governance.duty_matrix"]
