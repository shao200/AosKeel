"""Convert the paper Markdown to a Chinese-academic-style .docx.

Handles: H1/H2/H3, blockquote, bold-inline, Markdown tables, horizontal rules,
and reference/paragraph indentation. No external deps beyond python-docx.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

SRC = Path(sys.argv[1])
DST = Path(sys.argv[2])

CN_FONT = "宋体"
CN_FONT_HEAD = "黑体"
LATIN = "Times New Roman"


def set_run_font(run, name_cn=CN_FONT, name_latin=LATIN, size=12, bold=False, color=None):
    run.font.name = name_latin
    run.font.size = Pt(size)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name_cn)
    rfonts.set(qn("w:ascii"), name_latin)
    rfonts.set(qn("w:hAnsi"), name_latin)


def add_inline(paragraph, text, size=12, base_bold=False):
    """Parse **bold** and `code` inline markers."""
    tokens = re.split(r"(\*\*.*?\*\*|`[^`]+`)", text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith("**") and tok.endswith("**"):
            set_run_font(paragraph.add_run(tok[2:-2]), size=size, bold=True)
        elif tok.startswith("`") and tok.endswith("`"):
            set_run_font(paragraph.add_run(tok[1:-1]), name_cn="Consolas",
                         name_latin="Consolas", size=size - 1)
        else:
            set_run_font(paragraph.add_run(tok), size=size, bold=base_bold)


def parse_table_row(line):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def is_sep_row(line):
    return bool(re.match(r"^\s*\|[\s:\-|]+\|\s*$", line))


def main():
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    doc = Document()

    # Base style
    normal = doc.styles["Normal"]
    normal.font.name = LATIN
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), CN_FONT)

    i = 0
    in_refs = False
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and is_sep_row(lines[i + 1]):
            header = parse_table_row(stripped)
            i += 2
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(parse_table_row(lines[i]))
                i += 1
            table = doc.add_table(rows=1, cols=len(header))
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            for j, h in enumerate(header):
                cell = table.rows[0].cells[j]
                cell.text = ""
                p = cell.paragraphs[0]
                add_inline(p, h, size=10, base_bold=True)
            for r in rows:
                cells = table.add_row().cells
                for j in range(len(header)):
                    val = r[j] if j < len(r) else ""
                    cells[j].text = ""
                    p = cells[j].paragraphs[0]
                    add_inline(p, val, size=10)
            doc.add_paragraph()
            continue

        if stripped.startswith("# "):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            add_inline(p, stripped[2:], size=18, base_bold=True)
            for run in p.runs:
                set_run_font(run, name_cn=CN_FONT_HEAD, size=18, bold=True)
            i += 1
            continue

        if stripped.startswith("## "):
            content = stripped[3:]
            if content.startswith("——"):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                set_run_font(p.add_run(content), name_cn=CN_FONT_HEAD, size=13, bold=False)
            elif content.startswith("版本说明") or content.startswith("附录"):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.add_run(content), name_cn=CN_FONT_HEAD, size=14, bold=True)
            else:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                set_run_font(p.add_run(content), name_cn=CN_FONT_HEAD, size=14, bold=True)
            i += 1
            continue

        if stripped.startswith("### "):
            p = doc.add_paragraph()
            set_run_font(p.add_run(stripped[4:]), name_cn=CN_FONT_HEAD, size=12.5, bold=True)
            i += 1
            continue

        if stripped.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(24)
            p.paragraph_format.right_indent = Pt(24)
            add_inline(p, stripped[2:], size=12, base_bold=False)
            i += 1
            continue

        if stripped.startswith("**") and stripped.endswith("**") and ":" in stripped or (
            stripped.startswith("**") and "关键词" in stripped
        ):
            p = doc.add_paragraph()
            add_inline(p, stripped, size=11)
            i += 1
            continue

        # reference entries (year pattern) get hanging indent
        if re.match(r"^[A-Z\u4e00-\u9fff][^,，]{0,40}[,，]\s*(19|20)\d{2}", stripped):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(24)
            p.paragraph_format.first_line_indent = Pt(-24)
            add_inline(p, stripped, size=10.5)
            i += 1
            continue

        # normal paragraph: first line indent
        p = doc.add_paragraph()
        p.paragraph_format.first_line_indent = Pt(24)
        p.paragraph_format.line_spacing = 1.5
        add_inline(p, stripped, size=12)

        # collect wrapped plain lines into same paragraph is intentionally skipped:
        # the source keeps each paragraph on a single line.
        i += 1

    doc.save(str(DST))
    print(f"saved: {DST}")


if __name__ == "__main__":
    main()
