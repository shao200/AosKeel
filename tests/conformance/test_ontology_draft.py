"""tests/conformance/test_ontology_draft.py —— 需求 → 本体草案（缺口 ① 三段闸门）。
判据：解析确定性；编译不过不落盘；晋升 MUST 绑定治理提案（GOV-1）；
晋升不覆盖正典声明；晋升后 declared == registered（P-5 单写者 apply_generated）。
"""
import shutil
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import ontology_draft as od
from kernel import registration
REQ = """聚合体: OrderAggregate
  流: domain:OrderAggregate
  预算: 10000

对象: Order
  标识: order_id
  属性: status, total, customer_ref

动作: CreateOrder
  聚合: OrderAggregate
  参数: order_id(必填), total(选填)
  结构: exists order_id
  条件: snapshot.status == 'open'
"""
@pytest.fixture
def sandbox_spec(tmp_path, monkeypatch):
    """真实 spec/ 副本 + registration 沙箱替换（draft 闸门不碰正典）。
    drafts/ 是工作区不复制；晋升相关测试对已消费实例 skip（见 _ORDER_PROMOTED）。
    """
    shutil.copytree(ROOT / "spec", tmp_path / "spec",
                    ignore=shutil.ignore_patterns("drafts"))
    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config/capabilities.yaml", tmp_path / "config/capabilities.yaml")
    monkeypatch.setattr(registration, "SPEC_DIR", tmp_path / "spec")
    monkeypatch.setattr(registration, "CAPS", tmp_path / "config/capabilities.yaml")
    return tmp_path
# 实例消费状态标记：模板验收（未消费正典）对已晋升实例不适用 —— 跳过而非伪装
_ORDER_PROMOTED = (ROOT / "spec/ontology/objects/Order.object.yaml").exists()
_SKIP = pytest.mark.skipif(_ORDER_PROMOTED, reason="实例已晋升 Order —— "
                           "模板验收只对未消费状态有效；治理后状态走实例侧验收")
def test_parse_is_deterministic():
    d1 = od.parse_requirements(REQ); d2 = od.parse_requirements(REQ)
    assert d1 == d2
    assert d1["aggregates"][0]["evaluation_budget"] == 10000
    assert d1["objects"][0]["identity"] == "order_id"
    assert d1["actions"][0]["params"] == {"order_id": True, "total": False}
    assert d1["actions"][0]["conditional"] == ["snapshot.status == 'open'"]
def test_bad_syntax_rejected_not_written(sandbox_spec):
    """把关三线：预算超限 / 聚合缺失 / 条件违反 R2 源头 —— 均不落盘。"""
    bad = REQ.replace("预算: 10000", "预算: 999999") \
             .replace("条件: snapshot.status == 'open'",
                      "条件: contract.status == 'open'")            # R2：条件只可起于快照/主体
    bad += "\n动作: GhostAction\n  聚合: Ghost\n  参数: x(必填)\n"    # 未登记聚合
    report = od.draft_from_text(bad, "bad")
    assert any("BUDGET-EXCEEDED" in f for f in report["failures"])     # P-2
    assert any("AGGREGATE-NOT-DECLARED" in f for f in report["failures"])
    assert any("COMPILE-FAILED" in f and "R2" in f for f in report["failures"])  # KS-7.1
    assert not (sandbox_spec / "spec/drafts").exists()                 # 未全绿不落盘
def test_draft_written_when_green(sandbox_spec):
    report = od.draft_from_text(REQ, "order")
    assert report["failures"] == []
    assert (sandbox_spec / "spec/drafts/draft-order.yaml").exists()    # 人确认区
@_SKIP
def test_promote_requires_proposal_ref(sandbox_spec):
    draft = od.draft_from_text(REQ, "order")["draft"]
    with pytest.raises(od.DraftError, match="GOV-1"):
        od.promote(Path(draft), proposal_ref="")
    with pytest.raises(od.DraftError, match="GOV-1"):
        od.promote(Path(draft), proposal_ref="MADE-UP")
@_SKIP
def test_promote_then_registered_consistent(sandbox_spec):
    """晋升 → 声明落正典 + apply_generated（P-5）→ run_pipeline 全绿。"""
    draft = od.draft_from_text(REQ, "order")["draft"]
    r = od.promote(Path(draft), proposal_ref="SPEC-2026-021")
    assert (sandbox_spec / "spec/ontology/objects/Order.object.yaml").exists()
    assert (sandbox_spec / "spec/aggregates/OrderAggregate.aggregate.yaml").exists()
    assert (sandbox_spec / "spec/ontology/actions/CreateOrder.action.yaml").exists()
    gen = registration.run_pipeline()                                  # declared == registered
    ids = [e["id"] for e in gen["write_actions"]]
    assert "CreateOrder" in ids
    entry = next(e for e in gen["write_actions"] if e["id"] == "CreateOrder")
    assert entry["provenance"] == "SPEC-2026-021"                      # 能力回溯至提案（GOV-2.2）
def test_promote_refused_on_existing_canonical(sandbox_spec):
    """晋升不覆盖正典声明 —— 变更走 GOV-3 版本通道。"""
    dup = od.draft_from_text(REQ.replace("CreateOrder", "ApproveContract")
                             .replace("OrderAggregate", "ContractAggregate"), "dup2")
    with pytest.raises(od.DraftError, match="已存在"):
        od.promote(Path(dup["draft"]), proposal_ref="SPEC-2026-022")
