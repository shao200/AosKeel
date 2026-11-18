# AosKeel v2.2.0 投入使用评估与同行评议（第六轮 · 裁决版）

评审对象：HEAD `ecbedc1`（v2.2.0，AOS-ART-004），与 `origin/main` 同步。
前序基线：`e04875f`（第五轮评议）→ `3fa419f`（N1..N7/N10/N11 修复）→ `ecbedc1`（v2.2.0 信息性勘误，ADR-004 / SPEC-2026-003）。
方法：所有门禁与篡改实验在与脏工作区隔离的干净检出上执行（`git clone --local --no-hardlinks`，HEAD `ecbedc1`、0 处改动）；对冻结域与非冻结域分别做副本可证伪实验；结论以实测退出码为准，不以"本地全绿"推断系统一致。

## 0. 裁决（唯一）

**Conditional Go —— 有条件投入使用，不得裸投。**

- **可以投入使用**：单团队可信仓库内的研发、教学、原型验证、内部规范演示；前提是修完 F1（P0）或明确以 `aos release` 为唯一门禁命令，并走完第 6 节的最小登记路径。
- **禁止投入使用**：① 多方互信签署 / 把哈希门当作"防内鬼"的合规证据；② 对外生产环境暴露控制台；③ 宣称已实现形式化本体推理或"规范不可篡改"。
- **判据**：8 维中 3 维达门槛、1 维 P0 未达、2 维在指定场景禁用。工程与密码学层已达标；阻断项集中在标准命令可靠性、治理信任根、运维安全。

## 1. 评估矩阵

| 维度 | 得分 | 门槛 | 判定 | 主要依据 |
|---|---|---|---|---|
| 功能与回归 | 9.5 | 9.0 | 通过 | 404 用例 0 失败；74/74 布线无遗漏、无悬空；生成物零漂移 |
| 密码学完整性 | 9.0 | 8.0 | 通过 | 完整登记实例篡改声明 verify 0→1；init 实例 NOT-REGISTERED；release 拒 SKIP 出制品 |
| 实例上手路径 | 8.5 | 8.0 | 通过（需登记） | init→BOOT-0→DECL→verify→release 实测贯通 |
| 标准命令可靠性 | 6.0 | 9.0 | **P0 必须先修** | `aos test` 74 项全过但退出码 1（F1） |
| 文档一致性 | 7.5 | 9.0 | 待修订 | 两处 v2.1.1 / AOS-ART-003 残留逃过守卫（F2） |
| 治理信任根 | 5.0 | 8.0 | 多方场景禁用 | 两文件自签即可让门重新变绿（F3） |
| 理论宣称强度 | 7.0 | 8.0 | 维持 minor revision | R.5 欠账仍登记；S.4 计步为结构恒等式（F4） |
| 运维安全 | 6.0 | 8.0 | 对外生产禁用 | 控制台无认证（已披露），须前置网关 |

## 2. 门禁实测（干净检出 `ecbedc1`）

| 门禁 | 结果 |
|---|---|
| 全量 pytest | 404 collected，进度 100% 全点，0 失败 / 0 错误，退出码 0 |
| `aos verify` | `VERIFY-OK`（无 SKIP）；正典 `fff3d7e7…`、声明 `91ffe5a1…`，28 份声明 |
| `tools/fingerprint.py` | `FINGERPRINT-OK` 十节三元组在场 |
| `aos test` | 选中 74 / 可执行 74 / 缺失 0，**退出码 1**（见 F1） |
| `aos cq run` | 10/10 通过 |
| `aos release` | 五步全 PASS：structural / cryptographic（双比对）/ registered / tests 74 / codegen 7 文件 |
| `aos generate --force` | 7 文件生成物字节级零漂移 |
| 发布后工作区 | 仅 `dist/RELEASE-MANIFEST.json` 的 `released_at` 变化（F5） |

已明确**不算缺陷**的诚实披露：`〔强〕项未布线 1` 源于 `tools/wiring.py:43`（无 path 的人工检查表项）；`invariants: gate false` 源于 `config/verification.yaml:11`（该套件无测试文件）；15:59 观测到的工作区瞬时回退在 16:02 已自愈，评审结束源仓库 `git status` 干净。

## 3. 第五轮 11 项发现逐条复核

