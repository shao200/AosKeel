#!/usr/bin/env python3
"""src/cli/main.py —— 薄分发器（命令表驱动；make 目标保留为 CI 封装）。
aos verify 三关串联：结构层（指纹 GOV-2.4）→ 密码学层（哈希 GOV-2.3）→
注册层（declared == registered，KS-7.2 第 5 步）。任一失败 → exit 1。
护栏一（GOV-1）：bootstrap --stage 1 强制 --appointment-ref —— 拒绝合成创制任命。
运行形态：模板以源码树为交付物（pip install -e .）—— wheel 不含 docs/spec/config，
启动时自检并明确拒绝，不把误装报成一串 FileNotFoundError。
"""
import sys, shutil, json, subprocess, re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.hash_spec import (canonical_digest, _entries, register as hs_register,
                             verify as hs_verify, supersede as hs_supersede,
                             register_declarations as hs_register_declarations,
                             declaration_digest as hs_declaration_digest,
                             _decl_entries as hs_decl_entries,
                             decl_digest_skip as hs_decl_skip)
from tools import fingerprint, wiring, gate_history
from kernel import registration
USAGE = """\
用法: aos <command>
  init <dir>            实例化模板；写 TEMPLATE-LOCK        目标已存在 → 拒绝
  verify                三关: 指纹 → 哈希(正典+声明摘要) → 注册层  任一失败 → exit 1
  register <version>    GOV-2.3 正典登记                      同哈希幂等；漂移 → 拒绝
  bootstrap --stage N   BOOT-0..3；--dry-run 只跑检查表不写入  阶段乱序 → 拒绝
  test [--suite S]      按 verification.yaml 分组             套件失败 → exit 1
  cq [list|run] [CQ-n ...] [--domain D]
                        能力问题验收（contract 域十张冻结清单）
                        list 列题；无参或 run 全跑；指定 id 单跑
                        --domain D 跑实例自定义域（domains/）  任一 FAIL → exit 1
  spec fingerprint      独立结构层核对（GOV-2.5 分歧二分）     报缺 → exit 1
  spec digest           只读查看 spec/ 声明摘要与登记状态     不写入
  spec register-declarations <v> [--proposal-ref SPEC-YYYY-NNN]
                        GOV-2.3-DECL 声明摘要登记（append-only）；不改冻结正典
                        首次直接登记；后续漂移须带治理提案引用      缺 → 拒绝
  spec version <v>      GOV-3 版本通道：新版本登记（append-only）
                        --proposal-ref SPEC-YYYY-NNN 强制      缺 → 拒绝
  generate [--force]    声明 → 代码骨架（Profile 门控：backend.cqrs →
                        command_api/query_api；auth.oauth2_1 → auth_oauth2（IdP：
                        AC+PKCE/治理面 claims/DPoP）；actions/reducers 常驻）
                        手改检测：不一致 → 拒绝静默覆盖；--force 显式覆盖
  release               发布闸门（fail-closed）：三关 + 布线套件 + 骨架一致性
                        全绿 → dist/RELEASE-MANIFEST.json；任一失败 → 不出制品
  draft <file>          需求 DSL → 本体草案（解析→编译把关；全绿才写 spec/drafts/）
                        --name N 命名草案；编译不过逐条报告，不落盘
  draft promote <f>     草案晋升正典（--proposal-ref SPEC-YYYY-NNN 强制，GOV-1）
  import-db             数据库元结构 → 本体草案（旧系统迁移素材源）
                        (--dsn sqlite:///db | --ddl dump.sql) [--name N]
                        [--tables a,b] [--skip-failed] ｜ 只读 schema 不读业务数据，
                        凭据不落盘；方言失败如实拒绝（不静默跳过 = 不丢表）
                        目标已存在 → 拒绝（GOV-3 通道）；晋升含 apply_generated（P-5）
  import-data           数据迁徙（细胞移植）：老库数据行 → 创世事件草案
                        --dsn sqlite:///db --map M [--name N] [--skip-failed]
                        映射只声明「老表列→动作参数」，事件形态由正典动作定；
                        逐行走 Kernel.submit 完整求值链，违反约束即拒（fail-closed）；
                        只读源库（mode=ro）；凭据不落盘；产物 data-drafts/*.ndjson
  extract               语义提取：素材（源码/文档）→ 本体草案（过同一三段闸）
                        <file> --name N [--extractor script.py]
                        builtin 参考提取器 = 确定性规则（零 LLM）；LLM 调用写进
                        自定义适配器（契约: stdout YAML objects[]）；产物只进
                        spec/drafts/，晋升须 GOV-1 提案
  shadow-online         在线影子对账：消费部署侧探针 NDJSON（契约见工具头注释）
                        <probes.ndjson> ｜ 对比新旧在线系统状态/输出等价；
                        坏行 fail-closed 零静默；探针（拦流记录）属实例侧
  shadow                影子对账（离线双跑）：老库行 ↔ 新体系事件语义等价
                        --dsn sqlite:///db --map M ｜ 复用 import-data 映射；
                        对账三项：求值链接受 / 映射字段无损 / 声明效果落位；
                        差异清单应进 aos review；在线影子流量属部署期
  review                审核清单（只读咨询）：profile 锚点现状 / drafts 候选 /
                        [--out F]            治理授权对账 → 带编号裁决清单
                        每项附下一步命令（promote 须 GOV-1 提案；L3 不可自动定稿）
  manual [--out F]      领域说明书：spec/ 九类声明 → 可读文档（人读 + LLM 上下文注入）
                        派生件非真源；缺省打印到 stdout，--out 落盘
  impact <target>       变更影响分析（事前咨询）：声明名 / spec 路径 / ObjectType.prop
                        → 反向引用图报告；不进闸门，缺目标 → 拒绝
  profile               Feature Profile 解析：能力选择 → 依赖展开 → 生成序
                        （治理面在前）；锚点缺失 → 拒绝；只出计划不生成代码
  init <dir>            模板实例化到新目录（不覆盖既有目标）
                        [--name N] 实例名；实例化后可定制 Profile：
                        [--depth minimal|standard|full] [--cap ID] [--no-cap ID]
                        [--interactive] —— 无定制旗标 = 保留模板 profile 原样
  audit export <events.jsonl> [--out F]
                        统一审计导出：追加证据 + 决策引用 → 链式 audit_id JSONL
                        （只读派生件；进程内台账用 tools.audit_export.export）
  metrics               闸门度量：dist/gate-history.jsonl → 通过率 / 各关失败 /
                        漂移计数 / 连续通过（派生证据件，不参与判定）
"""


