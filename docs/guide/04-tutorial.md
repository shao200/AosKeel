# 04 · 实操教程：从安装到发布的全流程

> 信息性文档。下列命令与输出在 v0.3.0 源码树上**实测复现**过（含实例侧完整流程）。

## 结论先行

最短可用路径只有六步，且顺序不可换：

```
pip install -e .  →  aos verify  →  aos init <dir>
    → 实例内 BOOT-0 登记  →  建模/草案/晋升  →  generate → test → release
```

**两条最容易踩的事实**：

1. `aos` 控制台脚本来自模板源码树的 editable 安装，其 `ROOT` 锁定在**模板根**。进入实例后必须用 `python src/cli/main.py ...`，否则校验/发布操作的还是模板，不是实例。
2. 实例首次 `verify` / `release` 会报 `NOT-REGISTERED`——这是**正确行为**：`aos init` 故意不复制 `docs/ARTIFACT-REGISTRY.md`（实例须自行登记，GOV-2.3）。先做 `bootstrap --stage 0`。

---

## 0. 前置条件与安装

```powershell
cd D:\Vsproject\AosKeel
pip install -e .                    # 安装 pyyaml + pytest（均为声明的运行时依赖）
aos verify                          # 三关自检
aos test                            # 布线套件自检
```

预期输出（截取）：

```
VERIFY-OK: 三关连续通过 —— 结构 / 密码学 / 注册
套件 gate: {...} ｜ 选中 60 项，可执行 60，缺失 0，〔强〕项未布线 1
```

若 `aos` 报 `TypeError: main() missing 1 required positional argument: 'argv'`：依赖了旧版入口，重装 `pip install -e .`。
若报 `PYTEST-MISSING`：同样是依赖未刷新，重装即可（该错误是 fail-closed 提示，不是套件失败）。

---

## 1. 实例化（aos init）

```powershell
aos init my-org-system
cd my-org-system
```

预期：

```
INITIALIZED: ...\my-org-system（128 文件；TEMPLATE-LOCK: template 0.3 × v2.1.1 × AOS-ART-003）
下一步: cd 实例 && python src/cli/main.py bootstrap --stage 0
```

实例携带：九类声明样例、源码、测试（含 `tests/README.md` 测试组织与新增契约）、工具、布线配置、指南（`docs/guide/`，含 09 结构与开发轨迹）、CI 模板、根层文件（`.gitattributes` 的 `* -text` 字节精确防线、`.gitignore`、`pyproject.toml` 依赖声明）、生成的实例 README（首屏指向 BOOT-0 与 `docs/DOMAIN-MANUAL.md`）、`TEMPLATE-LOCK`（版本绑定）、`docs/DOMAIN-MANUAL.md`（init 从实例 spec/ 生成的领域说明书）。**不携带**：`ARTIFACT-REGISTRY.md`（自行登记）、`TEMPLATE-LOCK.md` 原稿（由 init 写入）、模板 README（描述模板自身，实例 README 由 init 生成）、`REVIEW-*` 作者本地文档、模板侧 DOMAIN-MANUAL 拷贝（派生件一律实例侧重生成）。

因此后续所有实例内命令用：

```powershell
python src/cli/main.py <command>
```

---

## 2. BOOT-0：登记与首跑（必须先做）

```powershell
python src/cli/main.py bootstrap --stage 0 --dry-run    # 只看检查表，不写入
python src/cli/main.py bootstrap --stage 0              # 真正登记
python src/cli/main.py verify                           # 三关首跑
```

预期（真实输出）：

```
DRY-RUN: 检查表 —— 指纹 PASS ｜ 登记 已有（幂等重跑，无写入）
[1/3] 结构层（指纹 GOV-2.4）
  OK —— 附录 F 十节三元组在场
[2/3] 密码学层（分离式哈希 GOV-2.3）
OK       computed sha256:18868adfa7dba890…
[3/3] 注册层（declared == registered，KS-7.2 / INV-13）
  OK —— 7 条能力一致（含 provenance 回溯）
VERIFY-OK: 三关连续通过 —— 结构 / 密码学 / 注册
BOOT-0-DONE: 内核部署 + 能力清单发布 + 工件哈希登记（附录 E 激活）
```

若跳过此步直接 `verify`，会得到 `NOT-REGISTERED: 先执行 aos register（BOOT-0）`——按提示回去做 BOOT-0。

---

## 3. 读懂九类声明（建模前必看）

