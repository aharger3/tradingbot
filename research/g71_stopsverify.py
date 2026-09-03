"""G71 adversarial verify of track `stops` (research/g71_stops.md) claim 3.

CLAIM UNDER TEST
    S4 "best RR tradable", implemented literally, is arithmetically a
    stop-TIGHTENING rule and is the WORST arm measured.

Reads only the arm books the `stops` track already wrote
(research/_g71s_*.json). Edits nothing, reimplements no fill.

    python research/g71_stopsverify.py
"""
from __future__ import annotations
import json, math, os, statistics, sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

ARMS = ["S0_shipped", "S1_level", "S2_candle", "S3_pivot", "S4_bestrr",
        "D_off", "D_075", "D_125", "D_150", "D_200"]


def load(a):
    with open(os.path.join(HERE, "_g71s_%s.json" % a)) as f:
        return json.load(f)["trades"]


def key(r):
    return (r["sym"], r["day"], r["et"], r["setup"], r["dir"])


def iso_week(d):
    y, w, _ = date.fromisoformat(d).isocalendar()
    return "%d-W%02d" % (y, w)


def dd(rs):
    peak = cum = worst = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        worst = min(worst, cum - peak)
    return worst


def stats(x):
    se = statistics.stdev(x) / math.sqrt(len(x))
    return statistics.fmean(x), se, statistics.fmean(x) / se


def table():
    print("\n== A. arm books, recomputed from the arm JSONs ==")
    for a in ARMS[:5]:
        tr = sorted((r for r in load(a) if r["traded"]),
                    key=lambda r: (r["day"], r["et"]))
        rs = [r["r"] for r in tr]
        dist = [abs(r["entry"] - r["stop"]) for r in tr]
        z = sum(1 for d in dist if d == 0.0)
        bym, byw = defaultdict(float), defaultdict(float)
        for r in tr:
            bym[r["ym"]] += r["r"]
            byw[iso_week(r["day"])] += r["r"]
        print("%-11s n=%5d meanR=%+.4f cap10=%+.4f mo=%d/%d wk=%d/%d dd=%.1fR "
              "zero=%d(%.2f%%) stop$=%.3f" % (
                  a, len(tr), statistics.fmean(rs),
                  statistics.fmean([min(r, 10.0) for r in rs]),
                  sum(1 for v in bym.values() if v > 0), len(bym),
                  sum(1 for v in byw.values() if v > 0), len(byw),
                  dd(rs), z, z / len(tr) * 100, statistics.fmean(dist)))


def paired():
    print("\n== B. paired vs S0_shipped, capped at +10R ==")
    base = {key(r): r for r in load("S0_shipped") if r["traded"]}
    for a in ARMS[1:]:
        dc = [min(r["r"], 10.0) - min(base[key(r)]["r"], 10.0)
              for r in load(a) if r["traded"] and key(r) in base]
        m, se, t = stats(dc)
        print("%-11s n=%5d d=%+.4f SE=%.4f t=%+.2f" % (a, len(dc), m, se, t))


def decompose():
    """THE FINDING: split S4's paired delta by whether the row is a real
    trade (|entry-stop|>0) or a harness artefact (risk==0 -> the `if risk > 0`
    guards in backtest_week never manage the position, it books r=0.0 and
    out='open')."""
    print("\n== C. S4_bestrr paired delta, split by risk==0 ==")
    base = {key(r): r for r in load("S0_shipped") if r["traded"]}
    z, nz = [], []
    for r in load("S4_bestrr"):
        if not r["traded"] or key(r) not in base:
            continue
        d = min(r["r"], 10.0) - min(base[key(r)]["r"], 10.0)
        (z if abs(r["entry"] - r["stop"]) == 0.0 else nz).append(d)
    for lab, x in (("ALL", z + nz), ("risk==0 artefact", z), ("risk>0 real", nz)):
        m, se, t = stats(x)
        print("%-18s n=%5d d=%+.4f SE=%.4f t=%+.2f" % (lab, len(x), m, se, t))
    print("share of the total delta carried by the artefact rows: %.1f%%"
          % (sum(z) / sum(z + nz) * 100))
    zr = [r for r in load("S4_bestrr")
          if r["traded"] and abs(r["entry"] - r["stop"]) == 0.0]
    from collections import Counter
    print("artefact rows by setup:", Counter(r["setup"] for r in zr).most_common())
    print("artefact rows by outcome:", Counter(r["out"] for r in zr).most_common())


def target_is_inert():
    """The selector never consults the target: num cancels out of the argmax."""
    print("\n== D. does `_nearest_target` change any pick? ==")
    import g71_stops as g

    class C:
        close, low, high = 100.0, 99.0, 101.0

    class R:
        candles, _active_levels, _pivot_prices = [], [105.0], []

    g._pivot_stop = lambda runner, candle, is_long: 98.0
    picks = []
    for tgt in (105.0, 1000.0, 100.5, None):
        g._nearest_target = lambda runner, candle, is_long, _t=tgt: _t
        picks.append(g._best_rr(R(), C(), True, level_stop=99.5,
                                structural_stop=97.0))
    print("candidates {level 99.50, candle 99.00, pivot 98.00}, close 100.00")
    print("picks for targets 105 / 1000 / 100.5 / None:", picks)
    print("IDENTICAL -> the target is arithmetically inert; the arm is "
          "'tightest tradable stop vs the bar CLOSE', not 'best RR'.")


def rr_universality():
    print("\n== E. is every executed RR exactly 2.00? ==")
    tr = [r for r in load("S0_shipped") if r["traded"]]
    n2 = sum(1 for r in tr
             if abs(r["entry"] - r["stop"]) > 0
             and abs(abs(r["target"] - r["entry"]) / abs(r["entry"] - r["stop"]) - 2.0) < 1e-6)
    print("traded=%d  RR==2.00: %d  RR!=2.00: %d (%.1f%%)"
          % (len(tr), n2, len(tr) - n2, (len(tr) - n2) / len(tr) * 100))


if __name__ == "__main__":
    table(); paired(); decompose(); target_is_inert(); rr_universality()
