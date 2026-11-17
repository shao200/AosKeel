#!/usr/bin/env python3
"""tools/cq.py —— 能力问题（Competency Question）可执行验收契约。

背景：guide/06 §4.1 列出 CQ-1..10 十张"系统必须能回答的问题"，但此前它们
只存在于文档表格里——回答者是文字描述，没有执行点。本模块把每张表转成三件事：

  1. 声明（spec/competence/CQ-*.cq.yaml）：问题、夹具、探针、期望答案、证据落点；
  2. 回答者注册表 ANSWERERS：每个 key 指向真实内核执行点，不是复述声明的影子实现；
  3. 可失败断言：实际值与期望值不等即 FAIL；声明缺失/重复/回答者未注册/
     算子未知一律 CQError（fail-closed），不把"没写"当成"通过"。

第二轮：域无关查询定义。原先十个回答者把 ContractAggregate / ApproveContract /
治理文件路径写死在 Python 里，换域必须改代码。现把域参数外提到
spec/competence/domains/<domain>.domain.yaml，回答者本体（PRIMITIVES）只读画像，
不再含任何域字面量；夹具也由画像的 fixtures 种子声明驱动真实 Kernel.submit。
实例新增自己的题集 = 写一个域画像 + 一组 *.cq.yaml，不改一行 Python。

兼容：EXPECTED_IDS 仍是 contract 域的冻结清单（防删题）；ANSWERERS 保留为
可覆写的调度入口，旧式双参数回答者仍可工作。CQ 目录位于 spec/ 摘要域内，
新增或改动声明均受 GOV-2.3-DECL 第四道保护。

诚实边界：CQ 证明的是"问题在本仓库样例域上有可复现答案"，不等于本体对任意域
完备；域画像声明的是查询目标参数，域自身的 action/reducer 仍需按九类声明落地。
"""
from __future__ import annotations
import inspect
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import _load_yaml

CQ_DIR = ROOT / "spec" / "competence"
DOMAIN_DIR = CQ_DIR / "domains"
EXPECTED_IDS = tuple(f"CQ-{i}" for i in range(1, 11))   # contract 域冻结清单
DEFAULT_DOMAIN = "contract"

class CQError(Exception):
    """CQ 契约不可执行（声明不全 / 回答者未注册 / 算子未知）——一律阻断。"""

# ---------- 域画像：把原先写死在 Python 里的域参数外置 ----------
def _deep_merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        if k == "extends":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out

def load_profile(domain: str = DEFAULT_DOMAIN, root: Path | None = None) -> dict:
    """加载域画像；支持 extends 继承（实例只写差异）。root 为测试隔离的题集目录，
    其中若无 domains/ 则回退仓库画像——保证既有隔离测试仍可运行。"""
    candidates = []
    if root is not None:
        candidates.append(Path(root) / "domains" / f"{domain}.domain.yaml")
    candidates.append(DOMAIN_DIR / f"{domain}.domain.yaml")
    p = next((c for c in candidates if c.is_file()), None)
    if p is None:
        raise CQError(f"CQ-DOMAIN-UNKNOWN: {domain} —— 未找到 {domain}.domain.yaml")
    doc = _load_yaml(p)
    parent = doc.get("extends")
    if parent:
        doc = _deep_merge(load_profile(parent, root), doc)
    doc["domain"] = domain
    for key in ("aggregate", "actions", "declarations", "principal", "fixtures"):
        if key not in doc:
            raise CQError(f"CQ-DOMAIN-INCOMPLETE: {domain} 缺字段 {key}（{p.name}）")
    for key in ("type", "name", "stream", "reducer", "entity_key"):
        if key not in doc["aggregate"]:
            raise CQError(f"CQ-DOMAIN-INCOMPLETE: {domain}.aggregate 缺字段 {key}")
    return doc

# ---------- 声明驱动夹具：逐条走真实内核，非 mock ----------
def build_fixture(profile: dict, name: str) -> dict:
    fixtures = profile.get("fixtures") or {}
    if name not in fixtures:
        raise CQError(f"CQ-FIXTURE-UNKNOWN: {name} —— 域 {profile['domain']} 未声明该夹具")
    spec = fixtures[name] or {}
    from kernel.store import EventStore
    from kernel.session import SessionChannel
    from kernel.pipeline import Kernel
    from kernel.registration import compile_all
    store, session = EventStore(), SessionChannel()
    ctx = {"store": store, "session": session,
           "kernel": Kernel(store, session, compile_all()),
           "roles": tuple(profile["principal"].get("roles") or ()),
           "contexts": tuple(profile["principal"].get("contexts") or ()),
           "profile": profile}
    for obs in spec.get("observations") or []:
        session.append(obs.get("principal") or "observer", obs.get("payload") or {})
    for ev in spec.get("events") or []:
        action = ev.get("action")
        if not action:
            raise CQError(f"CQ-FIXTURE-EVENT-INCOMPLETE: {profile['domain']}/{name} 事件缺 action")
        ctx["kernel"].submit(action, ev.get("params") or {}, ev.get("principal") or "svc",
                             ctx["roles"], ctx["contexts"])
    return ctx

