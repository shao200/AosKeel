# tests/ —— 测试组织与新增契约

> 信息性文档（随 `aos init` 进入实例）。判据的唯一真源是
> [config/verification.yaml](../config/verification.yaml) 与源码；本文件只解释怎么放、怎么加。

## 目录语义

| 目录 | 回答的问题 | 门禁 |
|---|---|---|
| `conformance/` | 条款规定的行为**发生了**（正例 + 结构核对） | `gate: true`，进 CI 与发布闸门 |
| `negative/` | 禁止的事**做不成**：forbidden 逐项拒绝、解释器逃逸、直写陷阱 | `gate: true` |
| `golden/` | 固定输入 → 固定输出（upcasting 等字节级口径） | `gate: true` |
| `genesis/` | 创世窗口状态机（KS-8：熄灭不可逆） | `gate: true` |
| `invariants/` `replay/` | 实例侧扩展位（模板只声明套件、目录留空）：不变量守卫、回放核对 | `gate: false` |
| `redteam/` | 直写陷阱/绕行演练等支撑件；VER-28 红队本体是〔强〕项：人工执行 + 检查表留档，**不进 auto 门禁** | `gate: false` |

## 三条硬契约（有元测试执法）

1. **布线是唯一分组依据**：`aos test` / 发布闸门只执行 `verification.yaml` 声明的
   路径；布线路径缺失 = `WIRING-REFUSED`（fail-closed，不静默降级）。
   新增测试文件若不在布线里，等于不存在——要么挂 VER 条目，要么走
   `integrity_paths`（INTEGRITY-* 不新增 VER 条款，只把守卫纳入既有布线）。
2. **forbidden 双射**（`negative/test_forbidden_coverage.py` 执法）：
   `config/capabilities.yaml` 的每个 forbidden 项恰好对应一个负向用例，
   不多不少；`negative/` 下每个测试模块必须携带治理映射
   （引用 `FORBIDDEN_TESTS` 或 VER 条目编号），否则判"未治理负向测试"。
3. **正负成对**：新增一条 MUST，就应有对应的拒绝路径测试；错误消息
   前缀（如 `SOURCE-FORBIDDEN`、`ATTRIBUTE-FORBIDDEN`）是判据的一部分，
   用 `pytest.raises(match=…)` 锚定，不匹配裸异常类型。

## 新增一类测试的步骤

1. 放进语义正确的目录；docstring 首行写明 `文件路径 —— 对应条款/判据`。
2. 在 `config/verification.yaml` 挂接：`ver:`（对应 VER 条款）或
   `integrity_paths:`（回归补充守卫）。
3. `python src/cli/main.py test` 本地过布线；`aos verify` 三关不受影响。
4. 若是负向：确认 governance 元测试通过（forbidden 双射 / VER 引用）。

## 实例侧注意

模板自带的 VER 条目以冻结正典 v2.2.0 为锚；实例扩展自己的领域时，
新增守卫优先走 `integrity_paths`，不改 VER 编号语义（GOV-2.3）。
