#!/usr/bin/env python3
"""tools/doc_sync.py —— 派生文档同步：版本号与测试规模从唯一真源写回。

评审暴露的问题：计数有守卫，语义版本没有；三处版本号漂移了三轮。本工具把
"手抄事实"收敛为派生量：
  真源   docs/ARTIFACT-REGISTRY.md（现行 AOS-ART 条目）+ tools/doc_metrics.py
  消费端 docs/README.md / docs/STRATEGY.md / docs/STRATEGY.en.md / pyproject.toml

用法：
  python -m tools.doc_sync --check    # CI：有漂移即非零退出（fail-closed）
  python -m tools.doc_sync --write    # 本地：把漂移写回派生文档
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))

from tools import doc_metrics as dm                      # noqa: E402


def current_spec_version() -> str:
    """现行规范版本 = 登记表最后一条 AOS-ART-*（与文档守卫同源）。"""
    reg = (ROOT / "docs/ARTIFACT-REGISTRY.md").read_text(encoding="utf-8")
    rows = [l for l in reg.splitlines()
            if re.match(r"\|\s*AOS-ART-\d+\s*\|\s*v[\d.]+\s*\|", l)]
    if not rows:
        raise SystemExit("DOC-SYNC: 登记表缺少 AOS-ART 条目")
    return rows[-1].split("|")[2].strip()


def substitutions() -> dict[str, list[tuple[str, str]]]:
    """(文件 → [(模式, 替换文本)])；替换文本全部由真源派生。"""
    s = dm.stats()
    v = current_spec_version()
    collected = dm.pytest_collected()
    return {
        "docs/README.md": [
            (r"\*\*\d+ test files / \d+ `def test_` functions\*\*",
             f"**{s['test_files']} test files / {s['test_fns']} `def test_` functions**"),
            (r"collects \d+ cases", f"collects {collected} cases"),
            (r"canonical spec `v[\d.]+`", f"canonical spec `{v}`"),
        ],
        "docs/STRATEGY.md": [
            (r"\d+ 个测试文件 / \d+ 个测试函数",
             f"{s['test_files']} 个测试文件 / {s['test_fns']} 个测试函数"),
        ],
        "docs/STRATEGY.en.md": [
            (r"\d+ test files / \d+ test functions",
             f"{s['test_files']} test files / {s['test_fns']} test functions"),
        ],
        "pyproject.toml": [
            (r"对应规范 v[\d.]+", f"对应规范 {v}"),
        ],
    }


def check() -> list[str]:
    """返回漂移描述列表；空列表 = 派生文档与真源一致。"""
    drift: list[str] = []
    for rel, pairs in substitutions().items():
        text = (ROOT / rel).read_text(encoding="utf-8")
        for pattern, expected in pairs:
            found = re.findall(pattern, text)
            if not found:
                drift.append(f"{rel}: 缺少派生片段 {pattern!r}")
            elif any(item != expected for item in found):
                drift.append(f"{rel}: {found!r} ≠ {expected!r}")
    return drift


def write() -> int:
    changed = 0
    for rel, pairs in substitutions().items():
        p = ROOT / rel
        text = p.read_text(encoding="utf-8")
        new = text
        for pattern, expected in pairs:
            new = re.sub(pattern, lambda _m, e=expected: e, new)
        if new != text:
            p.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    print(f"DOC-SYNC: 已写回 {changed} 个文件")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if "--write" in args:
        return write()
    drift = check()
    for line in drift:
        print(f"DOC-DRIFT: {line}")
    if drift:
        print("DOC-SYNC-FAILED: 派生文档与真源不一致（运行 --write 后提交）")
        return 1
    print("DOC-SYNC-OK: 版本号与测试规模均与真源一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
