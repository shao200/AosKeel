# AosKeel 同行评议意见
## —— 基于本体论理论与发展实践的评判

**被评审对象**：AosKeel（`aos-keel` 模板 v0.3，实现 AOS 规范 v2.0.0，登记哈希 sha256:e6884aed…，见 docs/ARTIFACT-REGISTRY.md）
**评审材料**：README.md、docs/aos-spec.md（673 行冻结中文正典）、docs/guide/（含 01-foundations、06-formal-semantics）、spec/ 全部 9 个声明文件、src/kernel 与 src/interpreter 全部模块、tools/、config/verification.yaml、tests/（41 文件 / 约 162 个测试函数）
**评审性质**：基于对规范文本与代码实现的直接核查，非二手转述

---

## 〇、评审基线与修订响应（2026-11-17 复核补记）

**历史基线**：本评议正文写于 2026-11-15，材料口径为"spec/ 9 个声明文件 / 41 测试文件 / 约 162 个测试函数"。此后仓库经 `v0.3.0` → `1a745bc` → `2aad3e0` 连续迭代，并经三轮修补，当前规模为 **spec/ 28 份声明（含 10 张 CQ、1 份元 schema、2 份域画像与 3 张自定义域题）/ 70 测试文件 / 353 测试函数，60 条布线**。正文保留原貌以供审计，不就地改写历史意见；下述响应表给出逐条状态。

**复核基线**：`HEAD 2aad3e0` + 三轮修补（声明摘要 AOS-DECL-005，正典哈希仍 `e6884aed…`）。

**第二轮修补（2026-11-17，理论层）**：在第一轮工程面收口后，继续兑现原评议 4/5/6 三条。新增 `spec/competence/CQ-1..10.cq.yaml` + `tools/cq.py`（回答者注册表 + 真实内核夹具 + 可失败断言）、`spec/meta/declaration-schema.yaml` + `registration.validate_meta_schema`，中英 README 补四谱系表；`pipeline.py` 把评估快照本体写入 KS-3.3 审计，使 CQ-4 的"表达式 + 快照 + 结果"由文档宣称变为可核事实。声明摘要按 GOV-2.3-DECL 追加登记（AOS-DECL-003/004），正典哈希仍 `e6884aed…`。

| # | 原修订要求 | 复核判定 | 本轮响应与证据 |
|---|---|---|---|
| 1 | Action 补形式化效果 | 部分 | 未扩：`effects` 仍是常量赋值；注册期校验属性/枚举域（`registration._validate_effects`）成立，但无条件效果与双向映射仍缺 |
| 2 | 权限强制点移入 `Kernel.submit` | 已修 + 加固 | `pipeline.py:65-72` 评估前拒绝已生效；本轮进一步把 `principal.role` 从"主体名字符串"改为内核出示的 `roles` 证据（`test_declaration_execution`） |
| 3 | 条件求值物化投影 | 部分 | 保持：`materialize()` 重放 reducer + 谎报拦截有效；无 reducer / 无 identity / 首次观测回退 params 是**已披露边界**，未伪称消除 |
| 4 | 可执行 competence questions | 已修（第二轮） | `spec/competence/CQ-1..10.cq.yaml` + `tools/cq.py` 回答者注册表 + `aos cq`；十题在真实内核夹具上执行，删题/未注册/断言错即 fail-closed；`test_competence_questions` 证明可证伪 |
| 5 | 元 schema 声明化 + 哈希域扩展 | 已修（第二轮） | 上一轮完成摘要域与第四道；本轮 `spec/meta/declaration-schema.yaml` 声明九类骨架字段与类型，`registration.validate_meta_schema` 注册期执行，专用语义校验保留原位；`test_meta_schema` 守卫 |
| 6 | 修订 README 学术谱系 | 已修（第二轮） | 中英首屏增四谱系表（描述逻辑 / 动作形式化 / 道义逻辑 / 工业图本体），明确"不是推理机、规划器、三元组库"；guide/01 把 Palantir 降为工业先例；PDDL 引用更正为 McDermott et al. (1998) |

