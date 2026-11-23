# 07 · 内核实操：一次可复现的提交生命周期

> 信息性教程。本文所有代码均在**模板根目录**逐行实测，输出中的时间戳统一缩写为 `<ts>`，其余为真实结果。
>
> 前置：`pip install -e .`（安装 `pyyaml` + `pytest`），工作目录为模板根。若你处在 `aos init` 生成的**实例**里，请改用 `python src/cli/main.py ...` 走 CLI；本文的内核 API 示例依赖模板根的 `config/capabilities.yaml` 与 `spec/`，实例中同样存在，但 `ROOT` 解析指向所在目录，因此也可在实例根运行。

## 结论先行

一条提交走完这五步：**装配内核 → 提交 → 拒绝路径 → 版本冲突重求值 → 投影与决策审计**。AOS 与常见 CRUD 代码的最大差别不在"如何成功"，而在**失败时留下什么**：

- 结构失败、条件失败、未注册能力、直写陷阱——四种失败，四种不同的拒绝点；
- 版本冲突不是简单重试追加，而是**整条评估管线重跑**（结构 + 条件各再执行一次）；
- 投影不是权威状态，删除后可从事件流确定性重建；
- 决策必须同时锚定投影半边与会话半边，否则拒绝写入。

---

## 0. 装配：四个对象，一条唯一写路径

```python
import sys
from pathlib import Path
ROOT = Path.cwd()                     # 模板根（或实例根）
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from kernel.registration import compile_all
from kernel.store import EventStore, VersionConflict
from kernel.session import SessionChannel
from kernel.pipeline import Kernel

store   = EventStore()                # append-only 本体事件日志
session = SessionChannel()            # 物理独立的会话事件流
kernel  = Kernel(store, session, compile_all())   # 唯一提交入口

print(sorted(kernel.compiled))        # 注册期五步的产物
print(dict(store.streams))            # 尚未写入
```

实测输出：

```
['ApproveContract', 'RegisterContract', 'VoidContract']
{}
```

**读输出**：`compile_all()` 把 `spec/ontology/actions/*.yaml` 编译成 `CompiledAction`；只有同时出现在 `spec/` 与 `config/capabilities.yaml` 的能力才可执行——这就是 `declared == registered` 双射（KS-7.2 第 5 步）。`store.streams` 为空说明**内核启动不产生治理世界事件**（GOV-1 诚实边界）。

---

## 1. 成功提交：认识事件八字段

```python
from pprint import pprint

R = {"contract_id": "C-1", "amount": 500000}
# 实体先经 RegisterContract 进入权威投影（effects 书写 status=pending，T24）
kernel.submit("RegisterContract", dict(R), "contract_steward",
              roles=("contract_steward",))
# 审批不再自报 status——条件对物化投影求值，状态效果由声明书写进事件
ev = kernel.submit("ApproveContract", {"contract_id": "C-1"}, "contract_steward",
                   roles=("contract_steward",))   # 角色证据必须出示（P-10/INV-4）

print({
    "event_id": ev.event_id,
    "stream_id": ev.stream_id,
    "expected_version": ev.expected_version,
    "event_type": ev.event_type,
    "action_id": ev.action_id,
    "principal": ev.principal,
})
pprint(dict(ev.payload))
```

实测输出（时间字段已缩写）：

```
{'event_id': 2, 'stream_id': 'domain:ContractAggregate',
 'expected_version': 1, 'event_type': 'ApproveContract@1',
 'action_id': 'ApproveContract', 'principal': 'contract_steward'}
{'contract_id': 'C-1', 'status': 'approved', 'valid_time': '<ts>'}
```

`payload['status']` 是 `approved`——不是调用方写的（本次提交根本没有 status 参数），而是声明的 `effects` 由内核书写（T24 副作用执行点）。状态只由事件导出。

**八字段逐项口径**（KS-1.2）：

| 字段 | 来源 | 含义 |
|---|---|---|
| `event_id` | 平台单调分配 | 全局序，投影重放按此排序 |
| `stream_id` | Action 声明的 `aggregate` | `domain:ContractAggregate`；一 Action 一聚合（P-1） |
| `expected_version` | 提交前读取的流长度 | 乐观并发；冲突触发完整重求值 |
| `event_type` | Action + schema 版本 | 必须含 `@1`（KS-5.1），缺版本即 `SCHEMA-FAIL` |
| `payload` | 调用参数 + `valid_time` + 声明效果（T24，内核书写） | `MappingProxyType` 只读，无 update 路径 |
| `transaction_time` | 平台维护 | 调用方不可提供；必须 ≥ `valid_time`（KS-6.1） |
| `action_id` | 提交入口参数 | 必在 `write_actions` 段（INV-13） |
| `principal` | 提交入口参数 | 主体归属；审计可追溯 |

