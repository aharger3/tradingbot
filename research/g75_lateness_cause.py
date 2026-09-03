"""g75_lateness_cause.py -- the causal test, immune to the counting confound.

The book comparison in g75_lateness_book.py has one honest weakness: the
break-and-retest arm emits 19x more signals than the one-candle rule, so its
FIRST signal of the day could be earlier purely because it takes more draws.

This script does not count signals at all. It measures WHEN THE LEVEL EXISTS:

  break-and-retest  -> the level is PDH/PDL/PMH/PML (drawn before the bell) or
                       the opening range (fixed at 9:35). Bar 0 / bar 5.
  one-candle rule   -> the level is an order block, and an order block cannot
                       exist until MarketStructure has a CONFIRMED break
                       (last_hh / last_ll). That bar is a hard floor on the
                       earliest the detector could possibly fire, no matter how
                       many signals it emits.

It also counts how many times the order block is REPLACED during a session,
because get_valid_order_blocks only ever keeps the block belonging to the most
recent structure break -- the older one is not remembered.

Sampled over symbol-days drawn from the book. Read-only.
Writes research/g75_lateness_cause.json.
"""
from __future__ import annotations
import json, os, random, statistics as st, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as T4
from omen_bot import MarketStructure, detect_order_block_setup
from signal_runner import OB_RETEST_TYPES

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g75_lateness_cause.json")
N = int(os.environ.get("G75_SAMPLE", "300"))
RNG = random.Random(7502)

rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
days = sorted({(r["sym"], r["day"]) for r in rows})
RNG.shuffle(days)
days = days[:N]
print("sampling %d symbol-days out of %d in the book" % (len(days), len(set(
    (r["sym"], r["day"]) for r in rows))))


def clock(off):
    return "%d:%02d" % (9 + (30 + off) // 60, (30 + off) % 60)


first_struct, first_block, first_entryable, nblocks = [], [], [], []
never_struct = never_block = 0
for k, (sym, day) in enumerate(days):
    candles = T4.rth_candles(sym, day)
    if not candles or len(candles) < 40:
        continue
    end = min(len(candles) - 1, 90)          # 09:30-11:00 only
    fs = fb = fe = None
    seen_blocks = set()
    for i in range(3, end + 1):
        w = candles[: i + 1]
        for d in ("bullish", "bearish"):
            stm = MarketStructure()
            stm.update(w)
            if (stm.last_hh if d == "bullish" else stm.last_ll) is not None and fs is None:
                fs = i
            _ob = {}
            block, retest, _ = detect_order_block_setup(w, d, out=_ob)
            if block is not None:
                if fb is None:
                    fb = i
                seen_blocks.add((d, round(block.low, 4), round(block.high, 4)))
                if retest in OB_RETEST_TYPES and fe is None:
                    beyond = (w[-1].close > block.high) if d == "bullish" \
                        else (w[-1].close < block.low)
                    if beyond:
                        fe = i
        if fe is not None and fs is not None and fb is not None:
            pass
    if fs is None:
        never_struct += 1
    else:
        first_struct.append(fs)
    if fb is None:
        never_block += 1
    else:
        first_block.append(fb)
    if fe is not None:
        first_entryable.append(fe)
    nblocks.append(len(seen_blocks))
    if (k + 1) % 50 == 0:
        print("  ... %d/%d" % (k + 1, len(days)), flush=True)

J = {
    "n_days": len(days),
    "first_structure_break_med": st.median(first_struct) if first_struct else None,
    "first_valid_block_med": st.median(first_block) if first_block else None,
    "first_entryable_block_med": st.median(first_entryable) if first_entryable else None,
    "distinct_blocks_med": st.median(nblocks) if nblocks else None,
    "distinct_blocks_mean": round(st.fmean(nblocks), 2) if nblocks else None,
    "days_with_no_structure_break": never_struct,
    "days_with_no_valid_block": never_block,
}
print()
print("=" * 90)
print("WHEN CAN EACH SETUP'S LEVEL EXIST AT ALL? (%d sampled symbol-days)" % len(days))
print("=" * 90)
print("  break-and-retest, his four levels (PDH/PDL/PMH/PML)   available at 9:30 "
      "-- 0 min in, every day")
print("  break-and-retest, the opening range                   available at 9:35 "
      "-- 5 min in, every day")
print("  one-candle rule, structure break confirmed            median %s (%.0f min in)"
      % (clock(J["first_structure_break_med"]), J["first_structure_break_med"]))
print("  one-candle rule, a VALID order block exists           median %s (%.0f min in)"
      % (clock(J["first_valid_block_med"]), J["first_valid_block_med"]))
print("  one-candle rule, block exists AND is being retested   median %s (%.0f min in)"
      % (clock(J["first_entryable_block_med"]), J["first_entryable_block_med"]))
print()
print("  distinct order blocks the engine holds during one session: median %.0f, mean %.2f"
      % (J["distinct_blocks_med"], J["distinct_blocks_mean"]))
print("  -- each new one REPLACES the last: get_valid_order_blocks reads only")
print("     MarketStructure.last_hh / last_ll, so the earlier block is forgotten.")
print("  days where no order block was ever valid before 11:00: %d of %d"
      % (never_block, len(days)))

json.dump(J, open(OUT, "w"), indent=1)
print()
print("wrote", OUT)