class UsageError(Exception):
    """参数缺失/非法：一律转成明确 REFUSED，不向用户丢裸 traceback。"""


def _value(rest: list[str], flag: str, usage: str) -> str | None:
    if flag not in rest:
        return None
    i = rest.index(flag)
    if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
        raise UsageError(f"{flag} 缺值 —— {usage}")
    return rest[i + 1]


def _positional(rest: list[str], index: int, usage: str) -> str:
    if len(rest) <= index or rest[index].startswith("--"):
        raise UsageError(f"缺位置参数 —— {usage}")
    return rest[index]


def _latest_spec_version() -> str:
    """规范版本真源：登记表最新条目的版本列（E-2：不再硬编码，跃迁自动跟随）。
    登记表为空（实例在 BOOT-0 首登记前）时回落冻结正典头部的版本标识。"""
    rows = _entries()
    if rows:
        cols = [c.strip() for c in rows[-1].split("|")]
        if len(cols) > 2 and re.fullmatch(r"v\d+\.\d+\.\d+", cols[2]):
            return cols[2]
    spec = (ROOT / "docs/aos-spec.md")
    if spec.exists():
        m = re.search(r"^v(\d+\.\d+\.\d+)\s+·\s+Frozen", spec.read_text(encoding="utf-8"), re.M)
        if m:
            return "v" + m.group(1)
    return "UNREGISTERED"


def _require_source_tree() -> int | None:
    """wheel 里没有 docs/spec/config；宁可明确拒绝，也不假装可用。"""
    if (ROOT / "docs/aos-spec.md").exists() and (ROOT / "config/verification.yaml").exists():
        return None
    print("REFUSED: 模板须从源码树运行（pip install -e . 或 python -m src.cli.main）—— "
          "wheel 仅是构建/签发产物，不含 docs/spec/config，不是可安装交付物。")
    return 1


