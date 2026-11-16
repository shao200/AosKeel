#!/usr/bin/env python3
"""tools/domain_manual.py —— 领域说明书生成器（aos manual）。
把 spec/ 八类声明编译成人类可读、LLM 可注入的单一文档：
- 对开发者：init 后第一份"本域能做什么/谁说了算/哪里会拒绝"的地图；
- 对 AI 集成：作为 system prompt 素材——LLM 拿到的是治理边界，
  不是自由发挥的领域描述（AX-2：概率只提议，此文档定义可提议的集合）。
派生件不是真源：一切以 spec/ 声明为准（本文件顶部注明）；生成不写盘
除非 --out。声明变更后重新生成即可，无手工维护成本。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
try:
    import yaml
except ImportError:
    yaml = None
SPEC = ROOT / "spec"
def _load(p: Path) -> list[dict]:
    out = []
    for f in sorted(p.glob("*.yaml")) if p.exists() else []:
        d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        d["_file"] = f.name
        out.append(d)
    return out
def _props(props: dict) -> list[str]:
    lines = []
    for name, spec in (props or {}).items():
        s = spec or {}
        marks = []
        if s.get("required"):
            marks.append("必填")
        if s.get("decision_relevant"):
            marks.append("决策相关（INV-8 审计语义）")
        if s.get("values"):
            marks.append("枚举: " + "/".join(map(str, s["values"])))
        lines.append(f"  - `{name}`（{s.get('type', '?')}）" +
                     ("；" + "；".join(marks) if marks else ""))
    return lines
def render() -> str:
    if yaml is None:
        raise SystemExit("DEPENDENCY: 生成说明书需要 pyyaml")
    objs = _load(SPEC / "ontology" / "objects")
    links = _load(SPEC / "ontology" / "links")
    acts = _load(SPEC / "ontology" / "actions")
    ctxs = _load(SPEC / "contexts")
    aggs = _load(SPEC / "aggregates")
    invs = _load(SPEC / "invariants")
    maps = _load(SPEC / "mappings")
    procs = _load(SPEC / "processes")
    L = ["# 领域说明书（生成件 —— 真源是 spec/，本文档是其派生视图）",
         "",
         "> 用途一：开发者理解本域结构的第一份地图。",
         "> 用途二：作为 AI Agent 的领域上下文注入——它定义 LLM 可以提议什么，",
         "> 而非让它自由发挥（AX-2）。与运行时不一致时，以 spec/ 声明与注册管线为准。",
         "", "## 1. 上下文与所有权（谁说了算）", ""]
    for c in ctxs:
        L += [f"### {c.get('context', '?')}",
              f"- steward：`{c.get('steward', '（缺失=注册拒绝）')}`（P-3）",
              f"- 投影延迟预算：{c.get('projection_delay_budget_ms', '?')} ms（P-16）", ""]
    L += ["## 2. 聚合与一致性边界（改动以什么单位生效）", ""]
    for a in aggs:
        L += [f"### {a.get('aggregate', '?')}",
              f"- 根对象：{a.get('root', '?')}；事件流：`{a.get('stream', '?')}`",
              f"- 求值预算：{a.get('evaluation_budget', '?')}（R8 上限 10^5）",
              f"- 在场不变量：{', '.join(a.get('invariants', []) or []) or '（无）'}", ""]
    L += ["## 3. 对象类型（概念与属性）", ""]
    for o in objs:
        L += [f"### {o.get('object_type', '?')}",
              f"- 标识：`{o.get('identity', '?')}`"]
        L += _props(o.get("properties"))
        L += [f"- 所属上下文：{o.get('context', '（未声明）')}", ""]
    L += ["## 4. 动作类型（世界允许怎样被改变 —— 唯一变更面）", ""]
    for a in acts:
        sc = a.get("submission_criteria") or {}
        cond = (sc.get("conditional") or {})
        perm = a.get("permissions") or {}
        L += [f"### {a.get('action_type', '?')}（provenance: {a.get('provenance', '?')}）",
              f"- 聚合：{a.get('aggregate', '?')}"]
        L += _props(a.get("params"))
        L += [f"- 结构校验：{'; '.join(sc.get('structural', []) or []) or '（无）'}",
              f"- 条件校验：`{cond.get('expression', '（无）')}`"
              f"（快照输入：{', '.join(map(str, cond.get('snapshot_inputs', []) or []))}）",
              f"- 状态效果（T24，内核书写进事件，勿自报）："
              f"{a.get('effects') or '（无）'}",
              f"- 权限角色：{', '.join(map(str, perm.get('roles', []) or [])) or '（未声明）'}"
              f"；上下文：{', '.join(map(str, perm.get('contexts', []) or [])) or '-'}",
              f"- 审计：{a.get('audit', '-')}；演练要求：{a.get('dry_run', '-')}；"
              f"补偿：{a.get('compensation', '-')}（幂等：{a.get('idempotent', '-')}）", ""]
    L += ["## 5. 不变量（必须永远为真 + 违约怎么办）", ""]
    for i in invs:
        decl = i.get("declaration") or {}
        vs = i.get("violation_semantics") or {}
        rb = i.get("repair_binding") or {}
        L += [f"### {i.get('invariant', '?')}",
              f"- 表达式：`{decl.get('expression', '?')}`（{vs.get('kind', '?')} → "
              f"{vs.get('detection', '?')}；宽限 {vs.get('grace', '-')}）",
              f"- 修复绑定：`{rb.get('action', '（缺失=注册拒绝）')}`"
              f"；兜底：{rb.get('fallback', '-')}（INV-3 / P-6）",
              f"- 移除后果：{i.get('removal_consequence', '-')}（反事实理由链）", ""]
    L += ["## 6. 链接（结构性关系，零业务语义）", ""]
    for lk in links:
        L += [f"### {lk.get('link_type', '?')}",
              f"- 三约束：属性空={lk.get('checks', {}).get('attributes_empty')}；"
              f"遍历透明={lk.get('checks', {}).get('traversal_transparent')}；"
              f"不绑 Action={not lk.get('action_binding')}（P-4 / INV-2）", ""]
    L += ["## 7. 外部映射（数据从哪来，丢了什么语义）", ""]
    for m in maps:
        L += [f"### {m.get('mapping', '?')}",
              f"- {m.get('source_context', '?')} → {m.get('target_context', '?')}；"
              f"锚点：`{m.get('anchor', '?')}`",
              f"- 字段映射：{m.get('transform', {}).get('field_map', {})}；"
              f"丢弃：{m.get('transform', {}).get('drop', [])}",
              f"- 语义损耗声明（KS-4 必填）："]
        L += [f"  - {x}" for x in m.get("semantic_loss_declared", []) or []]
        L += [""]
    L += ["## 8. 流程（跨聚合编排与补偿）", ""]
    for p in procs:
        comps = "; ".join(f"{c.get('for')}←{c.get('action')}"
                          for c in p.get("compensations", []) or []) or "（无）"
        L += [f"### {p.get('process', '?')}",
              f"- 步序：{', '.join(s.get('action', '?') for s in p.get('steps', []) or [])}",
              f"- 补偿：{comps}（补偿本身是 Action，P-9）", ""]
    L += ["---",
          "生成命令：`python src/cli/main.py manual [--out docs/DOMAIN-MANUAL.md]`；"
          "声明变更后重新生成。本文档不进哈希覆盖域（派生件不是真源）。"]
    return "\n".join(L) + "\n"
def main(out: str | None = None) -> int:
    text = render()
    if out:
        Path(out).write_bytes(text.encode("utf-8"))
        print(f"MANUAL: {out}（{text.count(chr(10)) + 1} 行；真源 = spec/）")
    else:
        print(text)
    return 0
if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
