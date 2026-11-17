#!/usr/bin/env python3
"""tools/shadow.py —— 影子对账（绞杀者模式第一块积木）：老库行 ↔ 新体系事件语义等价。
定位：CLI 能做的是**离线双跑** —— 同一业务事实，老系统按行存储，新体系按
事件流存储（经 import-data 创世事件灌入）。本模块逐行对账：
  1) 老行能否过新体系完整求值链（复用 Kernel.submit —— 求值链拒绝 = 差异）；
  2) 提交后事件 payload 的映射字段值与老行原值是否一致（语义搬运无损）；
  3) 动作声明的 effects（如 status=pending）是否如约落位。
真正的在线影子流量对比（新旧两个在线系统并行接流）属部署期动作 —— 本工具
是它的离线等价物，诚实披露边界。
纪律落点：只读源库（mode=ro）；凭据不落盘；对账报告是咨询产物（零写入正典），
差异清单应进 aos review 的人工裁决流程。
"""
from __future__ import annotations
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
from tools.data_import import _connect_ro, _required_params, PRINCIPAL
def shadow_reconcile(dsn: str, mapping_path: str, name: str | None = None) -> dict:
    """老库行 ↔ 创世事件语义对账。返回报告；不出制品文件（咨询产物）。"""
    mp = Path(mapping_path)
    if not mp.exists():
        raise FileNotFoundError(f"SHADOW-NOMAP: {mapping_path} 不存在")
    mapping = yaml.safe_load(mp.read_text(encoding="utf-8")) or {}
    entries = mapping.get("mappings") or []
    if not entries:
        raise ValueError("SHADOW-EMPTY-MAP: 映射无 mappings 条目")
    compiled = compile_all()
    kernel = Kernel(EventStore(), SessionChannel(), compiled)
    conn = _connect_ro(dsn)
    source = Path(dsn[len("sqlite:///"):]).name        # 只留文件名（凭据纪律）
    rows_total = matched_fields = mismatched = rejected = 0
    mismatches: list[dict] = []
    uncovered: list[str] = []
    try:
        for ent in entries:
            table, action = ent.get("table"), ent.get("action")
            if action not in compiled:
                raise ValueError(f"SHADOW-UNKNOWN-ACTION: {action} 未注册（INV-1）")
            act = compiled[action]
            roles = tuple(ent.get("roles") or [])
            colmap = ent.get("params") or {p: p for p in _required_params(act)}
            rows = conn.execute(f'SELECT rowid AS __rid__, * FROM "{table}"').fetchall()
            if not rows:
                raise ValueError(f"SHADOW-NO-TABLE: {table} 在源库中无数据")
            cols = [d[0] for d in conn.execute(f'SELECT * FROM "{table}" LIMIT 0').description]
            for row in rows:
                rec = dict(zip(cols, row[1:]))
                rows_total += 1
                params = {}
                missing_col = False
                for pname, col in colmap.items():
                    if col not in rec:
                        mismatches.append({"row": row[0], "kind": "mapping",
                                           "detail": f"列 {col} 不在源表"})
                        mismatched += 1
                        missing_col = True
                    else:
                        params[pname] = rec[col]
                if missing_col:
                    continue
                try:
                    ev = kernel.submit(action, params, PRINCIPAL, roles)
                except (StoreRejection, PermissionDenied, StructuralRejected,
                        ConditionalRejected, UnregisteredAction) as e:
                    rejected += 1
                    mismatches.append({"row": row[0], "kind": "rejection",
                                       "detail": str(e).splitlines()[0]})
                    continue
                payload = dict(ev.payload)
                # ② 语义搬运无损：映射字段值一致
                for pname, col in colmap.items():
                    if payload.get(pname) == rec[col]:
                        matched_fields += 1
                    else:
                        mismatched += 1
                        mismatches.append({"row": row[0], "kind": "field",
                                           "field": pname,
                                           "expected": rec[col],
                                           "actual": payload.get(pname)})
                # ③ 声明效果落位
                for k, v in (act.effects or {}).items():
                    if payload.get(k) == v:
                        matched_fields += 1
                    else:
                        mismatched += 1
                        mismatches.append({"row": row[0], "kind": "effect",
                                           "field": k, "expected": v,
                                           "actual": payload.get(k)})
                # 覆盖度：源行未被任何映射引用的列（对账盲区，如实披露）
                used = set(colmap.values())
                for c in cols:
                    if c not in used and f"{table}.{c}" not in uncovered:
                        uncovered.append(f"{table}.{c}")
    finally:
        conn.close()
    verdict = "MATCHED" if mismatched == 0 and rejected == 0 else "DIVERGED"
    return {"verdict": verdict, "source": f"sqlite:{source}", "rows": rows_total,
            "matched_fields": matched_fields, "mismatched": mismatched,
            "rejected": rejected, "mismatches": mismatches,
            "uncovered_columns": uncovered}