| 编号 | 结论 | 证据 |
|---|---|---|
| N1 谓词强转 | **闭合** | `boolean_profile.py` 增 `NON-BOOLEAN-PREDICATE`；实测裸数值/字符串/算术/列表 4 例全 REJECTED，合法谓词正常 |
| N2 白名单假命题 | **闭合** | `_lint` 把 `Call.func` 排除出 R2 根集合；9 个白名单函数按各自合法参数实测 9/9 可求值 |
| N3 第四道 SKIP | **闭合（有边界）** | CLI 打 `VERIFY-OK-WITH-SKIP`；`release_gate._crypto_step` 实测 REFUSED；完整登记实例篡改声明 verify 0→1 |
| N4 布线覆盖 | **闭合** | 74 布线 / 74 测试文件，未布线 0、悬空 0；INTEGRITY-30..42 补登 |
| N5 嵌套 pytest 不可诊断 | **半闭合** | release 内嵌路径已修（独立 basetemp + stderr 尾段）；`aos test` 未修（F1） |
| N6 任意提案号 | **闭合（格式层）** | `garbage-version` / `x` 均 REFUSED；`SPEC-2026-999` 接受——外部锚仍缺（F3） |
| N7 CRLF 字节对称 | **闭合** | CRLF 副本 ART+DECL 双路径写入后：CRLF 20 行 / 纯 LF 0 行 |
| N8 S.4 证明勘误 | **闭合** | 上界改为 `1+steps(e1)+steps(e2)`，结论不变；机器核对升级（但强度见 F4） |
| N9 R.2 术语归属 | **闭合** | Hayes histories / `h@t`，state 归 Galton 一侧；R.6 文献 ×12，抽查 [07] 卷期页码准确 |
| N10 文档口径 | **部分闭合** | 根 README / config / 指纹清单已同步；docs/README.md 与 guide/03 残留（F2） |
| N11 无认证披露 | **闭合** | README.md:287、docs/README.zh-CN.md:292 双语披露 |

GOV-3 流程：ADR-004 具备提案模板、备选否决、后果、回退、文献查证清单，`AOS-ART-004` 入表且旧行逐字保留，语义零变更成立。ADR 声称的"用户明确授权"属仓库外授权、按设计不在仓库内留痕，故仓库内不可自证——列为注记，不作缺陷认定。

## 4. 本轮新发现

**F1（P0，阻断标准命令）**：`aos test` 退出码 1，尽管 74 项全点通过。
证据：`src/cli/main.py:360` 为 `subprocess.call([... "pytest", "-q"] + paths, cwd=ROOT)`，未加 `--basetemp`；`tools/release_gate.py:39-43` 已用 `tempfile.mkdtemp` + 独立 basetemp 修好内嵌路径。实测 `AOS_TEST_EXIT=1`，宿主 safe-delete 报 `count:2524, threshold:50` 拦截 pytest 临时目录清理；同一环境直接跑 `pytest --basetemp=<仓库外>` 退出码 0，坐实根因是清理钩子而非测试失败。
影响：README / guide 的标准命令在本次评测环境下返回失败，CI 会判红；`aos release` 与全量 pytest 却是绿的，形成"同一套件、两条路径、两种结论"。
代价与修法：把 release_gate 的 basetemp 逻辑抽到共用处供 `cmd_test` 复用（约 10 行，非冻结域，不触发 GOV-3）。

**F2（P1，文档可信度）**：v2.2.0 下游口径漏两处，且守卫未覆盖。
`docs/README.md:97` 仍写 `canonical spec v2.1.1`，与根 `README.md` 的 v2.2.0 冲突；`docs/guide/03-implementation.md:77` 示例仍写 `spec_ref: AOS-ART-003`，与 `config/capabilities.yaml` 实际的 `AOS-ART-004` 冲突（用户照抄示例得到错误登记引用）。`tests/conformance/test_doc_consistency.py:184` 只断言两个 config 的 `spec_ref`，未覆盖这两处。修法：同步两行 + 补守卫，零语义成本。

**F3（P1，治理信任根）**：登记表无外部锚，规范可被自签改写。
副本实验：完整登记实例改正典 → `verify()=1`；执行 `supersede("v9.9.9","SPEC-2026-999")`（格式合法、无任何外部核验）→ `verify()=0`，全部门禁重新变绿。N6 只做格式收口，`tools/hash_spec.py` 注释亦写明"外部锚（git tag / 签名）属部署侧职责，另行落地"。
结论：密码学门证明的是"字节未被无意改动"，**不证明"规范未被有权者改写"**。单团队可信仓库够用；多方互签场景必须禁用或先补外部锚。补锚会改 `supersede` 的信任模型，属模型变更，须走 ADR→提案→gates→regression，权限在仓库之外。

