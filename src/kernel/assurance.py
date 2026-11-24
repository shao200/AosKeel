#!/usr/bin/env python3
"""src/kernel/assurance.py —— 校验强度策略（Assurance Policy，信息性参考实现）。

定位（诚实边界）：不产生规范条款 —— 不改冻结正典、不改 spec 九类声明、
不改能力清单、不动 AX/KS/P/INV/GOV/VER 标识符。本模块只做一件事：把
"控制 / 验证 / 检验的强度"从写死常量升格为可声明的策略档位，同时保证任何
档位都无法跌破宪法下限。

关键边界（P1.8 诚实口径）：档位是**建议复核强度（advisory）**，不是写路径
闸门。`Kernel.submit` 不消费本模块；档位只进入邀请/指派观察记录，并由
`assurance_enforced: false` 显式标注，避免读者误以为 min_approvals /
requires_dry_run / auto_commit 已在提交点强制。真正强制需要审批证据与演练
票据的持久化模型，属另立交付；`auto_commit` 亦不自动提交（人员提交边界）。

三层可调性（只有前两层落在本模块）：
    参数可调   dry_run 强度、复核人数、SLA 时限（纯取值，安全）
    组合可调   需要几道检验、哪些切面角色必须参与（受下限约束）
    语义禁调   fail-closed / 单一提交点 / 审计三元组 / 角色约束 —— 结构恒定：
               策略声明里根本没有对应字段可写，不是"默认开启"，而是"无法关闭"。

为什么语义层禁调是结构性的，而不是靠自觉：
    GatePlan.immutable_gates 直接取 IMMUTABLE_GATES 常量，与声明无关。声明中
    一旦出现 gates / immutable_gates 键，from_mapping 直接 FloorViolation ——
    不是静默忽略，而是拒绝加载（fail-closed）。

单调性护栏（全部 fail-closed）：
    1. 声明不得出现 gates / immutable_gates 键（不能声明"移除某道闸"）。
    2. 若声明了 floor，必须 ⊇ IMMUTABLE_GATES（只能加严，不能缩减）。
    3. 自主提交（auto_commit）必须同时要求 dry_run 取证 —— 自主 ≠ 免检。
    4. required_facets 若显式声明，必须是治理面可见集的子集（不得凭空造角色）。
    5. 未声明的 Action 无默认档位 —— UnknownActionTier，不默认放行。
    6. 布尔档严格 isinstance(bool)，禁止 bool() 强转兜底；计数须为非负整数。

调整的唯一通道是声明文件（config/assurance-policy.yaml）：实例侧可编辑，
生效带 digest 溯源，运行期只读 —— 不允许"热改策略"绕过治理。
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.errors import AosError  # noqa: E402

# 宪法下限：任一档位求值后都必须携带，常量赋值，声明无法覆盖。
IMMUTABLE_GATES = frozenset({
    "fail_closed",          # 校验失败即拒绝，不降级放行
    "single_submit_point",  # 提交点唯一，无特权通道（INV-1）
    "audit_triad",          # 每次评估留档（谁 / 何时 / 基于哪个快照）
    "role_constraint",      # 动作必须角色受限（P-10）
})

DEFAULT_POLICY_PATH = ROOT / "config" / "assurance-policy.yaml"

_BANNED_KEYS = ("gates", "immutable_gates")


class AssuranceViolation(AosError):
    """校验强度策略违规基类。"""


class FloorViolation(AssuranceViolation):
    """试图跌破宪法下限，或声明形态非法 —— 拒绝加载（fail-closed）。"""


class UnknownTier(AssuranceViolation):
    """Action 引用了未声明的档位。"""


class UnknownActionTier(AssuranceViolation):
    """Action 未声明校验强度 —— 无默认档位，不默认放行。"""


class FacetNotAuthorized(AssuranceViolation):
    """策略要求的检验切面不在可见集内 —— 检验无法成立，拒绝发出邀请。"""


def _strict_bool(value, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise FloorViolation(
            f"POLICY-NON-BOOL: {field_name} 必须是布尔值（禁止 bool() 兜底）")
    return value


def _strict_count(value, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise FloorViolation(
            f"POLICY-BAD-COUNT: {field_name} 必须是非负整数，实得 {value!r}")
    return value


@dataclass(frozen=True)
class AssuranceTier:
    """一个校验强度档位（不可变值对象）。"""

    name: str
    requires_dry_run: bool
    min_approvals: int
    sla_hours: int | None
    required_facets: tuple[str, ...]
    auto_commit: bool


@dataclass(frozen=True)
class GatePlan:
    """某 Action 的求值结果：档位 + 恒定携带的宪法下限。

    advisory 恒为 True：档位只标注建议复核强度，`Kernel.submit` 不消费。
    """

    action: str
    tier: AssuranceTier
    immutable_gates: frozenset[str]
    advisory: bool = True


class AssurancePolicy:
    """校验强度策略：声明 → 档位 → GatePlan。

    tiers    —— 档位表（名称 → AssuranceTier）
    actions  —— Action → 档位名
    floor    —— 声明的下限集（必须 ⊇ IMMUTABLE_GATES；缺省即取全集）
    """

    def __init__(self, tiers: dict, actions: dict, floor):
        self.tiers = dict(tiers)
        self.actions = dict(actions)
        self.floor = frozenset(floor)

    # ------------------------------------------------------------------
    # 构造：声明 → 策略（全部校验在这里收口，越界即拒绝加载）
    # ------------------------------------------------------------------
    @classmethod
    def from_mapping(cls, data: dict) -> "AssurancePolicy":
        if not isinstance(data, dict):
            raise FloorViolation("POLICY-NOT-MAPPING: 策略声明必须是映射")
        for banned in _BANNED_KEYS:
            if banned in data:
                raise FloorViolation(
                    f"POLICY-GATE-REMOVAL: 声明不得出现 {banned} 键 —— "
                    f"闸门不可关，只能调强度")

        version = data.get("version")
        if isinstance(version, bool) or version != 1:
            raise FloorViolation("POLICY-VERSION: version 必须为 1")

        floor_raw = data.get("floor")
        if floor_raw is None:
            floor = set(IMMUTABLE_GATES)
        else:
            if not isinstance(floor_raw, (list, tuple)):
                raise FloorViolation("POLICY-FLOOR-TYPE: floor 必须是列表")
            declared = frozenset(str(x) for x in floor_raw)
            missing = IMMUTABLE_GATES - declared
            if missing:
                raise FloorViolation(
                    f"POLICY-FLOOR-WEAKENED: 宪法下限缺 {sorted(missing)} —— "
                    f"只可加严，不可缩减")
            floor = set(declared)

        tiers_raw = data.get("tiers")
        if not isinstance(tiers_raw, dict) or not tiers_raw:
            raise FloorViolation("POLICY-NO-TIERS: 未声明任何档位（fail-closed）")
        tiers = {str(name): cls._parse_tier(str(name), spec)
                 for name, spec in tiers_raw.items()}

        actions_raw = data.get("actions") or {}
        if not isinstance(actions_raw, dict):
            raise FloorViolation("POLICY-ACTIONS-TYPE: actions 必须是映射")
        actions: dict[str, str] = {}
        for action, spec in actions_raw.items():
            tier_name = cls._tier_name_of(str(action), spec)
            if tier_name not in tiers:
                raise UnknownTier(
                    f"UNKNOWN-TIER: {action} 引用未声明档位 {tier_name}")
            actions[str(action)] = tier_name

        return cls(tiers, actions, floor)

    @staticmethod
    def _tier_name_of(action: str, spec) -> str:
        if isinstance(spec, str):
            return spec
        if isinstance(spec, dict):
            for banned in _BANNED_KEYS:
                if banned in spec:
                    raise FloorViolation(
                        f"POLICY-GATE-REMOVAL: {action} 不得声明 {banned}（闸门不可关）")
            name = spec.get("tier")
            if not isinstance(name, str) or not name:
                raise FloorViolation(f"POLICY-TIER-MISSING: {action} 未指定 tier")
            return name
        raise FloorViolation(f"POLICY-ACTION-SPEC: {action} 声明形态非法")

    @staticmethod
    def _parse_tier(name: str, spec) -> AssuranceTier:
        if not isinstance(spec, dict):
            raise FloorViolation(f"POLICY-TIER-TYPE: 档位 {name} 必须是映射")
        for banned in _BANNED_KEYS:
            if banned in spec:
                raise FloorViolation(
                    f"POLICY-GATE-REMOVAL: 档位 {name} 不得声明 {banned}（闸门不可关）")

        dry = _strict_bool(spec.get("requires_dry_run", False),
                           f"{name}.requires_dry_run")
        auto = _strict_bool(spec.get("auto_commit", False), f"{name}.auto_commit")
        approvals = _strict_count(spec.get("min_approvals", 0),
                                  f"{name}.min_approvals")

        sla = spec.get("sla_hours")
        if sla is not None:
            if isinstance(sla, bool) or not isinstance(sla, int) or sla <= 0:
                raise FloorViolation(
                    f"POLICY-BAD-SLA: {name}.sla_hours 必须是正整数或 null")

        facets = spec.get("required_facets") or []
        if not isinstance(facets, (list, tuple)):
            raise FloorViolation(f"POLICY-FACETS-TYPE: {name}.required_facets 必须是列表")

        # 自主 ≠ 免检：自动提交必须先由 dry_run 取证，否则不得声明。
        if auto and not dry:
            raise FloorViolation(
                f"POLICY-AUTO-WITHOUT-EVIDENCE: 档位 {name} 自主提交必须 "
                f"requires_dry_run: true（自主 ≠ 免检）")

        return AssuranceTier(
            name=name, requires_dry_run=dry, min_approvals=approvals,
            sla_hours=sla, required_facets=tuple(str(f) for f in facets),
            auto_commit=auto)

    @classmethod
    def load(cls, path=None) -> "AssurancePolicy":
        """从声明文件加载（唯一通道；运行期只读，不提供热改入口）。"""
        import yaml
        p = Path(path) if path is not None else DEFAULT_POLICY_PATH
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return cls.from_mapping(data)

    # ------------------------------------------------------------------
    # 求值
    # ------------------------------------------------------------------
    def tier_of(self, action: str) -> str:
        try:
            return self.actions[action]
        except KeyError:
            raise UnknownActionTier(
                f"UNKNOWN-ACTION-TIER: {action} 未声明校验强度 —— "
                f"无默认档位（fail-closed）")

    def plan(self, action: str) -> GatePlan:
        """求值：档位 + 恒定携带的宪法下限（下限与声明无关）。"""
        tier = self.tiers[self.tier_of(action)]
        return GatePlan(action=action, tier=tier,
                        immutable_gates=IMMUTABLE_GATES)

    def digest(self) -> str:
        """策略指纹：档位与下限的稳定摘要（可审计、可比对漂移）。"""
        rows = sorted(
            (a, t.name, t.requires_dry_run, t.min_approvals, t.sla_hours,
             tuple(t.required_facets), t.auto_commit)
            for a, t in ((a, self.tiers[n]) for a, n in self.actions.items()))
        blob = repr((tuple(rows), tuple(sorted(self.floor)))).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]


def ensure_facets_visible(plan: GatePlan, visible_roles) -> None:
    """组合可调的下限：策略要求的检验切面必须真的可见，否则检验无法成立。

    未声明 required_facets 时不做约束（默认继承治理面执行集）。
    """
    required = plan.tier.required_facets
    if not required:
        return
    have = set(visible_roles or ())
    missing = [f for f in required if f not in have]
    if missing:
        raise FacetNotAuthorized(
            f"FACET-NOT-AUTHORIZED: {plan.action} 要求切面 {missing} 不在可见集 "
            f"（fail-closed，不发出无法兑现的邀请）")
