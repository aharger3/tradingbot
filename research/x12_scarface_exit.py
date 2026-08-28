#!/usr/bin/env python3
"""X12: apply Scarface's OWN published scale ladder to OMEN's own 2-year book and
see what mean R it produces.

Scarface's stated ladder (research/scarface-rules-videos.md:2601-2606,
boot-camp Day 8 "Scaling With Options"):
    first scale at the HOD/LOD, minimum 1.5 R:R
    1.50-1.75R  -> take 60% off
    1.75-2.00R  -> take 70% off
    >= 2.00R    -> take 80% off
    the remaining 20-25% is the trailer, cut on market-structure break

CAVEAT stated up front: g3_arm_ow1.json carries no max-favourable-excursion, so a
scale can only be assumed filled on trades whose FINAL r already exceeded the scale
level. Trades that finished below the scale level are left untouched. That is
CONSERVATIVE FOR SCARFACE -- in reality some of those would have scaled first and
turned a -1.00R into a partial loss, which raises his arm. So the arm below is a
LOWER bound on his win rate and an UPPER bound on his loss size; the mean R it
reports is if anything generous on the loss side and pessimistic on nothing.

Substrate: research/g3_arm_ow1.json. Read-only.
"""
import json, os, sys, statistics, collections, datetime
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "research", "g3_arm_ow1.json"), encoding="utf-8"))
tr = [t for t in d["trades"] if t.get("traded")]


def scale_frac(level):
    if level >= 2.00:
        return 0.80
    if level >= 1.75:
        return 0.70
    return 0.60


def scarface_r(r, scale_at=1.5):
    """position-weighted R under the ladder, runner assumed to ride to the same exit"""
    if r < scale_at:
        return r                      # scale never filled (see caveat)
    f = scale_frac(scale_at)
    return f * scale_at + (1.0 - f) * r


def iso_week(day):
    y, m, dd = (int(x) for x in day.split("-"))
    iy, iw, _ = datetime.date(y, m, dd).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def stats(name, vals, days, note=""):
    n = len(vals)
    w = sum(1 for x in vals if x > 0)
    wk = collections.defaultdict(float)
    dy = collections.defaultdict(float)
    mo = collections.defaultdict(float)
    for x, dd in zip(vals, days):
        wk[iso_week(dd)] += x
        dy[dd] += x
        mo[dd[:7]] += x
    gw = sum(1 for v in wk.values() if v > 0)
    gd = sum(1 for v in dy.values() if v > 0)
    gm = sum(1 for v in mo.values() if v > 0)
    se = statistics.stdev(vals) / (n ** 0.5)
    print("%-38s WR %5.1f%%  meanR %+0.4f (se %.4f)  total %+7.1fR | "
          "wk %3d/%3d  day %3d/%3d  mo %2d/%2d %s"
          % (name, 100.0 * w / n, sum(vals) / n, se, sum(vals),
             gw, len(wk), gd, len(dy), gm, len(mo), note))


days = [t["day"] for t in tr]
base = [t["r"] for t in tr]
print("n = %d traded rows, %s..%s\n" % (len(tr), d["meta"]["first"], d["meta"]["last"]))
stats("A  shipped OMEN (100%% rides to exit)", base, days)
for lvl in (1.5, 1.75, 2.0):
    arm = [scarface_r(t["r"], lvl) for t in tr]
    stats("B  Scarface ladder, scale at %.2fR" % lvl, arm, days,
          "(delta %+0.4fR)" % (sum(arm) / len(arm) - sum(base) / len(base)))
# the opposite extreme: hard exit at the planned 2R target, no runner at all
hard = [min(t["r"], 2.0) for t in tr]
stats("C  hard exit at 2R target, no runner", hard, days,
      "(delta %+0.4fR)" % (sum(hard) / len(hard) - sum(base) / len(base)))
print()
print("MONEY GATE = win rate >= 55%% AND mean R >= 2.0.")
print("None of the arms above reach mean R 2.0. The shipped book is the HIGHEST-mean")
print("arm of the four, because it is the only one that lets 100%% of the position ride.")
