# 09 · 项目结构与开发轨迹：看懂、接上、走通

> **效力**：信息性材料，不产生规范条款；一切 MUST 以 [AOS 规范 v2.0.0](../aos-spec.md) 为准。
> **读者**：刚拿到实例（或模板）、需要回答"这些目录各是干什么的、我要改哪里、按什么顺序走"的开发者。
> **本篇回答三个问题**：① 项目结构怎么看；② 技术指引在哪、怎么查；③ 从 init 到自己领域跑通，标准轨迹是什么。

---

## 1. 结构导读：每个目录为什么在这

一句话总纲：**这个仓库只有四类东西——真源（spec/）、守护真源的机器（src/kernel + interpreter + tools）、真源的证据（tests + config 布线）、以及教人使用它们的文字（docs）。** 你未来的代码只会长在第一类和你自己的业务适配层里。

```
spec/            ★ 真源（TBox）。你要开发 = 主要在这里写。八类声明，
                    注册管线是唯一出口；generated 段能力清单由机器单写（P-5），
                    永远不要手改 config/capabilities.yaml 的生成段。
src/kernel/      守护机器·运行时。submit 唯一写路径（能力→权限→结构→条件→追加）、
                    EventStore 八字段 append-only（filestore.py 给持久化参考实现）、
                    投影重放、探测器、Saga、创世窗口。理解系统"怎么跑"= 读 pipeline.py + store.py。
src/interpreter/ 守护机器·沙箱。规则表达式的合法词汇表在这里（白名单 + 拒绝面）。
src/generated/   真源的代码影子。aos generate 的产物，带 provenance 头，
                    手改会被字节比对拦截——改行为请回 spec/。
src/agents/      AI 接入面。Agent 能力子集 + 同一条管线（无特权通道）。
tools/           守护机器·签发。指纹、哈希、骨架生成、布线、发布闸门、领域说明书。
config/          治理台账。capabilities.yaml=能力清单（对账对象）；
                    verification.yaml=VER↔测试布线（闸门的分组依据）。
tests/           条款的证据。conformance=应然行为；negative=禁止面必拒；
                    golden=历史快照不漂移；genesis=创世窗口；replay=重放确定性；
                    redteam=攻击路径。你新增声明，守卫写在这里。
bootstrap/       〔强〕项人工检查表（模板永不代签）。
docs/            文字层。aos-spec.md 冻结正典（勿改，GOV-2.3）；
                    guide/ 教学；DOMAIN-MANUAL.md 你的领域地图（init 生成）；
                    TEMPLATE-LOCK.md 版本绑定凭证。
```

**判断"该改哪里"的口诀**：改世界 → `spec/` 声明 + 治理晋升；改行为实现 → `src/generated/reducers.py`（效果层）或你自己的适配层；改守护规则 → 你是在用模板造新产品，先读 [03 实现方法](03-implementation.md) 再动手；改 `docs/aos-spec.md` → 不存在这个选项（冻结，走 GOV-3）。

---

## 2. 技术指引怎么查：条款 ID 是唯一的万能键

这套脚手架所有文档、代码注释、测试、报错共享同一套**条款 ID 词汇**（AX/KS/P/INV/BOOT/GOV/VER + T01–T26 术语）。它就是你最重要的导航工具：

| 你遇到 | 你看到 | 去哪查 |
|---|---|---|
| 一个报错 | `RECONCILE-FAILED …（INV-13）` | 正典搜 `INV-13` → 指南 02/03 对应节 → 布线表 `VER-27` 的测试文件 |
| 一个测试名 | `test_conflict_reeval.py` | `config/verification.yaml` 反查 `VER-3 / KS-1.4` |
| 一个声明字段 | `evaluation_budget` | 对象所属模式 `P-2`（正典第 4 部分）+ `R8` 释义 |
| 一句"为什么" | `removal_consequence: F` | 正典附录 B 事故类别——每条约束都有反事实理由 |

三条查询路径永远给出同一答案，因为它们是同一事实的三种索引。这就是"规范轨迹"的实体形态。

---

## 3. 标准开发轨迹：从 init 到你的领域跑通

### 第 0 天：看懂现状（约 30 分钟）

```powershell
python src/cli/main.py bootstrap --stage 0    # 实例自登记
python src/cli/main.py verify                 # 三关全绿 = 你接手的是合规基线
python src/cli/main.py manual                 # 读领域说明书：模板自带的 Contract 域
python src/cli/main.py test                   # 布线全绿
```

### 第 1 步：把你的领域写成声明（在 spec/，或用 draft 通道）

小步走：先一个上下文、一个聚合、2–3 个 Action。两种合法入口：

- **直接写 YAML**（学习期推荐）：仿照 `spec/ontology/actions/ApproveContract.action.yaml` 的八类文件各写一份；
- **需求 DSL → 把关 → 晋升**（生产期必用）：

