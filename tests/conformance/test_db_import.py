"""tests/conformance/test_db_import.py —— aos import-db（数据库元结构 → 本体草案）。
判据：只读元结构不读业务数据；凭据不落盘（source 仅文件名）；产物走同一三段闸
（编译不过不落盘、晋升须 GOV-1 提案）；方言温和翻译逐条报告；翻译失败 fail-closed
（--skip-failed 显式跳过并大声报告）；无主键表拒绝（AX-4）；导入不触碰正典声明区。
"""
import sqlite3
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.db_import import import_db, ImportRefused
from kernel.registration import compile_all
MYSQL_DDL = """
-- 旧系统 mysql 导出（方言样例）
CREATE TABLE `biz_user` (
  `user_id` INT AUTO_INCREMENT PRIMARY KEY,
  `user_name` VARCHAR(64) NOT NULL COMMENT '用户名',
  `email` VARCHAR(128)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE `biz_order` (
  `order_id` BIGINT PRIMARY KEY,
  `user_id` INT NOT NULL,
  `amount` DECIMAL(12,2),
  `created_at` DATETIME,
  CONSTRAINT fk_order_user FOREIGN KEY (`user_id`) REFERENCES `biz_user`(`user_id`),
  KEY `idx_user` (`user_id`)
) ENGINE=InnoDB;
"""
@pytest.fixture()
def ddl_file(tmp_path):
    p = tmp_path / "legacy_dump.sql"
    p.write_text(MYSQL_DDL, encoding="utf-8")
    return p
@pytest.fixture(autouse=True)
def _cleanup():
    yield
    p = ROOT / "spec/drafts/draft-db-import.yaml"
    if p.exists():
        p.unlink()                                        # 测试不污染草案工作区
def _draft_yaml(name="db-import"):
    p = ROOT / f"spec/drafts/draft-{name}.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))
def test_ddl_import_creates_gate_passed_draft(ddl_file):
    r = import_db(ddl=ddl_file, name="db-import")
    assert set(r["objects"]) == {"BizUser", "BizOrder"}
    data = _draft_yaml()
    user = next(o for o in data["objects"] if o["object_type"] == "BizUser")
    assert user["identity"] == "user_id"
    assert user["properties"]["user_name"]["required"] is True
    assert user["properties"]["user_name"]["type"] == "string"
    order = next(o for o in data["objects"] if o["object_type"] == "BizOrder")
    assert order["properties"]["amount"]["type"] == "number"      # DECIMAL→number
    assert any(a["aggregate"] == "BizOrderAggregate" for a in data["aggregates"])
    # 方言翻译逐条报告（不静默）：ENGINE/COMMENT 翻译、索引行丢弃均有注记
    assert any("方言翻译" in n and "ENGINE" in n for n in r["notes"])
    assert any("丢弃索引行" in n and "idx_user" in n for n in r["notes"])
def test_candidate_links_from_fks(ddl_file):
    r = import_db(ddl=ddl_file, name="db-import")
    lk = [l for l in r["candidate_links"] if l["source"] == "BizOrder.user_id"]
    assert lk and lk[0]["target"] == "BizUser.user_id"
def test_credentials_never_in_draft(ddl_file):
    """凭据纪律：source 标签只有文件名；draft 全文无路径/连接串。"""
    r = import_db(ddl=ddl_file, name="db-import")
    assert r["source"] == "ddl:legacy_dump.sql"
    text = (ROOT / "spec/drafts/draft-db-import.yaml").read_text(encoding="utf-8")
    assert str(ddl_file.parent) not in text and "sqlite:///" not in text
def test_sqlite_dsn_import(tmp_path):
    db = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE dept (dept_id TEXT PRIMARY KEY, dept_name TEXT)")
    conn.commit(); conn.close()
    r = import_db(dsn=f"sqlite:///{db}", name="db-import")
    assert r["objects"] == ["Dept"] and r["source"] == "sqlite:legacy.sqlite"
def test_quoted_table_name_survives_introspection(tmp_path):
    """复盘修复回归：表名含引号——参数化 pragma 下内省不破坏语句。"""
    db = tmp_path / "odd.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute('CREATE TABLE "we\'ird" (row_id TEXT PRIMARY KEY, note TEXT)')
    conn.commit(); conn.close()
    r = import_db(dsn=f"sqlite:///{db}", name="db-import")
    assert r["objects"] == ["WeIrd"]
def test_no_pk_table_refused(tmp_path):
    db = tmp_path / "nopk.sqlite"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE messy (a TEXT, b TEXT)")   # 无主键
    conn.commit(); conn.close()
    with pytest.raises(ImportRefused, match="PK-MISSING"):
        import_db(dsn=f"sqlite:///{db}")
def test_dialect_failure_fail_closed(tmp_path, ddl_file):
    """翻译后仍失败的语句 → 拒绝（不静默跳过 = 不丢表）。"""
    bad = tmp_path / "bad.sql"
    bad.write_text(MYSQL_DDL + "\nCREATE TABLE broken (x TEXT,;\n", encoding="utf-8")
    with pytest.raises(ImportRefused, match="DDL-FAILED"):
        import_db(ddl=bad)
def test_skip_failed_loud(tmp_path):
    """--skip-failed：失败语句大声跳过，好表照常导入。"""
    bad = tmp_path / "bad.sql"
    bad.write_text(MYSQL_DDL + "\nCREATE TABLE broken (x TEXT,;\n", encoding="utf-8")
    r = import_db(ddl=bad, skip_failed=True)
    assert any("broken" in s for s in r["skipped"])
    assert set(r["objects"]) == {"BizUser", "BizOrder"}   # 好表不受牵连
def test_unknown_table_filter_refused(ddl_file):
    with pytest.raises(ImportRefused, match="TABLE-UNKNOWN"):
        import_db(ddl=ddl_file, only=("no_such_table",))
def test_unknown_driver_honest_refusal():
    """缺驱动如实拒绝，不假装支持（诚实边界）。"""
    with pytest.raises(ImportRefused, match="DRIVER-MISSING"):
        import_db(dsn="postgres://u:p@host/db")           # 模板环境无 psycopg2
def test_import_never_touches_canonical(ddl_file):
    """导入的是候选不是事实：正典声明区零变化（append-only 纪律）。"""
    before = {p.name: p.read_bytes()
              for p in sorted((ROOT / "spec/ontology/objects").glob("*.yaml"))}
    import_db(ddl=ddl_file, name="db-import")
    after = {p.name: p.read_bytes()
             for p in sorted((ROOT / "spec/ontology/objects").glob("*.yaml"))}
    assert after == before
    assert compile_all()                                  # 正典依旧全绿
def test_gate_refusal_no_draft_written(tmp_path):
    """三段闸：把关不过不落盘（无主键场景在闸前已拒；此处验证 DRAFT 闸）。"""
    bad = tmp_path / "nopk.sql"
    bad.write_text("CREATE TABLE nopk_tbl (x TEXT);\n", encoding="utf-8")
    with pytest.raises(ImportRefused):
        import_db(ddl=bad)
    assert not (ROOT / "spec/drafts/draft-db-import.yaml").exists() or \
        _draft_yaml()["objects"]
