"""tests/conformance/test_codegen.py —— 声明 → 代码骨架生成器（KS-4.3 / GOV-2.2 / INV-1）。
判据：生成物带 provenance 头；手改即拒（禁止静默覆盖）；reducer 纯函数且
声明外字段漂移可见；handler 只封装 kernel.submit（同一条管线，无绕行）。
"""
import importlib.util
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools import codegen
from tools.codegen import CodegenDrift, generate
from kernel.registration import compile_all, RegistrationFailed
from kernel.store import EventStore
from kernel.session import SessionChannel
from kernel.pipeline import Kernel
PARAMS = {"contract_id": "C-1", "status": "pending", "amount": 500000}
@pytest.fixture(scope="module", autouse=True)
def _generate():
    generate()                     # 生成物随模块测试刷新（声明驱动，幂等）
def _load(filename):
    spec = importlib.util.spec_from_file_location(
        f"gen_{filename[:-3]}", ROOT / f"src/generated/{filename}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
def test_provenance_in_generated_code():
    """GOV-2.2 代码形态：生成物头部携带 spec_ref 与声明 provenance。"""
    src = (ROOT / "src/generated/actions.py").read_text(encoding="utf-8")
    assert "spec_ref: AOS-ART-" in src
    assert "provenance: SPEC-2026-014" in src          # ApproveContract/VoidContract 回溯
    assert "def approve_contract(" in src and "def void_contract(" in src
def test_generation_is_idempotent():
    src1 = (ROOT / "src/generated/reducers.py").read_text(encoding="utf-8")
    generate()
    src2 = (ROOT / "src/generated/reducers.py").read_text(encoding="utf-8")
    assert src1 == src2
def test_hand_edit_refused(tmp_path):
    """手改检测：生成物被人工修改后，再生成必拒（禁止静默覆盖人工代码）。"""
    p = ROOT / "src/generated/actions.py"
    original = p.read_text(encoding="utf-8")
    try:
        p.write_text(original + "\n# human hack\n", encoding="utf-8")
        with pytest.raises(CodegenDrift, match="禁止静默覆盖"):
            generate()
        generate(force=True)                           # --force 显式覆盖
        assert "human hack" not in p.read_text(encoding="utf-8")
    finally:
        p.write_text(original, encoding="utf-8")
def test_reducer_pure_and_drift_visible():
    """R11 纯函数 + KS-4.3 漂移可见：声明外字段进 _undeclared，不静默丢弃。"""
    mod = _load("reducers.py")
    from types import SimpleNamespace
    ev = SimpleNamespace(payload=dict(PARAMS, valid_time="2026-01-01",
                                      hacker_field="injected"))
    state1 = mod.reduce_contract({}, ev)
    state2 = mod.reduce_contract({}, ev)
    assert state1 == state2                            # 同输入同输出（纯）
    obj = state1["C-1"]
    assert obj["status"] == "pending" and obj["amount"] == 500000   # 声明内物化
    assert obj["_undeclared"] == {"hacker_field": "injected"}       # 声明外可见
    assert "valid_time" not in obj                     # 内核维护字段静默跳过
def test_handler_uses_same_pipeline():
    """INV-1 结构核对：生成 handler 无存储写路径；行为 = kernel.submit。"""
    src = (ROOT / "src/generated/actions.py").read_text(encoding="utf-8")
    for banned in ("store.commit", "_append", "write_raw", "session_append"):
        assert banned not in src                       # 骨架层无绕行（静态）
    mod = _load("actions.py")
    k = Kernel(EventStore(), SessionChannel(), compile_all())
    ev = mod.approve_contract(k, "contract_steward", contract_id="C-1",
                              status="pending", amount=500000)   # 快照字段经 **snapshot 透传
    assert ev.stream_id == "domain:ContractAggregate"  # 动态：走同一条管线
def test_uncompilable_declarations_block_generation(monkeypatch):
    """KS-7.1 前置：编译不过 → 拒绝生成（骨架不可先于声明成立）。"""
    def boom():
        raise RegistrationFailed("COMPILE-FAILED: x")
    monkeypatch.setattr(codegen, "compile_all", boom)
    with pytest.raises(RegistrationFailed):
        codegen.generate()
