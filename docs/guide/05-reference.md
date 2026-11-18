# 05 · 速查手册：命令、术语、布线、异常

> 信息性文档。真实口径以 [aos-spec.md](../aos-spec.md)、[verification.yaml](../../config/verification.yaml) 与源码为准。

## 1. CLI 26 命令面（21 顶层 + 5 子命令）与护栏 ×3

| 命令 | 作用 | 失败行为 |
|---|---|---|
| `aos init <dir> [--depth D] [--cap ID] [--no-cap ID]` | 实例化 + 能力画像（依赖自动展开；三档 depth 预设） | 目标已存在 → 拒绝（重铺须 `--force`）；非法 depth/能力 → 实例化前 fail-fast |
| `aos profile` | 解析能力画像：依赖展开 + 拓扑生成序 + 锚点核对 | 锚点缺失 → `PROFILE-FAIL` 带待声明清单；环/未知能力 → 拒绝 |
| `aos verify` | 三关串联：结构 → 哈希 → 注册 | 任一失败 → exit 1 |
| `aos register <version>` | GOV-2.3 工件登记 | 同哈希幂等；漂移 → 拒绝 |
| `aos bootstrap --stage N` | BOOT-0..3；`--dry-run` 只跑检查表 | 阶段乱序 → 拒绝；2/3 属实例侧 |
| `aos test [--suite S]` | 按 `verification.yaml` 分组执行 | 套件失败 / 布线路径缺失 / pytest 缺失 → exit 1 |
| `aos spec fingerprint` | 独立结构层核对（GOV-2.5 二分） | 报缺 → exit 1 |
| `aos spec version <v> --proposal-ref SPEC-…` | GOV-3 版本通道（append-only） | 缺提案引用 → 拒绝 |
| `aos generate [--force]` | 声明 → 代码骨架（Profile 门控：治理→CQRS→OAuth2.1→前端守卫；字节级零漂移） | 锚点缺失 → `CODEGEN-REFUSED`；手改漂移 → 拒绝静默覆盖 |
| `aos release` | 发布闸门（fail-closed） | 任一关失败 → 不出制品 |
| `aos draft <file> [--name N]` | 需求 DSL → 草案（编译把关） | 未全绿 → 不落盘 |
| `aos draft promote <f> --proposal-ref SPEC-…` | 草案晋升正典 + 能力清单同步 | 目标已存在 / 无提案 → 拒绝 |
| `aos import-db --ddl F / --dsn URI` | 老库元结构 → 本体草案（方言翻译大声报告） | 翻译失败 fail-closed 不丢表；无主键表拒绝（AX-4） |
| `aos import-data --dsn URI --map F` | 老库行 → 创世事件草案（逐行过完整求值链；迁移器不发明事件） | 脏行 → 完整问题清单 fail-closed；`--skip-failed` 大声跳过 |
| `aos extract <file> [--extractor script]` | 语义提取：源码/文档 → 草案（同一三段闸，闸门与来源无关） | 适配器崩溃/坏 schema/无候选 → 大声拒绝零落盘 |
| `aos review` | 只读裁决清单（锚点 roadmap / 草案候选 / 治理对账前置） | 只读咨询；晋升建议强制 `--proposal-ref` |
| `aos shadow --dsn URI --map F` | 影子对账（离线双跑）：行 ↔ 事件语义等价 | 分歧 → `DIVERGED` 带差异明细（进 review 裁决） |
| `aos shadow-online <probes.ndjson>` | 在线双跑对账协议（探针 NDJSON 契约；探针属部署侧） | 坏行 → fail-closed 零静默；空记录 → `PROBE-EMPTY` |
| `aos manual [--out F]` | 领域说明书：spec/ 九类声明 → 可读文档（人读 + LLM 上下文注入） | 派生视图；缺省打印 stdout；`--out` 落盘 |
| `aos impact <target>` | 变更影响分析：声明名 / spec 路径 / `ObjectType.prop` → 反向引用图（含治理授权边；事前咨询，不进闸门） | 目标不可解析 → `IMPACT-UNKNOWN` exit 1 |
| `aos audit export <events.jsonl> [--out F]` | 统一审计台账：追加证据 + 评估审计 + 决策引用 → 链式 `audit_id` JSONL（只读派生件） | 缺路径 / 文件不存在 → 拒绝 |
| `aos metrics` | 闸门度量：`dist/gate-history.jsonl` → 次数 / 通过率 / 各关失败 / 漂移计数 / 连续通过 | 空台账 → `METRICS-EMPTY`（exit 0） |

