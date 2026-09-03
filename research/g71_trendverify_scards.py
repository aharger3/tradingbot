"""ADVERSARIAL VERIFY: the 34 held-out S cards, hourly vs daily htf_bias.

Calls the REAL research/t4_engine_recall.htf_bias and the REAL
backtest_week.htf_bias_for (fed backtest_2y's own hourly construction).
No engine replay -- this only re-derives the definition drift.
"""
from __future__ import annotations
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import polygon_feed as pf                                # noqa: E402
from backtest_week import htf_bias_for                   # noqa: E402
from backtest_12mo import hourly_from_1m                 # noqa: E402
import t4_engine_recall as t4                            # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")


def archive_days(sym):
    d = os.path.join(ARCHIVE, sym)
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv")) if os.path.isdir(d) else []


def hourly_bias(sym, day, back=12):
    hourly = []
    for d in [x for x in archive_days(sym) if x < day][-back:]:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if bars:
            hourly += hourly_from_1m(d, bars)
    return htf_bias_for(hourly, day)


S, refused = set(), set()
for line in open(SWEEP, encoding="utf-8"):
    line = line.strip()
    if not line:
        continue
    r = json.loads(line)
    sym, _, day = r["card_id"].partition("_")
    g = (r.get("answers") or {}).get("s") or []
    g = g[0].strip().lower() if g else ""
    (S if g == "s" else refused).add((sym.upper(), day[:10]))

print("sweep: %d S cards, %d refused" % (len(S), len(refused)))
drift = Counter()
for sym, day in sorted(S):
    h, d = hourly_bias(sym, day), t4.htf_bias(sym, day)
    drift["%s|%s" % (h, d)] += 1
    print("  %-6s %s  hourly=%-8s daily=%-8s %s" % (sym, day, h, d, "" if h == d else "<< DIFFER"))
same = sum(v for k, v in drift.items() if k.split("|")[0] == k.split("|")[1])
inv = drift["bullish|bearish"] + drift["bearish|bullish"]
print("\nagree %d/%d = %.1f%%   outright inverted %d  (bull|bear %d, bear|bull %d)"
      % (same, len(S), same / len(S) * 100, inv,
         drift["bullish|bearish"], drift["bearish|bullish"]))
print("drift:", dict(sorted(drift.items(), key=lambda kv: -kv[1])))
