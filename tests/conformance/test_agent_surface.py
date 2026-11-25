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
# 测试注入的治理面视图：锚定只可收窄到在册角色，故"可见但无执行权"的切面角色
# 必须先在视图里声明（执行权仍由 compiled 权限矩阵决定，V ≠ E）。
_GOV_VIEW = {
    "contract_steward": {"authorizes": ["RegisterContract", "ApproveContract", "VoidContract"],
                         "org_units": ["org:contract"]},
    "qc_inspector": {"authorizes": ["ApproveContract"], "org_units": ["org:contract"]},
    "auditor": {"authorizes": ["ApproveContract"], "org_units": ["org:audit"]},
}
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
    k.submit("RegisterContract", {"contract_id": "C-1", "amount": 500000},
             "creator-A", roles=("contract_steward",))   # 非创建型动作须先有权威投影
    ev = agent.act("ApproveContract", PARAMS)
    assert ev.action_id == "ApproveContract"
    assert ev.stream_id == "domain:ContractAggregate"
    assert ev.payload["valid_time"] <= ev.transaction_time     # KS-6.1 同等强制
def test_agent_has_no_raw_write_path():
    """AgentRuntime 上不存在任何绕过管线的写方法（P-10 结构核对）。"""
    _, agent = _runtime()
    for banned in ("write_raw", "append", "commit", "_append"):
        assert not hasattr(agent, banned)


def test_agent_capabilities_are_ledger_projection():
    """能力面消除第二张皮：AgentRuntime.capabilities() 与能力账簿 supply() 同一实现。

    结构守卫：Agent 能力面 = 能力账簿（compiled 权限矩阵）的投影，不允许任何旁路。
    若未来有人试图在 runtime.py 里再手写一遍投影循环，本测试的等价断言会漂移。
    """
    from kernel.capability_ledger import CapabilityLedger
    k, agent = _runtime(roles=("contract_steward", "qc_inspector"))
    ledger = CapabilityLedger(k.compiled)
    assert agent.capabilities() == list(ledger.supply(agent.roles))
    # 显式注入同一本账时仍一致（测试/编排共用事实源）
    shared = CapabilityLedger(k.compiled)
    agent2 = AgentRuntime(k, "agent-2", ("contract_steward",), ledger=shared)
    assert agent2.capabilities() == list(shared.supply(agent2.roles))
    # 源文件必须"可见地"委托能力账簿——不残留自行遍历 compiled 的能力面
    src = (ROOT / "src" / "agents" / "runtime.py").read_text(encoding="utf-8")
    assert "self._ledger.supply" in src, "能力面必须委托能力账簿（消除第二张皮）"
    assert src.count("for aid, act in") == 0, "Agent 不得自研 compiled 投影循环"


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
               ["contract_steward", "auditor"], positions=_GOV_VIEW)
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


