#!/usr/bin/env python3
"""边界可见性编码信度计算：一致率、Cohen's kappa、Krippendorff's ordinal alpha。

用法：python 信度计算.py
输入：同目录下 作者编码_C0.md 与 编码结果_C1/C2/C3.md（第二轮为 *_R2.md）
"""
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent
INDICATORS = ["S1", "S2", "E1", "E2", "D1", "D2", "A1", "A2"]
UNITS = ["U1", "U2", "U3", "U4", "U5", "U6"]
VALUES = [0, 1, 2]


def parse(path):
    text = path.read_text(encoding="utf-8")
    rows = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*(U[1-6])[^|]*\|(.+)\|\s*$", line)
        if not m:
            continue
        unit = m.group(1)
        cells = [c.strip() for c in m.group(2).split("|")]
        cells = [c for c in cells if c]
        if len(cells) != 8:
            continue
        vals = []
        for c in cells:
            if c == "?":
                vals.append(None)
            elif c in {"0", "1", "2"}:
                vals.append(int(c))
            else:
                raise ValueError(f"{path.name} {unit}: 无法解析赋值 {c!r}")
        rows[unit] = vals
    if set(rows) != set(UNITS):
        raise ValueError(f"{path.name}: 解析到 {sorted(rows)}，缺少单元")
    return [rows[u] for u in UNITS]


def agreement(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    if not pairs:
        return None, 0
    return sum(1 for x, y in pairs if x == y) / len(pairs), len(pairs)


def cohen_kappa(a, b):
    pairs = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(pairs)
    if n == 0:
        return None, 0
    po = sum(1 for x, y in pairs if x == y) / n
    ca, cb = Counter(x for x, y in pairs), Counter(y for x, y in pairs)
    pe = sum((ca[v] / n) * (cb[v] / n) for v in set(ca) | set(cb))
    if pe >= 1:
        return None, n
    return (po - pe) / (1 - pe), n


def krippendorff_alpha(coders, level="ordinal"):
    """coders: list of lists; each inner list = one coder's 48 values (None = missing)."""
    n_coders, n_units = len(coders), len(coders[0])

    def delta(c, k):
        return (c - k) ** 2 if level == "ordinal" else (0 if c == k else 1)

    Do_sum, n_total = 0.0, 0
    for u in range(n_units):
        counts = {v: 0 for v in VALUES}
        nu = 0
        for cod in coders:
            v = cod[u]
            if v in counts:
                counts[v] += 1
                nu += 1
        n_total += nu
        if nu < 2:
            continue
        d_u = sum(counts[c] * counts[k] * delta(c, k)
                  for c in VALUES for k in VALUES) / (nu - 1)
        Do_sum += d_u
    Do = Do_sum / n_total

    totals = {v: 0 for v in VALUES}
    for cod in coders:
        for v in cod:
            if v in totals:
                totals[v] += 1
    De = sum(totals[c] * totals[k] * delta(c, k)
             for c in VALUES for k in VALUES) / (n_total * (n_total - 1))
    return 1 - Do / De


def flatten(rows):
    return [v for row in rows for v in row]


def report(coders, names, tag):
    print(f"\n{'=' * 64}\n{tag}：编码器 {', '.join(names)}\n{'=' * 64}")
    flat = [flatten(c) for c in coders]
    print(f"有效编码数：{sum(v is not None for f in flat for v in f)} / {len(flat[0]) * len(flat)}")
    print("\n两两一致率 / Cohen's kappa：")
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            agr, n = agreement(flat[i], flat[j])
            kap, _ = cohen_kappa(flat[i], flat[j])
            print(f"  {names[i]}–{names[j]}: agreement={agr:.3f} ({n} 对)  kappa={kap:.3f}")
    a = krippendorff_alpha(flat)
    print(f"\nKrippendorff's ordinal alpha（{len(names)} 编码者）：{a:.4f}")
    return a


def per_indicator(coders, names, tag):
    print(f"\n--- {tag} 逐指标一致率（三名独立编码者两两平均）---")
    for idx, ind in enumerate(INDICATORS):
        vals = []
        for i in range(len(coders)):
            for j in range(i + 1, len(coders)):
                a = [row[idx] for row in coders[i]]
                b = [row[idx] for row in coders[j]]
                ag, n = agreement(a, b)
                if ag is not None:
                    vals.append(ag)
        print(f"  {ind}: {sum(vals) / len(vals):.3f}")


def disagreements(coders, names):
    print("\n--- 分歧单元清单（三名独立编码者中任一不一致）---")
    for ui, unit in enumerate(UNITS):
        triple = [coders[k][ui] for k in range(3)]
        for ii, ind in enumerate(INDICATORS):
            vals = [t[ii] for t in triple]
            nonmiss = [v for v in vals if v is not None]
            if len(set(nonmiss)) <= 1:
                continue
            disp = "/".join("?" if v is None else str(v) for v in vals)
            print(f"  {unit}-{ind}: C1/C2/C3 = {disp}")


if __name__ == "__main__":
    suffix = "_R2" if (BASE / "编码结果_C1_R2.md").exists() else ""
    files = [BASE / "作者编码_C0.md"] + [
        BASE / f"编码结果_C{k}{suffix}.md" for k in (1, 2, 3)
    ]
    coders = [parse(f) for f in files]
    round_tag = "第二轮（手册 v1.1）" if suffix else "第一轮（手册 v1.0）"
    report(coders, ["C0", "C1", "C2", "C3"], round_tag)
    report(coders[1:], ["C1", "C2", "C3"], f"{round_tag} — 仅独立编码者")
    per_indicator(coders[1:], ["C1", "C2", "C3"], round_tag)
    disagreements(coders[1:], ["C1", "C2", "C3"])