**第三轮修补（2026-11-17，域无关 CQ 定义）**：第二轮虽把十张 CQ 变成可执行契约，但回答者内部仍硬编码 `ContractAggregate` / `ApproveContract` / 治理文件路径，`EXPECTED_IDS` 也写死十题——实例换域必须改 Python。本轮把域参数外提到 `spec/competence/domains/contract.domain.yaml`，夹具改由画像种子声明驱动真实内核，十个回答者改为域无关原语；新增 `audit-review` 域画像与三张自定义域题，证明"只写 YAML 即可定义自己的 CQ"（`aos cq --domain audit-review` 3/3，probe 可为空）。contract 域仍保留十题冻结清单防删题。声明摘要追加登记 AOS-DECL-005，正典哈希仍 `e6884aed…`。

**本轮新发现修补状态**

| 级别 | 发现 | 状态 | 可验证证据 |
|---|---|---|---|
| P0 | 声明语义不在密码学冻结域 | 已修 | 副本实验改 `10**6`→`10**9` → `verify` 第四道 MISMATCH；正典哈希不变（`test_declaration_digest`） |
| P0 | 控制台按首词放行治理写面 | 已修 | 白名单改「首词+子命令」二元组；`spec version` / `spec register-declarations` / `draft promote` 经 HTTP 均 403（`test_console`） |
| P1 | 死算子、无执行点字段、流名硬编码、principal 证据自报 | 已修 | `references` 注册期拒绝；`dry_run⇒audit`、`contexts` 引用完整性注册期校验；`stream` 取声明；`principal.*` 取内核证据 |
| P2 | 口径漂移、文献错引、测试写源码树 | 已修 | `tools/doc_metrics.py` 单一权威源（CLI 26 命令面 / 布线 60 条 / INTEGRITY 28 条）+ `test_doc_consistency` 锁住五份消费端；PDDL 文献 #10 更正为 McDermott et al. (1998)；语义提取样例改落 pytest `tmp_path`，`tools/` 源码树零残留 |

---

## 一、论文/系统摘要（评审者复述）

AosKeel 是一个"规范驱动、治理内建、机器可校验"的 0→1 脚手架，声称以本体论约束 LLM Agent 系统。核心构件为 T01 四元组（ObjectType/Property/LinkType/ActionType）与 T02 四构造（ContextType/AggregateType/Mapping/ProcessType），事实层为八字段 append-only 事件日志（AX-1"事件即真源"），查询层为确定性重放的只读投影。业务规则通过 submission_criteria 编译为受限 AST 布尔函数；启动与发布由三道闸门（结构指纹 → 密码学哈希 → declared==registered 双射）把关。项目自述 TBox/ABox 仅为"教学类比"，不使用 RDF/SPARQL/DL 推理机，并列出六条"诚实边界"。

---

## 二、理论评判：以本体论的标准衡量

### 2.1 判据选取

采用本体论领域两个最常被引用的定义作为标尺：Gruber（1993）的"概念化的显式规范（explicit specification of a conceptualization）"，以及 Studer 等（1998）补充的"形式化 + 共享"限定。在此之下，一个本体系统的理论成色通常考察五个维度：**概念与关系的形式化深度、公理与约束语言、推理服务、方法论（能力问题驱动）、演化与版本管理**。以下逐项对照。

### 2.2 概念/关系层：轻量但诚实

T01 四元组对"类—属性—关系—操作"的覆盖是完整的最小集。但核查 spec/ 九个实例文件后确认：

- **无类层次语义**。is-a/part-of 仅作为链接实例存在，注册与提交流水线中没有任何继承、传递闭包或包含（subsumption）推理处理；
- **无 domain/range 约束**，属性只有枚举/十进制/列表等数据类型；
- **无形式化基数公理**。"每个订单恰好一个客户"这一 README 自己举例的公理场景，在 AOS 声明语言里只能退化为 `exists` / `max_len` 结构检查或一条不变量布尔式，无法像 OWL 的 `⩽1` 限制那样参与推理。

