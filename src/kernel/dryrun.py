"""src/kernel/dryrun.py —— 演练模拟器（P-12 / VER-25）。
dry-run = 模拟整条提交管线（能力/权限 → 结构 → 条件 → 版本预演）并产出
DRYRUN-REPORT：可重复（两次同输入 → 同报告）、逐项留档、绝不追加事件、
不产生 structurally-rejected 审计副作用（演练不污染审计流）。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.sc_compiler import run_structural
from interpreter.boolean_profile import eval_boolean
def dryrun(kernel, action_type: str, params: dict, principal: str,
           roles: tuple[str, ...] = ()) -> dict:
    act = kernel.compiled.get(action_type)
    report: dict = {"action": action_type, "would_commit": False,
                    "checks": {}, "expected_version": None, "stream": None,
                    "reason": None}
    if act is None:                                     # INV-1
        report["reason"] = "unregistered: 不注册即不可执行（INV-1）"
        return report
    required = set(act.permissions.get("roles", []))
    if required and not (required & set(roles)):        # 能力/权限（与 submit 同序）
        report["checks"]["capability"] = "fail"
        report["reason"] = (f"permission: 要求角色 {sorted(required)}，"
                            f"出示 {sorted(set(roles)) or '∅'}（P-10 / INV-4）")
        return report
    report["stream"] = act.stream
    report["expected_version"] = len(kernel.store.streams.get(act.stream, []))
    try:                                                # 结构（KS-7.1 第一段）
        run_structural(act.structural, params)
        report["checks"]["structural"] = "pass"
    except ValueError as e:
        report["checks"]["structural"] = "fail"
        report["reason"] = f"structural: {e}"
        return report
    if act.conditional:                                 # 条件（R2 快照；不入评估审计）
        snap_keys = act.snapshot_keys            # 来源分类在编译期定死（R2）
        env = {"snapshot": {k: params.get(k) for k in snap_keys},
               "principal": {"role": principal}}
        try:
            ok = eval_boolean(act.conditional, env)
        except Exception as e:
            report["checks"]["conditional"] = "fail"
            report["reason"] = f"interpreter: {e}"
            return report
        report["checks"]["conditional"] = "pass" if ok else "fail"
        if not ok:
            report["reason"] = f"conditional: {act.conditional}"
            return report
    report["checks"]["capability"] = "pass"              # 权限已在前面强制
    report["would_commit"] = True                       # P-12：仅报告，不追加
    return report
