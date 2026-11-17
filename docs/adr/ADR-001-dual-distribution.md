# ADR-001：双分发制（aoskeel-kernel + aoskeel-template）

- 状态：Accepted（用户于 2026-11-17 授权"做 D"；按 ADR→PR→gates→regression 执行）
- 日期：2026-11-17
- 决策者：项目所有者（模型变更授权保留在仓库之外）

## 上下文

同行评议 D 建议"发布 wheel + 拆分 CLI / 内核两个包"：

- `aoskeel-kernel`：纯 Python、可 `pip install`；
- `aoskeel-template`：含 docs/spec/config，作 `aos init` 模板源。

取证发现三处硬约束，使字面方案不可直接执行：

1. **kernel 非无依赖**：`src/kernel/registration.py` 读 `config/capabilities.yaml`、`spec/`、`spec/meta/declaration-schema.yaml`；`src/kernel/session.py` 读 `config/capabilities.yaml`。14 个内核模块通过 `ROOT = Path(__file__).resolve().parents[2]` 锚定源码树。装进 site-packages 后该锚点失效。
2. **现有 wheel 边界是机器守卫**：`tests/conformance/test_installability.py` 断言根 wheel **不含** docs/spec/config，且 entry point `aos = src.cli.main:main` 在场；`src/cli/main.py::_require_source_tree` 在无正典时 `REFUSED`。这是"模板须从源码树运行"的诚实边界，不可就地推翻。
3. **口径派生源不可动**：`tools/doc_metrics.py` 从 `src/cli/main.py` 分派分支派生 CLI 命令数（26 = 21 顶层 + 5 子命令）；新增顶层/子命令会连带改动 6+ 文档与守卫。

冻结约束（任何方案不得触碰）：正典哈希域 `docs/aos-spec.md` + `docs/SPEC-FINGERPRINT.md`（`e6884aed…`）、声明摘要域 `spec/**/*.yaml`（`91ffe5a1…`）、登记表 `docs/ARTIFACT-REGISTRY.md`。

## 决策

采用**增量双分发**，不替换现有根 wheel：

1. **保留**根 `pyproject.toml`（`aos-keel` 0.3.0）与 `test_installability.py` 全部契约不变——源码树仍是唯一受支持的模板运行形态。
2. **新增** `packages/kernel/pyproject.toml`：构建 `aoskeel-kernel` wheel，仅含 `kernel` / `interpreter` / `generated` / `agents` 四个包（纯逻辑层），依赖 `pyyaml`；**不含** docs/spec/config/tools/cli。
3. **新增** `packages/template/build_sdist.py`：用标准库 `tarfile` 从源码树生成 `aoskeel-template` sdist（含 docs/spec/config/src/tools/tests），作为 `aos init` 的模板源分发工件；零外部依赖、可离线构建。
4. **ROOT 注入**：`registration.py` 与 `session.py` 的 `ROOT` 改为 `Path(os.environ.get("AOSKEEL_ROOT") or <原路径>)`. 未设环境变量时行为与原样**逐字等价**（零回归）；设置后指向 template 根，使 kernel wheel 真正可用而非空壳。其余 12 处 `ROOT` 仅用于 `sys.path` 注入，不读取外部数据，保持不动。
5. 新增守卫 `tests/conformance/test_dual_distribution.py` 锁住两个分发的边界与注入语义。

## 备选（否决）

- 改根 `pyproject.toml` 的 name / 把 docs 塞进 wheel：破坏 `test_installability` 与"源码树唯一运行形态"，属就地推翻诚实边界。
- 改 CLI 增加 `package` 命令：命令数从 26 漂移，连带 6+ 文档与守卫，收益不抵成本。
- 声称 kernel "无 config 依赖"直接打包：装到 site-packages 后 `load_caps()` 找不到 capabilities.yaml，是假通过。

## 后果

**正面**：CI/CD 与 Docker 可 `pip install aoskeel-kernel` 获得纯逻辑库；`aoskeel-template` sdist 可作远程模板源；两条路径都不动摇冻结正典与四道门禁。

**负面 / 诚实边界**：
- `aoskeel-kernel` 在 site-packages 中**必须**设置 `AOSKEEL_ROOT` 指向一份 template 根才能调用注册/提交链；这是 kernel 读 config/spec 的必然要求，不是缺陷。
- `aos init` 仍从本地源码树复制；"远程模板源 = sdist 工件下载后解包"是分发语义，未引入网络拉取逻辑（那会触动 CLI 与命令数口径）。

## 合规与回退

- 流程：ADR（本文件）→ 工作树变更（PR 载体）→ gates（`aos verify` 四道 + 全量 pytest）→ regression（双 wheel/sdist 真构建 + 现有 installability 守卫）。
- 回退：删除 `packages/` 与守卫、还原两处 `ROOT` 行即可；不涉及正典/声明/登记表，故无 GOV-3 版本通道成本。
