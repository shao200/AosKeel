"""tests/conformance/test_filestore.py —— FileStore 持久化参考实现守卫（INTEGRITY-3）。
判据对齐既有条款而非新造：重放一致（KS-1.2 八字段逐一）、拒绝不落盘
（KS-1.3 fail-closed；版本冲突口径 KS-1.4/VER-3）、直写陷阱在持久实现上
同样必拒且文件零字节变化（INV-1/VER-28）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.pipeline import Kernel
from kernel.session import SessionChannel
from kernel.store import EventStore, VersionConflict
from kernel.filestore import FileStore
from kernel.errors import DirectWriteForbidden, StoreRejection
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _kernel(store) -> Kernel:
    return Kernel(store, SessionChannel(), compile_all())
def _submit(k, cid="C-1") -> None:
    # 非创建型动作须先有权威投影：注册事件是实体存在的唯一来源（P-16）。
    if not any(ev.payload.get("contract_id") == cid
               for ev in k.store.streams.get("domain:ContractAggregate", [])):
        k.submit("RegisterContract", {"contract_id": cid, "amount": 500000},
                 "alice", roles=("contract_steward",))
    k.submit("ApproveContract", dict(PARAMS, contract_id=cid), "alice",
             roles=("contract_steward",))
def test_replay_rebuilds_eight_field_events(tmp_path):
    p = tmp_path / "events.jsonl"
    k = _kernel(FileStore(p))
    _submit(k)
    _submit(k, "C-2")                        # 不同实体：T24 效果后同实体重复 approve 应被语义拒绝
    rebuilt = FileStore(p)                     # "新进程"：只信文件
    for stream in rebuilt.streams:
        for a, b in zip(k.store.streams[stream], rebuilt.streams[stream]):
            assert a == b                      # 八字段逐一相等（含 payload 只读快照）
    assert rebuilt._next_id == k.store._next_id
def test_rejected_writes_never_reach_file(tmp_path):
    p = tmp_path / "events.jsonl"
    k = _kernel(FileStore(p))
    _submit(k)
    before = p.read_text(encoding="utf-8")
    s = k.store
    with pytest.raises(VersionConflict):       # 过期版本：拒绝在落盘之前
        s.commit("ApproveContract", "domain:ContractAggregate", 0,
                 "ApproveContract@1", dict(valid_time="2026-01-01T00:00:00+00:00"), "alice")
    with pytest.raises(DirectWriteForbidden):  # 直写陷阱：持久实现同样必拒
        s.write_raw(stream_id="domain:ContractAggregate")
    with pytest.raises(Exception):             # 未知能力：UnknownAction 亦不落盘
        s.commit("NotACapability", "domain:X", 9, "X@1", {}, "alice")
    assert p.read_text(encoding="utf-8") == before
def test_filestore_is_a_dropin_of_eventstore(tmp_path):
    """协议核对：FileStore 是 EventStore 的替换件，不新增任何写面。"""
    s = FileStore(tmp_path / "e.jsonl")
    assert isinstance(s, EventStore)
    for banned in ("update", "delete", "rewrite", "truncate", "clear", "pop"):
        assert not hasattr(s, banned)
    _submit(_kernel(s))
    assert s.path.exists() and s.path.read_text(encoding="utf-8").endswith("\n")


def test_persist_failure_rolls_back_memory_and_audit(tmp_path):
    """落盘失败必须回滚内存视图/事件号/appended 审计；修复存储后重试无空洞或谎账。"""
    p = tmp_path / "events.jsonl"
    k = _kernel(FileStore(p))
    _submit(k)                                    # 已持久化 2 条（register + approve）
    stream = "domain:ContractAggregate"
    mem_events = len(k.store.streams[stream])
    next_id = k.store._next_id
    appended = sum(1 for r in k.store.audit if r.get("kind") == "appended")
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    k.store.path = blocked                        # 模拟落盘不可写
    with pytest.raises(StoreRejection, match="PERSIST-FAIL"):
        _submit(k, "C-2")
    assert len(k.store.streams[stream]) == mem_events          # 内存追加已回滚
    assert k.store._next_id == next_id                         # 事件号已回滚
    assert sum(1 for r in k.store.audit if r.get("kind") == "appended") == appended
    assert k.store.audit[-1]["kind"] == "structurally-rejected"  # 恰一条拒绝审计
    k.store.path = p                              # 修复存储后重试
    _submit(k, "C-2")
    reg_c2 = [e for e in k.store.streams[stream]
              if e.event_type.startswith("RegisterContract")
              and e.payload.get("contract_id") == "C-2"]
    assert reg_c2 and reg_c2[0].event_id == next_id, "重试不得出现事件号空洞"
    assert FileStore(p)._next_id == k.store._next_id, "文件与内存必须重新一致"


def test_replay_repairs_trailing_partial_record(tmp_path):
    """崩溃窗口：write 与 fsync 之间被杀 → 文件尾半行可修复，前序事件完整保留。"""
    p = tmp_path / "events.jsonl"
    k = _kernel(FileStore(p))
    _submit(k)
    good = p.read_text(encoding="utf-8")
    p.write_text(good + '{"event_id": 99, "stream_id": "dom', encoding="utf-8")
    rebuilt = FileStore(p)                     # 新进程：重放时修复尾部半行
    assert len(rebuilt.streams["domain:ContractAggregate"]) == 2
    assert p.read_text(encoding="utf-8") == good            # 半行已截断
    _submit(_kernel(rebuilt), "C-2")                        # 修复后可继续追加
    assert p.read_text(encoding="utf-8").endswith("\n")


def test_replay_refuses_mid_file_corruption(tmp_path):
    """中段损坏不是崩溃窗口 → fail-closed 拒绝加载，绝不跳过坏行继续跑。"""
    p = tmp_path / "events.jsonl"
    k = _kernel(FileStore(p))
    _submit(k)
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text(lines[0] + "\n{broken}\n" + lines[1] + "\n", encoding="utf-8")
    with pytest.raises(StoreRejection, match="EVENT-LOG-CORRUPT"):
        FileStore(p)


def test_second_process_is_refused_by_store_lock(tmp_path):
    """单写进程模型是运行时事实：第二个进程打开同一日志即拒绝（STORE-LOCKED）。"""
    import subprocess
    p = tmp_path / "events.jsonl"
    holder = FileStore(p)
    code = ("import sys;"
            f"sys.path.insert(0, r'{ROOT}');sys.path.insert(0, r'{ROOT / 'src'}');"
            "from kernel.filestore import FileStore;"
            f"FileStore(r'{p}')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode != 0 and "STORE-LOCKED" in (r.stderr or "")
    holder.close()
