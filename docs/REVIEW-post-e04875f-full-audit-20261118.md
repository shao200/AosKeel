# AosKeel 更新后项目全新反省与同行评议（第五轮）

- 评审日期：2026-11-18
- 评审对象：仓库 HEAD `e04875f`（`fix(conformance): 附录 S 测试补登布线 + 登记表字节保真读写（同行评议四项修复）`），软件 `0.3.0`，正典 `v2.1.1`（`AOS-ART-003`，`sha256:18868adf…`）
- 评审基线：`6a21b1e`（双语文档收口）→ HEAD 共 44 文件 / +972 −111；`origin/main == HEAD`，工作区干净
- 评审性质：**独立新一轮**。沿用仓库评议序列（前轮 `REVIEW-ontology-peer-review.md`、第三轮《本体论同行评议-第三轮》、第四轮 v2.1.1 勘误复核），本轮为第五轮；不采信任何未经复核的项目自述
- 方法：源码逐行回查 + 门禁实测 + 副本可证伪实验 + 外部文献查证；全部结论标注证据路径
- 独立性声明：本轮**未修改任何被评审文件**，未执行 GOV-3、未推送、未 `git pull`。评审过程中 `aos release` 重写的 `dist/RELEASE-MANIFEST.json` 已按 HEAD 还原，收尾时 `git status` 为空

---

## 〇、结论先行

| 裁决对象 | 前轮判定 | 本轮判定 | 变化理由 |
|---|---|---|---|
| 可验证的本体工程脚手架 | accept（强） | **accept with minor revision（下调半档）** | 新增 4 条 P1 落在承重路径：条件谓词层、实例侧声明门、发布覆盖面、嵌套闸门稳定性 |
| "ontology-based" 理论宣称 | minor revision（②③ 待勘误） | **minor revision 维持，②③ 判「已落地、二次待勘误」** | v2.1.1 修好了字面错误，但附录 S 再次与实现不一致（N2），并新增 N8/N9 两处内容瑕疵 |
| GOV-3 治理流程 | 高度肯定 | **流程合规 2/2，内容一次通过率 0/2** | 两次正典跃迁（v2.1.0 / v2.1.1）均产生须勘误的内容错误；前轮建议的「附录内容独立校对」人工门尚未制度化 |

**一句话**：四项修复是真的，全部门禁在模板根也是真的绿；但「本地全绿 ≠ 系统一致」在本轮得到四点新的量化证据。最硬的一条不是文档口径，而是**冻结附录 S 描述了一个实现里不存在的语言**，而刚补登的守卫用「集合里有这些字符串」为它背书。

**不可宣称完成的部分**：条件表达式缺布尔类型约束（可致条件恒真放行）、白名单调用 9/9 不可达、实例侧第四道门默认 SKIP、12 个测试文件不在发布闸门内。这四项未闭合前，不建议以「发表级 / 可交付」对外表述。

---

## 一、评估矩阵（七维实测）

| 维度 | 本轮独立实测 | 裁决 |
|---|---|---|
| 冻结域与规范 | v2.1.1 语义零变更成立（6 处删除行均为版本标题 / 附录计数 / 指纹清单标题）；正典 `18868adf…`、声明 `91ffe5a1…`（28 份）零漂移 | 通过 |
| 门禁实测 | `verify` 三关全绿、`fingerprint` OK、`aos test` 61/61/0/1、`aos cq` 10/10、`release` 五步 PASS、`generate --force` 零漂移（7 文件） | 通过 |
| 全量回归 | 395 collected；两次全量各 1 failed（首次 `test_deselected_capability_pruned` 因评审并发 `generate`，串行复跑换成 `test_real_gate_end_to_end`）；单独复跑该测试亦 FAIL | 条件 |
| 附录 R/S 符合性 | R.1 谱系经外部文献逐条吻合；R.2 术语归属不精确；S.1 / S.3 / S.4 与实现矛盾 | 不通过 |
| 条件谓词层 | 白名单调用 9/9 被 `SOURCE-FORBIDDEN` 拒绝；非谓词表达式 `bool()` 强制转换后恒真 | 不通过 |
| 发布与测试覆盖 | 61/73 文件（83.6%）在布线表内；12 文件 / 55 函数（14.4%）发布闸门不执行 | 不通过 |
| 实例侧防护 | 无 DECL 登记的实例，篡改声明 288→319 字节、摘要 `91ffe5a1…→180f58a5…`，`verify()` 仍返回 0 | 不通过 |

