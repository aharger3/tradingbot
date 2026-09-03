"""G7.1 / `firsts` addendum: is the FIRST signal of the day actually special?

P1 (first-only) reads +0.6115R at 54.86%. The day's average candidate reads
+0.5110R at 47.19%. This asks whether that gap survives its own error bar,
paired day by day (each day contributes first_R - mean_of_that_day's_R), and
splits win rate from win SIZE.

Reads research/bt2y_trades.json only. Writes nothing.
"""
import json, statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
book = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
counted = [r for r in book["trades"]
           if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
by_day = defaultdict(list)
for r in counted:
    by_day[r["day"]].append(r)
for d in by_day:
    by_day[d].sort(key=lambda r: (r["entry_i"], r["et"], r["sym"]))

firsts = [rs[0] for rs in by_day.values()]
rest = [x for rs in by_day.values() for x in rs[1:]]

diffs = [rs[0]["r"] - statistics.fmean(x["r"] for x in rs)
         for rs in by_day.values() if len(rs) > 1]
m = statistics.fmean(diffs)
se = statistics.pstdev(diffs) / len(diffs) ** 0.5
print("paired first - day-mean:  n=%d  mean %+0.4fR  se %0.4f  t %+0.2f  %s"
      % (len(diffs), m, se, m / se, "SIGNIFICANT" if abs(m) > 2 * se else "inside the bar"))


def split(rows, label):
    w = [r["r"] for r in rows if r["out"] == "win"]
    l = [r["r"] for r in rows if r["out"] == "loss"]
    dec = len(w) + len(l)
    wr = len(w) / dec
    print("%-8s n=%4d  WR %5.2f%% (+-%.2fpp)  mean winner %+0.3fR  mean loser %+0.3fR  "
          "mean R %+0.4f" % (label, len(rows), wr * 100,
                             (wr * (1 - wr) / dec) ** 0.5 * 100,
                             statistics.fmean(w), statistics.fmean(l),
                             statistics.fmean(r["r"] for r in rows)))


split(firsts, "first")
split(rest, "rest")
split(counted, "all")

# how often does the day's first trade decide the day under P2 / P3?
w1 = sum(1 for rs in by_day.values() if rs[0]["out"] == "win")
print("\nday ends on trade #1 (first is a win): %d/%d = %.1f%%"
      % (w1, len(by_day), w1 / len(by_day) * 100))
print("days with >1 counted candidate: %d/%d"
      % (sum(1 for rs in by_day.values() if len(rs) > 1), len(by_day)))

# sgrade S: is it anti-predictive, and by how much, with a bar?
for g in ("S", "A", "C"):
    v = [r["r"] for r in counted if r["sgrade"] == g]
    print("sgrade %s  n=%4d  mean %+0.4fR  se %0.4f" % (g, len(v), statistics.fmean(v),
                                                        statistics.pstdev(v) / len(v) ** 0.5))
s = [r["r"] for r in counted if r["sgrade"] == "S"]
ns = [r["r"] for r in counted if r["sgrade"] != "S"]
d = statistics.fmean(s) - statistics.fmean(ns)
sed = (statistics.pvariance(s) / len(s) + statistics.pvariance(ns) / len(ns)) ** 0.5
print("S minus non-S: %+0.4fR  se %0.4f  t %+0.2f  %s"
      % (d, sed, d / sed, "SIGNIFICANT" if abs(d) > 2 * sed else "inside the bar"))
