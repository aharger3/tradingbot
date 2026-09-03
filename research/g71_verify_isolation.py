"""ADVERSARIAL VERIFY of track rule84ocr's isolation claim. Read-only.

Reproduces g71_rule84ocr_isolation.py / _funnel.py and adds four controls the
originals lack:
  1. right_ok is TRUE BY CONSTRUCTION -- block_idx is the LAST counter-coloured
     bar before the break, so bars[block_idx+1] cannot be counter-coloured.
     Decompose colour_iso into left_ok / right_ok and report each.
  2. per-BLOCK (deduped) kill rate vs per-BAR-EVALUATION kill rate.
  3. does downgrade.find_ocr actually RETURN block_idx? "colour_isolated=True"
     is not the same as "find_ocr would find this candle".
  4. full 28-symbol universe, not the first 6/8 alphabetically.
Usage: python research/g71_verify_isolation.py [ndays] [nsyms]
"""
import sys, os
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.chdir(Path(__file__).resolve().parent.parent)
import polygon_feed as pf
from omen_bot import MarketStructure, _is_isolated, _has_displacement
from signal_runner import SESSION_START, SESSION_END, bar_time
from research import downgrade as dg

NDAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 40
NSYMS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
CACHE = Path("data/cache")
allsyms = sorted(p.name for p in CACHE.iterdir() if (p / "1min").is_dir())
syms = allsyms[:NSYMS]
days = sorted({p.stem for s in syms for p in (CACHE / s / "1min").glob("*.csv")})[-NDAYS:]

x = Counter()          # (price_iso, colour_iso) cross-tab, per bar-eval
side = Counter()       # left_ok / right_ok separately
blocks_seen = {}       # (sym,day,dir,block_idx) -> price_iso  (dedup)
stage = Counter()
findocr_hit = Counter()

for sym in syms:
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(bars) < 30:
            continue
        raw = [{"o": b.open, "h": b.high, "l": b.low, "c": b.close} for b in bars]
        for i in range(20, len(bars)):
            if not (SESSION_START <= bar_time(bars[i].timestamp) < SESSION_END):
                continue
            w = bars[:i + 1]
            for direction in ("bullish", "bearish"):
                stage["0 candidate bars"] += 1
                s = MarketStructure(); s.update(w)
                if not s.get_valid_order_blocks(w, direction):
                    stage["1 no valid order block"] += 1
                    continue
                stage["2 block exists"] += 1
                brk = (s.last_hh if direction == "bullish" else s.last_ll)[2]
                try:
                    j = next(k for k in range(brk - 1, -1, -1)
                             if (w[k].is_bearish if direction == "bullish" else w[k].is_bullish))
                except StopIteration:
                    stage["2b no counter-coloured bar"] += 1
                    continue
                price_iso = _is_isolated(w, j)
                stage["3 passed isolation" if price_iso else "3 KILLED by _is_isolated"] += 1
                blocks_seen.setdefault((sym, d, direction, j), price_iso)
                if j - 1 < 0 or j + 1 >= len(w):
                    continue
                is_long = direction == "bullish"
                up = lambda b: b.close > b.open
                left = up(w[j - 1]) if is_long else not up(w[j - 1])
                right = up(w[j + 1]) if is_long else not up(w[j + 1])
                x[(price_iso, left and right)] += 1
                side["left_ok" if left else "left_FAIL"] += 1
                side["right_ok" if right else "right_FAIL"] += 1
                side["j+1 is inside (block,break) span"] += (j + 1 < brk)
                side["n"] += 1
                # control 3: would downgrade.find_ocr actually return j?
                if left and right:
                    got = dg.find_ocr(raw[:i + 1], i, is_long)
                    findocr_hit["colour_iso_candidates"] += 1
                    findocr_hit["find_ocr returns THIS bar" if got == j
                                else ("find_ocr returns a DIFFERENT bar" if got is not None
                                      else "find_ocr returns None")] += 1

tot = sum(x.values())
print(f"syms={syms}\ndays={days[0]}..{days[-1]} ({len(days)})")
print(f"\n--- cross-tab, per bar-eval  n={tot}")
for k in sorted(x):
    print(f"  price_iso={k[0]!s:5s} colour_iso={k[1]!s:5s} {x[k]:8d} {x[k]/tot*100:6.2f}%")
ag = x[(True, True)] + x[(False, False)]
print(f"  AGREE {ag/tot*100:.1f}%  DISAGREE {100-ag/tot*100:.1f}%")
print(f"  price passes {sum(v for k,v in x.items() if k[0])/tot*100:.1f}%  "
      f"colour passes {sum(v for k,v in x.items() if k[1])/tot*100:.1f}%")

n = side["n"]
print(f"\n--- CONTROL 1: colour test decomposed  n={n}")
for k in ("left_ok", "left_FAIL", "right_ok", "right_FAIL",
          "j+1 is inside (block,break) span"):
    print(f"  {k:36s} {side[k]:8d} {side[k]/n*100:6.2f}%")

print(f"\n--- CONTROL 2: per-BLOCK dedup")
nb = len(blocks_seen)
killed = sum(1 for v in blocks_seen.values() if not v)
print(f"  distinct (sym,day,dir,block_idx) blocks {nb}")
print(f"  killed by _is_isolated                  {killed}  {killed/nb*100:.1f}%")
be = stage["2 block exists"] - stage["2b no counter-coloured bar"]
print(f"  per-bar-eval kill rate (prior agent's)  "
      f"{stage['3 KILLED by _is_isolated']}/{be} = "
      f"{stage['3 KILLED by _is_isolated']/be*100:.1f}%")

print(f"\n--- CONTROL 3: does find_ocr actually return the block candle?")
c = findocr_hit["colour_iso_candidates"] or 1
for k in sorted(findocr_hit):
    print(f"  {k:36s} {findocr_hit[k]:8d} {findocr_hit[k]/c*100:6.2f}%")

print(f"\n--- funnel stages")
t0 = stage["0 candidate bars"]
for k in sorted(stage):
    print(f"  {k:40s} {stage[k]:8d} {stage[k]/t0*100:6.2f}%")