按描述逻辑（DL）的表达能力谱系，AOS 声明层大致位于 RDF Schema 之下、接近"带类型注解的模式（schema）"。项目对此**并不隐瞒**——06-formal-semantics.md §7 明确列出有意不提供层次传递、复杂基数、默认/非单调推理、图查询，并直言"AosKeel 不是描述逻辑推理器"。这在评审伦理上是加分项，但在理论定位上产生一个必须指出的矛盾（见 2.4）。

### 2.3 ActionType 的增量：真实，但学术先例比项目自述的更近

AOS 的核心宣称是从"描述性本体"到"治理性本体"的跃迁：OWL 能表达"已批准的合同是合同"，不能表达"只有合同管家且金额不超过一百万才能批准"。前半句是对的——OWL 是单调的真值描述逻辑，确实不表达许可；后半句也是对的。但由此推出的"第四元素"并非本体论内部的增量，而是**行动形式化（action formalization）传统的增量**：

- ActionType 的"参数 + 提交条件 + 副作用 + 权限"结构，与 PDDL 动作模式（parameters / precondition / effect）几乎同构，与情境演算（McCarthy）、事件演算（Kowalski & Sergot）中的事件— fluent 建模同源；
- "权限不进本体而进动作契约"的立场，其形式化归宿是道义逻辑（deontic logic）或授权语义，而非任何主流 OWL 扩展。

项目附录 D 提到了 SHACL、Rego、双时态数据库、Event Sourcing 等血统并自称"站在其上，非平行"，这是恰如其分的自我认知；但 README §1 与 01-foundations 把 Palantir 式工业本体作为主要背书、把 ActionType 叙述为本体论的"决定性差异"，**弱化了行动形式化这条更贴切的学术谱系**。同行评议角度：这是引用/定位上的可修订问题，不是错误。

一个更实质的理论缺口：**Action 只有前置条件，没有形式化效果（effect）**。提交条件被编译、被求值、被审计，但事件对世界的改变写在手写 Python reducer（projection.py 等）里，声明层与效果语义之间没有双向映射。用情境演算的话说，AOS 形式化了 precondition 而把 effect 留给人肉代码——这使得"声明 == 注册"双射实际上只覆盖能力清单，不覆盖状态变更语义。README §2 表格宣称消除"规范与代码之间的语义漂移"，就效果层而言该宣称未被机制支撑。

### 2.4 与本体工程方法论的对照：能力问题缺位

现代本体工程（Gruninger & Fox 的 competence questions、METHONTOLOGY、NeOn 方法论）的共识是：本体好坏由能力问题（CQ）能否被回答来验收。06-formal-semantics.md 提到了 CQ-1..10 与七步法的映射框架，但核查全部 spec/、tests/golden/ 后确认：**模板层没有给出任何一个可执行的 CQ 实例**，也没有查询/图遍历语言去回答它们（ABox 是事件流 + 投影，无 SPARQL 对应物）。这意味着本体的"共享共识、可被提问"这一功能维度在脚手架层是空的——项目把本体降维成了类型化的状态机规格，这与其"教学类比"的自我免责声明一致，但与 README 标题级宣称"ontology-based"之间存在张力。

### 2.5 元模型自反性：违反了自己的 AX-5

AX-5"Schema 即数据"宣称元层也应在声明体系内。核查确认：八类声明的元 schema 并未声明化——校验逻辑散落在 registration.py 的过程代码里（"约定即规范"）。哈希闸门的覆盖域只有 aos-spec.md 与 SPEC-FINGERPRINT.md 两个文件，声明文件本身不在密码学冻结域内。治理体系对自身地基的约束弱于它对业务声明的约束，这是形式化系统设计中典型的自指弱点，项目已通过"结构指纹层是弱保证"的免责声明部分承认。

**理论维度小结**：以本体论严格标准衡量，AosKeel 是一个"本体邻近"的治理性规格系统——它借用了本体的词汇（TBox/ABox/三元组）而放弃了本体的核心机器（公理语言 + 推理服务）。它的真正理论贡献候选是"治理即启动前置条件"与"事件作为带出处的断言"两点，这两点确实超出了经典本体论的处理范围。项目对自身的 DL 不等价性有清醒声明，理论上诚实，但 README 的叙事强度略高于其本体论实质。

