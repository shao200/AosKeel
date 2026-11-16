# 05 · 速查手册：命令、术语、布线、异常

> 信息性文档。真实口径以 [aos-spec.md](../aos-spec.md)、[verification.yaml](../../config/verification.yaml) 与源码为准。

## 1. CLI 命令 ×12

| 命令 | 作用 | 失败行为 |
|---|---|---|
| `aos init <dir>` | 实例化 + `TEMPLATE-LOCK` 版本绑定 | 目标已存在 → 拒绝 |
| `aos verify` | 三关串联：结构 → 哈希 → 注册 | 任一失败 → exit 1 |
| `aos register <version>` | GOV-2.3 工件登记 | 同哈希幂等；漂移 → 拒绝 |
| `aos bootstrap --stage N` | BOOT-0..3；`--dry-run` 只跑检查表 | 阶段乱序 → 拒绝；2/3 属实例侧 |
| `aos test [--suite S]` | 按 `verification.yaml` 分组执行 | 套件失败 / 布线路径缺失 / pytest 缺失 → exit 1 |
| `aos spec fingerprint` | 独立结构层核对（GOV-2.5 二分） | 报缺 → exit 1 |
| `aos spec version <v> --proposal-ref SPEC-…` | GOV-3 版本通道（append-only） | 缺提案引用 → 拒绝 |
| `aos generate [--force]` | 声明 → `actions.py` / `reducers.py`（provenance 头） | 手改漂移 → 拒绝静默覆盖 |
| `aos release` | 发布闸门（fail-closed） | 任一关失败 → 不出制品 |
| `aos draft <file> [--name N]` | 需求 DSL → 草案（编译把关） | 未全绿 → 不落盘 |
| `aos draft promote <f> --proposal-ref SPEC-…` | 草案晋升正典 + 能力清单同步 | 目标已存在 / 无提案 → 拒绝 |
| `aos manual [--out F]` | 领域说明书：spec/ 八类声明 → 可读文档（派生视图，非真源） | 缺省打印 stdout；`--out` 落盘 |

> **实例内命令**：`aos` 控制台脚本的 `ROOT` 锁在模板源码树。实例里一律用 `python src/cli/main.py <command>`。详见 [教程 §1](04-tutorial.md)。

---

## 2. 文件地图（按职责）

| 路径 | 职责 |
|---|---|
| `docs/aos-spec.md` | 正典规范 v2.0.0（冻结；AX/KS/P/INV/BOOT/GOV/VER/T/附录 A–G） |
| `docs/SPEC-FINGERPRINT.md` | 条款指纹清单（GOV-2.4，第二正典） |
| `docs/ARTIFACT-REGISTRY.md` | 工件登记（append-only；实例不复制，自行登记） |
| `docs/POSITIONING.md` / `RUNBOOK.md` | 定位与条款级对照 / BOOT-2/3 脚手架 |
| `docs/guide/` | 本指南（信息性；随 init 复制） |
| `config/capabilities.yaml` | 能力清单三段式（固定段/生成段/provenance） |
| `config/verification.yaml` | VER-1..33 布线（承重件；单一读取点 `tools/wiring.py`） |
| `spec/` | 八类声明 + `drafts/`（工作区，不入实例） |
| `src/cli/main.py` | 12 命令分发；`main()` 兼容 console script 无参调用 |
| `src/kernel/registration.py` | 注册五步，生成段唯一写者（P-5） |
| `src/kernel/sc_compiler.py` | SC 两段式编译（Check AST / BooleanFunctionRef） |
| `src/kernel/pipeline.py` | 提交管线 + 冲突完整重求值 |
| `src/kernel/store.py` | 本体事件日志（append-only） |
| `src/kernel/session.py` | 会话事件流（物理分离） |
| `src/kernel/projection.py` | 只读投影与重放 |
| `src/kernel/{detector,upcasting,merge,saga,dryrun,governance,genesis,errors}.py` | 探测器 / 读时升级 / 归并史 / 编排 / 演练 / 治理 / 创世窗口 / 类型化异常 |
| `src/interpreter/` | 受限解释器（布尔档 / 映射档 / 审计） |
| `src/agents/runtime.py` | Agent 能力面（清单严格子集） |
| `src/generated/` | 生成物（actions.py / reducers.py / __init__.py） |
| `tools/` | `hash_spec` / `fingerprint` / `wiring` / `codegen` / `release_gate` / `ontology_draft` |
| `tests/` | conformance / negative / golden / genesis / invariants / replay / redteam |
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

另有 `integrity_paths` 段登记 `tests/conformance/test_integrity.py`（16+ 例修补守卫）。**它不构成新 VER 条款**——冻结条款集仍是 VER-1..33，指纹清单与登记哈希均未改动。

`aos test` 当前统计：选中 28 / 可执行 28 / 缺失 0 / 〔强〕项未布线 6。

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
模板层只演示 append-only 语义与门控逻辑；持久化是实例侧职责。不要把它当生产存储。

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
不可。wheel 不含 `docs/spec/config`，启动自检明确拒绝。唯一受支持形态：源码树 + `pip install -e .`。

**Q9：能关掉三关核对提速吗？**
不能。三关 + 闸门是 fail-closed 设计；关掉等于把规范降级为文档。

**Q10：模型变更（新增 Action / 改公理）怎么走？**
新增 Action：需求 DSL → `aos draft` → `aos draft promote --proposal-ref`（单写者同步能力清单）。改公理/条款：GOV-3 提案 → 新版本登记 → 重跑全链路回归 → 重新签发。不要就地改冻结文本。
