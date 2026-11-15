# 06 · 形式语义与本体工程：从描述逻辑到可治理本体

> **教学性 / 信息性文档，不产生规范条款。** 本文前半部分是通用本体论理论（描述逻辑、开放世界假设、本体工程方法），后半部分把它映射到 AOS 的真实构件。凡涉及效力，以 [aos-spec.md](../aos-spec.md) 与源码为准。
>
> 特别声明：**AosKeel 不是描述逻辑推理器**。本文的 DL 公式用于解释"经典本体如何获得推理能力"，以及"AOS 为什么做了不同的取舍"；不要把 DL 公式当成 AOS 的声明语法，也不要把"AOS 的封闭性"等同于标准逻辑里的封闭世界假设。

## 结论先行

1. 经典本体之所以能"推理"，不是因为画了概念图，而是因为它有**形式语义**：每个概念被解释为集合，每个关系被解释为集合上的二元关系，公理的真假可由模型判定。
2. **OWA（开放世界假设）**下"未声明 ≠ 假"；**CWA（封闭世界假设）**下"未声明 = 假"。RDF/OWL 走 OWA，数据库与事件溯源走 CWA。这是两种根本不同的世界观，混用会产生最隐蔽的建模错误。
3. AOS 的取舍是：**权威状态在确定语义上封闭**（投影结果由事件序列唯一决定，没有"未知"占位），**外部现实只能以带出处的观测进入**（AX-1）；而"封闭"更重要的含义是**变更通道封闭**——只有经 Action 评估才能追加事件。
4. 经典本体回答"什么为真"；AOS 的 ActionType 回答"什么变更被允许发生"。前者是**模型论语义**，后者需要**操作语义**——这就是 OWL 公理无法直接表达 ActionType 的根本原因。
5. AOS 不提供全称推理、默认推理与非单调推理。它把"推理"拆成三个可审计的机械动作：**注册期结构编译 → 运行时受限布尔求值 → 写时不变量阻断**。代价是表达力受限，收益是每一步都能事后重放（AX-4）。

---

## 1. 形式语义：本体与"标签体系"的分界线

### 1.1 解释（interpretation）是推理的前提

描述逻辑（Description Logic, DL）用**解释** `I = (Δ^I, ·^I)` 给出形式语义：

- `Δ^I` 是论域（domain），即"世界里所有个体"的集合；
- 每个**概念**（类）`C` 被解释为子集 `C^I ⊆ Δ^I`；
- 每个**角色**（关系）`R` 被解释为二元关系 `R^I ⊆ Δ^I × Δ^I`。

于是"医生是员工的一种"不是一句自然语言，而是包含公理：

```
Doctor ⊑ Employee      含义：Doctor^I ⊆ Employee^I
```

"张三选修数据结构"是 ABox 断言：

```
Course(数据结构)      ZhangSan ∈ Student^I
enrolled(ZhangSan, 数据结构)    (ZhangSan, 数据结构) ∈ enrolled^I
```

有了这套语义，才能定义三种标准推理服务：

| 推理服务 | 提问方式 | 例子 |
|---|---|---|
| 可满足性（satisfiability） | 这个概念可能非空吗？ | `Approved ⊓ ¬Approved` 不可满足 → 建模矛盾 |
| 包含性（subsumption） | C 一定是 D 的子集吗？ | 由 `A ⊑ B, B ⊑ C` 推出 `A ⊑ C` |
| 实例检查（instance checking） | 个体 a 一定属于 C 吗？ | 由 `Doctor(张三)` 与 `Doctor ⊑ Employee` 推出 `Employee(张三)` |

**判据**：没有形式语义的"概念地图"只是标签体系——它能被人读懂，但不能被机器判定。这正是用户素材中"显式、形式化"两个词的重量所在。

### 1.2 DL 语法速览（用 Contract 领域举例）

