"""src/kernel/saga.py —— 跨聚合编排（P-9 / Process 唯一合法出口）。
编排 = Process 声明驱动：步序仅消费已注册 Action（KS-7.2 编译产物）；
补偿 = 追加补偿事件，补偿本身是 Action（幂等，P-9）；
步失败 → 已完成步按声明逆序补偿 → 原异常继续抛出（编排失败即整体失败）。
"""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.errors import SagaInvalid
class SagaRunner:
    def __init__(self, kernel, processes: dict[str, dict]):
        self.kernel = kernel
        self.processes: dict[str, dict] = {}
        for name, decl in processes.items():
            for step in decl.get("steps", []):
                if step.get("action") not in kernel.compiled:
                    raise SagaInvalid(f"PROCESS-INVALID: {name} 步骤 {step.get('action')} "
                                      f"未注册（编排仅可消费已编译 Action，P-9）")
            for comp in decl.get("compensations", []) or []:
                if comp.get("action") not in kernel.compiled:
                    raise SagaInvalid(f"PROCESS-INVALID: {name} 补偿 {comp.get('action')} "
                                      f"未注册（补偿本身必须是已注册 Action，P-9）")
            self.processes[name] = decl
        self.compensation_log: list[dict] = []
    @classmethod
    def from_spec(cls, kernel, spec_dir: Path):
        try:
            import yaml
        except ImportError as e:
            raise SagaInvalid("pyyaml 缺失（spec/ 声明解析需要）") from e
        processes = {}
        for p in sorted((spec_dir / "processes").glob("*.yaml")):
            d = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            processes[d.get("process", p.stem)] = d
        return cls(kernel, processes)
    def _compensation_for(self, action_type: str) -> dict | None:
        for comp in self.processes.get(self._current, {}).get("compensations", []) or []:
            if comp.get("for") == action_type:
                return comp
        return None
    _current: str = ""
    def run(self, process: str, params: dict, principal: str,
            roles: tuple[str, ...] = ()) -> list:
        if process not in self.processes:
            raise SagaInvalid(f"PROCESS-UNKNOWN: {process}（P-9：编排唯一合法出口 = Process 声明）")
        self._current = process
        completed: list[str] = []
        try:
            for step in self.processes[process]["steps"]:
                self.kernel.submit(step["action"], params, principal, roles=roles)
                completed.append(step["action"])
            return completed
        except Exception:
            for done in reversed(completed):            # 已完成步逆序补偿
                comp = self._compensation_for(done)
                if comp:
                    rec = self.kernel.submit(comp["action"], params, principal, roles=roles)
                    self.compensation_log.append({"for": done, "action": comp["action"],
                                                  "event_id": rec.event_id})
            raise                                        # 编排失败即整体失败（fail-closed）
