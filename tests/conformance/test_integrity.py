"""tests/conformance/test_integrity.py —— 修补守卫回归集（不新增 VER 条款）。

由 config/verification.yaml 的 integrity_paths 段纳入发布闸门。每一项对应一个
实测发现的缺口，判据都是可计算的量（次数、条数、字节），不是"看起来正常"：

1. KS-1.4 / VER-3：版本冲突后结构 + 条件必须重跑，而非仅换版本号重试追加；
2. KS-1.3：一次拒绝恰好一条 structurally-rejected 审计（不得双记）；
3. GOV-2.3 / `* -text`：全部写入点 UTF-8 + LF，闸门不改写生成物字节；
4. 承重件：verification.yaml 用真 YAML 解析，格式微调不丢项、缺路径即阻断；
5. 能力清单：带逗号/引号的值不被拆键；
6. CLI：参数缺失返回明确 REFUSED，不丢裸 traceback；
7. GOV-2.2：两份配置的 spec_ref 与登记表最新条目一致；
8. 控制台入口：`[project.scripts]` 生成的 aos.exe 固定调用无参 main()，argv 必须可省略；
9. 运行环境：pytest 为声明的运行时依赖，缺失时 aos test 报 PYTEST-MISSING 阻断。
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))

PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}


# ---------- 1. 冲突后的完整重求值 ----------
def test_conflict_reevaluates_full_pipeline(monkeypatch):
    import kernel.pipeline as P
    from kernel.store import EventStore, VersionConflict
    from kernel.session import SessionChannel
    from kernel.registration import compile_all

    counts = {"struct": 0, "bool": 0, "commit": 0}
    orig_s, orig_b = P.run_structural, P.eval_boolean

    def counted_s(*a, **k):
        counts["struct"] += 1
        return orig_s(*a, **k)

    def counted_b(*a, **k):
        counts["bool"] += 1
        return orig_b(*a, **k)

    monkeypatch.setattr(P, "run_structural", counted_s)
    monkeypatch.setattr(P, "eval_boolean", counted_b)
    k = P.Kernel(EventStore(), SessionChannel(), compile_all())
    real = k.store.commit
    calls = {"n": 0}

    def racing(*a):
        calls["n"] += 1
        counts["commit"] += 1
        if calls["n"] == 1:
            real(*a)                                  # 并发者抢先写入
            raise VersionConflict("模拟并发写入")
        return real(*a)

    monkeypatch.setattr(k.store, "commit", racing)
    ev = k.submit("ApproveContract", PARAMS, "contract_steward")
    assert ev is not None and counts["commit"] == 2
    assert counts["struct"] == counts["commit"], "结构校验未随重求值重跑（KS-1.4）"
    assert counts["bool"] == counts["commit"], "条件求值未随重求值重跑（KS-1.4）"
    assert len(k.interpreter_audit) == counts["bool"], "每轮评估应各留一条 KS-3.3 审计"


def test_single_rejection_single_audit():
    from kernel.store import EventStore, VersionConflict
    st = EventStore()
    p = dict(PARAMS, valid_time="2026-01-01T00:00:00+00:00")
    st.commit("ApproveContract", "domain:ContractAggregate", 0, "ApproveContract@1", p, "svc")
    with pytest.raises(VersionConflict):
        st.commit("ApproveContract", "domain:ContractAggregate", 0, "ApproveContract@1", p, "svc")
    rejected = [a for a in st.audit if a["kind"] == "structurally-rejected"]
    assert len(rejected) == 1, f"一次拒绝应恰好一条审计，实得 {len(rejected)}"


# ---------- 2. 字节精确 ----------
def _generated_bytes() -> dict:
    return {p.name: p.read_bytes() for p in (ROOT / "src/generated").glob("*.py")}


def test_generated_files_are_lf_bytes():
    from tools import codegen
    before = _generated_bytes()
    codegen.generate()                                  # 无漂移 → 不应改写一个字节
    after = _generated_bytes()
    assert before == after, "再生成改变了字节（含换行符）"
    assert all(b"\r\n" not in b for b in after.values()), "生成物出现 CRLF（* -text）"


def test_release_gate_keeps_generated_bytes(tmp_path):
    from tools import release_gate
    before = _generated_bytes()
    report = release_gate.run_gate(out_dir=tmp_path, run_tests=lambda: "stub")
    assert report["ok"] is True
    assert before == _generated_bytes(), "发布闸门改写了生成物字节"
    manifest = (tmp_path / "RELEASE-MANIFEST.json").read_bytes()
    assert b"\r\n" not in manifest, "签发清单出现 CRLF"


def _hs_sandbox(tmp_path, monkeypatch):
    import tools.hash_spec as hs
    (tmp_path / "config").mkdir(); (tmp_path / "docs").mkdir()
    (tmp_path / "config/capabilities.yaml").write_bytes(b"spec_ref: AOS-ART-000\n")
    (tmp_path / "config/verification.yaml").write_bytes(
        b"version: 1\nspec_ref: AOS-ART-000\nver: []\n")
    (tmp_path / "docs/aos-spec.md").write_bytes(b"# v1\n")
    (tmp_path / "docs/SPEC-FINGERPRINT.md").write_bytes(b"# F\n")
    monkeypatch.setattr(hs, "ROOT", tmp_path)
    monkeypatch.setattr(hs, "REGISTRY", tmp_path / "docs/ARTIFACT-REGISTRY.md")
    monkeypatch.setattr(hs, "CAPS", tmp_path / "config/capabilities.yaml")
    return hs


def test_register_writes_lf_and_syncs_spec_ref(tmp_path, monkeypatch):
    hs = _hs_sandbox(tmp_path, monkeypatch)
    assert hs.register("v1") == 0
    for rel in ("config/capabilities.yaml", "config/verification.yaml",
                "docs/ARTIFACT-REGISTRY.md"):
        assert b"\r\n" not in (tmp_path / rel).read_bytes(), f"{rel} 出现 CRLF"
    a = re.search(rb"spec_ref:\s*(AOS-ART-\d+)",
                  (tmp_path / "config/capabilities.yaml").read_bytes()).group(1)
    b = re.search(rb"spec_ref:\s*(AOS-ART-\d+)",
                  (tmp_path / "config/verification.yaml").read_bytes()).group(1)
    assert a == b == b"AOS-ART-001", "GOV-3 回填必须同步两份配置"


def test_apply_generated_keeps_lf_bytes(tmp_path, monkeypatch):
    from kernel import registration
    p = tmp_path / "capabilities.yaml"
    p.write_bytes((ROOT / "config/capabilities.yaml").read_bytes())
    monkeypatch.setattr(registration, "CAPS", p)
    registration.apply_generated()
    assert b"\r\n" not in p.read_bytes(), "P-5 单写者引入了 CRLF"


# ---------- 3. 承重件解析 ----------
def _wiring_sandbox(tmp_path, text: str, skip: tuple[str, ...] = ()):
    (tmp_path / "config").mkdir(exist_ok=True)
    (tmp_path / "config/verification.yaml").write_bytes(text.encode("utf-8"))
    data = yaml.safe_load(text)
    for e in list(data["ver"]) + list(data.get("integrity_paths", []) or []):
        if e.get("path") and e["path"] not in skip:
            q = tmp_path / e["path"]
            q.parent.mkdir(parents=True, exist_ok=True)
            q.write_bytes(b"# stub\n")
    return tmp_path


def test_wiring_survives_valid_yaml_variants(tmp_path):
    from tools import wiring
    base = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    expected = len(wiring.wired_paths())
    line = "- { id: VER-1,  clause: KS-1.2,      kind: auto, path: tests/conformance/test_event_schema.py }"
    variants = {
        "baseline": base,
        "quoted path": base.replace(
            "path: tests/conformance/test_event_schema.py",
            'path: "tests/conformance/test_event_schema.py"'),
        "reordered keys": base.replace(
            line,
            "- { path: tests/conformance/test_event_schema.py, id: VER-1, "
            "clause: KS-1.2, kind: auto }"),
    }
    for name, text in variants.items():
        sandbox = tmp_path / name.replace(" ", "_")
        sandbox.mkdir()
        _wiring_sandbox(sandbox, text)
        assert len(wiring.wired_paths(root=sandbox)) == expected, f"{name} 静默丢项"


def test_wiring_blocks_declared_but_missing_path(tmp_path):
    from tools import wiring
    base = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    broken = base.replace("path: tests/conformance/test_event_schema.py",
                          "path: tests/conformance/__deleted__.py")
    _wiring_sandbox(tmp_path, broken, skip=("tests/conformance/__deleted__.py",))
    with pytest.raises(wiring.WiringError, match="不存在"):
        wiring.wired_paths(root=tmp_path)


def test_load_caps_parses_quoted_comma_value(tmp_path, monkeypatch):
    from kernel import registration
    variant = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8").replace(
        "provenance: genesis", 'provenance: "SPEC-2026-014, addendum"')
    p = tmp_path / "capabilities.yaml"
    p.write_bytes(variant.encode("utf-8"))
    monkeypatch.setattr(registration, "CAPS", p)
    entry = registration.load_caps()["write_actions"][0]
    assert entry["provenance"] == "SPEC-2026-014, addendum"
    assert len(entry) == 4, f"带逗号的值被拆成额外键: {entry}"
    assert not any(k.endswith('"') for k in entry), f"残留引号键: {entry}"


def test_spec_ref_consistent_across_configs():
    """两份配置必须一致（所有环境）；登记条目只在实例已 BOOT-0 登记后比对。

    aos init 故意不复制 ARTIFACT-REGISTRY.md（实例自行登记，GOV-2.3），
    因此未登记的实例仍应能通过配置间一致性守卫，不把正常启动序列误判为漂移。
    """
    caps = yaml.safe_load((ROOT / "config/capabilities.yaml").read_text(encoding="utf-8"))
    ver = yaml.safe_load((ROOT / "config/verification.yaml").read_text(encoding="utf-8"))
    assert caps["spec_ref"] == ver["spec_ref"], "两份配置 spec_ref 漂移（GOV-2.2）"
    registry = ROOT / "docs/ARTIFACT-REGISTRY.md"
    if registry.exists():
        rows = [l for l in registry.read_text(encoding="utf-8").splitlines()
                if l.startswith("| AOS-ART-")]
        if rows:
            latest = rows[-1].split("|")[1].strip()
            assert caps["spec_ref"] == latest, "配置与登记条目漂移（GOV-2.2）"


# ---------- 4. CLI 失败形态 ----------
@pytest.mark.parametrize("args", [
    ("bootstrap", "--stage"),
    ("spec", "version", "v3", "--proposal-ref"),
    ("draft", "promote"),
    ("draft",),
    ("test", "--suite"),
    ("generate", "--name"),
])
def test_cli_missing_args_refused_cleanly(args):
    r = subprocess.run([sys.executable, "-m", "src.cli.main", *args],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr, f"{args} 抛了裸异常: {r.stderr[:200]}"
    assert "REFUSED" in r.stdout or "用法" in r.stdout


# ---------- 8. 控制台脚本入口：main() 必须可无参调用 ----------
def test_console_script_calls_main_without_args():
    """复现 aos.exe/__main__.py 的 `sys.exit(main())`；python -m 路径测不到这条。

    元数据断言只在模板根执行：aos init 只复制八个目录，实例侧没有 pyproject.toml，
    但无参调用这一行为在模板与实例中都必须成立（VER-27 前置不能被环境差异击穿）。
    """
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        import tomllib
        meta = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        assert meta["project"]["scripts"]["aos"] == "src.cli.main:main"
    r = subprocess.run(
        [sys.executable, "-c",
         "from src.cli.main import main; raise SystemExit(main())", "--help"],
        cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, f"console script 形态失败: {r.stderr[:300]}"
    assert "TypeError" not in r.stderr
    assert "用法" in r.stdout, "无参入口未落到 USAGE 分派"


def test_pytest_is_declared_runtime_dependency():
    """CI 曾手工装 pytest，纯净 venv 里 python -m pytest 直接 No module named pytest。

    声明断言只在模板根执行（实例无 pyproject.toml）；可探测性守卫两边都跑。
    """
    from tools import wiring
    pyproject = ROOT / "pyproject.toml"
    if pyproject.exists():
        import tomllib
        meta = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        deps = " ".join(meta["project"]["dependencies"])
        assert re.search(r"pytest\s*>=", deps), "pytest 未声明为运行时依赖"
    assert wiring.require_pytest() is None, "当前环境应能探测到 pytest"


def test_missing_pytest_blocks_cmd_test(monkeypatch, capsys):
    """执行引擎缺失 = fail-closed 明确拒绝，且不把 ImportError 当成套件失败。"""
    import importlib
    from tools import wiring
    cli = importlib.import_module("src.cli.main")

    def missing():
        raise wiring.WiringError("PYTEST-MISSING: 缺少 pytest —— 执行 pip install -e .")

    monkeypatch.setattr(wiring, "require_pytest", missing)
    monkeypatch.setattr(cli.subprocess, "call", lambda *a, **k: 999)
    assert cli.cmd_test(None) == 1
    assert "PYTEST-MISSING" in capsys.readouterr().out
