"""tests/conformance/test_impact.py —— 变更影响分析守卫（INTEGRITY-6）。
判据：aos impact 是**事前咨询**，三关是**事后检测**——本测试守的是咨询报告的
正确性与边界，MUST NOT 把它接成闸门。
1) 反向引用图覆盖已声明引用位：效果键、条件快照输入、流程步骤/补偿、聚合不变量；
2) 目标解析三形态：声明名 / spec 文件路径 / ObjectType.prop，未知 → IMPACT-UNKNOWN；
3) 报告纯读：不落盘、不改 spec；CLI 缺目标 → REFUSED（不裸 traceback）。
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import impact
from cli.main import main as cli_main
def test_graph_covers_effect_and_condition_edges():
    g = impact.build_graph()
    assert g["nodes"].get("Contract.status") == "property"
    rels = {(src, rel) for src, rel, _ in g["edges"]["Contract.status"]}
    assert ("ApproveContract", "效果键") in rels
    assert ("RegisterContract", "效果键") in rels
    assert ("ApproveContract", "条件快照输入") in rels
def test_graph_covers_process_and_aggregate_edges():
    g = impact.build_graph()
    ups = {src for src, _, _ in g["edges"]["ApproveContract"]}
    assert "ContractRenewal" in ups                    # process step
    ups = {src for src, _, _ in g["edges"]["VoidContract"]}
    assert "ContractRenewal" in ups                    # compensation
    ups = {src for src, _, _ in g["edges"]["NoOrphanContract"]}
    assert "ContractAggregate" in ups                  # aggregate invariants
def test_resolve_forms_and_unknown():
    g = impact.build_graph()
    assert impact.resolve("ApproveContract", g) == "ApproveContract"
    assert impact.resolve(str(ROOT / "spec/ontology/actions/VoidContract.action.yaml"), g) == "VoidContract"
    assert impact.resolve("Contract.status", g) == "Contract.status"
    assert impact.resolve("NoSuchDeclaration", g) is None
def test_report_advisory_and_exit_codes(capsys):
    assert impact.report("ApproveContract") == 0
    out = capsys.readouterr().out
    assert "IMPACT: ApproveContract（action）" in out
    assert "ContractRenewal" in out                    # 上游
    assert "本工具不放行也不拦截" in out                 # 咨询性声明
    assert impact.report("NoSuchDeclaration") == 1
    assert "IMPACT-UNKNOWN" in capsys.readouterr().out
def test_report_is_read_only():
    # 报告不改写 spec/ 任何文件（派生视图，不落地）
    before = {p: p.read_bytes() for p in (ROOT / "spec").rglob("*.yaml")}
    impact.report("Contract.status")
    assert {p: p.read_bytes() for p in (ROOT / "spec").rglob("*.yaml")} == before
def test_cli_missing_target_refused(capsys):
    assert cli_main(["impact"]) == 1
    assert "REFUSED" in capsys.readouterr().out