> **三关四道**（ADR-001/002/003 与 CLI 输出口径统一）：**三关**是门径（结构 / 密码学 / 注册），
> **四道**是密码学门内的比对域——正典哈希与声明摘要（GOV-2.3-DECL）双比对。实例未登记
> 声明基线时第四道显式 SKIP（`VERIFY-OK-WITH-SKIP`），发布闸门对 SKIP 实例拒出制品。

> **护栏 ×3（三条纪律跨命令生效）**：① 晋升通道一律 `--proposal-ref` 强制（GOV-1：CLI 只记录治理结果，不合成正当性）；② 编译不过不落盘（草案三段闸：解析 → 把关 → 晋升）；③ 草案通道产物只进 `drafts/`（工作区），凭据永不落盘（连接串/密钥只进命令行或临时环境）。

> **实例内命令**：`aos` 控制台脚本的 `ROOT` 锁在模板源码树。实例里一律用 `python src/cli/main.py <command>`。详见 [教程 §1](04-tutorial.md)。

---

## 2. 文件地图（按职责）

| 路径 | 职责 |
|---|---|
| `docs/aos-spec.md` | 正典规范 v2.2.0（冻结；AX/KS/P/INV/BOOT/GOV/VER/T/附录 A–G、R、S） |
| `docs/SPEC-FINGERPRINT.md` | 条款指纹清单（GOV-2.4，第二正典） |
| `docs/ARTIFACT-REGISTRY.md` | 工件登记（append-only；实例不复制，自行登记） |
| `docs/POSITIONING.md` / `RUNBOOK.md` | 定位与条款级对照 / BOOT-2/3 脚手架 |
| `docs/guide/` | 本指南（信息性；随 init 复制） |
| `config/capabilities.yaml` | 能力清单三段式（固定段/生成段/provenance） |
| `config/verification.yaml` | VER-1..33 布线（承重件；单一读取点 `tools/wiring.py`） |
| `spec/` | 九类声明 + `profile.yaml`（能力画像）+ `drafts/`（工作区，不入实例） |
| `src/cli/main.py` | 22 命令分发；`main()` 兼容 console script 无参调用；启动自检拒绝误装 wheel |
| `src/kernel/registration.py` | 注册五步，生成段唯一写者（P-5） |
| `src/kernel/profile.py` | 能力画像解析（依赖图展开、Kahn 拓扑生成序、锚点核对、fail-closed） |
| `src/kernel/sc_compiler.py` | SC 两段式编译（Check AST / BooleanFunctionRef） |
| `src/kernel/pipeline.py` | 提交管线 + 冲突完整重求值 |
| `src/kernel/store.py` | 本体事件日志（append-only） |
| `src/kernel/filestore.py` | FileStore：持久化参考实现（JSONL 追加 + 重放；单写进程模型） |
| `src/kernel/session.py` | 会话事件流（物理分离） |
| `src/kernel/projection.py` | 只读投影与重放 |
| `src/kernel/{detector,upcasting,merge,saga,dryrun,governance,genesis,errors}.py` | 探测器 / 读时升级 / 归并史 / 编排 / 演练 / 治理 / 创世窗口 / 类型化异常 |
| `src/interpreter/` | 受限解释器（布尔档 / 映射档 / 审计） |
| `src/agents/runtime.py` | Agent 能力面（清单严格子集） |
| `src/generated/` | 生成物（字节级零漂移 gate 强制）：actions.py / reducers.py + command_api.py / query_api.py（CQRS 双端）+ auth_oauth2.py（OAuth 2.1 IdP + 治理面 claims + DPoP）+ admin_console.py（前端守卫/表单/页面三张表） |
| `tools/` | `hash_spec` / `fingerprint` / `wiring` / `codegen` / `db_import` / `data_import` / `semantic_extract` / `shadow` / `shadow_online` / `review` / `console` / `release_gate` / `ontology_draft` / `domain_manual` / `impact` / `audit_export` / `gate_history` |
| `tests/` | conformance（含 42 条 INTEGRITY 回归守卫）/ negative / golden / genesis / invariants / replay / redteam |
| `bootstrap/checklists/` | 〔强〕项检查表（VER-20/24/26/27/28/29） |

