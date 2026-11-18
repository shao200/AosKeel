#!/usr/bin/env python3
"""tools/ontology_draft.py —— 需求文本 → 本体草案（缺口 ① 的模板层兑现）。
三段闸门（人确认前不进正典声明区）：
 1. 解析     需求 DSL（对象/动作块）→ 声明草案。模板提供**确定性解析器**；
             LLM 起草器是实例侧 hook：产出同一 DSL/声明格式、过同一闸门
             （GOV-6：模板不假装自己会 NLP —— 起草智能可以换，把关机械唯一）；
 2. 把关     compile_action 逐条编译（KS-7.1）+ 聚合已在案（P-2 求值预算闸门
             先于动作）—— 编译不过的草案不被写出，逐条报告失败原因；
 3. 晋升     aos draft promote --proposal-ref SPEC-YYYY-NNN 强制（GOV-1：
             模板只记录治理结果，不合成提案）。晋升 = 声明落正典（目标已存在
             即拒绝，晋升不覆盖正典）+ apply_generated（P-5 单写者）——
             晋升后 run_pipeline 必然全绿，aos generate 随后刷新代码骨架。
需求 DSL 样式（docs/samples/requirements-sample.txt）：
    对象: Contract
      标识: contract_id
      属性: status, amount, party_refs
    动作: ApproveContract
      聚合: ContractAggregate
      角色: contract_steward
      参数: contract_id(必填), approver_comment(选填)
      结构: exists contract_id; max_len approver_comment 2000
      条件: snapshot.status == 'pending'
      效果: status=approved
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
from kernel import registration
from kernel.sc_compiler import compile_action
from kernel.errors import RegistrationFailed
def drafts_dir() -> Path:
    return registration.SPEC_DIR / "drafts"                          # 动态取（沙箱可替换）
class DraftError(Exception):
    """草案闸门拒绝（解析/把关/晋升任一环）。"""
# ---------- 1. 解析（确定性；LLM hook 产出同格式即可替换本解析器） ----------
def parse_requirements(text: str) -> dict:
    objects, actions, aggregates, cur = [], [], [], None
    for lineno, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("对象:"):
            cur = {"object_type": s.split(":", 1)[1].strip(),
                   "properties": {}, "identity": ""}
            objects.append(cur); continue
        if s.startswith("动作:"):
            cur = {"action_type": s.split(":", 1)[1].strip(), "aggregate": "",
                   "roles": [], "params": {}, "structural": [],
                   "conditional": [], "effects": {}}
            actions.append(cur); continue
        if s.startswith("聚合体:"):                                   # 与动作块内的"聚合:"键区分
            cur = {"aggregate": s.split(":", 1)[1].strip(),
                   "stream": "", "evaluation_budget": None}
            aggregates.append(cur); continue
        k, _, v = s.partition(":")
        key, val = k.strip(), v.strip()
        if not cur or not key:
            raise DraftError(f"PARSE-FAIL L{lineno}: 无法归属的行「{s}」"
                             f"（须位于 对象:/动作:/聚合体: 块内）")
        if cur.get("action_type"):
            if key == "聚合": cur["aggregate"] = val
            elif key == "角色":
                cur["roles"] = [x.strip() for x in val.split(",") if x.strip()]
            elif key == "参数":
                for part in val.split(","):
                    name, _, req = part.strip().partition("(")
                    if name.strip():
                        cur["params"][name.strip()] = bool(req.startswith("必填"))
            elif key == "结构": cur["structural"] += [x.strip() for x in val.split(";") if x.strip()]
            elif key == "条件": cur["conditional"].append(val)
            elif key == "效果":
                for part in val.split(";"):
                    p, eq, q = part.strip().partition("=")
                    if eq and p.strip():
                        cur["effects"][p.strip()] = _scalar(q.strip())
        elif cur.get("object_type"):
            if key == "标识": cur["identity"] = val
            elif key == "属性":
                cur["properties"] = {p.strip(): {"type": "string"}
                                     for p in val.split(",") if p.strip()}
        else:                                                        # 聚合体块
            if key == "流": cur["stream"] = val
            elif key == "预算": cur["evaluation_budget"] = int(val)
    if not (objects or actions or aggregates):
        raise DraftError("PARSE-FAIL: 未识别任何 对象:/动作:/聚合体: 块")
    return {"objects": objects, "actions": actions, "aggregates": aggregates}
# ---------- 2. 把关（编译不过的草案不被写出） ----------
import re as _re
def _scalar(v: str):
    """效果值字面量：整数/浮点归型，其余保持字符串（enum 状态用）。"""
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    return v
def _cond_block(conditional: list[str]) -> dict:
    """条件段字典形态（与正典声明一致）：expression + snapshot_inputs（R2 快照声明）。"""
    expr = " and ".join(conditional) or None
    if expr is None:
        return {}
    inputs = sorted(set(_re.findall(r"snapshot\.(\w+)", expr)))
    return {"expression": expr, "snapshot_inputs": inputs}
def _action_decl(a: dict, provenance: str) -> dict:
    decl = {"action_type": a["action_type"], "provenance": provenance,
            "aggregate": a["aggregate"],
            "params": {k: {"type": "string", "required": req}
                       for k, req in a["params"].items()},
            "submission_criteria": {"structural": a["structural"],
                                    "conditional": _cond_block(a["conditional"])},
            "permissions": {"roles": a.get("roles") or [], "contexts": []},
            "audit": "required"}
    if a.get("effects"):
        decl["effects"] = a["effects"]
    return decl
def validate_draft(decls: dict) -> list[str]:
    failures = []
    aggregates = {p.stem.replace(".aggregate", "") for p in
                  (registration.SPEC_DIR / "aggregates").glob("*.aggregate.yaml")}
    aggregates |= {a["aggregate"] for a in decls.get("aggregates", [])}  # 草案内聚合视同已声明
    for a in decls.get("aggregates", []):
        if not a.get("stream") or not a.get("evaluation_budget"):
            failures.append(f"AGGREGATE-INCOMPLETE: {a['aggregate']}"
                            f"（流 与 预算 必填 —— P-2 求值预算闸门）")
        elif int(a["evaluation_budget"]) > registration.R8_BUDGET_LIMIT:
            failures.append(f"BUDGET-EXCEEDED: {a['aggregate']} 预算 "
                            f"{a['evaluation_budget']} > R8 上限 {registration.R8_BUDGET_LIMIT}（P-2）")
    for o in decls["objects"]:
        if not o.get("identity"):
            failures.append(f"OBJECT-IDENTITY-MISSING: {o['object_type']}"
                            f"（AX-4 个体须可辨识 —— 补 标识: 行）")
    for a in decls["actions"]:
        if a["aggregate"] not in aggregates:
            failures.append(f"AGGREGATE-NOT-DECLARED: {a['action_type']} 引用的聚合 "
                            f"{a['aggregate']} 未登记（先补 聚合体: 块，P-2 闸门先于动作）")
            continue
        if not a.get("roles"):
            failures.append(f"ROLE-MISSING: {a['action_type']}（动作 MUST 声明 角色: "
                            f"—— P-10 / KS-2：空角色 = 管线与网关守卫双短路，即不设限，"
                            f"fail-closed 拒绝晋升无源之水）")
        try:
            compile_action(_action_decl(a, "DRAFT"), "DRAFT")       # KS-7.1 把关
        except Exception as e:
            failures.append(f"COMPILE-FAILED: {a['action_type']}: {e}")
    return failures
def write_draft(decls: dict, name: str) -> Path:
    out = drafts_dir(); out.mkdir(parents=True, exist_ok=True)
    path = out / f"draft-{name}.yaml"
    path.write_bytes(yaml.safe_dump(decls, allow_unicode=True, sort_keys=False)
                     .encode("utf-8"))                      # 字节精确（* -text）
    return path
def draft_from_decls(decls: dict, name: str) -> dict:
    failures = validate_draft(decls)
    report = {"decls": decls, "failures": failures}
    if not failures:
        report["draft"] = str(write_draft(decls, name))
    return report
def draft(requirements_path: Path, name: str) -> dict:
    return draft_from_decls(parse_requirements(requirements_path.read_text(encoding="utf-8")), name)
def draft_from_text(text: str, name: str) -> dict:
    """程序化入口（测试与 LLM 起草 hook 共用同一闸门）。"""
    return draft_from_decls(parse_requirements(text), name)
# ---------- 3. 晋升（治理提案强制；晋升不覆盖正典） ----------
def promote(draft_path: Path, proposal_ref: str) -> dict:
    if not proposal_ref or not proposal_ref.startswith("SPEC-"):
        raise DraftError("PROMOTION-REFUSED: 晋升 MUST 绑定治理提案 "
                         "--proposal-ref SPEC-YYYY-NNN（GOV-1：模板只记录治理结果）")
    decls = yaml.safe_load(draft_path.read_text(encoding="utf-8")) if Path(draft_path).exists() else None
    if not decls:
        raise DraftError(f"PROMOTION-REFUSED: 草案不存在或为空: {draft_path}")
    targets = []                                                     # 先查后写（全部不冲突才落盘）
    for o in decls["objects"]:
        targets.append((o, registration.SPEC_DIR / "ontology/objects" / f"{o['object_type']}.object.yaml"))
    for g in decls.get("aggregates", []):
        targets.append((g, registration.SPEC_DIR / "aggregates" / f"{g['aggregate']}.aggregate.yaml"))
    for a in decls["actions"]:
        targets.append((a, registration.SPEC_DIR / "ontology/actions" / f"{a['action_type']}.action.yaml"))
    for _, t in targets:
        if t.exists():
            raise DraftError(f"PROMOTION-REFUSED: {t.name} 已存在 —— "
                             f"晋升不覆盖正典声明（变更走 GOV-3 版本通道）")
    promoted = []
    for o, t in targets:
        if t.name.endswith(".object.yaml"):
            doc = {"object_type": o["object_type"], "identity": o["identity"],
                   "properties": o["properties"]}
        elif t.name.endswith(".aggregate.yaml"):
            doc = {"aggregate": o["aggregate"], "stream": o["stream"],
                   "evaluation_budget": o["evaluation_budget"]}
        else:
            doc = _action_decl(o, proposal_ref)                      # provenance = 提案
        t.write_bytes(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
                      .encode("utf-8"))                    # 字节精确（* -text）
        promoted.append(t.name)
    try:
        generated = registration.apply_generated()                   # P-5 单写者
    except RegistrationFailed:
        for _, t in targets:                                         # fail-closed 回滚
            if t.exists():
                t.unlink()
        raise
    return {"promoted": promoted, "capabilities": len(generated["write_actions"]),
            "proposal_ref": proposal_ref}
