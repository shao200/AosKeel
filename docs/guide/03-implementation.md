# 03 · 实现方法：从声明到可校验运行

> 信息性文档，不产生规范条款。代码以当前源码树为准；条款号引用 [aos-spec.md](../aos-spec.md)。

## 结论先行

AOS 的实现是一条**机械链**，每一步都有可计算的判据与明确的失败形态：

```
需求 DSL → 九类声明 → 注册五步 → 能力清单 → 运行时提交管线 → 事件日志/投影
                                      ↓                    ↓
                              三关核对（aos verify）   解释器审计 + 决策双引用
                                      ↓
                              发布闸门（aos release，fail-closed）
```

设计纪律：**注册期拒绝优于运行时拒绝；运行时 fail-closed 优于静默降级；写路径只有一条。**

---

## 1. 注册五步：spec/ 与运行时之间的唯一通道

入口：`src/kernel/registration.py::run_pipeline()`。顺序即管线，任一步失败即整体失败。

| 步 | 名称 | 输入 → 输出 | 失败形态（判据） | 代码位置 |
|---|---|---|---|---|
| 1 | load | `spec/` 九类 YAML → 声明字典 | 缺文件/解析失败 → `RegistrationFailed` | `_load_yaml()` / `load_caps()` |
| 2 | compile | Action 声明 → `CompiledAction`（Check AST + BooleanFunctionRef） | SC 编译失败 → 注册失败，逐条报告 | `_load_actions()` / `sc_compiler.compile_action()` |
| 3 | validate | 各类声明 → 失败清单 | LinkPattern 三项、预算、修复绑定、steward、语义损耗、provenance 任一缺失即拒 | `_validate_spec()` |
| 4 | register | 编译产物 + 创世内建 → generated 段 | 不落盘，仅计算 | `_compute_generated()` |
| 5 | reconcile | generated vs `capabilities.yaml` → 通过/失败 | `RECONCILE-FAILED: declared != registered` | `run_pipeline()` |

### 1.1 第 2 步：SC 两段式编译（KS-7.1 / VER-18）

Submission Criteria 由两部分构成，**编译期就分道**：

- **structural（结构校验）**：声明式子语言——`exists <field>`、`max_len <field> N`、`required`、类型、基数、引用存在性。编译成 Check AST，**不进解释器**。
- **conditional（条件校验）**：受限布尔表达式，编译成 `BooleanFunctionRef`——注册期只保存引用，**运行时**由布尔档解释器求值，快照按 `snapshot_inputs` 枚举一次捕获（R2）。捕获来源是**物化投影**（`materialize()`，P-16）：每次评估在当轮版本视图上重放聚合流折叠权威状态；实体已投影时，调用方自报字段与权威值矛盾 → `SNAPSHOT-CONTRADICTION` 拒绝，未随附的字段以权威值回填；实体未投影（首次观测）才回退 params。

以 `spec/ontology/actions/ApproveContract.action.yaml` 为例：

```yaml
submission_criteria:
  structural:
    - "exists contract_id"
    - "max_len approver_comment 2000"
  conditional:
    expression: "snapshot.status == 'pending' and snapshot.amount < 10**6"
    snapshot_inputs: [status, amount, principal.role]
effects:
  status: approved         # T24 副作用：状态效果由声明书写，非调用方自报
```

**不注册谓词性代码，注册数据**（P-1）：把整段宿主函数塞进声明，在编译期就会被拒。

**effects（T24 副作用执行点）**：Action 声明的状态效果在提交时由内核写入事件载荷（`payload.update(act.effects)`），投影折叠后即为新的权威状态——状态只由事件导出，调用方不再自报 `status`。注册期双重把关：效果键 MUST 属于聚合根 object 的声明属性且枚举值不越值域（`EFFECTS-UNDECLARED-PROP` / `EFFECTS-VALUE-OUT-OF-DOMAIN`）；效果键与 params 重名在编译期即拒（`SC-COMPILE-FAIL`，同字段双事实源）。示例域基线：`RegisterContract` 让实体进入权威投影（effects: status=pending），`ApproveContract` → approved，`VoidContract` → void。守卫：`tests/conformance/test_effects_derivation.py`（INTEGRITY-5）。

