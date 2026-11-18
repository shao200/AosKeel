#!/usr/bin/env python3
"""GOV-2.4 / 附录 F 条款指纹 —— 结构层核对（任何介质可执行）。
每节核对 = 条数 + 首条锚 + 末条锚，三者齐备方为在场。
失败报告按 GOV-2.5 指明失败节与失败形态（条数不符 / 首锚缺失 / 末锚缺失 / 子项缺失）。
分歧二分：正典缺内容 → GOV-6 记录并修订；副本退化 → 重新分发，不修冻结文本。
"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs/aos-spec.md"
# (节名, 期望条数, 定义行正则, 首锚, 末锚, 计数域 scope[None=全文])
SECTIONS = [
    ("AX",   5, r"(?m)^\*\*(AX-\d+)\s",           "AX-1",   "AX-5",  None),
    ("KS",  30, r"(?m)^\*\*(KS-\d+\.\d+)\*\*",    "KS-1.1", "KS-8.5", None),
    ("P",   17, r"(?m)^\*\*(P-\d+)\s",            "P-1",    "P-17",  None),
    ("INV", 13, r"(?m)^(INV-\d+)\s+\[",           "INV-1",  "INV-13", None),
    ("BOOT", 5, r"(?m)^\*\*(BOOT-\d)",            "BOOT-0", "BOOT-4", None),
    ("GOV",  6, r"(?m)^\*\*(GOV-\d)\*?",          "GOV-1",  "GOV-6",  None),
    ("VER", 33, r"(?m)^(VER-\d+)\s+\[",           "VER-1",  "VER-33", None),
    ("术语",26, r"(?m)^(T\d{2})\s",               "T01",    "T26",   None),
    ("事故",18, r"(?m)^([A-R])\s\S",              "A",      "R",     r"(?s)### B\.2.*?(?=\n## )"),
]
GOV_SUBITEMS = [f"GOV-2.{i}" for i in range(1, 6)]
APPENDICES = list("ABCDEFG") + ["R", "S"]   # v2.1.0：R/S 为信息性附录，仍属附录清单
def check(text: str | None = None) -> list[str]:
    text = text if text is not None else SPEC.read_text(encoding="utf-8")
    failures = []
    for name, want, pat, first, last, scope in SECTIONS:
        scoped = text
        if scope:
            m = re.search(scope, text)
            if not m:
                failures.append(f"{name}: 登记节缺失（{scope}）")
                continue
            scoped = m.group(0)
        ids = re.findall(pat, scoped)
        if len(ids) != want:
            failures.append(f"{name}: 条数不符（期望 {want}，实得 {len(ids)}）")
            continue
        if not ids[0].startswith(first):
            failures.append(f"{name}: 首锚缺失（期望 {first}，实得 {ids[0]}）")
        if not ids[-1].startswith(last):
            failures.append(f"{name}: 末锚缺失（期望 {last}，实得 {ids[-1]}）")
    for s in GOV_SUBITEMS:
        if f"**{s}**" not in text:
            failures.append(f"GOV: 子项缺失 {s}")
    for a in APPENDICES:
        if f"附录 {a}：" not in text:
            failures.append(f"附录: 缺失 附录 {a}")
    return failures
def main() -> int:
    if not SPEC.exists():
        print(f"STRUCTURAL-FAIL: 正典文件缺失: {SPEC.name}"); return 1
    failures = check()
    if failures:
        print("STRUCTURAL-MISMATCH —— 失败节与失败形态（GOV-2.5）:")
        for f in failures: print(f"  - {f}")
        return 1
    print("FINGERPRINT-OK: 附录 F 十节三元组全部在场（条数+首锚+末锚）")
    return 0
if __name__ == "__main__":
    sys.exit(main())
