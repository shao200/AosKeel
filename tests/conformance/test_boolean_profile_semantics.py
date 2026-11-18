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


def test_s3_s1_grammar_is_strict_subset_of_r10_profile():
    """S-3：S.1 是 R10 真子集——白名单含调用/算术/复合字面量，编译器不强制 S.1。"""
    # 实现白名单超出 S.1（Atom 仅比较 + CONTAINS，Expr 仅 not/and/or）
    assert {"len", "sorted", "all"} <= _ALLOWED_CALLS
    assert {ast.Call, ast.BinOp, ast.Tuple, ast.List, ast.Dict} <= set(_ALLOWED_NODES)
    # SC 编译器只校验首 token 来源（R2），不把表达式限制在 S.1 文法内
    compiled = compile_action(
        {"action_type": "X", "aggregate": "A", "submission_criteria": {
            "conditional": {"expression": "snapshot.amount + 1 > 0"}}}, "genesis")
    assert compiled.conditional == "snapshot.amount + 1 > 0"   # 算术式通过编译


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
