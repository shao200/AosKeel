# 08 · 基于脚手架构建企业级"本体论 + AI"应用

> **效力**：信息性材料，不产生规范条款；一切 MUST 以 [AOS 规范 v2.0.0](../aos-spec.md) 为准。
> **读者**：已完成 [04 实操教程](04-tutorial.md) 首跑、准备把 AosKeel 用于真实企业系统的架构师与工程负责人。
> **本篇回答的问题**：`aos init` 之后，一个企业级本体论 + AI 应用是怎样一步步长出来的？脚手架给了什么，你必须自己补什么？

示例领域取"保险理赔"（与模板自带的 Contract 样例同构，命令与语法均可在模板上直接套用）。

---

## 全景：从领域共识到可签发系统

```
企业领域知识 ──(LLM 起草)──> 需求 DSL ──(机械把关)──> spec/ 八类声明
                                                        │ 注册管线（失败=不启动）
                                                        ▼
                                                能力清单 + 编译产物
     持久化存储/SSO/治理流程 ⟸(实例侧自建)⟽             │
                                                        ▼
  Agent(LLM) ←读← 投影 ←重放← 事件日志 ←写← Kernel.submit（唯一写路径）
     │              ↑三引用↑                    │
     └──会话流(观测)──┴──决策流(审计)────────────┘
                 三道闸门 + 布线测试 + 发布清单：治理内建
```

方法论一句话：**用声明层固化企业共识，用注册管线把共识变成启动条件，用能力子集把 AI 圈在确定性边界内做提议者，用治理通道让每一条规则可追溯到一次真实的人类批准。**

---

## 阶段 0 · 实例化与自登记

```powershell
aos init claims-system
cd claims-system
python src/cli/main.py bootstrap --stage 0   # 实例自行登记首个 AOS-ART 条目
python src/cli/main.py verify                 # 三关首跑
```

此刻你得到的不是空目录，而是一个**已通过自身治理校验的最小系统**：能力清单已发布，任何未注册的状态变更能力都不存在。未做 BOOT-0 时约 7 项测试失败是设计行为（GOV-1 不合成登记），不是缺陷。

---

## 阶段 1 · 领域建模：把企业共识写成 TBox

`spec/` 八类声明就是"概念化的显式规范"，每类回答一个建模问题：

| 声明 | 回答的问题 | 理赔示例 |
|---|---|---|
| `ontology/objects/Claim.object.yaml` | 什么概念存在？ | Claim：标识 claim_id，属性 status/amount/policy_ref |
| `ontology/links/*.link.yaml` | 概念间什么结构关系？ | same_as（系统写、零业务语义、跨上下文同一性） |
| `aggregates/ClaimAggregate.aggregate.yaml` | 一致性边界与并发单位？ | 流 `domain:ClaimAggregate` + 求值预算 ≤10⁵（R8） |
| `contexts/ClaimsContext.context.yaml` | 谁拥有哪块语义？ | **steward 必填**（P-3）+ 投影延迟预算（P-16） |
| `ontology/actions/*.action.yaml` | **世界允许怎样被改变？** | SettleClaim：参数+条件+权限+审计+演练 |
| `invariants/*.invariant.yaml` | 什么必须永远为真？ | "已结案金额 ≤ 保额"（三元组：声明+违规语义+修复绑定） |
| `mappings/*.mapping.yaml` | 外部数据怎样进入？ | 核心保单视图（语义损耗必须显式声明，KS-4） |
| `processes/*.process.yaml` | 跨聚合流程怎样编排？ | 理赔-支付-退单（补偿必须是指册 Action，P-9） |

Action 声明是整套方法的重心——企业规则从会议纪要变成机器检查：

```yaml
action_type: SettleClaim
aggregate: ClaimAggregate
params:
  claim_id: { type: ref, required: true }
submission_criteria:
  structural:
    - "exists claim_id"
  conditional:
    expression: "snapshot.status == 'approved' and snapshot.amount <= snapshot.coverage"
    snapshot_inputs: [status, amount, coverage, principal.role]
permissions: { roles: [claims_settler], contexts: [ClaimsContext] }
audit: required
dry_run: required          # 高风险动作：先演练后执行（P-12）
```

条件表达式的合法词汇以受限解释器白名单为准（KS-3.2 R1–R11）：只允许 `snapshot.*` / `principal.*` 两源、纯集合操作与函数白名单，dunder 属性链与任何宿主语义即拒。

---

## 阶段 2 · AI 起草 + 治理晋升（本体论 + AI 的分工点）

脚手架对"AI 参与建模"的制度化：**LLM 负责起草，机械负责把关，人负责签发**（AX-2 在开发流程上的投影）。

```powershell
# 1) 业务语言 → 需求 DSL（LLM/Agent 产出此格式即可，确定性解析器接管；GOV-6 起草智能可换）
python src/cli/main.py draft requirements-claims.txt --name claims
#    编译不过 → 逐条报告、不落盘（KS-7.1 把关）
# 2) 人工确认后走治理通道晋升（提案号来自真实审批流，GOV-1 拒绝合成）
python src/cli/main.py draft promote spec/drafts/claims.yaml --proposal-ref SPEC-2026-001
```

需求 DSL 语法（参见 `docs/samples/requirements-sample.txt`）：

```
聚合体: ClaimAggregate
  流: domain:ClaimAggregate
  预算: 10000

对象: Claim
  标识: claim_id
  属性: status, amount, policy_ref

动作: SettleClaim
  聚合: ClaimAggregate
  参数: claim_id(必填)
  结构: exists claim_id
  条件: snapshot.status == 'approved'
```

