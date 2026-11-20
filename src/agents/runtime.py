"""src/agents/runtime.py —— AGENT 能力面（P-10 / INV-1）。
Agent 不是新的执行主体类别：写路径必经同一条提交管线（INV-1），无特权通道；
能力面 = 编译产物权限矩阵 ∩ Agent 角色的严格子集；
越权 = PermissionDenied，在触达存储之前拒绝（不留审计污染的写尝试）。

单一事实源（消除第二张皮）：能力面不自行推导——本模块委托 kernel.capability_ledger
（编译产物权限矩阵的双向只读投影，与 Kernel.submit 门控同源）。匹配（供给方）与门控
（submit）读同一本账，"被匹配到的人"与"能通过门控的人"结构上不可能分叉。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import PermissionDenied  # noqa: E402
from kernel.capability_ledger import CapabilityLedger  # noqa: E402
class AgentRuntime:
    def __init__(self, kernel, agent_id: str, roles: tuple[str, ...], ledger=None):
        self.kernel, self.agent_id, self.roles = kernel, agent_id, tuple(roles)
        # 能力账簿：默认从本内核编译产物构造；亦可显式注入（测试/编排共用同一本账）
        self._ledger = ledger if ledger is not None else CapabilityLedger(kernel.compiled)
    def capabilities(self) -> list[str]:
        """P-10：能力面 = 能力账簿 supply 投影（编译权限矩阵 ∩ Agent 角色）。"""
        return list(self._ledger.supply(self.roles))
    def act(self, action_type: str, params: dict):
        if action_type not in self.capabilities():
            raise PermissionDenied(
                f"{self.agent_id} 无 {action_type} 权限 —— "
                f"能力面是能力清单的严格子集，无绕行（P-10 / INV-1）")
        return self.kernel.submit(action_type, params, self.agent_id, roles=self.roles)
    def record_decision(self, *args, **kwargs):
        """Agent 亦可记录决策：同一 record_decision 入口（KS-2.5 双引用同等强制）。"""
        return self.kernel.record_decision(*args, **kwargs)