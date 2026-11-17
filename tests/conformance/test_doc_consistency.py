"""tests/conformance/test_doc_consistency.py —— P2 口径单一权威源守卫。
文档中的 CLI 命令面、布线条数、INTEGRITY 守卫条数由 tools/doc_metrics.py
从源码与 verification.yaml 派生；本测试锁住消费端，杜绝手抄口径再次漂移。
"""
import sys
import re
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
        "README.md": [f"{n} commands ({s['cli_top']} top-level + {s['cli_sub']} subcommands)"],
        "docs/README.zh-CN.md": [f"命令面 {n}（{s['cli_top']} 顶层 + {s['cli_sub']} 子命令）",
                                 f"CLI {n} 命令面",
                                 f"{n} 命令面 = {s['cli_top']} 顶层 + {s['cli_sub']} 子命令"],
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

def test_readme_command_tables_cover_authoritative_commands():
    """README 速查表必须列全权威 26 命令面：任一命令条目被删即失败。

    这是"文档正确反映系统实际"的机械守卫——正文把 aos cq 当核心法律证，
    速查表却查不到它，正是本测试要杜绝的漂移。
    """
    s = dm.stats()
    authoritative = set(s["top_commands"]) | set(s["sub_commands"])
    # 每个文档里界定速查表片段的起止锚点
    sections = {
        "README.md": ("## 7. Command cheat sheet", "## 8."),
        "docs/README.zh-CN.md": ("## CLI ", "护栏一"),
    }
    for rel, (start, end) in sections.items():
        txt = (ROOT / rel).read_text(encoding="utf-8")
        seg = txt.split(start, 1)[1].split(end, 1)[0]
        # 只取表格行的首列命令 token，避免正文叙述里的同名词造成假阳性
        rows = [ln for ln in seg.splitlines() if ln.startswith("| `")]
        listed = set()
        for ln in rows:
            first = ln.split("|", 2)[1] if ln.count("|") >= 2 else ""
            for cmd in authoritative:
                if re.search(r"\b" + re.escape(cmd) + r"\b", first):
                    listed.add(cmd)
        missing = authoritative - listed
        assert not missing, f"{rel} 速查表缺命令面 {sorted(missing)}"


def test_no_stale_hand_copied_counts():
    """旧口径不得残留（随本轮修补一并清除）。"""
    stale = {
        "README.md": ["12 commands"],
        "docs/README.zh-CN.md": ["×24", "×22", "×25", "22 条 INTEGRITY", "25 条 INTEGRITY",
                                 "27 条 INTEGRITY", "（22 命令", "两者等价"],
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
