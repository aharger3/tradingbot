"""g75_lateness_gatecensus.py -- WHICH gate does the killing, and does it kill
harder in the first half hour than the second?

Walks the shipped one-candle-rule chain bar by bar over a sample of symbol-days
and records the FIRST condition that is false on every bar, split 9:30-10:00 vs
10:00-11:00. If lateness is mechanical, one gate should be much more fatal
early than late.

Read-only. Writes research/g75_lateness_gatecensus.json.
"""
from __future__ import annotations
import json, os, random, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as T4
from g75_lateness_cases import ocr_trace

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g75_lateness_gatecensus.json")
N = int(os.environ.get("G75_SAMPLE", "120"))
RNG = random.Random(7503)

rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
days = sorted({(r["sym"], r["day"]) for r in rows})
RNG.shuffle(days)
days = days[:N]

PLAIN = {
    "no_structure_break": "no confirmed swing break yet -- there is no block to find",
    "block_broken_or_absent": "the block is gone: price closed back through it",
    "not_isolated": "the block candle is not isolated -- it overlaps its neighbours",
    "no_displacement": "the move off the block was not forceful enough",
    "not_at_block": "price is nowhere near the block",
    "retest_too_deep": "price came back INTO the block, not just wicked it",
    "close_not_beyond": "the bar did not close back out of the block",
    "volume": "volume too thin",
    "PASS": "PASS -- an entry",
}
early, late = Counter(), Counter()
for k, (sym, day) in enumerate(days):
    candles = T4.rth_candles(sym, day)
    if not candles or len(candles) < 40:
        continue
    end = min(len(candles) - 1, 90)
    for i in range(5, end + 1):
        for d in ("bullish", "bearish"):
            s = ocr_trace(candles, i, d)["stage"]
            (early if i < 30 else late)[s] += 1
    if (k + 1) % 40 == 0:
        print("  ... %d/%d" % (k + 1, len(days)), flush=True)

te, tl = sum(early.values()), sum(late.values())
print()
print("=" * 96)
print("WHERE THE ONE-CANDLE-RULE CHAIN DIES, BAR BY BAR (%d symbol-days, both directions)" % N)
print("=" * 96)
print("  %-58s %11s %11s" % ("first condition that was false", "9:30-10:00", "10:00-11:00"))
for s in ["no_structure_break", "block_broken_or_absent", "not_isolated",
          "no_displacement", "not_at_block", "retest_too_deep",
          "close_not_beyond", "volume", "PASS"]:
    if not early[s] and not late[s]:
        continue
    print("  %-58s %10.1f%% %10.1f%%"
          % (PLAIN[s], 100.0 * early[s] / te, 100.0 * late[s] / tl))
print("  %-58s %10d  %10d" % ("(bars examined)", te, tl))
json.dump({"early": dict(early), "late": dict(late), "n_days": N},
          open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