| 构造 | 记法 | 读法 | Contract 领域示例 |
|---|---|---|---|
| 原子概念 | `Contract` | 合同类 | `Contract` |
| 交集 | `C ⊓ D` | 既是 C 又是 D | `Contract ⊓ Approved` |
| 并集 | `C ⊔ D` | 是 C 或是 D | `Pending ⊔ Approved` |
| 否定 | `¬C` | 不是 C | `¬Void` |
| 存在限制 | `∃R.C` | 至少有一个 R 关系指向 C | `Contract ⊑ ∃hasStatus.Status` |
| 全称限制 | `∀R.C` | 所有 R 关系都指向 C | `Contract ⊑ ∀hasParty.Party` |
| 基数限制 | `≥n R.C` / `≤n R.C` | R 关系数量的上下界 | `Contract ⊑ =1 hasCustomer.Customer` |
| 包含公理 | `C ⊑ D` | C 一定是 D | `ApprovedContract ⊑ Contract` |
| 断言 | `C(a)` / `R(a,b)` | 个体属于类 / 两个体有关系 | `ApprovedContract(C-1)` |

> 这些公式是**教学语言**。AOS 的声明写成 YAML，条件写成受限布尔表达式（如 `snapshot.status == 'pending' and snapshot.amount < 10**6`），两者表达力不同——见 §6 翻译边界。

---

## 2. 开放世界 vs 封闭世界：最容易被混淆的一层

### 2.1 两种世界观

| 维度 | 开放世界假设 OWA（RDF / OWL） | 封闭世界假设 CWA（数据库 / 事件溯源） |
|---|---|---|
| 未声明的命题 | **未知**，不是假 | **假** |
| 典型问题 | "能否推出 a 属于 C？" | "表里有没有这条记录？" |
| 缺失信息 | 允许不完整，推理保持谨慎 | 缺字段即数据错误 |
| 否定的表达 | 需要显式 `¬C`，否则推不出"不属于" | `NOT EXISTS` 直接得假 |
| 适用 | 元数据集成、语义互操作、知识融合 | 业务交易、账本、审计 |

一个具体分歧：声明 `Doctor(张三)` 之后问"张三是员工吗？"

- OWA：若没有 `Doctor ⊑ Employee`，回答**未知**（不能因为没说就判定不是）；
- CWA：若数据库里没有 `员工(张三)` 这条记录，回答**否**。

### 2.2 AOS 的立场：三种"封闭"要分开说

AOS 常被误读为"封闭世界本体"。准确说法是三层，必须分开：

| 层次 | 口径 | 规范依据 | 工程表现 |
|---|---|---|---|
| **变更通道封闭** | 本体权威状态在 Action 下封闭：改变状态只有一条路 | AX-1 / INV-1 | 无 `update`/`delete`；`write_raw` 必拒；未注册 Action 无写路径 |
| **投影状态确定** | 给定事件序列，投影结果唯一；没有"未知"占位符 | KS-3.4 重放纯度 / P-16 | 投影可丢弃后全量重建，得到同一状态 |
| **外部现实开放但带出处** | 外部事实可作为观测进入，不能静默变成权威状态 | AX-1 后半 / KS-2.2 | 会话事件流物理独立；禁止进入任何投影的权威重建 |

**这不是标准 OWA，也不是朴素 CWA。** 更准确的表述是：**权威层采用确定语义 + 封闭写通道，观测层采用带出处的开放摄入**。

实践后果非常具体：

- 声明里写了 `required: true` 的参数缺失 → `STRUCTURAL-FAIL: contract_id 必填（exists）`，而**不是**"值未知，继续推理"（KS-7.1）；
- 条件求值异常 → 记一条 `error` 审计并拒绝，**不是**"按缺省值补全"（KS-3.3）；
- 想要引入 LLM 的推断结论 → 它只能是**提议**，必须过确定性 Action 才成为断言（AX-2 / INV-7）。

这一层是本体论科普素材与 AOS 工程实践之间最大的落差：**OWA 的哲学优雅，在需要 fail-closed 的治理系统里被有意放弃**。

---

## 3. 三种推理服务在 AOS 中的对应物

AOS 不运行 DL reasoner。但经典本体的三类推理需求并没有消失，而是被拆成三个**可审计的机械动作**：

