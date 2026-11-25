"""src/kernel/jsonl.py —— JSONL 持久化辅助：崩溃尾部修复 + 单写进程锁。

两个 File* 参考实现（权威事件日志的 FileStore、观察通道的 FileSession）共用：
  * read_records：逐行解析；只修复"文件尾半行"（进程在 write 与 fsync 之间被杀的
    崩溃窗口），中段损坏一律 fail-closed。修复会截断半行，或为合法但缺换行的末条
    补一个换行，避免下次追加与它粘连；修复动作写入 stderr 留痕。
  * process_lock：同一路径在进程内可重入（引用计数），跨进程第二持有者立即拒绝 ——
    把"单写进程模型"从文档承诺变成运行时事实（fail-closed，不静默降级）。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_LOCKS: dict[str, list] = {}          # resolved path -> [file handle, refcount]


def read_records(path: Path, error_cls, code: str) -> list[dict]:
    """读取 JSONL 记录；仅可修复文件尾半行，中段损坏抛 error_cls。"""
    if not path.exists():
        return []
    raw = path.read_bytes()
    if not raw:
        return []
    parts = raw.split(b"\n")
    tail = parts.pop()                 # 以 \n 结尾时为 b""
    records: list[dict] = []
    for idx, chunk in enumerate(parts, 1):
        if not chunk.strip():
            continue
        try:
            records.append(json.loads(chunk.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise error_cls(
                f"{code}: 第 {idx} 行损坏（非文件尾半行）—— 拒绝加载：{e}") from e
    if not tail.strip():
        return records
    offset = len(raw) - len(tail)
    try:
        rec = json.loads(tail.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        with open(path, "r+b") as f:
            f.truncate(offset)
        print(f"REPLAY-REPAIRED: {path} 尾部半行已截断（崩溃窗口）", file=sys.stderr)
        return records
    records.append(rec)
    with open(path, "ab") as f:        # 合法末条缺尾换行：补上，避免下次追加粘连
        f.write(b"\n")
    print(f"REPLAY-REPAIRED: {path} 已补尾换行", file=sys.stderr)
    return records


class _Lock:
    def __init__(self, key: str):
        self.key = key

    def release(self) -> None:
        held = _LOCKS.get(self.key)
        if held is None:
            return
        held[1] -= 1
        if held[1] > 0:
            return
        fh = held.pop(0)
        del _LOCKS[self.key]
        try:
            if os.name == "nt":
                import msvcrt
                fh.seek(0)
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            fh.close()


def process_lock_or_defer(path: Path, error_cls, code: str):
    """目录尚不存在时推迟取锁：此时无数据可竞争，写路径会以持久化失败拒绝。

    这样"构造成功、落在 append 处失败"的既有语义不被改写；目录一旦存在，
    后续写入会重新取锁，仍保持单写进程约束。
    """
    try:
        return process_lock(path, error_cls, code)
    except error_cls:
        if not path.parent.exists():
            return None
        raise


def process_lock(path: Path, error_cls, code: str) -> _Lock:
    """按数据文件路径取进程级独占锁；同进程可重入，跨进程失败即拒。"""
    key = str(path.resolve())
    held = _LOCKS.get(key)
    if held is not None:
        held[1] += 1
        return _Lock(key)
    lock_path = path.with_name(path.name + ".lock")
    try:
        fh = open(lock_path, "a+b")
    except OSError as e:
        raise error_cls(f"{code}: 无法创建锁文件 {lock_path}（{e}）") from e
    try:
        if os.name == "nt":
            import msvcrt
            fh.seek(0, os.SEEK_END)
            if fh.tell() == 0:
                fh.write(b"\0")
                fh.flush()
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        fh.close()
        raise error_cls(
            f"{code}: {path} 已被其他进程持有（单写进程模型，fail-closed）") from e
    _LOCKS[key] = [fh, 1]
    return _Lock(key)
