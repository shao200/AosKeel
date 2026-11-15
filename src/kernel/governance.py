#!/usr/bin/env python3
"""src/kernel/governance.py —— 治理层（GOV-3 / GOV-4 / KV-4）。
生效重跑（GOV-4 / KV-4）：治理 Action 生效事件必须通过注册管线重跑
（declared == registered）；失败 → 生效被阻断，并产生 governance 类违规对象
（经 RaiseInvariantViolation 写入，P-7 / INV-10 —— 违规即对象，非日志行）。
版本通道（GOV-3）：规范变更经提案 → 新版本登记（aos spec version，CLI 化）；
冻结文本不就地修改（GOV-2.5 / P-15：登记表 append-only）。
"""
from __future__ import annotations
import datetime as dt
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import RegistrationFailed
from kernel.registration import run_pipeline
VIOLATION_STREAM = "domain:invariant"
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class GovernanceLedger:
    def __init__(self, store):
        self.store = store
    def record_effective(self, action_ref: str, proposal_ref: str, principal: str) -> dict:
        """GOV-4：治理 Action 生效 → 重跑注册管线。失败即阻断 + 违规对象化。"""
        if not action_ref or not proposal_ref:
            raise RegistrationFailed(
                "GOV-4-REFS-REQUIRED: 生效事件 MUST 绑定 (action_ref, proposal_ref)")
        try:
            gen = run_pipeline()                        # KV-4：重跑五步管线
        except RegistrationFailed as e:
            self.store.commit(                          # 生效被阻断 + 违规即对象（P-7）
                "RaiseInvariantViolation", VIOLATION_STREAM,
                len(self.store.streams.get(VIOLATION_STREAM, [])),
                "InvariantViolation@1",
                {"valid_time": _now(),
                 "invariant_ref": "GOV-4-effective-rerun",
                 "classification": "governance",
                 "status": "detected",
                 "violated_on": {"action_ref": action_ref, "proposal_ref": proposal_ref},
                 "reason": str(e),
                 "repair": "GOV-3-version-channel"},
                principal)
            raise                                       # 生效被阻断（fail-closed）
        return {"effective": action_ref, "proposal": proposal_ref,
                "rerun": "passed",
                "capabilities": len(gen["write_actions"])}