| 经典推理服务 | AOS 中的对应机制 | 执行时机 | 可审计产物 | 是否等价 |
|---|---|---|---|---|
| 一致性 / 可满足性 | `_validate_spec()`、`validate_link()`、`validate_context()`；SC 编译 Check AST | 注册期（内核启动前） | `RegistrationFailed` 拒绝；不发布能力清单 | **功能类比**：只校验声明格式与引用存在性，不做全域模型检测 |
| 包含性 / 层次推理 | 声明中的 `is-a` / `part-of` 被落成结构性链接与聚合边界 | 声明期 | `spec/ontology/links/*.yaml` + 注册期三项校验 | **不等价**：LinkType 零业务语义（INV-2），不参与推导 |
| 实例检查 / 规则触发 | 受限布尔解释器（R10）与受限映射解释器（R11）+ 不变量写时阻断 | 运行时（每次提交） | `kernel.interpreter_audit`（表达式、快照哈希、结果） | **不等价**：只求值声明的布尔函数，不做开放域推理 |
| （经典本体没有） | ActionType 门控：能力核查 → 结构 → 条件 → 追加 | 运行时 | 事件八字段 + store audit | AOS 独有 |
| （经典本体没有） | 决策三引用与会话半边解析 | 运行时 | `Decision@1` 事件 + session 记录 | AOS 独有 |

### 3.1 为什么放弃完整推理器

| 取舍 | 引入完整 DL reasoner | AOS 现状 |
|---|---|---|
| 可判定性 | 需限制在可判定描述逻辑片段（如 SROIQ）；复杂本体可能不可判定 | 受限子语言，求值终止性可证 |
| 性能 | 推理开销随 TBox 规模上升，难做写路径上的同步门控 | 编译一次（注册期），运行时只求值 |
| 审计闭环 | 推理链难以逐条重放为"当时依据什么" | 每次求值留表达式 + 快照 + 结果（KS-3.3） |
| 失败语义 | 推理器通常返回"不可满足 / 未知" | fail-closed：拒绝、记审计、不出制品 |
| 实现体积 | 需引入推理引擎依赖 | 模板依赖极简（pyyaml + pytest） |

**代价必须写明**：复杂关系推理（如传递闭包、复杂基数推理）在 AOS 中不能开箱即用。实例侧若需要，应在投影层或外部推理器中完成，其结果通过**声明的摄取 Action** 以观测或提议进入系统，不能直接改写权威事件流（AX-1 / AX-2）。

---

## 4. 本体工程方法：七步法如何落到 AosKeel

经典本体工程（如 Methontology / 七步法）的一般流程，与 AOS 的操作序列可以逐段对齐。这张表是本文最实用的一张：

| 本体工程步骤 | 通用产出 | AosKeel 中的落点 | 命令 / 文件 |
|---|---|---|---|
| ① 确定范围与领域 | 领域边界声明 | 上下文边界（ContextType） | `spec/contexts/*.context.yaml`；`docs/POSITIONING.md` |
| ② 列出能力问题 | Competency Questions | 需求 DSL 样例（按"系统必须能回答什么"写） | `docs/samples/requirements-sample.txt` |
| ③ 收集与抽取词汇 | 术语表 | T01–T26 唯一术语口径（变体禁入规范性条款） | `docs/aos-spec.md §1.1`；[05-reference.md](05-reference.md) |
| ④ 建立概念化 | 类 / 关系 / 层次草图 | 八类声明（对象 / 属性 / 链接 / 动作 / 上下文 / 聚合 / 不变量 / 映射 / 流程） | `spec/` 目录；[04-tutorial.md §3](04-tutorial.md) |
| ⑤ 形式化 | 公理与约束 | `submission_criteria.structural`（Check AST）+ `conditional`（受限布尔 Function）+ 不变量三元组 | `spec/ontology/actions/*.action.yaml` |
| ⑥ 实现与实例化 | 本体文件 + 实例数据 | 草案 → 晋升 → 代码骨架 → 能力清单 → 事件流 | `aos draft` → `aos draft promote --proposal-ref` → `aos generate --force` |
| ⑦ 评估与迭代 | 一致性 / 完备性检查 | 三关核对、布线测试、发布闸门、GOV-3 版本通道 | `aos verify` / `aos test` / `aos release` / `aos spec version` |

### 4.1 能力问题驱动建模（最容易被跳过的一步）

**能力问题（Competency Question, CQ）** 是"这个本体建成后，系统必须能回答哪些问题"。先写 CQ 再写声明，能显著降低过度建模。以下是 Contract 领域的示范清单，右列给出 AOS 中由谁回答——这列是本教程的关键：

