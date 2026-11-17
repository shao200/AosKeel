#!/usr/bin/env python3
"""构建 aoskeel-template 源码树 sdist（ADR-001 增量双分发）。

零外部依赖（标准库 tarfile）：把模板源码树整体打成 .tar.gz，作为
`aos init` 的模板源分发工件。与根 pyproject 的 aos-keel wheel 正交——
后者是 CLI/库安装形态，本 sdist 是"完整模板源码"分发形态。

用法: python packages/template/build_sdist.py [--out dist/aoskeel-template-0.3.0.tar.gz]
"""
from __future__ import annotations
import argparse
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]        # packages/template → 模板根
EXCLUDE_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache",
                "build", "dist", ".aos", ".trae-html-share-packages", "packages"}
EXCLUDE_SUFFIX = (".pyc", ".pyo", ".whl", ".tar.gz")
PREFIX = "aoskeel-template-0.3.0"


def _excluded(rel: Path) -> bool:
    parts = rel.parts
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    return rel.name.endswith(EXCLUDE_SUFFIX)


def build(out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in ROOT.rglob("*")
                   if p.is_file() and not _excluded(p.relative_to(ROOT)))
    with tarfile.open(out, "w:gz") as tf:
        for p in files:
            tf.add(p, arcname=f"{PREFIX}/{p.relative_to(ROOT).as_posix()}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist/aoskeel-template-0.3.0.tar.gz"))
    args = ap.parse_args()
    out = ROOT / args.out if not Path(args.out).is_absolute() else Path(args.out)
    result = build(out)
    with tarfile.open(result, "r:gz") as tf:
        names = tf.getnames()
    required = [f"{PREFIX}/docs/aos-spec.md", f"{PREFIX}/spec/profile.yaml",
                f"{PREFIX}/config/capabilities.yaml", f"{PREFIX}/src/cli/main.py"]
    missing = [r for r in required if r not in names]
    if missing:
        print(f"SDIST-INCOMPLETE: 缺 {missing}")
        return 1
    print(f"SDIST-OK: {result.name} —— {len(names)} 条目；docs/spec/config/src 全在场")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
