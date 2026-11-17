"""tests/conformance/test_onboarding_init.py —— aos init 初始化向导。
判据：depth 预设 ± --cap/--no-cap → spec/profile.yaml（同一解析器自校验）；
已初始化拒绝（append-only，--force 显式重铺）；未知能力/非法深度拒绝；
新项目锚点缺失不阻断 —— failures 作为待声明 roadmap 返回；产出可被 resolve() 复读。
"""
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.profile import init_profile, resolve, ProfileError, DEPTH_PRESETS
def test_minimal_init_writes_resolvable_profile(tmp_path):
    r = init_profile("proj-a", "minimal", root=tmp_path)
    assert r["order"][0] == "governance.duty_matrix"      # 治理面先行（语义根）
    assert r["selected"] == {"governance.duty_matrix": "declared"}
    # 落盘产出可被同一解析器复读（自校验闭环）
    r2 = resolve(root=tmp_path)
    assert r2["project"] == "proj-a" and r2["depth"] == "minimal"
    # 新项目无声明 → 锚点缺失作为 roadmap，不阻断 init
    assert any("ANCHOR-MISSING" in f for f in r2["failures"])
def test_full_depth_covers_all_modules(tmp_path):
    r = init_profile("proj-b", "full", root=tmp_path)
    assert {"frontend.admin_console", "auth.oauth2_1", "backend.cqrs",
            "governance.duty_matrix"} <= set(r["selected"])
    assert r["values"]["auth.token_binding"] == "dpop"
def test_cap_add_triggers_dependency_expansion(tmp_path):
    """minimal 只勾治理面，--cap frontend.admin_console → 后端链自动展开。"""
    r = init_profile("proj-c", "minimal", add=("frontend.admin_console",),
                     root=tmp_path)
    assert r["selected"]["backend.cqrs"] == "implied"     # 依赖展开兜底
    assert r["selected"]["governance.duty_matrix"] in ("declared", "implied")
def test_cap_remove(tmp_path):
    r = init_profile("proj-d", "standard", remove=("auth.token_binding",),
                     root=tmp_path)
    assert "auth.token_binding" not in r["selected"]
    assert "auth.oauth2_1" in r["selected"]               # 其余预设保留
def test_unknown_cap_refused(tmp_path):
    with pytest.raises(ProfileError, match="INIT-CAP-UNKNOWN"):
        init_profile("proj-e", "minimal", add=("backend.cqrs_typo",), root=tmp_path)
def test_illegal_depth_refused(tmp_path):
    with pytest.raises(ProfileError, match="INIT-DEPTH-ILLEGAL"):
        init_profile("proj-f", "mega", root=tmp_path)
def test_missing_name_refused(tmp_path):
    with pytest.raises(ProfileError, match="INIT-NAME-REQUIRED"):
        init_profile("", "minimal", root=tmp_path)
def test_existing_profile_refused_without_force(tmp_path):
    init_profile("proj-g", "minimal", root=tmp_path)
    with pytest.raises(ProfileError, match="INIT-EXISTS"):
        init_profile("proj-h", "standard", root=tmp_path)
    r = init_profile("proj-h", "standard", root=tmp_path, force=True)
    assert r["depth"] == "standard"
    assert resolve(root=tmp_path)["project"] == "proj-h"  # --force 重铺生效
def test_presets_shape():
    """预设必须是能力集的合法子集（防预设漂移到已删能力上）。"""
    from kernel.profile import DEPENDENCIES
    for preset in DEPTH_PRESETS.values():
        assert set(preset) <= set(DEPENDENCIES)
def test_cmd_init_fail_fast_before_copy(tmp_path):
    """复盘修复回归：非法 depth 在实例化**之前**拒绝 —— 不留半成品目录。"""
    import subprocess
    target = tmp_path / "waste-dir"
    r = subprocess.run([sys.executable, str(ROOT / "src/cli/main.py"), "init",
                        str(target), "--name", "w", "--depth", "bogus"],
                       capture_output=True, text=True, cwd=ROOT)
    assert r.returncode == 1 and "INIT-PROFILE-REFUSED" in r.stdout
    assert not target.exists()                          # fail-fast：目录未创建
def test_value_domain_enforced_on_init(tmp_path):
    """init 走同一值域校验：token_binding 只能从预设/合法值进入。"""
    assert DEPTH_PRESETS["standard"]["auth.token_binding"] == "dpop"
    r = init_profile("proj-i", "standard", root=tmp_path)
    assert r["values"]["auth.token_binding"] == "dpop"
def test_yaml_output_structure(tmp_path):
    init_profile("proj-j", "minimal", root=tmp_path)
    data = yaml.safe_load((tmp_path / "spec/profile.yaml").read_text(encoding="utf-8"))
    prof = data["profile"]
    assert prof["project"] == "proj-j" and prof["depth"] == "minimal"
    assert prof["capabilities"]["governance"]["duty_matrix"] is True
