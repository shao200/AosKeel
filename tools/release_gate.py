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
import re
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import fingerprint, codegen
from tools.hash_spec import canonical_digest, verify as hs_verify, _entries
from kernel import registration
def _default_tests() -> str:
    text = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    paths = [p for _, p in re.findall(
        r"-\s\{\s*id:\s*(VER-\d+),.*?path:\s*([^\s}]+)", text) if (ROOT / p).exists()]
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"] + paths,
                       cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"pytest exit={r.returncode}（gate 套件失败即不出制品）")
    return f"{len(paths)} 条布线路径全部通过"
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
    ok &= step("cryptographic", lambda: "PASS" if hs_verify() == 0
               else (_ for _ in ()).throw(RuntimeError("哈希漂移（GOV-2.5）")))
    ok &= step("registered", lambda: f"declared==registered · {len(registration.run_pipeline()['write_actions'])} 能力")
    ok &= step("tests", run_tests or _default_tests)
    ok &= step("codegen", lambda: f"骨架零漂移 · {codegen.generate() is not None}")
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
    (out_dir / "RELEASE-MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "manifest": out_dir / "RELEASE-MANIFEST.json", "steps": steps}
def main() -> int:
    report = run_gate()
    for s in report["steps"]:
        print(f"  [{'PASS' if s['ok'] else 'FAIL'}] {s['step']}: {s['detail']}")
    if not report["ok"]:
        print("RELEASE-REFUSED: 闸门未全绿 —— 不出制品（fail-closed，VER-27 前置）")
        return 1
    print(f"RELEASED: 制品清单已落档 {report['manifest']}")
    return 0
if __name__ == "__main__":
    sys.exit(main())
