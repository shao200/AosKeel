#!/usr/bin/env python3
"""tools/doc_metrics.py —— 文档口径的单一权威源（P2 修补）。
README / 指南 / 白皮书 / RELEASE-MANIFEST 中的"CLI ×N、布线 N 条"不再手抄：
命令面从 src/cli/main.py 的分派分支派生，布线数从 config/verification.yaml
经 tools/wiring.scan() 派生。test_doc_consistency 锁住文档与本模块一致。
测试套件规模（文件数 / `def test_` 函数数）亦从 tests/ 派生；pytest 实际收集数
（含参数化）经 collect-only 子进程派出——三类数字在文档中一律不得手抄。
"""
from __future__ import annotations
import json, re, subprocess, sys
from pathlib import Path
from functools import lru_cache
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
    test_files = sorted(p for p in (ROOT / "tests").rglob("test_*.py"))
    test_fns = sum(
        len(re.findall(r"^\s*def test_", p.read_text(encoding="utf-8"), re.M))
        for p in test_files
    )
    return {"cli_top": len(top), "cli_sub": len(sub),
            "cli_total": len(top) + len(sub),
            "wiring": paths, "executable": paths - len(missing),
            "missing": len(missing), "unwired": len(unwired),
            "integrity": integrity,
            "test_files": len(test_files), "test_fns": test_fns,
            "top_commands": top, "sub_commands": sub}

@lru_cache(maxsize=1)
def pytest_collected() -> int:
    """pytest 实际收集的用例数（含参数化）——完整 node-id 解析派生。

    不用 `-q` 逐文件计数（其行末数字依赖终端列宽、易被截断丢掉尾行）。
    逐条 `tests/xxx.py::<node>` 累积，参数化展开成多条 node-id 天然计入。
    注意：结果 = 测试函数数 + 参数化展开增量，与 stats() 的 test_fns 二者单位不同，
    不得互相换算；文档中引用任一只手抄其值即触发守卫。
    """
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    combined = (r.stdout or "") + "\n" + (r.stderr or "")
    return len(re.findall(r"^\s*\S+\.py::\S+", combined, re.M))

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