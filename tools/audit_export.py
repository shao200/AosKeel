#!/usr/bin/env python3
"""tools/audit_export.py —— 统一审计导出（治理面"审计与合规"的证据合流）。
运行时证据本来分三处：store.audit（追加/结构拒绝）、Kernel.interpreter_audit
（KS-3.3 评估三元组）、决策流事件（KS-2.5 三引用）。各说各话、无全局次序，
外部审计要手工拼。本工具把它们合成**一条链式台账**：
- 按 tx 时间稳定排序合流；
- audit_id = sha256(prev_id + 记录规范 JSON)，首条 prev = GENESIS——
  任何一条被改/删/插，下游链号全部对不上（verify_chain 机械可查）；
- 只读派生件：不改任何源账本，导出文件可删可重生成（真源仍是事件日志与账本）。
诚实边界：structurally-rejected 与解释器评估审计只随进程存在，进程外证据 =
事件日志（FileStore 重放可重建 appended 审计与决策引用）；导出时如实给数。
"""
from __future__ import annotations
import hashlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
GENESIS = "GENESIS"
def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
def _chain_id(prev: str, body: dict) -> str:
    return hashlib.sha256(f"{prev}|{_canonical(body)}".encode("utf-8")).hexdigest()
def unified(store, interpreter_audit=()) -> list[dict]:
    """三本台账 → 一条链。顺序 = (tx, 源内次序) 稳定排序。"""
    entries: list[tuple[str, int, dict]] = []
    for i, rec in enumerate(store.audit):
        entries.append((str(rec.get("tx", "")), i, {"source": "store-audit",
                                                    "record": rec}))
    for i, rec in enumerate(interpreter_audit):
        entries.append((str(rec.get("tx", "")), len(store.audit) + i,
                        {"source": "interpreter", "record": rec}))
    for i, ev in enumerate(store.streams.get("decision", [])):
        p = dict(ev.payload)
        entries.append((ev.transaction_time, 10**6 + i,
                        {"source": "decision", "record": {
                            "event_id": ev.event_id, "principal": ev.principal,
                            "projection_ref": p.get("projection_ref"),
                            "session_ref": p.get("session_ref"),
                            "decision_transaction_time":
                                p.get("transaction_time")}}))
    entries.sort(key=lambda e: (e[0], e[1]))
    prev = GENESIS
    out = []
    for seq, (_, _, body) in enumerate(entries):
        full = {"seq": seq, "prev": prev, **body}
        full["audit_id"] = _chain_id(prev, full)
        out.append(full)
        prev = full["audit_id"]
    return out
def to_jsonl(records: list[dict]) -> str:
    return "".join(json.dumps(r, sort_keys=True, ensure_ascii=False, default=str)
                   + "\n" for r in records)
def verify_chain(records: list[dict]) -> list[str]:
    """链自洽核对：返回问题清单（空 = 完好）。断链点即篡改/丢失位置。"""
    issues, prev = [], GENESIS
    for i, r in enumerate(records):
        body = {k: v for k, v in r.items() if k != "audit_id"}
        if r.get("seq") != i:
            issues.append(f"SEQ-BREAK @ {i}: seq={r.get('seq')}")
        if r.get("prev") != prev:
            issues.append(f"PREV-BREAK @ {i}: 前链号不接 —— 该条之前被改动")
            return issues                       # 断链后无法继续定位
        expect = _chain_id(prev, body)
        if r.get("audit_id") != expect:
            issues.append(f"AUDIT-ID-MISMATCH @ {i}: 记录内容与链号不符")
            return issues
        prev = r["audit_id"]
    return issues
def verify_file(path: str | Path) -> list[str]:
    text = Path(path).read_text(encoding="utf-8")
    recs = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    return verify_chain(recs)
def export(store, interpreter_audit, out_path: str | Path | None) -> list[dict]:
    """进程内导出 API（实例侧直接对活 Kernel 调用）；out_path=None 只回记录不落盘。"""
    records = unified(store, interpreter_audit)
    if out_path is not None:
        Path(out_path).write_bytes(to_jsonl(records).encode("utf-8"))
    return records
def main(argv: list[str]) -> int:
    usage = "用法: aos audit export <events.jsonl> [--out audit.jsonl]"
    if not argv or argv[0] != "export":
        print(f"REFUSED: audit 需要子命令 export —— {usage}")
        return 1
    rest = argv[1:]
    out = None
    if "--out" in rest:
        i = rest.index("--out")
        if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
            print(f"REFUSED: --out 缺值 —— {usage}")
            return 1
        out = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    positional = [a for a in rest if not a.startswith("--")]
    if not positional:
        print(f"REFUSED: 缺事件日志路径 —— {usage}")
        return 1
    events = Path(positional[0])
    if not events.exists():
        print(f"REFUSED: 事件日志不存在 {events} —— export 只从持久事件日志重建证据"
              f"（进程内台账用 tools.audit_export.export(store, interpreter_audit)）")
        return 1
    from kernel.filestore import FileStore
    records = unified(FileStore(events), ())
    if out is None:
        sys.stdout.write(to_jsonl(records))
        print(f"AUDIT-EXPORT: {len(records)} 条 → stdout（链首 prev={GENESIS}；"
              f"replay 不含进程内拒绝/评估审计）")
        return 0
    Path(out).write_bytes(to_jsonl(records).encode("utf-8"))
    issues = verify_file(out)
    if issues:
        print(f"CHAIN-BROKEN: {issues}")        # 写后即查：导出件自身必须链自洽
        return 1
    print(f"AUDIT-EXPORT: {len(records)} 条 → {out}（链式 audit_id 自洽；"
          f"派生件只读，重生成即可）")
    return 0
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
