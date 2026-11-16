# AosKeel 理论与实操指南（Guide）

> **语言 / Language**：本指南以**中文**撰写，与冻结正典 `docs/aos-spec.md` v2.0.0 同语言，保证条款级术语零损失；术语同时标注英文。项目 README 默认英文（见 [../README.md](../README.md) / [英文全文](../README.md) / [中文全文](../README.zh-CN.md)）。
>
> **效力 / Status**：本目录全部文档为**信息性（informative）**材料——只解释与教学，**不产生任何规范条款**。一切 MUST / MUST NOT 以 [AOS 规范 v2.0.0](../aos-spec.md) 为准；条款冲突时以 INV 裁决，不得援引本指南推翻规范。

## 一句话定位

AosKeel 是**双重定位**的工具：① 向使用者普及"基于本体论的 AI 系统"这套概念体系；② 提供把这套体系落成可校验系统的**脚手架**——八类声明（schema）+ 注册管线 + 提交内核 + 发布闸门。

它把规范从"人读文档"升级为**机器可执行、可校验的语义契约**。与一般知识图谱项目的根本差别：AOS 的四元组含 **ActionType**——本体不只描述"世界是什么"，还约束"谁、在什么条件下、可以怎样改变世界"。

## 学习路径（按读者分流）

| 你是谁 | 先读 | 再读 | 目标 |
|---|---|---|---|
| 只想搞懂"AI 本体论是什么" | [01 基础概念](01-foundations.md) | [02 架构模型 §1–3](02-architecture.md) | 能说清 TBox/ABox、蓝图/建筑、四元组/四构造 |
| 要评估 AOS 是否适合自己场景 | [01](01-foundations.md) → [02](02-architecture.md) | [02 §10 适用边界](02-architecture.md) | 能按错误代价/建模成本判断，知道不适用条件 |
| 要基于模板做二次开发 | [02 架构模型](02-architecture.md) | [03 实现方法](03-implementation.md) → [05 速查](05-reference.md) | 知道每个条款落在哪个模块、失败在哪一层 |
| 要立刻跑通一个实例 | [04 实操教程](04-tutorial.md) | [05 速查](05-reference.md) | 从 `pip install` 到 `aos release` 全程可复现 |
| 要写治理提案 / 改正典 | [02 §4、§9](02-architecture.md) | [03 §9](03-implementation.md) + [05](05-reference.md) | 走 GOV-3 版本通道，不就地改冻结文本 |
| 想要更严格的理论基础（形式语义） | [06 形式语义](06-formal-semantics.md) | [01 基础概念](01-foundations.md) → [02 §2](02-architecture.md) | 能说清 OWA/CWA 差异、DL 推理与 AOS 机制的对应与边界 |
| 要照着代码理解内核失败形态 | [07 内核实操](07-kernel-walkthrough.md) | [03 实现方法](03-implementation.md) | 能独立复现四类拒绝、完整重求值、投影重建与决策审计 |
| 要基于脚手架构建企业级应用 | [08 企业应用构建指南](08-enterprise-app-guide.md) | [04 实操教程](04-tutorial.md) → [02 架构模型](02-architecture.md) | 能从 init 走到可签发系统，并知道实例侧必须自建什么 |
| 要看懂实例结构并按规范轨迹推进 | [09 结构与开发轨迹](09-structure-and-trajectory.md) | [05 速查](05-reference.md) → [07 内核实操](07-kernel-walkthrough.md) | 能说清每个目录为什么在这、扩展一个领域每一步走哪条条款、卡住时先查哪张表 |

## 文档清单

