#!/usr/bin/env python3
"""src/kernel/genesis.py —— 创世窗口（KS-8 / AX-4 / GOV-1）。
创制任命是世界事件：本模块只接收其审计凭据引用（appointment_ref），不合成任命。
状态机（KS-8.5 / T20-T22）：
  open    —（TTL 到期且治理周期未闭环）→ frozen
  frozen  —（治理周期闭环 KS-8.4）→ extinguished
  open    —（治理周期闭环）→ extinguished
熄灭后：predicate 永久为假；类上不存在 revive/reopen 路径，再授权凭据重放必拒
（KS-8.2 / VER-28 item4 / INV-11 extinguish_override）。
"""
from __future__ import annotations
import datetime as dt
import time
class GenesisFrozen(Exception): ...
class GenesisExtinguished(Exception): ...
def _ts() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class GenesisWindow:
    def __init__(self, appointment_ref: str, ttl_seconds: float, now_fn=time.time):
        if not appointment_ref:
            raise ValueError("REFUSED: 创制任命凭据引用必填——CLI 只记录，不合成创制任命（GOV-1 / 护栏一）")
        self.appointment_ref = appointment_ref
        self.ttl_seconds = ttl_seconds
        self._now = now_fn
        self._opened_at = now_fn()
        self._governance_closed = False
        self._state = "open"
        self.timestamps: dict[str, str] = {"opened": _ts()}   # KS-8.4 三项在案之基
        self.audit: list[dict] = []                            # 只增（P-15）
    def _check_ttl(self):
        if self._state == "open" and self._now() - self._opened_at > self.ttl_seconds:
            self._state = "frozen"                              # 创世冻结（T21，可逆）
            self.timestamps["frozen"] = _ts()
            self.audit.append({"kind": "genesis-frozen", "tx": self.timestamps["frozen"]})
    def predicate(self) -> bool:
        """KS-8.2：'治理工作流尚未闭环' —— 先于每次 GenesisWrite 求值（VER-19）。"""
        self._check_ttl()
        return self._state == "open" and not self._governance_closed
    def reactivate(self, credentials: str):
        """创世冻结再启用（T21）：仅创制任命主体 + 记为新审计事件。"""
        self._check_ttl()
        if self._state == "extinguished":
            raise GenesisExtinguished(
                "EXTINGUISH-OVERRIDE-FORBIDDEN: 创世已熄灭，内核不存在任何重启用路径，"
                "再授权凭据对此无效（KS-8.2 / INV-11）")
        if self._state == "frozen" and credentials == self.appointment_ref:
            self._state = "open"
            self._opened_at = self._now()               # 再授权 = 新窗口起点（T21：否则立即再冻结）
            self.timestamps["opened"] = _ts()
            self.audit.append({"kind": "genesis-reactivated", "tx": _ts()})
            return
        raise PermissionError("再授权凭据与创制任命主体不符（KS-8.5）")
    def close_governance_cycle(self):
        """KS-8.4：完整治理周期闭环 → 创世熄灭（不可逆；故意不提供恢复路径）。"""
        if self._governance_closed:
            return
        self._governance_closed = True
        self._state = "extinguished"                            # T22，不可逆
        self.timestamps["closed"] = _ts()
        self.timestamps["extinguished"] = _ts()
        self.audit.append({"kind": "genesis-extinguished", "tx": self.timestamps["extinguished"]})
    def genesis_write(self, batch: dict) -> str:
        """GenesisWrite 能力（KS-8.3：仅治理上下文内建对象）。"""
        if self._state == "extinguished":
            raise GenesisExtinguished("创世已熄灭（KS-8.2）")
        if not self.predicate():
            raise GenesisFrozen("创世窗口冻结——TTL 到期，须再授权（KS-8.5）")
        self.audit.append({"kind": "genesis-write", "objects": sorted(batch),
                           "tx": _ts()})
        return f"genesis-batch-{len(self.audit)}"
