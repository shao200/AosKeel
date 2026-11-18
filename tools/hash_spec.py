#!/usr/bin/env python3
"""GOV-2.3 分离式哈希 —— 密码学层的唯一执行点。
规则：
- 覆盖域：CANONICAL_FILES 全部正典文件，按声明顺序拼接（含指纹清单，
  附录 F 核对规则："本清单与全文一并入哈希覆盖域"）；
- 分离性：登记文件自身不在覆盖域 —— 自指哈希不可构造，寻址外置；
- 只增性：登记表 append-only。同哈希重跑 = 幂等成功；哈希漂移 = 冻结文本
  被就地修改 → 拒绝并指向 GOV-3 通道（把 GOV-2.5"传输缺陷不修冻结文本"
  落成仓库规则）；
- 回填：capabilities.yaml 记登记条目 ID，禁止内联哈希（GOV-2.2）。

GOV-2.3-DECL（第四道比对）：冻结正典之外，spec/ 下的九类声明同样承载业务
语义（条件阈值、权限、副作用）。它们不进入 CANONICAL_FILES —— 那会改动
e6884aed… 历史封存基线（v2.0.0 登记行逐字保留）；改为独立的"声明摘要"条目登记进同一 append-only 表，
verify 时一并比对。未登记（如 aos init 生成的实例未复制登记表）显式 SKIP，
不把"没有基线"伪装成"校验通过"。spec/drafts/ 是工作区草案，不入摘要域。
"""
import hashlib, sys, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CANONICAL_FILES = [                    # 顺序即规范：改顺序 = 改工件
    "docs/aos-spec.md",
    "docs/SPEC-FINGERPRINT.md",
]
REGISTRY = ROOT / "docs/ARTIFACT-REGISTRY.md"
CAPS     = ROOT / "config/capabilities.yaml"
def canonical_digest() -> str:
    h = hashlib.sha256()
    for rel in CANONICAL_FILES:
        p = ROOT / rel
        if not p.exists():
            sys.exit(f"STRUCTURAL-FAIL: 正典文件缺失: {rel}")      # GOV-2.5 结构层
        h.update(rel.encode()); h.update(b"\x00")               # 文件名入域
        h.update(p.read_bytes()); h.update(b"\x00")             # 内容入域
    return h.hexdigest()
def _entries():
    if not REGISTRY.exists(): return []
    return [l for l in REGISTRY.read_text().splitlines() if l.startswith("| AOS-ART-")]
def _next_id() -> str:
    n = max([int(l.split("|")[1].strip().rsplit("-", 1)[-1]) for l in _entries()], default=0)
    return f"AOS-ART-{n+1:03d}"
def _set_spec_ref(art_id: str):
    """登记条目 ID 回填到两份配置：capabilities.yaml（GOV-2.2 溯源）与
    verification.yaml（布线件同源，GOV-3 版本更替时不再留占位符漂移）。
    文件不存在则跳过（实例侧可裁剪布线）；字节写入遵守 `* -text`。"""
    for path in (CAPS, ROOT / "config/verification.yaml"):
        if not path.exists():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        out = [f"spec_ref: {art_id}   # 登记条目 ID（GOV-2.2）；哈希见登记表"
               if l.strip().startswith("spec_ref:") else l for l in lines]
        path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))
def register(spec_version: str) -> int:
    digest = canonical_digest()
    rows = _entries()
    if rows and digest in rows[-1]:
        print(f"IDEMPOTENT: 已登记为 {rows[-1].split('|')[1].strip()}"); return 0
    if rows:
        sys.exit("FROZEN-TEXT-MUTATED: 正典哈希与最近登记不符 —— 冻结文本不得就地"
                 "修改；走 GOV-3 产生新版本后重新登记。")
    art_id, now = _next_id(), datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not REGISTRY.exists():
        REGISTRY.write_bytes(("# AOS 工件登记（append-only；GOV-2.3）\n\n"
                              "| 条目 ID | 版本 | 哈希 | 登记时间 | 状态 |\n"
                              "|---|---|---|---|---|\n").encode("utf-8"))
    with REGISTRY.open("ab") as f:                 # 字节追加：文本模式会写入 CRLF
        f.write(f"| {art_id} | {spec_version} | sha256:{digest} | {now} | registered |\n"
                .encode("utf-8"))
    _set_spec_ref(art_id)
    print(f"REGISTERED: {art_id}  sha256:{digest[:16]}…"); return 0
def supersede(spec_version: str, proposal_ref: str) -> int:
    """GOV-3 版本通道（CLI: aos spec version）：治理提案产生的规范新版本，
    以新登记条目取代前一登记（append-only，P-15 —— 旧行永不改写）。
    护栏（GOV-1 精神）：无 proposal_ref 一律拒绝 —— CLI 只记录治理结果，不合成版本。"""
    if not proposal_ref:
        sys.exit("REFUSED: 冻结文本版本更替 MUST 绑定治理提案（GOV-3）—— "
                 "用法: aos spec version <new-version> --proposal-ref SPEC-YYYY-NNN")
    digest = canonical_digest()
    rows = _entries()
    if rows and digest in rows[-1]:
        print(f"IDEMPOTENT: 当前文本已登记为 {rows[-1].split('|')[1].strip()}"); return 0
    art_id = _next_id()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not REGISTRY.exists():
        REGISTRY.write_bytes(("# AOS 工件登记（append-only；GOV-2.3）\n\n"
                              "| 条目 ID | 版本 | 哈希 | 登记时间 | 状态 |\n"
                              "|---|---|---|---|---|\n").encode("utf-8"))
    with REGISTRY.open("ab") as f:                 # 字节追加：文本模式会写入 CRLF
        f.write(f"| {art_id} | {spec_version} | sha256:{digest} | {now} | registered |\n"
                .encode("utf-8"))
        f.write(f"# superseded-via: {proposal_ref} → {art_id}（GOV-3 版本通道；"
                f"前一登记条目由本条目取代，旧行不改写——append-only P-15）\n"
                .encode("utf-8"))
    _set_spec_ref(art_id)
    print(f"SUPERSEDED: {art_id}  sha256:{digest[:16]}…  proposal={proposal_ref}")
    return 0