规模口径（实测）：`src` 30 个 `.py`、`tools` 21、`tests` 73、代码合计 10 284 行；381 个 `def test_` 函数 / 395 个 pytest 用例；`spec/` 28 份 yaml；61 条布线 / 29 条 INTEGRITY。

---

## 二、更新边界与「四项修复」逐条复核

相对 `6a21b1e` 的累计改动 = 双语文档收口 → 第三轮划界修补（`16d3114`）→ v2.1.0 附录 R/S（`078e93d`）→ v2.1.1 勘误（`b52582e`）→ 四项修复（`e04875f`）。

| 修复项 | 复核结论 | 证据 |
|---|---|---|
| ① INTEGRITY-29 补登 `test_boolean_profile_semantics.py` | **成立但未收口**：`config/verification.yaml:42` 已登记，`aos test` 选中 61 项；但另有 12 个测试文件仍未布线（N4） | `git show e04875f -- config/verification.yaml`；`wiring.wired_paths()` 与 `tests/**/test_*.py` 差集计算 |
| ② 登记表字节保真读写 | **仅 ART 路径成立**：`_append_art_rows` 与 `_set_spec_ref` 改 `read_bytes/write_bytes`，CRLF 副本下旧行原字节保留、无混合换行；但 `register_declarations` 仍是 `open("ab")` + `read_text` 判断（N7） | `tools/hash_spec.py:42-78`（已修）vs `:172-179`（未修）；`test_artifact_ref.py` CRLF 守卫只调 `hs.supersede` |
| ③ `_latest_spec_version()` 单测 | **成立**：空登记表回落正典头部 `v2.1.1`，登记后跟随 `v9.9.9` | `tests/conformance/test_artifact_ref.py::test_latest_spec_version_follows_registry_then_canonical` |
| ④ 口径同步九处文档 + 重签发布清单 | **漏一处**：`docs/guide/04-tutorial.md:263` 仍写「骨架字节级零漂移 · 3 文件」，实测 7 文件；同文件内 60→61 布线已更新，属同批次遗漏（N10） | `aos release` 实测输出 `codegen: … · 7 文件`；`grep -rn "3 文件" docs/` |

**语义零变更独立复核**：`git diff 16d3114..HEAD -- docs/aos-spec.md` 的删除行共 6 条，全部为头部版本标识、指纹清单标题、附录计数 `×7→×9` 与便携校验版标题；AX / KS / P / INV / BOOT / GOV / VER 规范性正文**零删除**。v2.1.1 走信息性通道的判定成立。

**已闭合项（本轮独立复核，非采信自述）**：`reconcile_bijection` 显式双射、`upcasting.CURRENT` 同源、四条边界披露 + `test_declaration_execution_boundaries_disclosed`、README §1–§9 镜像守卫、v2.1.0/1.1 的 append-only 登记与生成物头部联动、S.2 偏函数拒绝与 `pipeline.py:120-125` 审计记录一致、R.1 文献谱系（外部检索：Gruber 1993 → Borst 1997 → Studer/Benjamins/Fensel 1998，Gruber 1995 为设计原则，与正典一致）。

---

## 三、本轮新发现

### P1（承重路径，建议优先）

**N1 · 条件表达式无布尔类型约束，非谓词可恒真放行**
`eval_boolean` 末行 `return bool(result)`（`src/interpreter/boolean_profile.py:68`）；注册期 `sc_compiler.py:51-55` 只校验首 token 来源与 `dry_run ⇒ audit` 蕴含。实测：

| 表达式 | 结果 |
|---|---|
| `snapshot.amount` | `True` |
| `snapshot.status` | `True` |
| `snapshot.amount + 1` | `True` |
| `snapshot.amount >= 10**6` | `False` |

即「条件」写成任意一个白名单内的值表达式，会被静默求值为真并放行提交。这与 README §1「规则编译成机器可检查约束」、正典 S.1 `Expr ::= Atom | not | and | or` 的谓词语义不符，且是**唯一一条影响提交门放行方向的发现**。
建议：注册期或求值期要求 AST 顶层为 `Compare / BoolOp / UnaryOp(Not)` 且结果 `isinstance(x, bool)`，否则 `InterpreterRejected`；补负向守卫（非冻结域，可即修）。

