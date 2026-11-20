# ADR-005：实体主动性触发器调度点（提案）

- 状态：**Proposed（提案，未获授权，不执行）**
- 日期：2026-11-20
- 决策者：项目所有者（模型变更授权保留在仓库之外；本文件不构成授权）
- 关联决策：无前序 ADR 依赖；技术上承接 `docs/DESIGN-management-domain.md` §8.4 的双向主动性设计
- 关联实现（现状，信息性参考模块）：`src/kernel/initiative.py`（`run` 事找人 / `seek` 人找事）、
  `src/kernel/capability_ledger.py`（能力账簿）、`src/kernel/stewardship.py`（管理域 V）
- 变更性质：**内核运行时行为变更**（新增调度层 + `Projection.rebuild` opt-in 通知点），
  不触冻结正典条款、不触 spec 九类声明、不触能力清单。仍须按 ADR→PR→gates→regression
  走完整流程，且经项目所有者仓库外明确授权方可执行。

## 上下文

`initiative.py` 已把双向主动性做成可跑闭环：`run()`（事找人）与 `seek()`（人找事）都读
权威投影、都基于同一本能力账簿、都写 `SessionChannel` 观察通道。但两者目前**只能由外部
手动调用**——没有机制决定"何时调用"。回查确认项目当前不存在任何调度设施：

| 候选挂点 | 现状 | 是否可用 |
|---|---|---|
| `EventStore.commit`（`store.py:79`） | 纯追加，无订阅/回调/观察者 | 否（需新增） |
| `Kernel.submit`（`pipeline.py:60`） | 写路径，成功即返回事件，无成功后钩子 | 否（需新增，且碰敏感区） |
| `Projection.rebuild()`（`projection.py:30`） | 手动调用，无完成通知 | 部分（可加 opt-in 通知） |
| CLI（`cli/main.py`） | 仅 `verify`/`init`/`bootstrap`/`test` 四条命令 | 否（需新增 `drive` 命令） |

因此"实体主动性真正自主跑起来"缺的不是匹配逻辑（已具备），而是**触发器调度点**：回答
"哪个事件发生后、由谁、按什么顺序调用 `run`/`seek`，且重复调用不产生重复意向"。

约束（不可谈判，沿用既有红线）：
1. 不碰写路径语义：`Kernel.submit` 仍是唯一写路径（INV-1），调度器不得调用或绕开它。
2. 不污染权威投影：调度器只写 `SessionChannel`，投影源级排除 session（KS-2.2）。
3. 逐条主体归属：意向消息 principal 为实体 id（事找人）或人/Agent id（人找事）（KS-2.3）。
4. 失败隔离：调度失败不得影响触发它的主流程（写路径或投影重建）的结果。
5. 幂等：同一 `(实体, 触发规则, 目标)` 重复驱动不得产生重复意向。

## 决策（提议）

采用**方案 1：观察侧信号驱动 + 方案 3 的显式 `drive()` 入口并存**。核心是一个独立的
观察侧调度组件 `InitiativeDriver`，通过 **opt-in 通知**subscribe `Projection.rebuild()`
的完成事件；收到通知后对已注册的触发规则跑双向判定。`drive()` 作为公开入口保留，供
CLI/定时/manual 调用——信号驱动负责"自主"，`drive()` 负责"可控与可测"。

### 组件与职责

| 组件 | 落点 | 职责 | 写权限 |
|---|---|---|---|
| `InitiativeDriver` | 新模块 `src/kernel/driver.py` | 注册触发规则；收通知或直接 `drive()`；按 (V, 账簿 E) 过滤；写意向 | 仅 `SessionChannel` |
| 投影通知 | `Projection` 加 opt-in 信号注册（`rebuild()` 末尾 emit） | 通知"权威快照已更新" | 无（只读快照推广） |
| 去重索引 | `SessionChannel` 读侧（审计已有 `read_all`） | 按复合键过滤重复意向 | 无 |

### 算法（步骤固定，可测）

```
drive(projection_name, *, entity_ids=None):
    snap = projection.snapshot()                        # 只读；未物化 → fail-closed
    for rule in registered_rules:                      # 声明式触发规则（Trigger + 候选/供给）
        for entity in (entity_ids or snap.keys()):
            if not rule.predicate(snap, entity): continue # 逐实体判定（双参谓词，与 initiative.Trigger.fires 对齐）
            for kind in (demand, supply):               # 双向对称
                intents = engine.run/seek(...)
                for intent in intents:
                    key = (kind, intent.entity, intent.action,
                           intent.trigger, intent.to_role or intent.principal)
                    if key in seen: continue            # 幂等：读 session 建 seen 集
                    session.append(principal, intent)   # 唯一写入
                    seen.add(key)
```

### 关键设计点

1. **通知而非回调进写路径**：`Projection.rebuild()` 在末尾 emit 通知；调度器是订阅者。
   `submit`/`store.commit` 完全不改，切断"写路径→调度"的耦合。
