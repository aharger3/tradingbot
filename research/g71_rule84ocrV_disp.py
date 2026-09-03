"""G71/rule84ocrV: adversarial re-run of the rule84ocr displacement claim.
Read-only. Reproduces the funnel, then tests the two load-bearing sub-claims:
 (a) is the 39.5% a rate over DISTINCT setups or over re-counted bar-evaluations?
 (b) does the displacement veto actually remove BR+OCR-confluence signals?
"""
import sys, os
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)

import polygon_feed as pf
from omen_bot import MarketStructure, _is_isolated, _has_displacement, check_retest_type
from signal_runner import OB_RETEST_TYPES, SESSION_START, SESSION_END, bar_time
from research import downgrade as dg

NDAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 25
NSYMS = int(sys.argv[2]) if len(sys.argv) > 2 else 6

CACHE = Path("data/cache")
syms = sorted(p.name for p in CACHE.iterdir() if (p / "1min").is_dir())[:NSYMS]
days = sorted({p.stem for s in syms for p in (CACHE / s / "1min").glob("*.csv")})[-NDAYS:]

stage = Counter()
distinct_pass = set()      # (sym,day,dir,block_idx) that passed isolation
distinct_killed = set()    # ...and were then killed by displacement
confl = Counter()          # confluence-yes/no among killed vs passed

def bars_to_dg(w):
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close,
             "v": getattr(c, "volume", 0)} for c in w]

for sym in syms:
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(bars) < 30:
            continue
        for i in range(20, len(bars)):
            if not (SESSION_START <= bar_time(bars[i].timestamp) < SESSION_END):
                continue
            w = bars[:i + 1]
            for direction in ("bullish", "bearish"):
                stage["0 candidate bars"] += 1
                s = MarketStructure(); s.update(w)
                blocks = s.get_valid_order_blocks(w, direction)
                if not blocks:
                    stage["1 no valid order block"] += 1; continue
                stage["2 block exists"] += 1
                block = blocks[0]
                brk = (s.last_hh if direction == "bullish" else s.last_ll)[2]
                try:
                    bidx = next(j for j in range(brk - 1, -1, -1)
                                if (w[j].is_bearish if direction == "bullish" else w[j].is_bullish))
                except StopIteration:
                    stage["2b no counter-coloured bar"] += 1; continue
                if not _is_isolated(w, bidx):
                    stage["3 KILLED by _is_isolated"] += 1; continue
                stage["3 passed isolation"] += 1
                key = (sym, d, direction, bidx, brk)
                distinct_pass.add(key)
                killed = not _has_displacement(w, bidx, brk, direction)
                if killed:
                    stage["4 KILLED by _has_displacement"] += 1
                    distinct_killed.add(key)
                    continue
                stage["4 passed displacement"] += 1
                rt = check_retest_type(block, w[-1], direction)
                if rt == "not_retesting":
                    stage["5 not retesting"] += 1; continue
                stage[f"5 retest={rt}"] += 1
                if rt not in OB_RETEST_TYPES:
                    stage["6 KILLED by OB_RETEST_TYPES"] += 1; continue
                stage["7 OCR SIGNAL"] += 1

tot = stage["0 candidate bars"]
print(f"symbols={syms}\ndays={days[0]}..{days[-1]} ({len(days)})")
for k in sorted(stage):
    print(f"  {k:46s} {stage[k]:8d}  {stage[k]/tot*100:6.2f}%")

pas, kil = stage["3 passed isolation"], stage["4 KILLED by _has_displacement"]
print(f"\nBAR-EVAL rate  killed/survivors = {kil}/{pas} = {kil/pas*100:.2f}%   (the claim's 39.5%)")
dp, dk = len(distinct_pass), len(distinct_killed)
# a distinct (block,break) can be killed at some bars and pass at others only if
# the leg changes; record both
print(f"DISTINCT setups (sym,day,dir,block_idx,break_idx): passed isolation={dp}, "
      f"ever-killed-by-displacement={dk} = {dk/dp*100:.2f}%")
