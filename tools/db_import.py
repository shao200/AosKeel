#!/usr/bin/env python3
"""tools/db_import.py —— 数据库元结构 → 本体草案（旧系统迁移素材源，缺口 ③ 的兑现）。
边界（写死，不做开关）：
- 只读元结构（DDL/schema/外键），绝不读业务数据 —— 数据是世界状态，本体在 T03 边界外；
- 连接凭据不落盘：draft source 只记录 host/db 文件名（无用户名/密码/连接串）；
- 产物走同一三段闸（draft_from_decls）：编译不过不落盘、晋升须 GOV-1 提案 ——
  导入的是候选，不是事实；旧系统的规则是否成立由人裁决（aos draft promote）。
适配器：
- --dsn sqlite:///path/db.sqlite   stdlib 内省（PRAGMA）；
- --ddl file.sql                   旧系统导出的 CREATE TABLE 脚本装入内存 sqlite
                                   （免服务器导入）；方言差异温和翻译并逐条报告，
                                   翻译后仍失败的语句如实拒绝（不静默跳过 = 不丢表；
                                   --skip-failed 显式跳过并大声报告）；
- postgres/mysql                   需驱动，缺驱动如实拒绝（不假装支持）。
"""
from __future__ import annotations
import re
import sqlite3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.ontology_draft import draft_from_decls, DraftError
class ImportRefused(Exception):
    """素材导入拒绝（驱动缺失/方言失败/目标不可达）—— 一律如实报告。"""
DEFAULT_BUDGET = 10000          # 导入聚合的保守默认求值预算（人工审核可调，≤ R8 上限）
# 方言温和翻译：pg/mysql 转储 → sqlite 可执行。逐条记录（不静默）。
_TRANSLATIONS: list[tuple[str, str]] = [
    (r"\bAUTO_INCREMENT\s*=\s*\d+", ""),                        # 表选项
    (r"\bENGINE\s*=\s*\w+", ""), (r"\bDEFAULT\s+CHARSET\s*=\s*\w+", ""),
    (r"\bCOLLATE\s*=\s*\w+", ""), (r"\bCHARACTER\s+SET\s+\w+", ""),
    (r"\bAUTO_INCREMENT\b", ""), (r"\bUNSIGNED\b", ""),
    (r"\bSERIAL\b", "INTEGER"),
    (r"\bBIGINT\b", "INTEGER"), (r"\bSMALLINT\b", "INTEGER"),
    (r"\bTINYINT\b(?:\(\d+\))?", "INTEGER"), (r"\bINT\b", "INTEGER"),
    (r"\bDOUBLE\b(?:\s+PRECISION)?", "REAL"),
    (r"\bBOOLEAN\b", "INTEGER"),
    (r"\bENUM\s*\([^)]*\)", "TEXT"),
    (r"\bCOMMENT\s+'(?:[^']|'')*'", ""),
    (r"\bON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\(\d*\))?", ""),
    (r"\bUSING\s+(?:BTREE|HASH)\b", ""),
]
_DROP_LINE = re.compile(r"^\s*(KEY|INDEX|FULLTEXT|SPATIAL)\b")
_TYPE_MAP = {"INTEGER": "integer", "INT": "integer", "REAL": "number",
             "NUMERIC": "number", "DEC": "number", "NUMBER": "number",
             "FLOA": "number", "DOUB": "number", "TEXT": "string",
             "BLOB": "string", "CHAR": "string", "CLOB": "string"}