---

## 3. 术语 T01–T26（规范 §1.1 口径）

| 编号 | 术语 | 定义（摘要） |
|---|---|---|
| T01 | 四元组 | ObjectType / Property / LinkType / ActionType |
| T02 | 四构造 | ContextType / AggregateType / Mapping / ProcessType |
| T03 | 主体身份 | 平台 authN 签发的调用者标识，本体之外 |
| T04 | 实体身份 | Identity Context 辖区，判断两条记录是否同一实体 |
| T05 | 本体事件日志 | 唯一权威状态来源，append-only，含域流与决策流 |
| T06 | 会话事件流 | 只增观测记录，非本体状态 |
| T07 | 决策流 | 本体日志中承载决策事件的流，不经域不变量门控 |
| T08 | 决策事件 | 双引用本体事件，经 `RecordDecision` 追加 |
| T09 | 结构性链接 | 零属性 + 遍历透明 + 系统写入 |
| T10 | 不变量三元组 | 声明 + 违规语义 + 修复绑定 |
| T11 | 违规对象 | `InvariantViolation` 实例，一等公民，有生命周期 |
| T12 | 状态转移不变量 | 只取决于单次追加后的状态，可门控追加 |
| T13 | 时间限定不变量 | 取决于时间流逝，由探测器在投影上求值 |
| T14 | 受限解释器 | 平台内置求值引擎，含布尔/映射两档 |
| T15 | 布尔型 profile | 结果仅 true / false |
| T16 | 映射型 profile | 数据整形，禁止判断分派 |
| T17 | 投影 | 本体事件的只读物化视图，决策输入源 |
| T18 | 基座 | 不可能被系统内能力修改的 Tier-0 不变量，仅三项 |
| T19 | 能力清单 | 内核全部状态变更与通道写入能力，版本化 |
| T20 | 创世窗口 | `GenesisWrite` 有效时段，自熄灭 + TTL |
| T21 | 创世冻结 | TTL 到期未闭环；可逆（须再授权并记审计） |
| T22 | 创世熄灭 | 治理周期完成；不可逆，无重启用路径 |
| T23 | 创制任命 | 系统外事件，审计第一条（禁用变体："开国任命"） |
| T24 | ActionType | 声明式状态变更契约：参数、SC、权限、副作用、审计 |
| T25 | 探测器 | 对时间限定不变量周期求值，违规经专用 Action 写入 |
| T26 | 求值预算 | 不变量求值成本上限，受 R8 约束 |

---

## 4. VER-1..33 验证矩阵布线

来源：`config/verification.yaml`（冻结条款集，不新增）。〔自〕= auto 进 CI；〔强〕= mandatory 人工留档。

