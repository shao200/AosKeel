#!/usr/bin/env python3
"""src/kernel/selection.py —— 选择行为审计账本（责任传递，观察层）。

定位（诚实边界）：观察层 —— 不产生权威事件、不改写路径模型、不改事件八字段
（KS-1.2）、不动能力清单。本模块只负责把"上一轮发起人选择了哪个候选、把责任
交给谁"落成 append-only 的审计三元组：

    who   —— principal（选择人，即上一轮发起人）
    when  —— ts（记录时刻，平台维护）
    basis —— （投影标识, transaction_time）双引自证据（KS-2.5），可用
             projection.resolve_decision_ref 机械复核 —— 不是自由字符串。

红线（全部 fail-closed）：
    1. 无主体不得选择（SELECTION-PRINCIPAL-REQUIRED，KS-2.3 / INV-8）。
    2. 无投影依据不得选择（SELECTION-BASIS-REQUIRED）—— 选择必须可锚定到某个
       已物化的权威快照，禁止"凭印象选"。
    3. 承接岗位缺失即拒（SELECTION-ASSIGNEE-REQUIRED）—— 责任必须落到具体岗位，
       悬空的任务等于没有责任传递。
    4. 选择 ≠ 执行：本模块不写 EventStore（INV-1 唯一写路径），真正的状态变更
       仍须由持岗人以自己的 principal 走 submit 与全部闸门。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.errors import AosError  # noqa: E402


class SelectionViolation(AosError):
    """选择行为违规基类。"""


class SelectionPrincipalRequired(SelectionViolation):
    """缺少选择主体 —— 审计三元组不完整。"""


class SelectionBasisRequired(SelectionViolation):
    """缺少投影依据 —— 选择无法锚定到权威快照。"""


class SelectionAssigneeRequired(SelectionViolation):
    """缺少承接岗位 —— 责任无处落地。"""


class SelectionNotOffered(SelectionViolation):
    """选择了引擎未曾给出的候选（或该岗位无执行权）—— 选择不等于造选项。"""


class SelectionStaleBasis(SelectionViolation):
    """所选依据的快照在渲染后已推进 —— 必须重新渲染后再选（fail-closed）。"""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _validate_basis(basis) -> dict:
    """依据必须是 KS-2.5 双引用的投影半边，且两段都非空。"""
    if not isinstance(basis, dict):
        raise SelectionBasisRequired(
            "SELECTION-BASIS-REQUIRED: 选择必须携带投影依据（fail-closed）")
    proj = basis.get("projection")
    tx = basis.get("transaction_time")
    if not proj or not tx:
        raise SelectionBasisRequired(
            "SELECTION-BASIS-REQUIRED: 依据须含 projection + transaction_time"
            "（KS-2.5 双引用），不得凭印象选择")
    ref = {"projection": str(proj), "transaction_time": str(tx)}
    for key in ("watermark", "entity_watermark"):     # 水位：事后可复核选择是否基于陈旧视图
        if basis.get(key) is not None:
            ref[key] = basis.get(key)
    return ref


class SelectionLedger:
    """append-only 选择账本；无更新 / 删除路径（对齐 AX-3 / INV-6 口径）。"""

    def __init__(self):
        self._log: list[dict] = []

    def record(self, *, principal: str, entity: str, action: str, to_role: str,
               basis, tier: str | None = None,
               sla_hours: int | None = None) -> dict:
        if not principal:
            raise SelectionPrincipalRequired(
                "SELECTION-PRINCIPAL-REQUIRED: 无主体不得选择（KS-2.3 / INV-8）")
        if not to_role:
            raise SelectionAssigneeRequired(
                "SELECTION-ASSIGNEE-REQUIRED: 责任必须落到具体岗位")
        if not action:
            raise SelectionViolation("SELECTION-ACTION-REQUIRED: 未指明所选候选动作")
        if not entity:
            raise SelectionViolation("SELECTION-ENTITY-REQUIRED: 未指明责任传递的实体")

        ref = _validate_basis(basis)
        ts = _now()
        digest = hashlib.sha256(
            repr((principal, ts, entity, action, to_role,
                  ref["projection"], ref["transaction_time"],
                  ref.get("watermark"), ref.get("entity_watermark"),
                  tier, sla_hours)).encode("utf-8")).hexdigest()[:16]
        rec = {"kind": "initiative.selection", "principal": principal, "ts": ts,
               "entity": entity, "action": action, "to_role": to_role,
               "basis": ref, "tier": tier, "sla_hours": sla_hours,
               "digest": digest}
        self._log.append(rec)                      # append-only
        return rec

    def resolve(self, entity: str) -> str | None:
        """该实体最近一次选择的主体 —— 供下一次提交出示 initiator。"""
        for rec in reversed(self._log):
            if rec["entity"] == entity:
                return rec["principal"]
        return None

    def assigned_to(self, entity: str) -> str | None:
        """该实体最近一次选择承接的岗位。"""
        for rec in reversed(self._log):
            if rec["entity"] == entity:
                return rec["to_role"]
        return None

    def read_all(self) -> list[dict]:
        """仅限审计用途（不得进入任何投影源，KS-2.2 / KS-2.4）。"""
        return list(self._log)
