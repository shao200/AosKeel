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
    text = CAPS.read_text().splitlines()
    out = [f"spec_ref: {art_id}   # 登记条目 ID（GOV-2.2）；哈希见登记表"
           if l.strip().startswith("spec_ref:") else l for l in text]
    CAPS.write_text("\n".join(out) + "\n")
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
        REGISTRY.write_text("# AOS 工件登记（append-only；GOV-2.3）\n\n"
                            "| 条目 ID | 版本 | 哈希 | 登记时间 | 状态 |\n|---|---|---|---|---|\n")
    with REGISTRY.open("a") as f:
        f.write(f"| {art_id} | {spec_version} | sha256:{digest} | {now} | registered |\n")
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
        REGISTRY.write_text("# AOS 工件登记（append-only；GOV-2.3）\n\n"
                            "| 条目 ID | 版本 | 哈希 | 登记时间 | 状态 |\n|---|---|---|---|---|\n")
    with REGISTRY.open("a") as f:
        f.write(f"| {art_id} | {spec_version} | sha256:{digest} | {now} | registered |\n")
        f.write(f"# superseded-via: {proposal_ref} → {art_id}（GOV-3 版本通道；"
                f"前一登记条目由本条目取代，旧行不改写——append-only P-15）\n")
    _set_spec_ref(art_id)
    print(f"SUPERSEDED: {art_id}  sha256:{digest[:16]}…  proposal={proposal_ref}")
    return 0
def verify() -> int:
    rows = _entries()
    if not rows: sys.exit("NOT-REGISTERED: 先执行 aos register（BOOT-0）")
    digest = canonical_digest()
    ok = digest in rows[-1]
    print(("OK       " if ok else "MISMATCH ") + f"computed sha256:{digest[:16]}…")
    return 0 if ok else 1
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "verify"
    sys.exit(register(sys.argv[2]) if cmd == "register" else verify())