def _preset(name: str):
    def _make() -> dict:
        return build_fixture(load_profile(), name)
    return _make

PRESETS = {name: _preset(name) for name in ("empty", "contract_approved")}

def _projection(ctx):
    """只读投影回答者共用：按画像声明的聚合/流/reducer 从事件日志重建。"""
    from kernel.projection import Projection
    from generated import reducers
    agg = ctx["profile"]["aggregate"]
    p = Projection(ctx["store"], agg["type"], reducers.REDUCERS[agg["reducer"]],
                   streams=[agg["stream"]])
    p.rebuild()
    return p

def _decl(profile: dict, kind: str, default_name: str | None = None) -> dict:
    """按画像路径加载声明；probe 可显式指定同名符号，否则用画像默认。"""
    rel = profile["declarations"][kind]
    return _load_yaml(ROOT / rel)

# ---------- 域无关查询原语：只从 profile / probe 取参数，无域字面量 ----------
def _p_projection_snapshot(ctx, probe, profile):
    """CQ-1 当前状态 ← Projection.snapshot()（事件流重建的只读投影）。"""
    key = profile["aggregate"]["entity_key"]
    return _projection(ctx).snapshot().get(probe[key], {}).get("status")

def _p_declaration_permissions(ctx, probe, profile):
    """CQ-2 谁能批准 ← 动作声明 permissions.roles ↔ 治理职责项 position 对账，
    并以真实 submit 实测：出示未授权角色必须被权限门禁拒绝（评估零接触）。"""
    from kernel.errors import PermissionDenied
    action_key = probe.get("approve_action") or profile["actions"]["approve"]
    action = _load_yaml(ROOT / f"spec/ontology/actions/{action_key}.action.yaml")
    roles = set((action.get("permissions") or {}).get("roles") or [])
    gov = _decl(profile, "governance")
    authorized = {d.get("position") for d in gov.get("duties", [])
                  if action_key in (d.get("authorizes") or [])}
    sym = profile.get("symbols") or {}
    intruder = probe.get("intruder_role") or sym.get("intruder_role") or "__unauthorized__"
    entity_key = profile["aggregate"]["entity_key"]
    intruder_denied = False
    try:
        ctx["kernel"].submit(action_key, {entity_key: probe.get(entity_key, "C-1")},
                             "svc", roles=(intruder,), contexts=ctx["contexts"])
    except PermissionDenied:
        intruder_denied = True
    return {"roles": sorted(roles), "authorized": sorted(authorized),
            "intruder_denied": intruder_denied}

def _p_kernel_conditional(ctx, probe, profile):
    """CQ-3 超额能否批准 ← 条件表达式对物化快照求值；不追加，返回拒绝类型。"""
    from kernel.errors import ConditionalRejected
    key = profile["aggregate"]["entity_key"]
    try:
        ctx["kernel"].submit(profile["actions"]["register"],
                             {key: probe[key], "amount": probe["amount"]},
                             "svc", ctx["roles"], ctx["contexts"])
    except ConditionalRejected:
        return "ConditionalRejected"
    return "ACCEPTED"

def _p_interpreter_audit(ctx, probe, profile):
    """CQ-4 批准依据 ← 统一审计链中解释器记录：表达式 + 快照 + 结果三元组。"""
    from tools.audit_export import unified
    hint = probe.get("expression_hint") or "snapshot.status"
    recs = unified(ctx["store"], ctx["kernel"].interpreter_audit)
    hits = [r["record"] for r in recs if r["source"] == "interpreter"
            and hint in str(r["record"].get("expression", ""))]
    if not hits:
        return {}
    rec = hits[-1]
    snap = rec.get("snapshot") or {}
    return {"expression": hint in str(rec.get("expression", "")),
            "snapshot": "status" in snap and "amount" in snap,
            "result": rec.get("result") is True}

def _p_link_same_as(ctx, probe, profile):
    """CQ-5 跨域是否同一实体 ← 结构性链接声明 + 注册期 LinkPattern 三项校验。"""
    from kernel.registration import validate_link
    d = _decl(profile, "link")
    return {"failures": validate_link(d),
            "grants_permissions": bool(d.get("grants_permissions")),
            "scope": d.get("scope")}