注意：`payload` 里**没有** `transaction_time`——它独立存在 `ev.transaction_time`。把两者混为一谈是常见的双时态建模错误（P-13）。

---

## 2. 四条拒绝路径：失败发生在哪一步

注意"条件失败"一例：§1 已把 C-1 注册并批准（权威投影 `status=approved`，状态由事件导出），此处再自报 `status="pending"` 属**过时谎报**——条件对物化投影求值（P-16），拒绝以 `SNAPSHOT-CONTRADICTION` 形态出现，异常类型仍是 `ConditionalRejected`。

```python
from kernel.errors import (StructuralRejected, ConditionalRejected,
                           UnregisteredAction, DirectWriteForbidden)

cases = [
    ("结构失败", lambda: kernel.submit(
        "ApproveContract", {}, "contract_steward",
        roles=("contract_steward",)),
     StructuralRejected),
    ("条件失败", lambda: kernel.submit(
        "ApproveContract", {"contract_id": "C-1", "status": "pending"},
        "contract_steward", roles=("contract_steward",)),
     ConditionalRejected),
    ("未注册能力", lambda: kernel.submit("NukeEverything", {}, "agent"),
     UnregisteredAction),
    ("直写陷阱", lambda: store.write_raw(stream_id="domain:ContractAggregate"),
     DirectWriteForbidden),
]
for name, fn, exc in cases:
    try:
        fn()
    except exc as e:
        print(f"{name}: REFUSED — {str(e)[:56]}")
print("流长度:", len(store.streams["domain:ContractAggregate"]))
print("条件审计末条结果:", kernel.interpreter_audit[-1]["result"])
```

实测输出：

```
结构失败: REFUSED — STRUCTURAL-FAIL: contract_id 必填（exists）
条件失败: REFUSED — SNAPSHOT-CONTRADICTION: status 自报 pending ≠ 权威投影 approved ——
未注册能力: REFUSED — NukeEverything 未注册 —— 不注册即不可执行（INV-1 / P-1）
直写陷阱: REFUSED — INV-1: 禁止 Action 之外的事件写入路径 —— 已产生 structurally-rejected 
流长度: 2
条件审计末条结果: False
```

**关键判读**：

| 拒绝点 | 异常 | 是否追加 | 审计 |
|---|---|---|---|
| 能力核查 | `UnregisteredAction` / `UnknownAction` | 否 | 无写审计（根本没进存储） |
| 结构校验 | `StructuralRejected` | 否 | 无 interpreter audit（结构先于条件） |
| 条件求值 | `ConditionalRejected`（含 `SNAPSHOT-CONTRADICTION` 改口拦截） | 否 | **有** interpreter audit，`result=False`：矛盾记 `kind=snapshot-contradiction`，正常求值记表达式与快照哈希 |
| 存储流规则 | `StreamRuleViolation` / `StoreRejection` | 否 | store audit 恰一条 `structurally-rejected` |
| 直写绕过 | `DirectWriteForbidden` | 否 | store audit 恰一条 `structurally-rejected` |
| 版本冲突 | `VersionConflict` | 重求值后追加 | 冲突本身不记拒绝审计；成功追加记 `appended` |

`流长度: 2` 证明四条拒绝路径**都没有污染权威状态**——失败不追加（VER-2）。`条件审计末条结果: False` 证明失败也有留痕（KS-3.3）：这正是"可审计"与"只记成功日志"的差别。

> 曾出现过的缺陷：一次版本冲突会记两条 `structurally-rejected`。现已统一到 `store.commit` 的单一拒绝口，实测一次拒绝恰一条审计。守卫见 `tests/conformance/test_integrity.py`。

---

## 3. 版本冲突：整条管线重求值，而不是重试追加

这是最容易被实现错的一环。下面的探针**故意制造一次并发写入**：第一次 `commit` 先真实写入（使流版本前进）再抛 `VersionConflict`，观察结构和条件是否被重新执行。探针用 `RegisterContract` 而非 `ApproveContract`：后者的效果（`status=approved`）会把投影推向终态，重求值轮的条件本就该不过——重求值判据必须落在"两轮条件都为真"的能力上。

