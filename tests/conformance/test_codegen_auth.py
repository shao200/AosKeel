"""tests/conformance/test_codegen_auth.py —— auth.oauth2_1 能力模块生成器。
判据（OAuth 2.1 最小 IdP，声明驱动）：
- 仅 Authorization Code + PKCE（S256）；plain/隐式无生成路径；
- claims 由治理面投影：roles ⊆ 声明岗位（UNDECLARED-POSITION 拒绝），duties 不可自报；
- issue_token 强制 assignment_ref（外部 authN 凭据引用，T03/GOV-1 同构）；
- 授权码一次性 · redirect_uri 白名单 · DPoP 绑定（cnf.jkt）与证明重放核对；
- 密钥缺失 → 不签发不验证（fail-closed）；authorize() 与 command_api 路由对账。
"""
import base64
import hashlib
import importlib.util
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import codegen
from tools.codegen import generate
VERIFIER = "correct-horse-battery-staple-0123456789abcdef"
JKT = base64.urlsafe_b64encode(hashlib.sha256(b"dpop-key").digest()).rstrip(b"=").decode()
def _challenge(verifier=VERIFIER):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
@pytest.fixture(scope="module", autouse=True)
def _generate():
    generate()
def _load():
    spec = importlib.util.spec_from_file_location("gen_auth", ROOT / "src/generated/auth_oauth2.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
@pytest.fixture()
def idp(monkeypatch):
    monkeypatch.setenv("AOS_IDP_SECRET", "unit-test-secret-not-for-production")
    m = _load()
    m.register_client("console", ["https://app.example.com/cb"], scopes=("domain",))
    return m
def _flow(idp, **issue_kw):
    code = idp.begin_authorization("console", "https://app.example.com/cb",
                                   ["domain"], _challenge(), "S256")
    grant = idp.exchange_code("console", code, "https://app.example.com/cb", VERIFIER)
    kw = dict(principal="alice", roles=("contract_steward",),
              assignment_ref="BOOT-2026-001", dpop_jkt=JKT)
    kw.update(issue_kw)
    return idp.issue_token(grant, **kw)
def test_gov_positions_projection():
    """claims 唯一语义来源：岗位 → duties/org_units/authorizes 全部来自治理面声明。"""
    m = _load()
    e = m.GOV_POSITIONS["contract_steward"]
    assert set(e["duties"]) == {"register_contract_duty", "approve_contract_duty",
                                "void_contract_duty"}
    assert e["org_units"] == ["contract-department"]
    assert set(e["authorizes"]) == {"ApproveContract", "RegisterContract", "VoidContract"}
def test_full_flow_issue_and_verify(idp):
    token = _flow(idp)
    claims = idp.verify_token(token, dpop_jkt=JKT)
    assert claims["roles"] == ["contract_steward"]
    assert claims["duties"] == sorted(idp.GOV_POSITIONS["contract_steward"]["duties"])
    assert claims["asg"] == "BOOT-2026-001"          # 外部凭据引用进 token（可审计）
    assert claims["cnf"]["jkt"] == JKT               # DPoP 绑定
def test_pkce_plain_refused(idp):
    """OAuth 2.1 废除 plain —— 无降级路径。"""
    with pytest.raises(idp.AuthRefused, match="PKCE-METHOD-REFUSED"):
        idp.begin_authorization("console", "https://app.example.com/cb",
                                ["domain"], "whatever", "plain")
def test_code_one_time_and_pkce_mismatch(idp):
    code = idp.begin_authorization("console", "https://app.example.com/cb",
                                   ["domain"], _challenge(), "S256")
    with pytest.raises(idp.AuthRefused, match="PKCE-FAILED"):
        idp.exchange_code("console", code, "https://app.example.com/cb", "wrong")
    # 一次失败不消费授权码；正确换取后码即作废（一次性）
    grant = idp.exchange_code("console", code, "https://app.example.com/cb", VERIFIER)
    with pytest.raises(idp.AuthRefused, match="CODE-INVALID"):
        idp.exchange_code("console", code, "https://app.example.com/cb", VERIFIER)
    assert grant
def test_redirect_whitelist_refused(idp):
    with pytest.raises(idp.AuthRefused, match="REDIRECT-UNREGISTERED"):
        idp.begin_authorization("console", "https://evil.example.com/cb",
                                ["domain"], _challenge(), "S256")
def test_undeclared_position_refused(idp):
    """roles ⊆ 治理面声明岗位 —— 未声明角色不可签入 claims（fail-closed）。"""
    with pytest.raises(idp.AuthRefused, match="UNDECLARED-POSITION"):
        _flow(idp, roles=("ceo_of_everything",))
def test_assignment_ref_required(idp):
    """外部 authN 凭据引用必填：不合成正当性（T03 在本体之外，GOV-1 同构）。"""
    with pytest.raises(idp.AuthRefused, match="PRINCIPAL-REFS-REQUIRED"):
        _flow(idp, assignment_ref=None)
def test_dpop_required_and_proof_replay(idp):
    """token_binding=dpop：无 jkt 不签发；绑定令牌无证明重放 → 拒绝（防窃取重放）。"""
    with pytest.raises(idp.AuthRefused, match="DPOP-REQUIRED"):
        _flow(idp, dpop_jkt=None)
    token = _flow(idp)
    with pytest.raises(idp.AuthRefused, match="PROOF-REQUIRED"):
        idp.verify_token(token)
    with pytest.raises(idp.AuthRefused, match="PROOF-MISMATCH"):
        idp.verify_token(token, dpop_jkt=JKT.replace("a", "b"))
def test_secret_missing_fail_closed(idp, monkeypatch):
    """密钥缺失 → 签发/验证一律拒绝，不默认放行。"""
    monkeypatch.delenv("AOS_IDP_SECRET", raising=False)
    with pytest.raises(idp.AuthRefused, match="SECRET-MISSING"):
        idp.verify_token("x.y.z")
def test_authorize_reconciles_routes(idp):
    """资源服务器拦截器：token claims → command_api 路由所需角色对账（声明驱动）。"""
    token = _flow(idp)
    claims = idp.verify_token(token, dpop_jkt=JKT)
    route = idp.authorize("ApproveContract", claims)
    assert route["duty"] == "approve_contract_duty"
    stripped = {**claims, "roles": []}
    with pytest.raises(idp.AuthRefused, match="ROLE-MISMATCH"):
        idp.authorize("ApproveContract", stripped)
    with pytest.raises(idp.AuthRefused, match="UNROUTED"):
        idp.authorize("NoSuchAction", claims)
def test_gating_prune_and_restore(monkeypatch):
    """门控：auth.oauth2_1 未声明 → auth_oauth2.py 摘除；恢复声明 → 重生。
    摘除候选内容依赖 profile 值（token_binding）——模糊时护栏宁拒勿删，
    摘除须显式 --force（与手改护栏同一语义：不静默丢弃生成物）。"""
    codegen.generate(force=True)
    empty = {"project": "t", "selected": {}, "order": [], "values": {}, "failures": []}
    monkeypatch.setattr(codegen, "profile_resolve", lambda *a, **k: empty)
    try:
        report = codegen.generate(force=True)
        assert sorted(report["pruned"]) == ["admin_console.py", "auth_oauth2.py",
                                            "command_api.py", "query_api.py"]
        assert "auth_oauth2.py" in report["pruned"]
        assert not (ROOT / "src/generated/auth_oauth2.py").exists()
    finally:
        monkeypatch.undo()
        generate()
    assert (ROOT / "src/generated/auth_oauth2.py").exists()
