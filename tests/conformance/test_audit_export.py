"""tests/conformance/test_audit_export.py —— 统一审计导出守卫（INTEGRITY-7）。
判据：三本台账（store.audit / interpreter_audit / 决策流）合成一条链式 JSONL，
audit_id 逐条串接（prev=GENESIS 起）——改动任何一条，链校验机械可查；
导出是**只读派生件**：MUST NOT 改写任何源账本；持久证据可从事件日志重放
重建且链号确定（同文件两次导出 = 同字节）。
"""
import sys
from pathlib import Path
import json
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.filestore import FileStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.registration import compile_all
from tools import audit_export
STEWARD = dict(principal="svc", roles=("contract_steward",))
def _scenario(store) -> Kernel:
    k = Kernel(store, SessionChannel(), compile_all())
    k.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000}, **STEWARD)
    k.submit("ApproveContract", {"contract_id": "C-1"}, "alice",
             roles=("contract_steward",))
    srec = k.session.append("alice", {"intent": "review"})
    k.record_decision("proj-1", "2026-11-01T00:00:00+00:00", srec["ts"], "alice")
    try:
        k.store.write_raw(stream_id="x")            # 直写陷阱：拒绝也要进台账
    except Exception:
        pass
    return k
def test_unified_ledger_chains_and_covers_sources(tmp_path):
    k = _scenario(FileStore(tmp_path / "events.jsonl"))
    recs = audit_export.unified(k.store, k.interpreter_audit)
    sources = {r["source"] for r in recs}
    assert {"store-audit", "interpreter", "decision"} <= sources
    assert audit_export.verify_chain(recs) == []
    kinds = [r["record"].get("kind") for r in recs if r["source"] == "store-audit"]
    assert "structurally-rejected" in kinds          # 拒绝证据同链在案
def test_evaluation_audit_is_time_stamped():
    """KS-3.3 三元组之外的导出前置：每条评估记录带 tx/expression（合流排序键）。"""
    from kernel.store import EventStore
    from kernel.errors import ConditionalRejected
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    with pytest.raises(ConditionalRejected):       # 缺 status：条件失败也要留痕
        k.submit("ApproveContract", {"contract_id": "C-9"}, "alice",
                 roles=("contract_steward",))
    last = k.interpreter_audit[-1]
    assert last["expression"] and last["tx"]
def test_export_is_read_only(tmp_path):
    k = _scenario(FileStore(tmp_path / "events.jsonl"))
    before = (len(k.store.audit), len(k.interpreter_audit))
    audit_export.export(k.store, k.interpreter_audit, tmp_path / "audit.jsonl")
    assert (len(k.store.audit), len(k.interpreter_audit)) == before
def test_tampering_breaks_chain(tmp_path):
    k = _scenario(FileStore(tmp_path / "events.jsonl"))
    p = tmp_path / "audit.jsonl"
    audit_export.export(k.store, k.interpreter_audit, p)
    lines = p.read_text(encoding="utf-8").splitlines()
    rec = json.loads(lines[1])
    rec["record"]["action"] = "FakeContract"
    lines[1] = json.dumps(rec, sort_keys=True, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    issues = audit_export.verify_file(p)
    assert issues and issues[0].startswith(("AUDIT-ID-MISMATCH", "PREV-BREAK"))
def test_persistent_subset_deterministic_across_processes(tmp_path):
    """同一事件日志，两次独立重放导出 = 同字节：持久证据的链号可复核。"""
    ep = tmp_path / "events.jsonl"
    _scenario(FileStore(ep))
    a = audit_export.to_jsonl(audit_export.unified(FileStore(ep), ()))
    b = audit_export.to_jsonl(audit_export.unified(FileStore(ep), ()))
    assert a == b and a.count("\n") >= 4
def test_cli_export_and_refusals(tmp_path, capsys):
    ep = tmp_path / "events.jsonl"
    _scenario(FileStore(ep))
    out = tmp_path / "audit.jsonl"
    assert audit_export.main(["export", str(ep), "--out", str(out)]) == 0
    assert audit_export.verify_file(out) == []
    assert audit_export.main(["list"]) == 1
    assert "REFUSED" in capsys.readouterr().out
    assert audit_export.main(["export", str(tmp_path / "missing.jsonl")]) == 1