| 声明 | 实例路径 | 你要回答的问题 |
|---|---|---|
| Object | `spec/ontology/objects/Contract.object.yaml` | 有哪些对象类型、标识是什么、哪些属性参与决策 |
| Link | `spec/ontology/links/same_as.link.yaml` | 跨上下文链接是否零属性、遍历透明、无 Action 绑定 |
| Action | `spec/ontology/actions/*.action.yaml` | 参数、结构/条件 SC、副作用（effects）、权限、审计、补偿 |
| Context | `spec/contexts/ContractContext.context.yaml` | 通用语言、steward、投影延迟预算 |
| Aggregate | `spec/aggregates/ContractAggregate.aggregate.yaml` | 聚合根、事件流、求值预算、不变量列表 |
| Invariant | `spec/invariants/NoOrphanContract.invariant.yaml` | 声明 + 违规语义 + 修复绑定（三元组缺一不可） |
| Mapping | `spec/mappings/CRMContract.mapping.yaml` | 字段映射、语义损耗声明、golden 钩子 |
| Process | `spec/processes/ContractRenewal.process.yaml` | 跨聚合步骤、幂等补偿 |
| Governance | `spec/governance/ContractDutyMatrix.governance.yaml` | 谁的岗位可以执行哪个动作、在什么条件下（职责授权矩阵） |

**最小可运行域**：一个 Object + 一个 Aggregate + 一个 Action + 一个 Context；其余五类可在真实需求出现时再补（但注册管线对"存在的文件"全量校验，写了就得合规）。

---

## 4. 建模一个 Action：唯一合法通道

> **不要直接手改 `spec/ontology/actions/*.yaml` 然后跑 `verify`**——会命中 `RECONCILE-FAILED: declared != registered`。原因：`config/capabilities.yaml` 生成段由 P-5 单写者维护，只有 `aos draft promote` 会同步它。手工改声明 = 绕过治理。

### 4.1 写需求 DSL

输入格式见 `docs/samples/requirements-sample.txt`；核心语法：`对象:/动作:/聚合体:` 开块，块内缩进键。

```text
聚合体: OrderAggregate
  流: domain:OrderAggregate
  预算: 10000

对象: Order
  标识: order_id
  属性: status, total, customer_ref

动作: CreateOrder
  聚合: OrderAggregate
  参数: order_id(必填), total(选填)
  结构: exists order_id
  条件: snapshot.status == 'open'
```

### 4.2 草案（确定性解析 + 编译把关）

```powershell
python src/cli/main.py draft docs/samples/requirements-sample.txt --name order
```

预期：`DRAFT-OK: ...\spec\drafts\draft-order.yaml（人确认后执行 aos draft promote）`。
编译不过时逐条 `[FAIL]` 报告，且**不落盘**——编译把关在写文件之前。

### 4.3 晋升正典（治理提案强制）

```powershell
python src/cli/main.py draft promote spec/drafts/draft-order.yaml --proposal-ref SPEC-2026-099
```

预期：

```
PROMOTED: ['Order.object.yaml', 'OrderAggregate.aggregate.yaml', 'CreateOrder.action.yaml']
          ｜ capabilities=6 ｜ provenance=SPEC-2026-099
```

`--proposal-ref` 缺失或不以 `SPEC-` 开头 → 拒绝（GOV-1：模板只记录治理结果，不合成提案）。目标声明已存在 → 拒绝（不覆盖正典）。晋升内含 `apply_generated()`——能力清单在此刻同步，随后 `verify` 必然通过。

---

## 5. 生成代码骨架

```powershell
python src/cli/main.py generate            # 首次
python src/cli/main.py generate --force    # promote 改了声明之后
```

在晋升过声明的实例里，第一次 `generate` 可能报：

```
CODEGEN-DRIFT-REFUSED: 生成物与手改内容不一致（字节级）: ['actions.py', 'reducers.py']
—— 禁止静默覆盖；确认后执行 aos generate --force（正常路径：先改 spec/ 声明再生成）
```

这是**正确的保护**：先改声明、再用 `--force` 确认覆盖，正是规范路径。`--force` 后输出：

```
GENERATED: ['__init__.py', 'actions.py', 'reducers.py']
｜ actions: ['ApproveContract', 'CreateOrder', 'RegisterContract', 'VoidContract'] ｜ objects: ['Contract', 'Order']
```

生成物带 provenance 头；声明外字段进入 `_undeclared`，漂移可见。

---

## 6. 运行内核：提交、拒绝与审计

在实例根目录用同一解释器写一段校验脚本（例如 `build/smoke.py`）：

```python
import sys
from pathlib import Path
sys.path.insert(0, ".")
sys.path.insert(0, "src")

from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import StructuralRejected, ConditionalRejected, UnregisteredAction

k = Kernel(EventStore(), SessionChannel(), compile_all())

# 实体进入权威投影：RegisterContract，effects 书写 status=pending（T24）
k.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000},
         "alice", roles=("contract_steward",))

# 成功：权限（角色证据）→ 结构 → 条件（物化投影）→ 追加（载荷带声明效果）
ev = k.submit("ApproveContract", {"contract_id": "C-1"},
              "alice", roles=("contract_steward",))
print("APPENDED:", ev.stream_id, ev.action_id, ev.payload["status"],
      ev.payload["valid_time"] <= ev.transaction_time)   # approved True

# 结构失败：缺 contract_id，绝不进条件、绝不追加
try:
    k.submit("ApproveContract", {},
             "alice", roles=("contract_steward",))
except StructuralRejected as e:
    print("STRUCTURAL:", e)

# 条件失败：C-2 未注册，权威投影无 status → 条件不过，不追加，但审计留痕
# （状态不再由调用方自报——谎报进不了条件，改口走 SNAPSHOT-CONTRADICTION）
try:
    k.submit("ApproveContract", {"contract_id": "C-2", "amount": 1},
             "alice", roles=("contract_steward",))
except ConditionalRejected as e:
    print("CONDITIONAL:", e)
print("AUDIT:", k.interpreter_audit[-1])   # 含版本、快照哈希、result=False

# 未注册能力：拒绝（INV-1 / INV-13）
try:
    k.submit("MagicAction", {}, "contract_steward")
except UnregisteredAction as e:
    print("UNREGISTERED:", e)
```

