#!/usr/bin/env python3
"""tools/review.py —— 审核清单（入口层第 ③ 步）：待人工裁决项集中输出。
只读咨询，不做任何写操作：扫 profile 锚点现状 / drafts 草案（含候选引用）/
正典 actions 的治理授权对账，产出带编号的裁决清单 —— 每项附"下一步命令"。
纪律落点：
- 草案是候选不是事实：晋升须 GOV-1 提案（aos draft promote --proposal-ref）；
- 带角色的 action 若无治理背书：现在注册会被对账拒绝（fail-closed），审核前置提醒；
- L3 不变量不可自动定稿：由人在正典声明区手写，本清单只提醒缺口，不代写。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
from kernel.profile import resolve as profile_resolve
def _load_yaml_dir(d: Path) -> list[dict]:
    if not d.exists():
        return []
    return [yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            for p in sorted(d.glob("*.yaml"))]
def review_report(root: Path | None = None) -> dict:
    """扫现状 → 带编号裁决清单。Profile 结构性错误由调用方捕获（ProfileError）。"""
    root = root or ROOT
    spec_dir = root / "spec"
    prof = profile_resolve(root=root)
    items: list[dict] = []
    def add(category: str, subject: str, advise: str) -> None:
        items.append({"id": f"R-{len(items) + 1:02d}", "category": category,
                      "subject": subject, "advise": advise})
    # ① Profile 锚点现状（新项目的待声明 roadmap；已有项目 = 缺口）
    for f in prof["failures"]:
        add("profile-anchor", f, "补声明后 aos profile 复核；锚点缺失时 generate 拒绝")
    # ② 草案清单（候选 ≠ 事实：晋升须 GOV-1 提案；候选引用语义人工裁决）
    drafts = []
    for p in sorted((spec_dir / "drafts").glob("draft-*.yaml")):
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        n_obj = len(data.get("objects") or [])
        n_act = len(data.get("actions") or [])
        drafts.append({"path": str(p), "objects": n_obj, "actions": n_act,
                       "aggregates": len(data.get("aggregates") or [])})
        add("draft-promotion", f"{p.name}：{n_obj} 对象 / {n_act} 行为候选未晋升",
            "审核后 aos draft promote spec/drafts/… --proposal-ref SPEC-YYYY-NNN"
            "（GOV-1：CLI 只记录治理结果，不合成正当性）")
        for lk in data.get("candidate_links") or []:
            add("draft-link", f"{lk.get('source')} → {lk.get('target')}",
                "裁决引用语义（聚合归属/引用/委托）：改草案或在正典 links 声明")
    # ③ 治理授权对账（前置提醒 —— 注册时会被拒绝的对账项）
    gov_docs = _load_yaml_dir(spec_dir / "governance")
    gov_auth = {a for g in gov_docs
                for d in (g.get("duties") or []) for a in d.get("authorizes") or []}
    gov_pos = {d.get("position") for g in gov_docs
               for d in (g.get("duties") or [])}
    for a in _load_yaml_dir(spec_dir / "ontology/actions"):
        roles = (a.get("permissions") or {}).get("roles") or []
        name = a.get("action_type", "?")
        if name not in gov_auth:
            add("gov-missing", f"Action {name} 无治理授权",
                "补 spec/governance 职责项（authorizes）——注册时对账会拒绝（fail-closed）")
        unknown = [r for r in roles if r not in gov_pos]
        if unknown:
            add("gov-position", f"Action {name} 出示未声明岗位 {unknown}",
                "岗位须先在治理面声明（claims 只能投影声明角色）")
    return {"project": prof.get("project"), "depth": prof.get("depth"),
            "selected": len(prof["selected"]), "drafts": drafts,
            "items": items, "clean": not items}
def format_report(r: dict) -> str:
    """报告 → 文本（CLI 与 --out 共用）。"""
    L = [f"项目: {r['project']}（depth={r['depth']}，能力 {r['selected']} 项）"]
    if r["drafts"]:
        L.append("草案工作区:")
        for d in r["drafts"]:
            L.append(f"  {d['path']}（对象 {d['objects']} / 行为 {d['actions']} / "
                     f"聚合 {d['aggregates']}）")
    if r["items"]:
        L.append(f"待人工裁决 {len(r['items'])} 项:")
        for it in r["items"]:
            L.append(f"  [{it['id']}][{it['category']}] {it['subject']}")
            L.append(f"      ↳ {it['advise']}")
    else:
        L.append("无待裁决项 —— 流水线就绪：aos verify → aos generate")
    return "\n".join(L)
