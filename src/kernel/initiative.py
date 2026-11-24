#!/usr/bin/env python3
"""src/kernel/initiative.py —— 双向主动性：事找人 + 人找事，均落观察通道（信息性参考实现）。

定位（诚实边界）：不产生规范条款 —— 不改冻结正典、不改 spec 九类声明、不改能力
清单、不动 AX/KS/P/INV/GOV/VER 标识符。回答一个问题：管理域的可见集 V 与能力账簿
E 有了，谁来消费它们？答案是两个对称方向，都走与权威写路径物理分离的 SessionChannel：

    run()  事找人（demand）：投影状态触发 → 扫可见集 V → 按能力账 E 分类 →
          写 invitation（可提交）/ notice（切面见证），principal = 实体 id。
    seek() 人找事（supply）：人/Agent 出示角色 → 能力账簿反查可做 Action →
          投影命中 → 写 offer，principal = 人/Agent id。

两个方向都基于同一本能力账簿（capability_ledger，读 compiled 权限矩阵 = submit
门控同源），匹配即门控；都在 SessionChannel 落意向消息，认领后才走 Kernel.submit。

四条不可越的红线（写进代码结构，不靠自觉）：
1. 只读权威状态：从 Projection.snapshot() 读，不写 EventStore、不调用 Kernel.submit。
2. 只写观察：意向消息 append 到 SessionChannel，逐条 principal 归属（KS-2.3），
   不进任何权威投影（投影源级排除 session，KS-2.2）。
3. 不自动提交、不代签、不绕过门控：产出的是"邀请/通知/意向"，不是"已完成的动作"。
4. 匹配与门控同源：E 判定读 compiled 能力账簿，不读第二份治理推导。

触发器是受限谓词：只接受已注册的判定器（callable）或显式状态断言，不执行字符串
表达式、不开新的求值路径——受限解释器的唯一权威在 interpreter/，本模块不复制它。

fail-closed：投影未物化 / V 为空 / 能力账簿为空 / 触发器判定器缺失 → 拒绝或空结果。
"""
from __future__ import annotations

import inspect
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.errors import AosError  # noqa: E402
from kernel.stewardship import (  # noqa: E402  可见集 V（治理面，切面/跨组织）
    StewardshipRegistry,
)
from kernel.capability_ledger import CapabilityLedger  # noqa: E402  执行集 E（能力面，门控同源）
from kernel.assurance import (  # noqa: E402  校验强度档位（可调，但不跌破宪法下限）
    AssurancePolicy,
    GatePlan,
    ensure_facets_visible,
)
from kernel.selection import (  # noqa: E402  选择审计（责任传递：谁 / 何时 / 依据）
    SelectionLedger,
    SelectionNotOffered,
    SelectionStaleBasis,
    SelectionPrincipalMismatch,
)
from kernel.continuation import ContinuationView  # noqa: E402  续办只读视图（观察接口）


class InitiativeViolation(AosError):
    """双向主动性违规基类。"""


class ProjectionNotReady(InitiativeViolation):
    """权威投影未物化 —— 不能基于未重建状态做主动判定（fail-closed）。"""


class NoCandidates(InitiativeViolation):
    """可见集扫描无候选切面角色 —— 无事可邀（可预期终止，非错误，但显式）。"""


class NoCapability(InitiativeViolation):
    """人找事：出示角色无任何可推动 Action —— 能力账簿无匹配（可预期终止）。"""


@dataclass(frozen=True)
class Trigger:
    """一个主动触发规则（实例侧声明，信息性）。

    name      —— 规则名（进意向记录，可审计）
    action    —— 该触发想推动的 Action（用于 E 收窄候选 / 人找事按能力过滤）
    predicate —— 受限判定器 callable(snapshot: dict[, entity_id: str]) -> bool；
                 实例侧注入，本模块不解析表达式、不执行字符串（受限解释器仍是
                 唯一求值权威）。单参谓词兼容旧写法（全快照判定）；双参谓词
                 接收当前目标实体 id，支持多实体场景的逐实体精确判定。
    """

    name: str
    action: str
    predicate: object

    def fires(self, snapshot: dict, entity_id: str | None = None) -> bool:
        if not callable(self.predicate):
            raise InitiativeViolation(
                f"TRIGGER-PREDICATE-INVALID: {self.name} 判定器不可调用（fail-closed）")
        # 向后兼容：单参谓词仍是全快照判定；双参谓词按目标实体收窄。
        if entity_id is not None:
            try:
                arity = len(inspect.signature(self.predicate).parameters)
            except (TypeError, ValueError):
                arity = 1
            if arity >= 2:
                return bool(self.predicate(snapshot, entity_id))
        return bool(self.predicate(snapshot))