def cmd_verify() -> int:
    gates: dict[str, str] = {}                  # 度量留档：每关结果入 gate-history
    print("[1/3] 结构层（指纹 GOV-2.4）")
    failures = fingerprint.check()
    if failures:
        print("  STRUCTURAL-MISMATCH（GOV-2.5）:")
        for f in failures: print(f"    - {f}")
        gates["structural"] = "FAIL"; gate_history.record("verify", gates)
        return 1
    gates["structural"] = "PASS"
    print("  OK —— 附录 F 十节三元组在场")
    print("[2/3] 密码学层（分离式哈希 GOV-2.3：正典 + 声明摘要 双比对）")
    if hs_verify() != 0:
        gates["cryptographic"] = "FAIL"; gate_history.record("verify", gates)
        return 1
    gates["cryptographic"] = "PASS"
    print("[3/3] 注册层（declared == registered，KS-7.2 / INV-13）")
    try:
        gen = registration.run_pipeline()
        n = len(gen["write_actions"]) + len(gen["channel_writes"])
        print(f"  OK —— {n} 条能力一致（含 provenance 回溯）")
        gates["registered"] = "PASS"
    except registration.RegistrationFailed as e:
        print(f"  REGISTRATION-FAILED: {e}")
        gates["registered"] = "FAIL"; gate_history.record("verify", gates)
        return 1
    gate_history.record("verify", gates)
    if hs_decl_skip():
        # N3：SKIP 不得被包装成与全比对无差别的"三关连续通过" —— 实例未登记
        # 声明基线时，第四道（业务声明的密码学比对）并未真正执行。
        print("VERIFY-OK-WITH-SKIP: 三关连续通过 —— 结构 / 密码学 / 注册"
              "（第四道声明摘要 SKIP：未登记基线；aos spec register-declarations 后方可出制品）")
    else:
        print("VERIFY-OK: 三关连续通过 —— 结构 / 密码学 / 注册")
    return 0


def cmd_init(target: str, wizard: dict | None = None) -> int:
    dst = Path(target).resolve()
    if dst.exists():
        print(f"REFUSED: 目标已存在 {dst} —— init 不覆盖（护栏）"); return 1
    if wizard and any([wizard.get("depth"), wizard.get("add"),
                       wizard.get("remove")]):
        # 参数前置校验（fail-fast）：非法参数不得浪费一次完整实例化
        from kernel.profile import validate_init_args, ProfileError
        try:
            validate_init_args(wizard.get("name"), wizard.get("depth") or "standard",
                               tuple(wizard["add"]), tuple(wizard["remove"]))
        except ProfileError as e:
            print(f"INIT-PROFILE-REFUSED: {e} —— 未创建目标目录")
            return 1
    dst.mkdir(parents=True)
    EXCLUDE = {"__pycache__", ".aos", "drafts"}          # drafts=工作区，不入实例
    copied = 0
    for d in ("docs", "config", "spec", "tools", "src", "tests", "bootstrap", ".github"):
        src_dir = ROOT / d
        if not src_dir.exists(): continue
        for p in src_dir.rglob("*"):
            if p.is_dir() or any(part in EXCLUDE for part in p.parts): continue
            if p.name in ("ARTIFACT-REGISTRY.md", "TEMPLATE-LOCK.md",
                          "DOMAIN-MANUAL.md") or p.name.startswith("REVIEW-"):
                continue     # 实例自行登记（GOV-2.3）；LOCK/说明书由本命令生成；
                             # 作者本地评审文档不随实例外发
            rel = p.relative_to(ROOT)
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel); copied += 1
    rows = _entries()
    art_id = rows[-1].split("|")[1].strip() if rows else "NOT-REGISTERED"
    spec_ver = _latest_spec_version()
    # 根层文件：.gitattributes 的 `* -text` 是 GOV-2.3 字节精确防线的一部分，
    # 实例缺失时换行转换可破坏冻结哈希；pyproject/.gitignore 直接复制。
    for f in (".gitattributes", ".gitignore", "pyproject.toml"):
        src_f = ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, dst / f); copied += 1
    # 实例 README 由 init 生成（模板 README 描述的是模板自身，不复制）
    (dst / "README.md").write_bytes(
        _gen_instance_readme(dst.name, spec_ver, art_id).encode("utf-8"))
    snap_ok = not fingerprint.check((dst / "docs/aos-spec.md").read_text(encoding="utf-8"))
    # 领域说明书：init 即生成，用户第一眼看到"本域能做什么/谁说了算/哪里会拒绝"
    try:
        from tools.domain_manual import render as _render_manual
        (dst / "docs/DOMAIN-MANUAL.md").write_bytes(_render_manual().encode("utf-8"))
    except Exception as e:                               # 派生视图不阻断实例化
        print(f"WARN: 领域说明书生成失败（{e}）—— 可稍后 aos manual --out docs/DOMAIN-MANUAL.md")
    (dst / "docs/TEMPLATE-LOCK.md").write_bytes(
        _gen_template_lock(spec_ver, art_id, snap_ok, copied).encode("utf-8"))
    print(f"INITIALIZED: {dst}（{copied} 文件；TEMPLATE-LOCK: template 0.3 × {spec_ver} × {art_id}）")
    if wizard and any([wizard.get("depth"), wizard.get("add"),
                       wizard.get("remove"), wizard.get("interactive")]):
        # Profile 定制向导（实例化后第二步）：depth 预设 ± 能力增删。
        # 实例自带模板 profile —— 定制即重铺（init_profile force=True），
        # 产出走同一解析器自校验；失败则如实报告（模板 profile 仍在，实例可用）。
        from kernel.profile import init_profile, DEPTH_PRESETS, ProfileError
        wname = wizard.get("name") or dst.name
        depth = wizard.get("depth") or "standard"
        try:
            if wizard.get("interactive") and not wizard.get("depth"):
                depth = input(f"深度 {sorted(DEPTH_PRESETS)} [standard]: ").strip() \
                    or "standard"
            if wizard.get("interactive") and not wizard.get("name"):
                wname = input(f"项目名 [{wname}]: ").strip() or wname
            r = init_profile(wname, depth, tuple(wizard["add"]),
                             tuple(wizard["remove"]), root=dst, force=True)
        except ProfileError as e:
            print(f"INIT-PROFILE-REFUSED: {e} —— 实例保留模板 profile；"
                  "可手工编辑 spec/profile.yaml 后 aos profile 校验")
            return 1
        declared = sum(1 for s in r["selected"].values() if s == "declared")
        print(f"INIT-PROFILE: {r['path']}（depth={r['depth']}，"
              f"选定 {len(r['selected'])} 项 = 声明 {declared} + 自动展开 "
              f"{len(r['selected']) - declared}）")
        print("生成顺序: " + " → ".join(r["order"]))
        for f in r["failures"]:
            print(f"  [PENDING] {f}   ←（待声明 roadmap，补齐后即可 aos generate）")
        print("下一步: cd 实例 && python src/cli/main.py bootstrap --stage 0")
    else:
        print("下一步: cd 实例 && python src/cli/main.py bootstrap --stage 0"
              "（或 aos init <dir> --depth standard 定制能力广度）")
    # ADR-006：根层生成物不在目录白名单内 —— 按实例最终 profile 决定是否随脚手架带走。
    # 模板自身必须先跑过 aos generate 产出 compose；能力关闭时实例侧 generate 会摘除。
    try:
        import yaml as _yaml
        _prof = _yaml.safe_load((dst / "spec/profile.yaml").read_text(encoding="utf-8")) or {}
        _caps = (_prof.get("profile") or {}).get("capabilities") or {}
        _open_webui = bool((_caps.get("frontend") or {}).get("open_webui"))
    except Exception:
        _open_webui = False
    if _open_webui:
        _compose = ROOT / "docker-compose.openwebui.yml"
        if _compose.is_file():
            shutil.copy2(_compose, dst / _compose.name)
    return 0


