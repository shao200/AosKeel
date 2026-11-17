"""tests/conformance/test_governance_duty_matrix.py —— 治理面锚点（图1 职责授权矩阵）。
判据：治理声明 steward 必填（P-3）；职责项必须绑定岗位与组织锚点；
授权引用必须指向已声明 Action（声明完整性）；带角色的 Action 必须有治理授权背书
（L3/L4 锚点对账，fail-closed —— 权限不再是无源之水）。
"""
import sys
from pathlib import Path
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from kernel.registration import validate_governance, _validate_governance, _validate_spec
KNOWN_ACTIONS = {"RegisterContract", "ApproveContract", "VoidContract"}
BASE = {  # 合法基线（岗位/组织锚点/授权齐全）
    "governance": "DutyMatrix",
    "steward": "contract-steward-role",
    "duties": [
        {"duty": "approve_contract_duty", "position": "contract_steward",
         "org_unit": "contract-department", "authorizes": ["ApproveContract"]},
    ],
}
def test_real_governance_validates():
    gov = yaml.safe_load((ROOT / "spec/governance/ContractDutyMatrix.governance.yaml")
                         .read_text(encoding="utf-8"))
    assert validate_governance(gov, KNOWN_ACTIONS) == []
def test_missing_steward_rejected():
    gov = {**BASE, "steward": None}
    assert any("STEWARD-MISSING" in f for f in validate_governance(gov, KNOWN_ACTIONS))
def test_missing_position_and_org_unit_rejected():
    gov = {"governance": "D", "steward": "s",
           "duties": [{"duty": "d1", "authorizes": ["ApproveContract"]}]}
    failures = validate_governance(gov, KNOWN_ACTIONS)
    assert any("POSITION-MISSING" in f for f in failures)      # 岗位锚点缺失
    assert any("ORG-UNIT-MISSING" in f for f in failures)      # 组织锚点缺失
def test_empty_authorizes_rejected():
    gov = {"governance": "D", "steward": "s", "duties": [
        {"duty": "d1", "position": "p", "org_unit": "o", "authorizes": []}]}
    assert any("AUTHORIZES-EMPTY" in f for f in validate_governance(gov, KNOWN_ACTIONS))
def test_unknown_action_reference_rejected():
    gov = {"governance": "D", "steward": "s", "duties": [
        {"duty": "d1", "position": "p", "org_unit": "o", "authorizes": ["NoSuchAction"]}]}
    assert any("ACTION-UNKNOWN" in f for f in validate_governance(gov, KNOWN_ACTIONS))
def test_sla_unknown_duty_rejected():
    gov = {**BASE, "sla": [{"duty": "no_such_duty", "response_hours": 48}]}
    assert any("SLA-DUTY-UNKNOWN" in f for f in validate_governance(gov, KNOWN_ACTIONS))
def test_duplicate_duty_rejected():
    gov = {"governance": "D", "steward": "s", "duties": [
        {"duty": "d1", "position": "p", "org_unit": "o", "authorizes": ["ApproveContract"]},
        {"duty": "d1", "position": "p", "org_unit": "o", "authorizes": ["ApproveContract"]}]}
    assert any("DUTY-DUPLICATE" in f for f in validate_governance(gov, KNOWN_ACTIONS))
def test_role_reconciliation_passes_on_real_spec():
    """真实 spec：三个带角色的 Action 均有治理授权背书 → 全量校验零失败。"""
    assert _validate_spec() == []
def test_unbacked_role_rejected(tmp_path):
    """带角色的 Action 无治理背书 → 拒绝（fail-closed：权限须有治理链来源）。"""
    (tmp_path / "ontology" / "actions").mkdir(parents=True)
    (tmp_path / "ontology" / "actions" / "A.action.yaml").write_text(
        "action_type: SoloAction\npermissions: { roles: [steward_rare] }\n",
        encoding="utf-8")
    failures = _validate_governance(tmp_path)
    assert any("GOVERNANCE-AUTHORIZATION-MISSING" in f and "SoloAction" in f
               for f in failures)
def test_backed_role_passes(tmp_path):
    """治理面存在且岗位 ∈ Action 角色 → 对账通过。"""
    (tmp_path / "ontology" / "actions").mkdir(parents=True)
    (tmp_path / "ontology" / "actions" / "A.action.yaml").write_text(
        "action_type: SoloAction\npermissions: { roles: [steward_rare] }\n",
        encoding="utf-8")
    (tmp_path / "governance").mkdir()
    (tmp_path / "governance" / "G.governance.yaml").write_text(
        "governance: G\nsteward: s\nduties:\n  - duty: d1\n    position: steward_rare\n"
        "    org_unit: org1\n    authorizes: [SoloAction]\n", encoding="utf-8")
    assert _validate_governance(tmp_path) == []
