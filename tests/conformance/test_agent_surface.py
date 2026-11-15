"""tests/conformance/test_agent_surface.py —— P-10：AGENT 能力面 = 清单严格子集。
判据：能力面来自编译产物权限矩阵 ∩ 角色；越权在触达存储之前拒绝；
写路径与人类同一条管线（INV-1，无特权通道）。
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
from agents.runtime import AgentRuntime
from kernel.errors import PermissionDenied
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _runtime(roles=("contract_steward",)):
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    return k, AgentRuntime(k, "agent-1", roles)
def test_capability_surface_from_permissions():
    k, agent = _runtime()
    caps = agent.capabilities()
    assert "ApproveContract" in caps and "VoidContract" in caps
    assert "RecordDecision" not in caps                        # 无角色声明者不入面
def test_unauthorized_rejected_before_store():
    """越权 = PermissionDenied，在触达存储之前（无审计污染的写尝试）。"""
    k, agent = _runtime(roles=("viewer",))
    with pytest.raises(PermissionDenied, match="严格子集"):
        agent.act("ApproveContract", PARAMS)
    assert not k.store.streams and not k.store.audit           # 存储零接触
def test_authorized_uses_same_pipeline():
    """P-10：Agent 无特权通道 —— 与人类同一条提交管线（INV-1）。"""
    k, agent = _runtime()
    ev = agent.act("ApproveContract", PARAMS)
    assert ev.action_id == "ApproveContract"
    assert ev.stream_id == "domain:ContractAggregate"
    assert ev.payload["valid_time"] <= ev.transaction_time     # KS-6.1 同等强制
def test_agent_has_no_raw_write_path():
    """AgentRuntime 上不存在任何绕过管线的写方法（P-10 结构核对）。"""
    _, agent = _runtime()
    for banned in ("write_raw", "append", "commit", "_append"):
        assert not hasattr(agent, banned)