def _gen_instance_readme(name: str, spec_ver: str, art_id: str) -> str:
    return (
        f"# {name} —— AOS 实例\n\n"
        f"template 0.3 × spec {spec_ver} × registry {art_id}"
        f"（绑定详情见 docs/TEMPLATE-LOCK.md）\n\n"
        "## 先读两份地图\n\n"
        "- **docs/DOMAIN-MANUAL.md** —— 领域说明书（init 自动生成）：本域有什么概念、"
        "谁能改、什么条件会拒绝、违约怎么办。声明变更后 `python src/cli/main.py manual --out docs/DOMAIN-MANUAL.md` 重生成。\n"
        "- **docs/guide/09-structure-and-trajectory.md** —— 项目结构与开发轨迹："
        "每个目录为什么在这、扩展一个自己领域的完整走法、AI 怎么接。\n\n"
        "## 快速开始\n\n"
        "```powershell\n"
        "python src/cli/main.py bootstrap --stage 0   # 实例自行登记（首个 AOS-ART 条目）\n"
        "python src/cli/main.py verify                # 三关：指纹 → 哈希 → declared==registered\n"
        "python src/cli/main.py test                  # 按 config/verification.yaml 布线执行\n"
        "python src/cli/main.py manual                # 打印领域说明书\n"
        "```\n\n"
        "## 先做 BOOT-0\n\n"
        "新实例未登记时 `pytest` 会有约 7 项失败（release gate / spec_ref 类）——"
        "这是 GOV-1 设计行为：实例不合成登记与合法性。`bootstrap --stage 0` 后全绿。\n\n"
        "## 运行形态\n\n"
        "实例内命令一律经 `python src/cli/main.py <command>`；"
        "`aos` 控制台入口锚定模板根，不指向实例。\n\n"
        "提交动作需要出示角色证据（P-10/INV-4 单一写路径强制）：\n\n"
        "```python\n"
        "kernel.submit(\"ApproveContract\", params, \"alice\",\n"
        "              roles=(\"contract_steward\",))   # 未出示 = 无权（fail-closed）\n"
        "```\n\n"
        "## 学习路径\n\n"
        "构建企业应用全程指南：docs/guide/08-enterprise-app-guide.md"
        "（建模 → AI 起草与晋升 → 生成 → 外部接入 → Agent 装配 → 签发 → 自建清单）\n\n"
        "指南索引 docs/guide/README.md · 项目全貌 docs/README.zh-CN.md · "
        "冻结正典 docs/aos-spec.md（勿改：GOV-2.3）\n"
    )