### 1.2 第 3 步：结构化校验清单（逐项可测）

| 校验 | 规则 | 条款 | 反例 |
|---|---|---|---|
| LinkPattern 三项 | `attributes_empty` + `traversal_transparent` + 无 Action 绑定 | P-4 / INV-2 / VER-21 | 给 `same_as` 加属性 → 拒绝 |
| 求值预算 | `evaluation_budget` 存在且 ≤ 10⁵（R8 缺省上限） | P-2 / R8 | 缺字段或 200000 → 拒绝 |
| 修复绑定 | `repair_binding` 必须存在 | INV-3 / P-6 | 只有违规语义没有修复 → 拒绝 |
| 上下文 steward | 每个 Context 必有 steward | P-3 / VER-12 | 无所有者 → 拒绝 |
| 投影延迟预算 | `projection_delay_budget_ms` 必填 | P-16 | 缺字段 → 拒绝 |
| 语义损耗声明 | Mapping 必声明 `semantic_loss_declared` | KS-4 | 静默丢字段 → 拒绝 |
| 补偿完整性 | Process 每个 compensation 必带 action | P-9 | 空补偿 → 拒绝 |
| 求值路径 | provenance 必填（创世熄灭后须 SPEC 提案号） | KS-8.2 | 无出处 → 拒绝 |
| 副作用合法域 | effects 键 ∈ 聚合根声明属性（identity 除外）、枚举值不越值域、与 params 不同名 | T24 / AX-5 | `status: ratified`（值域外）→ 拒绝 |

### 1.3 第 4–5 步：能力清单三段式与单写者

`config/capabilities.yaml` 结构：

```yaml
spec_ref: AOS-ART-001          # 与登记表最新条目同源（GOV-2.2）
foundation:                    # 固定段：基座三项，人工维护，内核不可改
  - audit_append_only
  - perimeter_integrity
  - breakglass_resonant
forbidden:                     # 固定段：禁止路径
  - modify_foundation
  - direct_event_write
  - history_rewrite
  - extinguish_override
write_actions:                 # 生成段：内建 + 编译通过的业务 Action
  - { id: RecordDecision, ... provenance: genesis }
  - { id: ApproveContract, ... provenance: SPEC-2026-014 }
channel_writes:                # 生成段：会话通道写入，强制主体归属
  - { id: SessionAppend, stream: session, principal_required: true, ... }
```

**P-5 单写者**：`registration.apply_generated()` 是生成段的唯一写者，且只重写生成段——固定段逐行原样保留。调用点只有一处合法业务通道：`aos draft promote`。**手工改 `spec/ontology/actions/*.yaml` 后直接 `aos verify` 会命中 `RECONCILE-FAILED`**，这是设计使然，不是 bug；正确做法见 [04 教程 §4](04-tutorial.md)。

`run_pipeline()` 的三个调用点：内核启动（失败 = 不发布能力清单 = 不启动）、`aos verify`（静态核对）、治理 Action 生效后重跑（GOV-4）。

---

## 2. 提交管线：能力 → 权限 → 结构 → 条件 → 追加

入口：`src/kernel/pipeline.py::Kernel.submit()`。运行顺序与 KS-7.2 完全一致：

