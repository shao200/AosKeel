# ADR-004：附录 R / S 信息性勘误之二与 v2.2.0 版本更替

- 状态：Accepted（用户于 2026-11-18 明确授权执行第五轮评议的 P2 修订路线：
  "N8 证明式勘误、N9 R.2 术语 + 参考文献表、R.2 双时态对齐、R.5 增列欠账 —— 合并为
  一次 v2.2.0 信息性勘误"）
- 日期：2026-11-18
- 决策者：项目所有者（模型变更授权保留在仓库之外）
- 关联提案：`SPEC-2026-003`（GOV-3）
- 关联评审：`docs/REVIEW-post-e04875f-full-audit-20261118.md`（第五轮独立评议，N8/N9）
- 前序决策：ADR-002（`SPEC-2026-001`，v2.1.0）、ADR-003（`SPEC-2026-002`，v2.1.1）

## 上下文

第五轮独立评议（对象 `e04875f`）确认 N1..N7/N10/N11 已在前一轮修复收口，但指出两项
**冻结正典内容瑕疵**须走 GOV-3 通道：

1. **N8（附录 S.4 归纳证明步数上界错误）**：正典写 `and` / `or` 因短路取值，步数
   `≤ 1 + max(steps(e1), steps(e2))`。短路不保证只走一边——`e1` 为真时仍须求 `e2`，
   最坏上界应为 `1 + steps(e1) + steps(e2)`。结论 `steps(e) ≤ |nodes(e)|` 仍成立
   （AST 节点数含 BoolOp 节点），但证明中的不等式错了。另指出"机器核对（已接线）"
   的实际内容为 3 个常量样例的有限步返回——0 个计步断言、0 个反例、0 个 ∀ 量化，
   "可核对"的强度明显低于命题。
2. **N9（R.2 文献术语归属不精确，评审人自纠）**：正典写"Hayes 1985 称这种横截面为
   state"。外部查证：Hayes 1985（*Naive Physics I: Ontology for Liquids*）引入的术语是
   **histories**（4D 对象）与 `h@t` 时间切片；Pat Hayes 本人 2007 年 W3C 邮件明确
   "histories was the name I used for 4-d objects"。`state` 属 continuant–occurrent 一侧
   （Galton 传统 / situation calculus）。且 R.3/R.4 提到的 Situation/Event Calculus、
   von Wright、Jones–Sergot、Searle 均无文献条目，与 R.1 的引用保真密度不对称。
3. **理论层第 2 项（R.2 双时态对齐欠账）**：双时态回溯（`valid_time ≤ transaction_time`
   的补录语义）未纳入 R.2 立场论证——在 4D 图景下，补录是新增一个时间部分而非改写过去。

## 文献查证（冻结前人工门 ①：归属逐条核对）

- Hayes 1985：*Naive Physics I: Ontology for Liquids*，Hobbs & Moore 编
  *Formal Theories of the Commonsense World*，Ablex（Norwood NJ），71–107 —— 多来源一致。
- Galton & Mizoguchi 2009："The water falls but the waterfall does not fall: new
  perspectives on objects, processes and events"，*Applied Ontology* 4(2)，71–107 ——
  原文 PDF 与引用源一致；其正文直接讨论 continuant（waterfall 不随水流变化）与
  process/event 的区分。前轮评议遗留的 "Galton (2000) *Logic for Embedded Agents*"
  出处存疑，**不采信入典**。
- Gruber 1993（*Knowledge Acquisition* 5(2):199–220）/ Gruber 1995（*IJHCS* 43(5–6):
  907–928）/ Borst 1997（PhD, Twente）/ Studer et al. 1998（*DKE* 25(1–2):161–197）/
  Guarino 1998（FOIS'98, IOS Press, 3–15）：与 ADR-003 已核对谱系一致。
- McCarthy & Hayes 1969（*Machine Intelligence* 4:463–502）/ Kowalski & Sergot 1986
  （*New Generation Computing* 4(1):67–95）/ von Wright 1951（*Mind* 60(237):1–15）/
  Jones & Sergot 1996（*IGPL* 4(3):427–443）/ Searle 1995（*The Construction of Social
  Reality*, Free Press）：通行引用格式，R.3/R.4 术语对接原文。

## 决策

采用 **v2.2.0 信息性内容勘误版**，语义零变更（不新增任何 MUST、不动条款标识符、不触基座）：

1. **R.2 勘误（N9 + 双时态对齐）**：
   - 术语归属更正：Hayes 1985 将四维对象称 **histories**，`h@t` 即对象在时刻 t 的横截面
     切片；"给定时刻的 state" 属 continuant–occurrent 一侧的 Galton 传统，不归给 Hayes。
   - 补双时态补录的本体论承诺衔接：补录（KS-6.3）不重写过去，而是在四维对象上**新增
     一个时间部分**——`transaction_time` 使新增切片在案，`valid_time` 把它挂接到历史区段；
     append-only 因而不只是存储纪律，而是 4D 立场的本体论承诺：过去不可改写，只可增切片。
