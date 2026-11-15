"""tests/negative/test_mapping_profile.py —— VER-9：映射档无谓词分派（KS-3.2 / R11）。
映射 = 声明式字段映射三算子（rename/drop/const），结构上不存在判断分派入口；
语义损耗 MUST 先声明（KS-4 / mapping.yaml 的 semantic_loss_declared）。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from interpreter.mapping_profile import apply_field_map, profile_has_predicate_dispatch
def test_field_map_semantics():
    rec = {"crm_amount": 100, "crm_status": "ok", "crm_internal_note": "x", "extra": 1}
    out = apply_field_map(rec, {"crm_amount": "amount", "crm_status": "status"},
                          drop=["crm_internal_note"], const={"source": "CRM"})
    assert out == {"amount": 100, "status": "ok", "extra": 1, "source": "CRM"}
def test_no_predicate_dispatch():
    """结构自检：映射档不存在谓词分派 API（判断在映射型中不可表达，KS-3.2）。"""
    assert profile_has_predicate_dispatch() is False
    import inspect
    sig = inspect.signature(apply_field_map)
    empty = inspect.Parameter.empty
    assert all(not (v.default is not empty and callable(v.default))
               for v in sig.parameters.values())          # 参数不含函数默认值