**F4（P2，宣称强度）**：S.4 机器核对的证明对象需收窄。
样例空间实测 612 条（提交说明"约 570"、测试 docstring"数千条"，三处口径不一）。612/612 样例的参考步数恰好等于 `BoolOp+UnaryOp+Compare` 结构节点计数，`steps ≤ |nodes|` 在该计步定义下是结构恒等式（最大差值 30 来自叶节点），并非实现 `eval_boolean` 的真实执行成本。建议仅在 README / 评审记录中把"真实计步"表述为"参考语义下的归纳证明自洽"；附录 S 属冻结正典，改字须再开 GOV-3，不建议为此单独开版本。

**F5（P2）**：`dist/RELEASE-MANIFEST.json` 把 `released_at` 纳入 tracked 文件，每次 `aos release` 必然使工作区变脏（diff 仅时间戳）。"字节级零漂移"实际只覆盖 `src/generated/` 7 文件。建议 CI 显式忽略该文件，或把时间戳移出受控工件。

**F6（P2，可用性）**：`bootstrap --stage 0` 输出 `VERIFY-OK-WITH-SKIP` 与 `BOOT-0-DONE`，实例 README 的"下一步"只到 BOOT-0；DECL 登记需用户从 CLI 括号提示中自行发现。CLI 已给出 `aos spec register-declarations`，不构成阻断，但建议把两步写进实例 README 的连续步骤。

## 5. 放行条件 / 退出条件

放行（可检查、逐条验收）：
1. `aos test` 退出码 0（F1 修完复测），或项目文档明确 `aos release` 为唯一门禁命令并停用 `aos test`；
2. 每次出制品前 `aos verify` 输出必须是 `VERIFY-OK`，出现 `VERIFY-OK-WITH-SKIP` 即不得出制品；
3. 登记表挂仓库外锚（git tag / 签名 / 只写一次存储），否则不得作为多方合规证据；
4. 对外部署时控制台置于认证网关之后；
5. F2 两处口径同步并补守卫。

升为完全 Go 的退出条件：1–5 全部满足 + 外部锚方案验收 + 控制台认证方案验收 + R.5 理论欠账收敛或明确列入产品边界说明。

不予通过项（不得对外宣称）：规范不可篡改；已实现形式化本体推理 / 开放世界自动推理；控制台已具备身份鉴别；附录 R/S 产生 MUST 义务。

## 6. 最小可投入使用路径（本轮实测贯通）

```
aos init <dir>
cd <dir>
python src/cli/main.py bootstrap --stage 0
python src/cli/main.py spec register-declarations v2.2.0
python src/cli/main.py verify      # 必须是 VERIFY-OK，不能带 -WITH-SKIP
python src/cli/main.py release     # 五步 PASS，产出 dist/RELEASE-MANIFEST.json
```

实测记录：init 产出 205 文件且按 GOV-2.3 故意不复制登记表；首次 verify 为 `NOT-REGISTERED`（正确 fail-closed）；BOOT-0 后 `VERIFY-OK-WITH-SKIP`；DECL 登记后 `VERIFY-OK` 且声明摘要双比对通过。三形态副本实验另证：init 原样篡改正典仍被拒；BOOT-0 后篡改业务声明不被密码学门发现，但 release 的 cryptographic 步拒出制品；完整登记实例篡改声明 `verify()=1`。

## 7. 代价清单

| 动作 | 代价 | 通道 |
|---|---|---|
| F1 / F2 | 非冻结域、零语义成本；需重跑全量回归 + release（约 5 分钟） | 即修 |
| F5 / F6 | 文档与 CI 配置级，零语义成本 | 即修 |
| F3 外部锚 | 改 `supersede` 信任模型，需引入签名/tag 校验与部署侧凭据管理 | 模型变更：ADR→提案→gates→regression，权限在仓库之外，待授权 |
| F4 收窄措辞 | 若改冻结附录 S，须再开 v2.3.0 GOV-3；建议只在非冻结文档收窄 | 建议不单独开版本 |
| 控制台认证 | 反向代理/网关层，仓库零改动，但增加运维面与配置审计 | 部署侧 |

## 8. 评审边界

本轮未改动任何被评审文件；所有门禁、篡改实验均在隔离干净检出与临时副本中执行。评审结束时源仓库 `git status` 干净、`HEAD == origin/main == ecbedc1`。未执行 GOV-3、未 pull / push、未替用户做对外承诺。本报告为新增独立产物，是否收编由项目所有者决定。
