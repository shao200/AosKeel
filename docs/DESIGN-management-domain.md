# 设计说明：围绕聚合的管理域与成员集组织

> 信息性文档，不产生规范条款。本文回答一个问题：实体主动性可见性门控所用的
> "管理域成员集"应如何组织——进程内内存态，还是跨域消息机制？
> 结论先行：这是伪二选一。真正要定的是成员集是不是**权威可变状态**。

## 1. 结论（决议）

**采用"声明推导"为主、进程内锚定为兜底、事件投影为可选增强、跨域消息明确排除。**

| 层 | 事实源 | 成员从哪里来 | 重启/跨域 | 定位 |
|---|---|---|---|---|
| 归属层 owner | 事件流（append-only） | 实例首事件 `principal` 重建 | 天然存活、可重放 | 已实现（`stewardship.py:owner_of`） |
| 组织范围 orgs | 治理声明（`spec/governance`） | `duties[].org_unit` 跨组织并集 | 声明在册即一致 | 项目的联合域边界 |
| 可见集 V（切面成员） | 治理声明（`spec/governance`） | `∪ executor_roles(项目全部 Action)` | 声明在册即一致 | **scan 的过滤集，推荐主路径** |
| 执行集 E（按 Action） | **能力账簿**（`compiled` 权限矩阵，submit 门控同源） | `CapabilityLedger.demand/can_execute` | 编译产物即一致 | **唯一提交判据**；治理面 `executor_roles` 仅对账 |
| 实际执行人 claim（未来） | 认领事件投影 | 具体 principal 认领该任务实例 | 可重放、最终一致 | 运行态，不进管理域 |
| 显式覆盖层 | 观察通道（可选持久化） | owner 在册角色子集内显式收窄（域外角色即拒） | 给 `FileSession` 则重启重放并重校验，否则仅本进程 | 例外/演示兜底 |

一句话理由：**成员集是治理事实（谁被授权在这个域里行动），不是运行态数据。
治理事实的真相源是声明，不是进程内存，也不是消息总线。**

补充约束（2026-11-20，两轮）：**项目可跨多组织完成；任务执行是当事人，但还有检验、
监理等切面人员。** 连起来修正了上一版一个错误等式——"域成员 = 该任务执行人"。
正确模型是**可见集与执行集分离**：

- **可见集 V** = 项目全部 Action 的授权岗位并集 = 当事人 + 检验 + 监理 + ……跨组织所有切面角色。
  实体主动行为的扫描门控用 V——切面人员必须"看得见"这件事才能参与。
- **执行集 E(action)** = 单个 Action 的授权岗位。谁能提交哪个动作，按 Action 各自收窄。
- 二者都从同一份声明推导，只是聚合层级不同（并集 vs 单点），**不引入新声明类型**。

上一版把 scan 的过滤集写成"资格执行人"，窄化成只有当事人，漏了切面——这是错的，本版修正。

## 2. 为什么"进程内 vs 跨域消息"是错误的问题

两条独立的轴被混成了一条：

- **轴一（决定性）**：成员集是不是需要跨节点同步的*可变权威状态*？
  - 否 → 它就是声明的一个**推导视图**，`f(声明) = 角色集合`。没有状态要同步，
    每个进程读同一份在册声明，结论天然一致。进程内 vs 跨域这个问题**不存在**。
  - 是 → 才需要复制状态，才引出消息总线 / 分布式一致性 / 冲突解决。
- **轴二（次要）**：变更频率。治理域成员是低频、需审批、走 GOV 通道的；
  运行态参与者（谁正在接单）是高频的。两者不该用同一套机制。

你的规则——"创建者拥有管理域、只有域内角色可被主动行为扫描到"——描述的是
**治理域成员**（低频、结构性、需授权），落在轴一的"否"侧。所以跨域消息机制
从一开始就不是候选项。

## 3. 四方案评估矩阵

评分口径：存活=重启后成员关系是否还在；一致=多进程是否天然一致；
治理=成员变更是否有审批链背书；成本=改动面（含是否动冻结域）；粒度=能否到单实例。

