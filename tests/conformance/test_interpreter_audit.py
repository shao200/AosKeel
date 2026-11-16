"""tests/conformance/test_interpreter_audit.py —— VER-11 / KS-3.3：
受限解释器每次评估留审计三元组（解释器版本，快照哈希，评估结果）。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.registration import compile_all
def _kernel():
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_audit_triple_recorded_per_evaluation():
    k = _kernel()
    before = len(k.interpreter_audit)
    try:                                                        # 条件可能拒绝——审计照记
        k.submit("ApproveContract", {"contract_id": "c-audit", "status": "pending"}, "svc", roles=("contract_steward",))
    except Exception:
        pass
    assert len(k.interpreter_audit) > before
    entry = k.interpreter_audit[-1]
    assert entry["interpreter_version"]                         # 版本身份（KS-3.3）
    assert len(entry["snapshot_hash"]) == 64                    # 快照哈希
    assert isinstance(entry["result"], bool)                    # 评估结果
def test_audit_deterministic_snapshot_hash():
    from interpreter.audit import record_evaluation
    env = {"snapshot": {"status": "pending"}, "principal": {"role": "svc"}}
    e1 = record_evaluation("snapshot.status == 'pending'", env, True)
    e2 = record_evaluation("snapshot.status == 'pending'", env, True)
    assert e1["snapshot_hash"] == e2["snapshot_hash"]             # 同输入同哈希（R2）
