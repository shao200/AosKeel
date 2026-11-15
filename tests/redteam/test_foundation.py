"""tests/redteam/test_foundation.py —— VER-28 备料（自动化部分）。
红队演练的运行时执行点（checklist VER-28 四项的人工执行与留档）之外，
以下断言在 CI 中持续机械可核对；缺一项即基座不完整。
"""
import dataclasses
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore, DirectWriteForbidden
from kernel.registration import load_caps
VT = "2026-01-01T00:00:00+00:00"
def test_write_raw_trap_rejects_and_audits():
    """对应 checklist item1：宿主代码直调存储写接口 → 必拒 + 审计留痕。"""
    store = EventStore()
    with pytest.raises(DirectWriteForbidden):
        store.write_raw(stream_id="domain:ContractAggregate", event_type="X@1")
    assert any(a["kind"] == "structurally-rejected" and a["attempt"] == "write_raw"
               for a in store.audit)                            # structurally-rejected 留档
def test_forbidden_segment_complete():
    """对应 checklist item3：forbidden 四项在位且与基座交叉核对（INV-6）。"""
    caps = load_caps()
    forbidden = set(caps["forbidden"])
    assert {"modify_foundation", "direct_event_write",
            "history_rewrite", "extinguish_override"} <= forbidden
    assert "audit_append_only" in caps["foundation"]             # 基座三项在位
    assert "perimeter_integrity" in caps["foundation"]
    assert "breakglass_resonant" in caps["foundation"]
def test_events_immutable_against_replay_tampering():
    """对应 checklist item2：已追加事件无更新路径 —— 对象级冻结断言。"""
    store = EventStore()
    store.commit("VoidContract", "domain:ContractAggregate", 0, "VoidContract@1",
                 {"valid_time": VT, "contract_id": "c-1"}, "svc")
    ev = store.streams["domain:ContractAggregate"][0]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ev.payload = {"tampered": True}
def test_extinguish_override_path_absent():
    """对应 checklist item4：类上不存在熄灭覆盖路径（INV-11）。"""
    from kernel.genesis import GenesisWindow
    assert not any(hasattr(GenesisWindow, m) for m in ("revive", "reopen", "override"))
