"""tests/conformance/test_console.py —— WEB 治理控制台壳。
判据：壳不 import 内核（subprocess 驱动 CLI）；命令白名单 fail-closed（壳
白名单外的命令 403，治理签署类 release/register/bootstrap 不在白名单）；
只读咨询命令经壳真实可达（exit 0）；UI 页含全部白名单命令与壳定位声明。
"""
import json
import sys
import threading
import urllib.request
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "src"))
from tools.console import Handler, ALLOWED, READONLY, MUTATING
from tools.console import serve as _serve
@pytest.fixture()
def server():
    srv = __import__("http.server", fromlist=["ThreadingHTTPServer"]). \
        ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
def _post(url: str, payload: dict) -> tuple[int, dict]:
    req = urllib.request.Request(url + "/api/run",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
def test_shell_not_kernel_subprocess_only():
    """壳纪律：console.py 不 import 任何 kernel 模块（只 subprocess 调 CLI）。"""
    src = (ROOT / "tools" / "console.py").read_text(encoding="utf-8")
    assert "from kernel" not in src and "import kernel" not in src
    assert "subprocess.run" in src
def test_readonly_command_via_shell(server):
    """只读咨询命令经壳真实可达（subprocess → CLI → exit 0）。"""
    code, body = _post(server, {"cmd": "verify", "args": []})
    assert code == 200 and body["exit_code"] == 0
    assert "VERIFY-OK" in body["stdout"]
def test_whitelist_fail_closed(server):
    """白名单外命令 → 403（fail-closed）；治理签署类不在白名单。"""
    code, body = _post(server, {"cmd": "release", "args": []})
    assert code == 403 and "白名单" in body["error"]
    code, _ = _post(server, {"cmd": "register", "args": []})
    assert code == 403
    code, _ = _post(server, {"cmd": "bootstrap", "args": []})
    assert code == 403
    code, _ = _post(server, {"cmd": "__import__('os').system('x')", "args": []})
    assert code == 403
def test_ui_page_declares_scope():
    """UI 页含全部白名单命令 + 壳定位声明（不冒充内核）。"""
    from tools.console import PAGE
    page = PAGE % "".join(f"<option>{c}</option>" for c in sorted(ALLOWED))
    for c in sorted(ALLOWED):
        assert c in page
    assert "壳" in page and "subprocess" in page
def test_whitelist_split_is_honest():
    """白名单分级诚实：只读与可变更明确分组，无遗漏的写面混入只读级。"""
    assert {"release", "register", "bootstrap"}.isdisjoint(ALLOWED)
    assert set(READONLY) | set(MUTATING) == ALLOWED
