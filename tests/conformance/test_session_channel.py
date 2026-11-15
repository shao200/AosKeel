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
