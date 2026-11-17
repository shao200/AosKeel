# aoskeel-kernel

AOS 内核纯逻辑层（kernel / interpreter / generated / agents），可 `pip install` 的增量分发包。见仓库根 [ADR-001](../../docs/adr/ADR-001-dual-distribution.md)。

## 安装与使用边界

```powershell
pip install packages/kernel          # 从源码树构建安装
```

本 wheel **只含 Python 逻辑模块**，不含 `docs/spec/config/tools/cli`。这是刻意的边界：模板运行形态仍以源码树为准（根 `pyproject.toml` / `aos init`）。

`kernel.registration` 与 `kernel.session` 需要读取 `config/capabilities.yaml` 与 `spec/`。在 site-packages 中运行时，用 `AOSKEEL_ROOT` 指向一份 template 根：

```powershell
$env:AOSKEEL_ROOT = "D:\path\to\aos-template"   # 含 config/ 与 spec/ 的源码树
```

未设置 `AOSKEEL_ROOT` 时，行为与源码树内直接运行逐字一致（回退 `Path(__file__).parents[2]`）——零回归。

纯逻辑部分（如 `kernel.store.EventStore` 的结构校验、`kernel.session.SessionChannel` 的追加语义）不依赖外部数据目录，可直接导入使用。

## 配套

- `aoskeel-template`（`packages/template/`）：含 docs/spec/config 的源码树 sdist，作 `aos init` 模板源。
- 完整 CLI（top-level `aos-keel` wheel）：始终从源码树运行，见根 README。