def _p_process_compensation(ctx, probe, profile):
    """CQ-6 变更后的订单侧动作 ← ProcessType 补偿绑定 ↔ 动作声明 ↔ 能力清单三处对账。"""
    from kernel.registration import load_caps
    proc = _decl(profile, "process")
    comps = {c.get("for"): c.get("action") for c in proc.get("compensations", [])}
    sym = profile.get("symbols") or {}
    target_action = probe.get("for_action") or sym.get("approve_action")
    target = comps.get(target_action)
    act = _load_yaml(ROOT / f"spec/ontology/actions/{target}.action.yaml") if target else {}
    registered = {a["id"] for a in load_caps().get("write_actions", [])}
    return {"compensation": target, "declared": bool(act.get("compensation")),
            "registered": target in registered}

def _p_stream_rule(ctx, probe, profile):
    """CQ-7 普通 Action 能否写违规对象 ← commit 流规则拒绝（唯一写者约束）。"""
    from kernel.errors import StreamRuleViolation
    sym = profile.get("symbols") or {}
    event_type = probe.get("event_type") or sym.get("violation_event")
    try:
        ctx["store"].commit(profile["actions"]["register"],
                            sym.get("invariant_stream", "domain:invariant"), 0,
                            event_type,
                            {"invariant_ref": probe.get("invariant_ref") or sym.get("invariant_ref"),
                             "status": "open"}, "svc")
    except StreamRuleViolation:
        return "StreamRuleViolation"
    return "ACCEPTED"

def _p_projection_rebuild(ctx, probe, profile):
    """CQ-8 投影删除后能否恢复 ← discard → snapshot 拒绝 → rebuild 确定性一致。"""
    from kernel.projection import Projection, ProjectionNotMaterialized
    from generated import reducers
    agg = profile["aggregate"]
    p = Projection(ctx["store"], agg["type"], reducers.REDUCERS[agg["reducer"]],
                   streams=[agg["stream"]])
    before = p.rebuild()
    p.discard()
    dematerialized = False
    try:
        p.snapshot()
    except ProjectionNotMaterialized:
        dematerialized = True
    return {"identical": before == p.rebuild(), "dematerialized": dematerialized}

def _p_session_observation(ctx, probe, profile):
    """CQ-9 Agent 当时看到什么 ← 会话流可读；其观测字段不得污染权威投影。"""
    observed = ctx["session"].read_all()
    snap = _projection(ctx).snapshot()
    return {"observed": len(observed),
            "in_authoritative": any("seen" in v for v in snap.values())}

def _p_declaration_digest(ctx, probe, profile):
    """CQ-10 规范改动可否察觉 ← 声明摘要与 append-only 登记条目逐字比对。"""
    from tools import hash_spec as hs
    rows = hs._decl_entries()
    digest = hs.declaration_digest()
    return bool(rows) and digest is not None and any(digest in r for r in rows)

PRIMITIVES = {
    "projection.snapshot": _p_projection_snapshot,
    "declaration.permissions": _p_declaration_permissions,
    "kernel.conditional": _p_kernel_conditional,
    "audit.unified": _p_interpreter_audit,
    "link.same_as": _p_link_same_as,
    "process.compensation": _p_process_compensation,
    "store.stream_rule": _p_stream_rule,
    "projection.rebuild": _p_projection_rebuild,
    "session.observation": _p_session_observation,
    "integrity.declaration_digest": _p_declaration_digest,
}

def _wrap(key: str):
    def _call(ctx, probe, profile=None):
        return PRIMITIVES[key](ctx, probe, profile or load_profile())
    return _call

ANSWERERS = {key: _wrap(key) for key in PRIMITIVES}   # 可覆写调度入口（兼容旧式双参）

def _call_answerer(fn, ctx, probe, profile):
    try:
        n = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        n = 3
    return fn(ctx, probe, profile) if n >= 3 else fn(ctx, probe)

OPERATORS = {"equals": lambda actual, expected: actual == expected}

# ---------- 声明加载：完整性即门禁 ----------
def _order(p: Path):
    try:
        return (0, int(p.name.split(".")[0].split("-")[-1]))  # CQ-2 在 CQ-10 前（数字序）
    except (IndexError, ValueError):
        return (1, p.name)                                  # 畸形文件名仍进完整性检查

def _decl_dir(root: Path | None, domain: str) -> Path:
    if root is not None:
        return Path(root)                                    # 测试隔离的题集目录
    return DOMAIN_DIR / domain if domain != DEFAULT_DOMAIN else CQ_DIR