| 方案 | 存活 | 一致 | 治理 | 成本 | 实例粒度 | 判定 |
|---|---|---|---|---|---|---|
| A 进程内 dict（现状） | ✗ | ✗ | ✗ | 最低 | ✓ | 仅演示兜底 |
| **B 治理声明推导** | ✓ | ✓ | ✓ | 低（无冻结域改动） | 域级（非实例） | **推荐主路径** |
| C 事件溯源投影 | ✓ | ✓ | ✓ | 中（新增声明+投影） | ✓ | P2 条件启用 |
| D 跨域消息 | ✓ | 最终一致 | 视实现 | 高（新中间件/协议） | ✓ | 排除 |

B 的"域级非实例"不是缺陷：主动性的可见性边界本来就由组织域决定，
同一 org_unit 下的合同共享同一成员定义；实例差异由 owner 归属层承担。

## 4. 主路径 B：从治理声明推导成员集

### 4.1 现成的事实源（已验证可跑通）

`spec/governance/ContractDutyMatrix.governance.yaml`：

```yaml
duties:
  - { duty: register_contract_duty, position: contract_steward,
      org_unit: contract-department, authorizes: [RegisterContract] }
```

实测推导结果：`contract-department -> ['contract_steward']`。这条链上每个环节
都已有守卫：`registration.py::_validate_governance` 强制"带角色的 Action 必须有
职责授权背书"，`validate_governance` 强制 `position`/`org_unit` 锚点非空，
`_validate_context_refs` 强制上下文引用解析。所以声明里的成员关系是**已被机械核对
的治理事实**，拿它当成员集，不是新造事实，是复用。

### 4.2 推导算法（纯函数，无状态、无消息）

两级推导，均为跨组织并集（`org_unit` 是组织锚点标签，**不是过滤条件**）：

```
orgs_of(project_actions) =
  { duty.org_unit | duty ∈ governance.duties
                  , ∃ a ∈ project_actions : a ∈ duty.authorizes }

executor_roles(action_type) =                       # 执行集 E：单动作授权岗位
  { duty.position | duty ∈ governance.duties
                  , action_type ∈ duty.authorizes }

visible_roles(project_actions) =              # 可见集 V：跨切面并集 = scan 过滤集
  ⋃ executor_roles(a), a ∈ project_actions
```

- 输入：动作类型 + 在册治理声明（声明摘要哈希域保护，改动走 GOV-3）。
- 输出：跨组织授权岗位并集。确定性、可重放、零运行时状态。
- **跨组织**：若合同部、审计部、财务部的职责项都 `authorizes: [ApproveContract]`，
  三者岗位自动进入同一执行人集，无需任何消息同步——各节点读同一份哈希保护声明，
  函数相同则输出相同。项目"涉及哪些组织"由此反向可见，不必新增 project→org 声明。
- **可见性用并集、提交权按 Action 收窄**（关键修正）：
  `scan = candidates ∩ visible_roles(项目全部 Action)` —— 当事人、检验、监理等切面
  角色都在可见集里，缺任何切面实体都无法主动寻到它；而 `can_execute(action) =
  roles ∩ executor_roles(action)` 只放行该动作的授权岗位（审批岗 ≠ 检验岗 ≠ 付款岗）。
  **可见 ≠ 可执行**，两个集合用途不同，不能互相替代。
- 与 `owner_of`（首事件 principal）组合：owner 回答"谁创建"，`visible_roles` 回答
  "哪些切面岗位与这个实体相关"；**"谁能提交这个动作"由能力账簿 `CapabilityLedger`
  回答**（读 `compiled` 权限矩阵 = submit 门控同源），治理面 `executor_roles` 只作对账，
  不是运行时判据——这是 §8.4 收敛后的定论。
- 现成对账：生成面 `GOV_POSITIONS`（`auth_oauth2.py:19`）已把 `position →
  duties / org_units / authorizes` 投影好，`authorize()` 用 `need ⊆ have` 校验。
  治理面 V 推导与令牌授权读的是同一份治理事实；执行判据则与 submit 门控读同一份
  能力账簿。两侧各自单一事实源，并在 `test_executor_agrees_with_kernel_submit_gate`
  对账，不会两张皮。

### 4.3 与现有实现的关系

