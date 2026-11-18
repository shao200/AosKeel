#!/usr/bin/env python3
"""tools/release_gate.py —— 智能体发布闸门（缺口 ③：VER-27 前置的 CI 兑现）。
发布 = 制品出库。闸门语义（fail-closed，全绿才出制品）：
  1. 结构层  指纹核对（GOV-2.4）
  2. 密码学层 哈希比对（GOV-2.3，漂移 = 冻结文本被改 → 拒绝）
  3. 注册层  declared == registered（KS-7.2 reconcile）
  4. 测试    config/verification.yaml 全部已布线套件（aos test 等价）
  5. 骨架    codegen 再生成零漂移（声明与代码骨架一致，KS-4.3）
任一失败 → 不出制品、不写清单（fail-closed）；全绿 → dist/RELEASE-MANIFEST.json
（spec_ref / digest / 登记条目 / 能力数 / 各步结果）随制品出库 —— VER-27
"内核加载的是 generated 段"的发布侧对应物。
"""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import fingerprint, codegen, wiring
from tools.hash_spec import (canonical_digest, verify as hs_verify, _entries,
                             decl_digest_skip)
from kernel import registration
def _default_tests() -> str:
    # 承重件统一解析（tools/wiring.py）：正则抠 path 会在合法 YAML 格式微调时
    # 静默丢项，使"全绿"变成少跑一条 VER 的假绿 —— 缺路径一律阻断。
    # 执行引擎缺失同样 fail-closed：明确报 PYTEST-MISSING，不伪装成"套件失败"。
    wiring.require_pytest()
    paths = [p for _, p in wiring.wired_paths()]
    # N5：嵌套 pytest 固定 basetemp 到仓库外隔离目录（可经 AOS_GATE_BASETEMP 覆盖）。
    # 不固定时 pytest 用系统临时目录并自清理，宿主 safe-delete 阈值会让
    # "61 条测试 100% 通过、进程退出码 1"这类不可诊断的绿出现在本可全绿的环境。
    # 每次闸门独立 mkdtemp 且不回收：固定目录会被残留进程的 sqlite 句柄锁死
    # （WinError 32），就地清理又是一次大规模删除。目录留给系统临时目录回收。
    basetemp = os.environ.get("AOS_GATE_BASETEMP") or tempfile.mkdtemp(prefix="aos-gate-")
    # AOS_IN_GATE=1：标记嵌套 pytest 运行于闸门之内。test_real_gate_end_to_end
    # 据此自跳，否则 gate → e2e → gate 无限递归（INTEGRITY-34 补登后实测爆炸）。
    env = {**os.environ, "AOS_IN_GATE": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", f"--basetemp={basetemp}"]
                       + list(dict.fromkeys(paths)),
                       cwd=ROOT, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        tail = "\n".join((r.stdout or "").splitlines()[-25:]
                         + (r.stderr or "").splitlines()[-10:])
        raise RuntimeError(f"pytest exit={r.returncode}（gate 套件失败即不出制品）\n{tail}")
    return f"{len(paths)} 条布线路径全部通过"
def _crypto_step() -> str:
    if hs_verify() != 0:
        raise RuntimeError("哈希漂移（GOV-2.5）")
    if decl_digest_skip():
        # N3：实例未登记声明基线时第四道是 SKIP —— 业务声明（条件阈值/权限/副作用）
        # 的篡改不被密码学门发现。verify() 返回 0 只是三关绿；出制品必须四道全比对。
        raise RuntimeError("第四道声明摘要 SKIP —— 实例未登记 spec/ 声明基线，"
                           "篡改不可检测 → 拒出制品（aos spec register-declarations）")
    return "PASS（正典 + 声明摘要 双比对）"
def _first_fail() -> str:
    fails = fingerprint.check()
    if fails:
        raise RuntimeError(f"{fails}")
    return "PASS"
def run_gate(out_dir: Path | None = None, run_tests=None) -> dict:
    out_dir = Path(out_dir) if out_dir else ROOT / "dist"
    steps: list[dict] = []
    def step(name: str, fn) -> bool:
        try:
            detail = fn(); ok = True
        except Exception as e:
            detail, ok = str(e), False
        steps.append({"step": name, "ok": ok, "detail": detail})
        return ok
    ok = True
    ok &= step("structural", lambda: _first_fail())
    ok &= step("cryptographic", _crypto_step)
    ok &= step("registered", lambda: f"declared==registered · {len(registration.run_pipeline()['write_actions'])} 能力")
    ok &= step("tests", run_tests or _default_tests)
    ok &= step("codegen", lambda: f"骨架字节级零漂移 · {len(codegen.generate()['files'])} 文件")
    caps_text = (ROOT / "config/capabilities.yaml").read_text(encoding="utf-8")
    m = re.search(r"spec_ref:\s*(AOS-ART-\d+)", caps_text)
    manifest = {
        "released_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "spec_ref": m.group(1) if m else "UNKNOWN",
        "digest": f"sha256:{canonical_digest()}",
        "registry_entry": (_entries()[-1].split("|")[1].strip() if _entries() else "NONE"),
        "steps": steps,
    }
    if not ok:
        return {"ok": False, "manifest": None, "steps": steps}
    out_dir.mkdir(exist_ok=True)
    (out_dir / "RELEASE-MANIFEST.json").write_bytes(
        json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
    return {"ok": True, "manifest": out_dir / "RELEASE-MANIFEST.json", "steps": steps}
def main() -> int:
    report = run_gate()
    for s in report["steps"]:
        print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}: {s['detail']}")
    from tools import gate_history                     # 度量留档（派生件，不判定）
    gate_history.record("release",
                        {s["step"]: "PASS" if s["ok"] else "FAIL"
                         for s in report["steps"]})
    if not report["ok"]:
        print("RELEASE-REFUSED: 闸门未全绿 —— 不出制品（fail-closed，VER-27 前置）")
        return 1
    print(f"RELEASED: 制品清单已落档 {report['manifest']}")
    return 0
if __name__ == "__main__":
    sys.exit(main())