| 序号 | 文档 | 覆盖 | 关键判据 |
|---|---|---|---|
| 01 | [基础概念](01-foundations.md) | 本体论概念、TBox/ABox、蓝图-建筑、Palantir 风格工程对照、LLM 的结构缺陷、AOS 四元组 | 能画出"通用概念 → AOS 条款 → 代码构件"映射 |
| 02 | [体系逻辑与架构模型](02-architecture.md) | AX→KS→P→INV→BOOT→GOV→VER 推导链、三层数据+治理层、八类声明、双流、事故反证模式、适用边界 | 能指出任一构件由哪条公理派生 |
| 03 | [实现方法](03-implementation.md) | 注册五步、SC 编译、提交管线、受限解释器、事件日志/upcasting、三关核对、字节精确 | 能定位失败发生在哪一步、哪个文件 |
| 04 | [实操教程](04-tutorial.md) | 安装 → 建模 → 草案 → 晋升 → 生成 → 测试 → 发布 → 启动序列；失败形态与排错 | 每条命令能说出预期输出和拒绝条件 |
| 05 | [速查手册](05-reference.md) | CLI ×12、文件地图、术语 T01–T26、VER-1..33 布线、异常/错误码、FAQ | 不查正文即可完成日常操作 |
| 06 | [形式语义与本体工程](06-formal-semantics.md) | 描述逻辑与解释、OWA/CWA、三类推理服务的 AOS 对应物、本体工程七步法、能力问题、OWL↔AOS 翻译边界 | 能区分"描述性本体"与"治理性本体"，知道哪些推理 AOS 有意不提供 |
| 07 | [内核实操](07-kernel-walkthrough.md) | 可运行 Python：装配、事件八字段、四类拒绝、冲突完整重求值、投影重建、决策三引用、两套审计账本 | 文档内全部代码块实测可跑，输出可逐条对照 |
| 08 | [企业应用构建指南](08-enterprise-app-guide.md) | init → 建模 → AI 起草与晋升 → 生成 → 外部接入 → Agent 装配 → 签发 → 实例侧自建清单；角色分工与推进节奏 | 能规划并启动一个真实企业系统的落地路径 |
| 09 | [结构与开发轨迹](09-structure-and-trajectory.md) | 项目结构地图（每个目录为什么在这）、条款编号速查、标准开发轨迹（draft→promote→generate→guards→AI 最小闭环→release）、权限模型、卡点排查表 | 能看懂结构、按规范轨迹把自有领域推进到可签发 |

## 与本仓库其他文档的关系

```
docs/aos-spec.md         正典规范 v2.0.0（冻结；含 AX/KS/P/INV/BOOT/GOV/VER/术语/附录 A-G）
docs/SPEC-FINGERPRINT.md 条款指纹清单（GOV-2.4；结构层核对）
docs/ARTIFACT-REGISTRY.md 工件登记（append-only；GOV-2.3）
docs/POSITIONING.md      项目在规范驱动开发 / AI 软件工厂中的位置与条款级对照
docs/RUNBOOK.md          BOOT-2/3 工作流脚手架与〔强〕项索引
docs/guide/              本指南（信息性；随 aos init 复制到实例）
```

三关核对（`aos verify`）覆盖：结构指纹 → 密码学哈希 → 注册层 `declared == registered`。本指南不在哈希覆盖域内（`hash_spec.CANONICAL_FILES` 仅 `aos-spec.md` + `SPEC-FINGERPRINT.md`），因此**改指南不会影响签发摘要**；但改规范必须走 GOV-3。

## 三条诚实边界（先读，避免误判）

1. **AOS 不是知识图谱系统**：它不提供 RDF 三元组存储与 SPARQL 查询；事实以 append-only 事件流承载，读经只读投影。TBox/ABox 是**教学类比**，不是项目术语。
2. **模板不制造治理世界事件**：创制任命、steward 资格、红队与审批是现实世界的事件，模板只记录其引用，不合成（GOV-1）。`bootstrap --stage 2/3` 返回拒绝即是这条边界的可执行形态。
3. **事件存储本体是纯内存**：`EventStore` 进程退出即失；`kernel/filestore.py` 提供 FileStore 持久化**参考实现**（JSONL 追加 + 启动重放，单写进程模型），生产实例仍须自行证明 append-only 与审计持久性。wheel 也不是可安装交付物——唯一受支持形态是源码树 + `pip install -e .`。

## 最短入口

```powershell
pip install -e .                     # 安装 pyyaml + pytest（均为运行时依赖）
aos verify                           # 三关：结构 → 哈希 → 注册
aos test                             # 按 config/verification.yaml 执行布线套件
```