`stewardship.py` 的 `scan()` 已定义为 `candidates ∩ members`。改成 B 只需把
members 的来源从 `anchor()` 的进程内登记，替换为 `visible_roles()` 的声明推导：
- `anchor()` 保留为**显式覆盖**（owner 想临时缩小可见范围时用），优先级高于推导；
- 未锚定时不再 fail-closed 抛错，而是回落推导值——这更符合"切面成员默认可见"；
- `owner_of` 不变，仍是事实层重建。
- **注意**：现有 `can_interact()` 语义是"域内即可互动"，在切面模型下要拆为两问——
  "能否看见/被通知"（可见集 V）与"能否提交某动作"（执行集 E），前者宽、后者窄。
  这是 P1 落地时必须处理的接口语义变更。

## 5. 层次职责与"谁动谁"（防越界）

| 变化类型 | 频率 | 走哪条路 | 闸口 |
|---|---|---|---|
| 换一个 owner 建同类实例 | 高 | 事件流自然产生新首事件 | `owner_of` 自动重建，无需任何写入 |
| 域内增减一个岗位授权 | 低 | 改 governance 声明 | GOV 提案 + 摘要哈希 + 全量闸门 |
| 某实例临时收窄可见角色 | 中 | owner 调 `anchor()` 覆盖 | owner 校验（已实现） |
| 运行态"谁在接这个任务" | 高 | **不属于管理域**，属调度/认领层 | 用 CQ 能力声明 + 认领事件，另案 |
| 项目跨组织 / 任务换执行人 | 低 | 改 governance 声明的 `authorizes`/`org_unit` | GOV 提案 + 摘要哈希 + 全量闸门 |

最后一行之前那条是关键切分：不要把"接单人的实时集合"塞进管理域成员集。那是**运行态
参与者**，高频、易变；管理域成员是**治理态授权**，低频、稳定。混在一起会同时
污染两边——这正是你担心的"复杂"的根源。

**"参与角色"的三层含义必须分开**（否则方案会再次变复杂）：

| 层 | 问题 | 事实源 | 粒度 | 归属 |
|---|---|---|---|---|
| 切面成员（可见集 V） | 谁*与这件事相关*（含当事人/检验/监理） | 治理声明 `visible_roles()` | 岗位 position（跨组织并集） | 管理域，低频、声明推导 |
| 动作执行人（执行集 E） | 谁*有资格提交该动作* | 能力账簿 `CapabilityLedger`（compiled 权限矩阵，门控同源）；治理面 `executor_roles` 仅对账 | 岗位 position（单动作收窄） | 匹配层，编译产物推导 |
| 实际执行人 | 谁*实际接了*这个任务实例 | 认领事件投影（未来） | 具体 principal | 运行态，高频、另案 |

邵工修正后："任务的执行是当事人，但还有检验、监理等切面人员"——前两层正是为此：
- **可见性门控用 V**：实体主动行为扫描到的是所有切面岗位，检验/监理必须"看得见"才能介入；
- **提交权门控用 E**：真正推动某状态跃迁的只有该 Action 的授权岗位，检验不能代签审批。

后者（具体谁认领）是实体主动寻人要解决的下一层闭环，不该塞进成员集。
当前在册声明只有 `contract_steward` 一个岗位，检验/监理是**声明扩展**（新增 Action +
duty + GOV 提案），不是当前缺陷；模型的容量已经留出。

## 6. 跨域场景怎么处理（不需要消息总线）

多进程/多域部署时，每个节点：
1. 加载同一份在册 `spec/` 声明（摘要哈希域保证字节一致，verify 第四道核对）；
2. 各自从事件流用 `owner_of` / `executor_roles` 本地推导——**纯函数、无共享状态**；
3. 因为输入相同、函数确定，输出必然相同——这就是一致性，不需要消息传播。

只有当成员关系需要**运行时动态变更且必须多节点同步**时（例如全域临时撤销某角色，
要求所有节点秒级生效），才进入方案 C：把"成员变更"做成领域事件，各节点投影重建，
接受最终一致。触发条件写死为可判据：

> 启用 C 的三个条件**同时满足**：(a) 出现实例级差异化成员需求；
> (b) 变更频率高于 GOV 通道可承受（实测 > N 次/发布周期）；
> (c) 可接受投影延迟预算（现有 `ContractContext.projection_delay_budget_ms: 500`）。

