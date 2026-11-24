"""tests/conformance/test_session_channel.py —— VER-5 / KS-2.2 / KS-2.3：
会话通道物理分离（另一对象=另一存储）；会话事件强制主体；会话引用可解析。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.session import SessionChannel
from kernel.errors import PrincipalRequired
def test_session_append_requires_principal():
    ch = SessionChannel()
    with pytest.raises(PrincipalRequired):
        ch.append("", {"text": "无主体会话写入（KS-2.2）"})
def test_session_is_physically_separate_storage():
    """会话不进 EventStore.streams（另一对象=另一存储，KS-2.2）。"""
    from kernel.store import EventStore
    ch, store = SessionChannel(), EventStore()
    ev = ch.append("agent-1", {"text": "hello"})
    assert ch.exists(ev["ts"])
    assert all("session" not in s for s in store.streams)       # 物理分离
    assert ev["principal"] == "agent-1"
def test_session_ref_resolvable():
    ch = SessionChannel()
    ev = ch.append("agent-1", {"text": "x"})
    assert ch.exists(ev["ts"]) and not ch.exists("sess-nope")


def test_file_session_replays_after_restart(tmp_path):
    """观察通道持久化：重启重放恢复同一日志，且仍不进入权威存储（KS-2.2）。"""
    from kernel.session import FileSession
    p = tmp_path / "session.jsonl"
    rec = FileSession(p).append(
        "agent-1", {"kind": "initiative.invitation", "entity": "C-1"})
    again = FileSession(p)                                  # 重启：以文件为准重放
    assert again.read_all() == [rec]
    assert again.exists(rec["ts"])


def test_file_session_persist_failure_leaves_no_half_record(tmp_path):
    """落盘失败 → SessionPersistFailed 且内存不留半条（先落盘后入内存，fail-closed）。"""
    from kernel.session import FileSession
    from kernel.errors import SessionPersistFailed
    ch = FileSession(tmp_path / "missing-dir" / "session.jsonl")   # 父目录不存在
    with pytest.raises(SessionPersistFailed, match="SESSION-PERSIST-FAIL"):
        ch.append("agent-1", {"kind": "initiative.invitation"})
    assert ch.read_all() == [], "落盘失败不得留下内存半条观察记录"
