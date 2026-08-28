#!/usr/bin/env python3
"""X12: is 2.0R reachable as a MEAN with a fixed target? And what R:R does the
engine actually plan at entry vs realize at exit?

Substrate: research/g3_arm_ow1.json. Read-only.
"""
import json, os, sys, collections, statistics
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "research", "g3_arm_ow1.json"), encoding="utf-8"))
tr = [t for t in d["trades"] if t.get("traded")]
n = len(tr)

print("--- 1. THE ARITHMETIC: fixed target T, 1R stop, win rate p -> mean R = pT-(1-p)")
print("    win rate needed for mean R = 2.0 at each fixed target")
for T in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0):
    p = 3.0 / (T + 1.0)          # solve pT-(1-p)=2
    tag = "IMPOSSIBLE" if p > 1.0 else ""
    print("    target %.1fR -> need p = %6.1f%%  %s" % (T, 100 * p, tag))
print("    and at Austin's own >=55%% WR floor, a fixed target T yields mean R = 0.55T-0.45:")
for T in (2.0, 3.0, 4.0, 5.0):
    print("        T=%.0fR -> mean %+0.2fR" % (T, 0.55 * T - 0.45))
print()

print("--- 2. WHAT THE ENGINE PLANS AT ENTRY (target R:R from entry/stop/target) ---")
rr = []
for t in tr:
    risk = abs(t["entry"] - t["stop"])
    rew = abs(t["target"] - t["entry"])
    if risk > 0:
        rr.append(rew / risk)
print("    n=%d  mean planned R:R %.3f   median %.3f   p10 %.3f  p90 %.3f"
      % (len(rr), sum(rr) / len(rr), statistics.median(rr),
         sorted(rr)[len(rr) // 10], sorted(rr)[9 * len(rr) // 10]))
b = collections.Counter()
for x in rr:
    b["<1R" if x < 1 else "1-2R" if x < 2 else "2-3R" if x < 3 else ">=3R"] += 1
for k in ("<1R", "1-2R", "2-3R", ">=3R"):
    print("      planned %-5s %4d  %5.1f%%" % (k, b[k], 100.0 * b[k] / len(rr)))
print()

print("--- 3. WHAT IT REALIZES (r distribution) ---")
rs = sorted(t["r"] for t in tr)
buckets = [(-99, -0.999), (-0.999, 0), (0, 1), (1, 2), (2, 3), (3, 5), (5, 10), (10, 99)]
for lo, hi in buckets:
    c = sum(1 for x in rs if lo < x <= hi)
    print("      %6.1f < r <= %5.1f : %4d  %5.1f%%   sum %+8.1fR"
          % (lo, hi, c, 100.0 * c / n, sum(x for x in rs if lo < x <= hi)))
print("    trades >= +2R: %d (%.1f%%)   >= +4R: %d (%.1f%%)"
      % (sum(1 for x in rs if x >= 2), 100.0 * sum(1 for x in rs if x >= 2) / n,
         sum(1 for x in rs if x >= 4), 100.0 * sum(1 for x in rs if x >= 4) / n))
print()

print("--- 4. WHAT AVG WIN IS REQUIRED FOR MEAN R = 2.0 AT THE BOOK'S OWN WIN RATE ---")
w = [t["r"] for t in tr if t["r"] > 0]
l = [t["r"] for t in tr if t["r"] <= 0]
p = len(w) / n
print("    p = %.4f, avg loss = %+0.4fR, avg win today = %+0.4fR (ratio %.2f)"
      % (p, sum(l) / len(l), sum(w) / len(w), abs((sum(w) / len(w)) / (sum(l) / len(l)))))
need = (2.0 - (1 - p) * (sum(l) / len(l))) / p
print("    avg win needed for mean 2.0R = %+0.3fR  -> win/loss ratio %.2f (today %.2f)"
      % (need, need / abs(sum(l) / len(l)), abs((sum(w) / len(w)) / (sum(l) / len(l)))))
for pp in (0.55, 0.60, 0.65, 0.70, 0.80):
    print("      if WR were %.0f%%: avg win needed = %+0.2fR" % (100 * pp, (2.0 - (1 - pp) * -1.0) / pp))