**N2 · 白名单函数调用 9/9 不可达，冻结附录 S 描述了一个不存在的语言**
`_ALLOWED_CALLS = {len, all, any, min, max, sum, abs, round, sorted}`（`boolean_profile.py:17`），`ast.Call` 也在 `_ALLOWED_NODES`（`:16`）。但 `_lint` 把**所有** `ast.Name` 收进 `roots`（`:35-36`），R2 随后拒绝任何不起于 `snapshot./principal.` 的名字（`:54-56`）——函数名本身即被拒。全量实测 9/9 全部 `REJECTED: SOURCE-FORBIDDEN`。

后果落在冻结正典：`aos-spec.md:747-748`（S.1「完整 R10 profile 另许白名单函数…」）、`:781-783`（S.3「按同一 AST 白名单求值」）、`:790-792`（S.4「含 `sorted` 等白名单调用的表达式其求值步数可超线性，不适用 `≤ |nodes(e)|` 界」）三处，都以一个运行时不存在的扩展语言为前提。尤其 S.4 用 `sorted` 的超线性来划定命题范围，而 `sorted` 根本无法求值。

更值得指出的是**守卫的代理指标失效**：`test_boolean_profile_semantics.py:51` 只断言 `{"len","sorted","all"} <= _ALLOWED_CALLS`（检查集合成员），从不对任一调用实际求值；`:48-57` 的 S-3 测试用「算术式通过编译」证明「不限制在 S.1 文法内」，也未验证调用可执行。因此 `e04875f` 提交信息所称「附录 S 机器核对从宣称落为事实」，实际核对的是字符串集合，不是语言能力。
建议二选一：**(a)** 修实现让 R2 跳过 `Call.func` 的函数名，使 9 个调用可用，并补 `sorted` 超线性的真实计步反例；**(b)** 修附录，把「完整 profile 另许调用」改为「AST 白名单允许、R2 源封闭使其不可达」，并重写 S.4 的范围论证。**(b) 触冻结正典，属模型变更，须走 ADR → GOV-3 提案 → gates → regression；模型变更权限在仓库之外，本轮不执行、仅给方案。**

**N3 · 实例侧第四道门默认 SKIP，且被包装成 `VERIFY-OK`**
前轮 P0-1 加的声明摘要门在模板根有效，但 `aos init` 实例不复制 DECL 区（设计如此，`hash_spec.py:15-16` 明示 SKIP）。副本实验（`labC2`）：登记表只保留 ART 区 → `verify()` 打印 `DECL-DIGEST: SKIP —— 未登记` 并返回 0；随后把 `spec/competence/CQ-3.cq.yaml` 从 288 字节改为 319 字节，声明摘要 `91ffe5a1… → 180f58a5…`，`verify()` **仍返回 0**，CLI 仍输出 `VERIFY-OK: 三关连续通过 —— 结构 / 密码学 / 注册`（`src/cli/main.py:134-152`）。

即：实际部署形态下，业务声明（条件阈值、权限、副作用）的篡改不被密码学门发现。`docs/samples/llm/README.md:24` 只披露「干净实例 CQ-10 必失败、须 `spec register-declarations`」，未披露密码学门同样 SKIP。SKIP 本身是诚实设计，但「显式 SKIP」与「三关连续通过」并置构成误导。
建议：三关输出把 SKIP 显式标为 `PASS-WITH-SKIP` 并列出跳过项；`release_gate` 对 SKIP 实例拒不出制品；或 `aos init` 强制登记声明摘要（此项改变实例基线，须评估是否属模型变更）。

**N4 · 发布闸门只跑 61/73 个测试文件**
`tools/release_gate.py:24-32` 的 `_default_tests()` 只执行 `wiring.wired_paths()`。差集实测：

