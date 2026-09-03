"""G71/rule84ocr: the UPSTREAM one-candle-rule funnel.

T2 (research/t2_ocr-detector.md) measured the five clauses of Austin's sentence
AFTER `detect_order_block_setup` had already returned a block. This measures the
gates INSIDE that function -- the ones that decide whether an OCR candidate is
even seen. Two of them are not in any sentence Austin has said:

  _is_isolated       omen_bot.py:388  price-overlap isolation vs the prior 4 bars
  _has_displacement  omen_bot.py:425  hard veto; the rulebook lists no-displacement
                                      as a DOWNGRADE with a BR+OCR EXEMPTION

Read-only: reads cached bars via polygon_feed, writes nothing but stdout.
Usage: python research/g71_rule84ocr_funnel.py [n_days] [n_syms]
"""
import sys, os
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

import polygon_feed as pf
from omen_bot import (MarketStructure, _is_isolated, _has_displacement,
                      check_retest_type, detect_order_block_setup)
from signal_runner import OB_RETEST_TYPES, SESSION_START, SESSION_END, bar_time

NDAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
NSYMS = int(sys.argv[2]) if len(sys.argv) > 2 else 8

CACHE = Path("data/cache")
syms = sorted(p.name for p in CACHE.iterdir() if (p / "1min").is_dir())[:NSYMS]
days = sorted({p.stem for s in syms for p in (CACHE / s / "1min").glob("*.csv")})
days = days[-NDAYS:]

stage = Counter()
for sym in syms:
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(bars) < 30:
            continue
        for i in range(20, len(bars)):
            t = bar_time(bars[i].timestamp)
            if not (SESSION_START <= t < SESSION_END):
                continue
            window = bars[:i + 1]
            for direction in ("bullish", "bearish"):
                stage["0 candidate bars"] += 1
                s = MarketStructure(); s.update(window)
                blocks = s.get_valid_order_blocks(window, direction)
                if not blocks:
                    stage["1 no valid order block"] += 1
                    continue
                stage["2 block exists"] += 1
                block = blocks[0]
                brk = (s.last_hh if direction == "bullish" else s.last_ll)[2]
                try:
                    bidx = next(j for j in range(brk - 1, -1, -1)
                                if (window[j].is_bearish if direction == "bullish"
                                    else window[j].is_bullish))
                except StopIteration:
                    stage["2b no counter-coloured bar"] += 1
                    continue
                if not _is_isolated(window, bidx):
                    stage["3 KILLED by _is_isolated"] += 1
                    continue
                stage["3 passed isolation"] += 1
                if not _has_displacement(window, bidx, brk, direction):
                    stage["4 KILLED by _has_displacement"] += 1
                    continue
                stage["4 passed displacement"] += 1
                rt = check_retest_type(block, window[-1], direction)
                if rt == "not_retesting":
                    stage["5 not retesting"] += 1
                    continue
                stage[f"5 retest={rt}"] += 1
                if rt not in OB_RETEST_TYPES:
                    stage["6 KILLED by OB_RETEST_TYPES (not wick_only)"] += 1
                    continue
                stage["7 OCR SIGNAL"] += 1

print(f"symbols={syms}\ndays={days[0]}..{days[-1]} ({len(days)})")
tot = stage["0 candidate bars"]
for k in sorted(stage):
    print(f"  {k:46s} {stage[k]:8d}  {stage[k]/tot*100:6.2f}%")

# --- dead-clause proof: signal_runner.py:2881 `current.close > block.high` ----
# retest=="wick_only" (omen_bot.check_retest_type:355) already requires
#   min(open,close) > block.high, and close >= min(open,close).
# So the extra close-test can never be False. Same on the short side (:3143).
import itertools
viol = tot_wick = 0
for sym in syms:
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        for i in range(20, len(bars)):
            if not (SESSION_START <= bar_time(bars[i].timestamp) < SESSION_END):
                continue
            w = bars[:i + 1]
            for direction in ("bullish", "bearish"):
                blk, rt, _n = detect_order_block_setup(w, direction)
                if blk is None or rt not in OB_RETEST_TYPES:
                    continue
                tot_wick += 1
                ok = (w[-1].close > blk.high) if direction == "bullish" else (w[-1].close < blk.low)
                viol += (not ok)
print(f"\ndead-clause check: wick_only retests={tot_wick}, close-test False on {viol}"
      f"  -> the clause is {'DEAD (never False)' if viol == 0 else 'live'}")
