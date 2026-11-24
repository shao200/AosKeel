"""tests/negative/test_snapshot_materialization.py —— P-16 / KS-1.4 条件求值物化投影。
治理映射：VER-2（条件失败不追加——物化矛盾拒绝的负向形态）+ VER-3（版本冲突
完整重求值：重求值轮以权威投影为条件输入）+ VER-11（拒绝照记评估审计）。
评审裂缝修复的守卫：条件快照此前直接取调用方自报 params —— 同一实体二次提交
谎报 status/amount 即可过条件。现每次评估在当轮版本视图上重放聚合流折叠权威
投影（materialize）：改口 → SNAPSHOT-CONTRADICTION 拒绝；未 claim → 权威值回填；
实体未投影 → 仅创建型动作（域画像 actions.register）可按 params 作初始观测；
非创建型动作在未注册实体上直接拒绝；声明了身份但未随附亦拒绝。
状态基线迁移到 RegisterContract-first 正典形态：实体先经注册进入权威投影，
approve 的条件输入全部来自物化投影，不再靠调用方携带初始状态。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel, materialize
from kernel.errors import ConditionalRejected, SnapshotIdentityMissing, SnapshotEntityMissing
STREAM = "domain:ContractAggregate"
STEWARD = dict(principal="svc", roles=("contract_steward",))
RPARAMS = {"contract_id": "C-R", "amount": 500000}
def _k():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def _registered(k) -> None:
    k.submit("RegisterContract", dict(RPARAMS), **STEWARD)
def test_reissued_contradiction_rejected_and_stream_unchanged():
    """VER-2 负向：注册后谎报 status → SNAPSHOT-CONTRADICTION，流不追加。"""
    k = _k()
    _registered(k)
    v0 = len(k.store.streams[STREAM])
    with pytest.raises(ConditionalRejected, match="SNAPSHOT-CONTRADICTION"):
        k.submit("ApproveContract", dict(RPARAMS, status="approved"), **STEWARD)
    assert len(k.store.streams[STREAM]) == v0
def test_contradiction_recorded_in_interpreter_audit():
    """VER-11 口径：矛盾拒绝照记审计，末条 result 为 False。"""
    k = _k()
    _registered(k)
    with pytest.raises(ConditionalRejected):
        k.submit("ApproveContract", dict(RPARAMS, amount=400), **STEWARD)
    entry = k.interpreter_audit[-1]
    assert entry["kind"] == "snapshot-contradiction"
    assert entry["result"] is False
    assert entry["key"] == "amount" and entry["claim"] == 400
    assert entry["authority"] == 500000
def test_authoritative_backfill_without_claim():
    """未随附 claim → 权威投影回填：投影已 approved，条件自然不过（非矛盾路径）。"""
    k = _k()
    _registered(k)
    k.submit("ApproveContract", dict(RPARAMS), **STEWARD)   # 效果书写 approved（T24）
    with pytest.raises(ConditionalRejected, match="条件校验未通过"):
        k.submit("ApproveContract", dict(RPARAMS), **STEWARD)  # 不 claim → 权威回填
    assert all(a.get("kind") != "snapshot-contradiction" for a in k.interpreter_audit)
def test_consistent_claim_passes_and_effect_wins_payload():
    """与权威投影一致的 claim 不误伤；事件载荷的状态由声明效果书写，非自报值。"""
    k = _k()
    _registered(k)
    ev = k.submit("ApproveContract", dict(RPARAMS, status="pending"), **STEWARD)
    assert ev.payload["status"] == "approved"          # T24 effects：内核书写
    assert sum(1 for a in k.interpreter_audit
               if a.get("kind") == "snapshot-contradiction") == 0
def test_dryrun_reports_contradiction_without_audit_side_effects():
    """P-12：演练对同一物化路径求值，报告矛盾但不污染审计流。"""
    from kernel.dryrun import dryrun
    k = _k()
    _registered(k)
    audit_len = len(k.interpreter_audit)
    r = dryrun(k, "ApproveContract", dict(RPARAMS, status="void"), **STEWARD)
    assert not r["would_commit"] and r["checks"]["conditional"] == "fail"
    assert "snapshot-contradiction" in r["reason"]
    assert len(k.interpreter_audit) == audit_len
    assert r["effects"] == {"status": "approved"}      # 演练呈现声明效果，不追加
def test_race_reval_evaluates_authority_not_claims():
    """VER-3 呼应：竞速写改变权威状态 → 重求值轮以投影为准，谎报不过。"""
    k = _k()
    k.store.commit("VoidContract", STREAM, 0, "VoidContract@1",
                   dict(RPARAMS, status="void", valid_time="2026-01-01T00:00:00+00:00"),
                   "other")                                # 抢先：权威 status=void
    with pytest.raises(ConditionalRejected, match="SNAPSHOT-CONTRADICTION"):
        k.submit("ApproveContract", dict(RPARAMS, status="pending"), **STEWARD)


def test_materialize_rejects_identity_missing_from_params():
    """声明了身份键但调用方未随附 → 拒绝，不得整体回退自报值。"""
    act = compile_all()["ApproveContract"]
    with pytest.raises(SnapshotIdentityMissing, match="SNAPSHOT-IDENTITY-MISSING"):
        materialize(EventStore(), act, {"status": "pending", "amount": 1})


def test_non_create_action_cannot_first_touch():
    """非创建型动作在未投影实体上 fail-closed（禁止凭空审批），且留痕不追加。"""
    k = _k()
    with pytest.raises(SnapshotEntityMissing, match="SNAPSHOT-ENTITY-MISSING"):
        k.submit("ApproveContract",
                 {"contract_id": "C-GHOST", "status": "pending", "amount": 1}, **STEWARD)
    assert STREAM not in k.store.streams                  # VER-2：不追加
    assert k.interpreter_audit[-1]["result"] is False     # VER-11：拒绝照记评估


def test_create_action_declared_by_domain_profile():
    """唯一可首次观测的动作 = 域画像 actions.register 声明的创建型动作。"""
    compiled = compile_all()
    assert compiled["RegisterContract"].creates is True
    assert compiled["ApproveContract"].creates is False
    snap, contra = materialize(EventStore(), compiled["RegisterContract"],
                               {"contract_id": "C-NEW", "amount": 7})
    assert snap == {"amount": 7} and contra is None
