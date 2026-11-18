#!/usr/bin/env python3
"""tools/semantic_extract.py —— 语义提取契约层（"创建"支柱最后缺口）。
定位（与项目哲学同构，同 FileStore 模式）：内核**不绑定任何 LLM 服务**——
提供 提取契约 + 确定性参考提取器（零依赖可跑） + 可插拔适配器。LLM 调用是
实例侧职责（用户自己的适配器脚本）；**无论提取器是规则还是 LLM，产物都是
草案、都过同一三段闸（draft_from_decls）、晋升都必须 GOV-1 提案**——闸门
与来源无关。
参考提取器（确定性启发式，置信度如实标注）：
- 源码（Python/Java/C#）：类 → object 候选；类型化字段 → properties；
- 文档（Markdown/文本）：英文标题 → 实体候选；纯中文标题大声跳过（命名须人工）。
参考提取器只产**结构层**（objects + aggregates 候选）——行为层（actions）
是人与 LLM 适配器的职责，模板不编造行为。
适配器契约：脚本以素材路径为 argv[1]，stdout 输出 YAML
  {objects: [{object_type, identity, properties: {name: type}}]}
AosKeel 校验 schema 后过同一闸；origin 来源标注在案（file/extractor/confidence）。
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import yaml
from tools.ontology_draft import draft_from_decls
CLASS_RE = re.compile(r"^\s*(?:class|interface)\s+([A-Z]\w+)", re.M)
PY_FIELD_RE = re.compile(r"^\s+([a-z]\w*)\s*:\s*([A-Za-z_][\w\[\]\.]*)", re.M)      # 注解字段
JAVA_FIELD_RE = re.compile(
    r"^\s*(?:private|public|protected)\s+[A-Za-z_][\w<>\[\]\.]*\s+([a-z]\w*)\s*;", re.M)
GENERIC_FIELD_RE = re.compile(r"^\s+([a-z]\w*)\s*[:=]\s*", re.M)                    # dataclass/赋值
TITLE_RE = re.compile(r"^#{1,3}\s+(.+?)\s*$", re.M)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*")
BUILTIN = "builtin-rules-v1"
def _pascal(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(p[:1].upper() + p[1:] for p in parts if p)
def _fields_from_block(block: str) -> list[str]:
    for rex in (PY_FIELD_RE, JAVA_FIELD_RE, GENERIC_FIELD_RE):
        names, seen = [], set()
        for m in rex.finditer(block):
            if m.group(1) not in seen:
                seen.add(m.group(1))
                names.append(m.group(1))
        if names:
            return names
    return []
def extract_code(text: str, source: str) -> tuple[list[dict], list[str]]:
    """类 → object 候选（identity：id 字段优先，否则首字段+低置信标注）。"""
    objects, notes = [], []
    matches = list(CLASS_RE.finditer(text))
    for i, m in enumerate(matches):
        block = text[m.start(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        fields = _fields_from_block(block)
        if not fields:
            notes.append(f"SKIP-NO-FIELDS: {m.group(1)}（{source}）无可辨识字段")
            continue
        ident = next((f for f in fields if f.lower().endswith(("id", "_id", "key"))), fields[0])
        conf = "medium" if ident.lower().endswith(("id", "_id", "key")) else "low"
        objects.append({"object_type": m.group(1),
                        "identity": ident,
                        "properties": {f: "string" for f in fields},
                        "_confidence": conf})
    return objects, notes
def extract_doc(text: str, source: str) -> tuple[list[dict], list[str]]:
    """英文标题 → 实体候选；纯中文标题大声跳过（object_type 命名须人工）。"""
    objects, notes = [], []
    for m in TITLE_RE.finditer(text):
        title = m.group(1)
        words = WORD_RE.findall(title)
        if not words:
            notes.append(f"SKIP-NON-ASCII-TITLE: 「{title}」（{source}）"
                         "—— 中文标题需人工命名 object_type")
            continue
        ot = _pascal(" ".join(words[:3]))
        objects.append({"object_type": ot, "identity": ot.lower() + "_id",
                        "properties": {}, "_confidence": "low"})
    return objects, notes
def _builtin_extract(path: Path) -> tuple[list[dict], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".py", ".java", ".cs"):
        return extract_code(text, path.name)
    return extract_doc(text, path.name)
def _custom_extract(script: str, path: Path) -> tuple[list[dict], list[str]]:
    """适配器契约：脚本收素材路径，stdout 出候选 YAML。fail-closed。"""
    proc = subprocess.run([sys.executable, script, str(path)],
                          capture_output=True, text=True, timeout=120, cwd=str(ROOT))
    if proc.returncode != 0:
        raise ValueError(f"EXTRACTOR-FAILED: 适配器退出码 {proc.returncode}: "
                         f"{proc.stderr[-500:]}")
    out = yaml.safe_load(proc.stdout) or {}
    objs = out.get("objects") or []
    if not isinstance(objs, list):
        raise ValueError("EXTRACTOR-BAD-OUTPUT: 适配器输出缺少 objects 列表")
    for o in objs:
        if not (o.get("object_type") and "identity" in o
                and isinstance(o.get("properties"), dict)):
            raise ValueError(f"EXTRACTOR-BAD-SCHEMA: {o.get('object_type')!r} 缺少 "
                             "object_type/identity/properties（契约: stdout YAML objects[]）")
    return objs, [f"ADAPTER: {Path(script).name} 产出 {len(objs)} 个候选"]
def extract(path: str, name: str, extractor: str | None = None) -> dict:
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"EXTRACT-NOSOURCE: {path} 不存在")
    if extractor and extractor != "builtin":
        objs, notes = _custom_extract(extractor, src)
        ext = f"custom:{Path(extractor).name}"
    else:
        objs, notes = _builtin_extract(src)
        ext = BUILTIN
    if not objs:
        raise ValueError(f"EXTRACT-EMPTY: 未从 {src.name} 提取到候选 "
                         f"（{len(notes)} 条跳过说明——不静默）")
    decls = {"origin": {"source_file": src.name, "extractor": ext,
                        "note": "语义提取候选——晋升须 GOV-1 提案（来源可审计）"},
             "objects": [{"object_type": o["object_type"], "identity": o["identity"],
                          "properties": o.get("properties") or {}} for o in objs],
             "aggregates": [{"aggregate": o["object_type"],
                             "root": o["object_type"],          # 同名聚合 → 根即对象（读侧实例标识）
                             "stream": o["object_type"],
                             "evaluation_budget": 10000} for o in objs],
             "actions": []}                       # 行为层如实留空——不编造
    report = draft_from_decls(decls, name)        # 同一三段闸（编译不过不落盘）
    report["notes"] = notes
    report["extractor"] = ext
    report["confidence"] = {o["object_type"]: o.get("_confidence", "low") for o in objs}
    return report
