#!/usr/bin/env python3
"""src/cli/main.py —— 薄分发器（六命令，命令表驱动；make 目标保留为 CI 封装）。
aos verify 三关串联：结构层（指纹 GOV-2.4）→ 密码学层（哈希 GOV-2.3）→
注册层（declared == registered，KS-7.2 第 5 步）。任一失败 → exit 1。
护栏一（GOV-1）：bootstrap --stage 1 强制 --appointment-ref —— 拒绝合成创制任命。
"""
import sys, shutil, json, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.hash_spec import (canonical_digest, _entries, register as hs_register,
                             verify as hs_verify, supersede as hs_supersede)
from tools import fingerprint
from kernel import registration
USAGE = """\
用法: aos <command>
  init <dir>            实例化模板；写 TEMPLATE-LOCK        目标已存在 → 拒绝
  verify                三关: 指纹 → 哈希 → declared==registered   任一失败 → exit 1
  register <version>    GOV-2.3 登记                         同哈希幂等；漂移 → 拒绝
  bootstrap --stage N   BOOT-0..3；--dry-run 只跑检查表不写入  阶段乱序 → 拒绝
  test [--suite S]      按 verification.yaml 分组             套件失败 → exit 1
  spec fingerprint      独立结构层核对（GOV-2.5 分歧二分）     报缺 → exit 1
  spec version <v>      GOV-3 版本通道：新版本登记（append-only）
                        --proposal-ref SPEC-YYYY-NNN 强制      缺 → 拒绝
  generate [--force]    声明 → 代码骨架（actions/reducers，provenance 头）
                        手改检测：不一致 → 拒绝静默覆盖；--force 显式覆盖
  release               发布闸门（fail-closed）：三关 + 布线套件 + 骨架一致性
                        全绿 → dist/RELEASE-MANIFEST.json；任一失败 → 不出制品
  draft <file>          需求 DSL → 本体草案（解析→编译把关；全绿才写 spec/drafts/）
                        --name N 命名草案；编译不过逐条报告，不落盘
  draft promote <f>     草案晋升正典（--proposal-ref SPEC-YYYY-NNN 强制，GOV-1）
                        目标已存在 → 拒绝（GOV-3 通道）；晋升含 apply_generated（P-5）
"""
def cmd_verify() -> int:
    print("[1/3] 结构层（指纹 GOV-2.4）")
    failures = fingerprint.check()
    if failures:
        print("  STRUCTURAL-MISMATCH（GOV-2.5）:")
        for f in failures: print(f"    - {f}")
        return 1
    print("  OK —— 附录 F 十节三元组在场")
    print("[2/3] 密码学层（分离式哈希 GOV-2.3）")
    if hs_verify() != 0: return 1
    print("[3/3] 注册层（declared == registered，KS-7.2 / INV-13）")
    try:
        gen = registration.run_pipeline()
        n = len(gen["write_actions"]) + len(gen["channel_writes"])
        print(f"  OK —— {n} 条能力一致（含 provenance 回溯）")
    except registration.RegistrationFailed as e:
        print(f"  REGISTRATION-FAILED: {e}"); return 1
    print("VERIFY-OK: 三关连续通过 —— 结构 / 密码学 / 注册")
    return 0
def cmd_init(target: str) -> int:
    dst = Path(target).resolve()
    if dst.exists():
        print(f"REFUSED: 目标已存在 {dst} —— init 不覆盖（护栏）"); return 1
    dst.mkdir(parents=True)
    EXCLUDE = {"__pycache__", ".aos", "drafts"}          # drafts=工作区，不入实例
    copied = 0
    for d in ("docs", "config", "spec", "tools", "src", "tests", "bootstrap", ".github"):
        src_dir = ROOT / d
        if not src_dir.exists(): continue
        for p in src_dir.rglob("*"):
            if p.is_dir() or any(part in EXCLUDE for part in p.parts): continue
            if p.name in ("ARTIFACT-REGISTRY.md", "TEMPLATE-LOCK.md"):
                continue                     # 实例自行登记（GOV-2.3）；LOCK 由本命令写入
            rel = p.relative_to(ROOT)
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel); copied += 1
    rows = _entries()
    art_id = rows[-1].split("|")[1].strip() if rows else "NOT-REGISTERED"
    spec_ver = "v2.0.0"
    snap_ok = not fingerprint.check((dst / "docs/aos-spec.md").read_text(encoding="utf-8"))
    lock = (f"# TEMPLATE-LOCK（init 时写入；版本绑定）\n\n"
            f"- template_version: 0.3\n- spec_version: {spec_ver}\n"
            f"- registry_entry: {art_id}\n"
            f"- fingerprint_snapshot: {'PASS' if snap_ok else 'FAIL'}\n"
            f"- files_copied: {copied}\n"
            f"- 规范副本哈希绑定登记条目 {art_id}；实例内 aos verify 校验"
            f"副本哈希 = 登记哈希，改动即 FROZEN-TEXT-MUTATED（INV-12）\n"
            f"- 下一步: aos bootstrap --stage 0（实例自行登记为首个 AOS-ART 条目）\n")
    (dst / "docs/TEMPLATE-LOCK.md").write_text(lock, encoding="utf-8")
    print(f"INITIALIZED: {dst}（{copied} 文件；TEMPLATE-LOCK: template 0.3 × {spec_ver} × {art_id}）")
    print("下一步: cd 实例 && python src/cli/main.py bootstrap --stage 0")
    return 0
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
        code = hs_register("v2.0.0") or cmd_verify()
        if code == 0:
            marker_dir.mkdir(exist_ok=True)
            (marker_dir / "boot-0.done").write_text(
                f"art={(_entries()[-1].split('|')[1].strip() if _entries() else 'NONE')}\n",
                encoding="utf-8")
            print("BOOT-0-DONE: 内核部署 + 能力清单发布 + 工件哈希登记（附录 E 激活）")
        return code
    if stage == 1:
        if not appointment_ref:                                   # 护栏一
            print("REFUSED: BOOT-1 强制 --appointment-ref <外部凭据> —— "
                  "CLI 只记录创制任命，拒绝合成创制任命（GOV-1）"); return 1
        marker_dir.mkdir(exist_ok=True)
        (marker_dir / "boot-1.json").write_text(json.dumps(
            {"appointment_ref": appointment_ref, "note":
             "创制任命是世界事件；此处仅记录引用，不制造正当性（AX-4/GOV-1）"},
            ensure_ascii=False, indent=2), encoding="utf-8")
        (marker_dir / "boot-1.done").write_text("recorded\n", encoding="utf-8")
        print(f"BOOT-1-RECORDED: 创制任命引用已留档（audit 第一条由运行时内核落账）")
        return 0
    print(f"BOOT-{stage}: 需要运行时内核实例（治理工作流 / Identity Context 验收）——"
          "模板层未实装，此为诚实边界（P-13），不模拟治理。")
    return 1
