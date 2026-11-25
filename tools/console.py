#!/usr/bin/env python3
"""tools/console.py —— WEB 治理控制台壳（"壳，不是核"）。
定位（入口层架构纪律的落点）：
- 壳不 import 内核：所有操作经 subprocess 调 src/cli/main.py —— 内核升级壳
  不变，壳崩溃不伤内核；同一组 CLI 命令是唯一交互面，WEB 与终端殊途同归；
- 命令白名单分级：只读咨询（review/profile/verify/impact/shadow/shadow-online/manual/
  spec fingerprint/spec digest）+ 参数化操作（import-db/import-data/extract/
  generate/draft/test）；高危写面（release / register / bootstrap）**不提供**，
  治理写子命令（spec version / spec register-declarations / draft promote）
  同样**不提供** —— 治理签署必须走终端显式执行；
- 白名单是「首词 + 子命令」二元组，不按首词分级：先前把 `spec` 整族放进
  只读级导致 `spec version` 可经无认证 HTTP 触发 GOV-3 写面，已收紧；
- 默认仅绑定 127.0.0.1（治理数据不出本机）；无任何持久化状态。
用法: python tools/console.py [--port 7800]
"""
from __future__ import annotations
import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "src" / "cli" / "main.py"
# 白名单（分级 + 二元组）：壳只放行这些「首词[ 子命令]」标签；不在表内 = 拒绝
READONLY = ["review", "profile", "verify", "impact", "shadow", "shadow-online",
            "manual", "spec fingerprint", "spec digest"]
MUTATING = ["import-db", "import-data", "extract", "generate", "draft", "test"]
ALLOWED = set(READONLY) | set(MUTATING)
# 子命令敏感族：只有列出的子命令拼入标签参与白名单匹配，其余一律按首词
# 处理（如 `draft <file>` 的首参是文件名，不是子命令）。
SUBCOMMAND_FIRST = {"spec"}          # 需要按子命令精确匹配的族
# 显式拒绝的子命令对：即使首词在 MUTATING 白名单内，治理写面也不经壳执行。
DENIED_PAIRS = {("spec", "version"), ("spec", "register-declarations"),
                ("draft", "promote")}
def _authorize(cmd: str, args: list[str]) -> tuple[bool, str]:
    """二元组授权：返回 (是否放行, 实际派发的 CLI 参数)。
    先查显式拒绝对，再按标签匹配白名单；选项形式（--x）不作为子命令。"""
    sub = args[0] if args and not args[0].startswith("-") else None
    pair = (cmd, sub)
    if pair in DENIED_PAIRS:
        return False, f"{cmd} {sub}".strip()
    if cmd in SUBCOMMAND_FIRST and sub:
        label = f"{cmd} {sub}"
    else:
        label = cmd
    return label in ALLOWED, label
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>AosKeel Console</title>
<style>body{font-family:monospace;background:#111;color:#ddd;max-width:900px;margin:2em auto}
h1{color:#7ec9ff}button,select,input{background:#222;color:#ddd;border:1px solid #555;padding:6px}
pre{background:#000;padding:1em;white-space:pre-wrap;border:1px solid #333}</style></head>
<body><h1>AosKeel 治理控制台（壳）</h1>
<p>壳只驱动同一组 CLI 命令（subprocess），不直接触碰内核；高危写面（release/register/bootstrap）不在此提供。</p>
<p><select id="cmd">%s</select> <input id="args" placeholder="--map map.yaml ..." size="50">
<button onclick="run()">执行</button></p><pre id="out">（输出区）</pre>
<script>
async function run(){
 const parts=document.getElementById('cmd').value.split(/\\s+/);
 const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},
   body:JSON.stringify({cmd:parts[0],
     args:parts.slice(1).concat(document.getElementById('args').value.split(/\\s+/).filter(Boolean))})});
 const j=await r.json();
 document.getElementById('out').textContent=(j.exit_code===0?'OK':'EXIT '+j.exit_code)+'\\n'+j.stdout;
}</script></body></html>"""
class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype="application/json; charset=utf-8"):
        raw = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)
    def do_GET(self):
        if not self._local_request():
            self._send(403, json.dumps({"error": "仅接受本机 Host"}))
            return
        opts = "".join(f'<option>{c}</option>' for c in sorted(ALLOWED))
        self._send(200, PAGE % opts, "text/html; charset=utf-8")
    def _local_request(self) -> bool:
        """本机约束：Host 须为回环地址；带 Origin 时亦须为回环来源。

        防 DNS rebinding（Host 伪造）与跨站触发（浏览器携带外部 Origin）——
        壳无认证层，来源校验是它唯一能自带的边界。
        """
        host = (self.headers.get("Host") or "").lower()
        if not (host.startswith("127.0.0.1") or host.startswith("localhost")
                or host.startswith("[::1]")):
            return False
        origin = (self.headers.get("Origin") or "").lower()
        return not origin or origin.startswith(("http://127.0.0.1", "http://localhost",
                                                "http://[::1]"))
    def do_POST(self):
        if self.path != "/api/run":
            self._send(404, json.dumps({"error": "no such endpoint"}))
            return
        if not self._local_request():
            self._send(403, json.dumps({"error": "仅接受本机回环来源"}))
            return
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":               # 拒绝 text/plain 等简单请求跨站触发
            self._send(415, json.dumps({"error": "Content-Type 须为 application/json"}))
            return
        try:
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except (json.JSONDecodeError, ValueError):
            self._send(400, json.dumps({"error": "bad json"}))
            return
        cmd = req.get("cmd")
        args = [str(a) for a in (req.get("args") or [])]
        if not isinstance(cmd, str):                # 非字符串命令提前 fail-closed
            self._send(403, json.dumps({"error": "cmd 须为字符串 —— 不在壳白名单"}))
            return
        allowed, label = _authorize(cmd, args)      # 首词+子命令二元组
        if not allowed:                             # 白名单外 fail-closed
            self._send(403, json.dumps({"error": f"命令 {label!r} 不在壳白名单 —— "
                                        "治理签署类命令与写子命令必须走终端显式执行"}))
            return
        proc = subprocess.run([sys.executable, str(CLI), cmd, *args],
                              capture_output=True, text=True, timeout=600,
                              cwd=str(ROOT))
        self._send(200, json.dumps({"exit_code": proc.returncode,
                                    "stdout": proc.stdout[-20000:],
                                    "stderr": proc.stderr[-4000:]}))
    def log_message(self, *a):                      # 静默访问日志
        pass
def serve(port: int = 7800):
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"CONSOLE-UP: http://127.0.0.1:{port}（壳 → subprocess → CLI；Ctrl-C 退出）")
    srv.serve_forever()
if __name__ == "__main__":
    port = 7800
    if "--port" in sys.argv:
        port = int(sys.argv[sys.argv.index("--port") + 1])
    serve(port)
