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
def _lint(node, depth: int = 0, roots: set | None = None) -> None:
    """单遍遍历：白名单/深度/调用/dunder 校验 + 收集全部 Name（R2 源检查同源）。

    白名单函数名（len/sorted/…）不是数据源：作为 Call.func 出现时不入 R2 根集合
    （否则 9 个白名单调用整体不可达，冻结附录 S 描述的语言在运行时不存在），
    但仍走 NAME-FORBIDDEN 检查；调用参数照常入根 —— R2 源封闭不放松（N2 修复）。
    """
    if roots is None:
        roots = set()
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
        if isinstance(fn, ast.Name):
            fn_roots: set = set()               # 函数名：查禁用名，不入 R2 根
            _lint(fn, depth + 1, fn_roots)
        for child in ast.iter_child_nodes(node):
            if child is fn:                     # func 已单独处理
                continue
            _lint(child, depth + 1, roots)
        return
    if isinstance(node, ast.Name):
        roots.add(node.id)
        if node.id in _FORBIDDEN_NAMES:
            raise InterpreterRejected(f"NAME-FORBIDDEN: {node.id}（R1 输入封闭 / R4-R6 无时钟）")
    if isinstance(node, ast.Attribute) and node.attr.startswith("__"):
        # dunder 属性链（__class__/__base__ 等）可遍历类型结构 —— R1 输入封闭禁止
        raise InterpreterRejected(
            f"ATTRIBUTE-FORBIDDEN: {node.attr} dunder 属性访问（R1 输入封闭）")
    for child in ast.iter_child_nodes(node):
        _lint(child, depth + 1, roots)
def eval_boolean(expr: str, env: dict) -> bool:
    """受限求值：仅允许 snapshot.* 与 principal.* 两源（R2），
    环境缺名 = InterpreterRejected（R1 输入封闭，拒绝谓词性猜测）。"""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise InterpreterRejected(f"PARSE-FAIL: {e}") from e
    roots: set = set()
    _lint(tree, roots=roots)
    for name in roots:                          # R2：仅此二源
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
    if not isinstance(result, bool):
        # N1：条件谓词 MUST 求值为 bool。非谓词值表达式经 bool() 强制转换会
        # 恒真放行（snapshot.amount → True），使提交门的放行方向被静默改写。
        raise InterpreterRejected(
            f"NON-BOOLEAN-PREDICATE: 条件表达式求值结果为 {type(result).__name__} "
            f"而非 bool —— 谓词必须是比较/成员/逻辑组合（R10 布尔档）")
    return result
def _namespace(v):
    """dict → SimpleNamespace（递归）；其余原样。"""
    if isinstance(v, dict):
        return SimpleNamespace(**{k: _namespace(x) for k, x in v.items()})
    if isinstance(v, list):
        return [_namespace(x) for x in v]
    return v
