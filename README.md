# Jev airbag

A Claude Code hook that asks [Jev](https://typesafe.ai) four questions about every shell command before it runs, and blocks the ones that would delete something that matters.

```
$ git push --force origin main
Jev airbag BLOCKED this command (remote + critical; destroys 0.77, remote 0.97, escapes 0.24, critical 0.95)
```

Claude Code in auto mode runs hundreds of shell commands a day. Most are `ls` and `git status`. A few are `rm -rf` in the wrong directory or a force push to main. A permission prompt on every command trains you to click yes without reading, so the airbag stays quiet on the safe ones and only speaks up when Jev thinks a command is dangerous.

## How it decides

One Jev call per command answers four questions at once, each as a probability from 0 to 1:

| question | asks whether the command |
|---|---|
| destroys | deletes or overwrites something hard to get back |
| remote | changes something off this machine (push, deploy, publish) |
| escapes | touches files outside the project directory |
| critical | targets main, shared history, production, home, or system files |

If two questions are strongly yes, the command is **blocked** and Claude is told why. If one is, Claude Code **asks you** first. Otherwise it runs normally. A single strong signal only asks because `rm -rf build/` really does destroy files; it just doesn't destroy anything you care about. The thresholds live in `airbag.py` and are tuned on 24 hand-labeled commands (`smoke_airbag.py`).

On that set all 8 dangerous commands are blocked, median latency is 107 ms, and each call costs about 520 input tokens, which is roughly two thousandths of a cent.

## Install

```bash
git clone https://github.com/velvetchief/jev-airbag ~/jev-airbag
cd ~/jev-airbag && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
mkdir -p ~/.config/jev-airbag && echo "TYPESAFE_API_KEY=your-key" > ~/.config/jev-airbag/.env
```

Then add this to `.claude/settings.json` in any project (or `~/.claude/settings.json` for all of them):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": "~/jev-airbag/.venv/bin/python ~/jev-airbag/hook.py", "timeout": 10 }
        ]
      }
    ]
  }
}
```

If Jev can't be reached the hook asks you rather than letting the command through. Set `AIRBAG_FAIL=open` to change that. Every decision is logged to `~/.jev-airbag/log.jsonl`.

## Try a command without Claude Code

```bash
.venv/bin/python airbag.py "rm -rf ~/Documents"
```

## Replay your own history

`extract_calls.py` pulls every Bash command Claude Code has run from your local transcripts. `replay.py` sends them through the airbag (commands that look like they contain a key are skipped), and `scoreboard.py` shows how many would have been allowed, asked, or blocked, the fifteen worst, and what the whole run cost. Your history stays in `data/` and `out/`, which are git-ignored.

```bash
.venv/bin/python extract_calls.py && .venv/bin/python replay.py && .venv/bin/python scoreboard.py
```

## Tests

`tests/test_policy.py` freezes real Jev scores from the smoke run so the tier rules can be changed without an API key. The first test is the promise: every command in the block set stays blocked.

## Known misses

`sed -i` on a source file and `kill -9` on a port are allowed when they should ask. Jev scores both low on every question, so fixing them means a better question, not a different threshold.

Built at Jevathon, 2026-09-26. The questions, policy, hook, scoreboard, and tests were written during the event; the transcript extractor and first smoke test were written the night before.
