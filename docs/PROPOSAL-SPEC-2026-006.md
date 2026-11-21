# SPEC-2026-006：新增 frontend.open_webui 能力

- 日期：2026-11-21
- 状态：Submitted（随 ADR-006 一起执行）
- 决策依据：`docs/adr/ADR-006-open-webui-generated-frontend.md`

## 变更面

- `spec/profile.yaml`：在 `frontend` 能力段新增 `open_webui: true`，使模板实例在
  `aos generate` 时产出 Open WebUI Pipe 胶水与运行时 compose。
- 冻结正典 `docs/aos-spec.md` **不动**；本提案只影响 Feature Profile 声明摘要
  （GOV-2.3-DECL 域），因此走 `aos spec register-declarations` 的治理变更通道。

## 纪律不变量

- Open WebUI 源码不进入实例树；只生成 Pipe、compose 与使用说明。
- Pipe 只读白名单 + 草稿通道；治理签署面继续只在终端/CLI。
- roles 只来自管理员目录映射，不从聊天内容自报；Pipe 不 import 内核。

## 闸门

- `INTEGRITY-43`：`tests/conformance/test_codegen_openwebui.py` 进入
  `config/verification.yaml`。
- `aos verify` / `pytest` / `aos test` / `aos release` 全绿后放行。