```powershell
python src/cli/main.py draft my-requirements.txt --name billing
python src/cli/main.py draft promote spec/drafts/draft-billing.yaml --proposal-ref SPEC-2026-001
python src/cli/main.py generate --force       # 声明变了，骨架要显式重生成
python src/cli/main.py verify                 # declared==registered 必须重新全绿
```

> 注意 `generate --force` 不是可选项：promote 改声明后骨架会漂移，漂移状态下测试报 `CodegenDrift`。看到成片的 codegen ERROR，先跑 generate。

### 第 2 步：实现效果层（reducers）

`src/generated/reducers.py` 给出物化骨架；你写纯 reducer（事件 → 状态），纪律：**无 I/O、无时钟、无宿主调用**（KS-3.4 重放纯度，`test_replay_purity` 会抓）。

### 第 3 步：给新域写守卫（这是"符合规范"的证据来源）

至少四件，放进 `tests/conformance/` 与 `tests/negative/`：

1. 正路径：合法提交产生事件，流与版本正确；
2. 拒绝面：未注册动作、缺必填、条件不满足、**角色不交**各自必拒且存储零接触；
3. 重放：你的 reducer 从事件重建投影 = 期望快照；
4. 不变量：构造一个违规场景，断言违规对象走 `RaiseInvariantViolation` 且有修复绑定。

### 第 4 步：接 AI（最小闭环，可直接运行）

```python
# 演示：LLM 位置用 mock（任何模型适配器替换 propose() 即可）
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.projection import Projection
from agents.runtime import AgentRuntime

kernel = Kernel(EventStore(), SessionChannel(), compile_all())
agent = AgentRuntime(kernel, "agent-1", ("contract_steward",))

def propose(context_md: str, request: str) -> tuple[str, dict]:
    """LLM 插槽：输入 = 领域说明书（manual 输出）+ 用户请求；
    输出 = (action_type, params)。概率只提议（AX-2）——这里什么都不保证。"""
    return "ApproveContract", {"contract_id": "C-9", "status": "pending",
                               "amount": 100}

at, params = propose(open("docs/DOMAIN-MANUAL.md", encoding="utf-8").read(),
                     "帮我批准 C-9")
ev = agent.act(at, params)                       # 权限/结构/条件/追加全在管线内强制
sid = kernel.session.append("agent-1", {"intent": "approve C-9"})   # 观测留痕
kernel.record_decision(projection_ref="ContractAggregate",
                       transaction_time=ev.transaction_time,
                       session_ref=sid, principal="agent-1")          # 决策三引用
print(ev.event_type, "->", agent.capabilities())
```

这段代码演示了 AI 融合的全部接线：**说明书进上下文（LLM 知道能提议什么）→ 提议 → 管线把关（LLM 保证不了的一切由机器保证）→ 决策三引用（事后可问"它当时基于什么")**。拒绝反馈同理：捕获 `StructuralRejected/ConditionalRejected` 的 message 回流给模型修正提议——异常类型就是条款的运行时形态，天然可路由。

### 第 5 步：签发

```powershell
python src/cli/main.py test && python src/cli/main.py verify && python src/cli/main.py release
```

---

## 4. 权限模型速览（本轮起的新形态）

Action 声明 `permissions.roles` 后，**任何调用方**（人、服务、Agent）在 `Kernel.submit` 单一写路径上都要出示角色证据：

```python
kernel.submit("ApproveContract", params, "alice", roles=("contract_steward",))
```

- 未出示 / 不相交 → `PermissionDenied`，发生在评估与存储**之前**（零审计污染、零事件）；
- `roles=()` 且 Action 声明了角色 = 无权（fail-closed，不默认放行）；
- 未声明角色的 Action（如创世内建）不受此门——与能力清单语义一致；
- 主体→角色的映射属于平台 authN（T03 在本体之外）：模板强制"出示的证据必须够"，你的 SSO/LDAP 决定"谁真的有"。

---

## 5. 常见卡点对照

| 症状 | 根因 | 出路 |
|---|---|---|
| 成片 codegen ERROR / drift | promote 后没重生成 | `generate --force` |
| `RECONCILE-FAILED` | 手改了 spec/ 或 capabilities 生成段 | 走 draft promote；生成段是单写者（P-5） |
| `NOT-REGISTERED` | 实例没做 BOOT-0 | `bootstrap --stage 0` |
| `PermissionDenied … 出示 ∅` | 调用没带 roles | 出示角色证据（§4） |
| `SOURCE-FORBIDDEN` | 规则表达式起于非法源 | 只允许 `snapshot.` / `principal.`（R2） |
| `FROZEN-TEXT-MUTATED` | 有人动了 docs/aos-spec.md | 恢复正典；规范变更走 GOV-3 |

---

## 6. 延伸阅读

- 结构背后的"为什么"：[02 架构模型](02-architecture.md)
- 每条管线阶段的代码落点：[03 实现方法](03-implementation.md)
- 完整企业落地路径与自建清单：[08 企业应用构建指南](08-enterprise-app-guide.md)
- 内核失败形态可运行版：[07 内核实操](07-kernel-walkthrough.md)
