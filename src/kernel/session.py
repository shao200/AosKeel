"""src/kernel/session.py —— 会话事件流（KS-2.2 / KS-2.3 / INV-8 / VER-4 / VER-5）。
另一对象 = 另一存储（KS-2.2）：会话流与本体事件日志（EventStore）无任何共享结构 ——
物理分离，非本体状态，不参与任何投影的权威重建（projection.py 另有源级排除防御）。
仅追加"观测记录"，逐条强制主体归属（KS-2.3 / INV-8）；
提供 exists() 供决策双引用（KS-2.5）解析；read_all 仅限审计用途。
"""
from __future__ import annotations
import datetime as dt
import sys
import os                                                 # ADR-001: kernel 包 ROOT 外置注入
from pathlib import Path
ROOT = Path(os.environ.get("AOSKEEL_ROOT") or Path(__file__).resolve().parents[2])
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import PrincipalRequired
def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
class SessionChannel:
    def __init__(self):
        caps_path = ROOT / "config/capabilities.yaml"
        text = caps_path.read_text(encoding="utf-8") if caps_path.exists() else ""
        self._principal_required = "SessionAppend" in text   # 能力清单声明（KS-2.3）
        self._log: list[dict] = []          # 独立存储；与 EventStore.streams 无共享
    def append(self, principal: str, payload: dict) -> dict:
        if self._principal_required and not principal:
            raise PrincipalRequired("SESSION-PRINCIPAL-REQUIRED（KS-2.3 / INV-8）")
        rec = {"principal": principal, "ts": _now(), **payload}
        self._log.append(rec)               # append-only；无更新/删除路径
        return rec
    def exists(self, ref: str) -> bool:
        """决策双引用的会话半边可解析（KS-2.5 / VER-7）。"""
        return any(str(r.get("ts")) == str(ref) for r in self._log)
    def read_all(self) -> list[dict]:
        """仅限审计用途（KS-2.4：闭包禁读会话内容 —— 投影不得调用本方法）。"""
        return list(self._log)
