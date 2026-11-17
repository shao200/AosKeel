"""tests/conformance/test_shadow.py —— 影子对账（离线双跑/绞杀者第一块积木）。
判据：老库行 ↔ 新体系创世事件语义等价三项对账（求值链接受 / 映射字段无损 /
声明效果落位）；差异行进 mismatches（rejection/field/effect 分类）；源行未映射
列如实披露为对账盲区；凭据不落盘；正典零变化（咨询产物零写入）。
"""
import sqlite3
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.shadow import shadow_reconcile
@pytest.fixture()
def legacy_db(tmp_path):
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t_contract (contract_id TEXT, amount REAL, party_refs TEXT)")
    conn.execute("INSERT INTO t_contract VALUES ('C-001', 5000, 'U1|U2')")
    conn.execute("INSERT INTO t_contract VALUES ('C-002', 999999, 'U3')")
    conn.commit()
    yield f"sqlite:///{db}"
    conn.close()
def _mapping(tmp_path, params=None):
    m = tmp_path / "map.yaml"
    m.write_text(yaml.safe_dump({"mappings": [{"table": "t_contract",
        "action": "RegisterContract", "roles": ["contract_steward"],
        "params": params or {"contract_id": "contract_id", "amount": "amount"}}]},
        allow_unicode=True), encoding="utf-8")
    return str(m)
def test_matched_full_semantics(legacy_db, tmp_path):
    """正向：字段无损 + effects 落位 → MATCHED。"""
    r = shadow_reconcile(legacy_db, _mapping(tmp_path))
    assert r["verdict"] == "MATCHED" and r["rows"] == 2
    assert r["rejected"] == 0 and r["mismatched"] == 0
    assert r["matched_fields"] >= 4                    # 2 行 × (2 映射 + 1 effect)
    assert r["uncovered_columns"] == ["t_contract.party_refs"]   # 盲区如实披露
def test_dirty_row_diverges_with_rejection(tmp_path):
    """求值链拒绝的行 → DIVERGED + rejection 记录（新体系不容的旧事实）。"""
    db = tmp_path / "dirty.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t_contract (contract_id TEXT, amount REAL)")
    conn.execute("INSERT INTO t_contract VALUES ('C-OK', 5000)")
    conn.execute("INSERT INTO t_contract VALUES ('C-BAD', 10000000)")   # 超上限
    conn.commit(); conn.close()
    r = shadow_reconcile(f"sqlite:///{db}", _mapping(tmp_path))
    assert r["verdict"] == "DIVERGED" and r["rejected"] == 1
    assert any(m["kind"] == "rejection" and "条件校验" in m["detail"]
               for m in r["mismatches"])
def test_partial_mapping_divergence(tmp_path):
    """映射引用源表不存在的列 → mapping 类差异（对账不可继续该行）。"""
    db = tmp_path / "x.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t_contract (contract_id TEXT)")
    conn.execute("INSERT INTO t_contract VALUES ('C-1')")
    conn.commit(); conn.close()
    r = shadow_reconcile(f"sqlite:///{db}", _mapping(
        tmp_path, {"contract_id": "contract_id", "amount": "no_such_col"}))
    assert r["verdict"] == "DIVERGED"
    assert any(m["kind"] == "mapping" for m in r["mismatches"])
def test_unknown_action_refused(tmp_path):
    db = tmp_path / "x.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (a TEXT)"); conn.commit(); conn.close()
    m = tmp_path / "bad.yaml"
    m.write_text(yaml.safe_dump({"mappings": [{"table": "t", "action": "Nope",
                                               "params": {}}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="SHADOW-UNKNOWN-ACTION"):
        shadow_reconcile(f"sqlite:///{db}", str(m))
def test_readonly_and_canonical_untouched(legacy_db, tmp_path):
    """源库零改动 + 正典零变化（咨询产物零写入）。"""
    def snap():
        return {str(p.relative_to(ROOT)): len(p.read_bytes())
                for p in sorted((ROOT / "spec").rglob("*")) if p.is_file()}
    before, before_rows = snap(), sqlite3.connect(
        legacy_db[len("sqlite:///"):]).execute(
        "SELECT count(*) FROM t_contract").fetchone()[0]
    r = shadow_reconcile(legacy_db, _mapping(tmp_path))
    assert snap() == before and r["verdict"] == "MATCHED"
    assert sqlite3.connect(legacy_db[len("sqlite:///"):]).execute(
        "SELECT count(*) FROM t_contract").fetchone()[0] == before_rows
    assert "sqlite:///" not in str(r)                  # 凭据不落任何报告
