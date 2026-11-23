#!/usr/bin/env python3
"""src/kernel/store.py —— 本体事件日志（KS-1 / AX-1 / AX-3 / INV-1 / INV-13）。
写路径仅一条能力面：commit(action_id, ...) —— action_id 必在能力清单
write_actions 段（INV-13 闭环 / VER-27）。会话事件流已物理分离至 session.py
（KS-2.2：另一对象 = 另一存储；VER-4）。
基座 audit_append_only：不存在 update / delete / rewrite 路径（AX-3 / VER-28 item2）；
write_raw 直写陷阱必拒并产生 structurally-rejected 审计记录（INV-1 / VER-28 item1）。
事件八字段（KS-1.2）：event_id / stream_id / expected_version / event_type /
payload（含 valid_time）/ transaction_time / action_id / principal。
追加前校验（KS-1.3）：结构(schema) → 流规则 → 追加；fail-closed。
"""
from __future__ import annotations
import datetime as dt
import sys
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import (StoreRejection, DirectWriteForbidden, VersionConflict,   # noqa: F401
                           ValidTimeViolation, UnknownAction, StreamRuleViolation)  # 类型即条款
from kernel.registration import load_caps
DECISION_STREAM = "decision"
VIOLATION_STREAM = "domain:invariant"
@dataclass(frozen=True)
class Event:
    event_id: int
    stream_id: str
    expected_version: int
    event_type: str            # 含 schema 版本号（KS-5.1），形如 Order@1
    payload: MappingProxyType  # 含 valid_time；只读（AX-3）
    transaction_time: str      # 平台维护（P-13），调用方不可提供
    action_id: str
    principal: str
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class EventStore:
    """append-only 事件存储。唯一的写方法是 _append，仅由 commit 到达。"""
    def __init__(self):
        self.streams: dict[str, list[Event]] = {}
        self.audit: list[dict] = []            # audit_append_only：只增（INV-6）
        self._next_id = 1
        caps = load_caps()
        self._actions = {a["id"] for a in caps.get("write_actions", [])}
    def _reject(self, reason: str, exc: StoreRejection):
        self.audit.append({"kind": "structurally-rejected", "reason": reason,
                           "tx": _now()})
        raise exc
    # ---------- 唯一追加路径 ----------
    def _append(self, stream_id, expected_version, event_type, payload,
                action_id, principal, initiator=None) -> Event:
        if "@" not in event_type:                                   # KS-5.1
            self._reject(f"schema: {event_type} 缺版本号",
                         StoreRejection(f"SCHEMA-FAIL: event_type 须含 schema 版本号: {event_type}"))
        tx = _now()
        vt = payload.get("valid_time")
        if not vt:
            self._reject("schema: 缺 valid_time",
                         StoreRejection("SCHEMA-FAIL: payload 缺 valid_time（KS-1.2 八字段）"))
        if dt.datetime.fromisoformat(str(vt)) > dt.datetime.fromisoformat(tx):
            self._reject(f"valid_time {vt} > transaction_time {tx}",   # KS-6.1
                         ValidTimeViolation(f"VALID-TIME-DOMAIN: valid_time {vt} "
                                            f"> transaction_time {tx}（KS-6.1 / VER-16）"))
        actual = len(self.streams.get(stream_id, []))
        if expected_version != actual:
            self._reject(f"版本冲突 stream={stream_id}",
                         VersionConflict(
                             f"版本冲突: stream={stream_id} 期望 v{expected_version}，"
                             f"实际 v{actual} —— 必须完整重求值（结构 → 条件 → 聚合不变量）"
                             f"而非仅重试追加（KS-1.4 / VER-3）"))
        ev = Event(self._next_id, stream_id, expected_version, event_type,
                   MappingProxyType(dict(payload)), tx, action_id, principal)
        self.streams.setdefault(stream_id, []).append(ev)
        self._next_id += 1
        self.audit.append({"kind": "appended", "event_id": ev.event_id,
                           "stream": stream_id, "action": action_id, "tx": tx,
                           # 发起人身份：追加审计元数据，不进入事件八字段（KS-1.2）
                           "initiator": initiator})
        return ev
    # ---------- 能力清单上的唯一写面（INV-13 / KS-2.1） ----------
    def commit(self, action_id: str, stream_id: str, expected_version: int,
               event_type: str, payload: dict, principal: str,
               initiator: str | None = None) -> Event:
        if action_id not in self._actions:
            self._reject(f"未知能力 {action_id}",
                         UnknownAction(f"{action_id} 不在能力清单 write_actions 段（INV-13）"))
        def reject(reason: str, exc: StoreRejection):
            """commit 层的统一拒绝口：每次拒绝恰好一条审计（INV-1 / KS-1.3）。"""
            self._reject(f"commit/{action_id}: {reason}", exc)
        try:
            if event_type.startswith("InvariantViolation@") and action_id != "RaiseInvariantViolation":
                reject("违规对象写者不合法", StreamRuleViolation(           # INV-10
                    "违规对象仅可经 RaiseInvariantViolation 写入（P-7 / INV-10 / VER-23）"))
            if event_type.startswith("MergeDeclared@") and action_id != "DeclareIdentityMerge":
                reject("归并声明写者不合法", StreamRuleViolation(           # INV-13
                    "归并声明仅可经 DeclareIdentityMerge 写入（P-8 / INV-13 / VER-24）"))
            if action_id == "RecordDecision":
                if stream_id != DECISION_STREAM:
                    reject("决策流归属不符", StreamRuleViolation(
                        "决策事件 MUST 归属决策流（KS-2.6 / VER-33）"))
                missing = {"projection_ref", "session_ref"} - set(payload)   # KS-2.5
                if missing:
                    reject("决策引用缺失", StoreRejection(
                        f"DECISION-REFS-MISSING: 缺 {sorted(missing)}（KS-2.5 / VER-7）"))
            elif action_id == "RaiseInvariantViolation":
                if stream_id != VIOLATION_STREAM:
                    reject("违规流归属不符", StreamRuleViolation(
                        "违规对象 MUST 写入 domain:invariant 流（P-7 / VER-23）"))
                missing = {"invariant_ref", "status"} - set(payload)
                if missing:
                    reject("违规对象不完整", StoreRejection(
                        f"VIOLATION-OBJECT-INCOMPLETE: 缺 {sorted(missing)}"
                        f"（P-7 生命周期 / INV-10）"))
            elif action_id == "DeclareIdentityMerge":
                if stream_id != "domain:identity":
                    reject("归并流归属不符", StreamRuleViolation(
                        "归并声明 MUST 写入 domain:identity 流（P-8）"))
                missing = {"canonical", "absorbed"} - set(payload)
                if missing:
                    reject("归并引用缺失", StoreRejection(
                        f"MERGE-REFS-MISSING: 缺 {sorted(missing)}（P-8 双向记录）"))
                if payload.get("canonical") == payload.get("absorbed"):
                    reject("自归并", StoreRejection(
                        "SELF-MERGE-FORBIDDEN: canonical == absorbed（P-8）"))
            elif stream_id == DECISION_STREAM or stream_id.startswith("session"):
                reject("越权写入保留流", StreamRuleViolation(
                    f"{action_id} 不得写决策流/会话流（KS-2.1 / INV-5）"))
            return self._append(stream_id, expected_version, event_type, payload,
                                action_id, principal, initiator)
        except StoreRejection:
            raise          # _append / reject 已记审计：不重复记第二笔（审计双记缺陷）
    # ---------- 直写陷阱（必拒；VER-28 item1 模板层执行点） ----------
    def write_raw(self, **kwargs) -> Event:
        self.audit.append({"kind": "structurally-rejected", "attempt": "write_raw",
                           "tx": _now()})
        raise DirectWriteForbidden(
            "INV-1: 禁止 Action 之外的事件写入路径 —— 已产生 structurally-rejected 审计记录")
