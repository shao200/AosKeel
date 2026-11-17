#!/usr/bin/env python3
"""一键复现 LLM-in-the-loop 全链路（可离线、零密钥、零网络）。

在模板根执行：python docs/samples/llm/run_demo.py

做三件事并对每步断言，任一步不符即非零退出（fail-closed）：
  1. 模板根权威门禁：aos verify 三关（正典 + 声明摘要双比对）
  2. 反例：LLM 载荷直写存储被拒 + 留审计
  3. 实例内契约：init → BOOT-0 → 适配器 extract → promote（无提案拒绝 / 有提案成功）
     → 声明摘要登记 → CQ-10 复验

验证范围限定为「模板根权威门禁 + 实例内契约行为」，不声称干净实例的
test/release 全套全绿（实例裁剪的既有边界，见 04 教程与同目录 README）。
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent
ROOT = SAMPLES.parents[2]
PY = sys.executable
MAIN = "src/cli/main.py"


def run(args, cwd, expect=None, label=""):
    """执行一步，返回 stdout+stderr；给了 expect 就断言其子串在场。"""
    proc = subprocess.run([PY, *args], cwd=str(cwd), capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    tag = label or " ".join(args[:3])
    ok = proc.returncode == 0 and (expect is None or expect in out)
    print(f"[{'OK' if ok else 'FAIL'}] {tag}" + (f" —— 缺字样 {expect!r}" if expect and expect not in out else ""))
    if not ok:
        print("---- output ----\n" + out[-1200:])
        raise SystemExit(1)
    return out


def main() -> int:
    print("== 模板根权威门禁 ==")
    run([MAIN, "verify"], ROOT, expect="VERIFY-OK", label="aos verify 三关")

    print("== 反例：直写被拒 ==")
    run([str(SAMPLES / "gate_rejection_demo.py")], ROOT,
        expect="GATE-DEMO: PASS", label="LLM 载荷直写被拒")

    with tempfile.TemporaryDirectory(prefix="aos-llm-demo-") as td:
        inst = Path(td) / "instance"
        print(f"== 实例内契约（{inst.name}）==")
        run([MAIN, "init", str(inst)], ROOT, expect="INITIALIZED")
        run([MAIN, "bootstrap", "--stage", "0"], inst, expect="BOOT-0-DONE")

        mat = inst / "docs/samples/llm/llm_material.txt"
        adp = inst / "docs/samples/llm/llm_extractor.py"
        mat.parent.mkdir(parents=True, exist_ok=True)
        mat.write_text((SAMPLES / "llm_material.txt").read_text(encoding="utf-8"),
                       encoding="utf-8")
        adp.write_text((SAMPLES / "llm_extractor.py").read_text(encoding="utf-8"),
                       encoding="utf-8")

        run([MAIN, "extract", str(mat), "--name", "ledger", "--extractor", str(adp)],
            inst, expect="EXTRACT-DRAFT", label="适配器 extract → 草案")

        draft = inst / "spec/drafts/draft-ledger.yaml"
        # 反例：无治理提案 → 拒绝
        p = subprocess.run([PY, MAIN, "draft", "promote", str(draft)],
                           cwd=str(inst), capture_output=True, text=True)
        no_ref_ok = p.returncode != 0 and "proposal-ref" in (p.stdout + p.stderr)
        print(f"[{'OK' if no_ref_ok else 'FAIL'}] promote 无提案被拒")
        if not no_ref_ok:
            print("---- output ----\n" + (p.stdout + p.stderr)[-800:])
            raise SystemExit(1)

        run([MAIN, "draft", "promote", str(draft),
             "--proposal-ref", "SPEC-2026-LLMDemo"],
            inst, expect="PROMOTED", label="promote 带提案成功")

        # 声明摘要登记后 CQ-10 才成立（干净实例故意不复制登记表）
        run([MAIN, "spec", "register-declarations", "v0.3.0"], inst)
        run([MAIN, "cq", "run", "CQ-10"], inst, expect="[PASS] CQ-10",
            label="声明摘要登记 → CQ-10 复验")

    print("DEMO-OK: LLM 候选过闸 / 直写被拒 / 治理提案强制 —— 三条证据全部兑现")
    return 0


if __name__ == "__main__":
    sys.exit(main())
