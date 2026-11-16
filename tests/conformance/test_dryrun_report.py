"""tests/conformance/test_dryrun_report.py —— VER-25：dry-run 可重复且无副作用（P-12）。
判据：两次同输入 → 同报告；演练绝不追加事件、不产生 structurally-rejected 审计。
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
from kernel.dryrun import dryrun
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _kernel():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_report_repeatable():
    k = _kernel()
    r1 = dryrun(k, "ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))
    r2 = dryrun(k, "ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))
    assert r1 == r2 and r1["would_commit"] is True             # P-12：可重复
def test_dryrun_has_no_side_effects():
    """演练不追加事件、不留 structurally-rejected 审计（P-12 诚实性）。"""
    k = _kernel()
    before_streams, before_audit = dict(k.store.streams), list(k.store.audit)
    dryrun(k, "ApproveContract", dict(PARAMS, status="void"), "contract_steward", roles=("contract_steward",))
    dryrun(k, "GhostAction", {}, "agent")
    assert k.store.streams == before_streams                   # 零事件
    assert k.store.audit == before_audit                       # 零审计副作用
def test_dryrun_reject_reason_is_actionable():
    k = _kernel()
    r = dryrun(k, "ApproveContract", {"status": "pending"}, "contract_steward", roles=("contract_steward",))  # 缺 contract_id
    assert r["would_commit"] is False
    assert r["checks"]["structural"] == "fail" and "contract_id" in r["reason"]
    r2 = dryrun(k, "NukeEverything", {}, "agent")              # INV-1
    assert r2["reason"] and "unregistered" in r2["reason"]
def test_dryrun_then_commit_consistent():
    """演练通过 = 正式提交也通过（同一管线两段式消费）。"""
    k = _kernel()
    assert dryrun(k, "ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))["would_commit"]
    ev = k.submit("ApproveContract", PARAMS, "contract_steward", roles=("contract_steward",))
    assert ev.stream_id == "domain:ContractAggregate"
