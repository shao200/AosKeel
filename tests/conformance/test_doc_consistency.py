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


def test_readme_section_skeleton_is_mirrored():
    """§§1–9 + 附录 A 的顶层骨架必须逐槽对应——不再只靠人工约定。

    中文 §7 的标题被仓库口径守卫固定以 `## CLI ` 开头，不可直译；因此本测试
    按「显式槽号」比对（英文 `7.` / 中文「对应英文 §7」/ 双方「附录 A」），
    而不是按标题文本比对。任一版新增、删除或错序顶层章节都会失败。
    """
    expected = list(range(1, 10)) + ["A"]

    def heads_and_slots(rel):
        txt = (ROOT / rel).read_text(encoding="utf-8")
        heads = re.findall(r"^##\s+(.+)$", txt, re.M)
        slots = []
        for h in heads:
            m = re.match(r"^(\d+)\.", h)
            if m:
                slots.append(int(m.group(1)))
                continue
            m = re.search(r"对应英文\s*§\s*(\d+)", h)
            if m:
                slots.append(int(m.group(1)))
                continue
            if h.startswith("Appendix A") or h.startswith("附录 A"):
                slots.append("A")
        return heads, slots

    for rel in ("README.md", "docs/README.zh-CN.md"):
        heads, slots = heads_and_slots(rel)
        assert len(heads) == len(expected), (
            f"{rel} 顶层章节数漂移：期望 {len(expected)}，实得 {len(heads)}：{heads}"
        )
        assert slots == expected, f"{rel} 章节骨架未镜像：期望 {expected}，实得 {slots}"


def test_readme_editions_cross_link_and_mirror_shared_facts():
    """两版互链、§1–§9 对偶声明与双分发增量子节必须同时存在。"""
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    zh = (ROOT / "docs/README.zh-CN.md").read_text(encoding="utf-8")
    assert "[简体中文](docs/README.zh-CN.md)" in en
    assert "[English (default)](../README.md)" in zh
    assert "ADR-001" in en and "ADR-001" in zh
    assert "### Two distribution artifacts" in en
    assert "### 双分发工件" in zh
    assert "docs/adr/ADR-001-dual-distribution.md" in en
    assert "adr/ADR-001-dual-distribution.md" in zh


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


def test_declaration_execution_boundaries_disclosed():
    """无运行时消费者的声明字段必须在两版 §9 同时披露，且 invariants.gate 保持 false。"""
    anchors = {
        "README.md": [
            "invariants: {gate: false}", "kernel/detector.py", "kernel/dryrun.py",
            "Agent 权限 = 角色 × 所在上下文", "Frozen bytes cover",
        ],
        "docs/README.zh-CN.md": [
            "invariants: {gate: false}", "kernel/detector.py", "kernel/dryrun.py",
            "Agent 权限 = 角色 × 所在上下文", "冻结字节仅",
        ],
    }
    for rel, needles in anchors.items():
        txt = (ROOT / rel).read_text(encoding="utf-8")
        for needle in needles:
            assert needle in txt, f"{rel} §9 缺执行边界披露 {needle!r}"
    cfg = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    assert re.search(r"invariants:\s*\{\s*gate:\s*false\s*\}", cfg), (
        "invariants.gate 必须为 false：没有 tests/invariants 执行点时不得声称已布线")
