"""tests/conformance/test_codegen_openwebui.py —— ADR-006 前端生成能力守卫。

判据：frontend.open_webui 必须先在 profile 能力集注册；生成物只有胶水（Pipe /
compose / 使用说明），Open WebUI 源码不进实例树；Pipe 只读白名单与草稿通道
对账 tools/console.py 的治理纪律，角色只来自管理员映射；手改/摘除护栏与既有
生成物同构；正典零变化。
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from tools import codegen, console  # noqa: E402
from kernel.profile import DEPENDENCIES, DEPTH_PRESETS  # noqa: E402


def _pydantic_stub():
    """模板 venv 不装 pydantic（Open WebUI 运行时自带）；测试用最小替身。"""
    if "pydantic" in sys.modules:
        return

    class _Field:
        def __init__(self, default=None, **_kw):
            self.default = default

    class _BaseModel:
        def __init__(self, **kwargs):
            for key, value in vars(type(self)).items():
                if isinstance(value, _Field):
                    setattr(self, key, kwargs.get(key, value.default))

    mod = types.ModuleType("pydantic")
    mod.BaseModel = _BaseModel
    mod.Field = lambda default=None, **kw: _Field(default, **kw)  # noqa: E731
    sys.modules["pydantic"] = mod


def _load_pipe():
    _pydantic_stub()
    path = ROOT / "src/generated/openwebui_pipe.py"
    spec = importlib.util.spec_from_file_location("aoskeel_openwebui_pipe_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_capability_registered_with_discipline():
    """能力必须先注册；依赖含管理控制台与 OAuth2；minimal 预设不含。"""
    assert set(DEPENDENCIES["frontend.open_webui"]) == {
        "frontend.admin_console", "auth.oauth2_1"}
    assert "frontend.open_webui" in DEPTH_PRESETS["full"]
    assert "frontend.open_webui" in DEPTH_PRESETS["standard"]
    assert "frontend.open_webui" not in DEPTH_PRESETS["minimal"]
    assert "frontend.open_webui" in codegen.CAPABILITY_MODULES
    assert "frontend.open_webui" in codegen.ROOT_CAPABILITY_MODULES


def test_generated_glue_and_runtime_are_separated():
    """生成物只有胶水：Pipe + compose + 文档；不存在 Open WebUI 源码目录。"""
    report = codegen.generate()
    assert "openwebui_pipe.py" in report["files"]
    assert set(report["root_files"]) == {
        "docker-compose.openwebui.yml", "docs/OPENWEBUI.md"}
    pipe = (ROOT / "src/generated/openwebui_pipe.py").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.openwebui.yml").read_text(encoding="utf-8")
    doc = (ROOT / "docs/OPENWEBUI.md").read_text(encoding="utf-8")
    for text in (pipe, compose, doc):
        assert "AOS-ART-" in text
    assert "ghcr.io/open-webui/open-webui" in compose
    assert "docker-compose.openwebui.yml" in doc
    assert "WRITE_OPTIONS" in pipe          # 写面护栏在生成物中在场
    assert not (ROOT / "src/generated/open_webui").exists()
    assert "Kernel.submit(" not in pipe and "from kernel" not in pipe


def test_pipe_whitelist_matches_governance_console():
    """Pipe 白名单是治理壳的严格子集；治理签署子命令对一条不漏。"""
    mod = _load_pipe()
    assert set(mod.READONLY) <= console.ALLOWED
    assert set(mod.DRAFT_ONLY) <= console.ALLOWED
    for pair in console.DENIED_PAIRS:
        assert pair in mod.DENIED_PAIRS
    for argv in (["spec", "version"], ["spec", "register-declarations"],
                 ["draft", "promote"], ["release"], ["bootstrap"]):
        assert mod._authorized(argv) is False
    for argv in (["review"], ["spec", "fingerprint"], ["draft", "requirements.txt"]):
        assert mod._authorized(argv) is True


def test_write_options_and_unsafe_draft_names_are_refused():
    """CLI 的真实写面不得借只读白名单进入 Pipe（ADR-006 修订 1）。"""
    mod = _load_pipe()
    for argv in (["review", "--out", "spec/aos-spec.md"],
                 ["manual", "--out", "docs/X.md"],
                 ["extract", "a.txt", "--extractor", "evil.py"],
                 ["draft", "a.txt", "--name", "../escape"],
                 ["draft", "a.txt", "--name", "a/b"],
                 ["draft", "a.txt", "--name", ""]):
        assert mod._authorized(argv) is False, argv
    assert mod._authorized(["draft", "a.txt", "--name", "r-1"]) is True


def test_plain_text_never_dispatches_cli():
    """裸聊天文本只出帮助；不得被切词后当 CLI 执行。"""
    import asyncio
    mod = _load_pipe()
    ans = asyncio.run(mod.Pipe().pipe(
        {"messages": [{"role": "user", "content": "review --out spec/aos-spec.md"}]}, {}))
    assert "仅执行显式命令" in ans
    assert "REVIEW-WRITTEN" not in ans and "EXIT" not in ans


def test_draft_channel_requires_mapped_role(monkeypatch):
    """起草是写通道：无映射角色 fail-closed，且在派发前拒绝。"""
    mod = _load_pipe()
    pipe = mod.Pipe()
    pipe.valves.INSTANCE_ROOT = str(ROOT)
    calls: list = []

    class _Proc:
        returncode = 0
        stdout = "OK"
        stderr = ""

    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: (calls.append(a), _Proc())[1])
    assert "REFUSED" in pipe._run(["draft", "requirements-sample.txt"], {"id": "u-1"})
    assert calls == []
    pipe.valves.ROLE_MAP_JSON = '{"default": ["contract_steward"]}'
    assert pipe._run(["draft", "requirements-sample.txt"], {"id": "u-1"}).startswith("principal=")
    assert len(calls) == 1


def test_compose_is_hardened():
    """运行时默认面：本地端口、固定镜像、根只读、仅草稿可写、禁开放注册。"""
    text = (ROOT / "docker-compose.openwebui.yml").read_text(encoding="utf-8")
    assert "127.0.0.1:${AOS_OPENWEBUI_PORT" in text
    assert ":v0.13.4}" in text and ":main" not in text
    assert ":/aos-instance:ro" in text
    assert "/spec/drafts:/aos-instance/spec/drafts" in text
    assert 'ENABLE_SIGNUP: "${ENABLE_SIGNUP:-false}"' in text
    assert 'ENABLE_PIP_INSTALL_FRONTMATTER_REQUIREMENTS: "false"' in text


def test_roles_come_from_admin_mapping_only():
    """角色只认管理员 ROLE_MAP_JSON；聊天自报无效；非法映射 fail-closed。"""
    mod = _load_pipe()
    pipe = mod.Pipe()
    pipe.valves.ROLE_MAP_JSON = '{"admin": ["contract_steward"], "default": []}'
    assert pipe._roles({"id": "u-1", "role": "admin"}) == ("contract_steward",)
    assert pipe._roles({"id": "u-2", "role": "user"}) == ()
    pipe.valves.ROLE_MAP_JSON = "not json"
    assert pipe._roles({"id": "u-1", "role": "admin"}) == ()
    assert pipe._principal({"email": "a@b.c", "id": "u-1"}) == "a@b.c"


def test_path_and_generation_guards():
    """路径护栏拒绝越界；字节漂移与手改拒绝走既有生成器护栏。"""
    mod = _load_pipe()
    root = ROOT
    assert mod._safe_args(root, ["draft", "requirements-sample.txt"]) is True
    assert mod._safe_args(root, ["draft", "../secrets.txt"]) is False
    assert mod._safe_args(root, ["draft", str(ROOT.parent / "secrets.txt")]) is False
    p = ROOT / "src/generated/openwebui_pipe.py"
    original = p.read_bytes()
    try:
        p.write_bytes(original + b"\n# human hack\n")
        with pytest.raises(codegen.CodegenDrift, match="禁止静默覆盖"):
            codegen.generate()
        codegen.generate(force=True)
        assert b"human hack" not in p.read_bytes()
    finally:
        p.write_bytes(original)


def test_capability_gating_prunes_glue(tmp_path, monkeypatch):
    """能力关闭时模块与根层生成物一并摘除——在沙箱内验证，不删工作区受控字节。"""
    sandbox = tmp_path / "sandbox"
    (sandbox / "src/generated").mkdir(parents=True)
    (sandbox / "config").mkdir()
    (sandbox / "config/capabilities.yaml").write_bytes(
        (ROOT / "config/capabilities.yaml").read_bytes())
    monkeypatch.setattr(codegen, "ROOT", sandbox)
    monkeypatch.setattr(codegen, "OUT_DIR", sandbox / "src/generated")
    first = codegen.generate(force=True)
    assert "openwebui_pipe.py" in first["files"]
    assert set(first["root_files"]) == {
        "docker-compose.openwebui.yml", "docs/OPENWEBUI.md"}
    empty = {"project": "t", "selected": {}, "order": [], "values": {}, "failures": []}
    monkeypatch.setattr(codegen, "profile_resolve", lambda *a, **k: empty)
    r = codegen.generate(force=True)
    assert "openwebui_pipe.py" in r["pruned"]
    assert set(r["pruned"]) >= {"docker-compose.openwebui.yml", "docs/OPENWEBUI.md"}
    assert not (sandbox / "src/generated/openwebui_pipe.py").exists()
    assert not (sandbox / "docker-compose.openwebui.yml").exists()
    assert not (sandbox / "docs/OPENWEBUI.md").exists()


def test_init_carries_openwebui_glue(tmp_path):
    """aos init 产出的实例自带 compose 与使用说明（根层白名单之外的补位）。"""
    from cli.main import cmd_init
    dst = tmp_path / "myorg-system"
    assert cmd_init(str(dst)) == 0
    assert (dst / "docker-compose.openwebui.yml").is_file()
    assert (dst / "docs/OPENWEBUI.md").is_file()
    assert (dst / "src/generated/openwebui_pipe.py").is_file()
    prof = (dst / "spec/profile.yaml").read_text(encoding="utf-8")
    assert "open_webui: true" in prof


def test_canonical_untouched():
    """正典零变化：generate 是声明驱动输出端，spec/ 内容哈希不变。"""
    import hashlib

    def snap():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted((ROOT / "spec").rglob("*")) if p.is_file()}
    before = snap()
    codegen.generate(force=True)
    assert snap() == before