def _load_connection(dsn: str | None, ddl_path: Path | None,
                     skip_failed: bool = False) -> tuple[sqlite3.Connection, str, list, list]:
    """素材源 → (sqlite 连接, 脱敏 source 标签, 翻译注记, 跳过的失败语句)。
    凭据永不落盘。"""
    if ddl_path is not None:
        raw = Path(ddl_path).read_text(encoding="utf-8")
        return _memory_from_ddl(raw, Path(ddl_path).name, skip_failed)
    if dsn is None:
        raise ImportRefused("SOURCE-MISSING: 须提供 --dsn 或 --ddl 其一")
    if dsn.startswith("sqlite://"):
        db = dsn[len("sqlite:///"):] if dsn.startswith("sqlite:///") else dsn[len("sqlite://"):]
        p = Path(db)
        if not p.exists():
            raise ImportRefused(f"DB-NOT-FOUND: {p}（--dsn 只接受文件路径型 sqlite）")
        return sqlite3.connect(str(p)), "sqlite:" + p.name, [], []
    for drv, pkg in (("postgres://", "psycopg2"), ("postgresql://", "psycopg2"),
                     ("mysql://", "pymysql")):
        if dsn.startswith(drv):
            raise ImportRefused(f"DRIVER-MISSING: {pkg} 未安装 —— "
                                f"pip install {pkg}；或从旧系统导出 DDL 用 --ddl 免驱动导入")
    raise ImportRefused(f"DSN-UNKNOWN: 仅支持 sqlite:/// 与 --ddl（诚实边界："
                        "postgres/mysql 经驱动支持或 DDL 导出导入）")
def _memory_from_ddl(raw: str, filename: str,
                     skip_failed: bool = False) -> tuple[sqlite3.Connection, str, list, list]:
    """DDL 脚本 → 内存库。翻译逐条记录；失败语句 fail-closed 或大声跳过。"""
    text = re.sub(r"/\*.*?\*/", "", raw, flags=re.S)
    lines = [l for l in text.splitlines() if not l.strip().startswith("--")]
    notes, failed = [], []
    stmts, cur = [], []
    for l in lines:
        cur.append(l)
        if l.rstrip().endswith(";"):
            stmts.append("\n".join(cur)); cur = []
    if cur and any(cur):
        stmts.append("\n".join(cur))
    conn = sqlite3.connect(":memory:")
    for si, stmt in enumerate(stmts, 1):
        s = stmt.strip().rstrip(";").strip()
        if not s:
            continue
        t = s
        for pat, rep in _TRANSLATIONS:
            if re.search(pat, t):
                t = re.sub(pat, rep, t)
                notes.append(f"方言翻译: /{pat}/ → '{rep}'")
        kept = []
        for l in t.splitlines():
            if _DROP_LINE.match(l):
                notes.append(f"丢弃索引行: {l.strip()[:60]}"
                             "（sqlite 建表内不支持，索引请另行声明）")
                continue
            kept.append(l)
        t = "\n".join(kept)
        m = re.search(r"\s*,\s*(?:UNIQUE\s+)?(?:KEY|INDEX|FULLTEXT|SPATIAL)\s+"
                      r"[^\s(]+\s*\([^)]*\)", t)
        if m:                                           # 内联索引子句（单行 DDL 常见）
            t = re.sub(r"\s*,\s*(?:UNIQUE\s+)?(?:KEY|INDEX|FULLTEXT|SPATIAL)\s+"
                       r"[^\s(]+\s*\([^)]*\)", "", t)
            notes.append(f"丢弃内联索引子句: {m.group(0).strip()[:60]}"
                         "（索引请另行声明）")
        if re.search(r",\s*\)", t):                     # 丢行/方言留下的尾逗号
            t = re.sub(r",\s*\)", ")", t)
            notes.append("清理尾逗号（丢行后的悬空逗号）")
        try:
            conn.executescript(t + ";")
        except sqlite3.Error as e:
            failed.append(f"DDL-FAIL #{si}: {e} ｜ 语句首行: {s.splitlines()[0][:70]}")
    if failed and not skip_failed:
        raise ImportRefused("DDL-FAILED（fail-closed：翻译后仍不能执行 —— "
                            "修脚本或 --skip-failed 显式跳过并大声报告）:\n  "
                            + "\n  ".join(failed))
    return conn, "ddl:" + filename, notes, failed
