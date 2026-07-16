#!/usr/bin/env python3
"""Summarize the CLAUDE.md orientation A/B (see PROTOCOL.md). Reads results/*.json."""
import json, glob, os, statistics

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
rows = {}
for f in sorted(glob.glob(os.path.join(OUT, "*.json"))):
    name = os.path.basename(f)[:-5]          # e.g. graph-guard-A
    repo, arm = name.rsplit("-", 1)
    with open(f) as fh:
        d = json.load(fh)
    if isinstance(d, list):                   # CLI 2.1.x emits a message list; telemetry is the 'result' item
        d = next((m for m in reversed(d) if m.get("type") == "result"), {})
    u = d.get("usage", {})
    tokens = (u.get("input_tokens", 0) + u.get("output_tokens", 0)
              + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0))
    rows.setdefault(repo, {})[arm] = {
        "turns": d.get("num_turns"),
        "tokens": tokens,
        "cost": d.get("total_cost_usd"),
        "ms": d.get("duration_ms"),
        "answer": (d.get("result") or "")[:2000],
    }

hdr = f"{'repo':<24} {'A turns':>7} {'B turns':>7} {'A tokens':>9} {'B tokens':>9} {'A $':>7} {'B $':>7}"
print(hdr); print("-" * len(hdr))
at, bt, atok, btok = [], [], [], []
for repo, arms in sorted(rows.items()):
    a, b = arms.get("A"), arms.get("B")
    if not (a and b):
        print(f"{repo:<24} INCOMPLETE"); continue
    at.append(a["turns"]); bt.append(b["turns"])
    atok.append(a["tokens"]); btok.append(b["tokens"])
    print(f"{repo:<24} {a['turns']:>7} {b['turns']:>7} {a['tokens']:>9,} {b['tokens']:>9,} "
          f"{a['cost']:>7.4f} {b['cost']:>7.4f}")
if at:
    print("-" * len(hdr))
    mt_a, mt_b = statistics.median(at), statistics.median(bt)
    mk_a, mk_b = statistics.median(atok), statistics.median(btok)
    print(f"{'MEDIAN':<24} {mt_a:>7g} {mt_b:>7g} {mk_a:>9,.0f} {mk_b:>9,.0f}")
    verdict = "MAPPED WINS" if (mt_a < mt_b and mk_a < mk_b) else \
              "MAPPED LOSES" if (mt_a > mt_b and mk_a > mk_b) else "MIXED"
    print(f"\nPre-registered decision rule verdict: {verdict}")
    print("(answers saved in results/*.json for the manual correctness spot-check)")