2. **S.4 勘误（N8）**：步数上界改为 `≤ 1 + steps(e1) + steps(e2)`（最坏情形两侧均求值）；
   结论 `steps(e) ≤ |nodes(e)|` 不变（AST 节点数含 BoolOp 节点）。
3. **S.4 机器核对升级**：测试内置 S.3 求值规则的**参考求值器（带步数计数）**，对生成式
   S.1 样例空间批量断言 `steps(e) ≤ |nodes(e)|` 并与实现 `eval_boolean` 结果逐一比对——
   真实计步断言替代"样例有限步返回"的代理指标（正典措辞同步）。
4. **R.6 参考文献表（N9）**：新增信息性文献登记 ×12（[01]–[05] → R.1；[06][07] → R.2；
   [08][09] → R.3；[10]–[12] → R.4），归属错误按 GOV-6 处置记录更正。
5. **版本标识**：正典头部 `v2.1.1` → `v2.2.0`；A.1 谱系与 A.3 语义声明、冻结声明各加
   v2.2.0 行；附录 F 指纹清单与附录 G 便携校验版标题版本同步；`docs/SPEC-FINGERPRINT.md`
   标题同步（**指纹算法不动**，仅标题版本字样）。
6. **GOV-3 版本通道**：提案 `SPEC-2026-003`，`base_spec_id: AOS-ART-003`，
   `axiom_or_invariant_touched: none`，`base_layer_touched: no`；执行
   `aos spec version v2.2.0 --proposal-ref SPEC-2026-003`，append `AOS-ART-004` 并回填
   spec_ref。旧行逐字保留（P-15）。
7. **下游口径**：两版根 README、docs/README 双语版、英文概览哈希指引、04-tutorial 的
   TEMPLATE-LOCK 示例输出、05-reference 当前版本行、tests/README 锚点说明同步 v2.2.0 /
   AOS-ART-004；历史签发说明、历史评审正文、AOS-ART-001/002/003 旧行逐字保留。

## GOV-3 提案模板回执（SPEC-2026-003）

```
proposal_id: SPEC-2026-003
proposer: 项目所有者（经仓库外授权）
base_spec_id: AOS-ART-003
schema_objects_affected: []                     # 信息性附录，不触 schema
axiom_or_invariant_touched: none
base_layer_touched: no
affected_existing_deployments: []               # 语义零变更；附录 R/S 无 MUST
migration_path:
  data: n/a
  event_upcasting: n/a
removal_consequence_reference:
  identified_accident: R                        # 介质/登记纪律同源（append-only 保持）
golden_test_required: no
dry_run_simulation_required: no
```

## 备选（否决）

- 修实现去迁就 S.4 旧不等式（给 `and`/`or` 加短路计步豁免）：与实现无关——错在证明文本
  的不等式本身，实现语义无恙；改文本是唯一正确方向。
- 把 S.4 命题扩大到完整 R10 profile（给出全局步数界）：`sorted` 超线性使全局线性界
  不成立，范围限定（v2.1.1 已做）维持；不升级宣称。
- 只改 R.2 术语、不开参考文献表：与 R.1"引用保真"密度不对称的欠账继续存在，评议明确
  建议同轮补齐；一并执行。
- 文献表收录第三轮评议列出的 "Galton (2000) *Logic for Embedded Agents*"：出处存疑，
  未采信入典（宁可缺一条不可错一条——v2.1.0/v2.1.1 内容一次通过率 0/2 的教训）。

## 后果

**正面**：N8/N9 与 R.2 双时态欠账全部收口；S.4 机器核对从"3 样例有限步"升级为
"生成式样例空间上的真实计步断言 + 实现一致性比对"；文献归属密度与 R.1 对齐；
第五轮评议全部 11 项发现（N1..N11）至此全部闭环或显式登记。

**负面 / 诚实边界**：
- 正典哈希再次变更，`AOS-ART-003` 永久为历史行；`AOS-ART-001/002/003` 旧副本不再通过
  新仓库核对——版本更替固有代价，ADR-002/003 已披露。
- R.5 的理论欠账（道义算子未一阶编码、制度事实仅残余清单）继续登记，不因本版闭合。
- "state 属 Galton 一侧" 的对接仍属谱系定位而非形式化归约；R.6 为信息性登记，
  归属错误按 GOV-6 处置记录更正。
- 连续两轮勘误后本版执行了 ADR-003 承诺的冻结前人工门（归属逐条查证 + 语义与实现
  逐行对照 + 证明式复核），其结果即本 ADR 上下文段与文献查证段的证据清单。

## 合规与回退

- 流程：ADR-004（本文件）→ GOV-3 提案 `SPEC-2026-003` → `aos spec version v2.2.0` →
  gates（`spec fingerprint` + `verify` 四道）→ regression（全量 pytest + 文档守卫 +
  发布闸门）。
- 回退：`AOS-ART-004` 登记行不可删除（append-only）；真正回退须再开 GOV-3 提案以
  更高版本执行。
