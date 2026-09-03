"""ADVERSARIAL re-check of G71/symbols durability BLOCKER (independent of g71_symbols_trio.py).

Recomputes, from research/bt2y_trades.json directly:
  * whole-book traded count + green months
  * green months for EVERY SPY+2 trio over ALL book symbols (not just the 15-name POOL)
  * the specific trios named in the claim
Optionally against an alternate book path (the committed T0 2,595 book).
"""
import json, sys, itertools
from collections import defaultdict

path = sys.argv[1] if len(sys.argv) > 1 else "research/bt2y_trades.json"
b = json.load(open(path, encoding="utf-8"))
tr = [t for t in b["trades"] if t.get("traded")]
print("book", path, b["meta"].get("generated"), "traded", len(tr))

allm = defaultdict(float)
per = defaultdict(lambda: defaultdict(float))
for t in tr:
    allm[t["ym"]] += t["r"]
    per[t["sym"]][t["ym"]] += t["r"]
print("whole book: months %d green %d red %d  meanR %+0.4f  win(r>0) %.1f%%" % (
    len(allm), sum(1 for v in allm.values() if v > 0),
    sum(1 for v in allm.values() if v <= 0),
    sum(t["r"] for t in tr)/len(tr),
    100*sum(1 for t in tr if t["r"] > 0)/len(tr)))
print("red months:", sorted(k for k, v in allm.items() if v <= 0))

syms = sorted(per)
POOL = ["TSLA","NVDA","AAPL","MU","AMD","PLTR","META","MSFT","GOOGL","AMZN","INTC","COIN","ORCL","NFLX","QQQ"]
def score(trio):
    mm = defaultdict(float)
    n = 0
    for s in trio:
        for ym, v in per[s].items():
            mm[ym] += v
        n += sum(1 for t in tr if t["sym"] == s)
    return sum(1 for v in mm.values() if v > 0), len(mm), n

rows = []
for pair in itertools.combinations([s for s in syms if s != "SPY"], 2):
    trio = ("SPY",) + pair
    g, m, n = score(trio)
    rows.append(("+".join(trio), g, m, n, all(x in POOL for x in pair)))
rows.sort(key=lambda x: (-x[1], -x[3]))
print("\nALL SPY trios over book symbols: %d combos (%d inside the 15-name POOL)" % (
    len(rows), sum(1 for r in rows if r[4])))
print("top 12 by green:")
for r in rows[:12]:
    print("  %-22s green %2d/%-2d  n=%-4d poolscored=%s" % (r[0], r[1], r[2], r[3], r[4]))
best_pool = max((r for r in rows if r[4]), key=lambda x: x[1])
print("best inside POOL:", best_pool)
named = ["SPY+TSLA+AAPL","SPY+TSLA+NVDA","SPY+AAPL+ORCL","SPY+NVDA+GOOGL"]
print("\nclaim's named trios:")
d = {r[0]: r for r in rows}
for k in named:
    print("  %-18s %s" % (k, d.get(k)))
print("\nall TSLA trios (SPY+TSLA+x), sorted by green:")
tt = sorted([r for r in rows if "TSLA" in r[0]], key=lambda x: x[1])
for r in tt:
    print("  %-22s green %2d/%-2d n=%-4d pool=%s" % (r[0], r[1], r[2], r[3], r[4]))