def _gen_template_lock(spec_ver: str, art_id: str, snap_ok: bool, copied: int) -> str:
    return (f"# TEMPLATE-LOCK（init 时写入；版本绑定）\n\n"
            f"- template_version: 0.3\n- spec_version: {spec_ver}\n"
            f"- registry_entry: {art_id}\n"
            f"- fingerprint_snapshot: {'PASS' if snap_ok else 'FAIL'}\n"
            f"- files_copied: {copied}\n"
            f"- 规范副本哈希绑定登记条目 {art_id}；实例内 aos verify 校验"
            f"副本哈希 = 登记哈希，改动即 FROZEN-TEXT-MUTATED（INV-12）\n"
            f"- 下一步: aos bootstrap --stage 0（实例自行登记为首个 AOS-ART 条目）\n")


def cmd_bootstrap(stage: int, appointment_ref: str | None, dry_run: bool) -> int:
    marker_dir = ROOT / ".aos"
    def done(n: int) -> bool:
        return (marker_dir / f"boot-{n}.done").exists()
    if stage > 0 and not done(stage - 1):
        print(f"REFUSED: BOOT-{stage - 1} 未完成 —— 阶段乱序拒绝"); return 1
    if stage == 0:
        if dry_run:
            failures = fingerprint.check()
            print("DRY-RUN: 检查表 —— 指纹", "PASS" if not failures else f"FAIL {failures}",
                  "｜ 登记", "已有（幂等重跑，无写入）" if _entries() else "缺失（正式执行将写入）")
            return 0 if not failures else 1
        code = hs_register(_latest_spec_version()) or cmd_verify()
        if code == 0:
            marker_dir.mkdir(exist_ok=True)
            (marker_dir / "boot-0.done").write_bytes(
                f"art={(_entries()[-1].split('|')[1].strip() if _entries() else 'NONE')}\n"
                .encode("utf-8"))
            print("BOOT-0-DONE: 内核部署 + 能力清单发布 + 工件哈希登记（附录 E 激活）")
        return code
    if stage == 1:
        if not appointment_ref:                                   # 护栏一
            print("REFUSED: BOOT-1 强制 --appointment-ref <外部凭据> —— "
                  "CLI 只记录创制任命，拒绝合成创制任命（GOV-1）"); return 1
        marker_dir.mkdir(exist_ok=True)
        (marker_dir / "boot-1.json").write_bytes(json.dumps(
            {"appointment_ref": appointment_ref, "note":
             "创制任命是世界事件；此处仅记录引用，不制造正当性（AX-4/GOV-1）"},
            ensure_ascii=False, indent=2).encode("utf-8"))
        (marker_dir / "boot-1.done").write_bytes(b"recorded\n")
        print(f"BOOT-1-RECORDED: 创制任命引用已留档（audit 第一条由运行时内核落账）")
        return 0
    print(f"BOOT-{stage}: 需要运行时内核实例（治理工作流 / Identity Context 验收）——"
          "模板层未实装，此为诚实边界（P-13），不模拟治理。")
    return 1


def cmd_test(suite: str | None) -> int:
    try:
        ready, missing, unwired = wiring.scan(suite=suite)
        gates = wiring.suites()
    except wiring.WiringError as e:
        print(str(e)); return 1
    print(f"套件 gate: {gates} ｜ 选中 {len(ready) + len(missing)} 项，"
          f"可执行 {len(ready)}，缺失 {len(missing)}，〔强〕项未布线 {len(unwired)}")
    if missing:
        print("WIRING-REFUSED: 声明的测试路径不存在（fail-closed，不得静默降级）:")
        for m in missing: print(f"  - {m}")
        return 1
    if not ready:
        return 0 if unwired else 1
    try:
        wiring.require_pytest()      # 执行引擎缺失 → 明确拒绝，不把 ImportError 当成套件失败
    except wiring.WiringError as e:
        print(str(e)); return 1
    paths = list(dict.fromkeys(p for _, p in ready))
    return subprocess.call([sys.executable, "-m", "pytest", "-q"] + paths, cwd=ROOT)