三个条件当前均不成立 → 不启用 C。

## 7. 明确排除 D 的理由

跨域消息机制会引入：消息中间件依赖、投递语义（至少一次/恰好一次）、幂等、
最终一致的冲突解决。而本项目定位是"规范驱动的模板生成系统 + 进程内内存态内核
参考实现"（`POSITIONING.md` §5），`FileStore` 明示单写进程模型。在此之上叠消息
总线，等于用分布式复杂度换取本可由声明推导解决的一致性问题——过度工程。
若未来真做多组织联邦部署，那是**实例侧/产品侧**职责，不是内核模板层该提供的。

## 8. 落地顺序与状态

1. **P0（已落地）**：`stewardship.py` 的 owner 重建 + `scan` 交集 + 显式锚定 fail-closed。
2. **P1（已落地，本轮收敛）**：成员事实源收敛到 `stewardship.governance_positions()`
   单一投影（**不**自行解析第二份 yaml、**不**依赖 auth 门控生成物；推导已下沉内核，
   `tools/codegen.py` 反向委托，消除 kernel → tools 依赖）。新增四个纯函数
   `governance_view / executor_roles / visible_roles / org_units_of`；`scan` 未锚定时
   回落可见集 V，`anchor()` 降为显式覆盖；`can_interact`（V 宽判据）与 `can_execute`
   （E 窄判据）分离。跨组织 + 切面成员 + 任务收窄在同一次投影的不同聚合层级兑现。
   测试扩展到已布线的 `test_agent_surface.py`（INTEGRITY-36，17 passed），不动 doc 口径。
3. **P1.5（已落地，V 的消费者）**：`src/kernel/initiative.py` —— 实体主动行为闭环。
   解决"孤儿模块"问题：V 终于有了该有的消费者，但不是接 `Kernel.submit`（写路径
   属模型变更），而是走观察通道：只读权威投影 → 受限触发判定 → 扫 V → 按 E 分类
   → 写 SessionChannel（逐条带主体归属）。不写 EventStore、不调用 submit、不自动
   提交、不代签。
4. **P1.6（已落地，本轮：双向统一 + 能力账簿）**：回答邵工"事找人 / 人找事都用消息
   机制，都基于能力账簿"。
   - 新增 `src/kernel/capability_ledger.py` —— **能力账簿 = `compiled` 权限矩阵
     （Action × Role）的双向只读投影**，即 `Kernel.submit` 门控（pipeline.py:65
     `required & roles`）读的同一份事实。`demand(actions)→roles`（事找人）、
     `supply(roles)→actions`（人找事）、`can_execute(action, roles)`（门控同源预检）。
     消除上轮隐患：E 曾读治理面 `authorizes`（第二张皮），现统一到能力面——匹配即门控。
   - `InitiativeEngine` 新增 `seek()`（人找事）：出示角色 → 能力账簿反查可做 Action
     → 投影命中 → 写 `initiative.offer`（principal=人/Agent id）。与 `run()`（事找人）
     对称：同一本账簿、同一观察通道、都不碰写路径。构造时**强制注入** CapabilityLedger，
     拒绝治理面推导。
   - 6 个新测试（双向投影 / 门控对账 / seek 观察侧 / 双门过滤 / 对称 / 拒绝缺账簿）。
     当时全量 428 passed，verify 三关 OK，正典 `fff3d7e7…` / 声明摘要 `91ffe5a1…` 未变。
5. **P1.7（已落地，本轮检查/反思/完善）**：回查暴露三处真问题并修掉——
   ① `stewardship.can_execute` 作为治理面同名 API 与 `CapabilityLedger.can_execute`
   构成双源，**已移除**，唯一执行判据收敛到能力账簿，治理投影 `executor_roles`
   降级为对账用途；② `seek()` 只给 `entity_id` 不给 `stream_id` 可绕过 V 域门控
   （fail-open），**已改为参数成对强制校验**（`SEEK-SCOPE-INCOMPLETE`）；
   ③ 多实体下谓词只判定一次却对全投影扇出 offer，**已改为逐目标判定**——
   `Trigger.fires(snapshot[, entity_id])` 支持双参实体级谓词，单参旧写法向后兼容。
   新增 2 个守卫（半参数拒绝 / 逐目标不扇出），并对账治理面 E == 能力面 E。
   全量 430 passed，verify 三关 OK，正典 `fff3d7e7…` / 声明摘要 `91ffe5a1…` 仍未变。
