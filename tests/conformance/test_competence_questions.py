"""tests/conformance/test_competence_questions.py —— 理论层修补：CQ 可执行契约回归。

判据（三条缺一不可）：
1. guide/06 的十张能力问题全部有可执行回答，且回答走真实内核而非影子实现；
2. 清单完整性 fail-closed —— 删题/改题名/未注册回答者即拒绝，不把缺失当通过；
3. 断言可证伪 —— 篡改期望或调包回答者必须导致 CQ 失败。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import cq

def _copy_decls(tmp_path, mutate=None):
    """把十张声明复制进临时目录，可选按文件名前缀改文本（隔离主仓库）。"""
    for p in sorted(cq.CQ_DIR.glob("*.cq.yaml")):
        text = p.read_text(encoding="utf-8")
        if mutate is not None:
            text = mutate(p.name, text)
        (tmp_path / p.name).write_text(text, encoding="utf-8")
    return tmp_path

@pytest.mark.parametrize("cid", cq.EXPECTED_IDS)
def test_each_competency_question_executes(cid):
    results = cq.run([cid])
    assert len(results) == 1
    r = results[0]
    assert r["ok"], (f"{cid} 未兑现：期望 {r.get('expected')!r} "
                     f"实际 {r.get('actual', r.get('error'))!r}")
    assert r["question"] and r["evidence"]

def test_ten_questions_are_a_frozen_checklist():
    assert [d["id"] for d in cq.declarations()] == list(cq.EXPECTED_IDS)

def test_fixture_is_a_real_kernel_run_not_a_mock():
    """夹具必须真的走两次 Kernel.submit 并留下八字段事件 + 会话观测。"""
    ctx = cq.PRESETS["contract_approved"]()
    stream = ctx["store"].streams["domain:ContractAggregate"]
    assert [ev.event_type for ev in stream] == ["RegisterContract@1", "ApproveContract@1"]
    assert all(ev.payload.get("valid_time") for ev in stream)
    assert len(ctx["session"].read_all()) == 1

def test_missing_question_is_refused(tmp_path):
    """删掉难题不等于全绿：少一张即 CQ-INCOMPLETE。"""
    for p in sorted(cq.CQ_DIR.glob("*.cq.yaml")):
        if p.name.startswith("CQ-10"):
            continue
        (tmp_path / p.name).write_bytes(p.read_bytes())
    with pytest.raises(cq.CQError, match="CQ-INCOMPLETE"):
        cq.declarations(tmp_path)

def test_unknown_answerer_is_refused(tmp_path):
    def mutate(name, text):
        return text.replace("projection.snapshot", "ghost.answerer") if name.startswith("CQ-1.") else text
    with pytest.raises(cq.CQError, match="CQ-ANSWERER-UNKNOWN"):
        cq.declarations(_copy_decls(tmp_path, mutate))

def test_duplicate_id_is_refused(tmp_path):
    def mutate(name, text):
        return text.replace("id: CQ-9", "id: CQ-1") if name.startswith("CQ-9") else text
    with pytest.raises(cq.CQError, match="CQ-ID-DUPLICATE"):
        cq.declarations(_copy_decls(tmp_path, mutate))

def test_unknown_operator_is_refused(tmp_path):
    def mutate(name, text):
        return text.replace("op: equals", "op: whatever") if name.startswith("CQ-1.") else text
    with pytest.raises(cq.CQError, match="CQ-OPERATOR-UNKNOWN"):
        cq.declarations(_copy_decls(tmp_path, mutate))

def test_expectation_tamper_is_detected(tmp_path):
    """改期望值必须被断言抓到（声明不是装饰）。"""
    def mutate(name, text):
        return text.replace("value: approved", "value: void") if name.startswith("CQ-1.") else text
    r = cq.run(["CQ-1"], root=_copy_decls(tmp_path, mutate))[0]
    assert not r["ok"]
    assert r["expected"] == "void" and r["actual"] == "approved"

def test_answerer_swap_is_detected(monkeypatch):
    """回答者被调包必须失败 —— 证明断言真的在比较实际值。"""
    monkeypatch.setitem(cq.ANSWERERS, "projection.snapshot", lambda ctx, probe: "forged")
    r = cq.run(["CQ-1"])[0]
    assert not r["ok"] and r["actual"] == "forged"

def test_unknown_cq_id_is_refused():
    with pytest.raises(cq.CQError, match="CQ-UNKNOWN-ID"):
        cq.run(["CQ-99"])