晋升后注册管线单写更新能力清单（P-5），`declared == registered` 对账必然全绿。

---

## 阶段 3 · 生成骨架并实现效果层

```powershell
python src/cli/main.py generate    # 声明 → src/generated/actions.py + reducers.py
```

骨架带 provenance 头，手改后禁静默覆盖（字节比对）。`reducers.py`——事件如何改变投影状态——就是声明的**效果语义实现处**。注意：形式化目前只覆盖前置条件（提交条件），效果层是脚手架留给工程团队的真实工作量所在（见"阶段 7"与 06 §7 边界）。

---

## 阶段 4 · 接入外部世界（两条合法通道，二选一）

外部事实进入本体只有 AX-1 认可的两条路：

1. **摄取 Action**：外部变更触发指册动作（如 `IngestPolicyRecord`），事件负载强制携带出处（来源系统、源时间、置信度，KS-4.1）——成为权威事实；
2. **只读 Mapping**：外部系统经映射投影进上下文，不产生本体事件——只作决策输入。

禁止第三条路：存储层 `write_raw` 直写陷阱必拒并留 `structurally-rejected` 审计（INV-1 / VER-28）。

---

## 阶段 5 · 装配 AI Agent 运行时

Agent 在这套体系里的位置被精确规定（P-10 / KS-2）：

| 环节 | 机制 | 约束 |
|---|---|---|
| 读 | 投影（T17） | Agent 只看确定性视图；会话流禁止参与权威重建（KS-2.2/2.4） |
| 判 | LLM / 规则引擎 | 概率性，只能产出"提议"（AX-2） |
| 写 | `AgentRuntime` → `Kernel.submit` | 能力面 = 上下文能力清单的**严格子集**；未注册动作对 Agent 根本不存在 |
| 证 | `record_decision` 三引用 | （投影标识, transaction_time, 会话事件引用）缺一即拒（KS-2.5 / P-16） |

效果是审计四问的机械可答性："当时基于什么信息（投影快照哈希）、想了什么（会话流）、做了什么（Action）、结果如何（事件+条件求值审计）"——在纯 LLM 系统里靠日志碰运气，在这里是启动前置条件。

---

## 阶段 6 · 验证与签发

```powershell
python src/cli/main.py test        # 按 config/verification.yaml 布线（新增声明的守卫要补进来）
python src/cli/main.py verify      # 三关：指纹 → 哈希 → declared==registered
python src/cli/main.py release     # fail-closed：三关+布线全绿+骨架零漂移 → RELEASE-MANIFEST
```

5 个〔强〕项（VER-20/24/26/27/28/29 中的人工部分）指向 `bootstrap/checklists/`——由人执行、留证据、签字；模板永远不代签"通过"。

---

## 阶段 7 · 实例侧必须自建的生产件（诚实边界）

脚手架交付的是**内核参考实现**。投产前，五件事必须补齐：

1. **持久事件存储**——模板 `EventStore` 是内存 dict；`kernel/filestore.py` 已给 FileStore **参考实现**（JSONL 追加 + 重放，拒绝不落盘，单写进程模型，守卫见 `tests/conformance/test_filestore.py`）。装配只换一处：`Kernel(FileStore("data/events.jsonl"), SessionChannel(), compile_all())`。多进程/多实例生产并发须以数据库实现同一协议（streams 只读 + commit 唯一写面 + audit 只增），并自行取证 append-only 与审计持久性（数据库仅经摄取 Action 或映射进入本体，见阶段 4）；
2. **主体身份接入**——T03 主体身份来自平台 authN（SSO/LDAP），生产环境 `principal` 参数不可信自报；`roles` 证据同样必须由认证层解析后出示，调用方自报的 `roles` 与自报的 `principal` 一样不可信；
3. **权限强制点已归位（模板层）**——`Kernel.submit` 在单一写路径上强制 `permissions.roles`：出示的角色与声明角色不相交即 `PermissionDenied`，在触达存储与评估之前（fail-closed，P-10/INV-4）；实例侧剩余职责只是把 authN 结果接到 `roles` 参数上；
4. **条件求值物化投影**——当前条件在调用方参数快照上求值而非权威投影状态（评审已知裂缝），高风险域须接投影快照后再求值；
5. **BOOT-2/3 治理工作流与 Identity Context**——模板层明示未实装，治理闭环依赖组织流程。

---

## 团队分工与推进节奏（建议）

| 角色 | 负责 | 产出物 |
|---|---|---|
| 领域专家 | 审定八类声明的业务语义；执行〔强〕项 | 提案记录、检查表签字 |
| 架构师 | 上下文/聚合切分；不变量三元组 | spec/ 声明 + 能力问题清单 |
| 工程团队 | reducers/持久化/SSO 与 roles 证据接入 | src/generated 实现 + 实例侧守卫 |
| AI 工程师 | Agent 装配、起草 DSL | 提议-把关流水线 + 决策引用纪律 |
| 治理委员会 | GOV-3 提案处置、SpecChange | 提案号（draft promote 的必填输入） |

推进节奏建议：先以 1 个上下文、3–5 个 Action 走通阶段 0→6 全链路（一周内可完成），再按上下文逐个扩展——每个新上下文独立走声明→把关→晋升→生成→守卫循环。

---

## 延伸阅读

- 命令逐条真实输出：[04 实操教程](04-tutorial.md)
- 条款落点与失败定位：[03 实现方法](03-implementation.md)、[05 速查](05-reference.md)
- 本体论边界（哪些推理有意不提供）：[06 形式语义](06-formal-semantics.md)
- 内核失败形态可运行代码：[07 内核实操](07-kernel-walkthrough.md)