| 阶段 | 动作 | 失败即 | 审计 |
|---|---|---|---|
| 0 能力核查 | `action_type` 必在编译产物中 | `UnregisteredAction`（INV-1） | 无 |
| 0.5 权限（角色证据） | 声明了 `permissions.roles` 的 Action：出示的 `roles` 与之相交才放行；未出示 = 无权（fail-closed） | `PermissionDenied`，在触达存储与评估之前（P-10 / INV-4） | 无（零接触） |
| 1 结构 | `run_structural(Check AST, params)` | `StructuralRejected` | 无（结构失败不进解释器） |
| 2 条件 | `eval_boolean(BooleanFunctionRef, env)` | `ConditionalRejected`；求值异常照记审计 | `record_evaluation`：版本 + 快照哈希 + 结果（KS-3.3） |
| 3 追加 | `payload.update(act.effects)` 后 `store.commit(action_id, stream, expected_version, ...)`——状态效果随声明进事件载荷（T24） | `StoreRejection` / `StreamRuleViolation` | 一条拒绝恰一条审计（不双记） |

**版本冲突 = 完整重求值（KS-1.4 / VER-3）**：`VersionConflict` 后不是换 `expected_version` 重试追加，而是重新执行**结构 + 条件 + 追加**整条管线，每轮各留审计；重试有界（有界防爆炸），超限 `BudgetExceeded` → fail-closed。

可核对的实测判据（`tests/conformance/test_conflict_reeval.py` / `test_integrity.py`）：

```
制造一次 VersionConflict → commit=2, structural=2, conditional=1(有条件的 Action)
只重试追加的错误实现    → commit=2, structural=1, conditional=0   ← 会被守卫测出
```

**写路径唯一性**：`store.py` 没有 update/delete/rewrite 方法；`write_raw` 直写陷阱必拒并留审计（VER-28）。一次拒绝恰一条 `structurally-rejected` 审计——重复记账也是缺陷。

---

## 3. 受限解释器：规则执行的沙箱

| 模块 | 职责 | 分布 |
|---|---|---|
| `src/interpreter/boolean_profile.py` | AST 节点白名单 + 调用函数白名单 + dunder 属性拦截（`__` 前缀属性访问即拒，R1 输入封闭）+ 深度上限；`__builtins__` 置空 | R10 / VER-8 |
| `src/interpreter/mapping_profile.py` | `rename / drop / const` 三算子，纯数据驱动；结构上无谓词分派入口 | R11 / VER-9 |
| `src/interpreter/audit.py` | 记录（解释器版本, 快照哈希, 结果） | KS-3.3 / VER-11 |

非白名单结构 → `InterpreterRejected`（fail-closed）。投影重建与 upcasting **只允许映射型**（KS-3.4），因此"重放时做判断"在结构上不可表达。

**预算纪律**：R8 上限 10⁵ 贯穿注册期（声明超限拒绝）、运行时门控（超限即拒）、探测器路径（超限产生预算超限类违规对象）——三条路径都不静默降级。

---

## 4. 事件存储、升级与投影

### 4.1 append-only 日志

`src/kernel/store.py` 的 `EventStore` 为纯内存 `dict[str, list[Event]]`，按 `stream_id` 分流：

- 唯一写入口 `commit(action_id, stream_id, expected_version, event_type, payload, principal)`；
- `action_id` 不在能力清单 write_actions 段 → `UnknownAction`（INV-13）；
- 特定事件类型有唯一写者约束：`InvariantViolation@*` 只能由 `RaiseInvariantViolation` 写，`MergeDeclared@*` 只能由 `DeclareIdentityMerge` 写；
- 决策事件只能在决策流且带 `projection_ref` + `session_ref`（KS-2.5 / VER-7 / VER-33）。

**工程边界与参考实现**：`EventStore` 本体是纯内存（进程退出即失）；`src/kernel/filestore.py` 提供 **FileStore 参考实现**——单一 JSONL 文件、写路径只有追加一行、启动时以文件为准重放重建流；拒绝（版本冲突/未知能力/直写陷阱）发生在落盘之前，文件不留半行。参考实现是**单写进程模型**：多进程并发需实例侧加锁，或直接以数据库实现同一协议（`streams` 只读 + `commit` 唯一写面 + `audit` 只增）；数据库本身不消除 append-only 证明义务，仍需实例自行取证。

### 4.2 读时升级（upcasting）

