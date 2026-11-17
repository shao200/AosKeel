"""tests/conformance/test_shadow_online.py —— 在线影子流量对账协议层。
判据：探针契约逐条对账（状态等价 / dict 输出字段等价 / 标量输出等价）；
分歧逐字段列出；坏行（坏 JSON / 缺键）fail-closed 零静默；空记录大声拒绝；
对账器只读（零写入正典）。探针（拦流记录）属实例侧 —— 本测试只测协议层。
"""
import json
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.shadow_online import reconcile_probes
def _probe(action="RegisterContract", inp=None, ls=0, lo=None, ms=0, mo=None):
    return {"action": action, "input": inp or {}, "legacy": {"status": ls, "output": lo},
            "modern": {"status": ms, "output": mo}}
def _write(tmp_path, records) -> str:
    p = tmp_path / "probes.ndjson"
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records),
                 encoding="utf-8")
    return str(p)
def test_matched_full_semantics(tmp_path):
    """状态 + dict 输出逐字段一致 → MATCHED。"""
    p = _write(tmp_path, [_probe(lo={"amount": 5000, "status_text": "pending"},
                                 mo={"amount": 5000, "status_text": "pending"}),
                          _probe(lo="C-001", mo="C-001")])       # 标量输出
    r = reconcile_probes(p)
    assert r["verdict"] == "MATCHED" and r["total"] == 2 and r["diverged"] == 0
def test_divergence_field_and_status(tmp_path):
    """状态分歧 + 字段分歧逐条列出（含 modern 缺字段）。"""
    p = _write(tmp_path, [_probe(ls=0, lo={"amount": 5000, "status_text": "pending"},
                                 ms=1, mo={"amount": 5000}),
                          _probe(lo="A", mo="B")])
    r = reconcile_probes(p)
    assert r["verdict"] == "DIVERGED" and r["diverged"] == 2
    kinds = [d["kind"] for m in r["mismatches"] for d in m["diffs"]]
    assert kinds.count("status") == 1 and kinds.count("field") == 1
    assert kinds.count("output") == 1
def test_bad_lines_fail_closed(tmp_path):
    """坏 JSON / 缺契约键 → 整体 fail-closed 拒绝（零静默跳过）。"""
    p = tmp_path / "bad.ndjson"
    p.write_text('{"action":"A","legacy":{"status":0}}\n'      # 缺 modern
                 'not-json-at-all\n', encoding="utf-8")
    with pytest.raises(ValueError, match="PROBE-BAD-LINES") as e:
        reconcile_probes(str(p))
    assert "行 1" in str(e.value) and "行 2" in str(e.value)
def test_empty_and_missing_refused(tmp_path):
    p0 = tmp_path / "empty.ndjson"
    p0.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="PROBE-EMPTY"):
        reconcile_probes(str(p0))
    with pytest.raises(FileNotFoundError, match="PROBE-NOFILE"):
        reconcile_probes(str(tmp_path / "nope.ndjson"))
def test_readonly_canonical_untouched(tmp_path):
    """对账器只读：spec/ 字节零变化（报告是咨询产物）。"""
    def snap():
        return {str(p_.relative_to(ROOT)): len(p_.read_bytes())
                for p_ in sorted((ROOT / "spec").rglob("*")) if p_.is_file()}
    before = snap()
    r = reconcile_probes(_write(tmp_path, [_probe(lo="x", mo="x")]))
    assert r["verdict"] == "MATCHED" and snap() == before
