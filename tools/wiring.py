#!/usr/bin/env python3
"""tools/wiring.py —— config/verification.yaml 的唯一读取点（承重件，AX-5）。

历史问题：`aos test` 与 `release_gate._default_tests` 各自用正则从文本里抠
`path:`，合法 YAML 的格式微调（键序、引号、空格、跨行）会静默丢项：
27 条布线可以变成 26 条而闸门照样出制品 —— 与 fail-closed 相悖。
此处统一用 pyyaml 解析，并把"声明了 path 但文件不存在"从打印降级改成阻断。

不新增 VER 条款：v2.0.0 的 VER-1..33 是冻结条款集；`integrity_paths` 段只登记
回归补充测试的执行路径，不构成条款，也不改指纹清单。

另提供 `require_pytest()`：`aos test` 与发布闸门共同的执行前置。pytest 是布线
测试的执行引擎（已在 pyproject 声明为运行时依赖），缺失时 fail-closed 明确
拒绝，不把 ImportError 伪装成"套件失败"。
"""
from __future__ import annotations
from pathlib import Path
import importlib.util
import yaml

ROOT = Path(__file__).resolve().parents[1]


class WiringError(Exception):
    """布线件不可用（缺失、格式非法、声明路径不存在）—— 一律阻断。"""


def load(root: Path | None = None) -> dict:
    root = Path(root) if root is not None else ROOT
    p = root / "config/verification.yaml"
    if not p.exists():
        raise WiringError(f"WIRING-MISSING: 布线文件缺失: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not isinstance(data.get("ver"), list):
        raise WiringError("WIRING-INVALID: 布线文件缺 ver 列表（承重件不可为空）")
    return data


def scan(root: Path | None = None,
         suite: str | None = None) -> tuple[list[tuple[str, str]], list[str], list[str]]:
    """返回 (可执行的 (id, path), 声明但缺文件的描述, 无 path 的条目 id)。

    无 path 的条目 = 〔强〕项（只有 checklist / support），按诚实边界不在模板内
    伪装通过；它们不算缺失，但会被如实列出。
    """
    root = Path(root) if root is not None else ROOT
    data = load(root)
    entries = list(data["ver"]) + list(data.get("integrity_paths", []) or [])
    ready, missing, unwired = [], [], []
    for e in entries:
        if not isinstance(e, dict) or not e.get("path"):
            unwired.append(str(e.get("id", "?")) if isinstance(e, dict) else "?")
            continue
        ident, rel = str(e["id"]), str(e["path"])
        if suite is not None and not rel.startswith(f"tests/{suite}/"):
            continue
        if (root / rel).exists():
            ready.append((ident, rel))
        else:
            missing.append(f"{ident}: {rel}")
    return ready, missing, unwired


def wired_paths(root: Path | None = None, suite: str | None = None) -> list[tuple[str, str]]:
    """严格入口：声明路径缺失即 WiringError（发布闸门与 CI 用）。"""
    ready, missing, _ = scan(root, suite)
    if missing:
        raise WiringError("WIRING-REFUSED: 声明的测试路径不存在（fail-closed）: "
                          + "; ".join(missing))
    return ready


def suites(root: Path | None = None) -> dict:
    """套件 gate 声明（值统一成小写字符串，便于展示与比对）。"""
    raw = load(root).get("suites", {}) or {}
    return {k: str(v.get("gate", "")).lower() if isinstance(v, dict) else str(v).lower()
            for k, v in raw.items()}


def require_pytest(probe=None) -> None:
    """执行前置：pytest 必须可导入，否则 WiringError（fail-closed，不静默降级）。

    `probe` 仅用于注入可探测函数（回归测试模拟缺失环境），生产路径恒用
    importlib.util.find_spec —— 不导入 pytest 本体，避免把异常藏进模块加载。
    """
    find = probe if probe is not None else importlib.util.find_spec
    if find("pytest") is None:
        raise WiringError(
            "PYTEST-MISSING: 缺少 pytest —— 执行 pip install -e . 重新安装依赖"
            "（pytest 是 aos test / aos release 声明的运行时依赖）")
