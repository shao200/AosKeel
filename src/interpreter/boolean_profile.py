"""src/interpreter/boolean_profile.py —— 布尔档受限解释器（R10 / KS-3.2 / VER-8）。
AST 节点白名单 + 调用函数白名单 + 深度上限（R8 同源预算纪律）；
执行环境 __builtins__ 置空 —— 非白名单结构 = InterpreterRejected（fail-closed）。
纯性不可证明、只可执行核对：本模块就是"解释器实现的正确性"那条诚实边界的兑现点。
"""
from __future__ import annotations
import ast
from types import SimpleNamespace
from kernel.errors import InterpreterRejected
MAX_DEPTH = 16
_ALLOWED_NODES = tuple({ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
                        ast.Compare, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq,
                        ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.BinOp, ast.Add, ast.Sub,
                        ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.Constant,
                        ast.Name, ast.Attribute, ast.Load, ast.Tuple, ast.List,
                        ast.Call, ast.keyword, ast.Dict})
_ALLOWED_CALLS = {"len", "all", "any", "min", "max", "sum", "abs", "round", "sorted"}
_FORBIDDEN_NAMES = {"open", "eval", "exec", "compile", "__import__", "input", "globals",
                    "locals", "vars", "getattr", "setattr", "delattr", "time", "random",
                    "os", "sys", "subprocess", "socket", "importlib", "builtins"}
def _lint(node, depth: int = 0) -> None:
    if depth > MAX_DEPTH:                       # R8 预算纪律的静态同源
        raise InterpreterRejected("DEPTH-LIMIT: 表达式深度超限（R8）")
    if not isinstance(node, _ALLOWED_NODES):
        raise InterpreterRejected(f"NODE-FORBIDDEN: {type(node).__name__} 不在布尔档白名单（R10）")
    if isinstance(node, ast.Call):
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else (
            fn.attr if isinstance(fn, ast.Attribute) else None)
        if name not in _ALLOWED_CALLS:
            raise InterpreterRejected(f"CALL-FORBIDDEN: {name} 不在布尔档函数白名单（R10）")
    if isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
        raise InterpreterRejected(f"NAME-FORBIDDEN: {node.id}（R1 输入封闭 / R4-R6 无时钟）")
    if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
        # dunder 属性链（__class__/__base__ 等）可遍历类型结构 —— R1 输入封闭禁止
        raise InterpreterRejected(
            f"ATTRIBUTE-FORBIDDEN: {node.attr} dunder 属性访问（R1 输入封闭）")
    for child in ast.iter_child_nodes(node):
        _lint(child, depth + 1)
def eval_boolean(expr: str, env: dict) -> bool:
    """受限求值：仅允许 snapshot.* 与 principal.* 两源（R2），
    环境缺名 = InterpreterRejected（R1 输入封闭，拒绝谓词性猜测）。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise InterpreterRejected(f"PARSE-FAIL: {e}") from e
    _lint(tree)
    root = tree.body
    for name in _collect_roots(root):           # R2：仅此二源
        if name.split(".")[0] not in ("snapshot", "principal"):
            raise InterpreterRejected(f"SOURCE-FORBIDDEN: {name} 必须起于 snapshot./principal.（R2）")
    sandbox = {"__builtins__": {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                                for k in _ALLOWED_CALLS}}
    env = {k: _namespace(v) for k, v in env.items()}    # 快照对象化：支持 snapshot.x 属性访问
    try:
        result = eval(compile(tree, "<boolean_profile>", "eval"), sandbox, env)
    except NameError as e:
        raise InterpreterRejected(f"UNDECLARED-NAME: {e}（R1 输入封闭）") from e
    except AttributeError as e:                          # 未声明字段的属性访问 = 未声明名（R1）
        raise InterpreterRejected(f"UNDECLARED-NAME: {e}（R1 输入封闭）") from e
    except (TypeError, ZeroDivisionError) as e:
        raise InterpreterRejected(f"EVAL-FAIL: {e}") from e
    return bool(result)
def _namespace(v):
    """dict → SimpleNamespace（递归）；其余原样。"""
    if isinstance(v, dict):
        return SimpleNamespace(**{k: _namespace(x) for k, x in v.items()})
    if isinstance(v, list):
        return [_namespace(x) for x in v]
    return v
def _collect_roots(node) -> set:
    roots = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            roots.add(sub.id)
    return roots