6. **P2（条件触发，未做）**：实例级动态成员 + 事件投影，需单独提案与授权。
   调度点已另起 `docs/adr/ADR-005-trigger-scheduling.md`（Proposed，未授权、未执行）。
7. **P1.8（已落地，本轮：责任传递闭环 + 校验强度可调）**：把"状态事件驱动任务完成"
   落成观察侧闭环，写路径与正典零变更。新增 `assurance / selection / continuation`
   三个模块，`Projection.entity_key` 转为必填，发起人身份只进审计元数据；生成期新增
   聚合标识与域画像 `entity_key` 的 fail-closed 校验。细节与红线见 §8.6。
8. **不做**：接写路径（模型变更，需 ADR→PR→gates→regression）、跨域消息总线。

## 8.3 实体主动行为闭环（initiative.py）的三条红线

这是把"实体主动性"从概念变成可跑代码的一步，但刻意停在观察侧。写进结构、不靠自觉：

| 红线 | 结构保证 | 守卫测试 |
|---|---|---|
| 只读权威状态 | 只持 `projections`（dict）与 `session`，**不持 store 引用**；从 `snapshot()` 读 | `test_initiative_never_calls_submit_or_bypasses_gate` |
| 只写观察通道 | 唯一写入是 `session.append(entity_id, ...)`；投影源级排除 session（KS-2.2） | `test_initiative_writes_only_observation_not_eventstore`（EventStore 零增长） |
| 不自动提交 | 产出的是 Invitation/Notice 记录，人/Agent 认领后仍走原 submit 门控 | 引擎无 submit/commit/_append 能力（结构核对） |

V/E 在此闭环里的分工得到实证：在册只声明 contract_steward 一岗；测试注入的治理视图
另声明 `qc_inspector`（可授权 ApproveContract），owner 才能把它锚定进 V——它
`can_execute=False`、只收 notice——**可见 ≠ 可执行**落地为可观测的两种邀请类型。
锚定只可在册角色子集内收窄，域外角色直接 `UNDECLARED-ROLE` 拒绝。切线仍是：
运行态"谁认领"属调度层，不进成员集。

P1.8 之后同类约束又多了两条——**选择不落事件、续办不臆造期限**，与上表三条同性质，
见 §8.6 的红线表。

## 8.4 能力账簿：双向匹配的单一事实源（capability_ledger.py）

邵工指出"事找人 / 人找事都用消息机制，都基于能力账簿"。落地要点：

| 维度 | 事找人（demand / run） | 人找事（supply / seek） |
|---|---|---|
| 发起主体 | 实体（principal=entity_id） | 人/Agent（principal=agent_id） |
| 查询 | `ledger.demand(actions) → roles` | `ledger.supply(roles) → actions` |
| 前置门 | 可见集 V（治理面，切面/跨组织） | 能力账簿 E + 可选 V 门控 |
| 意向类型 | invitation（可提交）/ notice（见证） | offer（可推动的 Action） |
| 落点 | SessionChannel（观察，不进投影） | 同左 |

**为什么能力账簿是唯一正确的匹配源**：它就是 `compiled` 权限矩阵，而 `submit`
门控读的正是这一份（`pipeline.py:65`）。上一轮 E 读治理面 `governance.authorizes`
是隐患——现网两者经 CQ-2 对账一致，但两套推导一旦漂移，"被匹配到的人"和"能通过
门控的人"就会分叉。现统一到能力面：**匹配即门控**。`test_ledger_gate_agrees_with_real_submit`
逐角色比对账簿判据与真实 submit 行为（含 fail-closed 拒绝）。

**两本账的分工（不重叠）**：治理面 V 答"谁看得见这件事"（owner 可锚定、含切面），
能力账 E 答"谁能实际提交"（不可自报、门控同源）。检验/监理在 V 不在 E——事找人时
只收 notice；人找事时 `supply()` 不含其无权的 Action。可见 ≠ 可执行，双向一致。