| ID | 条款 | 类型 | 布线 |
|---|---|---|---|
| VER-1 | KS-1.2 | 〔自〕 | `test_event_schema.py` |
| VER-2 | KS-7.2 | 〔自〕 | `test_pipeline_order.py` |
| VER-3 | KS-1.4 | 〔自〕 | `test_conflict_reeval.py` |
| VER-4 | KS-2.1 | 〔自〕 | `test_stream_separation.py` |
| VER-5 | KS-2.2/2.3 | 〔自〕 | `test_session_channel.py` |
| VER-6 | KS-2.4 | 〔自〕 | `test_closure_no_session.py` |
| VER-7 | KS-2.5 | 〔自〕 | `test_decision_refs.py` |
| VER-8 | KS-3.2/R10 | 〔自〕 | `test_interpreter_forbidden.py` |
| VER-9 | KS-3.2/R11 | 〔自〕 | `test_mapping_profile.py` |
| VER-10 | KS-3.4 | 〔自〕 | `test_replay_purity.py` |
| VER-11 | KS-3.3 | 〔自〕 | `test_interpreter_audit.py` |
| VER-12 | KS-4.1/4.2 | 〔自〕 | `test_source_declaration.py` |
| VER-13 | KS-5.2 | 〔自〕 | `test_upcasting_contract.py` |
| VER-14 | KS-5.3 | 〔自〕 | `test_upcasting_golden.py` |
| VER-15 | KS-5.4 | 〔自〕 | `test_no_event_deletion.py` |
| VER-16 | KS-6.1 | 〔自〕 | `test_valid_time_domain.py` |
| VER-17 | KS-6.3 | 〔自〕 | `test_backfill_provenance.py` |
| VER-18 | KS-7.1 | 〔自〕 | `test_sc_compile.py` |
| VER-19 | KS-8.2 | 〔自〕 | `test_genesis_predicate.py` |
| VER-20 | KS-8.4/8.5 | 〔强〕 | `bootstrap/checklists/VER-20.yaml` |
| VER-21 | P-4/INV-2 | 〔自〕 | `test_link_pattern.py` |
| VER-22 | P-6/INV-3 | 〔自〕 | `test_repair_binding.py` |
| VER-23 | P-7/INV-10 | 〔自〕 | `test_violation_object.py` |
| VER-24 | P-8 | 〔强〕 | checklist + `test_merge_replay.py` |
| VER-25 | P-12 | 〔自〕 | `test_dryrun_report.py` |
| VER-26 | P-16 | 〔强〕 | checklist + `test_projection_rebuild.py` |
| VER-27 | INV-13 | 〔强〕 | checklist + `verify_capability_list.py` |
| VER-28 | INV-6 | 〔强〕 | checklist + `test_foundation.py` |
| VER-29 | P-15 | 〔强〕 | checklist + `test_breakglass.py` |
| VER-30 | GOV-2/3 | 〔自〕 | `test_artifact_ref.py` |
| VER-31 | P-4/8/11 | 〔自〕 | `test_genesis_scope.py` |
| VER-32 | KS-8.5 | 〔自〕 | `test_genesis_ttl.py` |
| VER-33 | KS-2.6 | 〔自〕 | `test_decision_stream.py` |

另有 `integrity_paths` 段登记 `tests/conformance/test_integrity.py` 等 **42 条 INTEGRITY 回归守卫**（INTEGRITY-1..42：工作区清零、能力清单完备性、生成物零漂移、wheel 可安装性、语义提取契约、在线对账协议、声明摘要第四道、声明执行点、口径单一权威源、CQ 可执行契约、元 schema 声明化、域无关 CQ 定义、附录 S 语义机器核对、十二个补登测试文件与全量在册守卫等）。**它不构成新 VER 条款**——冻结条款集仍是 VER-1..33，指纹清单与登记哈希均未改动。

`aos test` 当前统计：选中 74 / 可执行 74 / 缺失 0 / 〔强〕项未布线 1（VER-20 属实例侧人工留档）。口径由 `tools/doc_metrics.py` 从源码与布线文件派生，不由人工抄写。

---

## 5. 异常类型索引（`src/kernel/errors.py`）

