# AosKeel 白皮书 —— 本体驱动的企业级 AI 架构迁移引擎

> 版本：v1.0（2026-11）· 语言：中文（术语与正典一致）· 配套：[README](../README.md) · [正式规范](aos-spec.md)

## 0. 定位

**AosKeel = 语义提炼 → 契约声明 → 确定性生成 → 闭环治理 的完整技术栈。**

它不只是代码生成器，而是把企业"老系统（Legacy）"向"本体论 + AI"体系迁徙的工程纪律集合。老系统的业务逻辑是"死的"（改动靠人肉）；本体驱动的系统是"活的"（改声明，机器重编译，闸门把关）。

AosKeel 实现的规范是 *AOS: Ontology-Based Agent System Development Specification* v2.0.0（[正式规范](aos-spec.md)）：30 条内核语义、13 条全局不变量、6 条治理条款、33 个验证点，全部机器可校验。

## 1. 理论基座：五层标准模型 + 治理面横切

```
L1 概念层  spec/contexts/      限界上下文、统一语言（职责域 owner）
L2 结构层  spec/ontology/objects + links、spec/aggregates/   实体、关系、聚合边界
L3 约束层  spec/invariants/    不变量、状态约束、权限约束（requires-role/duty）
L4 行为层  spec/ontology/actions/ + spec/processes/          命令、状态机、SLA
L5 映射层  spec/mappings/      到后端 / 前端 / 存储 / API 的投影
─────────────────────────────────────────────
治理面横切 spec/governance/     职责授权矩阵（图1）：岗位 × 组织锚点 × 职责项 × 额度
```

**横切必须在每层留锚点**，否则横切退化为贴在代码上的装饰：

| 层 | 治理锚点 | 生成落点 |
|---|---|---|
| L1 | context 的职责域 owner | 上下文地图 |
| L2 | object 的 ownership 标注 | 聚合归属 |
| L3 | invariant 的 `requires-role`/`requires-duty` | 写端鉴权断言 |
| L4 | action 的 authorization + process 的 SLA | `command_api.ROUTES` 的 `required_roles`/`duty` |
| L5 | mapping 生成时注入拦截器/审计/claims 断言 | OAuth JWT claims = 治理面直接投影 |

**OAuth 2.1 不是独立插件，是治理面的投影**：`claims = { org, duty[], roles[] }` 来自 L1/L2 的 ownership 与 L3 的授权约束；IdP 出示未声明岗位 = 拒绝（`UNDECLARED-POSITION`，fail-closed）。

## 2. 十条核心纪律（比代码更稀缺的部分）

1. **确定性生成，LLM 只产草案。** 生成物（Command/Query/OAuth2.1 骨架）全部由模板引擎产出、字节级零漂移（release gate 强制）。LLM 的唯一合法位置是 `aos draft` 的候选生产者：LLM 提候选 → 编译闸把关 → 人工裁决晋升。LLM 永远不直接写正典。
2. **三段闸：草案 → 编译 → 晋升。** 一切素材（需求 DSL、老库 schema、老库数据、文档）进来都是草案（`spec/drafts/`、`data-drafts/`），编译不过不落盘；晋升必须携带治理提案引用（GOV-1：CLI 只记录治理结果，不合成正当性）。
3. **fail-closed。** 未注册动作没有写路径（INV-1）；角色未出示在触碰存储前拒绝（P-10/INV-4）；未知能力/环/脏行/凭据缺失一律拒绝——系统对"不确定"的回答永远是"不"。
4. **凭据永不落盘。** 连接串、签名密钥、密码是运行时凭据：命令行传入或环境变量，不进任何声明文件、任何草案、任何报告。
5. **append-only + 单一写者。** spec 是注册制（GOV-3 版本通道 + 治理提案）；事件日志八字段只追加不更新；投影可丢弃重建。
6. **能力 Profile 依赖推导。** 用户选择"能力"（backend.cqrs / auth.oauth2_1 / frontend…），脚手架按依赖图拓扑展开（`auth.oauth2_1 → governance.duty_matrix` 强制），锚点缺失拒绝生成——选择单位是能力，不是模块勾选。
7. **数据迁徙 = 创世事件 + 求值链验证。** 老数据不是搬进新库，而是作为领域事件重放进新体系的完整求值链：违反新体系约束的行 = 拒绝（脏数据不得洗白进事件流）。
8. **影子对账。** 同一业务事实，老系统按行存、新体系按事件流存，逐行对账语义等价（求值链接受 / 映射字段无损 / 声明效果落位）；未映射列如实披露为对账盲区。
9. **壳，不是核。** WEB 控制台（`tools/console.py`）不 import 内核——subprocess 驱动同一组 CLI 命令；命令白名单 fail-closed；治理签署类命令（release/register/bootstrap）不在壳中提供。界面换皮，内核纪律不变。
10. **诚实披露边界。** 每个工具头注释写明"它不做什"。mandatory 条款永不自动打勾；翻译/覆盖度/盲区大声列出，不静默跳过。

