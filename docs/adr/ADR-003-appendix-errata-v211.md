# ADR-003：附录 R / S 内容勘误与 v2.1.1 版本更替

- 状态：Accepted（用户于 2026-11-18 明确授权"按 ADR → GOV-3 提案 → gates → regression 执行"，
  针对第四轮复核"已落地、待勘误"结论）
- 日期：2026-11-18
- 决策者：项目所有者（模型变更授权保留在仓库之外）
- 关联提案：`SPEC-2026-002`（GOV-3）
- 关联评审：`docs/本体论同行评议-第三轮-20261118.md` §〇·续（2026-11-18 复核补记）
- 前序决策：ADR-002（`SPEC-2026-001`，v2.1.0）

## 勘误项与版本命名冲突的消解

ADR-002 曾把 `v2.1.1` 预留为"撤销附录 R/S 的回退版本"。本 ADR 把 `v2.1.1` **改作附录内容勘误版**——
理由：回退从未发生、R/S 方向已经评审肯定（R.3/R.4/R.5、S.4 证明），撤销是低概率分支；而勘误是已确认的
当前需求。两者同走 GOV-3 信息性通道、同样 append-only，命名不改变任何条款语义；回退选项仍可由后续
提案以更高版本号（如 v2.2.0）执行。此取舍在本 ADR 留痕，不构成对 ADR-002 正文的改写。

## 上下文

第四轮复核独立复跑确认 v2.1.0 的**流程全绿**（语义零变更、append-only 登记、三关+指纹、387 passed、
生成物仅头部联动），但认定附录 R/S 的**内容**存在学术/技术错误，通过条件②③判定为"已落地、待勘误"。
证据经本轮再次回查全部成立：

1. **R-1（文献归属）**：`aos-spec.md` R.1 把 formal/shared 归给 Gruber 1995。查证的标准谱系为
   Gruber 1993（explicit specification of a conceptualization）→ Borst 1997（引入 shared）→
   Studer/Benjamins/Fensel 1998（合并为 formal, explicit specification of a shared conceptualization）。
   Gruber 1995（*Toward principles for the design of ontologies used for knowledge sharing*）谈设计原则，
   未以 formal+shared 修订定义。新冻结正典里的学术错误，与 R 附录"引用保真"目的相悖。
2. **R-2（立场认领）**：R.2 标题称"接续体立场（显式认领）"，正文却把 perdurant 偷换为动词义"接续…传统"，
   未声明 4D 本体论承诺（个体 = 事件流时间切片；状态 = valid_time 上的函数），亦未引 Galton / 4D fluents。
3. **R-3（补引）**：Studer 1998 / Borst 1997 / Guarino 1998 未入典；与 R-1 同源，一并修复。
4. **S-1（P1，缺失语义）**：S.2/S.3 称 `eval` 为全函数、字段缺失返回 false；实现
   `boolean_profile.py:62-67` 对 NameError/AttributeError/TypeError 抛 `InterpreterRejected`，
   `pipeline.py:120-125` 记审计后重抛 → 提交被拒绝。两者皆 fail-closed，但"全函数 false"不是被实现语言的最小语义。
5. **S-2（now）**：S.2 写 `env=(snapshot, principal, now)`；实现 env 仅两键，R1 只许两源，R4–R6 禁时钟。
6. **S-3（符合性）**：S.1 是 R10 profile 真子集（实现另许 len/sorted 等白名单调用与算术），
   SC 编译器只校验首 token 来源（`sc_compiler.py:51-55`），未把表达式限制在 S.1；S.5"编译器实现 S.1 语法"不实。
7. **S-4（范围与机器核对）**：`steps ≤ |nodes|` 对含 sorted 的完整 profile 不成立，应限定到 S.1；
   "可由中止性测试核对"缺位——本轮已补 `tests/conformance/test_boolean_profile_semantics.py`。
8. **E-3（头部版本）**：正典头部仍自署 `v2.0.0 · Frozen`，与 A.1 谱系/冻结声明/登记表的 v2.1.0 并存。

非冻结域 E-1（登记行追加位置）、E-2（版本硬编码）已于本轮**在 v2.1.1 之前即修**，不占本次版本通道。

## 决策

采用 **v2.1.1 信息性内容勘误版**，语义零变更（不新增任何 MUST、不动条款标识符、不触基座）：

