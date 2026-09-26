"""Vercel function behind the public live page: POST {"command": ...} returns
the same JSON as live.py. Commands are scored by Jev, never executed. Each IP
gets LIMIT checks a day per warm instance so a public link can't drain the key."""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler

# The hook sees a plausible developer machine rather than the Lambda sandbox.
os.environ["HOME"] = "/home/dev"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from live import run_hook  # noqa: E402

CWD = "/home/dev/projects/jev-airbag-demo"
LIMIT = 30
seen: dict[str, list[float]] = {}


def allowed(ip: str) -> bool:
    now = time.time()
    hits = [t for t in seen.get(ip, []) if now - t < 86400]
    seen[ip] = hits + [now]
    return len(hits) < LIMIT


class handler(BaseHTTPRequestHandler):
    def send(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        ip = (self.headers.get("x-forwarded-for") or "?").split(",")[0].strip()
        if not allowed(ip):
            return self.send(429, {"error": f"{LIMIT} checks a day per visitor. Clone the repo to run more."})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except ValueError:
            return self.send(400, {"error": "bad json"})
        command = (body.get("command") or "").strip()[:500]
        if not command:
            return self.send(400, {"error": "empty"})
        self.send(200, run_hook(command, CWD))