| 编号 | 能力问题 | AOS 回答者 |
|---|---|---|
| CQ-1 | 合同 C-1 当前处于什么状态？ | 只读投影（`Projection.snapshot()`），由事件流重建 |
| CQ-2 | 谁能批准合同？ | `ApproveContract.action.yaml` 的 `permissions.roles` + 能力清单 |
| CQ-3 | 金额 200 万的合同能否批准？ | 条件表达式 `snapshot.amount < 10**6` → 条件拒绝 |
| CQ-4 | 批准动作发生时依据了什么？ | `interpreter_audit`（表达式 + 快照 + 结果）+ 事件八字段 |
| CQ-5 | 两个系统里的"合同"是不是同一个？ | `same_as.link.yaml`（结构性链接）+ Identity Context |
| CQ-6 | 合同变更时订单侧要做什么？ | `ProcessType` 跨聚合编排 + 补偿 Action |
| CQ-7 | 违规事件能否被普通 Action 写入？ | 流规则拒绝：`RaiseInvariantViolation` 是唯一写者 |
| CQ-8 | 删掉投影后状态还能恢复吗？ | `Projection.discard()` → `rebuild()`（VER-26） |
| CQ-9 | Agent 当时"看到"了什么？ | 会话事件流（**不是**权威状态，禁止进投影） |
| CQ-10 | 规范改了一句话，系统怎么知道？ | 全文哈希 + GOV-3 版本通道；漂移即 `FROZEN-TEXT-MUTATED` |

> **方法要点**：CQ-9 和 CQ-10 在经典本体工程里通常不会出现在能力问题清单中——它们属于治理与观测维度。这正是"治理性本体"比"描述性本体"多出来的建模负担。

### 4.2 本体评估维度与本项目的检查手段

| 评估维度 | 经典判据 | AOS 中的可操作检查 |
|---|---|---|
| 一致性 | 不存在不可满足概念 | 注册期声明校验；结构编译不过即 `RegistrationFailed` |
| 完备性 | 能回答全部 CQ | `config/verification.yaml` 的 VER-1..33 布线；`aos test` |
| 简洁性 | 无冗余公理 | 单一语义真相源在 `spec/`；能力清单严格子集（P-10） |
| 可解释性 | 推理链可被追踪 | 解释器审计（KS-3.3）+ 决策双引用（KS-2.5） |
| 可演化性 | 变更可管理 | GOV-3 提案通道 + append-only 登记表 + 读时升级（KS-5.2） |

---

## 5. 一个领域的两种写法：DL 公理 ↔ AOS 声明

以 `ApproveContract` 为例，把同一个业务规则写成两种形式，差异立刻显现。

### 5.1 DL 写法（描述"什么为真"）

```
ApprovedContract ⊑ Contract
Contract         ⊑ ∃hasStatus.Status
Contract         ⊑ ∀hasAmount.Number
Approve          ⊑ ∃hasPrincipal.ContractSteward
Approve          ⊑ ∃on.Contract
```

这组公理能推出"被批准的合同是合同""批准者是合同管家"，但**推不出**"金额 ≥ 100 万时不得批准"这种**禁止性门控**应该如何执行——DL 会说该状态不可满足，却不会告诉你拒绝发生在哪一步、留下什么审计。

### 5.2 AOS 写法（约束"什么变更被允许"）

实际声明（`spec/ontology/actions/ApproveContract.action.yaml`）：

```yaml
action_type: ApproveContract
aggregate: ContractAggregate
params:
  contract_id:      { type: ref, required: true }
  approver_comment: { type: string, required: false, max_len: 2000 }
submission_criteria:
  structural:
    - "exists contract_id"
    - "max_len approver_comment 2000"
  conditional:
    expression: "snapshot.status == 'pending' and snapshot.amount < 10**6"
    snapshot_inputs: [status, amount, principal.role]
permissions: { roles: [contract_steward], contexts: [ContractContext] }
audit: required
dry_run: required
```

对应的运行时行为（每一步都有失败形态与审计落点）：

| 阶段 | 检查内容 | 违反时的异常 | 是否追加事件 |
|---|---|---|---|
| 能力核查 | `ApproveContract` 是否在 `write_actions` | `UnregisteredAction` / `UnknownAction` | 否 |
| 结构 | `exists contract_id`、`max_len` | `StructuralRejected` | 否 |
| 条件 | 快照一次捕获，`status=pending and amount<10**6` | `ConditionalRejected` + interpreter audit | 否 |
| 追加 | schema 版本、valid_time 域、expected_version | `VersionConflict`（完整重求值）/ `ValidTimeViolation` | 冲突后重评估再追加 |
| 不变量 | 聚合级不变量写时阻断 | `InvariantViolated` | 否 |

