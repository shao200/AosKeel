"""tests/conformance/test_codegen_cqrs.py —— backend.cqrs 能力模块生成器。
判据：Profile 门控（backend.cqrs → command_api/query_api，未声明 → 摘除，
手改 → 拒绝摘除）；Command 路由表携带治理授权链（required_roles / duty，
OAuth2.1 claims 对接面）；dispatch 走同一条提交管线（INV-1）；Query 端纯读。
"""
import importlib.util
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import codegen
from tools.codegen import generate, CodegenProfile, CodegenDrift
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import PermissionDenied
@pytest.fixture(scope="module", autouse=True)
def _generate():
    generate()                     # 生成物随模块测试刷新（声明驱动，幂等）
def _load(filename):
    spec = importlib.util.spec_from_file_location(
        f"gen_cqrs_{filename[:-3]}", ROOT / f"src/generated/{filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def _kernel():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_route_metadata_carries_governance_chain():
    """L4 锚点：路由表暴露 required_roles 与治理职责项（图1 → 图4 的对接面）。"""
    mod = _load("command_api.py")
    route = mod.ROUTES["ApproveContract"]
    assert route["required_roles"] == ("contract_steward",)
    assert route["duty"] == "approve_contract_duty"          # 治理授权链来源
    assert route["provenance"] == "SPEC-2026-014"
    assert {"RegisterContract", "ApproveContract", "VoidContract"} <= set(mod.ROUTES)
def test_dispatch_uses_same_pipeline():
    """dispatch → handler → kernel.submit：唯一写路径（INV-1），无绕行。"""
    src = (ROOT / "src/generated/command_api.py").read_text(encoding="utf-8")
    for banned in ("store.commit", "_append", "write_raw", "session_append"):
        assert banned not in src
    k = _kernel()
    ev = mod = _load("command_api.py").dispatch(
        k, "ApproveContract", "contract_steward",
        roles=("contract_steward",), contract_id="C-1",
        status="pending", amount=500000)                     # 快照字段透传
    assert ev.stream_id == "domain:ContractAggregate"
def test_dispatch_fail_closed_without_roles():
    """未出示角色 = 无权（kernel P-10/INV-4 强制；dispatch 不复判也不放行）。"""
    with pytest.raises(PermissionDenied):
        _load("command_api.py").dispatch(
            _kernel(), "ApproveContract", "contract_steward", contract_id="C-1")
def test_dispatch_unrouted_refused():
    with pytest.raises(KeyError, match="UNROUTED"):
        _load("command_api.py").dispatch(_kernel(), "NoSuchAction", "p")
def test_query_read_side():
    """Query 端纯读：get/list 只读 reducer 折叠的投影状态。"""
    reducers = _load("reducers.py")
    queries = _load("query_api.py")
    from types import SimpleNamespace
    state = reducers.reduce_contract({}, SimpleNamespace(payload={
        "contract_id": "C-1", "status": "pending", "amount": 500000,
        "valid_time": "2026-01-01"}))
    assert queries.QUERIES["ContractAggregate.get"] is queries.get_contract
    assert queries.get_contract(state, "C-1")["status"] == "pending"
    rows = queries.list_contract(state)
    assert len(rows) == 1 and rows[0]["contract_id"] == "C-1"
    assert queries.get_contract(state, "NOPE") is None       # 未投影实例 → None（容错）
def test_deselected_capability_pruned(monkeypatch):
    """门控摘除：能力未声明 → 对应生成物摘除（模糊时宁拒勿删，摘除须 --force）；
    恢复声明 → 重生。"""
    codegen.generate(force=True)               # 先同步磁盘为当前声明驱动结果
    empty = {"project": "t", "selected": {}, "order": [], "values": {}, "failures": []}
    monkeypatch.setattr(codegen, "profile_resolve", lambda *a, **k: empty)
    try:
        report = codegen.generate(force=True)  # 摘除全部未声明能力模块
        assert sorted(report["pruned"]) == ["admin_console.py", "auth_oauth2.py",
                                            "command_api.py", "query_api.py"]
        assert not (ROOT / "src/generated/command_api.py").exists()
    finally:
        monkeypatch.undo()         # 先解除补丁再恢复，否则恢复本身仍走空 profile
        generate()                 # 恢复真实生成物，不污染工作区
    assert (ROOT / "src/generated/command_api.py").exists()
def test_hand_modified_deselected_module_refused(monkeypatch, tmp_path):
    """手改的未声明能力模块：禁止静默删除（与覆盖同一护栏）。"""
    empty = {"project": "t", "selected": {}, "order": [], "failures": []}
    monkeypatch.setattr(codegen, "profile_resolve", lambda *a, **k: empty)
    p = ROOT / "src/generated/command_api.py"
    original = p.read_bytes()
    try:
        p.write_bytes(original + "\n# human hack\n".encode("utf-8"))
        with pytest.raises(CodegenDrift, match="禁止静默删除"):
            codegen.generate()
    finally:
        p.write_bytes(original)
        monkeypatch.undo()
        generate()
def test_profile_refused_blocks_generation(monkeypatch):
    """Profile 锚点缺失 → 生成拒绝（先补声明，再生成 —— fail-closed）。"""
    failed = {"project": "t", "selected": {}, "order": [],
              "failures": ["PROFILE-ANCHOR-MISSING: x"]}
    monkeypatch.setattr(codegen, "profile_resolve", lambda *a, **k: failed)
    with pytest.raises(CodegenProfile, match="PROFILE-REFUSED"):
        codegen.generate()
    monkeypatch.undo()
    generate()                     # 恢复（真实 profile 全绿）
