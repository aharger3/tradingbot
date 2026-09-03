"""G7.1 adversarial verify of track `losshalt` claim S2c.

Independent re-implementation (does NOT import g71_losshalt_grid) of:
  - the candidate pool
  - the causal day walker (streak halt + realised-R floor)
  - per-day R, worst day, max drawdown
  - a paired day-block bootstrap on total-R differences

Read-only over research/bt2y_trades.json. Publishes the numbers quoted in
research/g71_losshaltverify.md.
"""
from __future__ import annotations
import json, random, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"

d = json.loads(BOOK.read_text(encoding="utf-8"))
rows = d["trades"]
cand = [r for r in rows if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
sessions = sorted({r["day"] for r in rows})
print("meta traded/halted:", d["meta"]["traded"], d["meta"]["halted"], "sessions", d["meta"]["sessions"])
print("candidates:", len(cand), "traded days in pool:", len({r['day'] for r in cand}))

def ek(r): return (r["entry_i"], r["et"], r["sym"])
def xk(r): return (r["entry_i"] + r["bars"], r["et"], r["sym"])

def walk(day_rows, halt_n, floor):
    order = sorted(day_rows, key=ek)
    pend = []           # (exitkey, lost, r)
    streak = 0; realised = 0.0; taken = []
    for row in order:
        at = ek(row)
        while pend and pend[0][0] <= at:
            _x, lost, r = pend.pop(0)
            streak = streak + 1 if lost else 0
            realised += r
        gated = False
        if halt_n and streak >= halt_n: gated = True
        if floor is not None and realised <= floor: gated = True
        if gated: continue
        taken.append(row)
        pend.append((xk(row), row["out"] == "loss", row["r"]))
        pend.sort(key=lambda p: p[0])
    return taken

by_day = defaultdict(list)
for r in cand: by_day[r["day"]].append(r)

def arm(halt_n, floor):
    dayr = {}; n = 0; tot = 0.0; wins = 0
    for day in sorted(by_day):
        t = walk(by_day[day], halt_n, floor)
        s = sum(x["r"] for x in t)
        dayr[day] = s; tot += s; n += len(t)
        wins += sum(1 for x in t if x["r"] > 0)
    return dict(n=n, tot=tot, win=100.0*wins/n if n else 0.0, dayr=dayr)

def maxdd(dayr):
    eq = 0.0; peak = 0.0; dd = 0.0
    for day in sessions:
        eq += dayr.get(day, 0.0)
        peak = max(peak, eq)
        dd = min(dd, eq - peak)
    return dd

ARMS = {
    "none":        (None, None),
    "halt2":       (2, None),
    "halt3+f2":    (3, -2.0),
    "floor2only":  (None, -2.0),
    "halt2+f2":    (2, -2.0),
    "halt3":       (3, None),
    "halt4":       (4, None),
    "halt1":       (1, None),
}
res = {k: arm(*v) for k, v in ARMS.items()}
print("\n%-12s %6s %10s %9s %6s %9s %9s" % ("arm","n","totR","R/trade","win%","worstday","maxDD"))
for k, a in res.items():
    wd = min(a["dayr"].values())
    print("%-12s %6d %10.1f %9.4f %6.1f %9.2f %9.2f" % (k, a["n"], a["tot"], a["tot"]/a["n"], a["win"], wd, maxdd(a["dayr"])))

def boot(a, b, seed, nboot=4000):
    days = sorted(set(res[a]["dayr"]) | set(res[b]["dayr"]))
    diff = [res[a]["dayr"].get(x,0.0) - res[b]["dayr"].get(x,0.0) for x in days]
    rng = random.Random(seed)
    N = len(diff)
    tots = []
    for _ in range(nboot):
        tots.append(sum(diff[rng.randrange(N)] for _ in range(N)))
    tots.sort()
    return sum(diff), tots[int(0.025*nboot)], tots[int(0.975*nboot)]

print("\npaired day-block bootstrap (4000, seeds 11 and 99):")
for a, b in [("floor2only","halt2"), ("halt3+f2","halt2"), ("halt3+f2","floor2only"),
             ("halt2","none"), ("halt3+f2","none"), ("floor2only","none")]:
    for seed in (11, 99):
        dl, lo, hi = boot(a, b, seed)
        print("  %-22s d=%+8.1f  [%+8.1f, %+8.1f]  seed%d %s" % (
            a+" vs "+b, dl, lo, hi, seed, "TIE" if lo < 0 < hi else "READABLE"))

# streak-conditional edge, ungoverned book
buckets = defaultdict(list)
for day in sorted(by_day):
    order = sorted(by_day[day], key=ek); pend=[]; streak=0
    for row in order:
        at = ek(row)
        while pend and pend[0][0] <= at:
            _x, lost = pend.pop(0)
            streak = streak + 1 if lost else 0
        buckets[min(streak,4)].append(row["r"])
        pend.append((xk(row), row["out"]=="loss")); pend.sort(key=lambda p:p[0])
print("\nstreak-at-entry edge (ungoverned):")
for k in sorted(buckets):
    v = buckets[k]
    se = statistics.stdev(v)/len(v)**0.5
    print("  streak %d n=%4d mean %+0.4f SE %0.4f  t=%.2f" % (k, len(v), statistics.mean(v), se, statistics.mean(v)/se))

# --- adversarial stress: alternative uncertainty units + tail detail ---
import math
print("\npaired t-test on day differences (496 days):")
for a,b in [("floor2only","halt2"),("halt3+f2","halt2"),("halt3+f2","floor2only")]:
    days = sorted(set(res[a]["dayr"]) | set(res[b]["dayr"]))
    diff = [res[a]["dayr"].get(x,0.0)-res[b]["dayr"].get(x,0.0) for x in days]
    m = statistics.mean(diff); se = statistics.stdev(diff)/len(diff)**0.5
    print("  %-22s sum=%+7.1f mean/day=%+0.4f SE=%0.4f t=%+.2f  95%%CI total [%+.1f,%+.1f]" % (
        a+" vs "+b, sum(diff), m, se, m/se, (m-1.96*se)*len(diff), (m+1.96*se)*len(diff)))

print("\nweek-block bootstrap (4000, seed 11):")
from datetime import date
def wk(dstr):
    y,w,_ = date.fromisoformat(dstr).isocalendar(); return (y,w)
for a,b in [("floor2only","halt2"),("halt3+f2","halt2")]:
    days = sorted(set(res[a]["dayr"]) | set(res[b]["dayr"]))
    byw = defaultdict(float)
    for x in days: byw[wk(x)] += res[a]["dayr"].get(x,0.0)-res[b]["dayr"].get(x,0.0)
    v = list(byw.values()); rng = random.Random(11); N=len(v)
    t = sorted(sum(v[rng.randrange(N)] for _ in range(N)) for _ in range(4000))
    print("  %-22s weeks=%d d=%+.1f [%+.1f,%+.1f] %s" % (a+" vs "+b, N, sum(v), t[100], t[3899],
          "TIE" if t[100]<0<t[3899] else "READABLE"))

print("\nworst 5 days per arm:")
for k in ("halt2","halt3+f2","floor2only"):
    w = sorted(res[k]["dayr"].items(), key=lambda kv: kv[1])[:5]
    print("  %-11s %s" % (k, "  ".join("%s %+0.2f" % (d,r) for d,r in w)))
