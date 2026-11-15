"""tests/negative/test_forbidden.py —— forbidden × 负向测试（INV-11 / P-10 双射的 forbidden 半边）。
每个 forbidden 恰好一个用例。内核运行时骨架（store.py / genesis.py）就位后，
本套件为可执行真测试；更深层的运行时半边由 VER-28 红队演练执行并留档。
"""
import re
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from dataclasses import FrozenInstanceError
from kernel.store import EventStore, DirectWriteForbidden, StoreRejection
from kernel.genesis import GenesisWindow, GenesisExtinguished
CAPS = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8")

def _strip_docstring(src: str) -> str:
    return re.sub(r'""".*?"""', "", src, flags=re.S)

# P-10 双射映射表：forbidden 条目 → 本文件中的用例函数名
FORBIDDEN_TESTS = {
    "modify_foundation":  "test_no_modify_foundation",
    "direct_event_write": "test_no_direct_event_write",
    "history_rewrite":    "test_no_history_rewrite",
    "extinguish_override": "test_no_extinguish_override",
}

def test_no_modify_foundation():
    """modify_foundation：基座配置只读——注册期管线（固定段唯一合法读者）从不
    构造/写回 foundation 与 forbidden 段（P-5 单写者只辖生成段；INV-6）。"""
    src = _strip_docstring((ROOT / "src/kernel/registration.py").read_text(encoding="utf-8"))
    for seg in ("foundation", "forbidden"):
        assert f'"{seg}"' not in src and f"'{seg}'" not in src, \
            f"registration.py 不得出现对 {seg} 段的写引用（INV-6 / P-5）"

def test_no_direct_event_write():
    """direct_event_write：绕 Action 调存储写 → 必抛 + structurally-rejected 审计（INV-1）。"""
    store = EventStore()
    with pytest.raises(DirectWriteForbidden):
        store.write_raw(stream_id="domain:orders", event_type="Order@1", payload={})
    assert store.audit[-1]["kind"] == "structurally-rejected"
    assert all(not streams for streams in store.streams.values()), "直写不得产生任何事件"

def test_no_history_rewrite():
    """history_rewrite：已追加事件无更新路径 → append-only 断言（AX-3 / VER-28 item2）。"""
    store = EventStore()
    store.commit("RecordDecision", "decision", 0, "Decision@1",
                 {"valid_time": "2026-01-01T00:00:00+00:00",
                  "projection_ref": "proj-1", "session_ref": "sess-1"}, "steward")
    ev = store.streams["decision"][0]
    for banned in ("update", "delete", "rewrite", "truncate"):
        assert not hasattr(store, banned), f"存储层存在违禁路径: {banned}"
    with pytest.raises(FrozenInstanceError):
        ev.event_id = 999                      # 事件对象不可变
    with pytest.raises(TypeError):
        ev.payload["valid_time"] = "1999-01-01T00:00:00+00:00"   # payload 只读

def test_no_extinguish_override():
    """extinguish_override：创世谓词为假后无重启用路径 → 凭据重放必拒（KS-8.2）。"""
    w = GenesisWindow("APPT-001", ttl_seconds=3600)
    assert w.predicate() is True
    w.close_governance_cycle()                 # KS-8.4 治理闭环 → 熄灭
    assert w.predicate() is False
    for banned in ("revive", "reopen", "unextinguish", "reset"):
        assert not hasattr(w, banned), f"创世窗口存在违禁重启用路径: {banned}"
    with pytest.raises(GenesisExtinguished):
        w.reactivate(w.appointment_ref)        # 凭据重放必拒
    assert w.predicate() is False              # 永久为假
