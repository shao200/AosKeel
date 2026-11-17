# LLM-in-the-loop 端到端实战样例

> 信息性样例，不是规范条款。效力以 [aos-spec.md](../../aos-spec.md) 与源码为准。

本目录把 AosKeel 的核心主张——**AI 只提候选，闸门机械唯一**——变成三条可一眼验证的命令行证据。全部可离线运行（零 LLM 密钥、零网络），适配器默认用确定性 stub；接真实 LLM 只需替换 `llm_extractor.py` 的 `generate_candidates()`，其余链路一字不改。

## 三件事，三条证据

| # | 演示 | 命令 | 你应看到的 |
|---|---|---|---|
| 1 | LLM 候选过闸成为草案 | `aos extract <material> --name ledger --extractor llm_extractor.py` | `EXTRACT-DRAFT` + `候选不是事实` |
| 2 | 草案晋升需治理提案 | `aos draft promote ... --proposal-ref SPEC-...` | 无 ref → 拒绝；有 ref → `PROMOTED` |
| 3 | AI 直写正典被拒 | `python gate_rejection_demo.py` | `REFUSED: INV-1` + 审计 `structurally-rejected` |

第 3 条是全套的关键：**即使给出一段"看起来像 LLM 输出"的事件载荷，绕过 Action 直写存储仍被内核拒绝，并留下审计**。权限、结构、条件、单写者四道机械闸与候选来自规则还是 LLM 完全无关。

## 一键复现

```powershell
# 在模板根（有 docs/spec/config 的源码树）执行：
python docs/samples/llm/run_demo.py
```

脚本会在临时目录 `aos init` 一个干净实例，依次跑：BOOT-0 → 适配器 extract → promote（含无提案拒绝反例）→ 内核直写反例 → 声明摘要登记 → CQ-10 复验，并对每一步的预期字样做断言。任一步不符合预期即非零退出（fail-closed），不伪装成通过。

> 说明：`run_demo.py` 验证范围限定为「模板根权威门禁 + 实例内契约行为」。干净实例的 `test` / `release` 全套因实例裁剪（实例 README 口径、DOMAIN-MANUAL 生成时机）存在与模板根不同的既有失败，这属于 [04 教程](../../guide/04-tutorial.md) 声明的实例侧治理边界，与本样例的"闸门与来源无关"主张无关，脚本不声称它们全绿。

## 适配器契约（接真实 LLM 的唯一接口）

`tools/semantic_extract._custom_extract` 调用约定：

- 输入：`argv[1]` = 素材文件路径
- 输出：stdout 一个 YAML —— `{objects: [{object_type, identity, properties: {name: type}}]}`
- 失败：非零退出码 → `EXTRACTOR-FAILED`（fail-closed）

无论提取器是确定性规则还是 LLM，产物都是草案、都过同一三段闸、晋升都必须 GOV-1 提案。参考提取器只产结构层候选，行为层（action）如实留空，不编造。