def _introspect(conn: sqlite3.Connection, only: tuple[str, ...] = ()) -> dict:
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    if only:
        missing = [t for t in only if t not in tables]
        if missing:
            raise ImportRefused(f"TABLE-UNKNOWN: {missing} 不在元结构中（可用: {sorted(tables)}）")
        tables = [t for t in tables if t in only]
    schema = {}
    for t in sorted(tables):
        # table-valued pragma 参数化查询：表名含引号/特殊字符不再破坏语句
        cols = conn.execute("SELECT cid, name, type, \"notnull\", pk "
                            "FROM pragma_table_info(?)", (t,)).fetchall()
        schema[t] = {"columns": [(c[1], (c[2] or "TEXT").upper(), c[3], c[4]) for c in cols],
                     "fks": conn.execute("SELECT id, seq, \"table\", \"from\", \"to\" "
                                         "FROM pragma_foreign_key_list(?)", (t,)).fetchall()}
    return schema
def _pascal(name: str) -> str:
    """表名 → PascalCase 对象类型：按非字母数字切分（引号/美元符等一律作分隔符）。"""
    return "".join(p.capitalize() for p in re.split(r"[^0-9a-zA-Z]+", name) if p)
def _prop_type(sql_type: str) -> str:
    return next((v for k, v in _TYPE_MAP.items() if k in sql_type), "string")
def _decls_from_schema(schema: dict) -> dict:
    """元结构 → 本体草案声明（结构层候选：objects + aggregates + candidate_links）。
    聚合根启发：无外键指向的表 = 根候选（人工审核裁决边界）；行为层（actions）
    DLL 无法推断 —— 如实留空，不编造。"""
    objects, aggregates, links = [], [], []
    for t, meta in schema.items():
        pks = [c for c in meta["columns"] if c[3] > 0]
        if not pks:
            raise ImportRefused(f"PK-MISSING: 表 {t} 无主键 —— AX-4 个体须可辨识，"
                                "先补主键或排除该表（--tables）")
        o = {"object_type": _pascal(t),
             "identity": pks[0][0],
             "properties": {c[0]: {"type": _prop_type(c[1]),
                                   **({"required": True} if c[2] else {})}
                            for c in meta["columns"]}}
        objects.append(o)
        aggregates.append({"aggregate": f"{_pascal(t)}Aggregate",
                           "stream": f"domain:{_pascal(t)}Aggregate",
                           "evaluation_budget": DEFAULT_BUDGET})
        for fk in meta["fks"]:
            links.append({"link_type": f"{_pascal(fk[2])}Ref",
                          "source": f"{_pascal(t)}.{fk[3]}",
                          "target": f"{_pascal(fk[2])}.{fk[4] or 'id'}",
                          "note": "候选引用 —— 语义（聚合归属/引用/委托）由人工裁决"})
    return {"objects": objects, "aggregates": aggregates, "actions": [],
            "candidate_links": links}
def import_db(dsn: str | None = None, ddl: Path | None = None, name: str = "db-import",
              only: tuple[str, ...] = (), skip_failed: bool = False) -> dict:
    """素材源 → 三段闸 → spec/drafts/draft-<name>.yaml。永不触碰正典声明区。"""
    conn, source, notes, skipped = _load_connection(dsn, ddl, skip_failed)
    schema = _introspect(conn, only)
    decls = _decls_from_schema(schema)
    try:
        report = draft_from_decls(decls, name)         # 同一闸门：编译不过不落盘
    except DraftError as e:
        raise ImportRefused(f"DRAFT-GATE-REFUSED: {e}") from e
    if report["failures"]:
        raise ImportRefused("DRAFT-GATE-REFUSED: 草案未通过把关 —— "
                            + "; ".join(report["failures"]))
    return {"draft": report["draft"], "source": source,
            "objects": [o["object_type"] for o in decls["objects"]],
            "aggregates": [a["aggregate"] for a in decls["aggregates"]],
            "candidate_links": decls["candidate_links"],
            "notes": notes, "skipped": skipped}
