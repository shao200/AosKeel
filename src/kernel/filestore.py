"""src/kernel/filestore.py —— FileStore：append-only 事件日志的持久化参考实现。
单一 JSONL 文件；写路径只有"追加一行"（open 'a'，无 truncate/seek 写/重写），
重启经重放重建 streams —— append-only 语义在此是自证的，不靠约定。
继承 EventStore 的全部校验面（KS-1.3 结构 → 流规则 → 追加、版本冲突、
write_raw 直写陷阱、一次拒绝恰一条审计）；拒绝发生在落盘之前，文件不留半行。
诚实边界（参考实现，非生产件）：单写进程模型 —— 多进程并发需实例侧
自行加锁或以数据库实现同协议；崩溃窗口（内存已追加、落盘前断电）以
"启动时以文件为准重放"为恢复口径。
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
from types import MappingProxyType
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import Event, EventStore   # noqa: E402
class FileStore(EventStore):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self._replay()
    # ---------- 重放：文件是唯一持久真源 ----------
    def _replay(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            ev = Event(rec["event_id"], rec["stream_id"], rec["expected_version"],
                       rec["event_type"], MappingProxyType(rec["payload"]),
                       rec["transaction_time"], rec["action_id"], rec["principal"])
            self.streams.setdefault(ev.stream_id, []).append(ev)
            self._next_id = max(self._next_id, ev.event_id + 1)
            # 重放同时重建追加证据：appended 审计可从持久事件日志机械导出；
            # structurally-rejected 与解释器评估审计只随进程存在（诚实边界）。
            self.audit.append({"kind": "appended", "event_id": ev.event_id,
                               "stream": ev.stream_id, "action": ev.action_id,
                               "tx": ev.transaction_time,
                               # 发起人身份随事件日志持久化，重启后可重建
                               "initiator": rec.get("initiator")})
    # ---------- 唯一追加路径的写穿：内存校验通过后才落盘 ----------
    def _append(self, stream_id, expected_version, event_type, payload,
                action_id, principal, initiator=None) -> Event:
        ev = super()._append(stream_id, expected_version, event_type, payload,
                             action_id, principal, initiator)  # 任何拒绝在此抛出，未触文件
        rec = {"event_id": ev.event_id, "stream_id": ev.stream_id,
               "expected_version": ev.expected_version, "event_type": ev.event_type,
               "payload": dict(ev.payload), "transaction_time": ev.transaction_time,
               "action_id": ev.action_id, "principal": ev.principal,
               "initiator": initiator}
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
        return ev