| 类别 | 异常 | 触发条款 |
|---|---|---|
| 存储拒绝 | `DirectWriteForbidden` / `VersionConflict` / `ValidTimeViolation` / `UnknownAction` / `StreamRuleViolation` | INV-1·VER-28 / KS-1.4 / KS-6.1 / INV-13 / KS-2.1 |
| 管线拒绝 | `UnregisteredAction` / `StructuralRejected` / `ConditionalRejected` / `InvariantViolated` / `BudgetExceeded` | INV-1 / KS-7.1 / KS-7.1 / KS-1.3 / R8 |
| 主体与引用 | `PrincipalRequired` / `DecisionRefIncomplete` | KS-2.3·INV-8 / KS-2.5·VER-7 |
| 解释器与路径 | `InterpreterRejected` / `ForbiddenPath` / `RegistrationFailed` | R1–R11 / INV-13 / KS-7.2 |
| 创世状态 | `GenesisFrozen` / `GenesisExtinguished` / `ReauthorizeAfterExtinguish` | KS-8.5 / KS-8.2 / 基座周界完整 |
| 投影与演化 | `ProjectionViolation` / `ProjectionNotMaterialized` / `UpcastingFailed` | P-16 / P-16 / KS-5.2 |
| 能力面与编排 | `PermissionDenied` / `SagaInvalid` | P-10 / P-9 |

异常类型即条款的运行时形态（模块 docstring）；每个异常可回溯条款号，不允许"无兑现的宣称"（GOV-6）。

---

## 6. FAQ（诚实边界）

**Q1：这是不是一个运行时业务系统？**
不是。AosKeel 是模板生成系统——交付源码树 + 规范 + 脚手架，实例侧仍需接数据库、实现治理工作流与 Agent 业务逻辑。

**Q2：为什么 `EventStore` 是内存实现？**
模板层只演示 append-only 语义与门控逻辑；持久化是实例侧职责。`kernel/filestore.py` 的 `FileStore` 是持久化**参考实现**（JSONL 追加 + 重放，单写进程模型），不是生产存储。

**Q3：为什么 `verify` 通过仍不能宣称合规？**
结构层只是弱在场证明；强保证来自全文哈希。〔强〕项必须在运行系统上人工执行并留 evidence/judge/signer，模板不伪装通过。

**Q4：TBox/ABox 是项目术语吗？**
不是。它是教学类比（见 [01 基础](01-foundations.md)）。项目术语以 T01–T26 为准；事实以事件流 + 投影承载，不是 RDF 三元组。

**Q5：能否改规范文本让测试通过？**
不能。`docs/aos-spec.md` 与 `SPEC-FINGERPRINT.md` 入哈希覆盖域；变更走 GOV-3 版本通道（`aos spec version --proposal-ref`），冻结文本不就地改。

**Q6：为什么实例里 `aos verify` 不管用？**
`aos` 控制台脚本的 ROOT 锁在模板根。实例内用 `python src/cli/main.py verify`。

**Q7：为什么 promote 后 `generate` 要 `--force`？**
因为生成物已存在且与新声明不一致；`--force` 是显式确认覆盖，不是绕过校验。漂移检测仍是字节级。

**Q8：wheel 可安装吗？**
可构建、不作交付。`pip wheel .` 能产出 `.whl`（含 src/tools 与 `aos` console script），但它不含 `docs/spec/config`——脱离源码树运行输出明确 `REFUSED`（机器守卫，INTEGRITY-20）。唯一受支持形态：源码树 + `pip install -e .`（正典声明与代码同版本管理）。

**Q9：能关掉三关核对提速吗？**
不能。三关 + 闸门是 fail-closed 设计；关掉等于把规范降级为文档。

**Q10：模型变更（新增 Action / 改公理）怎么走？**
新增 Action：需求 DSL → `aos draft` → `aos draft promote --proposal-ref`（单写者同步能力清单）。改公理/条款：GOV-3 提案 → 新版本登记 → 重跑全链路回归 → 重新签发。不要就地改冻结文本。

**Q11：旧系统迁徙走哪条路？**
绞杀者管线八步：`init` → `import-db`（老库元结构 → 本体草案）→ `extract`（源码/文档语义提取）→ `review`（人工裁决清单）→ `draft promote`（治理晋升）→ `generate`（代码骨架）→ `import-data` + `shadow` / `shadow-online`（数据行 → 创世事件草案，离线/在线双跑对账）。素材永远先成草案；数据迁徙是事件重放不是表拷贝——每行数据过 `Kernel.submit()` 完整求值链，迁移器不发明事件。
