#!/usr/bin/env python3
"""tools/verify_capability_list.py —— VER-27 支撑工具（能力清单完备性核对）。
核对：三段式结构在位（INV-6/INV-11）· 生成段 provenance 全覆盖（KS-8.2）·
spec_ref == 登记表最新条目（GOV-2.2）· forbidden ↔ 负向测试双射文件在位（P-10）。
exit 0 = 完备；exit 1 = 差异清单（VER-27 item3 判据输入）。
"""
import re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import run_pipeline, load_caps
def main() -> int:
    issues = []
    caps = load_caps()
    if caps.get("foundation") != ["audit_append_only", "perimeter_integrity", "breakglass_resonant"]:
        issues.append("INV-6: foundation ≠ 三项基座")
    if sorted(caps.get("forbidden", [])) != sorted(["modify_foundation", "direct_event_write",
                                                    "history_rewrite", "extinguish_override"]):
        issues.append("INV-11: forbidden ≠ 四项")
    for seg in ("write_actions", "channel_writes"):
        for e in caps.get(seg, []):
            if "provenance" not in e:
                issues.append(f"KS-8.2: {seg}/{e.get('id')} 缺 provenance")
    registry = ROOT / "docs/ARTIFACT-REGISTRY.md"
    rows = [l for l in registry.read_text(encoding="utf-8").splitlines()
            if l.startswith("| AOS-ART-")] if registry.exists() else []
    if rows and caps.get("spec_ref") != rows[-1].split("|")[1].strip():
        issues.append("GOV-2.2: spec_ref 与登记表最新条目不符")
    neg = ROOT / "tests/negative/test_forbidden.py"
    if not neg.exists() or "FORBIDDEN_TESTS" not in neg.read_text(encoding="utf-8"):
        issues.append("P-10: forbidden ↔ 负向测试映射文件缺失")
    try:
        run_pipeline()
    except Exception as e:
        issues.append(f"KS-7.2: 管线 reconcile 失败 —— {e}")
    if issues:
        print("CAPABILITY-LIST-ISSUES:")
        for i in issues: print(f"  - {i}")
        return 1
    n = len(caps.get("write_actions", [])) + len(caps.get("channel_writes", []))
    print(f"CAPABILITY-LIST-OK: {n} 条生成能力 + 固定段完备 + provenance 全覆盖 + spec_ref 一致")
    return 0
if __name__ == "__main__":
    sys.exit(main())
