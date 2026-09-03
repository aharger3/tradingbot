"""G7.1 adversarial verify of track `levels`. Re-derives the six_target claim
off my own re-run books (research/_v/) and stress-tests the error bar.

Attacks:
  A. paired dR with a DAY-CLUSTERED bootstrap (trades on one session are not
     independent -- same halt state, same tape).
  B. durability: which months flip green->red and by how much.
  C. reachability of the six branch, off the probe rows.
  D. look-ahead: ORH/ORL are only known at 09:35; count entries before that
     whose six target IS the OR level.
"""
from __future__ import annotations
import json, math, random, statistics as st, sys
from collections import defaultdict

BASE, ARM = sys.argv[1], sys.argv[2]
PB, PA = sys.argv[3], sys.argv[4]


def load(p):
    d = json.load(open(p, encoding="utf-8"))
    return [t for t in d["trades"] if t["traded"]]


def key(t):
    return (t["sym"], t["day"], t["et"], t["setup"], t["dir"], t["entry"], t["stop"])


b, a = load(BASE), load(ARM)
bm, am = {key(t): t for t in b}, {key(t): t for t in a}
shared = sorted(set(bm) & set(am))
print("shared=%d base-only=%d arm-only=%d" % (len(shared), len(bm) - len(shared),
                                              len(am) - len(shared)))

# ---- A. naive paired vs day-clustered
diffs = [am[k]["r"] - bm[k]["r"] for k in shared]
moved = sum(1 for d in diffs if abs(d) > 1e-9)
mean = st.fmean(diffs)
se_naive = st.pstdev(diffs) / math.sqrt(len(diffs))
print("paired dR=%+.4f  moved=%d  naive 95%%=+/-%.4f  -> [%+.4f,%+.4f]"
      % (mean, moved, 1.96 * se_naive, mean - 1.96 * se_naive, mean + 1.96 * se_naive))

byday = defaultdict(list)
for k, d in zip(shared, diffs):
    byday[k[1]].append(d)
days = list(byday)
# cluster-robust SE: sum of day totals / N
N = len(diffs)
day_tot = [sum(v) - mean * len(v) for v in byday.values()]
se_cl = math.sqrt(sum(x * x for x in day_tot)) / N
print("day-clustered 95%%=+/-%.4f  -> [%+.4f,%+.4f]  (days=%d)"
      % (1.96 * se_cl, mean - 1.96 * se_cl, mean + 1.96 * se_cl, len(days)))

random.seed(7)
boot = []
for _ in range(4000):
    s = t = 0.0
    n = 0
    for _ in range(len(days)):
        v = byday[random.choice(days)]
        s += sum(v); n += len(v)
    boot.append(s / n)
boot.sort()
print("day-block bootstrap 95%% CI = [%+.4f, %+.4f]  P(dR>=0)=%.4f"
      % (boot[100], boot[3899], sum(1 for x in boot if x >= 0) / len(boot)))

# also unpaired mean-R gap on the full books
print("unpaired meanR: base=%+.4f arm=%+.4f gap=%+.4f"
      % (st.fmean([t["r"] for t in b]), st.fmean([t["r"] for t in a]),
         st.fmean([t["r"] for t in a]) - st.fmean([t["r"] for t in b])))

# ---- B. durability
mb, ma = defaultdict(float), defaultdict(float)
for t in b: mb[t["ym"]] += t["r"]
for t in a: ma[t["ym"]] += t["r"]
print("\nmonths that flip:")
for ym in sorted(set(mb) | set(ma)):
    if (mb[ym] > 0) != (ma[ym] > 0):
        print("  %s base=%+8.2fR arm=%+8.2fR  (n_base=%d)"
              % (ym, mb[ym], ma[ym], sum(1 for t in b if t["ym"] == ym)))
neg = sorted((v, k) for k, v in ma.items() if v <= 0)
print("  arm reds: %s" % ["%s %+.2fR" % (k, v) for v, k in neg])
thin = sorted((v, k) for k, v in mb.items())[:4]
print("  base thinnest greens: %s" % ["%s %+.2fR" % (k, v) for v, k in thin])

# ---- C/D. probe
pb = json.load(open(PB, encoding="utf-8"))
pa = json.load(open(PA, encoding="utf-8"))
print("\nprobe rows base=%d arm=%d" % (len(pb), len(pa)))
n = len(pb)
none6 = sum(1 for r in pb if r["six_is_none"])
whole = sum(1 for r in pb if r["shipped_is_whole"])
same = sum(1 for r in pb if (not r["six_is_none"]) and abs(r["six"] - r["shipped"]) < 1e-9)
print("scale-armed rows: %d  six_is_none=%d (%.1f%%)  shipped==whole$=%d (%.1f%%)  six==shipped=%d (%.1f%%)"
      % (n, none6, none6 / n * 100, whole, whole / n * 100, same, same / n * 100))
rr_s = [r["rr_shipped"] for r in pb if r["rr_shipped"] is not None]
rr_6 = [r["rr_six"] for r in pb if r["rr_six"] is not None]
print("median RR shipped=%.2f  six=%.2f" % (st.median(rr_s), st.median(rr_6)))

# D: look-ahead -- OR levels only known at 09:35
early = [r for r in pb if r["et"] < "09:35"]
print("\nrows with entry < 09:35: %d" % len(early))
