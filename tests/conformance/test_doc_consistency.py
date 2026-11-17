"""tests/conformance/test_doc_consistency.py —— P2 口径单一权威源守卫。
文档中的 CLI 命令面、布线条数、INTEGRITY 守卫条数由 tools/doc_metrics.py
从源码与 verification.yaml 派生；本测试锁住消费端，杜绝手抄口径再次漂移。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import doc_metrics as dm

def test_metrics_derived_from_source():
    s = dm.stats()
    assert s["top_commands"] and s["sub_commands"]
    assert s["cli_total"] == s["cli_top"] + s["cli_sub"]
    assert s["wiring"] == s["executable"] + s["missing"]
    assert s["missing"] == 0                       # 布线缺失即 fail-closed
    assert dm.cli_clause() in dm.canonical_line()
    assert dm.wiring_clause() in dm.canonical_line()

def test_documents_follow_authoritative_counts():
    s = dm.stats()
    n, w = s["cli_total"], s["wiring"]
    expected = {
        "docs/README.zh-CN.md": [f"命令面 {n}（{s['cli_top']} 顶层 + {s['cli_sub']} 子命令）",
                                 f"CLI {n} 命令面"],
        "docs/guide/05-reference.md": [f"CLI {n} 命令面",
                                       f"{s['integrity']} 条 INTEGRITY 回归守卫",
                                       f"选中 {w} / 可执行 {w} / 缺失 {s['missing']}"],
        "docs/guide/04-tutorial.md": [f"选中 {w} 项，可执行 {w}",
                                      f"{w} 条布线路径"],
        "docs/WHITEPAPER.md": [f"{w} 条布线"],
        "docs/STRATEGY.md": [f"{w} 条布线（可执行 {w} / 缺失 {s['missing']}）",
                             f"{n} 个命令面"],
        "docs/STRATEGY.en.md": [f"{w} wired paths ({w} executable / {s['missing']} missing)",
                                f"{n} command surfaces"],
        "dist/RELEASE-MANIFEST.json": [f"{w} 条布线路径全部通过"],
    }
    for rel, needles in expected.items():
        txt = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in txt, f"{rel} 口径漂移：期望含 {needle!r}"

def test_no_stale_hand_copied_counts():
    """旧口径不得残留（随本轮修补一并清除）。"""
    stale = {
        "docs/README.zh-CN.md": ["×24", "×22", "×25", "22 条 INTEGRITY", "25 条 INTEGRITY",
                                 "27 条 INTEGRITY"],
        "docs/guide/05-reference.md": ["命令 ×22", "命令 ×25", "22 条 INTEGRITY",
                                       "25 条 INTEGRITY", "27 条 INTEGRITY", "选中 54",
                                       "选中 57", "选中 59"],
        "docs/guide/04-tutorial.md": ["选中 35 项", "选中 57 项", "选中 59 项",
                                      "28 条布线路径", "57 条布线路径", "59 条布线路径"],
        "docs/WHITEPAPER.md": ["49 条布线", "57 条布线", "59 条布线"],
        "docs/STRATEGY.md": ["47+ 条布线", "64 项全量绿灯", "22 个命令"],
        "docs/STRATEGY.en.md": ["47+ wired tests", "64-test all-green", "22 commands"],
        "dist/RELEASE-MANIFEST.json": ["52 条布线路径", "57 条布线路径", "59 条布线路径"],
    }
    for rel, needles in stale.items():
        txt = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle not in txt, f"{rel} 仍有旧口径 {needle!r}"
