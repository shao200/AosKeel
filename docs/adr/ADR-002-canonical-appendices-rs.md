# ADR-002：正典信息性附录 R / S 与 v2.1.0 版本更替

- 状态：Accepted（用户于 2026-11-18 明确授权"按 ADR → GOV-3 提案 → gates → regression 执行"）
- 日期：2026-11-18
- 决策者：项目所有者（模型变更授权保留在仓库之外）
- 关联提案：`SPEC-2026-001`（GOV-3）
- 关联评审：第三轮同行评议通过条件 ② 与 ③

## 上下文

第三轮同行评议把"ontology-based"理论宣称的通过条件收敛为三件事。① Invariant 执行点已在
`16d3114` 以"实例侧义务 + §9 披露 + 机器守卫"划界闭环；剩余两条都指向冻结正典：

- ② 经典本体定义未入正典、接续体立场未认领、治理理论未与道义逻辑 / 制度事实文献对接；
- ③ 条件语言缺最小求值语义，"终止性可证"停留在宣称，不可核对。

取证确认的冻结约束：

1. `tools/hash_spec.py:21-24` 的 `CANONICAL_FILES` 为 `docs/aos-spec.md` + `docs/SPEC-FINGERPRINT.md`，
   两文件字节拼接成 SHA256（`e6884aed…`，登记行 `AOS-ART-001`）。改任一文件即触发 GOV-3。
2. `tools/fingerprint.py:24` 的 `APPENDICES = list("ABCDEFG")` 与附录 F/G 的 `附录 ×7`
   三处共同锁定附录集合；新增附录必须同步结构层清单，否则第 1 关结构核对失败。
3. 多处测试锁死旧基线：`test_new_capabilities.py:18,33`、`test_declaration_digest.py:95`
   直接断言 `e6884aed`；`test_declared_registered.py:62` 与 `test_integrity.py:203`
   要求 `spec_ref` 与登记表最新条目一致。GOV-3 回填会把 `spec_ref` 改为 `AOS-ART-002`。
4. `spec/**/*.yaml` 声明摘要 `91ffe5a1…` 独立于正典哈希域；本轮不改 `spec/`，该域应保持逐字不变。

## 决策

采用 **v2.1.0 信息性附录增量**，语义零变更：

1. **附录 R：理论谱系与立场（信息性）**。写入 Gruber 1993/1995 的经典本体定义；显式认领
   接续体立场为"本体作为契约的工程传统，不接续描述逻辑的开放世界自动推理"；把
   Situation/Event Calculus、von Wright 与 Jones–Sergot 的道义逻辑、Searle 的制度事实 /
   构成性规则分别接到 AX-1/KS-1/KS-5、INV-4/GOV-1 与第 9.3 节残余清单；末节披露
   "谱系定位不等于形式化归约"的理论欠账。
2. **附录 S：条件语言最小求值语义（信息性）**。给出受限布尔档语法（Atom/op/Expr）、
   `env=(snapshot, principal, now)`、`eval: Expr × Env → Bool` 全函数与字段缺失返回
   false 的规则，并以结构归纳证明 `eval` 在 ≤ `|nodes(e)|` 步内停机——使"终止性可证"
   成为可按 AST 节点数与解释器中止性测试核对的命题。明确本附录**不新增 MUST**，
   与 KS-3.3 / KS-7.1 及 INV-11 的关系是解释而非改写。
3. **两个附录均为信息性**。不得作为推翻条款的凭据；条款冲突以正文与 INV 裁决。
   因此不触发 GOV-4 新模式准入、不动 AX/KS/P/INV/BOOT/GOV/VER 的任何标识符与语义。
4. **GOV-3 版本通道**：提案 `SPEC-2026-001`，`base_spec_id: AOS-ART-001`，
   `axiom_or_invariant_touched: none`，`base_layer_touched: no`，
   `golden_test_required: no`，`dry_run_simulation_required: no`；执行
   `aos spec version v2.1.0 --proposal-ref SPEC-2026-001`，append 登记行
   `AOS-ART-002` 并回填两份配置的 `spec_ref`。
5. **结构层同步**：附录 F 与 G 的 `附录 ×7` → `附录 ×9` 并列入 R/S；
   `tools/fingerprint.py` 的 `APPENDICES` 增补 `R`、`S`；A.1 版本谱系加 v2.1.0 行；
   A.3 语义声明补"附录 R/S 为信息性，条款语义逐字一致"。
6. **封存断言改写**：把"当前哈希必须等于 `e6884aed…`"的断言改为"当前哈希已登记 +
   `AOS-ART-001` 历史行仍逐字保留 `e6884aed…`"，守住 append-only 而不阻止合法版本更替。

## 备选（否决）

- 把 R/S 写成新的规范性条款或 MUST：会触发 GOV-4 新模式准入、基座触及判定与 golden test，
  且把"理论谱系定位"升格为强制义务，超出评审通过条件的要求，代价远大于收益。
- 只把 R/S 放进 `docs/` 非正典文档：评审明确要求"引入正典附录"，且这样不会进入哈希域，
  条款级术语保真无从谈起。
- 复用 A–G 之后的 H/I 编号：会与上轮已批准方案（R = references/lineage，S = semantics）
  不一致，并迫使所有下游引用再改一次；R/S 也不与既有附录锚冲突，指纹清单可显式列举。
- 就地改写 `AOS-ART-001` 登记行或删旧行：直接违反 GOV-2.3 只增性（P-15），是自毁登记链。

## 后果

**正面**：理论侧三条通过条件全部闭环——经典定义入典、接续体立场显式认领、道义逻辑 /
制度事实对接、条件语言有可核对的终止性命题；`accept` 的两项遗留条件被消除。

**负面 / 诚实边界**：
- 正典哈希从 `e6884aed…` 变为 `48df813aa7dba890…`（`AOS-ART-002`），`docs/aos-spec.en-overview.md` 的哈希指引、
  两版 README、索引、战略稿、白皮书、定位、指南的版本口径全部联动更新。
- `AOS-ART-001` 永久保留为历史行；`aos verify` 只与登记表**最后一行**比对，
  旧版本副本将不再通过新版本仓库的核对——这是版本更替的固有代价，不是缺陷。
- 附录 R 明示"谱系定位不等于形式化归约"，理论欠账继续在案：道义算子未一阶编码，
  制度事实只以残余清单登记；本 ADR 不宣称已闭合这些欠账。

## 合规与回退

- 流程：ADR-002（本文件）→ GOV-3 提案 `SPEC-2026-001` → `aos spec version` 登记 →
  gates（`aos spec fingerprint` + `aos verify` 四道）→ regression（全量 pytest + 文档守卫）。
- 回退：附录 R/S 可从正典移除、版本说明回滚；但 `AOS-ART-002` 登记行**不可删除**
  （append-only）。真正回退须再开一个 GOV-3 提案登记 v2.1.1 恢复旧文本语义，
  并同步回填 `spec_ref`——这是选择本方案时就接受的不可逆成本。
