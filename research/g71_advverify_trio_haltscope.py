"""ADVERSARIAL: the trio green-month counts subset a book whose R31 loss halt was
computed ACCOUNT-WIDE over 28 symbols (loss_halt.apply_to_book, account-wide by
design). A real 3-symbol run halts on the trio's own losses only. This re-applies
loss_halt.halt_day scoped to each trio and re-counts green months.
"""
import json, sys, os, itertools
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import loss_halt

b = json.load(open("research/bt2y_trades.json", encoding="utf-8"))
rows = b["trades"]
# the unhalted candidate set: taken, or taken-then-blocked by the account-wide halt
cand = [r for r in rows if r.get("traded") or r.get("halted")]
print("candidates (unhalted book) %d ; account-wide traded %d ; halted %d"
      % (len(cand), sum(1 for r in rows if r.get("traded")),
         sum(1 for r in rows if r.get("halted"))))

EK = lambda x: (x.get("entry_i", 0), x.get("et", ""), x.get("sym", ""))
XK = lambda x: (x.get("entry_i", 0) + x.get("bars", 0), x.get("et", ""), x.get("sym", ""))
LK = lambda x: x.get("out") == "loss"

def rescope(syms):
    sub = [r for r in cand if r["sym"] in syms]
    byday = defaultdict(list)
    for r in sub:
        byday[r["day"]].append(r)
    blocked = set()
    for day, rs in byday.items():
        for r in loss_halt.halt_day(rs, EK, XK, LK):
            blocked.add(id(r))
    kept = [r for r in sub if id(r) not in blocked]
    mm = defaultdict(float)
    for r in kept:
        mm[r["ym"]] += r["r"]
    return kept, sum(1 for v in mm.values() if v > 0), len(mm)

# whole book control: rescoping over ALL symbols must reproduce 2437 / 25 green
k, g, m = rescope(set(r["sym"] for r in cand))
print("CONTROL all-symbol rescope: traded %d green %d/%d (expect 2437, 25/25)" % (len(k), g, m))

named = [("SPY","TSLA","AAPL"), ("SPY","TSLA","NVDA"), ("SPY","AAPL","ORCL"), ("SPY","NVDA","GOOGL")]
print("\ntrio                  account-wide-halt   trio-scoped-halt")
allsyms = sorted(set(r["sym"] for r in cand) - {"SPY"})
def acct(syms):
    mm = defaultdict(float); n = 0
    for r in rows:
        if r.get("traded") and r["sym"] in syms:
            mm[r["ym"]] += r["r"]; n += 1
    return n, sum(1 for v in mm.values() if v > 0), len(mm)
for t in named:
    an, ag, am = acct(set(t))
    k, g, m = rescope(set(t))
    print("%-20s  n=%-4d %2d/%-2d       n=%-4d %2d/%-2d" % ("+".join(t), an, ag, am, len(k), g, m))

best = []
for pair in itertools.combinations(allsyms, 2):
    t = ("SPY",) + pair
    k, g, m = rescope(set(t))
    best.append(("+".join(t), g, m, len(k)))
best.sort(key=lambda x: (-x[1], -x[3]))
print("\nALL 351 SPY trios under a TRIO-SCOPED halt, top 10:")
for r in best[:10]:
    print("  %-22s green %2d/%-2d n=%d" % (r[0], r[1], r[2], r[3]))
print("trios reaching 25/25:", [r[0] for r in best if r[1] == 25 and r[2] == 25])

print("\nTSLA trios under trio-scoped halt, worst first:")
for r in sorted([x for x in best if "TSLA" in x[0]], key=lambda x: x[1])[:8]:
    print("  %-22s green %2d/%-2d n=%d" % (r[0], r[1], r[2], r[3]))
