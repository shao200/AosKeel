"""src/interpreter/mapping_profile.py —— 映射档受限解释器（R11 / KS-3.2 / VER-9）。
声明式字段映射：rename / drop / const 三算子，纯数据驱动；
结构上不存在谓词分派入口 —— 判断在映射型中不可表达（KS-3.2）。
"""
from __future__ import annotations
def apply_field_map(record: dict, field_map: dict, drop: list | None = None,
                    const: dict | None = None) -> dict:
    """声明式字段映射（无谓词分派）：
    field_map {src: dst} 改名；drop 列表丢弃；const 注入常量。未映射键原样保留。"""
    out = {}
    dropped = set(drop or [])
    for k, v in record.items():
        if k in dropped:
            continue                             # 语义损耗 MUST 已在 mapping 声明（KS-4）
        out[field_map.get(k, k)] = v
    for k, v in (const or {}).items():
        out[k] = v
    return out
def profile_has_predicate_dispatch() -> bool:
    """结构自检：映射档不存在谓词分派 API（VER-9 断言的机械依据）。"""
    return False
