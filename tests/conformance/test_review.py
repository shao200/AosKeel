"""tests/conformance/test_review.py —— aos review 审核清单（只读咨询）。
判据：profile 锚点现状进清单；drafts 草案候选（含 candidate_links）逐项列出且
晋升建议携带 GOV-1 提案要求；带角色的 action 无治理授权/未声明岗位 → 前置提醒
（注册时会 fail-closed 拒绝）；review 本身零写入（只读纪律）；真实正典上报告生成。
"""
import sys
from pathlib import Path
import pytest
import yaml
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.review import review_report, format_report
from kernel.profile import init_profile
@pytest.fixture()
def fresh_project(tmp_path):
    """最小实例：init 产出 profile；无正典声明（锚点缺失进清单）。"""
    init_profile("rev-proj", "minimal", root=tmp_path)
    return tmp_path
def _cats(r):
    return [(i["category"], i["subject"]) for i in r["items"]]
def test_profile_anchors_listed(fresh_project):
    r = review_report(root=fresh_project)
    assert any(c == "profile-anchor" for c, _ in _cats(r))   # 新项目 roadmap 进清单
    assert r["project"] == "rev-proj" and r["depth"] == "minimal"
def test_draft_items_with_gov1_advise(fresh_project):
    """草案候选 → 晋升项 + 候选引用项，建议强制 GOV-1 提案。"""
    d = fresh_project / "spec/drafts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "draft-rev-demo.yaml").write_text(yaml.safe_dump({
        "objects": [{"object_type": "Widget", "identity": "widget_id",
                     "properties": {"widget_id": {"type": "string"}}}],
        "actions": [], "aggregates": [{"aggregate": "WidgetAggregate",
                                       "stream": "domain:WidgetAggregate",
                                       "evaluation_budget": 100}],
        "candidate_links": [{"link_type": "GadgetRef", "source": "Widget.arm_id",
                             "target": "Gadget.gadget_id"}],
    }, allow_unicode=True), encoding="utf-8")
    r = review_report(root=fresh_project)
    assert any(d2["objects"] == 1 for d2 in r["drafts"])
    promote = next(i for i in r["items"] if i["category"] == "draft-promotion")
    assert "draft-rev-demo" in promote["subject"]
    assert "--proposal-ref" in promote["advise"] and "GOV-1" in promote["advise"]
    link = next(i for i in r["items"] if i["category"] == "draft-link")
    assert "Widget.arm_id → Gadget.gadget_id" in link["subject"]
def test_unbacked_action_flagged(fresh_project):
    """带角色的 action 无治理授权 → 前置提醒（注册会拒绝，审核先行）。"""
    acts = fresh_project / "spec/ontology/actions"
    acts.mkdir(parents=True)
    (acts / "Sneaky.action.yaml").write_text(
        yaml.safe_dump({"action_type": "Sneaky",
                        "permissions": {"roles": ["shadow_lord"]}}),
        encoding="utf-8")
    r = review_report(root=fresh_project)
    cats = _cats(r)
    assert ("gov-missing", "Action Sneaky 无治理授权") in cats
    assert ("gov-position", "Action Sneaky 出示未声明岗位 ['shadow_lord']") in cats
def test_review_is_read_only(fresh_project):
    """只读纪律：review 前后 spec 树字节零变化。"""
    def snap():
        return {str(p.relative_to(fresh_project)): p.read_bytes()
                for p in sorted(fresh_project.rglob("*")) if p.is_file()}
    before = snap()
    review_report(root=fresh_project)
    assert snap() == before
def test_format_report_and_clean_state(fresh_project):
    r = review_report(root=fresh_project)
    text = format_report(r)
    assert "待人工裁决" in text and "R-01" in text
    r["items"] = []
    assert "流水线就绪" in format_report(r)
def test_real_canonical_report():
    """真实正典：模板全部对账通过 → 无 gov 缺口项（有则说明治理漂移）。"""
    r = review_report()                                    # 仓库正典
    assert not any(c in ("gov-missing", "gov-position")
                   for c, _ in _cats(r))                   # 治理对账干净
