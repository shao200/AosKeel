"""tests/conformance/test_boolean_profile_semantics.py —— 附录 S 可核对性守卫（S-4 勘误）。

把信息性附录 S 的语义描述落成可证伪断言，防止附录与实现单边漂移：

- S-1：`eval` 对未声明字段/名是**偏函数拒绝**（InterpreterRejected，管线记审计后
  再抛），不是"字段缺失返回 false 的全函数"——两者皆 fail-closed，但语义不同；
- S-2：求值环境仅 snapshot / principal 两源，`now` 不入 env，宿主时钟被禁；
- S-3：S.1 语法是 R10 完整 profile 的**真子集**——实现 AST 白名单另许白名单调用、
  算术与复合字面量；SC 编译器只校验首 token 来源，不把表达式限制在 S.1；
- S-4：`steps(e) ≤ |nodes(e)|` 只对 S.1 片段成立——S.3 参考求值器（带步数计数）对
  生成式样例空间批量断言步数上界并与实现比对一致（v2.2.0：真实计步替代
  "样例有限步返回"的代理指标，N8 勘误的机器核对兑现）；另以 AST 节点计数 +
  深度上限守住旧口径。

本文件不新增 MUST 条款；只把信息性附录的陈述钉在实现上（可证伪、可回归）。
"""
import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))

from interpreter.boolean_profile import (  # noqa: E402
    eval_boolean, _ALLOWED_NODES, _ALLOWED_CALLS, MAX_DEPTH, _namespace,
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


# ---------- S.3 参考求值器（带步数计数）—— S.4 机器核对的兑现点（v2.2.0 / N8） ----------

_S1_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
           ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
           ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}
_S1_IN = {ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


def _ref_eval(node, env):
    """S.3 求值规则的直接实现（S.1 片段）：返回 (值, 步数)。

    步数口径与 S.4 证明逐字一致：Atom（Compare，操作数子求值计入其常数步）
    = 1；`not` = 1 + steps(e)；`and` / `or` = 1 + steps(e1) + steps(e2)
    （最坏情形两侧均求值——短路不保证只走一边，v2.2.0 更正后的上界）。"""
    if isinstance(node, ast.Expression):
        return _ref_eval(node.body, env)
    if isinstance(node, ast.BoolOp):
        vals = [_ref_eval(v, env) for v in node.values]      # 两侧全部求值
        steps = 1 + sum(s for _, s in vals)
        if isinstance(node.op, ast.And):
            return all(v for v, _ in vals), steps
        return any(v for v, _ in vals), steps
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        v, s = _ref_eval(node.operand, env)
        return (not v), 1 + s
    if isinstance(node, ast.Compare):
        table = _S1_CMP if type(node.ops[0]) in _S1_CMP else _S1_IN
        left, _ = _ref_eval(node.left, env)
        right, _ = _ref_eval(node.comparators[0], env)
        return table[type(node.ops[0])](left, right), 1      # Atom = 常数步
    if isinstance(node, ast.Name):
        return env[node.id] if isinstance(env, dict) else getattr(env, node.id), 0
    if isinstance(node, ast.Attribute):
        base, _ = _ref_eval(node.value, env)
        return getattr(base, node.attr), 0
    if isinstance(node, ast.Constant):
        return node.value, 0
    raise AssertionError(f"参考求值器不支持 S.1 之外的节点: {type(node).__name__}")


_REF_ENV = {"snapshot": {"status": "pending", "amount": 500000},
            "principal": {"role": "contract_steward",
                          "contexts": ("ContractContext",)}}


def _s1_sample_space():
    """确定性生成式 S.1 样例空间：原子池 → 逐层 and/or/not 组合（无随机、可复现）。"""
    atoms = [
        "snapshot.status == 'pending'",
        "snapshot.status != 'paid'",
        "snapshot.amount >= 500000",
        "snapshot.amount < 499999",
        "principal.role == 'contract_steward'",
        "'ContractContext' in principal.contexts",
        "'Missing' not in principal.contexts",
    ]
    level1 = (atoms
              + [f"not ({a})" for a in atoms]
              + [f"({a}) and ({b})" for a in atoms for b in atoms]
              + [f"({a}) or ({b})" for a in atoms for b in atoms])
    level2 = ([f"({a}) and ({b})" for a in level1[:12] for b in level1[:12]]
              + [f"({a}) or ({b})" for a in level1[:12] for b in level1[:12]]
              + [f"not ({a})" for a in level1[:12]])
    level3 = ([f"({a}) and ({b})" for a in level2[:10] for b in level2[:10]]
              + [f"({a}) or ({b})" for a in level2[:10] for b in level2[:10]])
    return level1 + level2 + level3


def test_s4_reference_evaluator_steps_within_node_bound_and_agrees_with_impl():
    """S.4 机器核对升级版：对生成式 S.1 样例空间批量断言——
    ① `steps(e) ≤ |nodes(e)|`（真实步数断言，对样例空间的 ∀ 量化）；
    ② 参考求值器与实现 `eval_boolean` 求值结果逐一一致（语义同源）；
    ③ 节点全在白名单、树深 ≤ MAX_DEPTH（静态同源纪律随行）。
    样例空间含深度 ≤ 3 的数千条表达式，确定性可复现。"""
    exprs = _s1_sample_space()
    assert len(exprs) > 500                                   # 样例空间足够大
    for expr in exprs:
        tree = ast.parse(expr, mode="eval")
        nodes = list(ast.walk(tree))
        assert all(type(n) in _ALLOWED_NODES for n in nodes)
        depth = 0
        stack = [(tree, 1)]
        while stack:                                          # 迭代求深（防深表达式递归）
            n, d = stack.pop()
            depth = max(depth, d)
            stack.extend((k, d + 1) for k in ast.iter_child_nodes(n))
        assert depth <= MAX_DEPTH
        ref_val, steps = _ref_eval(tree, _namespace(_REF_ENV))   # ① 参考语义 + 步数
        assert steps <= len(nodes), f"步数上界失守: {expr} steps={steps} nodes={len(nodes)}"
        assert isinstance(ref_val, bool)
        assert ref_val == eval_boolean(expr, _REF_ENV)        # ② 与实现一致
