"""src/kernel/filestore.py —— FileStore：append-only 事件日志的持久化参考实现。
单一 JSONL 文件；写路径只有"追加一行"（open 'a'，不 seek、不改写已确认事件；
仅在落盘失败回滚时把文件字节截回追加前偏移，清掉半行）。
重启经重放重建 streams —— append-only 语义在此是自证的，不靠约定。
继承 EventStore 的全部校验面（KS-1.3 结构 → 流规则 → 追加、版本冲突、
write_raw 直写陷阱、一次拒绝恰一条审计）；拒绝发生在落盘之前，文件不留半行。
诚实边界（参考实现，非生产件）：单写进程模型 —— 进程级文件锁拒绝第二个写入者
（STORE-LOCKED）；重放只修复文件尾半行（崩溃窗口），中段损坏拒绝加载
（EVENT-LOG-CORRUPT）。多进程并发需实例侧自行加锁或以数据库实现同协议；落盘失败
（权限/磁盘/IO）时回滚内存追加、事件号与 appended 审计，再留一条拒绝审计并抛出
StoreRejection —— 进程内视图不会与文件分叉；进程被强杀的崩溃窗口仍以
"启动时以文件为准重放"为恢复口径。
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from types import MappingProxyType
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import Event, EventStore   # noqa: E402
from kernel.errors import StoreRejection     # noqa: E402
from kernel.jsonl import process_lock, process_lock_or_defer, read_records  # noqa: E402
class FileStore(EventStore):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self._lock = process_lock_or_defer(self.path, StoreRejection, "STORE-LOCKED")
        self._replay()
    def close(self) -> None:
        """释放单写进程锁（同进程引用计数归零才真正解锁）。"""
        if self._lock is not None:
            self._lock.release()
    # ---------- 重放：文件是唯一持久真源 ----------
    def _replay(self) -> None:
        if not self.path.exists():
            return
        for rec in read_records(self.path, StoreRejection, "EVENT-LOG-CORRUPT"):
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
        if self._lock is None:                   # 构造时目录不存在：写入前补取锁
            self._lock = process_lock_or_defer(self.path, StoreRejection, "STORE-LOCKED")
        try:
            offset = self.path.stat().st_size        # 落盘失败时回到追加前字节位置
        except OSError:
            offset = 0
        ev = super()._append(stream_id, expected_version, event_type, payload,
                             action_id, principal, initiator)  # 任何拒绝在此抛出，未触文件
        rec = {"event_id": ev.event_id, "stream_id": ev.stream_id,
               "expected_version": ev.expected_version, "event_type": ev.event_type,
               "payload": dict(ev.payload), "transaction_time": ev.transaction_time,
               "action_id": ev.action_id, "principal": ev.principal,
               "initiator": initiator}
        try:
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())                 # 把"追加成功"变成可检测的持久事实
        except OSError as e:
            # 落盘失败必须回滚：否则进程内视图含一条文件里没有的事件，
            # appended 审计也会谎报（重试还会因内存版本号偏大而错乱）。
            self.streams[stream_id].pop()
            if not self.streams[stream_id]:
                del self.streams[stream_id]
            self._next_id -= 1
            self.audit.pop()                          # 撤销 super 记下的 appended
            try:
                with open(self.path, "r+b") as f:     # 清掉可能已写出的半行
                    f.truncate(offset)
            except OSError:
                pass                                  # 截断也失败：保持拒绝，不掩盖
            self._reject(f"persist: {stream_id} 落盘失败"
                         f"（{type(e).__name__}: {e}）—— 内存追加/事件号/审计已回滚",
                         StoreRejection(
                             f"PERSIST-FAIL: {event_type} 落盘失败，内存追加已回滚；"
                             f"修复存储后可安全重试（KS-1.3 / INV-1）：{e}"))
        return ev