| 未布线文件 | 函数数 |
|---|---|
| `test_declared_registered.py`（第三轮双射修复） | 5 |
| `test_new_capabilities.py`（A/B/C/E 边界守卫） | 7 |
| `test_dual_distribution.py`（ADR-001 双分发守卫） | 6 |
| `test_codegen.py` / `test_release_gate.py` / `test_ontology_draft.py` | 6 / 4 / 6 |
| `test_agent_surface.py` / `test_governance_effective.py` / `test_saga_compensation.py` | 4 / 3 / 4 |
| `test_forbidden.py` / `test_forbidden_coverage.py` / `test_kernel_roles_enforced.py` | 4 / 2 / 4 |
| **合计** | **55 / 381（14.4%）** |

`e04875f` 补登了 `test_boolean_profile_semantics.py` 一个，另 12 个仍在门外，其中包含 4 个直接守卫前几轮修复成果的文件。这与第三轮评议提出的「每个声明字段 MUST 有命名消费者或注册期显式豁免」是同一纪律的延伸：**测试文件同样应「在布线表内或显式豁免」**。
建议：把 12 个补入 `integrity_paths`（非冻结域），并加一条守卫锁住「`tests/**/test_*.py` 全量在册」，防止再次漏登。

**N5 · 发布闸门判定在本环境可复现地不稳定，且失败信息被吞**
`test_real_gate_end_to_end` 单独复跑亦 FAIL；两次全量 pytest 各有 1 failed 且落点不同。根因实测：闸门内嵌 pytest（不带 `--basetemp`）清理临时目录时触发宿主 safe-delete 阈值（`SAFE_DELETE_BULK_CONFIRM_REQUIRED`，count 2332 / threshold 50 / scope turn），**61 条布线测试全部通过但进程退出码 1** → `step("tests")` 判 FAIL → `report["ok"] = False`。而同一会话里前台 `aos release` 五步 PASS（该 turn 计数未超阈值）。

前几轮一直把这类结果归为「环境限制、非代码回归」，本轮建议升级为工程改进项：`_default_tests()` 用 `capture_output=True` 吞掉 stdout/stderr，只抛 `pytest exit=<code>`（`release_gate.py:28-30`），既不可诊断，又使「5 关全绿」依赖宿主临时目录策略。
建议：嵌套 pytest 固定 `--basetemp` 到仓库外隔离目录（可由环境变量配置），失败时把 stdout/stderr 尾段写进 `detail`。**这是环境耦合问题，不是产品回归，但「不可复现的绿」不应算作发布证据。**

### P2

**N6 · GOV-3 治理通道缺机器校验，登记表是无外部锚的自签信任根**
`supersede()` 只检查 `if not proposal_ref`（`hash_spec.py:100-102`），`src/cli/main.py:381` 的 `SPEC-YYYY-NNN` 仅出现在 usage 字符串；版本号 `spec_version` 无任何格式/单调性约束。副本实验（`labB`）：

1. 初始 `verify() = 0`；改正典 +33 字节 → `verify() = 1`（MISMATCH，门有效）；
2. `supersede("garbage-version", "x")` → **接受**，登记 `| AOS-ART-004 | garbage-version | sha256:ae88e615… |`；
3. 再 `verify() = 0`。

即：**同时改 `docs/aos-spec.md` 与 `docs/ARTIFACT-REGISTRY.md` 两个文件、不需要任何密钥，即可让密码学门重新全绿**；登记表按设计不在哈希域（`hash_spec.py:6`），也未被签名、git tag 或 RELEASE-MANIFEST 二次锚定。历史 DECL 行还使用了 `REVIEW-2026-11-17-R2` 这类非 `SPEC-YYYY-NNN` 提案号，说明格式约束从未生效。
建议：提案号格式 + ADR 文件存在性校验（非冻结域可加）；登记表当前哈希锚定到外部不可变引用（git tag / 签名 / 双向清单）。若改哈希域或指纹算法，**属模型变更，不照做**。

**N7 · 字节保真修复只覆盖 ART 路径**
CRLF 登记表副本（`labA2`，起始 10 行纯 CRLF）：`supersede()` 后旧 ART 行原字节保留、无混合换行（**已修部分成立**）；但随后 `register_declarations()` 首次写入 DECL 段，文件变为 **12 行 CRLF + 6 行纯 LF** 的混合换行。`tools/hash_spec.py:172-179` 仍用 `open("ab")` 追加 + `read_text()` 判断，`test_artifact_ref.py` 的 CRLF 守卫只覆盖 `supersede`。
建议：`register_declarations` 复用 `_append_art_rows` 的字节纪律（新行随既有 EOL），补对称守卫。功能未损坏，但 P-15「字节精确」在半条路径上仍失守，与 `.gitattributes * -text` 的纪律不一致。

