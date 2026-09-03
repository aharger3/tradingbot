"""G71/rule84ocr: the two `isolated` tests for the SAME rule, cross-tabbed.

omen_bot._is_isolated (omen_bot.py:388)  -- PRICE overlap vs the prior 4 bars
research/downgrade.find_ocr (:302-312)   -- COLOUR isolation, both neighbours
                                            trend-coloured ("it is called the ONE
                                            candle rule")
Both claim to implement Austin's "isolated, hard to dispute" OCR. They are
different predicates. This measures how often they disagree.
Read-only.
"""
import sys, os
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)
import polygon_feed as pf
from omen_bot import MarketStructure, _is_isolated

CACHE = Path("data/cache")
syms = sorted(p.name for p in CACHE.iterdir() if (p / "1min").is_dir())[:6]
days = sorted({p.stem for s in syms for p in (CACHE / s / "1min").glob("*.csv")})[-25:]

x = Counter()
for sym in syms:
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(bars) < 30:
            continue
        for i in range(20, min(len(bars), 91)):
            w = bars[:i + 1]
            for direction in ("bullish", "bearish"):
                s = MarketStructure(); s.update(w)
                if not s.get_valid_order_blocks(w, direction):
                    continue
                brk = (s.last_hh if direction == "bullish" else s.last_ll)[2]
                try:
                    j = next(k for k in range(brk - 1, -1, -1)
                             if (w[k].is_bearish if direction == "bullish" else w[k].is_bullish))
                except StopIteration:
                    continue
                if j - 1 < 0 or j + 1 >= len(w):
                    continue
                price_iso = _is_isolated(w, j)
                up = lambda b: b.close > b.open
                is_long = direction == "bullish"
                left = up(w[j - 1]) if is_long else not up(w[j - 1])
                right = up(w[j + 1]) if is_long else not up(w[j + 1])
                colour_iso = left and right
                x[(price_iso, colour_iso)] += 1
tot = sum(x.values())
print(f"n={tot} order-block candidates ({syms}, {days[0]}..{days[-1]})")
for k in sorted(x):
    print(f"  price_isolated={k[0]!s:5s} colour_isolated={k[1]!s:5s}  {x[k]:7d}  {x[k]/tot*100:5.2f}%")
agree = x[(True, True)] + x[(False, False)]
print(f"  AGREE {agree/tot*100:.1f}%   DISAGREE {100-agree/tot*100:.1f}%")
print(f"  price test passes {sum(v for k,v in x.items() if k[0])/tot*100:.1f}% ; "
      f"colour test passes {sum(v for k,v in x.items() if k[1])/tot*100:.1f}%")
