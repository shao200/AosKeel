"""tests/negative/test_snapshot_materialization.py —— P-16 / KS-1.4 条件求值物化投影。
治理映射：VER-2（条件失败不追加——物化矛盾拒绝的负向形态）+ VER-3（版本冲突
完整重求值：重求值轮以权威投影为条件输入）+ VER-11（拒绝照记评估审计）。
评审裂缝修复的守卫：条件快照此前直接取调用方自报 params —— 同一实体二次提交
谎报 status/amount 即可过条件。现每次评估在当轮版本视图上重放聚合流折叠权威
投影（materialize）：改口 → SNAPSHOT-CONTRADICTION 拒绝；未 claim → 权威值回填；
实体未投影 → params 作初始观测（首次观测无权威可对照）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import ConditionalRejected
PARAMS = {"contract_id": "C-R", "status": "pending", "amount": 500000}
STEWARD = dict(principal="svc", roles=("contract_steward",))
def _k():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_reissued_contradiction_rejected_and_stream_unchanged():
    """VER-2 负向：首次观测后改口谎报 → SNAPSHOT-CONTRADICTION，流不追加。"""
    k = _k()
    k.submit("ApproveContract", PARAMS, **STEWARD)
    v0 = len(k.store.streams["domain:ContractAggregate"])
    with pytest.raises(ConditionalRejected, match="SNAPSHOT-CONTRADICTION"):
        k.submit("ApproveContract", dict(PARAMS, status="approved"), **STEWARD)
    assert len(k.store.streams["domain:ContractAggregate"]) == v0
def test_contradiction_recorded_in_interpreter_audit():
    """VER-11 口径：矛盾拒绝照记审计，末条 result 为 False。"""
    k = _k()
    k.submit("ApproveContract", PARAMS, **STEWARD)
    with pytest.raises(ConditionalRejected):
        k.submit("ApproveContract", dict(PARAMS, amount=400), **STEWARD)
    entry = k.interpreter_audit[-1]
    assert entry["kind"] == "snapshot-contradiction"
    assert entry["result"] is False
    assert entry["key"] == "amount" and entry["claim"] == 400
    assert entry["authority"] == 500000
def test_authoritative_backfill_without_claim():
    """未随附 claim → 权威投影回填：投影已 approved，条件自然不过（非矛盾路径）。"""
    k = _k()
    k.submit("ApproveContract", PARAMS, **STEWARD)
    k.store.commit("ApproveContract", "domain:ContractAggregate", 1, "ApproveContract@1",
                   dict(PARAMS, status="approved", valid_time="2026-01-02T00:00:00+00:00"),
                   "other")                                # 权威侧推进：投影 status=approved
    with pytest.raises(ConditionalRejected, match="条件校验未通过"):
        k.submit("ApproveContract", {"contract_id": "C-R", "amount": 500000},
                 **STEWARD)                                # 不 claim status → 权威回填
    assert all(a.get("kind") != "snapshot-contradiction" for a in k.interpreter_audit)
def test_consistent_claim_passes():
    """与权威投影一致的 claim 不误伤：同值二次提交照常过条件。"""
    k = _k()
    k.submit("ApproveContract", PARAMS, **STEWARD)
    ev = k.submit("ApproveContract", dict(PARAMS, valid_time="2026-01-02T00:00:00+00:00"),
                  **STEWARD)
    assert ev.payload["status"] == "pending"
    assert sum(1 for a in k.interpreter_audit
               if a.get("kind") == "snapshot-contradiction") == 0
def test_dryrun_reports_contradiction_without_audit_side_effects():
    """P-12：演练对同一物化路径求值，报告矛盾但不污染审计流。"""
    from kernel.dryrun import dryrun
    k = _k()
    k.submit("ApproveContract", PARAMS, **STEWARD)
    audit_len = len(k.interpreter_audit)
    r = dryrun(k, "ApproveContract", dict(PARAMS, status="void"), **STEWARD)
    assert not r["would_commit"] and r["checks"]["conditional"] == "fail"
    assert "snapshot-contradiction" in r["reason"]
    assert len(k.interpreter_audit) == audit_len
def test_race_reval_evaluates_authority_not_claims():
    """VER-3 呼应：竞速写改变权威状态 → 重求值轮以投影为准，谎报不过。"""
    k = _k()
    k.store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                   dict(PARAMS, status="void", valid_time="2026-01-01T00:00:00+00:00"),
                   "other")                                # 抢先：权威 status=void
    with pytest.raises(ConditionalRejected, match="SNAPSHOT-CONTRADICTION"):
        k.submit("ApproveContract", dict(PARAMS, status="pending"), **STEWARD)