---

## 三、实践评判：工程实现核查

### 3.1 经得起核查的部分（强项）

1. **负向白名单解释器是真实的**：boolean_profile.py 的 AST 节点白名单、函数白名单、`__builtins__` 清空、深度上限、未声明名即拒（fail-closed）均已实现，且有 redteam 测试攻击路径；
2. **八字段事件与不可变性属实**：frozen dataclass + MappingProxyType，valid_time ≤ transaction_time 写时校验，版本冲突触发整条评估重跑（有测试计数断言），与 KS 条款声明一致；
3. **VER-1..33 全条挂接**：28 条自动验证指向真实测试路径，5 条强制项指向人工清单且模板拒绝代为签"通过"——"不合成合法性"（GOV-1）在 CLI 层确有代码兑现；
4. **诚实边界与代码相符**：内存存储、wheel 拒绝运行、指纹层弱等六条 README 自认局限，逐一在代码中核实为真。这在同类"理论驱动框架"项目中相当罕见。

### 3.2 实现与宣称之间的裂缝（须在正文列出）

| # | 发现 | 位置 | 影响 |
|---|---|---|---|
| 1 | `submission_criteria` 的条件快照取自调用方传入的 `params`，代码注释自承"模板层不物化投影" | pipeline.py:55-57 | "规则编译进机器检查"的核心卖点在模板层实际未对权威状态求值，只在参数上求值 |
| 2 | `permissions.roles/contexts` 编译进 CompiledAction 但 Kernel.submit 不强制，仅在 AgentRuntime 自检 | registration.py / agents/runtime.py | 能力检查先于存储拒绝（P-10/INV-4）的承诺在 kernel 层有洞 |
| 3 | `dry_run: required` 被编译但管线从不读取；`references` 结构算子有声明位但无执行点 | pipeline.py / sc_compiler.py:61-68 | P-12 等模式在模板层不可验证，属"规范超前于实现" |
| 4 | verification.yaml 声明的 invariants 套件目录不存在（gate:false 不阻断）；RUNBOOK 引用的 .github/workflows/ci.yml 缺失 | config / .github | 验证挂接存在静默空档 |
| 5 | BOOT-2/3 治理工作流、Identity Context、KS-8 创世窗口大部分返回"未实装" | cli/main.py:154-155, genesis.py | 六条治理条款中启动阶段相关的部分只有骨架 |

这些缺口大多在"诚实边界"精神上可辩护（模板不是产品），但 #1 和 #2 直接触及项目最核心的两条宣称（规则机器化、权限硬约束），建议在文档中同等显眼地承认，而非只埋在代码注释里。

### 3.3 建模层的实践单薄

八类声明共 9 个示例文件，全部围绕单一 Contract 领域。对一个以"声明即真源"的框架，缺跨聚合不变量、缺 upcasting 实例、缺 Mapping golden set 的对照示例，会让 `aos init` 后的用户面对正典 673 行规范却只有玩具级样本。规范文本体量与示例/实现体量约 673 行 : 9 文件 : 3.5k 行代码的不对称，是采纳摩擦的主要来源。

---

## 四、总体评判与结论

**定位判断**：AosKeel 目前最好的身份不是"本体系统"，而是**面向 Agent 系统的可验证领域规格 + 治理内核参考实现**。它把本体工程里"显式、形式、可审计"的价值观做到了罕见的机械可核对程度，同时把本体工程里"公理化 + 推理"的技术内核有意搁置。这个取舍是自洽的、被声明的，但 README 第一屏的叙事（"LLM 需要本体""决定性差异"）会让本体论背景的读者高估其 DL/OWL 血统。

**优点**（评审意见原文措辞）：
- 条款 ID ↔ 代码 ↔ 测试三向锚定的可追溯性，是我所见同类框架中最严格的一档；
- fail-closed 与负向测试文化贯穿始终；
- 反事实设计法（事故类别 A-R → 模式移除后果 → INV 裁决）为每条约束提供了可辩驳的理由链；
- 自我边界声明的诚实度极高且经代码核实为真。