**N8 · 附录 S.4 的归纳证明步骤不成立，机器核对未核对步数**
正典 `:796` 写「`and` / `or` 因短路取值，步数 `≤ 1 + max(steps(e1), steps(e2))`」。短路不保证只走一边：`e1` 为真时仍须求 `e2`，最坏上界应为 `1 + steps(e1) + steps(e2)`。结论 `steps(e) ≤ |nodes(e)|` **仍成立**（AST 节点数含 BoolOp 与 operator 节点），但证明中的不等式错了。

「机器核对（已接线）」（`:799-802`）实际内容为：`test_boolean_profile_semantics.py:60-77` 对 3 个常量样例断言节点数 < 64、节点类型在白名单、树深 ≤ `MAX_DEPTH`、求值返回 bool——**0 个计步断言、0 个反例、0 个 ∀ 量化**。它证明的是「3 个样例有限步返回」，不是命题 `∀e, steps(e) ≤ |nodes(e)|`。措辞上正典未直接谎称步数已测，但「可核对」的强度明显低于命题。
建议：随下次正典勘误把不等式改为 `1 + steps(e1) + steps(e2)`；守卫要么加真实计步（instrument interpreter），要么把定位降级为「样例有限步验证」并在正典同步措辞。

**N9 · R.2 文献术语归属不精确（评审人自纠）**
正典 `:698-700` 写「4D fluents…（Hayes 1985 称这种横截面为 state）」。外部查证：Hayes 1985（*Naive Physics I: Ontology for Liquids*）引入的术语是 **histories**（4D 对象）与 `h@t` 时间切片；Pat Hayes 本人 2007 年 W3C 邮件明确「*histories was the name I used for 4-d objects*」。`state` 属 situation calculus / Galton「state for a given time」一侧的术语。此处系前轮评仪表述被照抄进冻结正典的残留，**评审人主动更正**。
建议：改为「Hayes 1985 的 histories / `h@t` 时间切片；Galton 的 continuant–occurrent 区分与 state 概念」，并补一份附录 R 参考文献表（当前 R.3/R.4 提到 Situation/Event Calculus、von Wright、Jones–Sergot、Searle 均无文献条目，与 R.1 的引用保真密度不对称）。

### P3

**N10 · 文档口径残留两处**：① `docs/guide/04-tutorial.md:263`「3 文件」vs 实测 7 文件；② 「三关」（CLI 输出、`guide/02` `03` `04` `05` `08`）与「四道」（`ADR-001:40,48`、`ADR-002:81`、`ADR-003:96`）并存，无一处说明二者关系（实为三关四道：密码学层内含正典 + 声明摘要双比对）。建议纳入 `test_doc_consistency` 由 `doc_metrics` 派生。

**N11 · 控制台白名单的形式脆弱性（不构成漏洞）**：`_authorize` 仅取 `args[0]` 作子命令（`tools/console.py:31-40`），实测 `draft ['--proposal-ref','P','promote','x.yaml']` 被放行（label=`draft`），但 CLI `draft` 分支要求 `rest[0] == "promote"`（`main.py:433-435`），故不会触发晋升——**实测不可绕过**。另 `console.py` docstring 自承默认仅绑 `127.0.0.1` 且无认证，README §9 / 白皮书只写「白名单 fail-closed」，未披露「无认证」；建议在工程边界表补一行。

---

## 四、理论层评议