`src/kernel/upcasting.py`：注册表 `{(event_type, from_version) → upcaster}`，升级是纯映射（R11 / KS-3.4）。**未注册的升级路径 = 读失败**（KS-5.2 / VER-13），禁止猜测；升级链输出由 golden test 锚定（VER-14）；升级不改写日志，只改读出形态（AX-3）。

### 4.3 投影与重放

`src/kernel/projection.py`：投影是只读物化视图（T17），禁止做权威判断。reducer 必须是纯函数——同事件序列 → 同状态；删除物化后可从事件日志全量重建（VER-26）。决策输入留（投影标识, transaction_time）双引用的权威半边。

---

## 5. 三关核对与发布闸门的实现

| 关卡 | 实现 | 失败输出 | 对应工具 |
|---|---|---|---|
| 结构层 | 十节三元组：条数 + 首锚 + 末锚 | `STRUCTURAL-MISMATCH` + 失败节/形态 | `tools/fingerprint.py` |
| 密码学层 | 两个正典文件按声明顺序拼接 sha256 | `FROZEN-TEXT-MUTATED` / `HASH-MISMATCH` | `tools/hash_spec.py` |
| 注册层 | generated 逐条比对 capabilities | `RECONCILE-FAILED` | `kernel/registration.py` |
| 布线套件 | pyyaml 单一读取点；缺路径阻断 | `WIRING-REFUSED` / `PYTEST-MISSING` | `tools/wiring.py` |
| 骨架零漂移 | 字节级比较（UTF-8 + LF） | `CodegenDrift` → 拒绝静默覆盖 | `tools/codegen.py` |

**承重件教训**：`config/verification.yaml` 曾被两处正则抠 `path`，合法 YAML 改键序/加引号就 27→26 静默丢项。现在统一由 `tools/wiring.py` 用 pyyaml 解析，声明了 `path` 却不存在即阻断。`integrity_paths` 段只登记回归守卫测试的执行路径，**不构成新 VER 条款**——冻结条款集仍是 VER-1..33。

**字节精确**：Windows 上 `Path.write_text()` 会把 `\n` 写成 `\r\n`，而 `read_text()` 又读回 `\n`，导致"零漂移"判据对换行失效。所有写入点改为 `write_bytes(utf-8 + LF)`，`.gitattributes * -text` 禁止换行转换；登记表追加用二进制模式。

---

## 6. 常见实现反模式（被守卫测试锁死）

| 反模式 | 后果 | 守卫 |
|---|---|---|
| 冲突后只重试追加、不重跑结构/条件 | 在过期视图上通过门控 | `test_conflict_reevaluates_full_pipeline` |
| 一次拒绝写两条审计 | 审计流失真 | KS-1.3 守卫（一次拒绝恰一条） |
| 用正则从 YAML 抠 `path` | 静默少跑 VER | `test_wiring_survives_valid_yaml_variants` |
| 用 `write_text` 写生成物 | CRLF 漂移，工作区每测一次脏一次 | 字节级漂移检测 + CRLF 检查 |
| 手写"YAML 子集"解析器 | 值含逗号被拆成两个键 | `test_load_caps_parses_quoted_comma_value` |
| console 入口 `main(argv)` 无默认值 | 所有 `aos ...` 命令 TypeError | `test_console_script_calls_main_without_args` |
| pytest 只在 CI 手工安装 | 纯净 venv 里 `aos test` 不可用 | `test_pytest_is_declared_runtime_dependency` |

这些不是风格建议，而是从实测缺陷反推的判据。每一条都能定位到具体文件与具体量（次数、条数、字节）。

---

## 7. 小结与下一站

- 注册五步把"声明"变成"能力清单"，运行时只认清单；
- 提交管线的顺序与冲突重求值是可测的，不是口号；
- 解释器以不可表达性保证规则边界，事件层以 append-only + 读时升级保证历史可重放；
- 三关 + 闸门把规范条款变成机械拒绝点。

下一步：[04 · 实操教程](04-tutorial.md)——按真实命令走一遍，含每步的预期输出与失败形态。