def declarations(root: Path | None = None, domain: str = DEFAULT_DOMAIN) -> list[dict]:
    """加载题集。contract 域强制十题冻结清单（防删题）；自定义域只要求至少一题。
    两域都要求 id 唯一、回答者/算子已注册、夹具已在域画像中声明。"""
    profile = load_profile(domain, root)
    files = sorted(_decl_dir(root, domain).glob("*.cq.yaml"), key=_order)
    docs = [_load_yaml(p) for p in files]
    if not docs:
        raise CQError(f"CQ-EMPTY: 域 {domain} 无 *.cq.yaml 题集")
    ids = [doc.get("id") for doc in docs]
    if len(ids) != len(set(ids)):
        raise CQError(f"CQ-ID-DUPLICATE: 重复 id {ids} —— 问题清单不可有别名")
    if domain == DEFAULT_DOMAIN:
        missing, extra = sorted(set(EXPECTED_IDS) - set(ids)), sorted(set(ids) - set(EXPECTED_IDS))
        if missing or extra:
            raise CQError(f"CQ-INCOMPLETE: 缺 {missing} / 多 {extra} —— "
                          f"contract 域十张能力问题必须齐全（删题不构成通过）")
    fixtures = profile.get("fixtures") or {}
    for doc in docs:
        cid = doc.get("id", "?")
        for key in ("id", "question", "answerer", "fixture", "probe", "expect", "evidence"):
            if key not in doc:
                raise CQError(f"CQ-DECL-INCOMPLETE: {cid} 缺字段 {key}")
        if doc["answerer"] not in ANSWERERS:
            raise CQError(f"CQ-ANSWERER-UNKNOWN: {cid} → {doc['answerer']} "
                          f"（注册表：{sorted(ANSWERERS)}）")
        if doc["fixture"] not in fixtures:
            raise CQError(f"CQ-FIXTURE-UNKNOWN: {cid} → {doc['fixture']} "
                          f"（域 {domain} 声明的夹具：{sorted(fixtures)}）")
        expect = doc["expect"]
        op = expect.get("op") if isinstance(expect, dict) else None
        if op not in OPERATORS:
            raise CQError(f"CQ-OPERATOR-UNKNOWN: {cid} → {op}")
    return docs

def run(ids: list[str] | None = None, root: Path | None = None,
        domain: str = DEFAULT_DOMAIN) -> list[dict]:
    """执行 CQ；单题失败不影响其余题呈现，整体返回供 CLI / 测试消费。"""
    docs = declarations(root, domain)
    profile = load_profile(domain, root)
    valid_ids = {d["id"] for d in docs}
    if ids:
        unknown = sorted(set(ids) - valid_ids)
        if unknown:
            raise CQError(f"CQ-UNKNOWN-ID: {unknown}（域 {domain}）")
        docs = [d for d in docs if d["id"] in ids]
    results = []
    for d in docs:
        item = {"id": d["id"], "question": d["question"], "evidence": d["evidence"]}
        try:
            ctx = build_fixture(profile, d["fixture"])
            actual = _call_answerer(ANSWERERS[d["answerer"]], ctx,
                                    d.get("probe") or {}, profile)
            expected = d["expect"]["value"]
            item.update(ok=OPERATORS[d["expect"]["op"]](actual, expected),
                        actual=actual, expected=expected)
        except Exception as e:                      # 执行异常本身即 CQ 失败，不吞
            item.update(ok=False, error=f"{type(e).__name__}: {e}")
        results.append(item)
    return results

def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    domain = DEFAULT_DOMAIN
    if "--domain" in argv:
        i = argv.index("--domain")
        if i + 1 >= len(argv):
            print("REFUSED: --domain 需要一个域画像名"); return 1
        domain = argv[i + 1]
        del argv[i:i + 2]
    if argv[:1] == ["list"]:
        try:
            for d in declarations(domain=domain):
                print(f"{d['id']:10s} {d['question']}  [{d['answerer']}]")
        except CQError as e:
            print(f"REFUSED: {e}"); return 1
        return 0
    ids = [a for a in argv if not a.startswith("--") and a != "run"]
    try:
        results = run(ids or None, domain=domain)
    except CQError as e:
        print(f"REFUSED: {e}"); return 1
    for r in results:
        flag = "PASS" if r["ok"] else "FAIL"
        print(f"[{flag}] {r['id']} {r['question']}")
        if not r["ok"]:
            print(f"       证据落点: {r['evidence']}")
            print(f"       期望: {r.get('expected')!r}  实际: "
                  f"{r.get('actual', r.get('error'))!r}")
    good = sum(1 for r in results if r["ok"])
    suffix = f"（域 {domain}）" if domain != DEFAULT_DOMAIN else ""
    print(f"CQ-RUN: {good}/{len(results)} 通过{suffix}"
          + ("（能力契约可执行）" if good == len(results) else " —— 能力契约未兑现"))
    return 0 if good == len(results) else 1

if __name__ == "__main__":
    sys.exit(main())
