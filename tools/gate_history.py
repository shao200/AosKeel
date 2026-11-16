#!/usr/bin/env python3
"""tools/gate_history.py —— 度量口径：闸门运行留档（治理面"度量与反馈"）。
verify / release 每次运行追加一条 JSONL 记录到 dist/gate-history.jsonl：
    {ts, command, result, gates: {关卡名: PASS|FAIL}}
它是派生证据件，不是真源：不参与任何判定、不进门禁哈希覆盖域——
只回答"跑了多少次、通过率多少、哪一关在漂"（反馈面的最低机械可答性）。
漂移口径：cryptographic（冻结文本被改，GOV-2.3）与 codegen（骨架漂移，KS-4.3）。
追加失败只 WARN 不阻断闸门本身——度量是记账，不是把关。
"""
from __future__ import annotations
import datetime as dt
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
HISTORY_PATH = ROOT / "dist" / "gate-history.jsonl"
DRIFT_GATES = {"cryptographic", "codegen"}
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def record(command: str, gates: dict[str, str]) -> None:
    result = "PASS" if gates and all(v == "PASS" for v in gates.values()) else "FAIL"
    row = {"ts": _now(), "command": command, "result": result, "gates": gates}
    try:
        HISTORY_PATH.parent.mkdir(exist_ok=True)
        with open(HISTORY_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError as e:
        print(f"WARN: gate-history 追加失败（{e}）—— 度量不阻断闸门")
def load() -> list[dict]:
    if not HISTORY_PATH.exists():
        return []
    return [json.loads(ln) for ln in
            HISTORY_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()]
def report() -> int:
    rows = load()
    if not rows:
        print("METRICS-EMPTY: 尚无 dist/gate-history.jsonl —— "
              "aos verify / aos release 运行后自动累计（度量口径 = 闸门事件流）")
        return 0
    total = len(rows)
    passed = sum(1 for r in rows if r["result"] == "PASS")
    print(f"METRICS: {total} 次闸门运行 ｜ 通过 {passed}（{passed / total:.0%}）"
          f" ｜ 记录 @ {HISTORY_PATH}")
    for cmd in sorted({r["command"] for r in rows}):
        sub = [r for r in rows if r["command"] == cmd]
        ok = sum(1 for r in sub if r["result"] == "PASS")
        print(f"  · {cmd}: {len(sub)} 次，通过 {ok}（{ok / len(sub):.0%}）")
    fail_counts: dict[str, int] = {}
    for r in rows:
        for g, v in r.get("gates", {}).items():
            if v == "FAIL":
                fail_counts[g] = fail_counts.get(g, 0) + 1
    drift = sum(n for g, n in fail_counts.items() if g in DRIFT_GATES)
    print("  各关失败: " + (", ".join(f"{g}={n}" for g, n in
                            sorted(fail_counts.items())) or "无"))
    print(f"  漂移计数（cryptographic+codegen 失败）: {drift}")
    streak = 0
    for r in reversed(rows):
        if r["result"] != "PASS":
            break
        streak += 1
    print(f"  当前连续通过: {streak} ｜ 最近一次: {rows[-1]['ts']} "
          f"{rows[-1]['command']} {rows[-1]['result']}")
    print("（派生证据件：不参与判定；删除后重新累计即可）")
    return 0
if __name__ == "__main__":
    sys.exit(report())
