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
from tools import codegen as cg

def test_metrics_derived_from_source():
    s = dm.stats()
    assert s["top_commands"] and s["sub_commands"]
    assert s["cli_total"] == s["cli_top"] + s["cli_sub"]
    assert s["wiring"] == s["executable"] + s["missing"]
    assert s["missing"] == 0                       # 布线缺失即 fail-closed
    assert dm.cli_clause() in dm.canonical_line()
    assert dm.wiring_clause() in dm.canonical_line()


def test_suite_size_metrics_derived_from_tests_dir():
    """测试套件规模（文件数 / def test_ 函数数）从 tests/ 派生，杜绝手抄漂移。

    pytest 实际收集数含参数化展开增量，与函数数单位不同——第二条断言只锁
    "收集数 ≥ 函数数"的大小关系，不做跨单位换算。
    """
    s = dm.stats()
    assert s["test_files"] >= 1 and s["test_fns"] >= s["test_files"]
    collected = dm.pytest_collected()
    assert collected >= s["test_files"]
    assert collected >= s["test_fns"]

def test_documents_follow_authoritative_counts():
    s = dm.stats()
    n, w = s["cli_total"], s["wiring"]
    collected = dm.pytest_collected()
    skeleton_files = len(cg.generate()["files"])
    expected = {
        "README.md": [f"{n} commands ({s['cli_top']} top-level + {s['cli_sub']} subcommands)"],
        "docs/README.md": [f"**{s['test_files']} test files / {s['test_fns']} `def test_` functions**",
                           f"pytest collects {collected} cases"],
        "docs/README.zh-CN.md": [f"命令面 {n}（{s['cli_top']} 顶层 + {s['cli_sub']} 子命令）",
                                 f"CLI {n} 命令面",
                                 f"{n} 命令面 = {s['cli_top']} 顶层 + {s['cli_sub']} 子命令"],
        "docs/guide/05-reference.md": [f"CLI {n} 命令面",
                                       f"{s['integrity']} 条 INTEGRITY 回归守卫",
                                       f"选中 {w} / 可执行 {w} / 缺失 {s['missing']}",
                                       "三关四道"],
        "docs/guide/04-tutorial.md": [f"选中 {w} 项，可执行 {w}",
                                      f"{w} 条布线路径",
                                      f"骨架字节级零漂移 · {skeleton_files} 文件"],
        "docs/WHITEPAPER.md": [f"{w} 条布线"],
        "docs/STRATEGY.md": [f"{w} 条布线（可执行 {w} / 缺失 {s['missing']}）",
                             f"{n} 个命令面",
                             f"{s['test_files']} 个测试文件 / {s['test_fns']} 个测试函数"],
        "docs/STRATEGY.en.md": [f"{w} wired paths ({w} executable / {s['missing']} missing)",
                                f"{n} command surfaces",
                                f"{s['test_files']} test files / {s['test_fns']} test functions"],
        "dist/RELEASE-MANIFEST.json": [f"{w} 条布线路径全部通过"],
    }
    for rel, needles in expected.items():
        txt = re.sub(r"\s+", " ", (ROOT / rel).read_text(encoding="utf-8"))
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
        "docs/guide/05-reference.md": ["命令 ×22", "命令 ×25", "22 命令分发", "22 条 INTEGRITY",
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


def test_canonical_v211_registration_and_informative_appendices():
    """v2.1.1 附录勘误与 GOV-3 登记联动；封存登记行逐字保留（P-15）。"""
    spec = (ROOT / "docs/aos-spec.md").read_text(encoding="utf-8")
    fp = (ROOT / "docs/SPEC-FINGERPRINT.md").read_text(encoding="utf-8")
    reg = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    assert "## 附录 R：理论谱系与立场（信息性）" in spec
    assert "## 附录 S：条件语言最小求值语义（信息性）" in spec
    assert "附录 ×9" in spec and "附录 ×9" in fp
    assert any(l.startswith("| AOS-ART-002 |") and "v2.1.0" in l
               for l in reg.splitlines())                       # 历史行逐字保留
    assert any(l.startswith("| AOS-ART-001 |") and "e6884aed" in l
               for l in reg.splitlines())
    assert any(l.startswith("| AOS-ART-003 |") and "v2.1.1" in l
               for l in reg.splitlines())                       # 历史行逐字保留（v2.2.0 后降级）
    for ref in ("SPEC-2026-001", "SPEC-2026-002", "SPEC-2026-003"):
        assert ref in reg
    for rel in ("config/capabilities.yaml", "config/verification.yaml"):
        assert "spec_ref: AOS-ART-004" in (ROOT / rel).read_text(encoding="utf-8")


def test_canonical_v220_errata_and_references():
    """v2.2.0 信息性勘误之二与 GOV-3 登记联动；v2.1.1 登记行降为历史（P-15）。"""
    spec = (ROOT / "docs/aos-spec.md").read_text(encoding="utf-8")
    reg = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    fp = (ROOT / "docs/SPEC-FINGERPRINT.md").read_text(encoding="utf-8")
    assert any(l.startswith("| AOS-ART-003 |") and "v2.1.1" in l
               for l in reg.splitlines())                       # 历史行逐字保留
    assert any(l.startswith("| AOS-ART-004 |") and "v2.2.0" in l
               for l in reg.splitlines())                       # 现行条目
    assert "v2.2.0 · Frozen" in spec and "v2.2.0 必备条款指纹清单" in fp
    # R.2 术语归属更正（N9）：histories/h@t 归 Hayes，state 归 Galton 一侧
    assert "histories" in spec and "h@t" in spec
    assert "不归给 Hayes" in spec
    # R.2 双时态补录的本体论承诺衔接：过去不可改写，只可增切片
    assert "新增一个时间部分" in spec and "只可增切片" in spec
    # S.4 步数上界更正（N8）：1 + steps(e1) + steps(e2)，结论不变；
    # 旧不等式只允许在更正标注中作为历史引用出现一次
    assert "1 + steps(e1) + steps(e2)" in spec
    assert spec.count("1 + max(steps(e1), steps(e2))") == 1
    assert "更正 v2.1.1 的 `≤ 1 + max(steps(e1), steps(e2))`" in spec
    # R.6 参考文献表（N9）：×12 条信息性登记 + 对应关系
    assert "### R.6 参考文献（信息性）" in spec
    for needle in ("Galton, A., Mizoguchi, R. (2009)", "Kowalski, R., Sergot, M. (1986)",
                   "Jones, A. J. I., Sergot, M. (1996)", "von Wright, G. H. (1951)",
                   "McCarthy, J., Hayes, P. J. (1969)"):
        assert needle in spec
    assert "The water falls but the waterfall does not fall" not in spec.split("### R.6")[0]  # 正文不误植术语
    assert "[06][07] → R.2" in spec


def test_appendix_errata_content_is_accurate():
    """勘误内容守卫：文献归属谱系正确、4D 立场实质认领、S 语义与实现对齐。"""
    spec = (ROOT / "docs/aos-spec.md").read_text(encoding="utf-8")
    # R-1/R-3：Borst 1997 + Studer 1998 归位，Gruber 1995 明确非定义修订
    assert "Borst（1997）" in spec and "Studer、Benjamins 与 Fensel（1998）" in spec
    assert "Guarino（1998）" in spec
    assert "并未以 formal / shared 修订 1993 定义" in spec
    # R-2：真正的 4D 承诺，非动词义"接续"
    assert "perdurantism（四维论）" in spec
    assert "个体是事件流的时间切片" in spec
    assert "valid_time` 上的函数" in spec
    assert "Galton" in spec
    # S-1/S-2：偏函数拒绝 + 无 now
    assert "env = (snapshot, principal)" in spec
    assert "偏函数（拒绝语义）" in spec
    assert "`InterpreterRejected`" in spec
    # S-3/S-4：真子集 + 范围限定 + 机器核对接线
    assert "真子集（最小核心片段）" in spec
    assert "该命题不覆盖完整 R10 profile" in spec
    assert "tests/conformance/test_boolean_profile_semantics.py" in spec
    # E-3：头部版本标识与谱系一致
    assert spec.lstrip().startswith("《AOS：基于本体论的 Agent 系统开发规范》")
    assert "v2.2.0 · Frozen" in spec