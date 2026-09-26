"""Live demo page: type a shell command, it goes through the real hook.py exactly
as Claude Code would send it, and the page shows Jev's four scores and the
decision. Commands are scored, never executed. Binds to 127.0.0.1 only.

  python live.py            then open http://127.0.0.1:8765
"""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from airbag import HERE, QUESTIONS
from hook import decide

PORT = int(os.environ.get("PORT", "8765"))
DEMO_CWD = os.path.join(os.path.dirname(HERE), "jev-airbag-demo")


def run_hook(command: str, cwd: str = DEMO_CWD) -> dict:
    """Send one command through hook.decide() as a Claude Code PreToolUse event."""
    event = {"tool_name": "Bash", "tool_input": {"command": command},
             "cwd": cwd, "session_id": "live-demo", "hook_event_name": "PreToolUse"}
    code, out, err, r = decide(event)
    r = r or {}
    tier = "block" if code == 2 else "ask" if '"ask"' in out else "allow"
    return {"command": command, "tier": tier, "exit": code, "stdout": out, "stderr": err,
            **{k: r.get(k) for k in (*QUESTIONS, "ms", "tokens", "why")}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self.send(200, open(os.path.join(HERE, "live.html")).read(), "text/html; charset=utf-8")
        self.send(404, "not found", "text/plain")

    def do_POST(self):
        if self.path != "/run":
            return self.send(404, "not found", "text/plain")
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        command = (body.get("command") or "").strip()[:500]
        if not command:
            return self.send(400, '{"error":"empty"}', "application/json")
        self.send(200, json.dumps(run_hook(command)), "application/json")


if __name__ == "__main__":
    print(f"JevBag live demo on http://127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
