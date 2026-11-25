#!/usr/bin/env python3
"""src/kernel/continuation.py —— 续办只读视图（观察接口，读侧派生）。

定位（诚实边界）：纯读模型。不写 EventStore、不写会话流、不写选择账本，
不产生规范条款，不参与任何权威重建（P-16 / VER-26 只认本体事件日志）。
调用本模块的任何方法都不会改变系统状态。

回答的问题：**此刻谁在等谁、办哪个动作、什么时候到期、依据是否已经陈旧。**

数据来源（全部只读）：
    projections —— 权威投影（只取 head() 水位）
    session     —— 观察通道（invitation / notice / auto / assignment）
    selections  —— 选择账本（三元组）

续办口径：一条 assignment 的 `basis.watermark` 等于源流当前水位 → `open`（仍然有效）；
被新事实推进 → `stale`（依据已陈旧，必须重新渲染候选后再选）。这与
SELECTION-STALE-BASIS 守卫同源，避免"视图说待办、守卫说陈旧"的两套口径。

到期口径：SLA 起点取 `basis.transaction_time`（权威事实时间）而非选择时刻，
行上 `sla_anchor` 标注实际所用口径（authority / selection）。超期因此是
"权威事实落地后多久仍无对应业务事件"的读时派生，不依赖观察层时间戳，
也不需要任何 `expired` 事件（缺席本身可由权威日志证明）。
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.errors import AosError  # noqa: E402


class ContinuationViolation(AosError):
    """续办视图违规基类（目前仅用于非法查询参数）。"""


_KIND_PREFIX = "initiative."


def _due_at(assigned_at: str, sla_hours, basis=None) -> str | None:
    """到期时刻 = SLA 起点 + 档位 SLA；未声明 SLA 则无到期（不臆造期限）。

    起点优先取权威事实时间（basis.transaction_time，KS-2.5 双引用的投影半边）：
    "该办而未办"的时长应从业务事实落地起算，而不是从观察层的选择时刻起算——
    观察记录可丢弃重建，据其计时的超期结论无法从权威日志复核。缺该字段时回退
    选择时刻（兼容旧记录），并在行上以 sla_anchor 显式标注所用口径。
    """
    if not sla_hours:
        return None
    start_raw = (basis or {}).get("transaction_time") or assigned_at
    try:
        start = dt.datetime.fromisoformat(str(start_raw))
    except (TypeError, ValueError):
        return None
    return (start + dt.timedelta(hours=int(sla_hours))).isoformat(timespec="seconds")


def _sla_anchor(basis) -> str:
    """本行到期所用的起点口径：authority=权威事实时间，selection=观察层选择时刻。"""
    return "authority" if (basis or {}).get("transaction_time") else "selection"


def _overdue(due_at: str | None, now: dt.datetime) -> bool:
    if not due_at:
        return False
    try:
        return dt.datetime.fromisoformat(due_at) < now
    except ValueError:
        return False


class ContinuationView:
    """续办只读视图；构造即快照引用，不缓存、不物化、不写入。"""

    def __init__(self, projections: dict, session, selections):
        self.projections = projections
        self.session = session
        self.selections = selections

    # ---------- 内部：只读取源 ----------
    def _head(self, projection_name: str, entity: str) -> int:
        """实体级水位：只有本实体被推进才让待办转 stale（跨实体不误伤）。"""
        proj = self.projections.get(projection_name)
        return proj.entity_head(entity) if proj is not None else 0

    def _assignment_rows(self) -> list[dict]:
        now = dt.datetime.now(dt.timezone.utc)
        rows: list[dict] = []
        for sel in self.selections.read_all():
            basis = sel.get("basis") or {}
            projection_name = basis.get("projection")
            watermark = basis.get("entity_watermark", basis.get("watermark"))
            head = self._head(projection_name, sel.get("entity"))
            rows.append({
                "entity": sel.get("entity"),
                "action": sel.get("action"),
                "assignee": sel.get("to_role"),
                "initiator": sel.get("principal"),
                "assigned_at": sel.get("ts"),
                "projection": projection_name,
                "tier": sel.get("tier"),
                "sla_hours": sel.get("sla_hours"),
                "due_at": _due_at(sel.get("ts"), sel.get("sla_hours"), basis),
                "sla_anchor": _sla_anchor(basis),
                "status": "open" if watermark is not None and watermark == head else "stale",
                "watermark": watermark,
                "head": head,
                "digest": sel.get("digest"),
            })
        for row in rows:
            row["overdue"] = row["status"] == "open" and _overdue(row["due_at"], now)
        return rows

    # ---------- 观察接口 ----------
    def assignments(self, projection_name: str | None = None) -> list[dict]:
        """全部责任传递记录（含 open / stale），按选择先后排列。"""
        rows = self._assignment_rows()
        if projection_name is None:
            return rows
        return [r for r in rows if r["projection"] == projection_name]

    def awaiting(self, entity: str) -> dict | None:
        """某实体最近一次责任传递（谁此刻该办什么）。"""
        for row in reversed(self._assignment_rows()):
            if row["entity"] == entity:
                return row
        return None

    def timeline(self, entity: str, projection_name: str | None = None) -> list[dict]:
        """实体时间线：权威事件 + 观察记录，按时间稳定排序（同秒内事件在前）。"""
        entries: list[dict] = []
        # 权威事件（只读；实体归属只认投影声明的 entity_key，禁止 payload 任意值匹配）
        for name, proj in self.projections.items():
            if projection_name is not None and name != projection_name:
                continue
            for ev in proj._scanned_events():
                if str(ev.payload.get(proj.entity_key)) != str(entity):
                    continue
                entries.append({"at": ev.transaction_time, "kind": "event",
                                "source": "event", "action": ev.action_id,
                                "principal": ev.principal, "event_id": ev.event_id})
        # 观察记录（invitation / notice / auto / selection / assignment）；实体按显式字段匹配
        for rec in self.session.read_all():
            if rec.get("entity") != entity:
                continue
            kind = str(rec.get("kind", ""))
            entries.append({"at": rec.get("ts"),
                            "kind": kind[len(_KIND_PREFIX):]
                            if kind.startswith(_KIND_PREFIX) else kind,
                            "source": "observation", "action": rec.get("action"),
                            "principal": rec.get("principal"),
                            "role": rec.get("to_role") or rec.get("assignee"),
                            "initiator": rec.get("initiator")})
        entries.sort(key=lambda e: str(e.get("at")))     # 稳定排序：同秒内事件在前
        return entries

    def summary(self) -> dict:
        """看板计数：责任传递总量 / 仍有效 / 依据陈旧 / 已逾期。"""
        rows = self._assignment_rows()
        return {"assignments": len(rows),
                "open": sum(r["status"] == "open" for r in rows),
                "stale": sum(r["status"] == "stale" for r in rows),
                "overdue": sum(bool(r["overdue"]) for r in rows)}