2. **opt-in 注册**：通知默认关闭（`Projection` 持空订阅表），只有显式注册的投影实例在
   rebuild 后广播。现有所有 rebuild 调用（CQ 夹具、测试、materialize）行为零变化。
3. **失败隔离**：调度器用 try/except 包裹每次 `drive()`；异常写一条
   `kind=initiative.scheduler.error` 到 session，不向 emit 方抛出。
4. **幂等键**：复合键含 `kind`（区分事找人/人找事），避免两个方向的意向互相误判为重复。
5. **不自动认领**：调度器只产生 invitation/notice/offer；人/Agent 认领后仍走 `submit`，
   门控照旧。offer 不是执行。

## GOV-3 提案模板回执（预留，未提交）

```
proposal_id: SPEC-2026-00X          # 授权后按登记表分配，本提案不预占号
proposer: 项目所有者（须仓库外明确授权）
base_spec_id: AOS-ART-004           # 当前最新登记行
schema_objects_affected: []         # 不触九类声明
axiom_or_invariant_touched: none    # 不触正典 MUST / INV
base_layer_touched: no
kernel_runtime_touched: yes         # 新增 driver 模块 + Projection opt-in 通知点
affected_existing_deployments: []   # 默认 opt-in 关闭，现有部署零行为变化
migration_path:
  data: n/a
  event_upcasting: n/a
golden_test_required: yes           # 调度幂等 / 失败隔离需 golden 覆盖
dry_run_simulation_required: yes    # 通知驱动 vs 显式 drive 两条路径需对拍
```

## 备选（否决）

| 方案 | 做法 | 否决理由（可量化） |
|---|---|---|
| **写路径钩子**（commit 后 emit） | `Kernel.submit` 成功后广播 `event.committed` | ① 判定读 `snapshot`，而提交后投影**尚未重建**——读到旧状态，判定必然滞后；要么强制同步重建（把投影成本压进写路径），要么接受一次错误判定。② 碰 INV-1 敏感区，钩子异常隔离复杂。代价高于收益。 |
| **纯显式 tick**（仅 CLI/定时器调 `drive()`） | 不碰内核，外部循环调用 | 零内核变更是真优点，但调度责任全在外部——不是"自主"，每次新部署都要重接定时器。保留为 `drive()` 入口（方案 1 已含），但**不作为唯一方案**。 |
| **外部消息总线 / MQ** | 事件投递到 Kafka/RabbitMQ 由 worker 消费 | 项目定位是进程内参考实现；引入分布式一致性、顺序、重试语义，是为解决本可由进程内信号解决的问题付分布式复杂度。明确不做（与 §8 边界一致）。 |
| **轮询全投影** | 定时扫描全部实体跑判定 | 无事件即时性；O(实体 × 规则 × 角色) 全表开销，且仍需决定"何时扫"——没有回答调度点问题，只是把它藏进定时器。 |

## 后果

**正面**：双向主动性从"手动调用"变为"事件到达即判定"；调度责任收敛到一个可测组件；
写路径与投影语义零变化（opt-in 默认关闭）；幂等与失败隔离有明确判据。

**负面 / 诚实边界（代价必须说清）**：
- **零成本的假象不存在**：通知驱动把判定开销压进 `Projection.rebuild()` 的调用尾部。
  每次重建多跑 O(规则 × 实体 × 可见角色)。进程内参考实现规模可接受，但不等于免费。
- **进程内内存态**：订阅表与 `seen` 去重集均为进程内状态，重启需重新注册、去重集重建；
  与项目"内存态内核参考实现"定位一致，不宣称跨节点持久调度。
- **通知是同步的**：emit 在 rebuild 调用栈内执行。虽失败被隔离，仍占用调用时长；若未来
  需要异步，须另开提案，本提案不引入线程或队列。
- **幂等依赖读 session**：`seen` 集来自 `session.read_all()` 全表扫描；规模上来需索引，
  参考实现阶段接受此上限，不提前优化。
- **不是运行时能力**：即便批准，仍停在观察侧（意向消息），不自动认领、不改权威状态；
  真正"实体自治"需再解决认领回写，属更远的模型变更。

## 合规与回退

- 流程（授权后）：本提案 → 项目所有者仓库外授权 → GOV-3 提案（分配 `SPEC-2026-00X`）→
  PR（新增 `driver.py` + `Projection` opt-in 通知 + CLI `drive` 命令）→ gates
  （`spec fingerprint` + `verify` 四道 + 生成物一致性）→ regression（全量 pytest + doc
  + codegen + wiring 守卫）。
- 回退：本文件状态保持 Proposed 即"未执行"；若执行后需回退，opt-in 通知默认关闭即可
  使全部现有行为复原（新增模块留在仓库但不被注册）。不删除任何历史文件（append-only 纪律）。
- **本提案当前不改变任何源码、正典、spec、能力清单或配置**；仅此一份 Proposed 文档。
