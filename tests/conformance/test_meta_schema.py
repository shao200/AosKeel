"""tests/conformance/test_meta_schema.py —— 元 schema 声明化回归。

判据：九类声明的骨架要求来自 spec/meta/declaration-schema.yaml（可审查声明），
缺字段 / 类型错 / 元 schema 自身缺失都在注册期失败，而非静默放行。
专用语义校验仍由原 validate_* 承担，本测试确认二者并存不互相覆盖。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel import registration as reg

NINE = {"objects", "links", "actions", "contexts", "aggregates",
        "invariants", "mappings", "processes", "governance"}

def _copy_spec(tmp_path) -> Path:
    dst = tmp_path / "spec"
    for p in reg.SPEC_DIR.rglob("*.yaml"):
        q = dst / p.relative_to(reg.SPEC_DIR)
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(p.read_bytes())
    return dst

def _point_to(monkeypatch, spec: Path):
    monkeypatch.setattr(reg, "SPEC_DIR", spec)
    monkeypatch.setattr(reg, "META_SCHEMA", spec / "meta/declaration-schema.yaml")

def test_meta_schema_declares_nine_classes():
    meta = reg._load_yaml(reg.META_SCHEMA)
    assert meta["meta_schema"] == "AOS-declaration-schema"
    assert set(meta["classes"]) == NINE

def test_real_declarations_satisfy_meta_schema():
    meta = reg._load_yaml(reg.META_SCHEMA)
    assert reg.validate_meta_schema(meta, reg.SPEC_DIR) == []

def test_register_pipeline_still_reconciles():
    generated = reg.run_pipeline()
    assert {"RegisterContract", "ApproveContract", "VoidContract"} <= {
        a["id"] for a in generated["write_actions"]}

def test_missing_required_field_is_refused(tmp_path, monkeypatch):
    spec = _copy_spec(tmp_path)
    p = spec / "ontology/objects/Contract.object.yaml"
    p.write_text(p.read_text(encoding="utf-8").replace("object_type: Contract\n", ""),
                 encoding="utf-8")
    _point_to(monkeypatch, spec)
    failures = reg._validate_spec()
    assert any("META-REQUIRED-MISSING" in f and "object_type" in f for f in failures)

def test_type_mismatch_is_refused(tmp_path, monkeypatch):
    spec = _copy_spec(tmp_path)
    p = spec / "aggregates/ContractAggregate.aggregate.yaml"
    text = p.read_text(encoding="utf-8").replace(
        "evaluation_budget: 100000", 'evaluation_budget: "100000"')
    p.write_text(text, encoding="utf-8")
    _point_to(monkeypatch, spec)
    failures = reg._validate_spec()
    assert any("META-TYPE-MISMATCH" in f and "evaluation_budget" in f for f in failures)

def test_meta_schema_itself_missing_is_refused(tmp_path, monkeypatch):
    spec = _copy_spec(tmp_path)
    monkeypatch.setattr(reg, "META_SCHEMA", spec / "meta/gone.yaml")
    failures = reg._validate_meta_schema()
    assert any("META-SCHEMA-MISSING" in f for f in failures)

def test_specialized_validation_is_not_replaced(tmp_path, monkeypatch):
    """骨架合规不等于语义合规：LinkPattern 三项校验仍在。"""
    spec = _copy_spec(tmp_path)
    p = spec / "ontology/links/same_as.link.yaml"
    text = p.read_text(encoding="utf-8").replace("attributes_empty: true", "attributes_empty: false")
    p.write_text(text, encoding="utf-8")
    _point_to(monkeypatch, spec)
    failures = reg._validate_spec()
    assert any("LINK-PATTERN" in f for f in failures)   # 专用语义校验未被骨架校验取代