def test_governance_derivation_lives_in_kernel_not_tools():
    """依赖方向守卫：治理推导在内核，tools 反向委托；kernel 不得 import tools。"""
    from kernel.stewardship import governance_positions
    src = (ROOT / "src" / "kernel" / "stewardship.py").read_text(encoding="utf-8")
    assert "from tools" not in src and "import tools" not in src, \
        "内核不得反向依赖 tools 包（推导应下沉到 kernel）"
    view = governance_positions()
    assert "ApproveContract" in view["contract_steward"]["authorizes"]
    cg_src = (ROOT / "tools" / "codegen.py").read_text(encoding="utf-8")
    assert "from kernel.stewardship import governance_positions" in cg_src, \
        "工具链必须委托内核单一事实源，不得持有第二份解析"


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
    proj = Projection(k.store, "contract", reducer, streams=["domain:ContractAggregate"],
                      entity_key="contract_id")
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

    注意：真实治理声明只有 contract_steward 一个岗位。要测"可见但无执行权"，
    须由 owner 显式锚定把切面角色纳入可见集 V（测试注入的治理视图声明 qc_inspector
    可授权 ApproveContract，但编译期权限矩阵不含它）；执行权 E 仍由声明决定，
    于是它只被通知、不被邀请执行。这同时验证：可见集（owner 可控，只可收窄到
    在册角色）与执行集（治理声明决定）确实是两个独立维度。
    """
    k, engine, trig = _initiative_setup()
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["contract_steward", "qc_inspector"], positions=_GOV_VIEW)
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
                           ["qc_inspector"], positions=_GOV_VIEW)  # 域内锚定为切面角色
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
                   streams=["domain:ContractAggregate"], entity_key="contract_id")
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


# ---------- 校验强度策略：可调，但不跌破宪法下限 ----------
# 三层可调性：参数（dry_run/复核人数/SLA）与组合（检验切面）可调；
# 语义层（fail-closed/单一提交点/审计三元组/角色约束）由常量强制携带，声明无法关闭。
def _policy_mapping(actions=None, **over):
    base = {
        "version": 1,
        "floor": ["fail_closed", "single_submit_point", "audit_triad",
                  "role_constraint"],
        "tiers": {
            "autonomous": {"requires_dry_run": True, "min_approvals": 0,
                           "sla_hours": None, "required_facets": [],
                           "auto_commit": True},
            "dual_review": {"requires_dry_run": True, "min_approvals": 2,
                            "sla_hours": 24, "required_facets": [],
                            "auto_commit": False},
        },
        "actions": {"ApproveContract": {"tier": "dual_review"}},
    }
    if actions is not None:
        base["actions"] = actions
    base.update(over)
    return base


def _policy(**over):
    from kernel.assurance import AssurancePolicy
    return AssurancePolicy.from_mapping(_policy_mapping(**over))


def _engine_with_policy(policy):
    """在既有闭环装置上挂策略引擎（投影/账簿/注册表全部复用，只加 policy）。"""
    from kernel.initiative import InitiativeEngine
    k, engine, trig = _initiative_setup()
    return k, InitiativeEngine(engine.projections, k.session, engine.registry,
                               engine.ledger, policy=policy), trig


def test_policy_plan_always_carries_immutable_gates():
    """宪法下限与声明无关：任何档位的 GatePlan 都恒定携带四道不可关的闸。"""
    from kernel.assurance import IMMUTABLE_GATES
    p = _policy()
    plan = p.plan("ApproveContract")
    assert plan.immutable_gates == IMMUTABLE_GATES
    assert plan.tier.name == "dual_review"
    assert plan.tier.min_approvals == 2 and plan.tier.sla_hours == 24
    assert p.digest() == _policy().digest(), "策略指纹须稳定可复算（审计可比对）"


def test_policy_rejects_gate_removal_declaration():
    """语义禁调：声明里出现 gates/immutable_gates 即拒绝加载，不是静默忽略。"""
    from kernel.assurance import AssurancePolicy, FloorViolation
    evil = _policy_mapping()
    evil["tiers"]["dual_review"]["gates"] = ["audit_triad"]
    with pytest.raises(FloorViolation, match="POLICY-GATE-REMOVAL"):
        AssurancePolicy.from_mapping(evil)
    evil2 = _policy_mapping()
    evil2["immutable_gates"] = []
    with pytest.raises(FloorViolation, match="POLICY-GATE-REMOVAL"):
        AssurancePolicy.from_mapping(evil2)


def test_policy_rejects_autonomous_without_dry_run():
    """自主 ≠ 免检：允许自动提交的档位必须先 dry_run 取证。"""
    from kernel.assurance import AssurancePolicy, FloorViolation
    m = _policy_mapping()
    m["tiers"]["autonomous"]["requires_dry_run"] = False
    with pytest.raises(FloorViolation, match="AUTO-WITHOUT-EVIDENCE"):
        AssurancePolicy.from_mapping(m)


def test_policy_rejects_non_bool_and_weakened_floor():
    """布尔严格 isinstance；floor 只可加严不可缩减。"""
    from kernel.assurance import AssurancePolicy, FloorViolation
    m = _policy_mapping()
    m["tiers"]["dual_review"]["auto_commit"] = 1          # 非 bool，禁止 bool() 兜底
    with pytest.raises(FloorViolation, match="POLICY-NON-BOOL"):
        AssurancePolicy.from_mapping(m)
    m2 = _policy_mapping()
    m2["floor"] = ["fail_closed"]                          # 试图缩减宪法下限
    with pytest.raises(FloorViolation, match="FLOOR-WEAKENED"):
        AssurancePolicy.from_mapping(m2)
    m3 = _policy_mapping()
    m3["version"] = True                                   # bool 不得冒充版本号 1
    with pytest.raises(FloorViolation, match="POLICY-VERSION"):
        AssurancePolicy.from_mapping(m3)


def test_policy_unknown_action_is_fail_closed():
    """未声明强度的 Action 无默认档位，求值即拒绝。"""
    from kernel.assurance import UnknownActionTier
    with pytest.raises(UnknownActionTier):
        _policy().plan("NoSuchAction")


def test_shipped_policy_config_loads_and_covers_sample_actions():
    """随仓策略文件可加载，且三个样例 Action 全部有档位与下限。"""
    from kernel.assurance import AssurancePolicy, DEFAULT_POLICY_PATH
    assert DEFAULT_POLICY_PATH.exists(), "策略声明文件缺失（可调性无载体）"
    p = AssurancePolicy.load()
    for action in ("RegisterContract", "ApproveContract", "VoidContract"):
        plan = p.plan(action)
        assert plan.immutable_gates, f"{action} 档位丢失宪法下限"
    assert p.plan("VoidContract").tier.name == "supervised"


def test_engine_policy_annotates_tier_and_keeps_write_path_closed():
    """策略只增观察字段，不碰写路径：档位/复核人数/SLA 可审计，事件流零增长。"""
    k, engine, trig = _engine_with_policy(_policy())
    before = sum(len(s) for s in k.store.streams.values())
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT", candidates=["contract_steward"],
                      triggers=[trig], action_types=["ApproveContract"])
    after = sum(len(s) for s in k.store.streams.values())
    assert before == after, "策略层不得写权威事件流"
    rec = recs[0]
    assert rec["assurance_tier"] == "dual_review"
    assert rec["min_approvals"] == 2 and rec["sla_hours"] == 24
    assert rec["auto_commit"] is False
    assert rec["kind"] == "initiative.invitation"
    assert rec["immutable_gates"], "观察记录须携带宪法下限供审计"


def test_assurance_tier_is_advisory_only():
    """档位是建议复核强度（advisory）：记录显式标 enforced=False，且不构成写路径闸门。"""
    k, engine, trig = _engine_with_policy(_policy())
    rec = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                     entity_id="C-ACT", candidates=["contract_steward"],
                     triggers=[trig], action_types=["ApproveContract"])[0]
    assert rec["assurance_advisory"] is True
    assert rec["assurance_enforced"] is False
    assert rec["min_approvals"] == 2 and rec["requires_dry_run"] is True
    ev = k.submit("ApproveContract", dict(PARAMS, contract_id="C-ACT"),
                  "creator-A", roles=("contract_steward",))
    assert ev.action_id == "ApproveContract", "未出示演练票据/双人复核仍不拦——档位不是闸门"


def test_engine_policy_never_grants_auto_to_unauthorized_role():
    """自主 = 档位允许 ∧ 确有执行权：可见但无执行权的切面不得被判为自主。"""
    k, engine, trig = _engine_with_policy(
        _policy(actions={"ApproveContract": {"tier": "autonomous"}}))
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["contract_steward", "qc_inspector"], positions=_GOV_VIEW)
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT", candidates=["contract_steward", "qc_inspector"],
                      triggers=[trig], action_types=["ApproveContract"])
    by_role = {r["to_role"]: r for r in recs}
    assert by_role["contract_steward"]["auto_commit"] is True
    assert by_role["contract_steward"]["kind"] == "initiative.auto"
    assert by_role["qc_inspector"]["auto_commit"] is False
    assert by_role["qc_inspector"]["kind"] == "initiative.notice"


def test_engine_rejects_policy_facet_missing_from_visible_set():
    """组合可调的下限：要求的检验切面不可见 → 拒绝发出无法兑现的邀请。"""
    from kernel.assurance import AssurancePolicy, FacetNotAuthorized
    m = _policy_mapping()
    m["tiers"]["dual_review"]["required_facets"] = ["qc_inspector"]
    k, engine, trig = _engine_with_policy(AssurancePolicy.from_mapping(m))
    with pytest.raises(FacetNotAuthorized):
        engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                   entity_id="C-ACT", candidates=["contract_steward"],
                   triggers=[trig], action_types=["ApproveContract"])
    assert k.session.read_all() == [], "切面不满足即拒，不得先写观察"


def test_engine_without_policy_keeps_legacy_record_shape():
    """未注入策略时行为与记录形态完全不变（向后兼容，不是新增必经项）。"""
    k, engine, trig = _initiative_setup()
    recs = engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT", candidates=["contract_steward"],
                      triggers=[trig], action_types=["ApproveContract"])
    assert "assurance_tier" not in recs[0]
    assert recs[0]["kind"] == "initiative.invitation"


# ---------- 责任传递：发起人身份 + 选择审计三元组 ----------
# 选择 = 观察层行为：记 who / when / basis，不写权威事件流；执行仍走 submit。
def _run_once(engine, trig, candidates=("contract_steward",)):
    return engine.run(projection_name="contract", stream_id="domain:ContractAggregate",
                      entity_id="C-ACT", candidates=list(candidates),
                      triggers=[trig], action_types=["ApproveContract"])


def test_selection_records_triad_and_routes_to_holder():
    """三元组落账（谁 / 何时 / 依据），责任传到持岗人，事件流零增长。"""
    k, engine, trig = _initiative_setup()
    _run_once(engine, trig)
    before = sum(len(s) for s in k.store.streams.values())
    rec = engine.select(principal="creator-A", entity_id="C-ACT",
                        action="ApproveContract", to_role="contract_steward")
    after = sum(len(s) for s in k.store.streams.values())
    assert before == after, "选择 ≠ 执行：不得写权威事件流"
    assert rec["kind"] == "initiative.assignment"
    assert rec["initiator"] == "creator-A" and rec["assignee"] == "contract_steward"
    assert rec["principal"] == "creator-A" and rec["ts"]
    assert rec["basis"]["projection"] == "contract" and rec["basis"]["transaction_time"]
    assert rec["selection_digest"]
    triad = engine.selections.read_all()[0]
    assert (triad["principal"], triad["to_role"]) == ("creator-A", "contract_steward")
    assert triad["ts"] and triad["basis"]["transaction_time"]
    assert engine.selections.resolve("C-ACT", "ApproveContract") == "creator-A"


def test_selection_requires_principal_and_basis():
    """无主体或无投影依据不得选择；拒绝不留半条账。"""
    from kernel.selection import (SelectionLedger, SelectionPrincipalRequired,
                                  SelectionBasisRequired)
    led = SelectionLedger()
    good_basis = {"projection": "contract", "transaction_time": "2026-01-01T00:00:00+00:00"}
    with pytest.raises(SelectionPrincipalRequired):
        led.record(principal="", entity="C-ACT", action="ApproveContract",
                   to_role="contract_steward", basis=good_basis)
    with pytest.raises(SelectionBasisRequired):
        led.record(principal="creator-A", entity="C-ACT", action="ApproveContract",
                   to_role="contract_steward", basis={})
    assert led.read_all() == []


def test_selection_rejects_option_not_offered():
    """选择不得造选项：未给出的 Action 一律拒绝。"""
    from kernel.selection import SelectionNotOffered
    _, engine, trig = _initiative_setup()
    _run_once(engine, trig)
    with pytest.raises(SelectionNotOffered):
        engine.select(principal="creator-A", entity_id="C-ACT",
                      action="VoidContract", to_role="contract_steward")
    assert engine.selections.read_all() == []


def test_selection_rejects_role_without_execute_right():
    """可见但无执行权的切面不得承接责任（notice 不能变 assignment）。"""
    from kernel.selection import SelectionNotOffered
    _, engine, trig = _initiative_setup()
    engine.registry.anchor("domain:ContractAggregate", "C-ACT", "creator-A",
                           ["contract_steward", "qc_inspector"], positions=_GOV_VIEW)
    _run_once(engine, trig, candidates=("contract_steward", "qc_inspector"))
    with pytest.raises(SelectionNotOffered):
        engine.select(principal="creator-A", entity_id="C-ACT",
                      action="ApproveContract", to_role="qc_inspector")


def test_anchor_rejects_undeclared_role():
    """锚定只可收窄：域外角色不得被造进可见集（fail-closed）。"""
    from kernel.stewardship import UndeclaredRole, StewardshipRegistry
    k, _, _ = _initiative_setup()
    with pytest.raises(UndeclaredRole, match="UNDECLARED-ROLE"):
        StewardshipRegistry(k.store).anchor(
            "domain:ContractAggregate", "C-ACT", "creator-A", ["outsider"])


def test_selection_rejects_non_initiator_principal():
    """选择权只归上一轮发起人：任意调用方不得自称。"""
    from kernel.selection import SelectionPrincipalMismatch
    _, engine, trig = _initiative_setup()
    _run_once(engine, trig)
    with pytest.raises(SelectionPrincipalMismatch, match="SELECTION-PRINCIPAL-MISMATCH"):
        engine.select(principal="mallory", entity_id="C-ACT",
                      action="ApproveContract", to_role="contract_steward")
    assert engine.selections.read_all() == []              # 拒绝不留半条账


def test_resolve_is_action_scoped():
    """同一实体不同动作的责任人可能不同：解析必须显式给动作。"""
    from kernel.selection import SelectionLedger
    led = SelectionLedger()
    basis = {"projection": "contract", "transaction_time": "2026-01-01T00:00:00+00:00"}
    led.record(principal="alice", entity="C-1", action="ApproveContract",
               to_role="contract_steward", basis=basis)
    led.record(principal="bob", entity="C-1", action="VoidContract",
               to_role="contract_steward", basis=basis)
    assert led.resolve("C-1", "ApproveContract") == "alice"
    assert led.resolve("C-1", "VoidContract") == "bob"
    assert led.resolve("C-1", "RegisterContract") is None


def test_selection_is_idempotent_on_retry():
    """同一决策重试（主体/岗位/依据/档位全同）返回原记录，不重复留账。"""
    from kernel.selection import SelectionLedger
    led = SelectionLedger()
    basis = {"projection": "contract", "transaction_time": "2026-01-01T00:00:00+00:00"}
    first = led.record(principal="alice", entity="C-1", action="ApproveContract",
                       to_role="contract_steward", basis=basis)
    again = led.record(principal="alice", entity="C-1", action="ApproveContract",
                       to_role="contract_steward", basis=basis)
    assert again == first and again["digest"] == first["digest"]
    assert len(led.read_all()) == 1
    # 承接岗位不同 = 新决策，仍要留账
    led.record(principal="alice", entity="C-1", action="ApproveContract",
               to_role="qc_inspector", basis=basis)
    assert len(led.read_all()) == 2


def test_select_retry_appends_single_assignment():
    """引擎层幂等：重复 select 返回同一 assignment，观察通道只留一条。"""
    _, engine = _assigned()
    first = engine.select(principal="creator-A", entity_id="C-ACT",
                          action="ApproveContract", to_role="contract_steward")
    second = engine.select(principal="creator-A", entity_id="C-ACT",
                           action="ApproveContract", to_role="contract_steward")
    assert second == first
    assert len(engine.selections.read_all()) == 1
    kinds = [r["kind"] for r in engine.session.read_all()]
    assert kinds.count("initiative.assignment") == 1


def test_initiator_lands_in_event_metadata_without_touching_eight_fields():
    """发起人进追加审计元数据；执行人 principal 与事件八字段均不变（KS-1.2）。"""
    k, _, _ = _initiative_setup()
    ev = k.submit("ApproveContract",
                  {"contract_id": "C-ACT", "status": "pending", "amount": 500000},
                  "holder-B", roles=("contract_steward",), initiator="creator-A")
    assert ev.principal == "holder-B", "执行人身份不变（责任不串位）"
    assert set(vars(ev)) == {"event_id", "stream_id", "expected_version",
                             "event_type", "payload", "transaction_time",
                             "action_id", "principal"}, "八字段结构不得扩张"
    appended = [a for a in k.store.audit if a["kind"] == "appended"][-1]
    assert appended["initiator"] == "creator-A"


def test_initiator_survives_filestore_replay(tmp_path):
    """发起人身份随事件日志持久化，重启重放后可重建（责任链不断）。"""
    from kernel.filestore import FileStore
    p = tmp_path / "events.jsonl"
    FileStore(p).commit(
        "RecordDecision", "decision", 0, "Decision@1",
        {"valid_time": "2026-01-01T00:00:00+00:00",
         "projection_ref": "proj-1", "session_ref": "sess-1"},
        "steward", initiator="agent-1")
    again = FileStore(p)                                   # 重启：以文件为准重放
    appended = [a for a in again.audit if a["kind"] == "appended"][-1]
    assert appended["initiator"] == "agent-1"
    assert set(vars(again.streams["decision"][0])) == {
        "event_id", "stream_id", "expected_version", "event_type",
        "payload", "transaction_time", "action_id", "principal"}


def test_selection_rejects_stale_basis():
    """本实体被推进后候选依据陈旧，必须重渲染后再选（SELECTION-STALE-BASIS）。"""
    from kernel.selection import SelectionStaleBasis
    k, engine, trig = _initiative_setup()
    _run_once(engine, trig)
    k.submit("ApproveContract",
             {"contract_id": "C-ACT", "status": "pending", "amount": 500000},
             "holder-B", roles=("contract_steward",))          # 同一实体被推进
    with pytest.raises(SelectionStaleBasis, match="SELECTION-STALE-BASIS"):
        engine.select(principal="creator-A", entity_id="C-ACT",
                      action="ApproveContract", to_role="contract_steward")
    assert engine.selections.read_all() == [], "陈旧依据不得留账"


def test_selection_basis_carries_render_watermark():
    """候选与选择记录都携带渲染水位，事后可复核选择基于哪个快照。"""
    _, engine, trig = _initiative_setup()
    recs = _run_once(engine, trig)
    proj = engine.projections["contract"]
    assert recs[0]["basis"]["watermark"] == proj.head()
    chosen = engine.select(principal="creator-A", entity_id="C-ACT",
                           action="ApproveContract", to_role="contract_steward")
    assert chosen["basis"]["watermark"] == proj.head()
    assert engine.selections.read_all()[0]["basis"]["watermark"] == proj.head()


def test_projection_stamp_declares_freshness():
    """投影自报水位与新鲜度：源流推进后 is_fresh 转 False，rebuild 后恢复。"""
    k, engine, _ = _initiative_setup()
    proj = engine.projections["contract"]
    assert proj.is_fresh()
    assert proj.stamp() == {"projection": "contract",
                            "transaction_time": proj.decision_ref()["transaction_time"],
                            "watermark": proj.head()}
    k.submit("RegisterContract",
             {"contract_id": "C-NEW", "amount": 1, "party_refs": []},
             "creator-A", roles=("contract_steward",))
    assert not proj.is_fresh(), "源流推进后投影必须自报不新鲜"
    proj.rebuild()
    assert proj.is_fresh()


# ---------- 续办只读视图：谁在等谁、办什么、何时到期 ----------
def _assigned(policy=None):
    """跑一轮候选 + 选择，返回 (k, engine)，已有一条责任传递记录。"""
    if policy is None:
        k, engine, trig = _initiative_setup()
    else:
        k, engine, trig = _engine_with_policy(policy)
    _run_once(engine, trig)
    engine.select(principal="creator-A", entity_id="C-ACT",
                  action="ApproveContract", to_role="contract_steward")
    return k, engine


def test_continuation_lists_open_assignment_without_fake_deadline():
    """无 SLA 档位时不臆造期限：due_at 为 None，状态 open。"""
    _, engine = _assigned()
    rows = engine.continuation.assignments()
    assert len(rows) == 1
    row = rows[0]
    assert (row["entity"], row["action"], row["assignee"], row["initiator"]) == (
        "C-ACT", "ApproveContract", "contract_steward", "creator-A")
    assert row["projection"] == "contract"
    assert row["status"] == "open" and row["watermark"] == row["head"]
    assert row["due_at"] is None, "未声明 SLA 就不得编造到期时间"
    assert engine.continuation.awaiting("C-ACT")["assignee"] == "contract_steward"
    assert engine.continuation.summary() == {"assignments": 1, "open": 1,
                                             "stale": 0, "overdue": 0}


def test_continuation_derives_due_at_from_policy_sla():
    """有 SLA 档位时到期 = 选择时刻 + sla_hours（同一档位口径，不另立规则）。"""
    import datetime as dt
    _, engine = _assigned(policy=_policy())
    row = engine.continuation.assignments()[0]
    assert row["tier"] == "dual_review" and row["sla_hours"] == 24
    assert dt.datetime.fromisoformat(row["due_at"]) > \
        dt.datetime.fromisoformat(row["assigned_at"])
    assert row["overdue"] is False


def test_continuation_marks_stale_after_stream_advances():
    """本实体被推进后，既有责任传递立即转 stale（与 SELECTION-STALE-BASIS 同口径）。"""
    k, engine = _assigned()
    k.submit("ApproveContract",
             {"contract_id": "C-ACT", "status": "pending", "amount": 500000},
             "holder-B", roles=("contract_steward",))
    row = engine.continuation.assignments()[0]
    assert row["status"] == "stale" and row["head"] > row["watermark"]
    assert engine.continuation.summary() == {"assignments": 1, "open": 0,
                                             "stale": 1, "overdue": 0}


def test_entity_watermark_isolates_cross_entity_advance():
    """同一流内其它实体推进不得误伤：C-ACT 的待办仍 open，且仍可选择。"""
    k, engine = _assigned()
    k.submit("RegisterContract",
             {"contract_id": "C-NEW", "amount": 100, "party_refs": []},
             "creator-A", roles=("contract_steward",))          # 另一实体推进
    row = engine.continuation.assignments()[0]
    assert row["status"] == "open", "跨实体推进不应让 C-ACT 的待办陈旧"
    assert row["head"] == row["watermark"], "实体水位只看本实体事实"
    sel = engine.select(principal="creator-A", entity_id="C-ACT",
                        action="ApproveContract", to_role="contract_steward")
    assert sel["kind"] == "initiative.assignment"


def test_projection_requires_entity_key():
    """投影必须声明实体标识：缺失即拒绝；显式归属只认标识字段（禁止隐式归属）。"""
    from kernel.projection import Projection, ProjectionViolation
    from kernel.store import EventStore
    store = EventStore()
    store.commit("RegisterContract", "domain:ContractAggregate", 0,
                 "ContractRegistered@1",
                 {"contract_id": "C-NEW", "party_ref": "C-ACT",
                  "valid_time": "2026-01-01T00:00:00+00:00"}, "holder-A")
    with pytest.raises(ProjectionViolation, match="ENTITY-KEY-MISSING"):
        Projection(store, "loose", lambda s, e: s,
                   streams=["domain:ContractAggregate"])
    strict = Projection(store, "strict", lambda s, e: s,
                        streams=["domain:ContractAggregate"], entity_key="contract_id")
    assert strict.entity_head("C-ACT") == 0, "显式归属不得被同名字段值污染"
    assert strict.entity_head("C-NEW") == 1


def test_timeline_matches_declared_entity_key_only():
    """时间线归属只认投影声明的 entity_key，禁止 payload 任意值匹配。"""
    from kernel.continuation import ContinuationView
    from kernel.projection import Projection
    from kernel.selection import SelectionLedger
    from kernel.session import SessionChannel
    from kernel.store import EventStore
    store = EventStore()
    store.commit("RegisterContract", "domain:ContractAggregate", 0,
                 "ContractRegistered@1",
                 {"contract_id": "C-NEW", "party_ref": "C-ACT",
                  "valid_time": "2026-01-01T00:00:00+00:00"}, "holder-A")
    proj = Projection(store, "strict", lambda s, e: s,
                      streams=["domain:ContractAggregate"], entity_key="contract_id")
    view = ContinuationView({"strict": proj}, SessionChannel(), SelectionLedger())
    assert view.timeline("C-ACT") == [], "同值旁路字段不得把别的实体事件算进时间线"
    assert [e["kind"] for e in view.timeline("C-NEW")] == ["event"]


def test_continuation_timeline_merges_events_and_observations():
    """时间线同时给出权威事件与观察记录，且邀请早于责任传递。"""
    _, engine = _assigned()
    tl = engine.continuation.timeline("C-ACT", "contract")
    kinds = [e["kind"] for e in tl]
    assert {"event", "invitation", "assignment"} <= set(kinds)
    assert kinds.index("invitation") < kinds.index("assignment")
    assert {e["source"] for e in tl} == {"event", "observation"}


def test_continuation_is_read_only():
    """只读视图不得改变任何状态：事件流 / 会话 / 选择账本计数全不变。"""
    k, engine = _assigned()
    def snapshot():
        return (sum(len(s) for s in k.store.streams.values()),
                len(k.session.read_all()), len(engine.selections.read_all()),
                engine.projections["contract"].head())
    before = snapshot()
    view = engine.continuation
    view.assignments()
    view.assignments("contract")
    view.awaiting("C-ACT")
    view.timeline("C-ACT", "contract")
    view.summary()
    assert snapshot() == before


# ---------- 观察链持久化：选择账本 / 管理域锚定随会话通道复原 ----------
def test_selection_ledger_survives_restart(tmp_path):
    """选择审计账本随观察通道落盘：重启重放后可复原 resolve / assigned_to。"""
    from kernel.selection import SelectionLedger
    from kernel.session import FileSession
    p = tmp_path / "session.jsonl"
    led = SelectionLedger(FileSession(p))
    led.record(principal="creator-A", entity="C-ACT", action="ApproveContract",
               to_role="contract_steward", tier="dual_review", sla_hours=24,
               basis={"projection": "contract",
                      "transaction_time": "2026-01-01T00:00:00+00:00"})
    again = SelectionLedger(FileSession(p))                # 重启：重放观察记录
    assert again.resolve("C-ACT", "ApproveContract") == "creator-A"
    assert again.assigned_to("C-ACT", "ApproveContract") == "contract_steward"
    assert [r["digest"] for r in again.read_all()] == [r["digest"] for r in led.read_all()]


def test_selection_replay_rejects_incomplete_record(tmp_path):
    """观察通道里的选择记录缺三元组成分 → 重放即拒（账本不可信，fail-closed）。"""
    from kernel.selection import SelectionLedger, SelectionViolation
    from kernel.session import FileSession
    p = tmp_path / "session.jsonl"
    FileSession(p).append("creator-A", {
        "kind": "initiative.selection", "entity": "C-ACT",
        "action": "ApproveContract", "to_role": "contract_steward"})   # 缺 basis/ts
    with pytest.raises(SelectionViolation, match="SELECTION-REPLAY-INVALID"):
        SelectionLedger(FileSession(p))


def test_anchor_survives_restart_with_revalidation(tmp_path):
    """显式锚定随观察通道持久化：重启重放恢复，并重新经过在册角色校验。"""
    from kernel.session import FileSession
    from kernel.stewardship import StewardshipRegistry
    k, _, _ = _initiative_setup()
    p = tmp_path / "session.jsonl"
    StewardshipRegistry(k.store, session=FileSession(p),
                        positions=_GOV_VIEW).anchor(
        "domain:ContractAggregate", "C-ACT", "creator-A",
        ["contract_steward", "qc_inspector"])
    again = StewardshipRegistry(k.store, session=FileSession(p), positions=_GOV_VIEW)
    assert again.domain_of("domain:ContractAggregate", "C-ACT").members == \
        frozenset({"contract_steward", "qc_inspector"})


def test_anchor_replay_rejects_tampered_record(tmp_path):
    """篡改锚定记录（越权主体 / 域外角色）→ 重放拒绝，不静默接受。"""
    from kernel.session import FileSession
    from kernel.stewardship import (DomainOwnerMismatch, StewardshipRegistry,
                                    UndeclaredRole)
    k, _, _ = _initiative_setup()
    p1 = tmp_path / "tamper-owner.jsonl"
    FileSession(p1).append("mallory", {
        "kind": "initiative.anchor", "stream_id": "domain:ContractAggregate",
        "entity_id": "C-ACT", "roles": ["contract_steward"]})
    with pytest.raises(DomainOwnerMismatch):
        StewardshipRegistry(k.store, session=FileSession(p1))
    p2 = tmp_path / "tamper-role.jsonl"
    FileSession(p2).append("creator-A", {
        "kind": "initiative.anchor", "stream_id": "domain:ContractAggregate",
        "entity_id": "C-ACT", "roles": ["outsider"]})
    with pytest.raises(UndeclaredRole, match="UNDECLARED-ROLE"):
        StewardshipRegistry(k.store, session=FileSession(p2))


def test_engine_selection_ledger_is_channel_backed(tmp_path):
    """引擎的选择账本与观察通道共用同一存储：重启后仍能解析该动作的发起人。"""
    from kernel.initiative import InitiativeEngine
    from kernel.session import FileSession
    k, engine, trig = _initiative_setup()
    p = tmp_path / "session.jsonl"
    durable = InitiativeEngine(engine.projections, FileSession(p), engine.registry,
                               engine.ledger)
    _run_once(durable, trig)
    durable.select(principal="creator-A", entity_id="C-ACT",
                   action="ApproveContract", to_role="contract_steward")
    again = InitiativeEngine(engine.projections, FileSession(p), engine.registry,
                             engine.ledger)
    assert again.selections.resolve("C-ACT", "ApproveContract") == "creator-A"
    assert again.selections.assigned_to("C-ACT", "ApproveContract") == "contract_steward"


# ---------- 零新事实收件箱：路由只读、超期是缺席的投影、幂等含依据维度 ----------
def test_continuation_due_at_anchors_on_authoritative_fact_time():
    """到期起点取权威事实时间（basis.transaction_time），不是观察层选择时刻。

    这是"超期可由权威日志证明"的前提：观察记录可丢弃重建，若以选择时刻计时，
    超期结论就无法从事件流复核。行上 sla_anchor 显式标注所用口径。
    """
    import datetime as dt
    _, engine = _assigned(policy=_policy())
    row = engine.continuation.assignments()[0]
    assert row["sla_anchor"] == "authority"
    basis_tx = engine.selections.read_all()[0]["basis"]["transaction_time"]
    assert dt.datetime.fromisoformat(row["due_at"]) == (
        dt.datetime.fromisoformat(basis_tx) + dt.timedelta(hours=row["sla_hours"]))


def test_continuation_overdue_is_derived_from_absence_not_an_event():
    """"没人办"= 权威事实已落地足够久且无后续事件；不需要 expired 事件。

    构造：把 SLA 压到 1 小时，权威事实时间回填到 2 小时前 → 读时即判超期，
    且 EventStore 与观察通道均零增长（纯读派生）。
    """
    import datetime as dt
    k, engine = _assigned(policy=_policy())
    sel = engine.selections.read_all()[0]
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat(
        timespec="seconds")
    sel["basis"]["transaction_time"] = old        # 只改内存中的依据时间，不写任何流
    sel["sla_hours"] = 1
    before_events = sum(len(s) for s in k.store.streams.values())
    before_obs = len(k.session.read_all())
    row = engine.continuation.assignments()[0]
    assert row["overdue"] is True and row["status"] == "open"
    assert row["sla_anchor"] == "authority"
    assert sum(len(s) for s in k.store.streams.values()) == before_events
    assert len(k.session.read_all()) == before_obs, "超期判定不得产生任何写入"
    assert engine.continuation.summary()["overdue"] == 1


def test_continuation_falls_back_to_selection_anchor_without_authority_time():
    """缺权威时间的旧记录：回退选择时刻并标注 selection，不静默假装权威。"""
    _, engine = _assigned(policy=_policy())
    sel = engine.selections.read_all()[0]
    sel["basis"].pop("transaction_time")
    row = engine.continuation.assignments()[0]
    assert row["sla_anchor"] == "selection"
    assert row["due_at"] is not None


def test_routing_is_read_only_and_reuses_gate_ledger():
    """路由推导零写入，且执行权判定与 submit 门控同源（不造第二张皮）。"""
    k, engine, trig = _initiative_setup()
    before = sum(len(s) for s in k.store.streams.values())
    recs = _run_once(engine, trig)
    assert recs and recs[0]["can_execute"] is True
    assert sum(len(s) for s in k.store.streams.values()) == before
    # 同源核对：邀请的可执行结论 == 能力账簿判定 == 权限矩阵声明
    role = recs[0]["to_role"]
    assert engine.ledger.can_execute("ApproveContract", [role]) is True
    assert role in k.compiled["ApproveContract"].permissions["roles"]


def test_repeated_dispatch_same_basis_is_idempotent():
    """同一依据的重复派发只留一条 assignment（投影重放安全）。"""
    k, engine, trig = _initiative_setup()
    _run_once(engine, trig)
    first = engine.select(principal="creator-A", entity_id="C-ACT",
                          action="ApproveContract", to_role="contract_steward")
    _run_once(engine, trig)                      # 同水位重跑（模拟重放）
    second = engine.select(principal="creator-A", entity_id="C-ACT",
                           action="ApproveContract", to_role="contract_steward")
    assert first["selection_digest"] == second["selection_digest"]
    assert len(engine.continuation.assignments()) == 1


def test_stale_notice_submission_is_rejected_by_condition_gate():
    """旧通知不携带授权：状态已迁移后按原通知提交 → 条件门拒绝，无事件追加。"""
    from kernel.errors import ConditionalRejected
    k, engine = _assigned()
    k.submit("ApproveContract",
             {"contract_id": "C-ACT", "status": "pending", "amount": 500000},
             "holder-B", roles=("contract_steward",))
    before = sum(len(s) for s in k.store.streams.values())
    with pytest.raises(ConditionalRejected):
        k.submit("ApproveContract",
                 {"contract_id": "C-ACT", "status": "pending", "amount": 500000},
                 "holder-B", roles=("contract_steward",))
    assert sum(len(s) for s in k.store.streams.values()) == before


def test_missing_appointment_yields_no_capability_not_a_pass():
    """任命缺失（角色无声明）→ 能力账簿无匹配，绝不放行（fail-closed）。"""
    from kernel.initiative import NoCapability
    _, engine, trig = _initiative_setup()
    assert engine.ledger.can_execute("ApproveContract", ["viewer"]) is False
    with pytest.raises(NoCapability):
        engine.seek(principal="nobody", roles=["viewer"], projection_name="contract",
                    triggers=[trig], stream_id="domain:ContractAggregate",
                    entity_id="C-ACT")


# ---------- T0：只读收件箱（enabled_actions） ----------
# 三问漏斗的落地：路由只读派生；"该办未办"由缺席证明，不新增任何事件。
def test_file_session_repairs_trailing_half_record(tmp_path):
    """观察通道同样只修复尾部半行：崩溃后重启不丢已确认记录。"""
    from kernel.session import FileSession
    p = tmp_path / "session.jsonl"
    s = FileSession(p)
    s.append("creator-A", {"kind": "initiative.notice", "entity": "C-1"})
    good = p.read_text(encoding="utf-8")
    p.write_text(good + '{"kind": "initiative.', encoding="utf-8")
    again = FileSession(p)
    assert len(again.read_all()) == 1
    assert p.read_text(encoding="utf-8") == good


def test_inbox_is_read_only_and_mirrors_permission_gate():
    """收件箱零写入，且权限判定与 submit 同源（无执行权即不出现）。"""
    from kernel.initiative import enabled_actions
    k, _, _ = _initiative_setup()
    before = (sum(len(s) for s in k.store.streams.values()), len(k.store.audit),
              len(k.session.read_all()), len(k.interpreter_audit))
    args = dict(stream_id="domain:ContractAggregate", entity_id="C-ACT",
                principal="steward-A")
    assert enabled_actions(k.store, k.compiled, roles=("contract_steward",),
                           action_types=("ApproveContract",), **args) == ("ApproveContract",)
    assert enabled_actions(k.store, k.compiled, roles=("viewer",),
                           action_types=("ApproveContract",), **args) == ()
    after = (sum(len(s) for s in k.store.streams.values()), len(k.store.audit),
             len(k.session.read_all()), len(k.interpreter_audit))
    assert after == before, "收件箱是纯读派生：事件、审计、会话、求值审计均零增长"


def test_inbox_disappears_once_business_fact_lands():
    """业务事实落地后条件不再成立 → 动作移出收件箱（通知过期由门禁兜底）。"""
    from kernel.initiative import enabled_actions
    k, _, _ = _initiative_setup()
    args = dict(stream_id="domain:ContractAggregate", entity_id="C-ACT",
                principal="steward-A", roles=("contract_steward",),
                action_types=("ApproveContract",))
    assert enabled_actions(k.store, k.compiled, **args) == ("ApproveContract",)
    k.submit("ApproveContract", {"contract_id": "C-ACT"},
             "holder-B", roles=("contract_steward",))
    assert enabled_actions(k.store, k.compiled, **args) == ()


def test_inbox_unknown_entity_is_empty_not_an_invitation():
    """无权威投影的实体 → 依赖条件的动作不进入收件箱（不发无法兑现的邀请）。

    只筛无条件的 VoidContract 不在断言内：它没有条件段，内核同样允许提交 ——
    收件箱忠实反映"可提交"，不替声明补业务语义。要挡住它，应在声明里加条件。
    """
    from kernel.initiative import enabled_actions
    k, _, _ = _initiative_setup()
    assert enabled_actions(k.store, k.compiled, stream_id="domain:ContractAggregate",
                           entity_id="C-NONE", principal="steward-A",
                           roles=("contract_steward",),
                           action_types=("ApproveContract",)) == ()


def test_inbox_reuses_the_same_evaluator_and_principal_env():
    """结构守卫：收件箱复用 submit 的物化、受限解释器与主体环境，不另造语义。"""
    import kernel.initiative as ini
    import kernel.pipeline as pipe
    from interpreter.boolean_profile import eval_boolean
    assert ini.materialize is pipe.materialize
    assert ini.eval_boolean is pipe.eval_boolean is eval_boolean
    assert ini.principal_env is pipe.principal_env
    # 多角色语义必须与 _evaluate 一致：单角色退化为字符串，多角色为元组
    assert ini.principal_env("p", ("a",))["role"] == "a"
    assert ini.principal_env("p", ("a", "b"))["role"] == ("a", "b")
