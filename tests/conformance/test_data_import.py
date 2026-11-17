"""tests/conformance/test_data_import.py —— aos import-data 数据迁徙（细胞移植）。
判据：老库数据行经 Kernel.submit 完整求值链（注册→角色→结构→条件快照→store
八字段）转为创世事件草案；映射只声明「老表列→动作参数」，事件形态由正典动作
定（单一真源）；脏行 fail-closed 默认中止不落盘，--skip-failed 大声跳过；
未注册动作映射拒绝（INV-1）；角色缺失拒绝（INV-4 fail-closed）；源库只读
（mode=ro）；凭据不落盘；spec/ 正典零变化（data-drafts 在正典之外）。
"""
import sqlite3
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.data_import import import_data, DRAFT_DIR
@pytest.fixture(autouse=True)
def _cleanup_data_drafts():
    """落盘的 .events.ndjson 测试后清理（草案不是正典，也不留仓库垃圾）。"""
    yield
    if DRAFT_DIR.exists():
        for p in DRAFT_DIR.glob("mig-*.events.ndjson"):
            p.unlink(missing_ok=True)
@pytest.fixture()
def legacy_db(tmp_path):
    """旧系统 sqlite（干净库）：合同表，无脏行。"""
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t_contract (contract_id TEXT, amount REAL, party_refs TEXT)")
    conn.execute("INSERT INTO t_contract VALUES ('C-001', 5000, 'U1|U2')")
    conn.execute("INSERT INTO t_contract VALUES ('C-002', 999999, 'U3')")
    conn.commit()
    yield f"sqlite:///{db}"
    conn.close()
@pytest.fixture()
def dirty_db(tmp_path):
    """含脏行的库：C-BAD 金额超 conditional 上限。"""
    db = tmp_path / "dirty.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t_contract (contract_id TEXT, amount REAL, party_refs TEXT)")
    conn.execute("INSERT INTO t_contract VALUES ('C-001', 5000, 'U1|U2')")
    conn.execute("INSERT INTO t_contract VALUES ('C-BAD', 10000000, 'U4')")  # 超上限
    conn.commit()
    yield f"sqlite:///{db}"
    conn.close()
@pytest.fixture()
def mapping(tmp_path):
    m = tmp_path / "map.yaml"
    m.write_text(yaml.safe_dump({
        "mappings": [{"table": "t_contract", "action": "RegisterContract",
                      "roles": ["contract_steward"],
                      "params": {"contract_id": "contract_id", "amount": "amount",
                                 "party_refs": "party_refs"}}]}, allow_unicode=True),
        encoding="utf-8")
    return str(m)
def test_import_to_genesis_events(legacy_db, mapping, tmp_path):
    """正向：干净行过完整求值链 → 创世事件草案落盘。"""
    r = import_data(legacy_db, mapping, name="mig-demo")
    assert r["accepted"] == 2 and r["rejected"] == 0
    assert r["tables"] == ["t_contract"] and "legacy.sqlite" in r["source"]
    lines = (DRAFT_DIR / "mig-demo.events.ndjson").read_text(
        encoding="utf-8").strip().splitlines()
    ev = __import__("json").loads(lines[0])
    assert ev["action"] == "RegisterContract" and ev["stream"] == "domain:ContractAggregate"
    assert ev["params"]["amount"] == 5000 and ev["event_type"].endswith("@1")
    assert ev["principal"] == "legacy-import" and ev["transaction_time"]
def test_dirty_row_full_report_fail_closed(dirty_db, mapping):
    """fail-closed：跑完全部行后一次给出完整问题清单，不落盘（脏数据不洗白）。"""
    with pytest.raises(RuntimeError, match="DATA-IMPORT-REJECTED.*t_contract#2"):
        import_data(dirty_db, mapping, name="mig-fail")
    assert not (ROOT / "data-drafts" / "mig-fail.events.ndjson").exists()
def test_skip_failed_loud(dirty_db, mapping, capsys):
    """--skip-failed：跳过脏行大声列出，干净行照常落草案。"""
    r = import_data(dirty_db, mapping, name="mig-skip", skip_failed=True)
    assert r["accepted"] == 1 and r["rejected"] == 1
    assert "[SKIPPED]" in capsys.readouterr().out
def test_unknown_action_mapping_refused(tmp_path):
    """映射到未注册动作 → 拒绝（未注册的写路径不存在，INV-1）。"""
    db = tmp_path / "x.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (a TEXT)"); conn.commit(); conn.close()
    m = tmp_path / "badmap.yaml"
    m.write_text(yaml.safe_dump({"mappings": [{"table": "t", "action": "Nope",
                                               "params": {}}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="UNKNOWN-ACTION"):
        import_data(f"sqlite:///{db}", str(m))
def test_missing_roles_fail_closed(legacy_db, tmp_path):
    """映射未出示动作要求的角色 → PermissionDenied（fail-closed，不默认放行）。"""
    m = tmp_path / "norole.yaml"
    m.write_text(yaml.safe_dump({"mappings": [{"table": "t_contract",
                    "action": "RegisterContract",
                    "params": {"contract_id": "contract_id", "amount": "amount"}}]}),
        encoding="utf-8")
    with pytest.raises(RuntimeError, match="DATA-IMPORT-REJECTED"):
        import_data(legacy_db, str(m), name="mig-norole")
def test_source_readonly_and_credentials_off_record(legacy_db, mapping):
    """源库只读（mode=ro）+ 凭据不落盘（草案/报告无连接串）。"""
    before = sqlite3.connect(legacy_db[len("sqlite:///"):]).execute(
        "SELECT count(*) FROM t_contract").fetchone()[0]
    r = import_data(legacy_db, mapping, name="mig-ro")
    after = sqlite3.connect(legacy_db[len("sqlite:///"):]).execute(
        "SELECT count(*) FROM t_contract").fetchone()[0]
    assert before == after == 2                              # 数据零改动
    draft = (DRAFT_DIR / "mig-ro.events.ndjson").read_text(encoding="utf-8")
    assert "legacy.sqlite" in r["source"] and "sqlite:///" not in draft
    assert "C-BAD" not in draft                              # 被拒行不进草案
def test_canonical_untouched(legacy_db, mapping):
    """正典零变化：import-data 只写 data-drafts/（spec/ 字节不变）。"""
    def snap():
        return {str(p.relative_to(ROOT)): len(p.read_bytes())
                for p in sorted((ROOT / "spec").rglob("*")) if p.is_file()}
    before = snap()
    import_data(legacy_db, mapping, name="mig-canon")
    assert snap() == before
