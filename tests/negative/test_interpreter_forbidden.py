"""tests/negative/test_interpreter_forbidden.py —— VER-8：解释器禁止宿主语义（KS-3.2 / R1-R10）。
布尔档 AST 白名单：文件/时钟/随机/反射/动态导入/未声明名 = InterpreterRejected。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from interpreter.boolean_profile import eval_boolean
from kernel.errors import InterpreterRejected
ENV = {"snapshot": {"status": "pending", "amount": 500000},
       "principal": {"role": "contract_steward"}}
def test_no_io():
    with pytest.raises(InterpreterRejected):
        eval_boolean("open('/etc/passwd')", ENV)               # R1 输入封闭
def test_no_clock_or_random():
    for expr in ("time.time() > 0", "random.random() > 0"):    # R4-R6 无时钟无随机
        with pytest.raises(InterpreterRejected):
            eval_boolean(expr, ENV)
def test_no_dynamic_import_or_reflection():
    for expr in ("__import__('os')", "getattr(snapshot, 'status')"):
        with pytest.raises(InterpreterRejected):
            eval_boolean(expr, ENV)
def test_undeclared_name_rejected():
    with pytest.raises(InterpreterRejected, match="UNDECLARED-NAME"):
        eval_boolean("snapshot.undefined_field == 1", ENV)     # R1：拒绝谓词性猜测
def test_pure_boolean_ok():
    """合法受控行为：白名单算子 + 两源（R2）内自由表达。"""
    assert eval_boolean("snapshot.status == 'pending' and snapshot.amount < 10**6", ENV)
    assert not eval_boolean("principal.role == 'nobody'", ENV)
