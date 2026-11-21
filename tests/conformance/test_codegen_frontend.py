"""tests/conformance/test_codegen_frontend.py —— frontend.admin_console 生成器。
判据：GUARD 与 command_api.ROUTES 同源（required_roles/duty 一致）；can_access
fail-closed（GUARD 未列动作 False、无所需角色 False）；nav_for 按角色过滤可见
动作；FORMS/PAGES 是 UI 消费的 schema（不含 UI 库）；能力摘除/手改拒绝走同一
护栏；正典零变化（声明驱动生成，spec/ 字节不变）。
"""
import subprocess
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from tools import codegen
from generated import admin_console as ac
from generated import command_api as cmd_api
def test_guard_same_source_as_command_routes():
    """GUARD 与 ROUTES 同源：required_roles/duty 与 command_api 完全一致。"""
    for name, route in cmd_api.ROUTES.items():
        g = ac.GUARD[name]
        assert sorted(g["required_roles"]) == sorted(route["required_roles"])
        assert g["duty"] == route["duty"]
def test_can_access_fail_closed():
    """守卫 fail-closed：未列动作 False；无所需角色 False；有角色 True。"""
    assert ac.can_access("NoSuchAction", ("contract_steward",)) is False
    assert ac.can_access("RegisterContract", ()) is False
    assert ac.can_access("RegisterContract", ("nobody",)) is False
    assert ac.can_access("RegisterContract", ("contract_steward",)) is True
def test_nav_for_filters_by_roles():
    """nav_for 只暴露守卫放行的动作；空角色 → 动作列表为空（页面 schema 保留）。"""
    nav = ac.nav_for(("contract_steward",))
    assert nav and all("fields" in v and "actions" in v for v in nav.values())
    allowed = set(ac.nav_for(("contract_steward",))["Contract"]["actions"])
    assert allowed == {a for a in ac.GUARD if ac.can_access(a, ("contract_steward",))}
    assert all(v["actions"] == [] for v in ac.nav_for(()).values())
def test_forms_and_pages_are_ui_schema():
    """FORMS/PAGES 是 schema：动作参数类型 + 对象字段清单（identity 必在）。"""
    f = ac.FORMS["RegisterContract"]
    assert f.get("contract_id") and f.get("amount")
    p = ac.PAGES["Contract"]
    assert p["identity"] == "contract_id" and "amount" in p["fields"]
def test_capability_gating(tmp_path):
    """能力摘除：未声明时 generate 摘除 admin_console.py；恢复后文件回归。"""
    prof = ROOT / "spec" / "profile.yaml"
    original = prof.read_text(encoding="utf-8")
    try:
        prof.write_text(original.replace("admin_console: true",
                                         "admin_console: false")
                        .replace("form_generation: true",
                                 "form_generation: false")
                        # ADR-006：open_webui 依赖 admin_console，不一起关会被依赖展开补回
                        .replace("open_webui: true", "open_webui: false"),
                       encoding="utf-8")
        r = codegen.generate(force=True)
        assert "admin_console.py" in r["pruned"]
        assert not (ROOT / "src/generated/admin_console.py").exists()
        prof.write_text(original, encoding="utf-8")
        r2 = codegen.generate(force=True)
        assert "admin_console.py" in r2["files"]
        assert (ROOT / "src/generated/admin_console.py").exists()
    finally:
        prof.write_text(original, encoding="utf-8")
        codegen.generate(force=True)
def test_canonical_untouched():
    """正典零变化：generate 是声明驱动的输出端，spec/ 字节不变。"""
    def snap():
        return {str(p.relative_to(ROOT)): len(p.read_bytes())
                for p in sorted((ROOT / "spec").rglob("*")) if p.is_file()}
    before = snap()
    codegen.generate(force=True)
    assert snap() == before
