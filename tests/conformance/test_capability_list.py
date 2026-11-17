"""tests/conformance/test_capability_list.py —— VER-27 自动化支撑壳（复盘布线）。
VER-27 的核对本体是 tools/verify_capability_list.py（退出码工具：0=完备，
1=差异清单）。本壳把它纳入 pytest 布线：能力清单完备性每次发布闸门必跑。
人工 checklist（bootstrap/checklists/VER-27.yaml）仍然有效 —— 壳只自动化
机器可判部分，不替代人签（kind: mandatory 语义不变）。
执行约束：负向用例临时篡改 docs/ARTIFACT-REGISTRY.md（测后恢复）——与
VER-30 等读登记表的测试互斥，须单进程 pytest（pyproject 现状即单进程；
未来若引入 xdist 须加互斥锁，不得并行跑本文件）。
"""
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/verify_capability_list.py"
def test_capability_list_completeness():
    """工具退出码 0 = 能力清单完备（INV-6/INV-11/KS-8.2/GOV-2.2/P-10）。"""
    r = subprocess.run([sys.executable, str(TOOL)], capture_output=True,
                       text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, f"VER-27 能力清单差异:\n{r.stdout}{r.stderr}"
    assert "CAPABILITY-LIST-ISSUES" not in r.stdout
def test_capability_tool_fail_closed_on_drift(tmp_path):
    """负向：登记表最新条目被篡改（spec_ref 失配）→ 工具必须报差异退出 1。"""
    import shutil
    registry = ROOT / "docs/ARTIFACT-REGISTRY.md"
    backup = tmp_path / "ARTIFACT-REGISTRY.md.bak"
    shutil.copy2(registry, backup)
    try:
        text = registry.read_text(encoding="utf-8")
        drifted = text.replace("| AOS-ART-001 |", "| AOS-ART-999 |", 1)
        assert drifted != text, "登记表格式与预期不符（测试失效）"
        registry.write_text(drifted, encoding="utf-8")
        r = subprocess.run([sys.executable, str(TOOL)], capture_output=True,
                           text=True, cwd=ROOT, timeout=120)
        assert r.returncode == 1
        assert "CAPABILITY-LIST-ISSUES" in r.stdout
        assert "GOV-2.2" in r.stdout
    finally:
        shutil.copy2(backup, registry)                    # 恢复正典（测试零污染）