1. **R.1 已达标**：三段归属谱系经外部文献逐条吻合，Gruber 1995 的定位纠正准确，Guarino 1998 的 upper-level 对照恰当。这是 v2.1.1 勘误最实的一块。
2. **R.2 立场认领真实但欠一层对齐**：perdurantism / 时间切片 / `valid_time` 函数 / 不接续 DL 开放世界推理，均已显式写下，前轮「标题承诺正文未交付」的问题闭合。但**双时态回溯**（`valid_time ≤ transaction_time` 的补录语义）未纳入该立场论证：在 4D 图景下，补录是新增一个时间部分而非改写过去，正典只在 R.2 提了 `valid_time` 函数与 KS-6.1，没有把 append-only 与「过去不可改写、只可增切片」的本体论承诺接起来。这是比 N9 更实质的理论欠账，建议随 R.5 一并登记。
3. **R.5 的两项欠账（道义算子未一阶编码、制度事实仅残余清单）维持披露**，不判闭合——项目方自己也未宣称闭合，诚实度予以肯定。
4. **附录 S 的问题不是「没写模型论」，而是「写了模型论但没对准实现」**：v2.1.0 写成理想化全函数，v2.1.1 改成偏函数拒绝（这一步对了），但 N2 使「完整 R10 profile」整体不可达。连续两轮勘误都产生新的内容错误，说明「语义逐行对照」这道人工门没有真正执行到实现层，只执行到文档层。
5. **总体理论判断**：把「治理即启动条件 + 合法性残余清单」作为理论增量仍成立且稀缺；OWL↔AOS 不可译表、三层开闭世界口径、CQ 可执行化依然站在文献正确一侧。但以「ontology-based」为宣称，仍缺一篇独立理论章把治理义务与 deontic logic / 制度事实做成可引用的形式化对照（前轮已提，本轮维持）。**维持 minor revision，不升为 accept。**

---

## 五、工程层评议

**强项（本轮再次核实）**：提交管线顺序与版本冲突完整重跑、角色证据先于条件评估、`write_raw` 拒写落审计、内存事件存储与 wheel 边界如实披露、条款 ID ↔ 代码 ↔ 测试三向锚定、fail-closed 文化贯穿、所有生成物字节零漂移、v2.1.1 语义零变更。同类框架中，把「不提供什么」写成机器守卫的做法仍属最严一档。

**结构性弱点**：本轮 N1/N2/N4 与前几轮的 `invariant.expression` 无消费者、`dry_run` 无执行点、`references` 死算子属**同一根因**——「声明/白名单里写了，但没有命名消费者」。第三轮建议的通用规则「每个声明字段 MUST 有命名消费者或注册期显式豁免」目前只逐条打补丁，未上升为注册期元规则；N2 表明连**守卫本身**都会用代理指标（集合成员）放过无消费者的能力。建议把该规则实现为注册期校验 + 一张「消费者/豁免登记表」，而不是继续枚举。

---

## 六、治理与流程评议

- **流程合规 2/2**：v2.1.0（ADR-002 / `SPEC-2026-001`）与 v2.1.1（ADR-003 / `SPEC-2026-002`）均走 ADR → 提案 → 登记 → `spec_ref` 回填 → 生成物再生成 → gates → regression；旧登记行逐字保留，`_latest_spec_version` 消除了硬编码，E-1/E-2 工程残留已修。不可逆成本在 ADR 中披露充分。
- **内容一次通过率 0/2**：v2.1.0 有 R-1/R-2/S-1..S-4 九项须勘误；v2.1.1 修好了这九项，却留下 N2/N8/N9 三项。冻结文本的错误代价是不可逆的（须再开提案），因此这是治理流程的**实质缺陷而非瑕疵**。
- **建议增设冻结前强制门**：① 文献归属逐条核对（含术语原义）；② **实现语义逐行对照**——对附录中出现的每一个语言能力，写一个「实际求值成功」的正例，而不只是检查常量集合；③ 证明式单独复核（N8）。第②条若在前两轮执行，N2 在冻结前即被挡住。

---

## 七、通过条件与修订路线

| 优先级 | 事项 | 域 | 是否需授权 |
|---|---|---|---|
| P0 | N1 条件布尔类型约束 + 负向守卫；N2 先定方案（实现侧或附录侧） | 非冻结 / 冻结二选一 | 若改附录 S → **模型变更，须 ADR → GOV-3 提案 → gates → regression，权限在仓库之外** |
| P0 | N3 实例侧 SKIP 显式化 + release gate 对 SKIP 拒绝出制品；N4 补登 12 个测试文件并加「全量在册」守卫 | 非冻结 | 否，可即修 |
| P1 | N5 嵌套 pytest 固定 basetemp + 失败详情；N6 提案号/版本校验 + 登记表外部锚；N7 DECL 路径字节对称 + 对称守卫 | 非冻结（外部锚方案若改哈希域则需授权） | 部分 |
| P1 | N10 文档口径（3→7 文件、三关四道释义）纳入 `test_doc_consistency` | 非冻结 | 否 |
| P2 | N8 证明式勘误、N9 R.2 术语 + 参考文献表、R.2 双时态对齐、R.5 增列欠账 —— **合并为一次 v2.2.0 信息性勘误**，不单独开通道 | 冻结 | 是，须 GOV-3 |
| P2 | N11 控制台「无认证」写入两版 README §9 工程边界表 | 非冻结 | 否 |

