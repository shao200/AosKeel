#!/usr/bin/env python3
"""OWL → AOS 有限单向导出（迁移评估工具，非桥接器 / non-bridge）。

定位（严格单向，见 docs/guide/06-formal-semantics.md 的"翻译极限"）：
- 只导出两个可机械映射的构件：owl:Class → ObjectType，owl:ObjectProperty → LinkType；
- 导出物落在 data-drafts/（草案区），**不进 spec/ 声明摘要域**，不触冻结正典；
- 不宣称语义等价：OWL 的公理、推理、开放世界语义在 AOS 无对应，见下方 LIMITS。

这不是"把 OWL 喂给 AosKeel 就能跑"的桥接——那在 06 章已被明确否定。它是
一个让存量 OWL 库用户**评估迁移成本**的起点：先把类/关系骨架变成 AOS 草案
候选，再人工补齐 identity、decision_relevant、ActionType、Invariant 等语义增量。

零依赖：轻量解析 Turtle / RDF-XML 的类与对象属性声明，不引入 rdflib。
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml

LIMITS = [
    "owl:Class → ObjectType：只导出类名骨架；identity 与 properties 需人工补齐。",
    "owl:ObjectProperty → LinkType：只导出关系名；AOS LinkType 默认零业务语义、不授权，",
    "  OWL 属性的 domain/range/公理不构成 AOS 的 Check AST，需人工重写为 Invariant。",
    "owl:DatatypeProperty / 个体断言(ABox) / 推理结果：不导出（无对应语义）。",
    "开放世界假设(OWL) ≠ 封闭世界(AOS 事件溯源)：缺失数据语义不同，导出后须复核。",
    "ActionType、能力清单、观测层、创世窗口是 AOS 语义增量，OWL 无对应，不可导出。",
    "本工具输出为 data-drafts/ 草案候选，不构成规范声明；晋升须 aos draft promote + GOV-1 提案。",
]


def _names(text: str) -> list[str]:
    """从 <owl:Class rdf:about=\"#Foo\"> / :Foo a owl:Class 提取本地名。"""
    names: list[str] = []
    # RDF/XML
    for m in re.finditer(r'<(?:owl:)?Class\b[^>]*?rdf:(?:about|ID)="(?:#)?([^"]+)"', text):
        names.append(m.group(1))
    # Turtle:  Foo a owl:Class .  /  :Foo rdf:type owl:Class .
    for m in re.finditer(r'(?m)^\s*[:#]?([A-Za-z_]\w*)\s+(?:a|rdf:type)\s+owl:Class\b', text):
        names.append(m.group(1))
    return list(dict.fromkeys(names))  # 去重保序


def _props(text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r'<(?:owl:)?ObjectProperty\b[^>]*?rdf:(?:about|ID)="(?:#)?([^"]+)"', text):
        names.append(m.group(1))
    for m in re.finditer(r'(?m)^\s*[:#]?([A-Za-z_]\w*)\s+(?:a|rdf:type)\s+owl:ObjectProperty\b', text):
        names.append(m.group(1))
    return list(dict.fromkeys(names))


def export(src: Path) -> dict:
    text = src.read_text(encoding="utf-8", errors="replace")
    classes, props = _names(text), _props(text)
    objects = [{"object_type": c, "identity": f"{c[:1].lower() + c[1:]}_id",
                "properties": {}, "_confidence": "low", "_note": "OWL class 骨架；identity 待人工确认"}
               for c in classes]
    links = [{"link_type": p, "pattern": "structural", "_confidence": "low",
              "_note": "OWL objectProperty 骨架；AOS LinkType 零语义，domain/range 需人工重写"}
             for p in props]
    return {"origin": {"source": src.name, "tool": "owl_export", "direction": "OWL→AOS one-way",
                       "warning": "draft candidates only; see LIMITS"},
            "objects": objects, "links": links, "limits": LIMITS}


def main() -> int:
    if len(sys.argv) < 2:
        print("用法: python tools/owl_export.py <owl-file.ttl|owl-file.xml> "
              "[--out data-drafts/owl-export.yaml]", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    if not src.exists():
        print(f"OWL-EXPORT-NOSOURCE: {src} 不存在", file=sys.stderr)
        return 1
    out = ROOT / "data-drafts/owl-export.yaml"
    if "--out" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--out") + 1])
    decls = export(src)
    if not decls["objects"] and not decls["links"]:
        print("OWL-EXPORT-EMPTY: 未识别到 owl:Class / owl:ObjectProperty —— 不静默出空草案",
              file=sys.stderr)
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml.safe_dump(decls, allow_unicode=True, sort_keys=False),
                   encoding="utf-8")
    print(f"OWL-EXPORTED: {src.name} → {out} "
          f"（objects={len(decls['objects'])}, links={len(decls['links'])}）")
    print("单向导出，非桥接；草案不进声明摘要域，晋升须 GOV-1 提案。翻译极限：")
    for lim in LIMITS:
        print("  - " + lim)
    return 0


if __name__ == "__main__":
    sys.exit(main())