可核对的判据：

| 场景 | 事件是否追加 | 审计 |
|---|---|---|
| 成功 | 是，`stream_id = domain:ContractAggregate` | 条件评估留档 `result=True` |
| 结构失败 | 否 | 不进解释器 |
| 条件失败 | 否 | 留档 `result=False` |
| 版本冲突 | 第二次追加成功 | 结构+条件**各重跑一次**（KS-1.4） |
| 未注册 Action | 否 | 无写尝试污染审计 |

---

## 7. 测试、发布与启动序列

```powershell
python src/cli/main.py test            # 60 条布线路径
python src/cli/main.py release         # 5 关全绿才出制品
python src/cli/main.py bootstrap --stage 1 --appointment-ref <真实外部凭据>
```

`release` 的 5 关（任一失败 → 不出制品）：

```
[PASS] structural
[PASS] cryptographic
[PASS] registered        · 6 能力
[PASS] tests             · 60 条布线路径全部通过
[PASS] codegen           · 骨架字节级零漂移 · 3 文件
RELEASED: 制品清单已落档 ...\dist\RELEASE-MANIFEST.json
```

**BOOT-1 护栏**：`--appointment-ref` 强制。创制任命是系统外事件，模板只记录引用，不合成（GOV-1）。`bootstrap --stage 2/3` 返回拒绝——治理工作流与 Identity Context 验收属实例侧世界事件，这是诚实边界，不是待修 bug。

---

## 8. 失败形态与排错（按错误文本索引）

| 错误文本 | 含义 | 处理 |
|---|---|---|
| `NOT-REGISTERED: 先执行 aos register（BOOT-0）` | 实例尚未登记工件 | 先 `bootstrap --stage 0` |
| `RECONCILE-FAILED: declared != registered` | 改了声明但能力清单未同步 | 走 `aos draft` → `aos draft promote`，不要手改 capabilities |
| `CODEGEN-DRIFT-REFUSED` | 生成物与声明不一致 | 确认后 `aos generate --force` |
| `PYTEST-MISSING: 缺少 pytest` | 执行引擎缺失 | `pip install -e .` |
| `WIRING-REFUSED: 声明的测试路径不存在` | 布线件声明了不存在的测试 | 补文件或从 `verification.yaml` 移除；不可静默降级 |
| `STRUCTURAL-MISMATCH` | 正典条数/首锚/末锚不符 | 按 GOV-2.5 二分：正典缺内容走 GOV-6；副本退化则重新分发 |
| `FROZEN-TEXT-MUTATED` / `HASH-MISMATCH` | 冻结正典被就地改 | 走 GOV-3 版本通道，不回改登记表 |
| `REFUSED: 缺位置参数` / `用法: ...` | CLI 参数缺失 | 按用法补参；不会丢裸 traceback |
| `BOOT-1` 缺任命凭据 | 试图合成创制任命 | 提供真实外部凭据；模板不制造世界事件 |
| `BudgetExceeded` | 版本冲突重求值超上界 | 竞争过热，fail-closed；降低并发或调高有界重试需走变更流程 |

---

## 9. 不要做的事

1. 不要手改 `docs/aos-spec.md` / `SPEC-FINGERPRINT.md`——它们入 sha256 覆盖域，改了就是冻结文本变更（GOV-3）。
2. 不要清理 `build/` / `dist/` / `*.egg-info` 来"保持干净"——`.gitignore` 已覆盖；唯一跟踪的 `dist/RELEASE-MANIFEST.json` 是**签发证据**。
3. 不要期待实例里 `aos ...` 作用于实例——控制台脚本指向模板根；实例内用 `python src/cli/main.py`。
4. 不要把〔强〕项标记为通过——VER-20/24/26/27/28/29 需要运行系统上的人工执行与 evidence/judge/signer 留档。
5. 不要把模板当生产运行时——`EventStore` 纯内存；`kernel/filestore.py` 的 `FileStore` 是持久化**参考实现**（JSONL 追加 + 重放，单写进程模型），生产实例仍须自行证明 append-only 与审计持久性。

---

下一步：[05 · 速查手册](05-reference.md)——CLI、术语、异常与 VER 布线的随手索引。
