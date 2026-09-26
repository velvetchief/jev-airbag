"""Claude Code PreToolUse hook: ask Jev about every Bash call before it runs.

allow -> exit 0, normal permission rules apply
ask   -> JSON permissionDecision "ask", so you confirm it yourself
block -> exit 2, the reason goes back to Claude and the command never runs

If Jev is unreachable the hook asks (AIRBAG_FAIL=open lets it through instead).
Every decision is appended to ~/.jev-airbag/log.jsonl.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from airbag import QUESTIONS, check  # noqa: E402

LOG = os.path.expanduser("~/.jev-airbag/log.jsonl")


def log(row: dict):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write(json.dumps({"ts": time.time(), **row}) + "\n")
    except OSError:
        pass


def ask(reason: str) -> str:
    return json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "ask",
        "permissionDecisionReason": reason,
    }})


def decide(event: dict) -> tuple[int, str, str, dict | None]:
    """Return (exit code, stdout, stderr, Jev result) for one PreToolUse event."""
    if event.get("tool_name") != "Bash":
        return 0, "", "", None
    command = (event.get("tool_input") or {}).get("command", "")
    if not command.strip():
        return 0, "", "", None
    try:
        r = check(command, cwd=event.get("cwd"))
    except Exception as e:  # network, auth, timeout
        log({"command": command, "tier": "error", "error": repr(e)[:200]})
        if os.environ.get("AIRBAG_FAIL") == "open":
            return 0, "", "", None
        return 0, ask(f"Jev airbag could not reach Jev ({type(e).__name__}); confirm this one yourself."), "", None
    log({**r, "session": event.get("session_id"), "cwd": event.get("cwd")})
    scores = ", ".join(f"{k} {r[k]:.2f}" for k in QUESTIONS)
    if r["tier"] == "block":
        return 2, "", (f"Jev airbag BLOCKED this command ({r['why']}; {scores}). "
                       "Do not retry it or a variant of it. Explain to the user what you wanted "
                       "to do and let them run it themselves if they really want it."), r
    if r["tier"] == "ask":
        return 0, ask(f"Jev airbag: {r['why']} ({scores})"), "", r
    return 0, "", "", r


def main():
    code, out, err, _ = decide(json.load(sys.stdin))
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