```python
import kernel.pipeline as pipeline

orig_struct, orig_bool = pipeline.run_structural, pipeline.eval_boolean
cnt = {"struct": 0, "bool": 0, "commit": 0}

def counted_struct(*a, **k):
    cnt["struct"] += 1
    return orig_struct(*a, **k)

def counted_bool(*a, **k):
    cnt["bool"] += 1
    return orig_bool(*a, **k)

pipeline.run_structural, pipeline.eval_boolean = counted_struct, counted_bool

k2 = Kernel(EventStore(), SessionChannel(), compile_all())
real_commit = k2.store.commit

def racing(*a, **k):
    cnt["commit"] += 1
    if cnt["commit"] == 1:
        real_commit(*a, **k)                    # 对手抢先写入
        raise VersionConflict("simulated concurrent write")
    return real_commit(*a, **k)

k2.store.commit = racing
ev2 = k2.submit("RegisterContract", dict(R), "contract_steward",
                roles=("contract_steward",))

pipeline.run_structural, pipeline.eval_boolean = orig_struct, orig_bool
print("计数:", cnt)
print("追加事件数:", len(k2.store.streams[ev2.stream_id]))
print("store 审计种类:", [a["kind"] for a in k2.store.audit])
```

实测输出：

```
计数: {'struct': 2, 'bool': 2, 'commit': 2}
追加事件数: 2
store 审计种类: ['appended', 'appended']
```

**判据**：`struct=2 / bool=2` 说明结构与条件在冲突后**各重跑一次**；若只改 `expected_version` 重试追加，这里会是 `struct=1 / bool=1`。`commit=2` 与 `追加事件数=2` 对应"对手写入一次 + 本方重求值后写入一次"。`MAX_REEVAL=3` 是有界防爆；超过抛 `BudgetExceeded`（R8 fail-closed）。

> 历史缺陷供对照：旧实现把结构与条件放在循环外，探针结果是 `commit=2, struct=1, bool=0`；原测试只断言 `calls>=2`，测的是"重试"而不是"重求值"。现在两处都已修正并加守卫。

---

## 4. 投影：权威状态的只读视图，可丢弃可重建

```python
from kernel.projection import Projection, ProjectionNotMaterialized, resolve_decision_ref

def reducer(state, event):
    """纯函数：state, event -> state（KS-3.4 重放纯度）。"""
    if event.event_type == "ApproveContract@1":
        state[event.payload["contract_id"]] = "approved"
    return state

proj = Projection(store, "contract_state", reducer,
                  entity_key="contract_id", streams=["domain:ContractAggregate"])
print("重建:", proj.rebuild())
print("快照:", proj.snapshot())

ref = proj.decision_ref()                       # 决策双引用的投影半边
print("投影半边:", {k: v for k, v in ref.items()})
print("可解析:", resolve_decision_ref(store, ref, {"contract_state": proj}))

proj.discard()                                  # VER-26：删除物化
try:
    proj.snapshot()
except ProjectionNotMaterialized as e:
    print("REFUSED:", str(e))
print("再重建:", proj.rebuild())
```

实测输出（`<ts>` 为 `transaction_time`）：

```
重建: {'C-1': 'approved'}
快照: {'C-1': 'approved'}
投影半边: {'projection': 'contract_state', 'transaction_time': '<ts>'}
可解析: True
REFUSED: 投影 contract_state 未物化 —— 调用 rebuild()（P-16 / VER-26）
再重建: {'C-1': 'approved'}
```

**两条硬约束**：

1. 投影**禁止**把会话流作为源（`Projection.__init__` 遇到 `session*` 直接抛 `ProjectionViolation`；`rebuild()` 还做源级排除防御）——AX-3 / KS-2.2 / KS-2.4。
2. 投影只是**决策输入**（P-16），不能反过来当权威状态判断。想改变状态，只能回到 `kernel.submit()`。

---

## 5. 会话与决策：三引用缺一不可

```python
rec = session.append("contract_steward",
                     {"kind": "observation", "text": "reviewed C-1"})
print("会话引用:", rec["ts"], "| exists:", session.exists(rec["ts"]))

d = kernel.record_decision(
    proj.decision_ref()["projection"],          # ① 投影标识
    proj.decision_ref()["transaction_time"],    # ② 投影事务时间
    rec["ts"],                                  # ③ 会话半边
    "contract_steward",
    {"reason": "approved after review"},
)
print("决策事件:", d.event_type, "@", d.stream_id)
print("决策载荷:", {k: v for k, v in d.payload.items() if k != "valid_time"})
```

实测输出：

```
会话引用: <ts> | exists: True
决策事件: Decision@1 @ decision
决策载荷: {'reason': 'approved after review', 'projection_ref': 'contract_state',
           'session_ref': '<ts>', 'transaction_time': '<ts>'}
```

**结构要求**（KS-2.5 / INV-4）：决策事件必须写入 `decision` 流（写别的流 → `StreamRuleViolation`），载荷必须含 `projection_ref` 与 `session_ref`（缺 → `DECISION-REFS-MISSING`），且 `session_ref` 必须能在会话通道中解析（`exists()` 为假 → `DecisionRefIncomplete`）。

这两条"半边"的设计含义是：**决策既不能脱离它依据的系统状态，也不能脱离 Agent 当时的观察上下文**。只记一个 `prompt` 字符串不构成可审计决策。

---