@dataclass(frozen=True)
class Invitation:
    """一条主动意向（观察记录的值部分；principal 由 SessionChannel 单独携带）。"""

    kind: str            # initiative.invitation / initiative.notice / initiative.offer
    entity: str
    to_role: str         # 事找人：目标角色；人找事：空串（principal 即当事人）
    action: str
    trigger: str
    can_execute: bool    # 能力账簿 E(action) 确认可提交；否则只被通知（见证切面）
    rule_hash: str       # 触发规则的稳定指纹（声明溯源，可审计）


class InitiativeEngine:
    """双向主动行为引擎：投影 → 触发判定 → V 扫描 / 能力反查 → 观察通道落账。

    projections: dict[str, Projection] —— 权威投影（只读）
    session:     SessionChannel         —— 观察通道（唯一写入目标）
    registry:    StewardshipRegistry    —— 可见集 V（治理面：切面/跨组织）
    ledger:      CapabilityLedger       —— 执行集 E（能力面：submit 门控同源）
    policy:      AssurancePolicy | None —— 校验强度档位（可调；注入后意向记录
                 携带档位/复核人数/SLA/是否可自主提交，不改变"邀请≠执行"红线）
    """

    def __init__(self, projections: dict, session, registry: StewardshipRegistry,
                 ledger: CapabilityLedger, policy: AssurancePolicy | None = None):
        if not isinstance(ledger, CapabilityLedger):
            raise InitiativeViolation(
                "LEDGER-REQUIRED: 必须注入 CapabilityLedger（匹配与 submit 门控同源，"
                "拒绝治理面推导的第二张皮）")
        if policy is not None and not isinstance(policy, AssurancePolicy):
            raise InitiativeViolation(
                "POLICY-REQUIRED: policy 必须是 AssurancePolicy（拒绝形似策略的第二张皮）")
        self.projections = projections
        self.session = session
        self.registry = registry
        self.ledger = ledger
        self.policy = policy
        self.selections = SelectionLedger(session)   # 责任传递审计账本（观察层，随通道持久化）
        self._last: list[dict] = []

    def _snapshot(self, projection_name: str) -> dict:
        proj = self.projections.get(projection_name)
        if proj is None:
            raise ProjectionNotReady(
                f"PROJECTION-ABSENT: {projection_name} 未注册（fail-closed）")
        try:
            return proj.snapshot()
        except Exception as e:                       # ProjectionNotMaterialized 等
            raise ProjectionNotReady(
                f"PROJECTION-NOT-READY: {projection_name} 未物化（{e}）—— 先 rebuild") from e

    def scan_candidates(self, stream_id: str, entity_id: str,
                        candidates, action_types=None) -> tuple[str, ...]:
        """可见集扫描（V）：仅返回 V 内角色（切面成员：当事人+检验+监理…）。"""
        return self.registry.scan(stream_id, entity_id, candidates, action_types)

    def _plan(self, action: str) -> GatePlan | None:
        """求值该 Action 的校验强度档位；未注入策略时返回 None（保持旧行为）。"""
        return None if self.policy is None else self.policy.plan(action)

    @staticmethod
    def _assurance_fields(plan: GatePlan | None, can_exec: bool) -> dict:
        """档位字段：可调的强度 + 恒定的宪法下限一并进观察记录（可审计）。"""
        if plan is None:
            return {}
        tier = plan.tier
        return {
            "assurance_tier": tier.name,
            "requires_dry_run": tier.requires_dry_run,
            "min_approvals": tier.min_approvals,
            "sla_hours": tier.sla_hours,
            "required_facets": list(tier.required_facets),
            # 自主 = 档位允许 ∧ 确有执行权：无执行权者一律不得自主
            "auto_commit": bool(tier.auto_commit and can_exec),
            "immutable_gates": sorted(plan.immutable_gates),
            # 诚实边界：档位是建议复核强度，写路径不消费（advisory）
            "assurance_advisory": plan.advisory,
            "assurance_enforced": not plan.advisory,
        }

    # ------------------------------------------------------------------
    # 方向一：事找人（demand）
    # ------------------------------------------------------------------
    def run(self, *, projection_name: str, stream_id: str, entity_id: str,
            candidates, triggers: list[Trigger], action_types=None) -> list[dict]:
        """事找人：命中的触发规则 → 扫 V → 按能力账 E 分类 → 写意向消息。

        返回本次写入 session 的记录列表。不接触 EventStore、不调用 submit。
        """
        snapshot = self._snapshot(projection_name)          # 只读权威状态
        fired = [t for t in triggers if t.fires(snapshot, entity_id)]
        if not fired:
            self._last = []
            return []

        visible = self.scan_candidates(stream_id, entity_id, candidates, action_types)
        if not visible:
            raise NoCandidates(
                f"NO-CANDIDATES: {stream_id}/{entity_id} 可见集为空 —— 无可邀角色")

        records: list[dict] = []
        basis = self.projections[projection_name].stamp(entity_id)  # 渲染时戳（含实体水位）
        for trig in fired:
            plan = self._plan(trig.action)
            if plan is not None:
                # 组合可调的下限：要求的检验切面必须真的可见，否则不发出无法兑现的邀请
                ensure_facets_visible(plan, visible)
            for role in visible:
                can_exec = self.ledger.can_execute(trig.action, [role])
                fields = self._assurance_fields(plan, can_exec)
                if fields.get("auto_commit"):
                    kind = "initiative.auto"
                else:
                    kind = ("initiative.invitation" if can_exec
                            else "initiative.notice")
                invitation = Invitation(
                    kind=kind,
                    entity=entity_id, to_role=role, action=trig.action,
                    trigger=trig.name, can_execute=can_exec,
                    rule_hash=_stable_hash(f"{trig.name}|{trig.action}"))
                # 唯一写入：观察通道；principal=entity_id（事作为发起主体的归属）
                payload = {"kind": invitation.kind,
                           "entity": invitation.entity,
                           "to_role": invitation.to_role,
                           "action": invitation.action,
                           "trigger": invitation.trigger,
                           "can_execute": invitation.can_execute,
                           "rule_hash": invitation.rule_hash,
                           "projection": projection_name,
                           "stream_id": stream_id,
                           "basis": basis}
                payload.update(fields)
                rec = self.session.append(entity_id, payload)
                records.append(rec)
        self._last = records
        return records

    # ------------------------------------------------------------------
    # 责任传递：上一轮发起人对已给出的候选做选择（选择 ≠ 执行）
    # ------------------------------------------------------------------
    def select(self, *, principal: str, entity_id: str, action: str,
               to_role: str) -> dict:
        """上一轮发起人在候选集中做出选择 → 责任传递到承接岗位。

        fail-closed：
          * 只能选引擎刚刚给出、且确有执行权的候选（SELECTION-NOT-OFFERED）——
            选择不得造选项；
          * 选择主体必须是该实体的发起人（SELECTION-PRINCIPAL-MISMATCH）——
            "上一轮发起人选择"不能由任意调用方自称；
          * 依据取自已物化投影的 decision_ref（KS-2.5 双引用），不得凭印象；
          * 同一决策重试幂等：主体/岗位/依据/档位全同 → 返回原记录，不重复留账；
          * 不写 EventStore —— 真正的变更仍由持岗人以自己的主体走 submit 与全部闸门。
        """
        offered = {(r.get("entity"), r.get("action"), r.get("to_role")): r
                   for r in self._last if r.get("can_execute")}
        rec = offered.get((entity_id, action, to_role))
        if rec is None:
            raise SelectionNotOffered(
                f"SELECTION-NOT-OFFERED: {entity_id}/{action}/{to_role} 不在本轮候选"
                f"（或该岗位无执行权）—— 选择不得造选项（fail-closed）")
        stream_id = rec.get("stream_id")
        if not stream_id:
            raise SelectionNotOffered(
                "SELECTION-NOT-OFFERED: 候选记录缺聚合流标识，发起人不可重建")
        owner = self.registry.owner_of(stream_id, entity_id)
        if principal != owner:
            raise SelectionPrincipalMismatch(
                f"SELECTION-PRINCIPAL-MISMATCH: {principal} 不是 {entity_id} 的发起人"
                f"（应为 {owner}）—— 选择权只归上一轮发起人（fail-closed）")
        projection_name = rec.get("projection")
        proj = self.projections.get(projection_name)
        if proj is None:
            raise SelectionNotOffered(
                f"SELECTION-NOT-OFFERED: 候选记录缺可锚定投影 {projection_name!r}")
        basis = rec.get("basis")
        if not isinstance(basis, dict) or "watermark" not in basis:
            raise SelectionNotOffered(
                "SELECTION-NOT-OFFERED: 候选缺渲染时戳，无法校验依据新颖性")
        # 实体级新颖性：只有"本实体"被新事实推进才算陈旧（跨实体推进不误伤）
        if "entity_watermark" in basis:
            expected, current = basis["entity_watermark"], proj.entity_head(entity_id)
        else:
            expected, current = basis["watermark"], proj.head()
        if current != expected:
            raise SelectionStaleBasis(
                f"SELECTION-STALE-BASIS: {entity_id} 自渲染后已被新事实推进"
                f"（水位 {expected} → {current}）—— "
                f"必须重新渲染候选后再选（fail-closed）")

        chosen = self.selections.record(
            principal=principal, entity=entity_id, action=action, to_role=to_role,
            basis=basis, tier=rec.get("assurance_tier"),
            sla_hours=rec.get("sla_hours"))
        # 幂等：同一决策的重试不得重复写 assignment（选择账本已返回原记录）
        existing = next((r for r in reversed(self.session.read_all())
                         if r.get("kind") == "initiative.assignment"
                         and r.get("selection_digest") == chosen["digest"]), None)
        if existing is not None:
            return existing
        return self.session.append(principal, {
            "kind": "initiative.assignment",
            "entity": entity_id,
            "action": action,
            "initiator": principal,
            "assignee": to_role,
            "basis": chosen["basis"],
            "tier": chosen["tier"],
            "sla_hours": chosen["sla_hours"],
            "selection_digest": chosen["digest"],
        })

    # ------------------------------------------------------------------
    # 观察接口：续办只读视图（谁在等谁、办什么、何时到期）
    # ------------------------------------------------------------------
    @property
    def continuation(self) -> ContinuationView:
        """只读视图：不缓存、不物化、不写入（每次取当前事实的最新派生）。"""
        return ContinuationView(self.projections, self.session, self.selections)

    # ------------------------------------------------------------------
    # 方向二：人找事（supply）
    # ------------------------------------------------------------------
    def seek(self, *, principal: str, roles, projection_name: str,
             triggers: list[Trigger], stream_id=None, entity_id=None) -> list[dict]:
        """人找事：出示角色 → 能力账簿反查可推动 Action → 投影命中 → 写 offer。

        与 run() 对称：同一本能力账簿（supply 是 demand 的反向投影），同一观察通道。
        **stream_id 与 entity_id 必须成对提供**：成对时先做 V 门控（域外不可参与该
        实体的主动性互动）；都不传则在投影全实体上查找（参考实现的全局视角）。
        只给其一即拒绝（fail-closed，禁止用半参数绕过域门控）。

        人/Agent 认领后仍走原写路径 submit，权限与条件门控照旧——offer 不是执行。
        """
        if not principal:
            raise InitiativeViolation("SEEK-PRINCIPAL-REQUIRED: 人找事须出示主体（KS-2.3）")
        if (stream_id is None) != (entity_id is None):
            raise InitiativeViolation(
                "SEEK-SCOPE-INCOMPLETE: seek 的 stream_id 与 entity_id 必须成对提供，"
                "禁止半参数绕过可见集 V 的域门控（fail-closed）")
        eligible = set(self.ledger.supply(roles))
        if not eligible:
            raise NoCapability(
                f"NO-CAPABILITY: 角色 {sorted(set(roles or ()))} 无可推动 Action"
                " —— 能力账簿无匹配（fail-closed）")

        snapshot = self._snapshot(projection_name)          # 只读权威状态
        if stream_id is not None and entity_id is not None:
            if not self.registry.can_interact(stream_id, entity_id, roles):
                return []                                   # 域外：无 offer，不报错

        targets = [entity_id] if entity_id else sorted(snapshot.keys())
        records: list[dict] = []
        for trig in triggers:
            if trig.action not in eligible:                 # 能力账簿过滤：我做不了的不推给我
                continue
            plan = self._plan(trig.action)
            for target in targets:
                # 逐目标判定：单参谓词全快照判定；双参谓词按该实体精确判定，
                # 避免"一个实体命中 → 所有实体都收到 offer"的扇出错误。
                if not trig.fires(snapshot, str(target)):
                    continue
                invitation = Invitation(
                    kind="initiative.offer",
                    entity=str(target), to_role="", action=trig.action,
                    trigger=trig.name, can_execute=True,
                    rule_hash=_stable_hash(f"seek|{trig.name}|{trig.action}"))
                # 唯一写入：观察通道；principal = 找事的人/Agent（主体归属）
                payload = {"kind": invitation.kind,
                           "entity": invitation.entity,
                           "action": invitation.action,
                           "trigger": invitation.trigger,
                           "can_execute": invitation.can_execute,
                           "rule_hash": invitation.rule_hash}
                payload.update(self._assurance_fields(plan, can_exec=True))
                rec = self.session.append(principal, payload)
                records.append(rec)
        self._last = records
        return records

    def last_invitations(self) -> list[dict]:
        """本次 run/seek 产出的意向记录（只读快照，供上层展示/测试）。"""
        return list(self._last)


def _stable_hash(text: str) -> str:
    """规则指纹：稳定、可复算，不依赖进程随机盐（审计可重现）。"""
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