DECL_PREFIX = "AOS-DECL-"
DECL_SECTION = ("\n## 声明摘要登记（GOV-2.3-DECL；append-only；独立于冻结正典域）\n\n"
                "| 条目 ID | 版本 | 声明摘要 | 登记时间 | 状态 |\n"
                "|---|---|---|---|---|\n")
def declaration_files() -> list[Path]:
    """摘要覆盖域：spec/ 下全部 *.yaml，排除 drafts（工作区草案不入正典）。
    按 POSIX 相对路径排序 —— 顺序即规范，与正典覆盖域同一纪律。"""
    d = ROOT / "spec"
    if not d.is_dir():
        return []
    return sorted(p for p in d.rglob("*.yaml")
                  if "drafts" not in p.relative_to(ROOT).parts)
def declaration_digest() -> str | None:
    """返回 spec/ 声明摘要 sha256；无声明文件时返回 None（SKIP 的信号）。"""
    files = declaration_files()
    if not files:
        return None
    h = hashlib.sha256()
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        h.update(rel.encode()); h.update(b"\x00")
        h.update(p.read_bytes()); h.update(b"\x00")
    return h.hexdigest()
def _decl_entries():
    if not REGISTRY.exists():
        return []
    return [l for l in REGISTRY.read_text(encoding="utf-8").splitlines()
            if l.startswith(f"| {DECL_PREFIX}")]
def _next_decl_id() -> str:
    n = max([int(l.split("|")[1].strip().rsplit("-", 1)[-1])
             for l in _decl_entries()], default=0)
    return f"{DECL_PREFIX}{n+1:03d}"
def register_declarations(spec_version: str, proposal_ref: str = "") -> int:
    """登记当前 spec/ 声明摘要（append-only；不改冻结正典、不改 e6884aed…）。
    首次登记无需提案；后续漂移 MUST 绑定治理提案引用（GOV-1/3 同源护栏），
    以新条目取代前者，旧行逐字保留。"""
    digest = declaration_digest()
    if digest is None:
        sys.exit("REFUSED: spec/ 下无可摘要的 *.yaml —— 无登记对象")
    rows = _decl_entries()
    if rows and digest in rows[-1]:
        print(f"IDEMPOTENT: 声明摘要已登记为 {rows[-1].split('|')[1].strip()}"); return 0
    superseded = bool(rows)
    if superseded and not proposal_ref:
        sys.exit("DECL-FROZEN-MUTATED: 声明摘要与最近登记不符 —— 业务声明不得就地"
                 "修改；带 --proposal-ref SPEC-YYYY-NNN 走治理变更后登记。")
    art_id, now = _next_decl_id(), datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    if not REGISTRY.exists():
        REGISTRY.write_bytes(("# AOS 工件登记（append-only；GOV-2.3）\n\n"
                              "| 条目 ID | 版本 | 哈希 | 登记时间 | 状态 |\n"
                              "|---|---|---|---|---|\n").encode("utf-8"))
    with REGISTRY.open("ab") as f:                 # 字节追加：文本模式会写入 CRLF
        if DECL_SECTION.strip() not in REGISTRY.read_text(encoding="utf-8"):
            f.write(DECL_SECTION.encode("utf-8"))
        f.write(f"| {art_id} | {spec_version} | sha256:{digest} | {now} | registered |\n"
                .encode("utf-8"))
        if superseded:
            f.write(f"# decl-superseded-via: {proposal_ref} → {art_id}（GOV-3 声明变更通道；"
                    f"旧登记行不改写——append-only P-15）\n".encode("utf-8"))
    print(f"DECL-REGISTERED: {art_id}  sha256:{digest[:16]}…  "
          f"（{len(declaration_files())} 份声明；冻结正典未动"
          f"{'；提案 ' + proposal_ref if superseded else ''}）")
    return 0
def verify_declarations() -> int:
    """第四道：声明摘要比对。无声明 / 未登记 → 显式 SKIP（不伪装成 PASS）。"""
    digest = declaration_digest()
    rows = _decl_entries()
    if digest is None:
        print("  DECL-DIGEST: SKIP —— 无 spec/*.yaml（实例裁剪）")
        return 0
    if not rows:
        print("  DECL-DIGEST: SKIP —— 未登记（实例自行登记；GOV-2.3-DECL）")
        return 0
    ok = digest in rows[-1]
    print(("  OK       " if ok else "  MISMATCH ") +
          f"DECL sha256:{digest[:16]}…  （{len(declaration_files())} 份声明）")
    return 0 if ok else 1
def verify() -> int:
    rows = _entries()
    if not rows: sys.exit("NOT-REGISTERED: 先执行 aos register（BOOT-0）")
    digest = canonical_digest()
    ok = digest in rows[-1]
    print(("OK       " if ok else "MISMATCH ") + f"computed sha256:{digest[:16]}…")
    decl_ok = verify_declarations()                 # 第四道：业务声明摘要
    return 0 if ok and decl_ok == 0 else 1
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    if cmd == "register":
        sys.exit(register(sys.argv[2]))
    if cmd == "register-declarations":
        ref = sys.argv[3] if len(sys.argv) > 3 else ""
        sys.exit(register_declarations(sys.argv[2], ref))
    sys.exit(verify())
