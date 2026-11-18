"""守卫本轮新增的四项能力不漂移：LLM 样例 / 心智模型图 / OWL 单向导出 / 英文旁挂概览。

共同底线：这些全是信息性/工具性增量，不扩大冻结正典的哈希覆盖域，也不写入
声明摘要域（spec/**/*.yaml）。v2.1.0 依据 GOV-3 提案 SPEC-2026-001 增附录 R/S，
v2.1.1 依 SPEC-2026-002 做内容勘误；当前哈希已重新登记；本文件用可证伪断言锁住
"覆盖域不变 + 旧登记行逐字保留"。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools import hash_spec as hs  # noqa: E402


def test_canonical_digest_unchanged_by_new_docs():
    """新增文档/样例/工具不得进入正典哈希覆盖域；现行文本已按 GOV-3 登记。"""
    registry = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    assert hs.canonical_digest() in registry          # 当前正典已登记（AOS-ART-003）
    assert any(l.startswith("| AOS-ART-001 |") and "e6884aed" in l
               for l in registry.splitlines())        # 封存基线逐字保留（append-only P-15）
    assert hs.CANONICAL_FILES == ["docs/aos-spec.md", "docs/SPEC-FINGERPRINT.md"]


def test_declaration_digest_unchanged():
    """样例与旁挂件不得写入 spec/ 声明域。"""
    assert hs.declaration_digest().startswith("91ffe5a1")
    assert all("samples" not in str(p) and "owl" not in str(p)
               for p in hs.declaration_files())


def test_english_overview_is_non_normative():
    txt = (ROOT / "docs/aos-spec.en-overview.md").read_text(encoding="utf-8")
    low = txt.lower()
    assert "non-normative" in low or "not the specification" in low
    assert "sha256" in txt.lower()                    # 指向唯一正典的现行登记哈希
    assert "outside" in low and "hash coverage" in low
    assert "wins" in low                           # 冲突时中文正典为准
    # 不得声称自己是规范或翻译件
    assert "is the specification" not in low


def test_both_readmes_carry_mental_model_and_overview_link():
    en = (ROOT / "README.md").read_text(encoding="utf-8")
    zh = (ROOT / "docs/README.zh-CN.md").read_text(encoding="utf-8")
    for txt, link in ((en, "aos-spec.en-overview.md"), (zh, "aos-spec.en-overview.md")):
        assert "```mermaid" in txt
        assert "ActionType" in txt
        assert link in txt


def test_llm_sample_contract_in_place():
    d = ROOT / "docs/samples/llm"
    for f in ("README.md", "llm_extractor.py", "llm_material.txt",
              "gate_rejection_demo.py", "run_demo.py"):
        assert (d / f).exists(), f"缺 LLM 样例文件 {f}"
    adp = (d / "llm_extractor.py").read_text(encoding="utf-8")
    assert "objects" in adp and "object_type" in adp   # stdout YAML objects[] 契约
    demo = (d / "gate_rejection_demo.py").read_text(encoding="utf-8")
    assert "DirectWriteForbidden" in demo and "structurally-rejected" in demo


def test_owl_export_is_one_way_and_draft_only():
    txt = (ROOT / "tools/owl_export.py").read_text(encoding="utf-8")
    assert "owl:Class" in txt and "owl:ObjectProperty" in txt
    low = txt.lower()
    assert "one-way" in low and "non-bridge" in low
    assert "data-drafts" in txt                     # 草案区，非声明域
    assert "limits" in txt


def test_gate_rejection_demo_runs(tmp_path):
    """反例可执行：直写被拒 + 留 structurally-rejected 审计。"""
    import subprocess
    p = subprocess.run([sys.executable, str(ROOT / "docs/samples/llm/gate_rejection_demo.py")],
                       cwd=str(ROOT), capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "REFUSED: INV-1" in p.stdout
    assert "GATE-DEMO: PASS" in p.stdout