## 3. 迁徙管线全景（新旧系统殊途同归）

```
aos init <dir> --depth standard      ① 实例化 + 能力广度定制（依赖自动展开）
aos import-db --ddl legacy.sql       ② 结构提取：老库元结构 → 本体草案（只读 schema）
aos review                           ③ 集中裁决清单（锚点 / 草案候选 / 治理对账）
aos draft promote --proposal-ref …   ④ 人工裁决落点（GOV-1 提案强制）
aos generate                         ⑤ 新体系代码：治理 → CQRS → OAuth2.1 拓扑序
aos import-data --dsn … --map M      ⑥ 数据移植：老库行 → 创世事件草案（逐行过求值链）
aos shadow --dsn … --map M           ⑦ 影子对账：行 ↔ 事件语义等价，差异回 ③
tools/console.py                     ⑧ WEB 控制台壳（驱动 ①–⑦，白名单 fail-closed）
```

新建系统与旧系统迁移收敛到**同一 spec + profile**，后续三关验证（结构指纹 → 密码学哈希 → 声明=注册对账）与发布闸门（47+ 条布线测试、骨架字节校验）完全一致。

## 4. 六大核心组件 → 实际落点

| 组件 | 落点 | 状态 |
|---|---|---|
| Ontology-Core（元模型） | `spec/` 九类声明 + `src/kernel/registration.py` 编译器 + 指纹清单 | ✅ |
| Legacy-Scanner（老系统扫描） | `aos import-db`（DDL/直连 → 结构草案）；代码/文档语义提取 | 结构 ✅，语义 ⬜ |
| Semantic-DSL（声明式语言） | 需求 DSL + 三段闸 + GOV-1 晋升提案制 | ✅ |
| AI-Generation Pipeline | 确定性 codegen（治理→CQRS→OAuth2.1 拓扑序）+ draft 闸 | ✅ |
| Governance-Console | `aos review` + 职责授权矩阵对账 + WEB 壳（白名单） | ✅ |
| Verification-Suite | 三关 + release gate + 49 条布线 + redteam/replay 套件 | ✅ |

## 5. 诚实边界（采用前必读）

- **不提供合规证明。** mandatory 条款须人工在运行系统上执行并签署；模板永不替你打勾。
- **不合成正当性。** 岗位、职责、创制任命是世界事件；模板只记录，从不制造（GOV-1）。
- **实例侧职责清单。** 在线影子流量的拦流记录（探针）、LLM 服务绑定（`aos extract --extractor` 适配器契约）、持久化多进程存储（`kernel/filestore.py` 参考实现已给协议）——内核只提供协议与契约，零部署环境依赖、零 LLM 依赖纪律不变。
- **结构指纹弱校验是刻意的。** 条款计数与锚点检查；强保证在密码学哈希层。

## 6. 路线图：已全部清偿

内核侧路线图项已全部交付（v1.0）。唯一保留的实例侧职责（如实披露，非路线图项）：

- **探针组件**（在线影子流量的拦流记录）：部署侧职责——内核提供对账协议（`aos shadow-online` 消费探针 NDJSON，契约见工具头注释），探针本身由实例按部署环境实现；
- **LLM 服务绑定**：实例侧适配器（`aos extract --extractor` 契约）；
- **持久化多进程存储**：实例侧（`kernel/filestore.py` 参考实现已给协议）。

> 语义提取契约层已交付（v1.0，`aos extract`）：内核**不绑定任何 LLM 服务**——提供提取契约 + 确定性参考提取器（零依赖可跑）+ 可插拔适配器（LLM 调用是实例侧职责，契约：stdout YAML `objects[]`）。无论提取器是规则还是 LLM，产物都是草案、都过同一三段闸、晋升都必须 GOV-1 提案——闸门与来源无关；参考提取器只产结构层候选（行为层不编造），置信度如实标注。
> 在线影子对账协议已交付（v1.0，`aos shadow-online`）：对账协议在内核（状态等价 / 输出等价 / 坏行 fail-closed 零静默），探针在部署侧——与离线 `aos shadow` 共同构成绞杀者模式的双跑闭环。
> wheel 可安装性已验证（v0.3.0）：`pip wheel .` 构建 `aos_keel-*.whl`（含 src/ + tools/ 与 `aos` console script）；**wheel 不含 docs/spec/config，不是可安装交付物**——脱离源码树运行输出明确 `REFUSED`（机器判据 INTEGRITY-20）。唯一受支持的运行形态是源码树 + `pip install -e .`。

> frontend.admin_console 生成器已交付（v1.0）：`GUARD`/`FORMS`/`PAGES` 三张声明驱动表 + fail-closed 路由守卫（`can_access`/`nav_for`），与 `command_api.ROUTES` 同源（治理授权链）；UI 组件由实例前端框架消费这些 schema。
