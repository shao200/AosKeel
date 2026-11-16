#!/usr/bin/env python3
"""tools/impact.py —— 变更影响分析（治理面"版本与变更治理"的事前半边）。
三关与 reconcile 是**事后漂移检测**（改错了会被拦）；本工具回答**事前**问题：
"改这条声明，会牵动哪些声明、哪些生成段、哪些布线测试？"
做法：装载 spec/ 八类声明，按已知引用位建反向引用图——
  Action: aggregate / conditional.snapshot_inputs →聚合根属性 / effects →聚合根属性 /
          permissions.contexts
  Invariant: aggregate / snapshot_inputs / repair_binding.action
  Aggregate: root / invariants / context
  Mapping: source_context / target_context / field_map 值（目标属性）
  Process: steps[].action / compensations[].action
  Context: ubiquitous_language 键（同名词即对象类型时）
纯咨询，不进闸门、不写盘；真源仍是 spec/，图是派生视图（声明变更后重算即可）。
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
import yaml
SPEC = ROOT / "spec"
def _load(sub: str) -> list[tuple[dict, str]]:
    out = []
    for p in sorted((SPEC / sub).glob("*.yaml")) if (SPEC / sub).exists() else []:
        out.append((yaml.safe_load(p.read_text(encoding="utf-8")) or {},
                    f"spec/{sub}/{p.name}"))
    return out
def build_graph() -> dict:
    """nodes: name -> kind；edges: 目标 -> [(源节点, 引用位, 源文件)]。"""
    objects = {}      # object_type -> file
    properties = {}   # object_type -> [props]
    aggregates = {}   # aggregate -> (root, file)
    ctx_roots: dict[str, list[str]] = {}   # context -> 聚合根对象
    edges: dict[str, list[tuple[str, str, str]]] = {}
    names: dict[str, str] = {}          # 声明名 -> 类型标签
    def link(src: str, rel: str, src_file: str, dst: str) -> None:
        edges.setdefault(dst, []).append((src, rel, src_file))
    for d, f in _load("ontology/objects"):
        objects[d["object_type"]] = f
        properties[d["object_type"]] = list((d.get("properties") or {}).keys())
        names[d["object_type"]] = "object"
        if d.get("identity"):
            link(d["object_type"], "identity", f,
                 f"{d['object_type']}.{d['identity']}")
    for d, f in _load("aggregates"):
        aggregates[d["aggregate"]] = (d.get("root"), f)
        names[d["aggregate"]] = "aggregate"
        if d.get("root") and d.get("context"):
            ctx_roots.setdefault(d["context"], []).append(d["root"])
        if d.get("root"):
            link(d["aggregate"], "root", f, d["root"])
        for iv in d.get("invariants", []) or []:
            link(d["aggregate"], "invariant", f, iv)
        if d.get("context"):
            link(d["aggregate"], "context", f, d["context"])
    for d, f in _load("ontology/actions"):
        aid = d["action_type"]
        names[aid] = "action"
        agg = d.get("aggregate") or ""
        root = (aggregates.get(agg) or (None,))[0]
        if agg:
            link(aid, "aggregate", f, agg)
        cond = (d.get("submission_criteria") or {}).get("conditional") or {}
        for k in cond.get("snapshot_inputs", []) or []:
            if k.split(".", 1)[0] != "principal" and root:
                link(aid, "条件快照输入", f, f"{root}.{k}")
        for k in (d.get("effects") or {}):
            if root:
                link(aid, "效果键", f, f"{root}.{k}")
        for c in (d.get("permissions") or {}).get("contexts", []) or []:
            link(aid, "权限上下文", f, c)
    for d, f in _load("invariants"):
        iv = d.get("invariant") or Path(f).name
        names[iv] = "invariant"
        if d.get("aggregate"):
            link(iv, "aggregate", f, d["aggregate"])
        decl = d.get("declaration") or {}
        root = (aggregates.get(d.get("aggregate") or "") or (None,))[0]
        for k in decl.get("snapshot_inputs", []) or []:
            if root:
                link(iv, "不变量输入", f, f"{root}.{k}")
        rb = (d.get("repair_binding") or {}).get("action")
        if rb:
            link(iv, "修复绑定", f, rb)
    for d, f in _load("mappings"):
        m = d.get("mapping") or Path(f).name
        names[m] = "mapping"
        for side in ("source_context", "target_context"):
            if d.get(side):
                link(m, side, f, d[side])
        tgt = d.get("target_context")
        roots = ctx_roots.get(tgt or "", [])
        for src_field, prop in ((d.get("transform") or {}).get("field_map") or {}).items():
            node = next((f"{r}.{prop}" for r in roots if f"{r}.{prop}" in names), prop)
            link(m, "字段映射目标", f, node)        # 解析到目标上下文聚合根的属性节点
    for d, f in _load("processes"):
        p = d.get("process") or Path(f).name
        names[p] = "process"
        for s in d.get("steps", []) or []:
            if s.get("action"):
                link(p, "step", f, s["action"])
        for c in d.get("compensations", []) or []:
            if c.get("action"):
                link(p, "补偿", f, c["action"])
    for d, f in _load("contexts"):
        c = d.get("context") or Path(f).name
        names[c] = "context"
        if d.get("steward"):
            link(c, "steward 角色", f, d["steward"])
    # 属性节点：ObjectType.prop（由 object properties 枚举补全 names）
    for ot, props in properties.items():
        for pr in props:
            names[f"{ot}.{pr}"] = "property"
    return {"nodes": names, "edges": edges, "objects": objects}
def resolve(target: str, g: dict) -> str | None:
    """接受：spec 文件路径 / 声明名（Action、Object、属性 ObjectType.prop…）。"""
    p = Path(target)
    if p.exists() and p.suffix == ".yaml":
        d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        for key in ("action_type", "object_type", "aggregate", "invariant",
                    "mapping", "process", "context", "link_type"):
            if d.get(key):
                return d[key]
        return None
    if target in g["nodes"]:
        return target
    # 容错：按文件名 <name>.<kind>.yaml 猜测
    m = re.match(r".*?([^.\\/]+)\.(action|object|aggregate|invariant|mapping|process|context|link)\.yaml$",
                 target.replace("\\", "/"))
    if m and m.group(1) in g["nodes"]:
        return m.group(1)
    return None
def wired_mentions(name: str) -> list[str]:
    """扫描 tests/ 全部 .py：文本提及该声明名的测试文件。"""
    hits = []
    for tp in sorted((ROOT / "tests").rglob("*.py")):
        try:
            text = tp.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if name in text:
            hits.append(str(tp.relative_to(ROOT)).replace("\\", "/"))
    return hits
def report(target: str) -> int:
    g = build_graph()
    node = resolve(target, g)
    if node is None:
        print(f"IMPACT-UNKNOWN: 无法解析声明目标 '{target}' —— "
              f"传 spec 文件路径或声明名（对象/属性 ObjectType.prop/聚合/Action/不变量/映射/流程/上下文）")
        return 1
    kind = g["nodes"].get(node, "?")
    print(f"IMPACT: {node}（{kind}）")
    deps = g["edges"].get(node, [])
    print(f"—— 上游：{len(deps)} 个引用位（改了它，这些会受影响）")
    for src, rel, f in deps:
        print(f"  ← {src}（{rel}） @ {f}")
    downstream = [(dst, src, rel, f) for dst, es in g["edges"].items()
                  for (src, rel, f) in es if src == node]
    print(f"—— 下游：{len(downstream)} 个引用目标（它依赖这些）")
    for dst, src, rel, f in downstream:
        print(f"  → {dst}（{rel}） @ {f}")
    if kind in ("action",):
        caps = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8")
        print("—— 能力清单：", "在 generated 段" if f"id: {node}" in caps.replace("'", "") else "不在")
    hits = wired_mentions(node.split(".", 1)[1] if kind == "property" else node)
    print(f"—— 测试提及：{len(hits)} 个文件")
    for h in hits:
        print(f"  · {h}")
    print("（咨询性报告：真源是 spec/，门禁仍由三关 + 布线负责 —— 本工具不放行也不拦截）")
    return 0
if __name__ == "__main__":
    sys.exit(report(sys.argv[1] if len(sys.argv) > 1 else ""))