## 6. 审计总账：两个账本，不要混为一谈

```python
from collections import Counter
print("store 审计:", dict(Counter(a["kind"] for a in store.audit)))
print("解释器审计条数:", len(kernel.interpreter_audit))
```

实测输出：

```
store 审计: {'appended': 3, 'structurally-rejected': 1}
解释器审计条数: 3
```

| 账本 | 持有者 | 记录内容 | 覆盖阶段 |
|---|---|---|---|
| `store.audit` | `EventStore` | `appended` / `structurally-rejected`，含 event_id、stream、action、时间 | 存储层：追加、流规则、版本冲突、直写陷阱 |
| `kernel.interpreter_audit` | `Kernel` | 条件表达式、快照哈希、求值结果（失败带 `error`），含版本 | 评估层：每次条件布尔求值（含失败） |

`appended=3` 对应注册、审批与决策三次追加；`structurally-rejected=1` 对应直写陷阱；条件失败**不进** store 审计（它没到存储层），但**进**解释器审计。查问题时先确定要看哪个账本。

---

## 7. 把探针变成守卫测试

教程里的每一步都应能变成测试。模板已有现成范例（`tests/conformance/test_pipeline_order.py`），模式是：

```python
def test_conditional_failure_appends_nothing():
    k, store = _kernel()
    with pytest.raises(ConditionalRejected):
        # C-9 从未注册：权威投影无实体，status 回填为 None，条件不过
        # （新口径：状态自报已无意义——谎报走 SNAPSHOT-CONTRADICTION，见 INTEGRITY-4/5）
        k.submit("ApproveContract", {"contract_id": "C-9", "amount": 1},
                 "contract_steward", roles=("contract_steward",))
    assert "domain:ContractAggregate" not in store.streams       # 失败不追加
    assert k.interpreter_audit[-1]["result"] is False            # 失败也留痕
```

写新守卫时遵守三条：

1. **断言行为，不断言好心情**：拒绝路径要同时断言"抛了正确的异常"与"流未被污染"；
2. **计数要精确到阶段**：冲突重求值断言 `struct == 2 and bool == 2`，不要写 `calls >= 2`；
3. **元数据断言要区分环境**：`ARTIFACT-REGISTRY.md` 只存在于模板根（实例自行登记，init 不复制），实例侧不应硬读——模板已按此原则修正；`pyproject.toml` 自 init 根层完整性修复起随实例复制（依赖与 pytest 配置声明）。

---

## 8. 常见误区与排错

| 现象 | 真正原因 | 正确做法 |
|---|---|---|
| `UnregisteredAction` 但 spec 里明明有这个 Action | 能力清单 `write_actions` 没有它；`declared != registered` | 走 `aos draft promote --proposal-ref` 单写者通道，不要手改 YAML |
| `SCHEMA-FAIL: event_type 须含 schema 版本号` | 直接调 `store.commit` 传了 `Order` 而非 `Order@1` | 用 `kernel.submit()`；它自动拼 `<Action>@1` |
| `VALID-TIME-DOMAIN` | `valid_time` 晚于平台 `transaction_time` | 不要手工伪造未来有效时间；交给管线补 `valid_time` |
| `VersionConflict` 循环到 `BudgetExceeded` | 竞争过热或期望版本一直不刷新 | 让管线重求值；超过 3 轮说明外部写入异常，查写入者而非调大预算 |
| 投影改了但 `snapshot()` 还是旧值 | 投影是物化视图，不会自动跟随事件流 | `discard()` 后 `rebuild()`；或直接重建新 Projection |
| `ProjectionViolation: 会话流禁止进入投影源` | 把 `session` 写进 `streams` 参数 | 会话是观测，不是权威状态；改用带出处的摄取 Action |
| `DecisionRefIncomplete` | session 记录用自定义 id，`exists()` 按 `ts` 匹配 | 用 `session.append()` 返回的 `rec["ts"]` 作为 `session_ref` |
| 在实例里 `aos verify` 校验的却是模板 | 控制台脚本 ROOT 锁在模板根 | 实例内一律 `python src/cli/main.py ...` |

---

## 9. 小结与下一站

- `Kernel.submit()` 是唯一写入口；`EventStore` 只有 `_append`，无 update / delete。
- 四种拒绝路径都不污染权威状态；条件失败仍留解释器审计。
- 版本冲突完整重求值：`struct=2 / bool=2 / commit=2` 是可核对的判据。
- 投影可丢弃重建，禁止包含会话流；决策需要投影 + 会话两个半边。
- `store.audit` 与 `kernel.interpreter_audit` 是两个账本，分别覆盖存储层与评估层。

回到 [05 · 速查手册](05-reference.md) 查命令与条款，或回到 [guide 索引](README.md) 选择下一条学习路径。
