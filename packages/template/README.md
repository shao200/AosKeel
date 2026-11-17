# aoskeel-template

模板源码树 sdist 分发工件（ADR-001 增量双分发）。含 `docs/spec/config/src/tools/tests`，作为 `aos init` 的模板源——下载解包后即为可实例化的完整源码树。

```powershell
python packages/template/build_sdist.py     # → dist/aoskeel-template-0.3.0.tar.gz
```

构建脚本只用标准库 `tarfile`，排除 `.git/.venv/build/dist/__pycache__/packages` 等，并自检 `docs/aos-spec.md`、`spec/profile.yaml`、`config/capabilities.yaml`、`src/cli/main.py` 四件全在场（缺一即非零退出）。

这是"分发形态"，不改变运行形态：`aos init` 仍从本地源码树复制（见 [04 教程](../../docs/guide/04-tutorial.md)）。配套 `aoskeel-kernel`（`../kernel/`）提供可 pip 装的纯逻辑层。

冻结正典（`e6884aed…`）与声明摘要（`91ffe5a1…`）由根源码树携带，本 sdist 只是逐字节搬运，不改写。