def cmd_test(suite: str | None) -> int:
    import re
    text = (ROOT / "config/verification.yaml").read_text(encoding="utf-8")
    entries = re.findall(r"-\s\{\s*id:\s*(VER-\d+),.*?path:\s*([^\s}]+)", text)
    suites = dict(re.findall(r"(?m)^\s{2}(\w+):\s\{\sgate:\s(\w+)", text))
    picked = [e for e in entries if suite is None or f"tests/{suite}/" in e[1]]
    existing = [(i, p) for i, p in picked if (ROOT / p).exists()]
    missing  = [i for i, p in picked if not (ROOT / p).exists()]
    print(f"套件 gate: {suites} ｜ 选中 {len(picked)} 项，可执行 {len(existing)}，"
          f"未实例化 {len(missing)}")
    if missing:
        print("NOT-INSTANTIATED（实例侧职责/〔强〕项为检查表留档，不在模板内伪装通过）:")
        for m in missing: print(f"  - {m}")
    if not existing:
        return 0 if missing else 1
    return subprocess.call([sys.executable, "-m", "pytest", "-q"] + [p for _, p in existing], cwd=ROOT)
def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"): print(USAGE); return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "spec" and rest and rest[0] == "fingerprint":
        return fingerprint.main()
    if cmd == "spec" and rest and rest[0] == "version":
        ver = rest[1] if len(rest) > 1 else None
        ref = rest[rest.index("--proposal-ref") + 1] if "--proposal-ref" in rest else None
        if not ver:
            print("用法: aos spec version <new-version> --proposal-ref SPEC-YYYY-NNN")
            return 1
        return hs_supersede(ver, ref)
    if cmd == "verify":       return cmd_verify()
    if cmd == "register":
        if not rest: print("用法: aos register <version>"); return 1
        return hs_register(rest[0])
    if cmd == "init":
        if not rest: print("用法: aos init <dir>"); return 1
        return cmd_init(rest[0])
    if cmd == "bootstrap":
        stage, ref, dry = None, None, False
        it = iter(rest)
        for a in it:
            if a == "--stage": stage = int(next(it))
            elif a == "--appointment-ref": ref = next(it)
            elif a == "--dry-run": dry = True
        if stage is None: print("用法: aos bootstrap --stage N"); return 1
        return cmd_bootstrap(stage, ref, dry)
    if cmd == "generate":
        from tools.codegen import main as codegen_main
        return codegen_main("--force" in rest)
    if cmd == "release":
        from tools.release_gate import main as release_main
        return release_main()
    if cmd == "draft":
        from tools import ontology_draft as od
        if rest and rest[0] == "promote":
            args = rest[1:]
            ref = (args[args.index("--proposal-ref") + 1]
                   if "--proposal-ref" in args else "")
            try:
                r = od.promote(Path(args[0]), ref)
                print(f"PROMOTED: {r['promoted']} ｜ capabilities={r['capabilities']} "
                      f"｜ provenance={r['proposal_ref']}")
                return 0
            except od.DraftError as e:
                print(f"{e}"); return 1
        fname = rest[0] if rest else ""
        name = (rest[rest.index("--name") + 1] if "--name" in rest else "default")
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
    if cmd == "test":
        suite = rest[rest.index("--suite") + 1] if "--suite" in rest else None
        return cmd_test(suite)
    print(USAGE); return 1
if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