def main(argv: list[str] | None = None) -> int:
    """两种入口共用：console script 固定调用 main()，python -m 亦走同一路径。

    [project.scripts] 生成的 aos.exe/__main__.py 是 `sys.exit(main())`（不带参数），
    因此 argv 必须可省略；显式传参仍保留给嵌入式调用与回归测试。
    """
    argv = list(sys.argv[1:]) if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"): print(USAGE); return 0
    unavailable = _require_source_tree()
    if unavailable is not None: return unavailable
    cmd, rest = argv[0], argv[1:]
    try:
        if cmd == "spec" and rest and rest[0] == "fingerprint":
            return fingerprint.main()
        if cmd == "spec" and rest and rest[0] == "digest":
            d = hs_declaration_digest()
            print(f"DECL-DIGEST: {d or 'NONE'}  "
                  f"（已登记条目 {len(hs_decl_entries())}；无摘要/未登记时 verify 显式 SKIP）")
            return 0
        if cmd == "spec" and rest and rest[0] == "register-declarations":
            usage_d = ("用法: aos spec register-declarations <version> "
                       "[--proposal-ref SPEC-YYYY-NNN]")
            ver = _positional(rest, 1, usage_d)
            return hs_register_declarations(ver, _value(rest, "--proposal-ref", usage_d) or "")
        if cmd == "spec" and rest and rest[0] == "version":
            usage = "用法: aos spec version <new-version> --proposal-ref SPEC-YYYY-NNN"
            ver = _positional(rest, 1, usage)
            ref = _value(rest, "--proposal-ref", usage)
            return hs_supersede(ver, ref)
        if cmd == "cq":
            from tools import cq as cq_tool
            try:
                return cq_tool.main(rest)
            except cq_tool.CQError as e:
                print(f"CQ-REFUSED: {e}"); return 1
        if cmd == "verify":       return cmd_verify()
        if cmd == "register":
            return hs_register(_positional(rest, 0, "用法: aos register <version>"))
        if cmd == "init":
            usage_i = "用法: aos init <dir> [--name N] " \
                      "[--depth minimal|standard|full] [--cap ID ...] " \
                      "[--no-cap ID ...] [--interactive]"
            target = _positional(rest, 0, "用法: aos init <dir>")
            wizard: dict = {"name": _value(rest, "--name", usage_i),
                            "depth": _value(rest, "--depth", usage_i),
                            "add": [], "remove": [], "interactive": False}
            i = 0
            while i < len(rest):
                tok = rest[i]
                if tok in ("--cap", "--no-cap"):
                    if i + 1 >= len(rest) or rest[i + 1].startswith("--"):
                        raise UsageError(f"{tok} 缺能力 id —— {usage_i}")
                    (wizard["add"] if tok == "--cap" else wizard["remove"]).append(rest[i + 1])
                    i += 2
                elif tok == "--interactive":
                    wizard["interactive"] = True; i += 1
                else:
                    i += 1
            return cmd_init(target, wizard)
        if cmd == "bootstrap":
            stage_s = _value(rest, "--stage", "用法: aos bootstrap --stage N")
            if stage_s is None: print("用法: aos bootstrap --stage N"); return 1
            try:
                stage = int(stage_s)
            except ValueError:
                raise UsageError(f"--stage 须为整数，实得 {stage_s!r}")
            ref = _value(rest, "--appointment-ref", "用法: aos bootstrap --stage 1 --appointment-ref <外部凭据>")
            return cmd_bootstrap(stage, ref, "--dry-run" in rest)
        if cmd == "generate":
            unknown = [a for a in rest if a != "--force"]
            if unknown:
                raise UsageError(f"generate 不支持选项 {unknown}（仅 --force）")
            from tools.codegen import main as codegen_main
            return codegen_main("--force" in rest)
        if cmd == "release":
            from tools.release_gate import main as release_main
            return release_main()
        if cmd == "draft":
            from tools import ontology_draft as od
            if rest and rest[0] == "promote":
                args = rest[1:]
                usage = "用法: aos draft promote <draft.yaml> --proposal-ref SPEC-YYYY-NNN"
                fname = _positional(args, 0, usage)
                ref = _value(args, "--proposal-ref", usage) or ""
                try:
                    r = od.promote(Path(fname), ref)
                    print(f"PROMOTED: {r['promoted']} ｜ capabilities={r['capabilities']} "
                          f"｜ provenance={r['proposal_ref']}")
                    return 0
                except od.DraftError as e:
                    print(f"{e}"); return 1
            fname = _positional(rest, 0, "用法: aos draft <requirements.txt> --name N")
            name = _value(rest, "--name", "用法: aos draft <requirements.txt> --name N") or "default"
            try:
                report = od.draft(Path(fname), name)
            except od.DraftError as e:
                print(f"{e}"); return 1
            if report["failures"]:
                for f in report["failures"]:
                    print(f"  [FAIL] {f}")
                print("DRAFT-REFUSED: 把关未全绿 —— 草案不落盘（KS-7.1/P-2）")
                return 1
            print(f"DRAFT-OK: {report['draft']}（人确认后执行 aos draft promote）")
            return 0
        if cmd == "import-db":
            from tools.db_import import import_db, ImportRefused
            usage = "用法: aos import-db (--dsn sqlite:///db | --ddl dump.sql) " \
                    "[--name N] [--tables a,b] [--skip-failed]"
            dsn, ddl = _value(rest, "--dsn", usage), _value(rest, "--ddl", usage)
            if bool(dsn) == bool(ddl):
                raise UsageError("--dsn 与 --ddl 须二选一 —— " + usage)
            name = _value(rest, "--name", usage) or "db-import"
            only = _value(rest, "--tables", usage)
            try:
                r = import_db(dsn=dsn, ddl=Path(ddl) if ddl else None, name=name,
                              only=tuple(t.strip() for t in only.split(",")) if only else (),
                              skip_failed="--skip-failed" in rest)
            except ImportRefused as e:
                print(f"IMPORT-REFUSED: {e}")
                return 1
            print(f"IMPORT-DRAFT: {r['draft']}（source: {r['source']}，凭据不落盘）")
            print(f"对象候选: {r['objects']} ｜ 聚合候选: {r['aggregates']}")
            if r["candidate_links"]:
                print(f"候选引用 {len(r['candidate_links'])} 条"
                      "（聚合归属/引用语义由人工裁决后进正典 links）")
                for lk in r["candidate_links"]:
                    print(f"  [CANDIDATE] {lk['source']} → {lk['target']}（{lk['link_type']}）")
            for n in r["notes"]:
                print(f"  [TRANSLATED] {n}")
            for s in r["skipped"]:
                print(f"  [SKIPPED] {s}")
            print("下一步: 审核 spec/drafts/ 草案 → aos draft promote（GOV-1 提案强制）"
                  " —— 导入的是候选，不是事实")
            return 0
        if cmd == "import-data":
            from tools.data_import import import_data
            usage = "用法: aos import-data --dsn sqlite:///db --map M [--name N] [--skip-failed]"
            dsn, map_ = _value(rest, "--dsn", usage), _value(rest, "--map", usage)
            if not dsn or not map_:
                raise UsageError("--dsn 与 --map 必填 —— " + usage)
            r = import_data(dsn=dsn, mapping_path=map_,
                            name=_value(rest, "--name", usage),
                            skip_failed="--skip-failed" in rest)
            print(f"DATA-DRAFT: {r['draft']}（source: {r['source']}，凭据不落盘）")
            print(f"创世事件: 接受 {r['accepted']} 行 / 求值链拒绝 {r['rejected']} 行"
                  f" ｜ 来源表: {r['tables']}")
            print("下一步: 人工确认 data-drafts/ 事件流 → 部署期装载（须 GOV/人签，"
                  "CLI 不直写事件库）")
            return 0
        if cmd == "shadow-online":
            from tools.shadow_online import reconcile_probes, PROBE_CONTRACT
            usage = "用法: aos shadow-online <probes.ndjson>"
            pos = [a for a in rest if not a.startswith("--")]
            if not pos:
                raise UsageError("探针记录文件必填 —— " + usage)
            r = reconcile_probes(pos[0])
            print(f"SHADOW-ONLINE-{r['verdict']}（探针契约: {PROBE_CONTRACT}）")
            print(f"对账: {r['total']} 条 ｜ 一致 {r['matched']} ｜ 分歧 {r['diverged']}")
            for m in r["mismatches"][:20]:
                for d in m["diffs"]:
                    print(f"  [DIFF] 行 {m['line']} {m['action']} [{d['kind']}]"
                          f" legacy={d.get('legacy')!r} modern={d.get('modern')!r}")
            if r["verdict"] == "DIVERGED":
                print("下一步: 分歧清单进 aos review 人工裁决（语义映射修正或本体补声明）")
            return 0
        if cmd == "extract":
            from tools.semantic_extract import extract
            usage = "用法: aos extract <file> --name N [--extractor script.py]"
            pos = [a for a in rest if not a.startswith("--")]
            if not pos:
                raise UsageError("素材文件必填 —— " + usage)
            r = extract(pos[0], _value(rest, "--name", usage) or Path(pos[0]).stem,
                        _value(rest, "--extractor", usage))
            if "draft" in r:
                print(f"EXTRACT-DRAFT: {r['draft']}")
                print(f"来源: {r['extractor']} ｜ 候选 {len(r['decls']['objects'])} 个 ｜ "
                      f"置信度: {r['confidence']}")
                print("纪律: 候选不是事实 —— 晋升须 aos draft promote --proposal-ref（GOV-1）")
            else:
                print("EXTRACT-REFUSED（闸门失败，未落盘）:")
            for f in r.get("failures", []):
                print(f"  [GATE] {f}")
            for n in r.get("notes", []):
                print(f"  [NOTE] {n}")
            return 0
        if cmd == "shadow":
            from tools.shadow import shadow_reconcile
            usage = "用法: aos shadow --dsn sqlite:///db --map M"
            dsn, map_ = _value(rest, "--dsn", usage), _value(rest, "--map", usage)
            if not dsn or not map_:
                raise UsageError("--dsn 与 --map 必填 —— " + usage)
            r = shadow_reconcile(dsn, map_)
            print(f"SHADOW-{r['verdict']}（source: {r['source']}，凭据不落盘）")
            print(f"对账: {r['rows']} 行 ｜ 字段一致 {r['matched_fields']} ｜ "
                  f"差异 {r['mismatched']} ｜ 求值链拒绝 {r['rejected']}")
            if r["uncovered_columns"]:
                print(f"对账盲区（源列未被映射覆盖，如实披露）: {r['uncovered_columns']}")
            for m in r["mismatches"][:20]:
                print(f"  [DIFF] 行 {m['row']} [{m['kind']}] {m.get('field', '')}"
                      f" 期望 {m.get('expected', '-')} 实际 {m.get('actual', '-')}"
                      if m["kind"] != "rejection" else
                      f"  [REJECT] 行 {m['row']}: {m['detail']}")
            if r["verdict"] == "DIVERGED":
                print("下一步: 差异清单进 aos review 人工裁决（映射修正或本体补声明）")
            return 0
        if cmd == "review":
            from tools.review import review_report, format_report
            from kernel.profile import ProfileError
            usage = "用法: aos review [--out docs/REVIEW.md]"
            try:
                r = review_report()
            except ProfileError as e:
                print(f"REVIEW-REFUSED: {e}")
                return 1
            text = format_report(r)
            out = _value(rest, "--out", usage)
            if out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_bytes(text.encode("utf-8"))
                print(f"REVIEW-WRITTEN: {out}")
            else:
                print(text)
            return 0
        if cmd == "manual":
            from tools.domain_manual import main as manual_main
            usage = "用法: aos manual [--out docs/DOMAIN-MANUAL.md]"
            out = _value(rest, "--out", usage)
            unknown = [a for a in rest if a != "--out" and a != out]
            if unknown:
                raise UsageError(f"manual 不支持参数 {unknown} —— {usage}")
            return manual_main(out)
        if cmd == "metrics":  return gate_history.report()
        if cmd == "audit":
            from tools.audit_export import main as audit_main
            return audit_main(rest)
        if cmd == "profile":
            from kernel.profile import resolve as profile_resolve, ProfileError, ANCHORS
            try:
                r = profile_resolve()
            except ProfileError as e:
                print(f"REFUSED: {e}")
                return 1
            declared = sum(1 for s in r["selected"].values() if s == "declared")
            implied = len(r["selected"]) - declared
            print(f"PROFILE: {r['project']} —— 选定 {len(r['selected'])} 项"
                  f"（声明 {declared} / 自动展开 {implied}）")
            print("生成顺序: " + " → ".join(r["order"]))
            if r["failures"]:
                for f in r["failures"]:
                    print(f"  [FAIL] {f}")
                print("PROFILE-REFUSED: 锚点缺失 —— 计划不可执行（fail-closed）")
                return 1
            for a in sorted(ANCHORS.values()):
                n = len(list((ROOT / "spec" / a).glob("*.yaml"))) if (ROOT / "spec" / a).exists() else 0
                print(f"  锚点 spec/{a}/: OK（{n} 条声明）")
            print("PROFILE-OK: 生成计划就绪（本命令只出计划；代码生成按模块逐个接入）")
            return 0
        if cmd == "impact":
            from tools.impact import report as impact_report
            return impact_report(
                _positional(rest, 0, "用法: aos impact <声明路径|声明名|ObjectType.prop>"))
        if cmd == "test":
            suite = _value(rest, "--suite", "用法: aos test [suite|--suite S]")
            pos = [a for a in rest if not a.startswith("--")
                   and rest[max(0, rest.index(a) - 1)] not in ("--suite",)]
            suite = suite or (pos[0] if pos else None)   # 位置参数优先（复盘修复：
            return cmd_test(suite)                        # 此前被静默丢弃）
        print(USAGE); return 1
    except UsageError as e:
        print(f"REFUSED: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())          # 与 console script 完全同构，避免两条入口再次分叉
