"""tests/negative/test_kernel_roles_enforced.py —— P-10 / INV-4 单一写路径强制。
治理映射：VER-2（能力核查先于评估与存储——权限强制点归位后该顺序判据的
负向形态）+ VER-27（能力清单闭环）。
评审裂缝修复的守卫：权限强制点原只在 AgentRuntime，直连 Kernel.submit 的调用
可绕过角色面。现内核在能力核查段（评估与存储之前）强制：声明了 roles 的
Action，角色证据缺失或不交 → PermissionDenied，且零评估、零存储、零审计接触
（fail-closed：未出示 == 无权，不默认放行）。
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
from kernel.errors import PermissionDenied
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _k():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_missing_roles_rejected_fail_closed():
    k = _k()
    with pytest.raises(PermissionDenied, match="∅"):
        k.submit("ApproveContract", PARAMS, "someone")     # 未出示角色 = 无权
    assert not k.store.streams and not k.store.audit       # 存储零接触
    assert not k.interpreter_audit                         # 评估零接触（顺序即管线）
def test_disjoint_roles_rejected():
    k = _k()
    with pytest.raises(PermissionDenied, match="viewer"):
        k.submit("ApproveContract", PARAMS, "svc", roles=("viewer",))
    assert not k.store.streams
def test_matching_roles_pass_single_enforcement():
    k = _k()
    k.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000},
             "svc", roles=("contract_steward",))
    ev = k.submit("ApproveContract", PARAMS, "svc", roles=("contract_steward",))
    assert ev.action_id == "ApproveContract"
def test_dryrun_reports_permission_stage():
    """演练与提交同序强制：P-12 报告 capability=fail，不伪装可提交。"""
    from kernel.dryrun import dryrun
    k = _k()
    r = dryrun(k, "ApproveContract", PARAMS, "someone")
    assert not r["would_commit"] and r["checks"]["capability"] == "fail"
