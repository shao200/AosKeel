#!/usr/bin/env python3
"""tools/doc_metrics.py —— 文档口径的单一权威源（P2 修补）。
README / 指南 / 白皮书 / RELEASE-MANIFEST 中的"CLI ×N、布线 N 条"不再手抄：
命令面从 src/cli/main.py 的分派分支派生，布线数从 config/verification.yaml
经 tools/wiring.scan() 派生。test_doc_consistency 锁住文档与本模块一致。
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import wiring

def stats() -> dict:
    src = (ROOT / "src/cli/main.py").read_text(encoding="utf-8")
    top = sorted(set(re.findall(r'^\s+if cmd == "([a-z0-9-]+)"', src, re.M)))
    sub = sorted(set(re.findall(r'rest\[0\] == "([a-z0-9-]+)"', src)))
    ready, missing, unwired = wiring.scan()
    paths = len(set(p for _, p in ready))
    config = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    integrity = len(re.findall(r'^\s*-\s*\{ id: INTEGRITY-', config, re.M))
    return {"cli_top": len(top), "cli_sub": len(sub),
            "cli_total": len(top) + len(sub),
            "wiring": paths, "executable": paths - len(missing),
            "missing": len(missing), "unwired": len(unwired),
            "integrity": integrity,
            "top_commands": top, "sub_commands": sub}

def cli_clause() -> str:
    s = stats()
    return f"CLI {s['cli_total']} 命令面（{s['cli_top']} 顶层 + {s['cli_sub']} 子命令）"

def wiring_clause() -> str:
    s = stats()
    return (f"{s['wiring']} 条布线（可执行 {s['executable']} / 缺失 {s['missing']} / "
            f"〔强〕未布线 {s['unwired']}）")

def canonical_line() -> str:
    return f"{cli_clause()}；{wiring_clause()}"

if __name__ == "__main__":
    print(json.dumps(stats(), ensure_ascii=False, indent=2))
    print(canonical_line())
