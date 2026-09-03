"""G7.1 adversarial verify of track `drawdown`.

Re-tests the prop-firm claim against the rules stated IN THE CITED EVIDENCE:
g4_prop_fit.md:24 ("DD lock") and risk_of_ruin.py:5 ("floor locks once
equity >= start + 5.75%"). Every firm's trailing floor STOPS TRAILING at a
stated buffer. An unconditional peak-to-trough max drawdown is therefore not
the bust test once the account is past that buffer.

Read-only. Touches no engine file, no mark file.
"""
import json
from collections import OrderedDict
from pathlib import Path

def money(x):
    return ("-$" if x < 0 else "$") + format(abs(x), ",.0f")


ROOT = Path(__file__).resolve().parent.parent
d = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
meta = d["meta"]
tr = [t for t in d["trades"] if t.get("traded")]
tr.sort(key=lambda t: (t["day"], t["et"]))
byday = OrderedDict()
for t in tr:
    byday[t["day"]] = byday.get(t["day"], 0.0) + t["r"]
days = list(byday)
dvals = [byday[dd] for dd in days]

def eod_curve(unit):
    eq, out = 0.0, []
    for v in dvals:
        eq += v * unit
        out.append(eq)
    return out

def trade_curve(unit):
    eq, out = 0.0, []
    for t in tr:
        eq += t["r"] * unit
        out.append(eq)
    return out

def sim(curve, dd, lock_at, lock_floor, target=None):
    """Trailing floor that stops trailing at `lock_at` profit, then sits at
    `lock_floor`. Returns (busted, when_index, min_headroom, hit_target_i)."""
    peak, floor, locked = 0.0, -dd, False
    minhead, hit = 1e18, None
    for i, eq in enumerate(curve):
        if not locked and eq > peak:
            peak = eq
            floor = peak - dd
            if peak >= lock_at:
                floor, locked = lock_floor, True
        if target is not None and hit is None and eq >= target:
            hit = i
        head = eq - floor
        if head < minhead:
            minhead, argmin = head, i
        if eq <= floor:
            return True, i, head, hit
    return False, None, minhead, hit

FIRMS = [
    # name, dd, lock_at (profit at which trailing stops), lock_floor (equity level), eval target
    ("Apex $150K EOD 4.0",  4000.0, 4100.0,  100.0, 9000.0),
    ("Topstep $150K MLL",   4500.0, 4500.0,    0.0, 9000.0),
    ("MFF Pro $150K",       4500.0, 4600.0,  100.0, 9000.0),
    ("Vanquish $150k",      7500.0, 8625.0,    0.0, 15000.0),
]

print("book %s  traded=%d  days=%d  total=%+.2fR" % (meta["generated"], len(tr), len(days), sum(dvals)))
print()
for unit in (1000.0,):
    for name, dd, lock_at, lock_floor, tgt in FIRMS:
        for lab, c in (("EOD-trail", eod_curve(unit)), ("intraday-trail(trade-level proxy)", trade_curve(unit))):
            b, i, mh, hit = sim(c, dd, lock_at, lock_floor, tgt)
            lockidx = next((j for j, e in enumerate(c) if e >= lock_at), None)
            print("$%d/R  %-22s %-34s  bust=%-5s  min headroom %s"
                  % (unit, name, lab, b, money(mh)))
            if b:
                print("        busted at index %d" % i)
print()
# ---- unconditional (what the claim did): no lock at all
print("== unconditional trailing (NO lock) — the claim's model ==")
for name, dd, lock_at, lock_floor, tgt in FIRMS:
    for lab, c in (("EOD", eod_curve(1000.0)), ("intraday", trade_curve(1000.0))):
        b, i, mh, hit = sim(c, dd, 1e18, 0.0)
        print("  %-22s %-9s bust=%s" % (name, lab, b))
print()
# ---- how fast does the lock arrive?
c = eod_curve(1000.0)
for name, dd, lock_at, lock_floor, tgt in FIRMS:
    j = next((k for k, e in enumerate(c) if e >= lock_at), None)
    print("  %-22s locks after %d trading sessions (%s), equity %s" % (name, j + 1, days[j], money(c[j])))
print()
# ---- post-lock ruin test: does EOD equity ever return to the locked floor?
print("== post-lock: minimum EOD equity AFTER the lock date, per firm, $1000/R ==")
for name, dd, lock_at, lock_floor, tgt in FIRMS:
    j = next((k for k, e in enumerate(c) if e >= lock_at), None)
    post = c[j:]
    m = min(post)
    print("  %-22s locked floor %s | min EOD equity after lock %s (%s) | headroom %s"
          % (name, money(lock_floor), money(m), days[j + post.index(m)], money(m - lock_floor)))


# ------------------------------------------------------------------ part 2
# Largest risk unit that survives each floor ON THIS REALIZED PATH once the
# lock is modelled. Compare with the lock-blind numbers in g71_drawdown.md.
def prelock_dd_r(lock_r):
    """max (peak - eq) in R while the running peak is still below lock_r."""
    eq = peak = worst = 0.0
    for v in dvals:
        eq += v
        if eq > peak:
            peak = eq
        worst = max(worst, peak - eq)
        if peak >= lock_r:
            break
    return worst


print()
print("== largest risk unit surviving each floor, LOCK MODELLED, this path ==")
ROWS = [("4% of $150k", 6000., 6100.), ("5% of $150k", 7500., 7600.),
        ("6% of $150k", 9000., 9100.), ("Apex $150K EOD 4.0", 4000., 4100.),
        ("Topstep MLL / MFF Pro", 4500., 4600.), ("Vanquish $150k", 7500., 8625.)]
print("  %-24s %9s %9s %14s" % ("floor", "floor $", "preDD R", "max $/R"))
for name, fl, lk in ROWS:
    best = 0
    for u in range(25, 5001, 25):
        if prelock_dd_r(lk / u) * u < fl:
            best = u
    print("  %-24s %9s %9.2f %14s"
          % (name, money(fl), prelock_dd_r(lk / 1000.), money(best)))
print()
print("  CAVEAT: one realized ordering. g4_prop_fit.py sizes off 20k Monte-Carlo")
print("  orderings of pre-lock ruin, which is the correct method; this table only")
print("  shows that the FULL-HISTORY max drawdown is not the binding constraint.")
