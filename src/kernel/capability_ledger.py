#!/usr/bin/env python3
"""src/kernel/capability_ledger.py —— 能力账簿（Action × Role 双向匹配单一事实源）。

定位（信息性参考实现）：不产生规范条款 —— 不改冻结正典、不改 spec 九类声明、
不改能力清单、不动 AX/KS/P/INV/GOV/VER 标识符。能力账簿不是第十类声明，而是
对 ``Kernel.compiled`` 权限矩阵（Action → required roles）的双向只读投影——
这正是 ``Kernel.submit`` 门控（pipeline.py:65 ``required & set(roles)``）实际读取的
同一份事实。

为什么要有这本账（消除两张皮）：
    上一轮实体主动行为的执行集 E 来自治理面 ``governance.authorizes``
    （stewardship.executor_roles），而 submit 门控读能力面 ``compiled.permissions.roles``。
    两者现网对账一致（CQ-2），但概念上是两套推导——"被匹配到的人"与"能通过门控的
    人"来源不同，声明一漂移就会分叉。邵工指出"人基于能力账簿找事，反之也一样"：
    双向匹配都应读同一本能力账。匹配即门控，从根上消除漂移。

双向投影：
    demand(actions)             → roles    事找人：要推动这些 Action，需要哪些角色
    supply(roles)               → actions  人找事：持有这些角色，能推动哪些 Action
    can_execute(action, roles)  → bool     与 submit 门控同源的可执行预检

职责边界（与治理面 stewardship 分工，不重叠）：
    治理面 V（visible_roles） 答"谁看得见这件事"——切面/跨组织可见性，owner 可控；
    能力账簿 E（本模块）      答"谁能实际提交"——与 submit 门控同源，不可自报。
    可见 ≠ 可执行：切面角色在 V 但不在 E，只被通知、不被邀请执行。

fail-closed：未注册 Action / 空角色 → 空集或 False，不默认放行。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


class CapabilityLedger:
    """能力账簿：compiled 权限矩阵的双向只读投影。

    compiled: dict[str, CompiledAction] —— Kernel 编译产物（submit 门控同源）。
    不持有 store、不写任何通道、不执行动作——纯查询，匹配层专用。
    """

    def __init__(self, compiled: dict):
        self._compiled = compiled

    @staticmethod
    def _roles_of(act) -> frozenset:
        """从编译产物取必需角色；字段缺失/为空 → 空集（fail-closed）。"""
        perms = getattr(act, "permissions", None)
        if not isinstance(perms, dict):
            return frozenset()
        return frozenset(perms.get("roles") or ())

    # ---------- 事找人：需求 → 合格供给角色 ----------
    def demand(self, actions) -> tuple[str, ...]:
        """给定要推动的 Action 集，返回有能力提交的合格角色并集（排序去重）。

        未注册 Action 被忽略（不产生匹配）——与 submit 的 UnregisteredAction
        拒绝语义一致：不存在的动作不产生任何可执行主体。
        """
        roles: set[str] = set()
        for a in actions or ():
            act = self._compiled.get(a)
            if act is not None:
                roles |= self._roles_of(act)
        return tuple(sorted(roles))

    # ---------- 人找事：持有角色 → 可推动的 Action ----------
    def supply(self, roles) -> tuple[str, ...]:
        """给定持有的角色，返回这些角色有资格提交的 Action 集（排序去重）。

        AgentRuntime.capabilities() 委托本方法（见 agents/runtime.py）——全系统仅此
        一份能力面实现，杜绝"匹配"与"门控"两本账分叉。不依赖 Agent 实例：任何人/
        Agent 出示角色即可查询。
        """
        have = set(roles or ())
        if not have:
            return ()
        return tuple(sorted(
            aid for aid, act in self._compiled.items()
            if have & self._roles_of(act)
        ))

    # ---------- 门控同源预检 ----------
    def can_execute(self, action: str, roles) -> bool:
        """与 submit 门控同源的可执行判据：required ∩ 出示角色 ≠ ∅。

        未注册 Action → False（submit 会抛 UnregisteredAction，等价拒绝）。
        """
        act = self._compiled.get(action)
        if act is None:
            return False
        return bool(self._roles_of(act) & set(roles or ()))

    def digest(self) -> str:
        """能力账簿指纹：编译权限矩阵的稳定摘要（可审计、可比对门控漂移）。"""
        import hashlib
        rows = sorted(
            (aid, sorted(self._roles_of(act)))
            for aid, act in self._compiled.items()
        )
        blob = repr(rows).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]