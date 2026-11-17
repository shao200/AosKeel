#!/usr/bin/env python3
"""tools/shadow_online.py —— 在线影子流量对账协议层（绞杀者模式收官）。
定位（同 FileStore / extract 模式：协议在内核，执行在部署侧）：
- **探针是实例侧职责**：拦截新旧两个在线系统的并行流量、记录 (input, 双方
  output) 对为 NDJSON —— 这是部署组件，内核不绑定任何 HTTP 框架/代理；
- **对账协议在内核**：本模块消费探针记录（契约见 PROBE_CONTRACT），逐条对比
  新旧系统的状态与输出字段，产出差异报告 —— 报告应进 aos review 的人工裁决；
- **契约（PROBE_CONTRACT）**：每行一个 JSON 对象
  {action, input, legacy: {status, output}, modern: {status, output}}
  status ∈ 0|非0（成功/失败）；output 为业务结果（dict 或标量）；
- 纪律：坏行 fail-closed 大声列出（不静默跳过）；对账器只读（零写入正典）；
  对比语义与 aos shadow（离线）一致 —— 语义等价三项的在线版：状态等价 /
  输出等价 / 无丢失记录。
"""
from __future__ import annotations
import json
from pathlib import Path
PROBE_CONTRACT = ("{action, input, legacy: {status, output}, "
                  "modern: {status, output}}")
def reconcile_probes(ndjson_path: str) -> dict:
    """消费探针 NDJSON → 双跑对账报告。坏行 fail-closed 进 bad_lines。"""
    p = Path(ndjson_path)
    if not p.exists():
        raise FileNotFoundError(f"PROBE-NOFILE: {ndjson_path} 不存在")
    total = matched = diverged = 0
    mismatches: list[dict] = []
    bad_lines: list[str] = []
    for lineno, raw in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw)
            action = rec["action"]
            leg, mod = rec["legacy"], rec["modern"]
            leg_status, mod_status = leg["status"], mod["status"]
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            bad_lines.append(f"行 {lineno}: 契约不符（{PROBE_CONTRACT}）—— {e}")
            continue
        total += 1
        diffs: list[dict] = []
        if leg_status != mod_status:                      # ① 状态等价
            diffs.append({"kind": "status", "legacy": leg_status,
                          "modern": mod_status})
        leg_out, mod_out = leg.get("output"), mod.get("output")
        if isinstance(leg_out, dict) and isinstance(mod_out, dict):
            for k in sorted(set(leg_out) | set(mod_out)):  # ② 输出字段等价
                if leg_out.get(k) != mod_out.get(k):
                    diffs.append({"kind": "field", "field": k,
                                  "legacy": leg_out.get(k), "modern": mod_out.get(k)})
        elif leg_out != mod_out:                           # 标量输出直接比
            diffs.append({"kind": "output", "legacy": leg_out, "modern": mod_out})
        if diffs:
            diverged += 1
            mismatches.append({"line": lineno, "action": action, "diffs": diffs})
        else:
            matched += 1
    if bad_lines:                                         # ③ 无静默跳过
        raise ValueError("PROBE-BAD-LINES（fail-closed，零静默）:\n  "
                         + "\n  ".join(bad_lines[:20]))
    if total == 0:
        raise ValueError("PROBE-EMPTY: 探针记录为零（文件存在但无有效行）")
    return {"verdict": "MATCHED" if diverged == 0 else "DIVERGED",
            "total": total, "matched": matched, "diverged": diverged,
            "mismatches": mismatches}
