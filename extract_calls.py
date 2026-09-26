"""Pull every unique Bash tool call out of local Claude Code transcripts.

Output: data/bash_calls.json, one row per unique command with
project, timestamp, command, and the description Claude gave it.
"""
import collections
import glob
import hashlib
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
seen = set()
for path in glob.glob(os.path.expanduser("~/.claude/projects/*/*.jsonl")):
    proj = os.path.basename(os.path.dirname(path))
    with open(path, errors="ignore") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") or {}
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not (isinstance(block, dict) and block.get("type") == "tool_use"):
                    continue
                if block.get("name") != "Bash":
                    continue
                inp = block.get("input") or {}
                cmd = (inp.get("command") or "").strip()
                if not cmd:
                    continue
                key = hashlib.md5(cmd.encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({
                    "project": proj,
                    "ts": d.get("timestamp"),
                    "command": cmd,
                    "description": inp.get("description", ""),
                })

print("unique bash calls:", len(rows))
os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
with open(os.path.join(HERE, "data", "bash_calls.json"), "w") as fh:
    json.dump(rows, fh, indent=0)

by_project = collections.Counter(r["project"] for r in rows)
print(by_project.most_common(8))

buckets = {
    "rm": r"\brm\b",
    "git push": r"git push",
    "force flag": r"--force|\s-f\b",
    "sudo": r"\bsudo\b",
    "curl": r"\bcurl\b",
    "vercel": r"\bvercel\b",
    "git reset/checkout/clean": r"git (reset|checkout --|clean)",
    "kill": r"\bkill\b|pkill",
    "chmod/chown": r"chmod|chown",
    "mv": r"\bmv\b",
}
for name, pat in buckets.items():
    print(f"{name:28s}", sum(1 for r in rows if re.search(pat, r["command"])))
