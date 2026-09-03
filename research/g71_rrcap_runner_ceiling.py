"""g71 (rrcap): the ladder's OWN ceiling. backtest_week.py:851-858 builds the
runner target as min(PDH/PMH beyond the scale point, floor(scale)+$1). Because
the next-whole-dollar candidate is ALWAYS in the list and min() is taken, the
runner can never aim more than $1.00 past the session extreme as of the entry
bar -- whatever level actually sits out there. This prices that ceiling."""
import json, math, statistics, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf

bk = json.loads((ROOT / "research" / "bt2y_trades.json").read_text(encoding="utf-8"))
tr = [r for r in bk["trades"] if r["traded"]]
by_day = defaultdict(list)
for r in tr:
    by_day[(r["sym"], r["day"])].append(r)

rows = []
for (sym, day), rs in sorted(by_day.items()):
    try:
        rth = pf.rth(pf.fetch_day(sym, day))
    except Exception:
        continue
    if not rth:
        continue
    for r in rs:
        i0 = r["entry_i"]
        if i0 is None or i0 >= len(rth):
            continue
        entry, stop = r["entry"], r["stop"]
        long = r["dir"] == "call"
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        # exactly backtest_week.py:851-858, minus pdh/pmh (unavailable here) --
        # dropping them can only RAISE this ceiling, so it is an upper bound.
        if long:
            scale = max(c.high for c in rth[:i0 + 1])
            whole = math.floor(scale) + 1.0
        else:
            scale = min(c.low for c in rth[:i0 + 1])
            whole = math.ceil(scale) - 1.0
        scale_r = ((scale - entry) if long else (entry - scale)) / risk
        run_r = ((whole - entry) if long else (entry - whole)) / risk
        ceil_r = 0.5 * scale_r + 0.5 * run_r      # best case if BOTH rungs fill
        rows.append({"ceil": ceil_r, "scale_r": scale_r, "run_r": run_r,
                     "booked": r["r"], "scaled": bool(r.get("scaled"))})

n = len(rows)
c = [x["ceil"] for x in rows]
print("rows %d" % n)
print("ladder best-case ceiling R: mean %+.4f  median %+.4f  p90 %+.4f  max %+.4f"
      % (statistics.fmean(c), statistics.median(c), sorted(c)[int(.9*n)], max(c)))
for t in (2.0, 3.0, 4.0):
    k = sum(1 for x in c if x >= t)
    print("  ceiling >= %.1fR : %d (%.2f%%)" % (t, k, 100*k/n))
sc = [x for x in rows if x["scaled"]]
cs = [x["ceil"] for x in sc]
print("scaled rows %d -- ceiling mean %+.4f median %+.4f; >=2R %d (%.2f%%)"
      % (len(sc), statistics.fmean(cs), statistics.median(cs),
         sum(1 for x in cs if x >= 2), 100*sum(1 for x in cs if x >= 2)/len(sc)))
rr = [x["run_r"] for x in sc]
print("scaled runner-leg cap (whole-$ target) in R: mean %+.4f median %+.4f; <=2R %.2f%%"
      % (statistics.fmean(rr), statistics.median(rr),
         100*sum(1 for x in rr if x <= 2)/len(rr)))