**不予通过项**：在 N1/N2/N3/N4 未闭合前，不判「工程面 accept（强）」，不判理论条件②③完全闭环，不建议对外宣称发表级/可交付。

**本轮不执行项（红线）**：不改冻结正典与 `e6884aed` 历史行、不改 `SPEC-FINGERPRINT.md` 的指纹算法、不三栏化中文正典、不把 `spec/` 并入正典哈希域、不执行 GOV-3、不推送、不 `git pull`。所有模型变更保留在仓库之外的授权链上。

---

## 八、可复现实验清单

| # | 命令 / 方法 | 关键输出 |
|---|---|---|
| E1 | `.venv/Scripts/python.exe -m src.cli.main verify` | 三关 OK；`18868adf…` / `91ffe5a1…`（28 份） |
| E2 | `… -m src.cli.main test` / `cq run` / `release` / `generate --force` | 61/61/0/1；CQ 10/10；五步 PASS（7 文件）；零漂移 |
| E3 | `pytest -q --basetemp=<仓库外>` 两次 + `pytest tests/conformance/test_release_gate.py -q` | 各 1 failed；`test_real_gate_end_to_end` 单独亦 FAIL |
| E4 | 手动重放 `_default_tests()` 等价 61 路径 pytest（不带 basetemp） | 测试 100% 通过，`exit=1`，stderr `SAFE_DELETE_BULK_CONFIRM_REQUIRED count=2332 threshold=50` |
| E5 | `eval_boolean` 对 9 个 `_ALLOWED_CALLS` 逐一求值 | 9/9 `REJECTED: SOURCE-FORBIDDEN` |
| E6 | `eval_boolean` 对 `snapshot.amount` / `snapshot.status` / `snapshot.amount + 1` 求值 | 全部 `True` |
| E7 | 副本 `labA2`：CRLF 登记表 → `supersede` → `register_declarations` | 旧行原字节保留；12 CRLF 行 + 6 纯 LF 行 |
| E8 | 副本 `labB`：改正典 → `verify()=1` → `supersede("garbage-version","x")` → `verify()=0` | 任意提案号/版本被接受 |
| E9 | 副本 `labC2`：无 DECL 区 → 篡改 `CQ-3.cq.yaml` 288→319 字节 | 摘要 `91ffe5a1…→180f58a5…`，`verify()` 仍 0 |
| E10 | `wiring.wired_paths()` 与 `tests/**/test_*.py` 差集 | 61/73 文件、55/381 函数未布线 |
| E11 | `git diff 16d3114..HEAD -- docs/aos-spec.md` 删除行 | 6 条，均为版本/附录计数/标题 |

外部文献查证：Gruber 1993 / Borst 1997 / Studer et al. 1998 谱系（多来源一致）；Pat Hayes 2007 W3C 邮件自述 histories 术语、Hayes 1985 *Naive Physics I: Ontology for Liquids* 的 `h@t` 切片。

---

## 九、评审人备注

- 本文件为**独立评审产物**，刻意置于 `docs/` 且不纳入冻结域 / 声明域，不触发哈希漂移；是否 `git add` 收编作审计留痕，由项目所有者决定。
- 报告中「三关 / 四道」「395 用例」「61 布线」「7 文件」等数字均为本轮实测或项目权威口径，未采信任何未复核自述。
- 与前轮口径冲突处均已在正文标注（N9 为评审人自纠，§2 的「四项修复」复核为逐条回查而非整体采信）。
- 本轮结论不否定前四轮的修补成果：相反，正因这些修补把边界写清楚了，才使 N1/N2/N4 这类「守卫与被守卫对象之间的代理指标失效」变得可定位。

---

*第五轮独立评议 · 证据优先 · 未修改被评审对象*
