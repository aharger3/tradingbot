"""G7.1 / lnrverify -- decompose `level_not_respected` trips by SIDE.

The claim under test: "counts closes within a tolerance of the level on EITHER
side; Austin's rule is that only a close THROUGH the level is disrespect."

Replays the archived RTH bars for every TRADED row of research/bt2y_trades.json
and, over the same window downgrade.level_not_respected uses (bars[i-12..i]) with
the same eps (_eps), counts each close as:
    right_in  -- correct side of the level, within eps      (a2: "fine")
    wrong_in  -- wrong side of the level, within eps
    wrong_out -- wrong side by MORE than eps  (a close THROUGH -- what the claim
                 says should count; the committed code never counts it)
Then re-tests the variable under three readings.
"""
import json, statistics, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polygon_feed as pf
from research import downgrade as dg

ROOT = Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "research" / "bt2y_trades.json"))
TR = [r for r in B["trades"] if r["traded"]]
m = lambda rs: statistics.fmean(x for x in rs) if rs else float("nan")

cache = {}
def bars_for(sym, day):
    k = (sym, day)
    if k not in cache:
        try:
            cache[k] = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
                        for c in pf.rth(pf.fetch_day(sym, day))]
        except Exception:
            cache[k] = []
    return cache[k]

n = miss = 0
agree = 0
tot = {"right_in": 0, "wrong_in": 0, "wrong_out": 0}
rows = []   # (shipped, wrong_in>=2, wrong_out>=2, any_wrong>=2, r)
for r in TR:
    bs = bars_for(r["sym"], r["day"])
    i = r["entry_i"]
    if not bs or i >= len(bs):
        miss += 1
        continue
    n += 1
    level = r["stop"]; is_long = r["side"] == "L"
    e = dg._eps(bs, i)
    win = bs[max(0, i - 12):i + 1]
    ri = wi = wo = 0
    for b in win:
        d = (b["c"] - level) if is_long else (level - b["c"])   # >0 = correct side
        if abs(d) <= e:
            (ri if d >= 0 else wi).__class__          # no-op, keep explicit below
            if d >= 0: ri += 1
            else: wi += 1
        elif d < 0:
            wo += 1
    tot["right_in"] += ri; tot["wrong_in"] += wi; tot["wrong_out"] += wo
    shipped = (ri + wi) >= dg.CHOP_TOUCHES
    if shipped == ("level_not_respected" in r["downgrades"]):
        agree += 1
    rows.append((shipped, wi >= 2, wo >= 2, (wi + wo) >= 2, r["r"]))

print("replayed %d traded rows (%d missing bars)" % (n, miss))
print("agreement of local recompute with the book's stored flag: %d/%d (%.2f%%)"
      % (agree, n, 100.0 * agree / n))
print("closes in the 12-bar window, pooled: right-of-level within eps %d | "
      "wrong-of-level within eps %d | wrong-of-level BEYOND eps (a close THROUGH) %d"
      % (tot["right_in"], tot["wrong_in"], tot["wrong_out"]))
print()
def rep(label, idx):
    tp = [x[4] for x in rows if x[idx]]
    cl = [x[4] for x in rows if not x[idx]]
    print("  %-46s trips %4d/%d (%5.2f%%)  tripped %+.4f  clean %+.4f  delta %+.4f"
          % (label, len(tp), len(rows), 100.0*len(tp)/len(rows),
             m(tp), m(cl), m(tp) - m(cl)))
print("reading                                          (traded rows only)")
rep("SHIPPED  |c-level| <= eps, either side, >=2", 0)
rep("CLAIM    close THROUGH by > eps, >=2", 2)
rep("HYBRID   any close on the wrong side, >=2", 3)
rep("WRONG-IN only wrong side within eps, >=2", 1)

# --- does the CLAIM's reading fix the backwards S/A/C ranking? --------------
print()
print("re-grade traded rows swapping the shipped flag for the claim's reading")
def gr(trip, confl):
    net = len(trip) - (1 if confl else 0)
    return "S" if net <= 0 else ("A" if net == 1 else "C")
res = {}
for r, x in zip([r for r in TR], rows):
    pass
byrow = list(zip([r for r in TR], rows))
for label, idx in (("shipped", 0), ("claim close-through", 2), ("hybrid wrong-side", 3)):
    buckets = {"S": [], "A": [], "C": []}
    for r, x in byrow:
        trip = [d for d in r["downgrades"] if d != "level_not_respected"]
        if x[idx]:
            trip.append("level_not_respected")
        buckets[gr(trip, r["confluence"] == "yes")].append(r["r"])
    print("  %-20s " % label, " ".join(
        "%s n=%4d %+.4f" % (g, len(buckets[g]), m(buckets[g])) for g in "SAC"))
