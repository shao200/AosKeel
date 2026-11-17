"""tests/conformance/test_semantic_extract.py —— 语义提取契约层。
判据：参考提取器（确定性规则）与自定义适配器产物**都过同一三段闸**（闸门与
来源无关）；origin 来源标注在案；置信度如实标注（文档候选一律 low）；纯中文
标题大声跳过不静默；适配器崩溃/坏 schema/无候选 fail-closed 零落盘；产物只进
spec/drafts/（测试自清理，正典零变化）。
P2 隔离：输入样例全部落在 pytest 的 tmp_path，不再写 tools/ 源码树、不再靠
unlink 清理 —— 批量删除被拦截时不会在仓库里留下 `_tmp_*` 垃圾。
"""
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.semantic_extract import extract, BUILTIN
PY_SAMPLE = "class Customer:\n    customer_id: str\n    name: str\n"
DOC_SAMPLE = "# Order Management\n\n## Customer Profile\n\n## 客户档案\n"
ADAPTER_OK = ("import sys, yaml\n"
              "yaml.safe_dump({'objects': [{'object_type': 'LedgerEntry', "
              "'identity': 'entry_id', 'properties': {'amount': 'string'}}]}, sys.stdout)\n")
@pytest.fixture()
def drafts_cleanup():
    """记录 spec/ 快照；落盘的 draft 文件测试后清理（产物只进 drafts/）。"""
    made: list[Path] = []
    yield made
    for p in made:
        p.unlink(missing_ok=True)
def _snap():
    return {str(p.relative_to(ROOT)): len(p.read_bytes())
            for p in sorted((ROOT / "spec").rglob("*")) if p.is_file()}
def test_builtin_code_extractor_gated(drafts_cleanup, tmp_path):
    """源码样例 → object 候选过闸落草案；origin/置信度在案；行为层不编造。"""
    made = drafts_cleanup
    src = tmp_path / "_tmp_extract_sample.py"
    src.write_text(PY_SAMPLE, encoding="utf-8")
    r = extract(str(src), "sem-sample")
    made.append(ROOT / "spec/drafts" / "draft-sem-sample.yaml")
    assert "draft" in r and (ROOT / "spec/drafts" / "draft-sem-sample.yaml").exists()
    assert r["extractor"] == BUILTIN
    assert r["decls"]["origin"]["source_file"] == "_tmp_extract_sample.py"
    assert "晋升须 GOV-1" in r["decls"]["origin"]["note"]
    assert r["confidence"]["Customer"] == "medium"            # id 字段 → medium
    assert {o["object_type"] for o in r["decls"]["objects"]} == {"Customer"}
    assert r["decls"]["actions"] == []                        # 行为层如实留空
    assert all(o["aggregate"] == o["stream"]
               for o in r["decls"]["aggregates"])             # 聚合候选配套
def test_builtin_doc_extractor_skips_chinese_loudly(drafts_cleanup, tmp_path):
    """英文标题成候选；纯中文标题大声跳过（命名须人工，不静默）；文档一律 low。"""
    made = drafts_cleanup
    src = tmp_path / "_tmp_extract_doc.md"
    src.write_text(DOC_SAMPLE, encoding="utf-8")
    r = extract(str(src), "sem-doc")
    made.append(ROOT / "spec/drafts" / "draft-sem-doc.yaml")
    types = {o["object_type"] for o in r["decls"]["objects"]}
    assert types == {"OrderManagement", "CustomerProfile"}
    assert any("SKIP-NON-ASCII-TITLE" in n and "客户档案" in n for n in r["notes"])
    assert all(c == "low" for c in r["confidence"].values())
def test_custom_adapter_gated(drafts_cleanup, tmp_path):
    """自定义适配器（LLM 挂接点）产物过同一闸：schema 合法 → 落草案。"""
    made = drafts_cleanup
    script = tmp_path / "_tmp_adapter_ok.py"
    script.write_text(ADAPTER_OK, encoding="utf-8")
    src = tmp_path / "_tmp_material.txt"
    src.write_text("any material", encoding="utf-8")
    r = extract(str(src), "sem-adapter", extractor=str(script))
    made.append(ROOT / "spec/drafts" / "draft-sem-adapter.yaml")
    assert "draft" in r and r["extractor"] == "custom:_tmp_adapter_ok.py"
    assert r["decls"]["objects"][0]["object_type"] == "LedgerEntry"
def test_adapter_failures_fail_closed(drafts_cleanup, tmp_path):
    """适配器崩溃 / 坏 schema / 空候选 → 大声拒绝，零落盘。"""
    before = _snap()
    src = tmp_path / "_tmp_material2.txt"
    src.write_text("x", encoding="utf-8")
    crash = tmp_path / "_tmp_adapter_crash.py"
    crash.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    bad = tmp_path / "_tmp_adapter_bad.py"
    bad.write_text("import sys, yaml\nyaml.safe_dump({'objects': [{'foo': 1}]}, sys.stdout)\n",
                   encoding="utf-8")
    empty = tmp_path / "_tmp_adapter_empty.py"
    empty.write_text("import sys, yaml\nyaml.safe_dump({'objects': []}, sys.stdout)\n",
                     encoding="utf-8")
    with pytest.raises(ValueError, match="EXTRACTOR-FAILED"):
        extract(str(src), "x1", extractor=str(crash))
    with pytest.raises(ValueError, match="EXTRACTOR-BAD-SCHEMA"):
        extract(str(src), "x2", extractor=str(bad))
    with pytest.raises(ValueError, match="EXTRACT-EMPTY"):
        extract(str(src), "x3", extractor=str(empty))
    assert _snap() == before                                   # 零落盘
def test_canonical_only_via_drafts(drafts_cleanup, tmp_path):
    """产物只进 spec/drafts/ —— 正典声明区（spec 其余部分）字节零变化。"""
    made = drafts_cleanup
    def canon():
        return {k: v for k, v in _snap().items()
                if "/drafts/" not in k and "\\drafts\\" not in k}
    before = canon()
    src = tmp_path / "_tmp_extract_sample2.py"
    src.write_text(PY_SAMPLE, encoding="utf-8")
    r = extract(str(src), "sem-canon")
    made.append(ROOT / "spec/drafts" / "draft-sem-canon.yaml")
    assert "draft" in r
    assert canon() == before                                   # 正典区零变化
