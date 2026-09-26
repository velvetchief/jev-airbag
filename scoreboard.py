"""Scoreboard from out/replay.json: tier counts, the 15 scariest commands,
latency and token cost. Prints to the terminal and writes out/scoreboard.html.

  python scoreboard.py [path/to/replay.json]
"""
import html
import json
import os
import sys

from airbag import HERE, QUESTIONS, tier

PRICE_PER_M = 0.042  # USD per million input tokens, jev-1.13.0


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))] if xs else 0


def load(path):
    rows = json.load(open(path))
    for r in rows:
        r["tier"], r["why"] = tier(r)  # always re-derive with the current policy
        r["heat"] = max(r.get(k, 0) for k in QUESTIONS)
    return rows


def summarize(rows):
    order = {"block": 2, "ask": 1, "allow": 0}
    worst = sorted(rows, key=lambda r: (order[r["tier"]], r["heat"]), reverse=True)[:15]
    ms = [r["ms"] for r in rows]
    toks = sum(r.get("tokens") or 0 for r in rows)
    return {
        "n": len(rows),
        "tiers": {t: sum(r["tier"] == t for r in rows) for t in ("allow", "ask", "block")},
        "p50": pct(ms, 0.5), "p95": pct(ms, 0.95),
        "tokens": toks, "tokens_per_call": round(toks / max(1, len(rows))),
        "cost": toks / 1e6 * PRICE_PER_M,
        "worst": worst,
    }


def terminal(s):
    t = s["tiers"]
    print(f"{s['n']} real Claude Code commands replayed through Jev")
    print(f"  allow {t['allow']}   ask {t['ask']}   block {t['block']}")
    print(f"  latency p50 {s['p50']}ms  p95 {s['p95']}ms")
    print(f"  {s['tokens_per_call']} input tokens per call, ${s['cost']:.4f} for the whole replay\n")
    for r in s["worst"]:
        print(f"  {r['tier']:5s} {r['why']:30s} {r['command'][:90]}")


CSS = """
:root{--bg:#161616;--layer:#262626;--line:#393939;--text:#f4f4f4;--muted:#c6c6c6;
--allow:#42be65;--ask:#f1c21b;--block:#fa4d56}
@media (prefers-color-scheme: light){:root:not([data-theme="dark"]){--bg:#fff;--layer:#f4f4f4;
--line:#e0e0e0;--text:#161616;--muted:#525252;--allow:#198038;--ask:#8e6a00;--block:#da1e28}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:16px/1.5 'IBM Plex Sans',system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:48px 16px}
h1{font-weight:300;font-size:clamp(28px,5vw,48px);line-height:1.15;margin:0 0 8px}
.sub{color:var(--muted);margin:0 0 40px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:1px;
background:var(--line);border:1px solid var(--line);margin-bottom:40px}
.tile{background:var(--layer);padding:20px}
.tile b{display:block;font-weight:300;font-size:40px;font-family:'IBM Plex Mono',monospace}
.tile span{color:var(--muted);font-size:14px}
.allow b{color:var(--allow)}.ask b{color:var(--ask)}.block b{color:var(--block)}
h2{font-weight:400;font-size:20px;margin:0 0 12px}
.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:400}
td.c{font-family:'IBM Plex Mono',monospace;word-break:break-all;min-width:280px}
td.n{font-family:'IBM Plex Mono',monospace;text-align:right}
.tag{font-family:'IBM Plex Mono',monospace;font-size:12px;padding:2px 8px;border:1px solid}
.tag.block{color:var(--block)}.tag.ask{color:var(--ask)}.tag.allow{color:var(--allow)}
"""


def page(s):
    t = s["tiers"]
    rows = "".join(
        f"<tr><td><span class='tag {r['tier']}'>{r['tier']}</span></td>"
        f"<td class='c'>{html.escape(r['command'][:220])}</td>"
        + "".join(f"<td class='n'>{r.get(k, 0):.2f}</td>" for k in QUESTIONS) + "</tr>"
        for r in s["worst"])
    heads = "".join(f"<th>{k}</th>" for k in QUESTIONS)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Jev Airbag Scoreboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans:wght@300;400&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><main>
<h1>Jev read {s['n']:,} commands Claude Code actually ran on my machine.</h1>
<p class="sub">Each command got four yes-or-no questions in one call. Two strong yeses block it; one asks me first.</p>
<div class="tiles">
<div class="tile allow"><b>{t['allow']:,}</b><span>allowed</span></div>
<div class="tile ask"><b>{t['ask']:,}</b><span>asked me first</span></div>
<div class="tile block"><b>{t['block']:,}</b><span>blocked</span></div>
<div class="tile"><b>{s['p50']}ms</b><span>median per command, p95 {s['p95']}ms</span></div>
<div class="tile"><b>${s['cost']:.3f}</b><span>for all {s['n']:,}, {s['tokens_per_call']} tokens each</span></div>
</div>
<h2>The 15 it liked least</h2>
<div class="scroll"><table><tr><th>tier</th><th>command</th>{heads}</tr>{rows}</table></div>
</main></body></html>"""


def main(argv):
    path = argv[0] if argv else os.path.join(HERE, "out", "replay.json")
    s = summarize(load(path))
    terminal(s)
    out = os.path.join(HERE, "out", "scoreboard.html")
    open(out, "w").write(page(s))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
