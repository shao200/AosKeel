#!/usr/bin/env python3
"""src/kernel/stewardship.py —— 管理域：实体主动性的可见性边界（信息性参考实现）。

定位（诚实边界）：本模块是实例侧参考实现，不产生规范条款 —— 不改冻结正典、
不改 spec 九类声明、不改能力清单、不动任何 AX/KS/P/INV/GOV/VER 标识符。
它完全建立在既有事实上，兑现可计算的可见性与归属判据。

【本轮收敛（2026-11-20）】消除"第二张皮"风险：
- 成员事实源**唯一**：`tools/codegen.py::_governance_positions()` —— 与生成物
  `GOV_POSITIONS`（auth_oauth2.py）同源同推导，但不依赖 auth 模块门控（精简
  profile 下 auth_oauth2.py 会被摘除，硬依赖它会使本模块崩溃）。治理声明改动
  经摘要哈希保护并走 GOV 通道，本模块只是它的只读投影。
- 可见集 V 与执行集 E 分离（用户三轮修正的落点）：
    V = visible_roles(actions) = ⋃ 覆盖这些 Action 的授权岗位（跨切面/跨组织并集）
        —— scan 用它；当事人 + 检验 + 监理等切面角色都在内。
    E = executor_roles(action) = 治理面授权该单动作的岗位 —— **仅用于对账/推导**；
        真正的提交判据在 `capability_ledger.CapabilityLedger.can_execute`，读 compiled
        权限矩阵（submit 门控同源）。本模块**不提供 can_execute API**（已移除双源）。
    可见 ≠ 可执行：检验员在 V 但不在 E(ApproveContract)。
- owner 归属从该实例首事件 principal 重建；append-only 保证不可伪造。

写路径边界（必须讲清）：`Kernel.submit` 的 `required ∩ roles` 已经是执行集 E 的
运行时门控（触达存储前拒绝），令牌 `authorize()` 亦同源。本模块**不接写路径**、
不重复 E 的强制——那是模型变更，需 ADR→PR→gates→regression 流程。本模块提供
的是 E 不覆盖的那一半：可见集 V 与 owner 归属，供上层主动性扫描/通知调用。

fail-closed：未锚定 / 非 owner 锚定 / 空成员集一律拒绝，不静默放行（显式锚定路径）。
声明推导路径下 V 为空（无 Action 命中）同样拒绝。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.errors import AosError  # noqa: E402
from tools.codegen import _governance_positions  # noqa: E402  单一事实源（无门控）


class StewardshipViolation(AosError):
    """管理域违规基类。"""


class DomainNotAnchored(StewardshipViolation):
    """管理域未锚定 —— 无可见角色，fail-closed。"""


class DomainOwnerMismatch(StewardshipViolation):
    """非创建者试图锚定管理域 —— 拒绝。"""


class EmptyDomainRejected(StewardshipViolation):
    """空成员集 —— 无管理域，拒绝。"""


class NoVisibleRoles(StewardshipViolation):
    """声明推导下可见集为空 —— 无切面成员，fail-closed。"""


UNDECLARED_ROLE = "<undeclared>"  # 域外角色的占位标签：不进入可见结果


# ---------------------------------------------------------------------------
# 单一事实源推导：全部读 _governance_positions()，无第二份声明解析。
# ---------------------------------------------------------------------------
def governance_view():
    """治理面岗位投影（position → duties/org_units/authorizes）的只读快照。

    每次调用重新推导，反映在册声明的最新状态；声明本身受摘要哈希保护，
    绕过 GOV 通道手改会被 verify 第四道拒绝。
    """
    return _governance_positions()


def executor_roles(action_type: str, positions=None) -> tuple[str, ...]:
    """治理面执行集：授权该单动作的岗位（排序去重）。

    用途限于 V 的聚合推导与"治理面 ↔ 能力面"对账；**不是运行时提交判据**——
    提交判据请用 ``capability_ledger.CapabilityLedger.can_execute``（读 compiled
    权限矩阵，与 submit 门控同源）。action_type 未出现在任何职责项 → 空集。
    """
    view = governance_view() if positions is None else positions
    return tuple(sorted(p for p, v in view.items()
                        if action_type in v.get("authorizes", ())))


def visible_roles(action_types, positions=None) -> tuple[str, ...]:
    """可见集 V：覆盖给定项目动作集的岗位并集（跨切面、跨组织）。

    action_types 是项目涉及的 Action 全集；省略则取治理面声明的全部 Action——
    保守放大，保证切面（当事人/检验/监理）不因画像漏登记而被挡在可见集外。
    """
    view = governance_view() if positions is None else positions
    wanted = set(action_types) if action_types is not None else {
        a for v in view.values() for a in v.get("authorizes", ())}
    result = {p for p, v in view.items() if wanted & set(v.get("authorizes", ()))}
    if not result:
        raise NoVisibleRoles(
            "NO-VISIBLE-ROLES: 给定 Action 集无授权岗位 —— 可见集为空（fail-closed）")
    return tuple(sorted(result))


def org_units_of(action_types, positions=None) -> tuple[str, ...]:
    """组织范围：覆盖给定 Action 的授权岗位所属组织锚点并集（跨组织联合域）。"""
    view = governance_view() if positions is None else positions
    wanted = set(action_types) if action_types is not None else {
        a for v in view.values() for a in v.get("authorizes", ())}
    orgs: set[str] = set()
    for v in view.values():
        if wanted & set(v.get("authorizes", ())):
            orgs.update(v.get("org_units", ()))
    return tuple(sorted(orgs))


@dataclass(frozen=True)
class ManagementDomain:
    """一个实体实例的管理域（不可变值对象）。

    owner    —— 创建者 principal，来自事件流重建
    members  —— 可见角色集 V，来自声明推导或 owner 显式锚定
    """

    stream_id: str
    entity_id: str
    owner: str
    members: frozenset[str]

    def visible(self, candidates) -> tuple[str, ...]:
        """可见性过滤：仅返回域内角色，保持候选顺序、去重；域外不可见。"""
        out: list[str] = []
        seen: set[str] = set()
        for role in candidates:
            if role in self.members and role not in seen:
                seen.add(role)
                out.append(role)
        return tuple(out)

    def admits(self, roles) -> bool:
        """可见集内 ∧ 非空 → 可参与主动性互动（含切面角色）。"""
        return bool(set(roles) & self.members)


class StewardshipRegistry:
    """管理域注册表：owner 重建 + 可见性扫描，单一收口。

    identity_key 指定事件 payload 中定位实例的属性（示例域为 contract_id）；
    与投影 IDENTITIES 同口径，实例侧可按自身聚合根标识覆盖。
    """

    def __init__(self, store, identity_key: str = "contract_id"):
        self.store = store
        self.identity_key = identity_key
        self._domains: dict[tuple[str, str], ManagementDomain] = {}

    def owner_of(self, stream_id: str, entity_id: str) -> str:
        """从事件流重建创建者：按 event_id 序取该实例首事件的 principal。

        这是"创建者拥有管理域"的事实基础 —— append-only 保证首事件不可变，
        后续任何提交者（审批者、Agent）都无法改写归属。
        """
        matching = sorted(
            (ev for ev in self.store.streams.get(stream_id, [])
             if ev.payload.get(self.identity_key) == entity_id),
            key=lambda ev: ev.event_id,
        )
        if not matching:
            raise DomainNotAnchored(
                f"DOMAIN-NOT-ANCHORED: {stream_id}/{entity_id} 无事件，"
                f"创建者不可重建（fail-closed）")
        return matching[0].principal

    def anchor(self, stream_id: str, entity_id: str, principal: str, roles) -> ManagementDomain:
        """由创建者显式锚定可见角色集；非 owner / 空集即拒。

        显式锚定是 owner 临时收窄可见范围的覆盖手段，优先级高于声明推导。
        """
        owner = self.owner_of(stream_id, entity_id)
        if principal != owner:
            raise DomainOwnerMismatch(
                f"DOMAIN-OWNER-MISMATCH: {principal} ≠ 创建者 {owner} "
                f"（{stream_id}/{entity_id} 的管理域只归创建者锚定）")
        members = frozenset(roles or ())
        if not members:
            raise EmptyDomainRejected(
                f"EMPTY-DOMAIN: {stream_id}/{entity_id} 空成员集 —— 无管理域（fail-closed）")
        domain = ManagementDomain(stream_id, entity_id, owner, members)
        self._domains[(stream_id, entity_id)] = domain
        return domain

    def domain_of(self, stream_id: str, entity_id: str, action_types=None) -> ManagementDomain:
        """取管理域：显式锚定优先；未锚定时回落声明推导的可见集 V。

        action_types 为项目涉及的 Action 集；None 时取治理面全部 Action（保守放大）。
        两种情况都保持 fail-closed：未锚定且 V 为空 → NoVisibleRoles。
        """
        domain = self._domains.get((stream_id, entity_id))
        if domain is not None:
            return domain
        # 回落声明推导：可见成员默认在册（不再因未 anchor 而拒绝）
        members = visible_roles(action_types)
        owner = self.owner_of(stream_id, entity_id)
        return ManagementDomain(stream_id, entity_id, owner, frozenset(members))

    def scan(self, stream_id: str, entity_id: str, candidates, action_types=None) -> tuple[str, ...]:
        """实体主动行为的可见性扫描：仅可见集 V 内角色可见，域外不出现在结果里。

        未锚定时回落治理声明推导（可见集），这是 V 的语义；不是执行权。
        """
        return self.domain_of(stream_id, entity_id, action_types).visible(candidates)

    def can_interact(self, stream_id: str, entity_id: str, roles, action_types=None) -> bool:
        """能否参与主动性互动（可见集 V ∧ 非空）——含切面角色的宽判据。

        注意：这是 V（可见/被通知），不是提交权。提交权用
        ``capability_ledger.CapabilityLedger.can_execute``（能力面，门控同源）。
        """
        return self.domain_of(stream_id, entity_id, action_types).admits(roles)
