# ADR-006：把 Open WebUI 作为生成脚手架的可选前端能力

- 状态：Accepted
- 日期：2026-11-21
- 关联：`src/kernel/profile.py`（能力注册表）、`tools/codegen.py`（生成器）、`config/verification.yaml`（闸门布线）

## 背景

`aos init` 复制整棵源码树生成实例，实例自带 `tools/console.py` 治理壳（HTTP → subprocess → CLI，白名单、无认证、仅 127.0.0.1）。生成器已按 Feature Profile 输出 `GUARD/FORMS/PAGES` 前端元数据，但明确不含 UI 库，注释写明"实例侧框架消费"。Open WebUI（https://github.com/open-webui/open-webui）是可扩展、可离线、自托管的 AI 界面，支持 Ollama 与 OpenAI-compatible 后端，并提供服务端 Pipe 插件（可注册为自定义模型，`__user__` 提供可信身份，`Valves` 提供管理员配置）。

因此问题是：能否让生成出来的实例自带 Open WebUI 作为前端，而不是把它塞进 AosKeel 模板仓库本身。

## 决议

1. 新增能力 `frontend.open_webui`，依赖 `frontend.admin_console` 与 `auth.oauth2_1`；进入 `full` 与 `standard` 深度预设，`minimal` 不含。模板 `spec/profile.yaml` 默认声明该能力，使普通 `aos init` 生成的实例在 `aos generate` 时自带前端胶水；`--depth minimal` 或 `--no-cap frontend.open_webui` 可退出。
2. 生成物只有胶水，共三件：
   - `src/generated/openwebui_pipe.py`：Open WebUI Pipe，具备 `Valves.INSTANCE_ROOT` 与管理员配置的 `Valves.ROLE_MAP_JSON`；
   - `docker-compose.openwebui.yml`：以外部镜像 `ghcr.io/open-webui/open-webui` 启动，挂载实例目录；
   - `docs/OPENWEBUI.md`：安装、导入 Pipe、权限边界说明。
   Open WebUI 源码不 vendored、不进入实例树、不受 TEMPLATE-LOCK 与三闸门的字节保护。
3. Pipe 的交互面严格限于：
   - 只读 CLI 白名单（`review/profile/verify/impact/manual/shadow/shadow-online/spec fingerprint/spec digest`），且**整族禁带 `--out` / `--extractor`**——前者在 CLI 侧直接写盘，后者执行任意脚本；
   - 草稿通道（`aos draft` / `aos extract`，输出到 `spec/drafts/`，仍走三闸门），**要求至少一个映射角色**，草稿名只允许 `[A-Za-z0-9_-]{1,64}`；
   - 用生成的 `admin_console.GUARD/nav_for` 按映射角色**展示**可见动作。这是可见性展示，不是命令授权；`/nav` 中的治理签署动作本 Pipe 一律不执行。
   裸聊天文本不切词执行，须 `/cmd` 或 `/draft` 显式前缀。禁止 `spec version`、`spec register-declarations`、`draft promote`、`bootstrap`、`release`、`register` 等治理签署面——与 `tools/console.py` 的 `DENIED_PAIRS` 同判据。
4. 身份：`__user__` 的 email/id 映射为 `principal`；角色只能来自管理员配置的 `ROLE_MAP_JSON`（按 Open WebUI 目录角色或用户 id 映射），**不得从聊天内容自报**。起草通道无角色 fail-closed。Pipe 不 import 内核，不直接调用 `Kernel.submit()`；只经 subprocess 调实例 CLI，维持"壳不 import 内核"。
5. 手改检测、能力摘除、spec_ref 头、conformance 布线与既有生成物同构；新增测试 `tests/conformance/test_codegen_openwebui.py` 必须进入 `config/verification.yaml`。

## 被否决的方案

- **直接替换 `tools/console.py`**：Open WebUI 无治理表单的稳定扩展点，且无法承载治理签署的终端语义；否决。
- **把 Open WebUI 源码 vendored 进模板/实例**：第三方代码混入冻结哈希与三闸门保护面，升级成本转嫁给模板；否决。
- **Pipe 内直接 `Kernel.submit()`**：绕过 principal/roles 可信证据与写路径纪律（P-10 / INV-4），且破"壳不 import 内核"；否决。除非实例侧先补出带认证的写命令网关与审计回写，否则不重开。
- **仅用 OpenAI-compatible 适配层**：需新建 `/v1` 服务，而 Pipe 已能直接承载胶水，投入产出比更低；暂不采用。

## 修订 1（2026-11-21，反思后收紧）

初版经逐行回查，发现四项「宣称强于实现」的缺陷，均已修并纳入 conformance：

| 缺陷 | 代码证据 | 修正 |
| --- | --- | --- |
| 只读白名单实际可写盘 | `review`/`manual` 支持 `--out`，CLI 直接 `write_bytes` | Pipe 整族禁 `--out` / `--extractor` |
| 草稿 Pipe 藏代码执行面 | `extract --extractor` 执行实例内任意 `.py` | 同上；`--extractor` 只留终端 |
| 草稿名可拼出 drafts 之外 | `write_draft` 拼 `draft-{name}.yaml`，`--name` 原样透传 | 仅 `[A-Za-z0-9_-]{1,64}` |
| 角色守卫未参与授权 | `_run` 只回显 roles，`/nav` 只展示 | 起草通道无角色 fail-closed；`/nav` 明示仅展示 |

另修部署默认面：端口绑定 `127.0.0.1`、镜像 pin `v0.13.4`、实例根只读挂载且仅 `spec/drafts/` 可写、`ENABLE_SIGNUP=false` 并要求首次预置管理员；裸文本不再切词执行；`test_canonical_untouched` 从长度快照改为内容哈希。以上改动全部落在生成器，生成物由 `aos generate` 重新签发，不手改受控字节面。

## 代价与风险

- 生成一个外部运行时依赖（镜像或 pip/uvx），实例部署面变大；需要模型后端（Ollama 或 OpenAI-compatible API），本项目不提供。
- 挂载实例目录进容器是为让草稿通道可写；须在文档中明示仅限受信任的本地/内网部署。
- Open WebUI License 要求保留品牌标识；对外白标需商业授权，由实例方自行评估。
- `auth_oauth2.py` 目前只有 Python 函数、没有 HTTP 端点；Pipe 的身份映射是目录映射，不等价于 OAuth2.1 claims 注入，不能作为生产多租户授权依据。

## 退出条件

若后续同时满足：① Open WebUI 提供稳定的自定义表单/页面扩展点；② 实例侧存在带认证的读写 API 适配层与可信 claims 注入，则重新评估让 Open WebUI 接管完整治理控制台。在那之前，`FORMS/PAGES` 的原生表单渲染仍由实例侧薄前端承担。