**唯一判据（本轮收敛）**：`stewardship` 不再提供 `can_execute`（同名双源 API 已移除）；
治理面 `executor_roles` 只用于推导 V 与对账。`test_executor_agrees_with_kernel_submit_gate`
逐项核对"治理面 E == 能力面 E == 真实 submit 行为"，任一侧漂移即失败。

**消息机制的边界**：消息 = 意向（invitation / notice / offer），不是执行。认领后仍走
`Kernel.submit`，权限与条件门控照旧。没有引入 MQ / 总线——项目是进程内参考实现，
`SessionChannel`（能力清单登记的 `SessionAppend`）就是现成的 append-only 消息通道，
物理分离、逐条主体归属、不进权威投影。跨域消息是明确的"不做"。

## 8.5 本轮反思：从打补丁到收敛（工程债清理）

前三轮的模式是"每来一个新场景就加一个推导函数"——`owner_of` → `members_of` →
`orgs_of` → `visible_members`。回查暴露三处自造的工程债：
- **孤儿模块**：`scan/can_interact` 除自身定义与测试外零生产调用者，实为孤立数据结构。
- **第二张皮风险**：新函数若自行解析 `governance.yaml`，会与 codegen 生成的
  `GOV_POSITIONS` 形成两个事实源；而 `GOV_POSITIONS` 又是 auth 门控生成物，
  精简 profile 下会被摘除，硬依赖它会使模块崩溃。
- **重复造轮子**：`Kernel.submit` 的 `required ∩ roles` 早就实现了执行集 E 的运行时门控。

收敛动作：事实源唯一化为无门控的 `stewardship.governance_positions()`（与生成物同源同推导，
工具链反向委托）；V/E 语义分离；明确模块只补 E 不覆盖的可见集与 owner，**不接写路径**。
代价：模块仍是参考实现、无生产消费者——接写路径需模型变更授权，这是刻意保留的边界，
不是遗漏。

## 8.6 责任传递闭环与校验强度可调（本轮 P1.8）

状态事件发生后，谁该接着做什么——这件事从"概念"落成可跑链路，但**agent 只在读侧**：

```
状态事件 → 投影折叠（实体级水位）→ 候选集（档位 + 渲染时戳）
        → 上一轮发起人选择（审计三元组 + 新颖性校验）
        → 责任落到持岗人（assignment）
        → 持岗人 submit(initiator=…) → 原门控 → 新事件
```

| 能力 | 落点 | 关键约束 |
|---|---|---|
| 校验强度分档 | `src/kernel/assurance.py` + `config/assurance-policy.yaml` | 四档 autonomous / single_review / dual_review / supervised；下限是常量 `IMMUTABLE_GATES`，声明里出现 `gates` 即拒绝加载；自主档必须带 dry_run；未声明 Action 无默认档。定位为**建议档位（advisory）**：档位进入邀请/指派观察记录并显式标 `assurance_enforced: false`，`Kernel.submit` 不消费、不构成闸门；强制化须另立审批证据与演练票据的持久化模型 |
| 选择审计 | `src/kernel/selection.py` | who / when / basis 三元组成对落账；basis 取投影 `decision_ref()`（KS-2.5 双引用的一半），可用 `resolve_decision_ref` 机械复核 |
| 责任传递入口 | `InitiativeEngine.select()` | 只能选本轮已给出且确有执行权的候选；写 `initiative.assignment`，**不写 EventStore** |
| 陈旧判定 | `Projection.stamp(entity)` / `entity_head()` | 候选携带渲染水位；选择时与实体当前水位不一致即 `SELECTION-STALE-BASIS`，留账前拒绝 |
| 续办视图 | `src/kernel/continuation.py` | 待办 / 陈旧 / 逾期；每次派生不缓存；无声明 SLA 则 `due_at=None` |
| 发起人身份 | `Kernel.submit(initiator=…)` → store 审计记录 + FileStore 重放 | `Event` 仍为八字段（KS-1.2 未动），initiator 只进审计元数据 |
| 观察链持久化 | `FileSession` + `SelectionLedger(session)` / `StewardshipRegistry(session=…)` | 先落盘成功再入内存（失败抛 `SESSION-PERSIST-FAIL` 不留半条）；重放重新校验三元组 / owner / 在册角色，篡改即拒；恢复的只是观察账，不参与投影重建 |
| 时间线实体归属 | `ContinuationView.timeline` 只读投影声明的 `entity_key` | 不再匹配 payload 任意值：同值旁路字段不会把别的实体事件算进来 |
| 选择幂等 | `SelectionLedger.record` 去重 + 引擎复用同 digest 的 assignment | 同一决策（主体/岗位/依据/档位全同）重试不重复留账、不重复分配；换岗位或依据仍是新决策 |
| 实体归属 | `Projection.entity_key`（必填） | 归属由 `Contract.object.yaml` 的 identity 驱动；「payload 值匹配」的隐式口径已删除 |
| 生成期守卫 | `tools/codegen.py::_assert_identities` | 聚合缺标识 → `AGGREGATE-IDENTITY-MISSING`；域画像 `entity_key` 与 identity 分叉 → `ENTITY-KEY-MISMATCH`；均在落盘前拒绝 |