**须修订的问题**（按严重度排序）：
1. 为 ActionType 补形式化效果语义，或正式把"效果层不在保证范围"升格为一条与六条并列的诚实边界；
2. 将权限强制点移入 Kernel.submit 单一写路径，使 P-10/INV-4 的宣称与执行点一致；
3. 条件求值物化投影（或在文档中明示当前求值口径的差异）；
4. 引入至少一组可执行的 competence questions 与回答它们的查询示例，让"本体"一词名实相副；
5. 考虑将元 schema 声明化（兑现 AX-5），并把哈希覆盖域扩展到 spec/ 声明文件；
6. 修订 README 谱系叙述，引用行动形式化（PDDL/事件演算）与道义逻辑传统，降低对 OWL 缺位的归因式表述。

**审稿结论**：作为工程脚手架 —— **accept（强）**；作为"ontology-based"的理论宣称 —— **major revision**。项目不需要成为 DL 推理器才有价值，但它需要把"放弃推理内核"从免责声明升级为与"治理性本体"并列的显式设计论点，并修补权限与条件求值两处执行点裂缝。若修订完成，这一"治理即启动条件"的框架有潜力成为 Agent 规格领域的有引用价值的参考实现。

---

## 五、主要参考文献

1. Gruber, T. R. (1993). *A Translation Approach to Portable Ontology Specifications*. Knowledge Acquisition 5(2).
2. Studer, R., Benjamins, R., Fensel, D. (1998). *Knowledge Engineering: Principles and Methods*. Data & Knowledge Engineering 25.
3. Baader, F. et al. (2003). *The Description Logic Handbook*. Cambridge University Press.
4. W3C (2012/2024). *OWL 2 Ontology Language, Structural and Logical Specification*.
5. W3C (2017). *Shapes Constraint Language (SHACL)*.
6. Gruninger, M., Fox, M. S. (1995). *Methodology for the Design and Evaluation of Ontologies*. IJCAI Workshop on Ontologies.
7. Gómez-Pérez, A., Fernández-López, M., Cabrerizo, F. J. (2004). *A Methodology Description to Develop Ontologies* (METHONTOLOGY).
8. McGuinness, D. L. et al. (2014). *Ontology Development 101* 后续谱系与 NeOn Methodology (Suárez-Figueroa et al., 2012).
9. McCarthy, J. (1963). *Situations, Actions, and Causal Laws*; Kowalski, R., Sergot, M. (1986). *A Logic-Based Calculus of Events*.
10. McDermott, D., Ghallab, M., Howe, A., Knoblock, C., Ram, A., Veloso, M., Weld, D. & Wilkins, D. (1998). *PDDL — The Planning Domain Definition Language*（AIPS-98 规划竞赛委员会；动作模式 parameters/precondition/effect 结构之先例）. 本条原误署 Ghemawat / Fox (2003)，已于 2026-11-17 复核时更正 —— Ghemawat 以 GFS/MapReduce 著称，非 PDDL 作者。
11. Snodgrass, R. T. (1992). *Developing Time-Oriented Database Applications in SQL*（双时态建模先例）；Fowler, M. (2005). *Event Sourcing*（模式命名）.
12. Palantir Technologies. *Foundry Ontology* 产品文档（Object/Link/Action 工业先例；第二轮修订后 README 仅作工程形态对照，不再作为理论背书）.
13. von Wright, G. H. (1951). *Deontic Logic*. Mind 60(237)（许可/义务语义之源）.
14. Jones, A. J. I. & Carmo, J. (1993). *Deontic Logic and Contrary-to-Duties*. Handbook of Philosophical Logic（规范推理中例外与违例的结构化）.
15. Reiter, R. (2001). *Knowledge in Action: Logical Foundations for Specifying and Implementing Dynamical Systems*. MIT Press（情境演算与行动理论的系统表述）.

（注：以上文献为本体论/行动形式化领域稳定经典，用于建立评判坐标系；对 AosKeel 的一切事实性论断均来自对被评审仓库文件与代码的直接核查，正文 §3.2 已逐项标注位置。）
