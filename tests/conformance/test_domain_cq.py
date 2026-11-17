"""tests/conformance/test_domain_cq.py —— 域无关 CQ 契约回归。

判据（四条缺一不可）：
1. 实例自定义的域画像 + 题集无需改 Python 即可运行并通过；
2. 题集不再强制十题冻结清单（冻结只约束 contract 基线域）；
3. 域画像参数真的驱动查询结果（fixture 种子 / entity_key 改动改变实际答案）；
4. 域未知、夹具未声明、期望被篡改一律失败 —— 声明不是装饰。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import cq

AR_DOMAIN = ROOT / "spec" / "competence" / "domains" / "audit-review"

def test_custom_domain_checklist_runs_without_python_change():
    results = cq.run(domain="audit-review")
    assert [r["id"] for r in results] == ["CQ-AR-1", "CQ-AR-2", "CQ-AR-3"]
    assert all(r["ok"] for r in results), results
    # probe 为空的两题证明域参数来自画像而非 Python 字面量
    assert results[1]["actual"]["intruder_denied"] is True
    assert results[2]["actual"] == {"identical": True, "dematerialized": True}

def test_custom_domain_is_not_forced_to_ten_questions():
    docs = cq.declarations(domain="audit-review")
    assert len(docs) == 3
    assert all(d["id"] not in cq.EXPECTED_IDS for d in docs)

def test_custom_domain_expectation_tamper_is_detected(tmp_path):
    for p in sorted(AR_DOMAIN.glob("*.cq.yaml")):
        text = p.read_text(encoding="utf-8")
        if p.name.startswith("CQ-AR-1"):
            text = text.replace("value: approved", "value: void")
        (tmp_path / p.name).write_text(text, encoding="utf-8")
    r = cq.run(root=tmp_path, domain="audit-review")[0]
    assert not r["ok"] and r["expected"] == "void" and r["actual"] == "approved"

def test_profile_fixture_seed_drives_actual_answer(tmp_path):
    """只写一个域画像（extends + fixtures 差异），聚合查询的实际答案随之改变。"""
    (tmp_path / "domains").mkdir()
    (tmp_path / "domains" / "seeded.domain.yaml").write_text(
        "domain: seeded\nextends: contract\nlabel: 有种子事件的域\n"
        "fixtures:\n  empty:\n    observations: []\n    events:\n"
        "      - {action: RegisterContract, params: {contract_id: C-1, amount: 500000}}\n"
        "      - {action: ApproveContract, params: {contract_id: C-1, approver_comment: ok}}\n",
        encoding="utf-8")
    (tmp_path / "CQ-SEED-1.cq.yaml").write_text(
        "id: CQ-SEED-1\nquestion: 种子域的空夹具是否已有 approved 合同？\n"
        "answerer: projection.snapshot\nfixture: empty\n"
        "probe: { contract_id: C-1 }\n"
        "expect: { op: equals, value: approved }\nevidence: 画像 fixture 驱动\n",
        encoding="utf-8")
    r = cq.run(root=tmp_path, domain="seeded")[0]
    assert r["ok"] and r["actual"] == "approved", r
    # 同一探针在 contract 基线域的空夹具上无答案 —— 证明答案来自画像声明
    base = cq.load_profile()
    base_ctx = cq.build_fixture(base, "empty")
    assert cq.PRIMITIVES["projection.snapshot"](
        base_ctx, {"contract_id": "C-1"}, base) is None

def test_profile_entity_key_drives_probe_lookup():
    """entity_key 由画像提供：换键名后查询按新键取值，旧键不再可用。"""
    prof = cq.load_profile("audit-review")
    ctx = cq.build_fixture(prof, "contract_approved")
    alt = dict(prof, aggregate=dict(prof["aggregate"], entity_key="wrong_id"))
    assert cq.PRIMITIVES["projection.snapshot"](ctx, {"wrong_id": "C-1"}, alt) == "approved"
    with pytest.raises(KeyError):
        cq.PRIMITIVES["projection.snapshot"](ctx, {"wrong_id": "C-1"}, prof)

def test_unknown_domain_is_refused():
    with pytest.raises(cq.CQError, match="CQ-DOMAIN-UNKNOWN"):
        cq.run(domain="ghost-domain")

def test_undeclared_fixture_is_refused(tmp_path):
    (tmp_path / "domains").mkdir()
    (tmp_path / "domains" / "bare.domain.yaml").write_text(
        "domain: bare\nextends: contract\nfixtures: {}\n", encoding="utf-8")
    (tmp_path / "CQ-BARE-1.cq.yaml").write_text(
        "id: CQ-BARE-1\nquestion: 未声明夹具\nanswerer: projection.snapshot\n"
        "fixture: ghost_fixture\nprobe: {}\nexpect: { op: equals, value: x }\n"
        "evidence: x\n", encoding="utf-8")
    with pytest.raises(cq.CQError, match="CQ-FIXTURE-UNKNOWN"):
        cq.declarations(root=tmp_path, domain="bare")

def test_contract_checklist_still_frozen():
    assert [d["id"] for d in cq.declarations()] == list(cq.EXPECTED_IDS)
