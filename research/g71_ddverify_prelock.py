"""ADVERSARIAL VERIFY of the drawdown track's "$350 ceiling == g4 R*" claim.

g4_prop_fit.py:116-129 `funded_prelock_ruin` = P(blow the trailing DD BEFORE
reaching the lock buffer ~$4,100). After the lock the floor is static at
start+$100 and never trails again (g4_prop_fit.py:145-175).

g71_drawdown_audit.py instead divides the WHOLE-BOOK 2-year peak-to-trough
(17.13R, which happens at equity +588.6R, ~1,300 trades in) by the floor.
Those are not the same quantity. This script runs g4's ACTUAL mechanic on the
real 2,437-trade path to see what risk unit the book supports.

Read-only. Touches no engine file, no mark file.
"""
import json, statistics
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
meta = d["meta"]
tr = [t for t in d["trades"] if t.get("traded")]
tr.sort(key=lambda t: (t["day"], t["et"]))
rs = [t["r"] for t in tr]
byday = OrderedDict()
for t in tr:
    byday[t["day"]] = byday.get(t["day"], 0.0) + t["r"]
days, dvals = list(byday), list(byday.values())

print("book: traded=%d days=%d total=%+.2fR mean=%+.4fR" %
      (len(tr), len(days), sum(rs), sum(rs)/len(rs)))

def maxdd(seq):
    eq = peak = dd = 0.0
    for r in seq:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return dd

print("whole-book maxDD  trade-level %.2fR  day-level %.2fR"
      % (maxdd(rs), maxdd(dvals)))

# ---- 1. where does the worst DD sit in the equity path?
eq = 0.0; peak = 0.0; pi = -1; best = (0.0, -1, -1)
for i, r in enumerate(rs):
    eq += r
    if eq > peak: peak, pi = eq, i
    if peak - eq > best[0]: best = (peak - eq, pi, i)
print("worst DD %.2fR starts at trade #%d (equity %+.2fR), ends #%d"
      % (best[0], best[1], sum(rs[:best[1]+1]), best[2]))

# ---- 2. g4's ACTUAL mechanic on the real path, day-level (Apex EOD)
#     start at every session, trailing dd $4,000, lock buffer $4,100
def prelock_ruin(vals, unit, dd=4000.0, buf=4100.0):
    ruin = lock = incomplete = 0
    for s in range(len(vals)):
        e = 0.0; pk = 0.0; done = False
        for r in vals[s:]:
            e += r * unit
            pk = max(pk, e)
            if e <= pk - dd:
                ruin += 1; done = True; break
            if e >= buf:
                lock += 1; done = True; break
        if not done:
            incomplete += 1
    n = len(vals)
    return ruin/n, lock/n, incomplete/n

print()
print("PRE-LOCK RUIN on the REAL path (Apex $150K EOD: dd $4,000, lock +$4,100)")
print("  %-8s %10s %10s %10s" % ("unit", "ruin%", "lock%", "unresolved%"))
for unit in (250, 350, 400, 525, 650, 800, 1000):
    r_, l_, i_ = prelock_ruin(dvals, unit)
    print("  $%-7d %9.1f%% %9.1f%% %9.1f%%" % (unit, 100*r_, 100*l_, 100*i_))

# largest $25-grid unit with pre-lock ruin < 5%, same rule as g4:209-213
best_unit = None
for u in range(100, 3001, 25):
    if prelock_ruin(dvals, u)[0] < 0.05:
        best_unit = u
print("  -> largest $25-grid unit with pre-lock ruin <5%% on the real path: $%s"
      % best_unit)

# ---- 3. how big is the DD *inside* the pre-lock window?
worst_pre = []
for s in range(len(dvals)):
    e = 0.0; pk = 0.0; dd = 0.0
    for r in dvals[s:]:
        e += r; pk = max(pk, e); dd = max(dd, pk - e)
        if e >= 11.71:   # +$4,100 at $350/R
            break
    worst_pre.append(dd)
worst_pre.sort()
print()
print("day-level DD inside the pre-lock window (to +11.71R = $4,100 @ $350/R):")
print("  median %.2fR  p95 %.2fR  max %.2fR   (whole-book %.2fR)"
      % (worst_pre[len(worst_pre)//2], worst_pre[int(.95*len(worst_pre))],
         max(worst_pre), maxdd(dvals)))

# ---- 4. sensitivity: the "ceiling" is one episode
def unit_for(floor, dd): return floor/dd
eps = sorted([maxdd(rs)], reverse=True)
print()
print("sensitivity of the audit's own ceiling:")
for floor, lab in ((6000.0, "4% of $150k (Austin's hypo)"),
                   (4000.0, "Apex $4,000 (the firm g4 recommends)"),
                   (4500.0, "Topstep/MFF $4,500")):
    print("  %-38s intraday $%.0f | EOD $%.0f"
          % (lab, floor/maxdd(rs), floor/maxdd(dvals)))
# second-worst episode
print("  2nd-worst intraday episode is 15.40R -> 4%% floor gives $%.0f (not $350)"
      % (6000.0/15.40))
