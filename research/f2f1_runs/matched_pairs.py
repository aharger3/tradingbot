"""Matched-pairs stop A/B: same (symbol, day, entry-time, direction) trades in
both runs — isolates the stop-placement effect from the population shift
(wider stops un-D-gate extra signals and inflate S; this controls for that).

Usage: py -3.13 matched_pairs.py baseline.json variant.json
"""
import json
import sys


def load(path):
    recs = [r for r in json.load(open(path)) if not r["alert_only"]]
    return {(r["symbol"], r["day"], r["candles"][r["entry_i"]]["t"], r["direction"]): r
            for r in recs if r["setup"] == "break_and_retest"}


a = load(sys.argv[1])
b = load(sys.argv[2])
keys = sorted(set(a) & set(b))
print(f"matched B&R entries: {len(keys)}  (baseline {len(a)}, variant {len(b)})")
for name, side in (("baseline", a), ("variant ", b)):
    grp = [side[k] for k in keys]
    w = sum(1 for r in grp if r["outcome"] == "win")
    l = sum(1 for r in grp if r["outcome"] == "loss")
    pnl = sum(r["pnl"] for r in grp)
    print(f"  {name}: {w}W {l}L {len(grp)-w-l}scr  {w/(w+l)*100:.1f}%W  ${pnl:,.0f}")
flips = [(k, a[k]["outcome"], b[k]["outcome"]) for k in keys
         if a[k]["outcome"] != b[k]["outcome"]]
saved = sum(1 for _, ao, bo in flips if ao == "loss" and bo in ("win", "scratch"))
hurt = sum(1 for _, ao, bo in flips if ao == "win" and bo in ("loss", "scratch"))
print(f"  outcome flips: {len(flips)}  (loss->saved {saved}, win->hurt {hurt})")
