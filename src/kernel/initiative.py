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
    """

    def __init__(self, projections: dict, session, registry: StewardshipRegistry,
                 ledger: CapabilityLedger):
        if not isinstance(ledger, CapabilityLedger):
            raise InitiativeViolation(
                "LEDGER-REQUIRED: 必须注入 CapabilityLedger（匹配与 submit 门控同源，"
                "拒绝治理面推导的第二张皮）")
        self.projections = projections
        self.session = session
        self.registry = registry
        self.ledger = ledger
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
        for trig in fired:
            for role in visible:
                can_exec = self.ledger.can_execute(trig.action, [role])
                invitation = Invitation(
                    kind="initiative.invitation" if can_exec else "initiative.notice",
                    entity=entity_id, to_role=role, action=trig.action,
                    trigger=trig.name, can_execute=can_exec,
                    rule_hash=_stable_hash(f"{trig.name}|{trig.action}"))
                # 唯一写入：观察通道；principal=entity_id（事作为发起主体的归属）
                rec = self.session.append(
                    entity_id,
                    {"kind": invitation.kind,
                     "entity": invitation.entity,
                     "to_role": invitation.to_role,
                     "action": invitation.action,
                     "trigger": invitation.trigger,
                     "can_execute": invitation.can_execute,
                     "rule_hash": invitation.rule_hash})
                records.append(rec)
        self._last = records
        return records

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
                rec = self.session.append(
                    principal,
                    {"kind": invitation.kind,
                     "entity": invitation.entity,
                     "action": invitation.action,
                     "trigger": invitation.trigger,
                     "can_execute": invitation.can_execute,
                     "rule_hash": invitation.rule_hash})
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
