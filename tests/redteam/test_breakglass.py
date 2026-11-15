"""tests/redteam/test_breakglass.py —— VER-29 备料。
破窗演练（限时生效 + 自动过期 + 双记录 + 事后评审 Process 强制创建）是
运行系统上的人工执行项——本文件只做模板层可机械核对的备料断言，
演练本体按 bootstrap/checklists/VER-28/29.yaml 留档执行（诚实边界）。
"""
import sys
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
def test_breakglass_capability_declared():
    """破窗是声明过的基座能力（breakglass_resonant）—— 演练有可对账的声明。"""
    from kernel.registration import load_caps
    assert "breakglass_resent" not in load_caps()["foundation"]  # 拼写哨兵：防错别字漂移
    assert "breakglass_resonant" in load_caps()["foundation"]
def test_breakglass_runtime_drill_is_manual():
    """演练不在 CI 兑现（P-15 审计纪律 + GOV-1）：本套件不模拟治理。"""
    assert True   # 占位断言；真实判据见 bootstrap/checklists/VER-28.yaml item1-4
                  # 与 RUNBOOK #mandatory-records（双签：steward + 平台 owner）
