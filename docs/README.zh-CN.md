# AosKeel —— 基于本体论的 Agent 系统开发模板（AOS Template v0.3）

> **语言 / Language**: **简体中文** · [English (default)](README.md)
>
> 中英两版内容一致；默认展示为英文版。
> 正典规范（[aos-spec.md](aos-spec.md)）为中文冻结文本，未作翻译；`docs/` 下其余文档（POSITIONING / RUNBOOK / SPEC-FINGERPRINT）同样保持中文。

**定位**：规范驱动开发是方法论，AI 软件工厂是组织与流程载体，本体论架构是让前两者在语义层面真正"可执行"的基础设施——本项目是这层基础设施的一个完整、可校验的具体实现（条款级对照与全链路缺口地图见 [POSITIONING.md](POSITIONING.md)）。对标 `npm create vue` / VS 项目模板：从 0 到 1 实例化一个基于本体论的、治理内建的企业级 Agent 系统。

正典规范：《AOS：基于本体论的 Agent 系统开发规范》v2.0.0（[docs/aos-spec.md](aos-spec.md)，登记条目见 [docs/ARTIFACT-REGISTRY.md](ARTIFACT-REGISTRY.md)）。

## 理论与教程导览（从这里开始）

**AI 本体论是对某领域概念、关系、属性与规则所做的显式、形式化定义。** 数据库只存 `user_id`；本体则要定义"用户"是什么、"购买"意味着什么，以及"支付成功"是"发货"的前置规则。AosKeel 把这套骨架变成机器可校验的契约，让 Agent 的断言与行动有据可依、有规可循。

**TBox / ABox 是教学类比。** 本体是图纸——类、属性、关系、公理；知识图谱是按图纸盖好的大楼——个体与事实。在 AosKeel 中，图纸是 `spec/` 的八类声明，大楼是 append-only 事件日志与可重建的只读投影；**不是** RDF 三元组，也不是 SPARQL 查询。

**AOS 的增量。** 经典本体描述"什么为真"；AOS 把 `ActionType` 提升为一等元，于是本体同时约束"谁能改什么、在什么条件下、留下什么审计轨迹"——从描述性本体跃迁为**治理性本体**。另有两层经典本体没有的维度：非权威的观测层（会话事件流），以及作为启动条件的治理（`declared == registered`）。

| 经典概念 | AOS 构件 | 实际落点 |
|---|---|---|
| 类 Class | `ObjectType` | `spec/ontology/objects/*.object.yaml` |
| 属性 Property | `Property`（可标 `decision_relevant`） | 对象声明 |
| 关系 Relation | `LinkType`——结构性、零业务语义 | `spec/ontology/links/*.link.yaml` |
| 公理 / 规则 | 不变量三元组 + 受限布尔函数 | `spec/invariants/`、`src/interpreter/` |
| 个体 / 三元组 | 事件投影状态 / 八字段不可变事件 | `src/kernel/projection.py`、`src/kernel/store.py` |
| *（无对应）* | `ActionType`、能力清单、会话流、创世窗口 | `spec/ontology/actions/`、`config/capabilities.yaml`、`src/kernel/session.py`、`src/kernel/genesis.py` |

