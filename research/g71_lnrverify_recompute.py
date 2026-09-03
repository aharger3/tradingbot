"""G7.1 / lnrverify -- adversarial check of the `level_not_respected` claim.

Reads only the committed book (research/bt2y_trades.json). Rebuilds each row's
S/A/C grade from its stored `downgrades` + `confluence` using downgrade.score's
own arithmetic (net = len(tripped) - (1 if confluence else 0); S<=0, A==1, C>=2),
verifies the rebuild reproduces the stored `sgrade` exactly, then re-grades with
`level_not_respected` DELETED to see whether the backwards S<A<C money ranking is
actually caused by that variable.
"""
import json, statistics, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
B = json.load(open(ROOT / "research" / "bt2y_trades.json"))
T = B["trades"]; TR = [r for r in T if r["traded"]]
m = lambda rs: statistics.fmean(r["r"] for r in rs) if rs else float("nan")

def grade(trip, confl):
    net = len(trip) - (1 if confl else 0)
    return "S" if net <= 0 else ("A" if net == 1 else "C")

# 1. fidelity of the rebuild
bad = sum(1 for r in T if grade(r["downgrades"], r["confluence"] == "yes") != r["sgrade"])
print("rebuild mismatches vs stored sgrade: %d of %d" % (bad, len(T)))

def table(drop=None, label=""):
    print("\n-- %s --" % label)
    tot = collections.Counter()
    for r in T:
        tr = [d for d in r["downgrades"] if d != drop]
        tot[grade(tr, r["confluence"] == "yes")] += 1
    print("  all signals:", dict(tot))
    for g in ("S", "A", "C"):
        rs = [r for r in TR
              if grade([d for d in r["downgrades"] if d != drop],
                       r["confluence"] == "yes") == g]
        w = sum(1 for r in rs if r["out"] == "win")
        print("  traded %s n=%4d meanR %+.4f win%% %.1f sumR %+.1f"
              % (g, len(rs), m(rs), 100.0*w/len(rs) if rs else 0, sum(r["r"] for r in rs)))

table(None, "as shipped (all variables)")
table("level_not_respected", "level_not_respected DELETED")
table("counter_trend_not_respected", "counter_trend_not_respected DELETED (control)")
table("no_retest", "no_retest DELETED (control, correctly-signed var)")

# 2. is it the LARGEST input? rank by trip count and by |delta| on traded
print("\n-- rank of each variable as an input to the grade --")
dw = collections.Counter()
for r in T: dw.update(r["downgrades"])
rows = []
for v, n in dw.items():
    tp = [r for r in TR if v in r["downgrades"]]
    cl = [r for r in TR if v not in r["downgrades"]]
    rows.append((n, v, (m(tp) - m(cl)) if tp and cl else float("nan")))
for n, v, d in sorted(rows, reverse=True):
    print("  %-30s trips %6d (%5.2f%%)  traded delta %+.4f" % (v, n, 100.0*n/len(T), d))

# 3. does sgrade gate anything in this book?
print("\n-- does sgrade route? --")
print("  traded rows by sgrade:", dict(collections.Counter(r["sgrade"] for r in TR)))
print("  non-S traded: %d of %d (%.2f%%)"
      % (sum(1 for r in TR if r["sgrade"] != "S"), len(TR),
         100.0*sum(1 for r in TR if r["sgrade"] != "S")/len(TR)))
print("  traded rate by sgrade:",
      {g: "%d/%d" % (sum(1 for r in T if r["sgrade"] == g and r["traded"]),
                     sum(1 for r in T if r["sgrade"] == g)) for g in ("S", "A", "C")})