**关键差异**：DL 公理是**陈述性**的——违反意味着模型不成立；AOS 的 Action 契约是**操作性**的——违反意味着**这次变更请求被拒绝，并留下一条可重放的拒绝记录**。前者判定真假，后者决定世界是否改变。

---

## 6. 翻译边界：什么能映射，什么不能

| 经典本体 / 知识图谱构件 | AOS 对应物 | 可翻译程度 | 不可翻译的剩余 |
|---|---|---|---|
| Class（类） | `ObjectType` | 直接 | AOS 额外要求聚合归属与上下文边界 |
| DataProperty（数据属性） | `Property` | 直接 | 可标 `decision_relevant`（INV-8），OWL 无此语义 |
| ObjectProperty（对象属性） | `LinkType` | **受限** | AOS 的 LinkType 零属性、零业务语义、系统写入（T09 / P-4 / INV-2） |
| `is-a` / `part-of` | 结构性链接 / 聚合边界 | 部分 | 不参与自动分类推理 |
| Axiom（公理） | 不变量三元组 + 受限布尔 Function | **受限** | 表达力限于声明子语言与 R10/R11 profile |
| Individual（个体） | 事件投影得到的领域状态 | 部分 | 个体状态是时间函数（valid_time / transaction_time 双时态） |
| RDF 三元组断言 | 事件八字段 | **不可直接翻译** | AOS 事件带版本、动作、主体与事务时间，三元组无这些维度 |
| （无对应） | `ActionType` 与能力清单 | 不可 | OWL 描述"什么为真"，无法表达"谁能如何改变世界" |
| （无对应） | 会话事件流 | 不可 | 观测与权威物理分离，OWL 无观测层概念 |
| （无对应） | 创世窗口 / 治理 Action | 不可 | 合法性是社会世界事件，形式语义不覆盖（GOV-1） |

**结论**：可以把 OWL/RDF 当作**前期的概念建模工具**（厘清类与关系），但不要指望把 OWL 文件直接喂给 AosKeel。语义增益主要来自 ActionType、能力清单与审计结构——这些恰好是经典本体没有的维度。

---

## 7. 表达力与代价：一张取舍清单

| 你想要的推理能力 | AOS 是否开箱提供 | 替代路径 |
|---|---|---|
| 类的层次推理（`A ⊑ B` 传递） | 否（仅结构性声明） | 在声明中显式写出需要的链接；不要依赖隐式推导 |
| 基数约束（"必须且只能一个客户"） | 部分（结构段可声明 `exists`，复杂基数需自定义检查） | 用不变量三元组声明 + 违规对象（P-7） |
| 默认推理（"通常如此，除非例外"） | **否，有意不支持** | 显式写条件分支；缺省值不是可审计依据 |
| 非单调推理（新证据推翻旧结论） | 否 | 追加新事件；旧事件不改，状态重新投影（AX-1） |
| 传递闭包 / 图查询 | 否 | 在投影层实现，结果仅作决策输入（P-16），不写权威状态 |
| LLM 生成的领域猜测 | 否（只能是提议） | `aos draft` 确定性解析 → 同一闸门 → GOV 提案晋升（AX-2） |

> **设计判断**：这些"不提供"不是能力不足，而是治理系统的**故意约束**。一个能静默补全事实的推理器，会摧毁"当时依据什么"的可重放性（AX-4）。收益是审计确定性，代价是建模者必须把隐含规则全部显式化——这恰恰是本体论本来就该做的事。

---

## 8. 小结与下一站

- 形式语义 = 解释 + 公理 + 可判定推理服务；这是本体与标签体系的分水岭。
- OWA 与 CWA 不可混用；AOS 的准确口径是**权威层确定语义 + 封闭写通道 + 带出处的开放观测**，不是标准 OWA 也不是朴素 CWA。
- 经典三类推理在 AOS 中被替换为"注册期编译 / 运行时求值 / 写时阻断"，每一步都留审计；完整推理器被有意放弃。
- 本体工程七步法可直接映射到 `aos draft → promote → generate → verify/test/release`；先写能力问题再写声明。
- OWL 可作前期概念建模工具，但 ActionType、能力清单、会话流与创世窗口不可翻译——它们是 AOS 的语义增量。

下一篇：[07 · 内核实操](07-kernel-walkthrough.md)——用一段可运行代码把本文提到的结构拒绝、条件门控、冲突重求值、投影重建和决策审计逐条跑出来。
