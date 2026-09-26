"""Replay real Claude Code Bash calls through the Jev airbag questions.

NOT run yet: it sends your own shell history to hosted Jev. Run it yourself:
  cd "Content Ideas 2026/jev-airbag" && ../rfp-copilot/.venv-jev/bin/python replay.py

Commands that contain a long token-looking run of characters are skipped so
nothing that looks like a key leaves the machine. Output: out/replay.json.
"""
import argparse
import asyncio
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from airbag import MODEL, load_env, questions, state_for, tier  # noqa: E402

CONCURRENCY = 8
LOOKS_SECRET = re.compile(r"[A-Za-z0-9_\-]{28,}")


def load(limit: int) -> list[dict]:
    rows = json.load(open(os.path.join(HERE, "data", "bash_calls.json")))
    kept = [r for r in rows if not LOOKS_SECRET.search(r["command"]) and len(r["command"]) < 1500]
    print(f"{len(rows)} commands, {len(kept)} after the secret-shaped filter", file=sys.stderr)
    return kept[:limit] if limit else kept


async def main(limit: int):
    from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

    rows = load(limit)
    load_env()
    qs = questions()
    sem = asyncio.Semaphore(CONCURRENCY)
    client = AsyncTypeSafeClient(model=MODEL, retry=RetryPolicy(max_retries=4, timeout=30.0))

    async def one(r: dict) -> dict:
        async with sem:
            state = state_for(r["command"], "/Users/dev/" + r["project"].split("-")[-1])
            t0 = time.perf_counter()
            resp = await client.system_one(state, qs)
            ms = (time.perf_counter() - t0) * 1000
        a = {k: round(v.noul, 3) for k, v in resp.answers.items()}
        t, why = tier(a)
        return {**r, **a, "tier": t, "why": why, "ms": round(ms),
                "tokens": resp.usage.input_tokens if resp.usage else None}

    t0 = time.perf_counter()
    try:
        out = await asyncio.gather(*(one(r) for r in rows))
    finally:
        await client.aclose()
    wall = time.perf_counter() - t0
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    json.dump(out, open(os.path.join(HERE, "out", "replay.json"), "w"), indent=0)
    tiers = {t: sum(1 for o in out if o["tier"] == t) for t in ("allow", "ask", "block")}
    toks = sum(o["tokens"] or 0 for o in out)
    print(f"{len(out)} calls in {wall:.0f}s; tiers {tiers}; {toks} input tokens "
          f"(~${toks / 1e6 * 0.042:.3f})")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=0)
    asyncio.run(main(p.parse_args().limit))
