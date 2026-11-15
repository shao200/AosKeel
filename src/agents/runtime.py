"""src/agents/runtime.py —— AGENT 能力面（P-10 / INV-1）。
Agent 不是新的执行主体类别：写路径必经同一条提交管线（INV-1），无特权通道；
能力面 = 编译产物权限矩阵 ∩ Agent 角色的严格子集；
越权 = PermissionDenied，在触达存储之前拒绝（不留审计污染的写尝试）。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import PermissionDenied
class AgentRuntime:
    def __init__(self, kernel, agent_id: str, roles: tuple[str, ...]):
        self.kernel, self.agent_id, self.roles = kernel, agent_id, tuple(roles)
    def capabilities(self) -> list[str]:
        """P-10：能力面 = 编译产物权限矩阵 ∩ Agent 角色的严格子集。"""
        out = []
        for aid, act in self.kernel.compiled.items():
            if set(act.permissions.get("roles", [])) & set(self.roles):
                out.append(aid)
        return sorted(out)
    def act(self, action_type: str, params: dict):
        if action_type not in self.capabilities():
            raise PermissionDenied(
                f"{self.agent_id} 无 {action_type} 权限 —— "
                f"能力面是能力清单的严格子集，无绕行（P-10 / INV-1）")
        return self.kernel.submit(action_type, params, self.agent_id)   # 同一条管线
    def record_decision(self, *args, **kwargs):
        """Agent 亦可记录决策：同一 record_decision 入口（KS-2.5 双引用同等强制）。"""
        return self.kernel.record_decision(*args, **kwargs)
