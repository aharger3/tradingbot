"""t11_rescore.py -- the 2-year book before and after the stop-fill fix.

Reads two `backtest_2y.py` books and prints the money gate, durability, max
drawdown and the left tail for each:

    BEFORE  research/g3_arm_ow1.json          fill at `t.stop`  (commit c089b26b)
    AFTER   research/t11_arm_ow1_closefill.json  fill at the triggering close,
                                                 floored at -1.25R

Both are `ON_WATCH=1`, `--days 730`, the shipped arm, replayed off `data_archive/`
with zero fetches. Same engine, same detection, same 45,193 signals and 1,017
traded rows -- the ONLY thing that moved is the price a stop-out books.

The load-bearing number is `floor_binds`: how many rows the -1.25R floor actually
CLAMPS. Before the fix it is 0 of 45,193, because filling at `t.stop` makes the
floor unreachable (research/x2_stop_floor_audit.md). If it is still 0 after, the
fix did not land.

Run:

    python research/t11_rescore.py
    python research/t11_rescore.py --json research/_t11_rescore.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from stop_rule import MAX_LOSS_R                                  # noqa: E402

BEFORE = os.path.join(HERE, "g3_arm_ow1.json")
AFTER = os.path.join(HERE, "t11_arm_ow1_closefill.json")
EPS = 1e-9


def load(path):
    with open(path, encoding="utf-8") as fh:
        blob = json.load(fh)
    for key in ("trades", "rows"):
        if isinstance(blob, dict) and key in blob:
            return blob[key]
    rows = blob
    return rows


def maxdd(rs):
    """Max drawdown of the 1R-per-trade equity curve, in R, and its length."""
    peak = eq = 0.0
    worst = 0.0
    run = best_run = 0
    for r in rs:
        eq += r
        if eq >= peak - EPS:
            peak, run = eq, 0
        else:
            run += 1
            if peak - eq > worst:
                worst, best_run = peak - eq, run
    return worst, best_run


def longest_losing_streak(rs):
    cur = best = 0
    for r in rs:
        cur = cur + 1 if r < 0 else 0
        best = max(best, cur)
    return best


def stats(rows, label):
    traded = [r for r in rows if r.get("traded")]
    traded.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
    rs = [r["r"] for r in traded]
    n = len(rs)
    wins = sum(1 for r in traded if r["out"] == "win")

    months = {}
    for r in traded:
        months.setdefault(r["ym"], []).append(r["r"])
    green = sum(1 for v in months.values() if sum(v) > 0)

    dd, dd_len = maxdd(rs)

    # Rows the -1.25R FLOOR actually clamps, read off the book's own `r` column
    # and NOT off the prices beside it. Two reasons, both measured:
    #   * a price-space test (`exit == entry -/+ 1.25*risk`) has to carry a
    #     tolerance, because a book stores entry/stop/exit at 2 dp -- and with a
    #     20-cent stop that tolerance manufactures false positives. It claimed
    #     5,354 clamped rows in the BEFORE book, where the floor is provably
    #     unreachable, i.e. it was wrong 5,354 times out of 5,354.
    #   * tightening the tolerance then UNDER-counts: NVDA 2024-09-26 clamps at
    #     126.605, stores 126.61, and recomputes to -1.2333R. 303 real clamps
    #     read as 65.
    # `r` comes from `t.pnl` at full precision, so a clamped row is -1.250 flat
    # and an unclamped one is a bar's close, which lands there only by
    # coincidence. Scaled rows are excluded: their `r` blends two legs.
    binds = [r for r in rows
             if r["out"] == "loss" and not r.get("scaled")
             and abs(r["r"] + MAX_LOSS_R) < 5e-4]
    binds_traded = [r for r in binds if r.get("traded")]

    allr = [r["r"] for r in rows if r.get("traded")]
    return {
        "label": label,
        "n_signals": len(rows),
        "n_traded": n,
        "mean_r": sum(rs) / n if n else 0.0,
        "total_r": sum(rs),
        "win_rate": 100.0 * wins / n if n else 0.0,
        "n_win": wins,
        "n_loss": sum(1 for r in traded if r["out"] == "loss"),
        "n_scratch": sum(1 for r in traded if r["out"] == "scratch"),
        "months_green": green,
        "months": len(months),
        "max_dd": dd,
        "max_dd_trades": dd_len,
        "streak": longest_losing_streak(rs),
        "min_r": min(rs) if rs else 0.0,
        "n_worse_than_1r": sum(1 for r in allr if r < -1.0 - 1e-6),
        "n_worse_than_125r": sum(1 for r in allr if r < -MAX_LOSS_R - 1e-6),
        "n_exactly_1r": sum(1 for r in allr if abs(r + 1.0) < 1e-6),
        "floor_binds": len(binds),
        "floor_binds_traded": len(binds_traded),
        "distinct_neg": sorted({round(r, 3) for r in allr if r < 0})[:6],
        "n_distinct_neg": len({round(r, 3) for r in allr if r < 0}),
    }


ROWSPEC = [
    ("signals", "n_signals", "%d"),
    ("traded rows", "n_traded", "%d"),
    ("mean R", "mean_r", "%+.4f"),
    ("total R", "total_r", "%+.2f"),
    ("win rate", "win_rate", "%.1f%%"),
    ("win / loss / scratch", None, None),
    ("months green", None, None),
    ("max drawdown (R)", "max_dd", "%.2f"),
    ("  over N trades", "max_dd_trades", "%d"),
    ("longest losing streak", "streak", "%d"),
    ("min R", "min_r", "%+.4f"),
    ("rows worse than -1.0R", "n_worse_than_1r", "%d"),
    ("rows worse than -1.25R", "n_worse_than_125r", "%d"),
    ("rows at exactly -1.000R", "n_exactly_1r", "%d"),
    ("distinct negative R values", "n_distinct_neg", "%d"),
    ("**rows the -1.25R floor CLAMPS**", "floor_binds", "%d"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", default=BEFORE)
    ap.add_argument("--after", default=AFTER)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    b = stats(load(a.before), "before (fill at t.stop)")
    c = stats(load(a.after), "after (close fill, -1.25R floor)")

    w = 34
    print("%-*s  %18s  %18s  %12s" % (w, "", "BEFORE", "AFTER", "delta"))
    print("%-*s  %18s  %18s  %12s" % (w, "", os.path.basename(a.before),
                                      os.path.basename(a.after), ""))
    print("-" * (w + 56))
    for name, key, fmt in ROWSPEC:
        if key is None:
            if name.startswith("win /"):
                lhs = "%d / %d / %d" % (b["n_win"], b["n_loss"], b["n_scratch"])
                rhs = "%d / %d / %d" % (c["n_win"], c["n_loss"], c["n_scratch"])
            else:
                lhs = "%d / %d" % (b["months_green"], b["months"])
                rhs = "%d / %d" % (c["months_green"], c["months"])
            print("%-*s  %18s  %18s" % (w, name, lhs, rhs))
            continue
        d = c[key] - b[key]
        dfmt = ("%+.4f" if "f" in fmt and ".4" in fmt else
                "%+.2f" if "f" in fmt else "%+d")
        print("%-*s  %18s  %18s  %12s"
              % (w, name, fmt % b[key], fmt % c[key], dfmt % d))

    print()
    print("X2's prediction (research/x2_stop_floor_audit.md), and this rerun:")
    print("  book mean R   predicted %+.4f -> %+.4f (%+.4f) | measured %+.4f -> "
          "%+.4f (%+.4f)" % (0.9551, 0.8644, -0.0907,
                             b["mean_r"], c["mean_r"], c["mean_r"] - b["mean_r"]))
    print("  max DD        predicted %.2f R -> %.2f R          | measured %.2f R -> "
          "%.2f R" % (11.44, 14.49, b["max_dd"], c["max_dd"]))
    print("  months green  predicted 23/25 -> 23/25            | measured %d/%d -> "
          "%d/%d" % (b["months_green"], b["months"], c["months_green"], c["months"]))
    print()
    if c["floor_binds"] == 0:
        print("FLOOR STILL BINDS ON NOTHING -- the fix did not land.")
        return 1
    print("the -1.25R floor clamps %d rows (%d of them traded); before the fix it "
          "clamped 0 of %d." % (c["floor_binds"], c["floor_binds_traded"],
                                b["n_signals"]))

    # ---- attribution: why the measured delta is bigger than X2's estimate ----
    rb = {(r["sym"], r["day"], r["et"], r["side"]): r for r in load(a.before)
          if r.get("traded")}
    ra = {(r["sym"], r["day"], r["et"], r["side"]): r for r in load(a.after)
          if r.get("traded")}
    keys = set(rb) & set(ra)
    print("matched traded rows: %d of %d before / %d after"
          % (len(keys), len(rb), len(ra)))
    buckets = {}
    for k in keys:
        d = ra[k]["r"] - rb[k]["r"]
        if abs(d) < 1e-9:
            continue
        was_full_stop = (rb[k]["out"] == "loss" and not rb[k].get("scaled"))
        if was_full_stop and ra[k]["out"] == "loss":
            name = "X2's matched set: full stop-outs repriced at their close"
        elif rb[k].get("scaled") or ra[k].get("scaled"):
            name = "scaled rows: the runner leg now books a real loss"
        else:
            name = "outcome changed (a row that used to end differently)"
        b2 = buckets.setdefault(name, [0, 0.0])
        b2[0] += 1
        b2[1] += d
    print("%-58s %6s %10s" % ("total R moved by", "rows", "sum R"))
    for name, (n_, tot) in sorted(buckets.items(), key=lambda kv: kv[1][1]):
        print("%-58s %6d %+10.2f" % (name, n_, tot))
    print("%-58s %6d %+10.2f" % ("TOTAL", sum(v[0] for v in buckets.values()),
                                 sum(v[1] for v in buckets.values())))
    print()

    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"before": b, "after": c}, fh, indent=1)
        print("wrote %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
