"""tests/conformance/test_boolean_profile_semantics.py —— 附录 S 可核对性守卫（S-4 勘误）。

把信息性附录 S 的语义描述落成可证伪断言，防止附录与实现单边漂移：

- S-1：`eval` 对未声明字段/名是**偏函数拒绝**（InterpreterRejected，管线记审计后
  再抛），不是"字段缺失返回 false 的全函数"——两者皆 fail-closed，但语义不同；
- S-2：求值环境仅 snapshot / principal 两源，`now` 不入 env，宿主时钟被禁；
- S-3：S.1 语法是 R10 完整 profile 的**真子集**——实现 AST 白名单另许白名单调用、
  算术与复合字面量；SC 编译器只校验首 token 来源，不把表达式限制在 S.1；
- S-4：`steps(e) ≤ |nodes(e)|` 只对 S.1 片段成立——用 AST 节点计数 + 深度上限 +
  实际求值返回，使"终止性可核对"从宣称落地为测试。

本文件不新增 MUST 条款；只把信息性附录的陈述钉在实现上（可证伪、可回归）。
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))

from interpreter.boolean_profile import (  # noqa: E402
    eval_boolean, _ALLOWED_NODES, _ALLOWED_CALLS, MAX_DEPTH,
)
from kernel.errors import InterpreterRejected  # noqa: E402
from kernel.sc_compiler import compile_action  # noqa: E402

ENV = {"snapshot": {"status": "pending", "amount": 500000},
       "principal": {"role": "contract_steward", "contexts": ("ContractContext",)}}


def test_s1_missing_field_rejects_not_false():
    """S-1：字段缺失 = InterpreterRejected（拒绝），不是求值为 false。"""
    with pytest.raises(InterpreterRejected, match="UNDECLARED-NAME"):
        eval_boolean("snapshot.undefined_field == 1", ENV)


def test_s2_env_has_only_two_sources_no_now():
    """S-2：求值环境仅 snapshot/principal；now 不入 env，时钟源被拒。"""
    assert set(ENV) == {"snapshot", "principal"}
    for expr in ("now.year == 2026", "time.time() > 0"):
        with pytest.raises(InterpreterRejected):
            eval_boolean(expr, ENV)


def test_s3_whitelisted_calls_reachable_and_compiler_not_restricted_to_s1():
    """S-3：S.1 是 R10 真子集——白名单调用**真实可求值**（N2 修复），SC 编译器
    不把表达式限制在 S.1。

    N2 修复前：_lint 把函数名当数据源收进 R2 根集合，9/9 白名单调用全部
    SOURCE-FORBIDDEN——冻结附录 S 描述的语言在运行时不存在，而本文件的
    旧守卫只断言集合成员，用代理指标为不存在的语言背书。现以"实际求值成功"
    正例锁住语言能力（第五轮评议冻结前强制门 ② 的兑现）。"""
    assert {"len", "sorted", "all"} <= _ALLOWED_CALLS
    assert {ast.Call, ast.BinOp, ast.Tuple, ast.List, ast.Dict} <= set(_ALLOWED_NODES)
    env = {"snapshot": {"tags": ["b", "a"], "amounts": [300, 900], "amount": 500000},
           "principal": {"role": "contract_steward", "contexts": ("ContractContext",)}}
    assert eval_boolean("len(snapshot.tags) == 2", env) is True            # 调用可求值
    assert eval_boolean("sorted(snapshot.tags) == ['a', 'b']", env) is True  # sorted 可达
    assert eval_boolean("max(snapshot.amounts) == 900", env) is True
    assert eval_boolean("any(snapshot.tags)", env) is True
    with pytest.raises(InterpreterRejected):                              # 源封闭不放松
        eval_boolean("len(time)", env)                                    # 禁用名仍拒
    with pytest.raises(InterpreterRejected):
        eval_boolean("open('x')", env)                                    # 非白名单调用仍拒
    # SC 编译器只校验首 token 来源（R2），不把表达式限制在 S.1 文法内
    compiled = compile_action(
        {"action_type": "X", "aggregate": "A", "submission_criteria": {
            "conditional": {"expression": "snapshot.amount + 1 > 0"}}}, "genesis")
    assert compiled.conditional == "snapshot.amount + 1 > 0"   # 算术式通过编译


def test_n1_non_boolean_predicate_rejected_not_coerced():
    """N1：非谓词值表达式不得经 bool() 强转恒真放行——条件必须求值为 bool。

    修复前 snapshot.amount / snapshot.amount + 1 均被静默求值为 True 放行提交，
    是唯一影响提交门放行方向的缺陷；真谓词行为不变。"""
    for expr in ("snapshot.amount", "snapshot.status", "snapshot.amount + 1"):
        with pytest.raises(InterpreterRejected, match="NON-BOOLEAN-PREDICATE"):
            eval_boolean(expr, ENV)
    assert eval_boolean("snapshot.amount >= 10**6", ENV) is False          # 真谓词不受影响
    assert eval_boolean("not snapshot.amount >= 10**6", ENV) is True


def test_s4_s1_fragment_terminates_within_ast_node_bound():
    """S-4：S.1 片段 AST 节点计数有界 + 深度受限 + 实际求值返回 = 停机可核对。"""
    for expr in (
        "snapshot.status == 'pending'",
        "not snapshot.amount >= 10**6",
        "snapshot.status == 'pending' and snapshot.amount < 10**6",
    ):
        tree = ast.parse(expr, mode="eval")
        nodes = list(ast.walk(tree))
        assert 0 < len(nodes) < 64                              # 节点计数有界
        assert all(type(n) in _ALLOWED_NODES for n in nodes)     # 全在白名单内

        def _depth(node):   # 与解释器 _lint 同口径：根 = 0，逐层 +1
            kids = list(ast.iter_child_nodes(node))
            return 0 if not kids else 1 + max(_depth(k) for k in kids)

        assert _depth(tree) <= MAX_DEPTH
        assert isinstance(eval_boolean(expr, ENV), bool)        # 有限步内返回