1. **附录 R 勘误**：
   - R.1 改为正确三段谱系（Gruber 1993 → Borst 1997 → Studer/Benjamins/Fensel 1998），
     明确 Gruber 1995 是知识共享设计原则而非定义修订；补 Guarino 1998 的 upper-level 定位参照。
   - R.2 真正认领 perdurantism/4D 立场：显式声明"个体 = 事件流时间切片；状态 = valid_time 上的函数"，
     接 Galton 的 continuant/occurrent 与 4D fluents（Hayes 1985 把横截面称为 state）；
     保留"本体作为契约、不接续 OWL 开放世界推理"的工程边界，但不再用它冒充哲学认领。
   - R.3/R.4/R.5 正文准确，不动。
2. **附录 S 勘误**：
   - S.2 删 `now`，env = (snapshot, principal)；明示 now 仅为 KS-6 的 valid_time 记录口径，非求值环境成员。
   - S.2/S.3 把全函数描述改为**偏函数拒绝语义**：未声明名/字段/类型不合 → `InterpreterRejected`，
     管线记审计（等价 false 的留痕）后拒绝提交；both fail-closed，语义以拒绝为准。
   - S.1 显式声明是 R10 完整 profile 的**真子集**（最小核心片段）；S.5 改为"编译器只校验首 token 来源，
     不把表达式限制在 S.1；解释器按 R10 完整 profile 求值"，删除"编译器实现 S.1 语法"的不实宣称。
   - S.4 终止性命题限定到 S.1 片段；对完整 profile 只承诺 AST 白名单 + MAX_DEPTH=16 的预算上界；
     机器核对指向本轮新增的守卫测试。
3. **E-3**：正典头部 `v2.0.0` 改为 `v2.1.1`，签发说明保留历史层（v2.0.0 换代缘由），
   新增 v2.1.1 勘误说明；A.1 谱系与冻结声明加 v2.1.1 行。
4. **GOV-3 版本通道**：提案 `SPEC-2026-002`，`base_spec_id: AOS-ART-002`，
   `axiom_or_invariant_touched: none`，`base_layer_touched: no`；执行
   `aos spec version v2.1.1 --proposal-ref SPEC-2026-002`，append `AOS-ART-003` 并回填 spec_ref。
   依赖 E-1 已修的 ART 表尾插入，登记行自动归位（不再手工搬移）。
5. **下游口径**：指纹清单标题版本、英文概览哈希指引、两版 README、索引/战略/白皮书/定位/指南的
   当前版本声明同步 v2.1.1；历史签发说明、历史评审正文、AOS-ART-001/002 旧行逐字保留。

## 备选（否决）

- 把勘误塞进 `v2.1.0` 就地改：正典已冻结且 `AOS-ART-002` 登记哈希已生效，等于就地改历史 → 违反 GOV-2.5/P-15。
- 只改 README/指南、不动正典：评审明确指出错误在**冻结正典**里，且与"引用保真"目的相悖；旁挂件改了也盖不住。
- 为 S-1 改实现去迁就附录（让缺失字段返回 false）：会削弱 R1 输入封闭的 fail-closed 语义，
  把"拒绝谓词性猜测"改成"猜测为 false"，是安全性质倒退；正确方向是让附录如实描述实现。
- 把 R/S 升为规范性条款：会触发 GOV-4 与基座触及判定，超出勘误范围。

## 后果

**正面**：通过条件②③从"已落地、待勘误"转为闭环；引用谱系正确、4D 立场有实质承诺、附录 S 成为
被实现语言的可核对语义而非理想化描述；E-1/E-2/S-4 三项工程残留同轮收口。

**负面 / 诚实边界**：
- 正典哈希再次变更（`48df813a…` → 新值），`AOS-ART-002` 永久为历史行；
  `AOS-ART-001/002` 旧副本不再通过新仓库核对——版本更替固有代价，ADR-002 已披露。
- R.5 的理论欠账不因本次勘误闭合：道义算子未一阶编码、制度事实仅残余清单登记；本 ADR 不宣称已闭合。
- 4D 认领是**本体论立场声明**而非形式化归约：AOS 仍非描述逻辑推理机，OWL↔AOS 不可译表继续有效。
- 冻结文本出错代价高（不可逆、须再开提案）；本轮接受评审建议，在 gates 前增设
  "附录内容独立校对"人工门（文献归属逐条查证 + 语义与实现逐行对照），其结果即本 ADR 上下文段的证据清单。

## 合规与回退

- 流程：ADR-003（本文件）→ GOV-3 提案 `SPEC-2026-002` → `aos spec version v2.1.1` →
  gates（`spec fingerprint` + `verify` 四道）→ regression（全量 pytest + 文档守卫 + 发布闸门）。
- 回退：`AOS-ART-003` 登记行不可删除（append-only）；真正回退须再开 GOV-3 提案以更高版本执行。
