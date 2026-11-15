# Instance Runbook（BOOT-2/3 工作流脚手架 · 附录 C）

> 本文件是实例侧治理工作流的**脚手架**：模板提供流程位与留档格式，不模拟治理。
> 所有〔强〕项的"已通过"只能来自运行系统上的人工执行（检查表留档）——README 诚实边界。

## BOOT-2 治理工作流（提案 → 生效 → 重跑）

```
提案（SPEC-YYYY-NNN）→ 评审 → 生效（GOV-2026-NNN）→ GOV-4 生效重跑 → 能力清单更新
```

1. **提案**：变更以 `SPEC-YYYY-NNN` 编号；涉及规范文本的走 GOV-3 通道：
   ```
   aos spec version <new-version> --proposal-ref SPEC-YYYY-NNN
   ```
   （append-only：新登记条目取代旧行，`docs/ARTIFACT-REGISTRY.md` 留 superseded-via 记录）
2. **能力声明变更（首选通道：草案闸门）**：需求文本走草案闸门，人确认前不进正典：
   ```
   aos draft requirements.txt --name r1                                  # 解析→编译把关（KS-7.1/P-2/R2）
   aos draft promote spec/drafts/draft-r1.yaml --proposal-ref SPEC-YYYY-NNN   # 晋升（GOV-1 强制提案）
   aos generate                                                          # 声明 → 代码骨架（手改检测）
   ```
   晋升内部执行 `registration.apply_generated()`（P-5 单写者：固定段逐行原样保留，
   生成段唯一写点）；目标已存在 → 拒绝（变更走 GOV-3 版本通道，不覆盖正典）。
   直接手写 `spec/` 声明亦可，但生成段对账（P-5）与草案把关（KS-7.1）同样不可绕过。
3. **生效重跑（GOV-4，强制）**：
   ```python
   from kernel.governance import GovernanceLedger
   GovernanceLedger(store).record_effective("GOV-2026-NNN", "SPEC-YYYY-NNN", principal)
   ```
   重跑失败 → 生效被阻断 + `governance` 类违规对象落 `domain:invariant` 流
   （repair 绑定 GOV-3 通道）——见 `tests/conformance/test_governance_effective.py`。
4. **出库（发布闸门，fail-closed）**：`aos release` —— 三关 + 布线套件 + 骨架
   一致性全绿才出制品，`dist/RELEASE-MANIFEST.json` 随制品落档（VER-27 前置）；
   CI 等价物见 `.github/workflows/ci.yml`。
5. **留档**：提案号、生效号、重跑结果、RELEASE-MANIFEST 入 `#mandatory-records`。

## BOOT-3 Identity Context 验收

| 步骤 | 判据 | 留档 |
|---|---|---|
| 归并史声明 ≥3 组 | `MergeRegistry.declare`（P-8，自归并必拒） | `domain:identity` 流 |
| 双路径重放比对 | 投影引擎 vs 归并注册表终态逐属性一致（VER-24 item1） | 重放记录 |
| 归并史全量重放 | 删除物化 → 全量重放 → 恢复一致 | `tests/replay/` 对照输出 |

## GOV-2.5 分歧二分（分歧出现时先做的判断）

```
工件缺陷（fingerprint FAIL + 哈希一致）→ 修工件 → 重新登记
核对器缺陷（工件在声明序上完好，指纹判据漏抓）→ 修核对器（不动冻结文本）
判据：结构层（指纹）与密码学层（哈希）谁是分歧源 —— 两者矛盾时以上游声明为准
```

## 〔强〕项检查表索引（人工执行，签名留档）

`bootstrap/checklists/`：VER-20 创世闭合 · VER-24 归并重放 · VER-26 投影重建 ·
VER-27 清单完备 · VER-28 基座红队 · VER-29 破窗演练。schema 见 `_schema.yaml`
（P-14：id / check / evidence / judge / signer 五字段，结果随工件哈希入审计）。

## 破窗（GOV-5）与运行时不变量速查

破窗流程 = breakglass_resonant 双记录（立即生效 + 事后评审）→ 限时过期 →
事后评审 Process 被强制创建。运行时不变量 INV-1..13 与禁止行为（forbidden 段）
的机械核对见 `tests/negative/test_forbidden.py`。
