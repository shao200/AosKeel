"""src/kernel/upcasting.py —— 读时升级（KS-5.2-5.4 / VER-13 / VER-14）。
事件结构版本化（KS-5.1）；升级在读时发生：
- 注册表 {(event_type, from_version) → upcaster}；升级是纯映射（R11 / KS-3.4）；
- 未注册的升级路径 = 读失败（fail-closed，KS-5.2 / VER-13）——不做任何猜测；
- 交付契约（KS-5.3）：升级链输出结构被 golden 锚定（VER-14）；
- 无事件删除/改写（AX-3）：升级不改写日志，只改读出形态。
"""
from __future__ import annotations
from kernel.errors import UpcastingFailed
_CHAINS: dict[tuple[str, int], object] = {}
CURRENT: dict[str, int] = {"Order": 3, "Contract": 1}  # 各类型当前交付 schema 版本（与示例域同源）
def register_upcaster(event_type: str, from_version: int, fn):
    """fn: payload -> payload 纯映射；含副作用/读环境的 upcaster 在实例侧注册即拒
    （模板层以行为核对：同输入必同输出，见 VER-14 golden）。"""
    _CHAINS[(event_type, int(from_version))] = fn
def reset_registry():
    """测试钩子：清空注册表（生产代码不得调用——升级路径只增）。"""
    _CHAINS.clear()
def upcast(event_type: str, version: int, payload: dict) -> tuple[int, dict]:
    """沿注册链升到当前交付版本；无路径即拒（fail-closed）。"""
    v, data = int(version), dict(payload)
    while (event_type, v) in _CHAINS:
        data = dict(_CHAINS[(event_type, v)](data))     # 纯映射，不改写入参
        v += 1
    target = CURRENT.get(event_type)
    if target is not None and v != target:
        raise UpcastingFailed(
            f"UPCAST-PATH-MISSING: {event_type}@{version} 只能升到 @{v}，"
            f"当前交付为 @{target} —— 无升级路径即读失败（KS-5.2 / VER-13）")
    return v, data
