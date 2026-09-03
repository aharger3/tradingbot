"""G7.1/btrverify -- why break_then_rejection trips 0x, on real bars.

Three questions, one pass over the committed 2-year book:
  A. does the shipped call (level proxy = t.stop) reproduce 0 trips?  [harness check]
  B. is the entry bar ever on the wrong side of the stop?             [the real blocker]
  C. on the SAME real bars, does break_then_rejection fire at any other
     candidate level price?                                           [reachability]

Offline: reads data_archive/ through polygon_feed's cache-first path.
Usage: python research/g71_btrverify_book.py [n_rows]
"""
import json, random, sys, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research import downgrade as dg
from backtest_2y import dg_bars

N = int(sys.argv[1]) if len(sys.argv) > 1 else 6000
BOOK = json.load(open(ROOT / "research" / "bt2y_trades.json"))
T = BOOK["trades"]
TR = [r for r in T if r["traded"]]
rest = [r for r in T if not r["traded"]]
random.seed(11)
sample = TR + random.sample(rest, min(N, len(rest)))
by_day = collections.defaultdict(list)
for r in sample:
    by_day[(r["sym"], r["day"])].append(r)

stat = collections.Counter()
lvl_fire_rows = 0
lvl_fire_examples = []
mismatch = 0
for (sym, day), rows in sorted(by_day.items()):
    try:
        bars = dg_bars(pf.rth(pf.fetch_day(sym, day)))
    except Exception:
        stat["nobars"] += 1
        continue
    if not bars:
        stat["nobars"] += 1
        continue
    for r in rows:
        i = r["entry_i"]
        if i is None or i >= len(bars):
            stat["oob"] += 1
            continue
        L = r["stop"]                       # the shipped level proxy (rounded 2dp)
        is_long = r["side"] == "L"
        stat["n"] += 1
        # A. shipped call
        if dg.break_then_rejection(bars, i, L, is_long):
            stat["btr_at_stop"] += 1
        # harness check: does the whole tripped vector match the book?
        rec = dg.score(bars, i, L, is_long)
        if rec and sorted(rec["tripped"]) != sorted(r["downgrades"]):
            mismatch += 1
        # B. entry bar on the wrong side of the level proxy?
        c = bars[i]["c"]
        wrong_side = (c <= L) if is_long else (c >= L)
        if wrong_side:
            stat["entry_close_wrong_side_of_stop"] += 1
        # C. same bars, sweep candidate level prices = distinct closes before i
        cands = sorted({round(bars[j]["c"], 4) for j in range(max(0, i - 30), i)})
        hits = [x for x in cands if dg.break_then_rejection(bars, i, x, is_long)]
        if hits:
            lvl_fire_rows += 1
            stat["cand_hits"] += len(hits)
            if len(lvl_fire_examples) < 5:
                lvl_fire_examples.append((sym, day, r["et"], r["side"], r["stop"],
                                          round(hits[0], 2), len(hits), len(cands)))
        stat["cands"] += len(cands)

n = stat["n"]
print("rows evaluated on real bars: %d  (traded %d + sampled non-traded)" % (n, len(TR)))
print("book-vs-recompute tripped-vector mismatches: %d" % mismatch)
print()
print("A. break_then_rejection at the SHIPPED level proxy (t.stop): %d of %d" % (stat["btr_at_stop"], n))
print("B. entry-bar close on the wrong side of the stop:            %d of %d" % (stat["entry_close_wrong_side_of_stop"], n))
print()
print("C. SAME bars, sweeping candidate level prices (prior-30 closes):")
print("   rows with >=1 level where the branch is TRUE: %d of %d (%.1f%%)"
      % (lvl_fire_rows, n, 100.0 * lvl_fire_rows / n if n else 0))
print("   candidate (row, level) pairs true: %d of %d (%.2f%%)"
      % (stat["cand_hits"], stat["cands"], 100.0 * stat["cand_hits"] / stat["cands"] if stat["cands"] else 0))
for e in lvl_fire_examples:
    print("   e.g. %s %s %s %s stop=%s -> fires at level %s (%d of %d candidate levels)" % e)
