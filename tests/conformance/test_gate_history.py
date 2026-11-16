"""tests/conformance/test_gate_history.py —— 度量口径守卫（INTEGRITY-8）。
判据：闸门事件流是**派生证据**——verify/release 每次运行恰好追加一条 JSONL
（只增，不重写）；记录含逐关 PASS/FAIL；metrics 聚合可答四问
（跑了几次 / 通过率 / 哪关在漂 / 连续通过），空台账明确 METRICS-EMPTY；
追加失败绝不阻断闸门本身（度量是记账，不是把关）。
"""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import gate_history, release_gate
from cli.main import main as cli_main
def _rows(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in
            p.read_text(encoding="utf-8").splitlines() if ln.strip()]
def test_verify_appends_one_pass_record(tmp_path, monkeypatch):
    hist = tmp_path / "gate-history.jsonl"
    monkeypatch.setattr(gate_history, "HISTORY_PATH", hist)
    assert cli_main(["verify"]) == 0
    rows = _rows(hist)
    assert len(rows) == 1 and rows[0]["command"] == "verify"
    assert rows[0]["result"] == "PASS"
    assert set(rows[0]["gates"]) == {"structural", "cryptographic", "registered"}
def test_record_is_append_only_and_marks_failure(tmp_path, monkeypatch):
    hist = tmp_path / "gate-history.jsonl"
    monkeypatch.setattr(gate_history, "HISTORY_PATH", hist)
    gate_history.record("release", {"structural": "PASS"})
    gate_history.record("release", {"structural": "PASS", "tests": "FAIL"})
    rows = _rows(hist)
    assert [r["result"] for r in rows] == ["PASS", "FAIL"]
    before = hist.read_bytes()
    gate_history.record("release", {"structural": "PASS"})
    assert hist.read_bytes().startswith(before)     # 只增：旧字节不动
def test_release_main_records_gate_status(tmp_path, monkeypatch):
    hist = tmp_path / "gate-history.jsonl"
    monkeypatch.setattr(gate_history, "HISTORY_PATH", hist)
    fake = {"ok": False, "manifest": None,
            "steps": [{"step": "structural", "ok": True, "detail": "PASS"},
                      {"step": "codegen", "ok": False, "detail": "drift"}]}
    monkeypatch.setattr(release_gate, "run_gate", lambda *a, **k: fake)
    assert release_gate.main() == 1                  # fail-closed：不出制品
    rows = _rows(hist)
    assert rows[-1]["command"] == "release" and rows[-1]["result"] == "FAIL"
    assert rows[-1]["gates"]["codegen"] == "FAIL"
def test_metrics_report_four_questions(tmp_path, monkeypatch, capsys):
    hist = tmp_path / "gate-history.jsonl"
    monkeypatch.setattr(gate_history, "HISTORY_PATH", hist)
    gate_history.record("verify", {"cryptographic": "FAIL"})
    gate_history.record("verify", {"cryptographic": "PASS"})
    gate_history.record("release", {"codegen": "PASS", "tests": "PASS"})
    assert gate_history.report() == 0
    out = capsys.readouterr().out
    assert "3 次闸门运行" in out and "67%" in out
    assert "漂移计数" in out and "连续通过: 2" in out
def test_metrics_empty_is_advisory(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate_history, "HISTORY_PATH", tmp_path / "none.jsonl")
    assert gate_history.report() == 0
    assert "METRICS-EMPTY" in capsys.readouterr().out
def test_record_failure_never_blocks_gate(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(gate_history, "HISTORY_PATH",
                        tmp_path / "no" / "such" / "dir" / "x.jsonl")
    gate_history.record("verify", {"structural": "PASS"})   # 不抛异常
    assert "WARN" in capsys.readouterr().out
