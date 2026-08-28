#!/usr/bin/env python3
"""X12: Scarface takes ~1 trade a day and skips more days than he trades. OMEN takes
2.45. Measure what selectivity alone does to the book -- no new money, no scale-in.

Substrate: research/g3_arm_ow1.json. Read-only.
"""
import json, os, sys, collections, datetime, statistics
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
d = json.load(open(os.path.join(ROOT, "research", "g3_arm_ow1.json"), encoding="utf-8"))
tr = [t for t in d["trades"] if t.get("traded")]
SESS = d["meta"]["sessions"]

byday = collections.defaultdict(list)
for t in tr:
    byday[t["day"]].append(t)
for k in byday:
    byday[k].sort(key=lambda t: (t["et"], t.get("seq", 0)))

print("traded days %d of %d sessions   trades/traded-day %.2f   trades/session %.2f"
      % (len(byday), SESS, len(tr) / len(byday), len(tr) / SESS))
cnt = collections.Counter(len(v) for v in byday.values())
print("trades per traded day:", dict(sorted(cnt.items())))
print()


def iso_week(day):
    y, m, dd = (int(x) for x in day.split("-"))
    iy, iw, _ = datetime.date(y, m, dd).isocalendar()
    return "%04d-W%02d" % (iy, iw)


def report(name, rows):
    if not rows:
        print("%-34s EMPTY" % name)
        return
    n = len(rows)
    rs = [t["r"] for t in rows]
    w = sum(1 for x in rs if x > 0)
    wk = collections.defaultdict(float)
    dy = collections.defaultdict(float)
    mo = collections.defaultdict(float)
    for t in rows:
        wk[iso_week(t["day"])] += t["r"]
        dy[t["day"]] += t["r"]
        mo[t["day"][:7]] += t["r"]
    gw = sum(1 for v in wk.values() if v > 0)
    gd = sum(1 for v in dy.values() if v > 0)
    gm = sum(1 for v in mo.values() if v > 0)
    print("%-34s n=%4d  WR %5.1f%%  meanR %+0.4f  total %+7.1fR | "
          "green wk %3d/%3d (%.0f%%)  green day %3d/%3d (%.0f%%)  green mo %2d/%2d"
          % (name, n, 100.0 * w / n, sum(rs) / n, sum(rs),
             gw, len(wk), 100.0 * gw / len(wk),
             gd, len(dy), 100.0 * gd / len(dy), gm, len(mo)))


print("--- ARMS: pure selectivity on the SAME book, flat 1R risk, no new money ---")
report("A0 shipped (all trades)", tr)
report("A1 first trade of the day only", [v[0] for v in byday.values()])
report("A2 first TWO trades of the day", [t for v in byday.values() for t in v[:2]])
report("A3 sgrade S or A only", [t for t in tr if t.get("sgrade") in ("S", "A")])
report("A4 sgrade S only", [t for t in tr if t.get("sgrade") == "S"])
report("A5 first-of-day AND sgrade S/A",
       [v[0] for v in byday.values() if v[0].get("sgrade") in ("S", "A")])
report("A6 09:30 slot only", [t for t in tr if t["et"] < "10:00"])
report("A7 aligned with SPY trend", [t for t in tr if t.get("aligned") == "yes"])
print()
print("(error bar on an A/B of this book: +/-0.0095R -- but these arms change n, so the")
print(" bar on a SUBSET mean is wider: sd/sqrt(n) is printed below for each arm)")
for name, rows in [("A0 all", tr),
                   ("A1 first-of-day", [v[0] for v in byday.values()]),
                   ("A3 S or A", [t for t in tr if t.get("sgrade") in ("S", "A")]),
                   ("A4 S only", [t for t in tr if t.get("sgrade") == "S"])]:
    rs = [t["r"] for t in rows]
    se = statistics.stdev(rs) / (len(rs) ** 0.5)
    print("   %-18s n=%4d  meanR %+0.4f  se %.4f  95%% CI [%+0.3f, %+0.3f]"
          % (name, len(rs), sum(rs) / len(rs), se,
             sum(rs) / len(rs) - 1.96 * se, sum(rs) / len(rs) + 1.96 * se))


# ---------------------------------------------------------------------------
# Scarface's own stated day-management rules, applied to the same book.
#   "I'm able to take three trades maximum per day."
#   "75 to 80% of the time... I'll only be taking one trade a day."
#   "if I lose two trades in a row, call it quits... on that day."
#       -- research/scarface-rules-videos.md:8861-8863
# ---------------------------------------------------------------------------
print()
print("--- SCARFACE'S OWN DAY RULES, applied to the same book ---")


def cap_n(v, k):
    return v[:k]


def two_loss_stop(v):
    out, streak = [], 0
    for t in v:
        out.append(t)
        streak = streak + 1 if t["r"] <= 0 else 0
        if streak >= 2:
            break
    return out


report("S1 max 3 trades/day", [t for v in byday.values() for t in cap_n(v, 3)])
report("S2 two-losses-in-a-row -> done for day",
       [t for v in byday.values() for t in two_loss_stop(v)])
report("S3 max 3/day AND two-loss stop",
       [t for v in byday.values() for t in cap_n(two_loss_stop(v), 3)])
report("S4 one trade/day AND two-loss stop",
       [t for v in byday.values() for t in cap_n(two_loss_stop(v), 1)])
print()
print("trades per week: OMEN %.1f  |  Scarface stated ~1/day, 3 max, and he posts"
      % (len(tr) / 105.0))
print("  145 explicit no-trade/skip messages against 144 trailer messages.")
