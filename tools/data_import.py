#!/usr/bin/env python3
"""tools/data_import.py —— 数据迁徙（"细胞移植"）：老库数据行 → 领域事件草案。
定位（与 db_import 的分工）：db_import 只读**元结构**推结构层草案；本模块读
**业务数据行**，把存量数据转换为领域事件草案（"创世事件"）——老数据不是
直接搬进新库，而是作为事件重放进新体系的求值链。
纪律落点：
- 映射只声明「老表列 → 动作参数」；事件形态（流/类型/效果）由正典动作声明
  决定 —— 单一真源，迁移器不发明事件；
- 每行必须通过 Kernel.submit 完整求值链（注册 INV-1 → 角色 INV-4 → 结构 →
  条件快照 → store 八字段）才被接受 —— 老数据违反新体系约束 = 拒绝（fail-closed），
  脏数据不得洗白进事件流；
- 只读源库（sqlite mode=ro）；连接串/凭据永不落盘；
- 产物是草案（data-drafts/*.ndjson），生产装载属部署期动作、须人工确认 ——
  与本体草案同一晋升哲学，零写入正典。
"""
from __future__ import annotations
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
from kernel.pipeline import Kernel
from kernel.registration import compile_all
from kernel.session import SessionChannel
from kernel.store import EventStore
from kernel.errors import StoreRejection, PermissionDenied, StructuralRejected, \
    ConditionalRejected, UnregisteredAction
DRAFT_DIR = ROOT / "data-drafts"
PRINCIPAL = "legacy-import"           # 迁移主体固定标识（审计可辨）
def _connect_ro(dsn: str) -> sqlite3.Connection:
    """sqlite:///path → file:path?mode=ro（只读强制；凭据不落盘的前提）。"""
    if not dsn.startswith("sqlite:///"):
        raise ValueError("DATA-IMPORT-DSN: 仅支持 sqlite:///（pg/mysql 经导出 DDL+CSV 入 sqlite）")
    path = dsn[len("sqlite:///"):]
    if not Path(path).exists():
        raise FileNotFoundError(f"DATA-IMPORT-NOFILE: {path} 不存在")
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)
def _required_params(act) -> list[str]:
    return [name for name, spec in (act.params or {}).items()
            if isinstance(spec, dict) and spec.get("required")]
def import_data(dsn: str, mapping_path: str, name: str | None = None,
                skip_failed: bool = False) -> dict:
    """老库数据 → 创世事件草案。逐行走完整求值链；失败 fail-closed。"""
    mp = Path(mapping_path)
    if not mp.exists():
        raise FileNotFoundError(f"DATA-IMPORT-NOMAP: {mapping_path} 不存在")
    mapping = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    entries = mapping.get("mappings") or []
    if not entries:
        raise ValueError("DATA-IMPORT-EMPTY-MAP: 映射无 mappings 条目")
    compiled = compile_all()
    kernel = Kernel(EventStore(), SessionChannel(), compiled)
    conn = _connect_ro(dsn)
    source = Path(dsn[len("sqlite:///"):]).name        # 只留文件名（凭据纪律）
    accepted: list[dict] = []
    failures: list[dict] = []
    tables_seen: set[str] = set()
    try:
        for ent in entries:
            table, action = ent.get("table"), ent.get("action")
            if action not in compiled:
                raise ValueError(f"DATA-IMPORT-UNKNOWN-ACTION: {action} 未注册 —— "
                                 "映射到未注册动作即未注册的写路径（INV-1）")
            act = compiled[action]
            roles = tuple(ent.get("roles") or [])
            colmap = ent.get("params") or {p: p for p in _required_params(act)}
            if not table or not colmap:
                raise ValueError(f"DATA-IMPORT-MAP-INCOMPLETE: {table or '?'} 缺 table/params")
            rows = conn.execute(f'SELECT rowid AS __rid__, * FROM "{table}"').fetchall()
            if not rows:
                raise ValueError(f"DATA-IMPORT-NO-TABLE: {table} 在源库中无数据")
            cols = [d[0] for d in conn.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
            tables_seen.add(table)
            for row in rows:
                rec = dict(zip(cols, row[1:]))          # __rid__ 仅用于失败定位
                params = {}
                for pname, col in colmap.items():
                    if col not in rec:
                        failures.append({"table": table, "row": row[0],
                                         "reason": f"列 {col} 不在源表中"})
                        break
                    params[pname] = rec[col]
                else:
                    try:
                        ev = kernel.submit(action, params, PRINCIPAL, roles)
                        accepted.append({"action": action, "stream": ev.stream_id,
                                         "params": params, "principal": PRINCIPAL,
                                         "roles": list(roles),
                                         "transaction_time": ev.transaction_time,
                                         "event_type": ev.event_type})
                    except (StoreRejection, PermissionDenied, StructuralRejected,
                            ConditionalRejected, UnregisteredAction, ValueError) as e:
                        failures.append({"table": table, "row": row[0],
                                         "reason": str(e).splitlines()[0]})
                        # 不中止循环：预检应跑完全部行，一次给出完整问题清单
    finally:
        conn.close()
    if failures and not skip_failed:
        detail = "; ".join(f"{f['table']}#{f['row']}: {f['reason']}" for f in failures)
        raise RuntimeError(
            f"DATA-IMPORT-REJECTED: {len(failures)} 行被求值链拒绝 —— {detail}"
            "（fail-closed：脏数据不落草案；显式 --skip-failed 继续）")
    if failures:
        print(f"[SKIPPED] {len(failures)} 行被求值链拒绝（大声列出，不静默）:")
        for f in failures:
            print(f"  [SKIPPED] {f['table']} 行 {f['row']}: {f['reason']}")
    name = name or "legacy-" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
    DRAFT_DIR.mkdir(exist_ok=True)
    out = DRAFT_DIR / f"{name}.events.ndjson"
    out.write_text("".join(json.dumps(e, ensure_ascii=False, default=str) + "\n"
                           for e in accepted), encoding="utf-8")
    return {"accepted": len(accepted), "rejected": len(failures),
            "tables": sorted(tables_seen), "source": f"sqlite:{source}",
            "draft": str(out.relative_to(ROOT))}
