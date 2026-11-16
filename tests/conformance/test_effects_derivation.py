"""tests/conformance/test_effects_derivation.py —— T24 副作用执行点守卫（INTEGRITY-5）。
裂缝修复的判据：示例域状态 MUST 由事件导出，MUST NOT 由调用方自报。
1) 提交事件载荷里的状态效果由声明书写（谎报 claim 进不了载荷）；
2) 状态迁移链 register→approve→void 完全由投影导出，终态可重放核对；
3) 注册期拒绝：效果键不在聚合根声明属性内 / 枚举值越界 / 效果键与 params 重名
   （双事实源在编译期即拒，"不注册谓词性代码，注册数据"的对称面）。
"""
import shutil
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel import registration
from kernel.registration import compile_all
from kernel.sc_compiler import compile_action
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
from kernel.errors import ConditionalRejected, RegistrationFailed
STREAM = "domain:ContractAggregate"
STEWARD = dict(principal="svc", roles=("contract_steward",))
RPARAMS = {"contract_id": "C-1", "amount": 500000}
def _k() -> Kernel:
    return Kernel(EventStore(), SessionChannel(), compile_all())
def test_effect_written_into_event_not_claim():
    k = _k()
    k.submit("RegisterContract", dict(RPARAMS), **STEWARD)
    ev = k.submit("ApproveContract", dict(RPARAMS, status="pending"), **STEWARD)
    assert ev.payload["status"] == "approved"     # 声明效果书写，非调用方 claim
def test_state_transitions_derive_from_events():
    k = _k()
    k.submit("RegisterContract", dict(RPARAMS), **STEWARD)
    k.submit("ApproveContract", dict(RPARAMS), **STEWARD)
    k.submit("VoidContract", dict(RPARAMS, void_reason="risk"), **STEWARD)
    assert k.store.streams[STREAM][-1].payload["status"] == "void"
    with pytest.raises(ConditionalRejected, match="条件校验未通过"):
        k.submit("ApproveContract", dict(RPARAMS), **STEWARD)   # void 态不可再批准
def _sandbox(tmp_path: Path, bad_yaml: str, name: str) -> Path:
    dst = tmp_path / "spec"
    shutil.copytree(ROOT / "spec", dst)
    (dst / "ontology" / "actions" / f"{name}.action.yaml").write_text(
        bad_yaml, encoding="utf-8")
    return dst
def test_registration_rejects_undeclared_effect_property(tmp_path, monkeypatch):
    bad = (
        "action_type: BadEffectProp\naggregate: ContractAggregate\n"
        "params: { contract_id: { type: ref, required: true } }\n"
        "effects: { not_a_property: x }\n"
        "permissions: { roles: [contract_steward], contexts: [ContractContext] }\n")
    monkeypatch.setattr(registration, "SPEC_DIR", _sandbox(tmp_path, bad, "BadEffectProp"))
    assert any("EFFECTS-UNDECLARED-PROP" in f for f in registration._validate_spec())
def test_registration_rejects_effect_value_out_of_enum(tmp_path, monkeypatch):
    bad = (
        "action_type: BadEffectValue\naggregate: ContractAggregate\n"
        "params: { contract_id: { type: ref, required: true } }\n"
        "effects: { status: ratified }\n"
        "permissions: { roles: [contract_steward], contexts: [ContractContext] }\n")
    monkeypatch.setattr(registration, "SPEC_DIR", _sandbox(tmp_path, bad, "BadEffectValue"))
    assert any("EFFECTS-VALUE-OUT-OF-DOMAIN" in f for f in registration._validate_spec())
def test_effect_param_clash_refused_at_compile():
    decl = {"action_type": "ClashAction", "aggregate": "ContractAggregate",
            "params": {"status": {"type": "enum", "required": True}},
            "effects": {"status": "approved"}}
    with pytest.raises(RegistrationFailed, match="双事实源"):
        compile_action(decl, "SPEC-2026-014")
