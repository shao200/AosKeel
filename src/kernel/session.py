"""src/kernel/session.py —— 会话事件流（KS-2.2 / KS-2.3 / INV-8 / VER-4 / VER-5）。
另一对象 = 另一存储（KS-2.2）：会话流与本体事件日志（EventStore）无任何共享结构 ——
物理分离，非本体状态，不参与任何投影的权威重建（projection.py 另有源级排除防御）。
仅追加"观测记录"，逐条强制主体归属（KS-2.3 / INV-8）；
提供 exists() 供决策双引用（KS-2.5）解析；read_all 仅限审计用途。

持久化（可选）：给 path 即成为 FileSession（JSONL 追加 + 重放），追加顺序是
"先落盘成功、再进内存"，因此落盘失败不会留下半条观察记录；进程级锁强制单写
（SESSION-LOCKED），重放只修复文件尾半行（崩溃窗口），中段损坏拒绝加载
（SESSION-REPLAY-CORRUPT）。重放只恢复观测日志本身，不改变"会话流不参与权威
投影重建"的红线（KS-2.2）。
"""
from __future__ import annotations
import datetime as dt
import json
import sys
import os                                                 # ADR-001: kernel 包 ROOT 外置注入
from pathlib import Path
ROOT = Path(os.environ.get("AOSKEEL_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import PrincipalRequired, SessionPersistFailed
from kernel.jsonl import process_lock_or_defer, read_records      # 尾部修复 + 单写进程锁
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class SessionChannel:
    def __init__(self, path=None):
        caps_path = ROOT / "config/capabilities.yaml"
        text = caps_path.read_text(encoding="utf-8") if caps_path.exists() else ""
        self._principal_required = "SessionAppend" in text   # 能力清单声明（KS-2.3）
        self._log: list[dict] = []          # 独立存储；与 EventStore.streams 无共享
        self.path = Path(path) if path is not None else None
        self._lock = None
        if self.path is not None:
            self._lock = process_lock_or_defer(self.path, SessionPersistFailed,
                                               "SESSION-LOCKED")
            self._replay()

    def close(self) -> None:
        """释放单写进程锁（内存通道无锁，调用为空操作）。"""
        if self._lock is not None:
            self._lock.release()

    def _replay(self) -> None:
        """只重放观察记录；与权威事件流物理分离（KS-2.2 / INV-8）。"""
        self._log.extend(read_records(self.path, SessionPersistFailed,
                                      "SESSION-REPLAY-CORRUPT"))

    def _persist(self, rec: dict) -> None:
        """先落盘成功、再进内存：失败即不产生内存半条记录（fail-closed）。"""
        if self._lock is None:                  # 构造时目录不存在：写入前补取锁
            self._lock = process_lock_or_defer(self.path, SessionPersistFailed,
                                               "SESSION-LOCKED")
        try:
            offset = self.path.stat().st_size
        except OSError:
            offset = 0
        try:
            with open(self.path, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            try:
                with open(self.path, "r+b") as f:     # 清掉可能已写出的半行
                    f.truncate(offset)
            except OSError:
                pass
            raise SessionPersistFailed(
                f"SESSION-PERSIST-FAIL: 观察记录落盘失败（{type(e).__name__}: {e}）"
                f"—— 未写入内存，修复存储后重试安全（KS-2.2 / INV-1）") from e

    def append(self, principal: str, payload: dict) -> dict:
        if self._principal_required and not principal:
            raise PrincipalRequired("SESSION-PRINCIPAL-REQUIRED（KS-2.3 / INV-8）")
        rec = {"principal": principal, "ts": _now(), **payload}
        if self.path is not None:
            self._persist(rec)              # 持久化失败 → 内存不留半条
        self._log.append(rec)               # append-only；无更新/删除路径
        return rec
    def exists(self, ref: str) -> bool:
        """决策双引用的会话半边可解析（KS-2.5 / VER-7）。"""
        return any(str(r.get("ts")) == str(ref) for r in self._log)
    def read_all(self) -> list[dict]:
        """仅限审计用途（KS-2.4：闭包禁读会话内容 —— 投影不得调用本方法）。"""
        return list(self._log)


class FileSession(SessionChannel):
    """JSONL 持久化观察通道（参考实现）：重启经重放恢复，追加语义与 FileStore 对齐。"""

    def __init__(self, path):
        super().__init__(path)
