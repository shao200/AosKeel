"""tests/conformance/test_agent_surface.py —— P-10：AGENT 能力面 = 清单严格子集。
判据：能力面来自编译产物权限矩阵 ∩ 角色；越权在触达存储之前拒绝；
写路径与人类同一条管线（INV-1，无特权通道）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import compile_all
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from agents.runtime import AgentRuntime
from kernel.errors import PermissionDenied
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
def _runtime(roles=("contract_steward",)):
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    return k, AgentRuntime(k, "agent-1", roles)
def test_capability_surface_from_permissions():
    k, agent = _runtime()
    caps = agent.capabilities()
    assert "ApproveContract" in caps and "VoidContract" in caps
    assert "RecordDecision" not in caps                        # 无角色声明者不入面
def test_unauthorized_rejected_before_store():
    """越权 = PermissionDenied，在触达存储之前（无审计污染的写尝试）。"""
    k, agent = _runtime(roles=("viewer",))
    with pytest.raises(PermissionDenied, match="严格子集"):
        agent.act("ApproveContract", PARAMS)
    assert not k.store.streams and not k.store.audit           # 存储零接触
def test_authorized_uses_same_pipeline():
    """P-10：Agent 无特权通道 —— 与人类同一条提交管线（INV-1）。"""
    k, agent = _runtime()
    ev = agent.act("ApproveContract", PARAMS)
    assert ev.action_id == "ApproveContract"
    assert ev.stream_id == "domain:ContractAggregate"
    assert ev.payload["valid_time"] <= ev.transaction_time     # KS-6.1 同等强制
def test_agent_has_no_raw_write_path():
    """AgentRuntime 上不存在任何绕过管线的写方法（P-10 结构核对）。"""
    _, agent = _runtime()
    for banned in ("write_raw", "append", "commit", "_append"):
        assert not hasattr(agent, banned)


# ---------- 管理域：实体主动性的可见性边界（实例侧参考实现） ----------
# 三条规则：创建者拥有域 / 仅域内角色可被扫描到 / 仅域内角色可参与互动。
# 判据全部可计算（owner 来自首事件 principal，scan 为集合交），不是声称。
def _domain_kernel():
    """构造一条已注册的 Contract 实例，创建者为 creator-A。"""
    from kernel.stewardship import StewardshipRegistry
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    k.submit("RegisterContract",
             {"contract_id": "C-DOM", "amount": 500000, "party_refs": []},
             "creator-A", roles=("contract_steward",))
    return k, StewardshipRegistry(k.store)


def test_owner_reconstructed_from_first_event():
    """创建者拥有管理域：owner = 该实例首事件 principal，append-only 不可伪造。"""
    k, reg = _domain_kernel()
    assert reg.owner_of("domain:ContractAggregate", "C-DOM") == "creator-A"
    # 后续由别人提交审批事件，owner 不变
    k.submit("ApproveContract", {"contract_id": "C-DOM", "amount": 500000},
             "approver-B", roles=("contract_steward",))
    assert reg.owner_of("domain:ContractAggregate", "C-DOM") == "creator-A"


def test_owner_scoped_to_instance_not_first_stream_event():
    """管理域按实例隔离：同流第二实例的 owner 独立重建，不串到首事件。"""
    k, reg = _domain_kernel()
    k.submit("RegisterContract",
             {"contract_id": "C-DOM-2", "amount": 100, "party_refs": []},
             "creator-Z", roles=("contract_steward",))
    assert reg.owner_of("domain:ContractAggregate", "C-DOM-2") == "creator-Z"
    assert reg.owner_of("domain:ContractAggregate", "C-DOM") == "creator-A"


def test_only_creator_can_anchor_domain():
    """非创建者锚定即拒（DOMAIN-OWNER-MISMATCH），fail-closed。"""
    from kernel.stewardship import DomainOwnerMismatch
    _, reg = _domain_kernel()
    with pytest.raises(DomainOwnerMismatch, match="DOMAIN-OWNER-MISMATCH"):
        reg.anchor("domain:ContractAggregate", "C-DOM", "intruder", ["contract_steward"])


def test_empty_domain_rejected():
    """空成员集即拒（EMPTY-DOMAIN）——无管理域，不静默放行。"""
    from kernel.stewardship import EmptyDomainRejected
    _, reg = _domain_kernel()
    with pytest.raises(EmptyDomainRejected, match="EMPTY-DOMAIN"):
        reg.anchor("domain:ContractAggregate", "C-DOM", "creator-A", [])


def test_scan_returns_only_in_domain_roles():
    """只有域内角色可被主动行为扫描到：scan = 候选 ∩ 域内，域外不可见。"""
    _, reg = _domain_kernel()
    reg.anchor("domain:ContractAggregate", "C-DOM", "creator-A",
               ["contract_steward", "auditor"])
    visible = reg.scan("domain:ContractAggregate", "C-DOM",
                       ["contract_steward", "outsider", "auditor", "vendor"])
    assert visible == ("contract_steward", "auditor")   # 域外被过滤、顺序保持


def test_unanchored_domain_falls_back_to_declared_visible_set():
    """未锚定：回落治理声明推导的可见集 V（不再 fail-closed 拒绝）。

    语义变更记录：旧版未锚定即 DomainNotAnchored；收敛后默认"在册切面成员可见"，
    因为可见集是治理事实、无需 owner 逐实例重锚。真 fail-closed 保留在两处：
    V 为空（NoVisibleRoles）与显式锚定路径（非 owner / 空集）。
    """
    from kernel.stewardship import visible_roles
    _, reg = _domain_kernel()
    expected = visible_roles(None)                       # 治理面全部 Action
    visible = reg.scan("domain:ContractAggregate", "C-DOM",
                       ["contract_steward", "outsider"])
    assert visible == tuple(r for r in ("contract_steward", "outsider") if r in expected)
    assert "outsider" not in visible
    assert reg.can_interact("domain:ContractAggregate", "C-DOM", ["contract_steward"])


def test_unanchored_domain_with_no_entity_is_still_fail_closed():
    """无实体的域：即使声明 V 非空，owner 不可重建仍拒绝（归属 fail-closed）。"""
    from kernel.stewardship import DomainNotAnchored, StewardshipRegistry
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    reg = StewardshipRegistry(k.store)
    with pytest.raises(DomainNotAnchored):
        reg.scan("domain:ContractAggregate", "NO-SUCH-ENTITY", ["contract_steward"])


# ---------- 可见集 V / 执行集 E 分离 + 单一事实源 ----------
def _positions(roles, actions_by_role, orgs_by_role=None):
    """构造治理投影视图（模拟 codegen 输出），供纯函数测试，不碰在册声明。"""
    orgs_by_role = orgs_by_role or {}
    return {r: {"duties": [f"{r}-duty"],
                "org_units": orgs_by_role.get(r, ["dept"]),
                "authorizes": list(acts)} for r, acts in actions_by_role.items()}


def test_visible_set_is_union_across_facets_and_orgs():
    """可见集 V = 跨切面并集：当事人 + 检验 + 监理，跨组织。"""
    from kernel.stewardship import visible_roles
    p = _positions(None, {
        "contract_steward": ["ApproveContract"],
        "qc_inspector": ["InspectContract"],
        "site_supervisor": ["SuperviseContract"],
        "outsider": [],
    }, {"contract_steward": ["c-dept"], "qc_inspector": ["q-dept"],
        "site_supervisor": ["s-dept"]})
    v = visible_roles(["ApproveContract", "InspectContract", "SuperviseContract"], p)
    assert v == ("contract_steward", "qc_inspector", "site_supervisor")
    assert "outsider" not in v
    from kernel.stewardship import org_units_of
    assert org_units_of(["ApproveContract", "InspectContract", "SuperviseContract"], p) == (
        "c-dept", "q-dept", "s-dept")


def test_executor_set_is_narrower_than_visible_set():
    """执行集 E 按单动作收窄：检验员在 V 但不能提交审批（可见 ≠ 可执行）。"""
    from kernel.stewardship import executor_roles, visible_roles
    p = _positions(None, {
        "contract_steward": ["ApproveContract"],
        "qc_inspector": ["InspectContract"],
        "site_supervisor": ["SuperviseContract"],
    })
    assert "qc_inspector" in visible_roles(["ApproveContract", "InspectContract"], p)
    assert executor_roles("ApproveContract", p) == ("contract_steward",)
    assert "qc_inspector" not in executor_roles("ApproveContract", p)
    assert executor_roles("InspectContract", p) == ("qc_inspector",)


def test_empty_visible_set_is_fail_closed():
    """可见集为空（Action 无授权岗位）即拒，不静默放行。"""
    from kernel.stewardship import NoVisibleRoles, visible_roles
    p = _positions(None, {"contract_steward": ["ApproveContract"]})
    with pytest.raises(NoVisibleRoles):
        visible_roles(["NonExistentAction"], p)


def test_single_fact_source_agrees_with_generated_projection():
    """收敛守卫：本模块推导与生成物 GOV_POSITIONS 同源，不产生第二张皮。

    只在 auth 生成物在场时核对（精简 profile 下它被摘除，本模块仍可用）。
    """
    from kernel.stewardship import governance_view, executor_roles
    view = governance_view()
    gen = ROOT / "src" / "generated" / "auth_oauth2.py"
    if not gen.exists():
        pytest.skip("auth_oauth2 生成物未启用（精简 profile）—— 本模块仍独立可用")
    ns = {}
    exec(compile(gen.read_text(encoding="utf-8"), str(gen), "exec"), ns)
    assert view == ns["GOV_POSITIONS"], "治理投影与生成物漂移 —— 出现第二张皮"
    for action in ("ApproveContract", "RegisterContract", "VoidContract"):
        assert set(executor_roles(action)) == {
            p for p, v in view.items() if action in v["authorizes"]}


def test_executor_agrees_with_kernel_submit_gate():
    """唯一执行判据（能力账簿）与 submit 门控同源；治理面 E 仅用于对账。"""
    from kernel.capability_ledger import CapabilityLedger
    from kernel.stewardship import executor_roles
    k, _ = _domain_kernel()
    ledger = CapabilityLedger(k.compiled)
    assert ledger.can_execute("ApproveContract", ["contract_steward"]) is True
    assert ledger.can_execute("ApproveContract", ["qc_inspector"]) is False
    # 治理面 E 只做对账：现网须与能力面相等，漂移即失败（唯一判据是能力账簿）
    assert set(executor_roles("ApproveContract")) == set(ledger.demand(["ApproveContract"]))
    # 写路径实际行为对齐：出示授权角色能提交，非授权角色触达前被拒
    ev = k.submit("ApproveContract", {"contract_id": "C-DOM", "amount": 500000},
                  "approver-B", roles=("contract_steward",))
    assert ev.action_id == "ApproveContract"
    with pytest.raises(PermissionDenied):
        k.submit("ApproveContract", {"contract_id": "C-DOM", "amount": 500000},
                 "intruder", roles=("qc_inspector",))


def test_only_in_domain_roles_can_interact():
    """域内角色可参与主动性互动，域外角色不可（布尔判据可计算）。"""
    _, reg = _domain_kernel()
    reg.anchor("domain:ContractAggregate", "C-DOM", "creator-A", ["contract_steward"])
    assert reg.can_interact("domain:ContractAggregate", "C-DOM", ["contract_steward"]) is True
    assert reg.can_interact("domain:ContractAggregate", "C-DOM", ["outsider"]) is False
    assert reg.can_interact("domain:ContractAggregate", "C-DOM",
                            ["outsider", "contract_steward"]) is True


# ---------- 实体主动行为闭环（观察侧，事找人；不碰写路径） ----------
def _initiative_setup():
    """构造：一条 pending 合同 + 已物化投影 + 主动引擎。"""
    from kernel.stewardship import StewardshipRegistry
    from kernel.projection import Projection
    from kernel.initiative import InitiativeEngine, Trigger
    from kernel.capability_ledger import CapabilityLedger
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    k.submit("RegisterContract",
             {"contract_id": "C-ACT", "amount": 500000, "party_refs": []},
             "creator-A", roles=("contract_steward",))
    def reducer(state, ev):
        s = dict(state or {})
        s[ev.payload.get("contract_id", "?")] = {"status": ev.payload.get("status", "pending")}
        return s
    proj = Projection(k.store, "contract", reducer, streams=["domain:ContractAggregate"])
    proj.rebuild()
    engine = InitiativeEngine({"contract": proj}, k.session,
                              StewardshipRegistry(k.store), CapabilityLedger(k.compiled))
    trig = Trigger("pending-needs-approval", "ApproveContract",
                   lambda snap: snap.get("C-ACT", {}).get("status") == "pending")
    return k, engine, trig


def test_initiative_writes_only_observation_not_eventstore():
    """闭环核心：邀请写 session 观察通道，EventStore 零增长（不碰写路径）。"""
    k, engine, trig = _initiative_setup()
    before = sum(len(s) for s in k.store.streams.values())
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT",
                      candidates=["contract_steward", "qc_inspector", "outsider"],
                      triggers=[trig], action_types=["ApproveContract"])
    after = sum(len(s) for s in k.store.streams.values())
    assert before == after, "主动行为不得写权威事件流"
    assert recs, "pending 触发应产出邀请"
    assert k.session.read_all(), "邀请须落在观察通道"
    # 逐条带主体归属：principal = 实体 id（KS-2.3）
    assert all(r["principal"] == "C-ACT" for r in k.session.read_all())


def test_initiative_classifies_visible_vs_executable():
    """V 扫描结果按 E 分类：授权角色=invitation，非授权切面=notice，域外不出现。

    注意：在册治理声明只有 contract_steward 一个岗位，qc_inspector 不在声明里。
    要测"可见但无执行权"，须由 owner 显式锚定把它纳入可见集 V——执行权 E 仍由
    声明决定（qc_inspector 不在 E(ApproveContract)），于是它只被通知、不被邀请执行。
    这同时验证：可见集（owner 可控）与执行集（治理声明决定）确实是两个独立维度。
    """
    k, engine, trig = _initiative_setup()
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["contract_steward", "qc_inspector"])
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT",
                      candidates=["contract_steward", "qc_inspector", "outsider"],
                      triggers=[trig], action_types=["ApproveContract"])
    by_role = {r["to_role"]: r for r in recs}
    assert "outsider" not in by_role                       # 域外不可见
    assert by_role["contract_steward"]["can_execute"] is True
    assert by_role["contract_steward"]["kind"] == "initiative.invitation"
    assert by_role["qc_inspector"]["can_execute"] is False
    assert by_role["qc_inspector"]["kind"] == "initiative.notice"   # 见证切面只被通知


def test_initiative_no_fire_when_condition_false():
    """触发条件不成立 → 零邀请、零观察写入（可预期静默，非错误）。"""
    from kernel.initiative import Trigger
    k, engine, _ = _initiative_setup()
    never = Trigger("never", "ApproveContract", lambda snap: False)
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT", candidates=["contract_steward"],
                      triggers=[never], action_types=["ApproveContract"])
    assert recs == []
    assert k.session.read_all() == []


def test_initiative_fail_closed_on_unmaterialized_projection():
    """投影未物化即拒（fail-closed），不基于空状态做主动判定。"""
    from kernel.initiative import ProjectionNotReady
    k, engine, trig = _initiative_setup()
    engine.projections["contract"].discard()
    with pytest.raises(ProjectionNotReady):
        engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                   entity_id="C-ACT", candidates=["contract_steward"],
                   triggers=[trig], action_types=["ApproveContract"])


def test_initiative_never_calls_submit_or_bypasses_gate():
    """红线守卫：引擎无 submit/commit/append-to-store 能力（结构核对）。"""
    from kernel.initiative import InitiativeEngine
    k, engine, trig = _initiative_setup()
    for banned in ("submit", "commit", "write_raw", "_append"):
        assert not hasattr(engine, banned), f"主动引擎不得具备 {banned} 能力"
    # 引擎只持有 session（观察写）与 projections（只读），不持有 store
    assert not hasattr(engine, "store"), "主动引擎不得持有 EventStore 引用"


# ---------- 能力账簿：双向匹配的单一事实源（事找人 / 人找事同源） ----------
def test_capability_ledger_is_dual_projection_of_submit_gate():
    """能力账簿 demand/supply 是 compiled 权限矩阵的两个投影，与 submit 门控同源。"""
    from kernel.capability_ledger import CapabilityLedger
    ledger = CapabilityLedger(compile_all())
    # 事找人：需求 → 合格角色
    assert ledger.demand(["ApproveContract"]) == ("contract_steward",)
    assert ledger.demand(["NoSuchAction"]) == ()              # 未注册 → fail-closed
    # 人找事：角色 → 可做 Action（与 AgentRuntime.capabilities 同推导）
    supplied = ledger.supply(["contract_steward"])
    assert "ApproveContract" in supplied and "RegisterContract" in supplied
    assert ledger.supply(["outsider"]) == ()                   # 域外无能力
    # 门控同源：can_execute 与 demand 一致
    assert ledger.can_execute("ApproveContract", ["contract_steward"]) is True
    assert ledger.can_execute("ApproveContract", ["outsider"]) is False
    assert ledger.digest(), "账簿须有稳定指纹供审计"


def test_ledger_gate_agrees_with_real_submit():
    """账簿判据与真实 submit 角色门控逐字对齐：账上能提交的必放行，反之触达前被拒。"""
    from kernel.capability_ledger import CapabilityLedger
    from kernel.errors import PermissionDenied
    # 每个角色独立内核 + 先注册一条 pending 合同，排除条件门控干扰，只测角色门控。
    for roles in (["contract_steward"], ["qc_inspector"], ["outsider"]):
        k = Kernel(EventStore(), SessionChannel(), compile_all())
        ledger = CapabilityLedger(k.compiled)
        k.submit("RegisterContract", {"contract_id": "C-GATE", "amount": 1, "party_refs": []},
                 "svc", roles=("contract_steward",))
        predicted = ledger.can_execute("ApproveContract", roles)
        try:
            k.submit("ApproveContract", {"contract_id": "C-GATE", "amount": 1},
                     "svc", roles=tuple(roles))
            actual = True
        except PermissionDenied:
            actual = False
        assert predicted is actual, f"账簿判据与门控漂移：{roles} 预测{predicted} 实际{actual}"


def test_seek_is_demand_mirror_writing_observation_only():
    """人找事：出示角色反查能力 → 投影命中 → offer 写观察通道，EventStore 零增长。"""
    from kernel.initiative import Trigger
    k, engine, _ = _initiative_setup()
    seeker = Trigger("pending-needs-approval", "ApproveContract",
                     lambda snap: snap.get("C-ACT", {}).get("status") == "pending")
    before = sum(len(s) for s in k.store.streams.values())
    recs = engine.seek(principal="agent-1", roles=["contract_steward"],
                       projection_name="contract", triggers=[seeker],
                       stream_id="domain:ContractAggregate", entity_id="C-ACT")
    after = sum(len(s) for s in k.store.streams.values())
    assert before == after, "人找事不得写权威事件流"
    assert len(recs) == 1
    assert recs[0]["kind"] == "initiative.offer"
    assert recs[0]["principal"] == "agent-1"          # 主体归属 = 找事的人（KS-2.3）
    assert recs[0]["action"] == "ApproveContract"


def test_seek_filters_by_capability_and_domain():
    """人找事两道门：无能力者无 offer（能力账簿）；域外者无 offer（可见集 V）。"""
    from kernel.initiative import NoCapability, Trigger
    k, engine, trig = _initiative_setup()
    # 门1：域外角色无可推动 Action → fail-closed
    with pytest.raises(NoCapability):
        engine.seek(principal="outsider", roles=["outsider"],
                    projection_name="contract", triggers=[trig])
    # 门2：有能力但不在该实体管理域 → 无 offer（静默，不报错）
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["qc_inspector"])              # 域内锚定为切面角色，不含 steward
    offers = engine.seek(principal="agent-x", roles=["contract_steward"],
                         projection_name="contract", triggers=[trig],
                         stream_id="domain:ContractAggregate", entity_id="C-ACT")
    assert offers == [], "有能力但域外角色不应拿到该实体的 offer"
    # 正常路径：域内 + 有能力 → 拿到 offer
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["contract_steward"])
    offers2 = engine.seek(principal="agent-z", roles=["contract_steward"],
                          projection_name="contract", triggers=[trig],
                          stream_id="domain:ContractAggregate", entity_id="C-ACT")
    assert len(offers2) == 1 and offers2[0]["kind"] == "initiative.offer"


def test_both_directions_share_one_ledger_and_one_channel():
    """双向对称：run（事找人）与 seek（人找事）读同一账簿、写同一观察通道、都不碰写路径。"""
    k, engine, trig = _initiative_setup()
    assert engine.ledger is not None
    before = sum(len(s) for s in k.store.streams.values())
    engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
               entity_id="C-ACT", candidates=["contract_steward"],
               triggers=[trig], action_types=["ApproveContract"])
    engine.seek(principal="agent-1", roles=["contract_steward"],
                projection_name="contract", triggers=[trig])
    after = sum(len(s) for s in k.store.streams.values())
    assert before == after, "双向匹配均不得改权威状态"
    kinds = {r["kind"] for r in k.session.read_all()}
    assert "initiative.invitation" in kinds and "initiative.offer" in kinds


def test_engine_rejects_missing_ledger():
    """拒绝治理面第二张皮：未注入能力账簿即拒绝构造。"""
    from kernel.initiative import InitiativeEngine, InitiativeViolation
    from kernel.stewardship import StewardshipRegistry
    from kernel.projection import Projection
    from generated import reducers
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    k.submit("RegisterContract", {"contract_id": "C-X", "amount": 1, "party_refs": []},
             "creator", roles=("contract_steward",))
    p = Projection(k.store, "contract", reducers.REDUCERS["ContractAggregate"],
                   streams=["domain:ContractAggregate"])
    p.rebuild()
    with pytest.raises(InitiativeViolation):
        InitiativeEngine({"contract": p}, k.session, StewardshipRegistry(k.store), None)


def test_seek_rejects_half_domain_scope():
    """半参数 seek 必须拒绝：禁止只给 entity_id 或只给 stream_id 绕过 V 域门控。"""
    from kernel.initiative import InitiativeViolation
    from kernel.initiative import Trigger
    k, engine, trig = _initiative_setup()
    with pytest.raises(InitiativeViolation, match="SEEK-SCOPE-INCOMPLETE"):
        engine.seek(principal="agent-1", roles=["contract_steward"],
                    projection_name="contract", triggers=[trig],
                    entity_id="C-ACT")                      # 缺 stream_id
    with pytest.raises(InitiativeViolation, match="SEEK-SCOPE-INCOMPLETE"):
        engine.seek(principal="agent-1", roles=["contract_steward"],
                    projection_name="contract", triggers=[trig],
                    stream_id="domain:ContractAggregate")   # 缺 entity_id
    assert k.session.read_all() == [], "被拒调用不得产生任何意向消息"


def test_entity_scoped_trigger_avoids_cross_target_fanout():
    """双参谓词逐目标判定：只有命中的实体收到 offer，不扇出到全投影。"""
    from kernel.initiative import Trigger
    k, engine, _ = _initiative_setup()
    k.submit("RegisterContract",
             {"contract_id": "C-OTHER", "amount": 100, "party_refs": []},
             "creator-B", roles=("contract_steward",))
    engine.projections["contract"].rebuild()                # 两实体入快照
    scoped = Trigger("only-C-ACT", "ApproveContract",
                     lambda snap, eid: eid == "C-ACT"
                     and snap.get(eid, {}).get("status") == "pending")
    recs = engine.seek(principal="agent-1", roles=["contract_steward"],
                       projection_name="contract", triggers=[scoped])
    assert [r["entity"] for r in recs] == ["C-ACT"], "谓词必须逐目标判定，不得全表扇出"
    # 单参谓词向后兼容：仍按全快照判定
    legacy = Trigger("any-pending", "ApproveContract",
                     lambda snap: snap.get("C-ACT", {}).get("status") == "pending")
    recs2 = engine.seek(principal="agent-2", roles=["contract_steward"],
                        projection_name="contract", triggers=[legacy])
    assert len(recs2) == 2, "单参谓词保持旧语义（全快照判定），兼容既有写法"