**本轮红线表**（与 §8.3 同性质，写进结构不靠自觉）：

| 红线 | 结构保证 | 守卫测试 |
|---|---|---|
| 选择 ≠ 执行 | `select()` 只写选择账本与观察通道，EventStore 零增长；提交仍由持岗人发起 | `test_selection_records_triad_and_routes_to_holder` |
| 陈旧即拒 | 依据携带实体水位，与当前 `entity_head()` 不一致则在留账前拒绝 | `test_selection_rejects_stale_basis` |
| 续办只读 | 每次派生不缓存；不臆造期限；调用前后事件流、账本、水位零变化 | `test_continuation_is_read_only` / `test_continuation_lists_open_assignment_without_fake_deadline` |
| 收件箱只读 | `initiative.enabled_actions` 复用 `materialize` / `principal_env` / `eval_boolean`（与 submit 同源），不 append、不写审计；不可物化或不可求值即不展示 | `test_inbox_is_read_only_and_mirrors_permission_gate` / `test_inbox_reuses_the_same_evaluator_and_principal_env` |
| 档位不可破底 | 闸门清单为常量，声明无法缩减；自主档仍需 dry_run 取证 | `test_policy_rejects_gate_removal_declaration` / `test_policy_rejects_autonomous_without_dry_run` |

**证据**：全量 430 → 461 测试函数 / 446 → 475 用例；verify 三关、release 五关通过；
正典 `fff3d7e7…` 与声明摘要 `7c653e79…` 均未变——本轮全程未触碰 `spec/`。

## 9. 诚实边界

- 本文的设计主体已落地（§8 P0/P1/P1.5/P1.6/P1.7/P1.8），P2 与写路径接入仍属未做。
- B 的成员粒度是**域级**（org_unit / 岗位），不是单实例级；实例差异靠 owner 归属层与显式覆盖。
- 可见集 V 的完备性依赖该项目**全部 Action 都已声明**——若某切面的动作未进在册声明，
  该切面角色就不在 V 里（fail-closed 的正确表现，但需治理面补齐才完整）。
- 推导正确性依赖治理声明完整，由现有对账守卫保证；绕过 GOV 通道手改声明，摘要哈希漂移
  被 verify 拒绝。本模块的单一事实源守卫（`test_single_fact_source_agrees_with_generated_projection`）
  进一步锁定"推导 == 生成投影"，一旦漂移即失败。
- 项目归属（哪些 Action 属于同一项目）当前靠 `spec/competence/domains/*.domain.yaml`
  的 actions 段提供；调用 `scan/can_interact/domain_of` 时可不传 `action_types` 取治理面
  全部 Action 的并集（保守放大可见集，不漏切面）。
- 唯一执行判据是 `CapabilityLedger.can_execute`（读 `compiled` 权限矩阵）；它不改变
  `Kernel.submit` 的强制行为，二者同源，不会出现"预检可过、submit 被拒"的口径分裂。
  `stewardship.executor_roles` 是治理面对账视图，不是判据——同名 `can_execute` 已移除。
- `seek()` 的域门控必须成对传 `stream_id` + `entity_id`；只给其一即拒。
  触发谓词单参为全快照判定（兼容旧写法），双参按目标实体判定（多实体场景必须用双参，
  否则会全表扇出 offer）。