完整的**九篇指南**为中文撰写（保证条款级术语零损失），随 `aos init` 复制到每个实例；也可从 [GitHub 首屏入口](../README.md#6-guided-learning) 进入。

| 指南 | 覆盖内容 |
|---|---|
| [索引](guide/README.md) | 按读者分流的路径与三条诚实边界 |
| [01 基础概念](guide/01-foundations.md) | 本体论、TBox/ABox、蓝图-建筑、Palantir 风格对照、四元组 |
| [02 体系逻辑](guide/02-architecture.md) | AX→KS→P→INV→BOOT→GOV→VER 推导链、四条事件流、事故反证模式 |
| [03 实现方法](guide/03-implementation.md) | 注册、SC 编译、提交管线、受限解释器、升级、闸门 |
| [04 实操教程](guide/04-tutorial.md) | install → init → BOOT-0 → draft/promote → generate → 提交 → test/release（实测输出） |
| [05 速查手册](guide/05-reference.md) | CLI ×12、文件地图、T01–T26、VER-1..33 布线、异常、FAQ |
| [06 形式语义](guide/06-formal-semantics.md) | 描述逻辑、开放/封闭世界、本体工程方法、OWL↔AOS 翻译边界 |
| [07 内核实操](guide/07-kernel-walkthrough.md) | 可运行 Python：拒绝路径、完整重求值、投影、决策审计 |
| [08 企业应用构建指南](guide/08-enterprise-app-guide.md) | 完整构建路径：建模 → AI 起草与晋升 → 生成 → 外部接入 → Agent 装配 → 签发 → 实例侧自建清单 |
| [09 结构与开发轨迹](guide/09-structure-and-trajectory.md) | 项目结构地图、条款编号速查、标准开发轨迹（含权限模型与卡点排查表） |

## 这个模板给什么、不给什么（先读这个）

**给**：VER 全部 auto 项的 CI 兑现 · 注册期管线（五步，单写者）· BOOT 序列脚手架 · 〔强〕项检查表（6 份）· 三关核对（结构/密码学/注册）· 双射断言。

**不给**：合规证明。〔强〕项的"已通过"只能来自运行系统上的人工执行（检查表留档：evidence + judge + signer）；基座不可修改的证明 = VER-28 红队演练；解释器纯性 = 解释器实现的正确性；正当性（steward、创制任命）是世界事件——本模板只记录，不制造（GOV-1）。

## 快速开始（0 → 1）

```powershell
pip install -e .                              # 安装 pyyaml + pytest；或直接 python -m src.cli.main
aos init my-org-system                        # 实例化（拒绝覆盖已存在目标）
cd my-org-system
aos bootstrap --stage 0                       # BOOT-0：工件哈希登记 + 三关首跑
aos verify                                    # 三关：结构(指纹) → 密码学(哈希) → 注册(declared==registered)
python -m pytest -q tests                     # 一致性 + forbidden 双射 + 解释器负向集
aos bootstrap --stage 1 --appointment-ref <外部凭据>   # BOOT-1 创制任命（强制真实凭据）
aos test                                      # 按 config/verification.yaml 分组执行
# —— 全链路生命周期（需求 → 制品）——
aos draft requirements.txt --name r1          # 需求 DSL → 草案（编译把关，未全绿不落盘）
aos draft promote spec/drafts/draft-r1.yaml --proposal-ref SPEC-2026-021   # 晋升正典（治理提案强制）
aos generate                                  # 声明 → 代码骨架（手改检测，provenance 头）
aos release                                   # 发布闸门（fail-closed）→ dist/RELEASE-MANIFEST.json
```

之后的 BOOT-2/3（治理工作流、Identity Context 验收）与业务建模变更（走 GOV-3 版本通道，见 [docs/RUNBOOK.md](RUNBOOK.md)）属实例侧治理工作——模板提供声明位、编译器、闸门与验收清单，不模拟治理（诚实边界；Makefile 不合成创制任命凭据）。CI 门禁见 `.github/workflows/ci.yml`（pytest → 三关 → 发布闸门）。

`aos` 控制台脚本与 `python -m src.cli.main` 等价：两者都经 `main()` 分发，argv 缺省取 `sys.argv[1:]`。`pytest` 是声明的运行时依赖（`aos test` / `aos release` 要执行布线套件）；缺失时明确报 `PYTEST-MISSING` 拒绝，不伪装成"套件失败"。

## 模板树（v0.1 → v0.3）

```
README.md                      仓库根首屏入口（英文默认；指向两份完整文档）
docs/README.md                 英文版（默认；首屏诚实边界 + 快速开始 + 模板树）
docs/README.zh-CN.md           本文件（简体中文版，内容与英文版一致）
docs/aos-spec.md               正典规范 v2.0.0（冻结）
docs/SPEC-FINGERPRINT.md       条款指纹清单（正典之二，GOV-2.4）
docs/ARTIFACT-REGISTRY.md      工件登记（append-only，GOV-2.3；实例自行重新登记）
docs/POSITIONING.md            项目定位：规范驱动开发 / AI 软件工厂 / 本体论三者的对照与缺口地图
docs/RUNBOOK.md                BOOT-2/3 工作流脚手架（GOV-3 版本通道 / GOV-2.5 二分 / 〔强〕项索引）
docs/guide/                    理论与实操指南（九篇 + 索引；随 init 复制；见上文"理论与教程导览"）
docs/TEMPLATE-LOCK.md          init 时写入版本绑定
config/capabilities.yaml       能力清单三段式（固定段/生成段/provenance）
config/verification.yaml       VER-1..33 实文布线（承重件）
spec/                          八类声明样例（objects/links/actions/contexts/aggregates/mappings/processes/invariants）
src/cli/main.py                命令表驱动入口（12 命令，见下表；启动自检拒绝误装 wheel）
src/kernel/registration.py     注册期管线（KS-7.2 五步，P-5 单写者；装载 spec/ 八类声明）
src/kernel/sc_compiler.py      SC 两段式编译器（KS-7.1 / VER-18）
src/kernel/pipeline.py         内核提交管线（结构→条件→追加；冲突完整重求值 VER-2/3）
src/kernel/store.py            本体事件日志（append-only；INV-1 写路径闭环）
src/kernel/filestore.py        FileStore：持久化参考实现（JSONL 追加 + 重放；单写进程模型）
src/kernel/session.py          会话事件流（KS-2.2 物理分离存储 / VER-4）
src/kernel/genesis.py          创世窗口状态机（KS-8；熄灭不可逆）
src/kernel/projection.py       投影与决策输入（P-16；可重建 / 会话禁入）
src/kernel/detector.py         探测器（T25；违规对象经 RaiseInvariantViolation，P-7/INV-10）
src/kernel/upcasting.py        读时升级（KS-5.2-5.4；无路径即读失败，golden 锚定）
src/kernel/merge.py            Identity 归并史（P-8；双路径重放比对，VER-24）
src/kernel/saga.py             跨聚合编排（P-9；补偿本身是 Action，幂等）
src/kernel/dryrun.py           演练模拟器（P-12；可重复、零副作用，VER-25）
src/agents/runtime.py          AGENT 能力面（P-10；清单严格子集，无特权通道）
src/kernel/governance.py       治理层（GOV-4 生效重跑；失败 = 阻断 + governance 类违规对象）
src/kernel/errors.py           类型化异常（异常类型即条款的运行时形态）
src/interpreter/boolean_profile.py   布尔档受限解释器（R10 AST 白名单，含 dunder 属性拦截——R1 输入封闭 / VER-8）
src/interpreter/mapping_profile.py   映射档受限解释器（R11 无谓词分派 / VER-9）
src/interpreter/audit.py       解释器审计（KS-3.3 版本身份 + 快照哈希）
tools/hash_spec.py             分离式哈希（密码学层唯一执行点，GOV-2.3）
tools/fingerprint.py           结构层指纹核对（GOV-2.5 分歧二分）
tools/verify_capability_list.py  VER-27 支撑（清单完备性）
tools/wiring.py                  verification.yaml 唯一读取点（pyyaml；缺路径阻断）
tools/codegen.py                 声明 → 代码骨架生成器（aos generate；手改检测，provenance 头）
tools/release_gate.py            发布闸门（aos release；fail-closed，VER-27 前置）
tools/ontology_draft.py          需求 DSL → 本体草案（aos draft；编译把关，晋升须治理提案）
docs/samples/requirements-sample.txt  需求 DSL 样例（draft 入口）
src/generated/                   生成物：actions.py（INV-1 封装 submit）+ reducers.py（纯函数，漂移可见）
tests/negative/test_forbidden.py            forbidden × 负向测试（每项恰一用例）
tests/negative/test_forbidden_coverage.py   双射断言（P-10）
tests/conformance/test_declared_registered.py  declared == registered 持续核对（INV-13）
tests/conformance/test_integrity.py        v0.3 加固的完整性守卫（经 integrity_paths 布线，不构成新 VER 条款）
bootstrap/checklists/          _schema + VER-20/24/26/27/28/29（P-14 证据留档）
```

## CLI 命令 ×12 与护栏 ×2

| 命令 | 语义 | 失败行为 |
|---|---|---|
| `init <dir>` | 实例化 + TEMPLATE-LOCK 版本绑定 | 目标已存在 → 拒绝 |
| `verify` | 三关串联 | 任一失败 → exit 1 |
| `register <version>` | GOV-2.3 登记 | 同哈希幂等；漂移 → 拒绝（GOV-3） |
| `bootstrap --stage N` | BOOT-0..3；`--dry-run` 只跑检查表 | 阶段乱序 → 拒绝；2/3 属实例侧 |
| `test [--suite S]` | 按 verification.yaml 分组 | 套件失败 / 布线路径缺失 → exit 1 |
| `spec fingerprint` | 独立结构层核对 | 报缺 → exit 1 |
| `spec version <v>` | GOV-3 版本通道（append-only） | 缺 `--proposal-ref` → 拒绝 |
| `generate [--force]` | 声明 → 代码骨架（字节级零漂移） | 手改漂移 → 拒绝静默覆盖 |
| `release` | 发布闸门（fail-closed） | 任一关失败 → 不出制品 |
| `draft <file>` | 需求 DSL → 草案（编译把关） | 未全绿 → 不落盘 |
| `draft promote <f>` | 草案晋升正典（GOV-1 提案强制） | 目标已存在 → 拒绝；走 GOV-3 |
| `manual [--out F]` | 领域说明书：八类声明 → 可读文档（人读 + LLM 上下文注入） | 派生视图；缺省打印到 stdout |

护栏一：`bootstrap --stage 1` 强制 `--appointment-ref`——拒绝合成创制任命（GOV-1）。
护栏二：实例携带规范副本 + 登记条目 ID，副本哈希 = 登记哈希，改动即 FROZEN-TEXT-MUTATED（INV-12）。

## 运行形态与工程边界（先读，避免误判）

| 边界 | 事实 | 代价 / 实例侧职责 |
|---|---|---|
| 交付形态 | 模板以**源码树**交付：`pip install -e .`（之后用 `aos ...`）或 `python -m src.cli.main`。wheel 不含 `docs/spec/config`，启动自检明确拒绝，**不是可安装制品** | 若要 wheel 可安装，须重构 ROOT 解析与数据文件打包（P2，本版未做） |
| 事件存储 | `EventStore` 为**纯内存** dict，进程退出即失；`kernel/filestore.py` 提供 **FileStore 持久化参考实现**（JSONL 追加 + 启动重放，单写进程模型，拒绝不落盘） | 生产多进程部署须以数据库实现同一协议（streams 只读 · commit 唯一写面 · audit 只增），并自行证明 append-only 与审计持久性 |
| 结构层指纹 | 核对"条数 + 首锚 + 末锚"，**不校验中间条款内容**；强保证来自密码学层全文哈希（GOV-2.3） | 中间条款被改而首尾不变 → 结构层 PASS，靠哈希层拦截；这是附录 F 清单定义的取舍 |
| BOOT-2/3 | 模板只给脚手架与检查表，`bootstrap --stage 2/3` 返回拒绝 | 治理工作流与 Identity Context 验收属实例侧世界事件（GOV-1） |
| 〔强〕项 | VER-20/24/26/27/28/29 只有 checklist/support，不进 auto 套件 | 人工执行 + evidence / judge / signer 留档，模板不伪装通过 |
| 字节精确 | 所有写入点为 UTF-8 + LF 字节写入；`.gitattributes * -text` 禁止换行转换 | 生成物/登记/清单被外部工具改成 CRLF 时，`generate`/`release` 以字节级漂移拒绝 |

布线件 `config/verification.yaml` 由 `tools/wiring.py` 统一用 pyyaml 解析：声明了
`path` 但文件不存在 → `aos test` 与 `aos release` **阻断**（不再静默降级）。
`integrity_paths` 段只登记回归守卫测试的执行路径，**不构成新 VER 条款**
（v2.0.0 冻结条款集仍为 VER-1..33，指纹清单与登记哈希均未改动）。
