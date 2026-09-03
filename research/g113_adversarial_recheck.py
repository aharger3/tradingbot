"""g113_adversarial_recheck -- refute research/g113_ladder_shapes_sweep.py.

Independent recompute of the ladder_shapes sweep. Nothing here trusts g113's
bar-walk: `my_walk` is a from-scratch implementation of the documented exit
rules (level stop on intrabar touch before any scale-out; a bar that touches
both a rung and the stop goes to the STOP; break-even stop on the CLOSE after
the first fill, filled at that close clamped to -1.25R; leftover exits at the
11:00 close) written against the prose, not against g101.walk_ladder. It is
diffed row by row against g101's fill.

What it adds beyond reproduction:
  1. RUNG-COUNT AUDIT. build_rungs truncates the WEIGHT LIST when fewer rungs
     survive (`weights[:len(kept)]`, renormalised). Only 50 of 444 rows carry
     4 rungs, so "30/30/30/10", "25/25/25/25" and "20/20/20/40" collapse to
     the same 1/3-1/3-1/3 on every 3-rung row. Measured: identical on 411/444.
  2. DURABILITY. Split-half and calendar-year EV/R.
  3. START-DATE ROBUSTNESS of the prop evaluation. g113 evaluates ONE
     chronological path per (shape, size) cell; this rolls the start date and
     shows the pass/fail is a regime artifact, not a property of the shape.
  4. PAIRED PERMUTATION on the shape differences (same 444 rows, so pair them).
  5. R1 CHECK. min R per arm; nothing may book worse than -1.000R.

    python research/g113_adversarial_recheck.py
"""
from __future__ import annotations

import json
import os
import random
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g97_mfe as g97                             # noqa: E402
import g101_open_and_ladder as g101               # noqa: E402
import signal_runner as sr                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402
import omen_metrics as om                         # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT = os.path.join(HERE, "g113_adversarial_recheck.json")
WIN_END = "11:00:00"

SHAPES = {
    "one_target":      ((1.0,), 0.0),
    "50/50":           ((.50, .50), 0.0),
    "30/30/30/10":     ((.30, .30, .30, .10), 0.0),
    "50/20/20/10":     ((.50, .20, .20, .10), 0.0),
    "25/25/25/25":     ((.25, .25, .25, .25), 0.0),
    "20/20/20/40P":    ((.20, .20, .20, .40), 0.0),
    "20/20/20+40run":  ((1 / 3, 1 / 3, 1 / 3), 0.40),
}
SIZES = (75, 100, 125, 150, 175, 200, 250, 300)


def my_walk(entry, stop, long, i, bars, rungs, runner_w):
    """From-scratch fill. Deliberately does NOT call g101.walk_ladder."""
    risk = abs(entry - stop)
    sign = 1.0 if long else -1.0
    scale = 1.0 - runner_w
    rem, fills, filled, be, last_close = 1.0, [], set(), False, entry
    for c in bars[i + 1:]:
        if c.timestamp > WIN_END:
            break
        last_close = c.close
        if not be and ((c.low <= stop) if long else (c.high >= stop)):
            fills.append((rem, stop))
            rem = 0.0
            break
        touched = [k for k, r in enumerate(rungs) if k not in filled
                   and ((c.high >= r.price) if long else (c.low <= r.price))]
        if be and ((c.close <= entry) if long else (c.close >= entry)):
            px = (max(c.close, entry - 1.25 * risk) if long
                  else min(c.close, entry + 1.25 * risk))
            if touched:
                px = min(px, entry) if long else max(px, entry)
            fills.append((rem, px))
            rem = 0.0
            break
        if touched:
            for k in sorted(touched, key=lambda j: rungs[j].price if long
                            else -rungs[j].price):
                filled.add(k)
                fills.append((rungs[k].weight * scale, rungs[k].price))
                rem -= rungs[k].weight * scale
            be = True
            if len(filled) == len(rungs) and rem <= 1e-9:
                rem = 0.0
                break
    if rem > 1e-9:
        fills.append((rem, last_close))
    return sum(w * sign * (px - entry) / risk for w, px in fills)


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    byday = g86.candidates(rows_all)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    print("min_risk_floor source: %s" % om.MIN_RISK_FLOOR_SOURCE)

    arms = {k: [] for k in SHAPES}
    arms["shipped"] = []
    mine = {k: [] for k in SHAPES}
    days, rungnames = [], []
    gated = nobars = 0

    for r in firsts:
        entry, stop = r["entry"], r["stop"]
        if abs(entry - stop) < sr.min_risk_floor(entry):
            gated += 1
            continue
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            nobars += 1
            continue
        long = r["dir"] == "call"
        if g97.walk(r, bars) is None:
            gated += 1
            continue
        extreme = (max(c.high for c in bars[:i + 1]) if long
                   else min(c.low for c in bars[:i + 1]))
        named = ({"PDH": pdh, "PMH": pmh} if long else {"PDL": pdl, "PML": pml})
        days.append(r["day"])
        arms["shipped"].append(r["r"])
        rungnames.append([x.name for x in g101.build_rungs(
            entry, stop, long, extreme, named, (.25,) * 4, "4")])
        for lbl, (w, rw) in SHAPES.items():
            rungs = g101.build_rungs(entry, stop, long, extreme, named, w, "4")
            arms[lbl].append(g101.r_of(
                g101.walk_ladder(r, bars, rungs, trail="be", runner_w=rw),
                entry, stop, long))
            mine[lbl].append(my_walk(entry, stop, long, i, bars, rungs, rw))

    n = len(days)
    print("n=%d gated=%d nobars=%d\n" % (n, gated, nobars))

    print("=== 1. INDEPENDENT FILL DIFF + R1 CHECK ===")
    print("| arm | EV/R g113 | EV/R independent | worst row diff | min R | rows < -1.000R |")
    print("|---|---:|---:|---:|---:|---:|")
    for k in SHAPES:
        dmax = max(abs(x - y) for x, y in zip(arms[k], mine[k]))
        print("| %-16s | %+.4f | %+.4f | %.9f | %+.4f | %d |"
              % (k, om.ev_r_scoreboard(arms[k], size_gate=False)["ev_r"],
                 om.ev_r_scoreboard(mine[k], size_gate=False)["ev_r"],
                 dmax, min(arms[k]), sum(1 for x in arms[k] if x < -1.0)))

    print("\n=== 2. RUNG-COUNT AUDIT (why three arms are one arm) ===")
    print("rungs surviving per row: %s" % dict(Counter(len(v) for v in rungnames)))
    print("nearest rung (the one 'one_target' buys): %s"
          % dict(Counter(v[0] for v in rungnames if v)))
    for a, c in (("30/30/30/10", "25/25/25/25"), ("25/25/25/25", "20/20/20/40P"),
                 ("30/30/30/10", "20/20/20/40P"), ("50/20/20/10", "25/25/25/25")):
        same = sum(1 for x, y in zip(arms[a], arms[c]) if abs(x - y) < 1e-9)
        print("  %-14s vs %-14s identical on %d/%d rows (%.1f%%)"
              % (a, c, same, n, same / n * 100))

    print("\n=== 3. DURABILITY ===")
    cut = n // 2
    print("H1 %s..%s   H2 %s..%s" % (days[0], days[cut - 1], days[cut], days[-1]))
    print("| arm | EV/R all | EV/R H1 | EV/R H2 | 2024 | 2025 | 2026 |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    dur = {}

    def ev(seq):
        return om.ev_r_scoreboard(seq, size_gate=False)["ev_r"]

    for k in list(SHAPES) + ["shipped"]:
        v = arms[k]
        per = {}
        for d, x in zip(days, v):
            per.setdefault(d[:4], []).append(x)
        dur[k] = {"all": ev(v), "H1": ev(v[:cut]), "H2": ev(v[cut:]),
                  "by_year": {y: ev(s) for y, s in sorted(per.items())}}
        print("| %-16s | %+.4f | %+.4f | %+.4f | %+.4f | %+.4f | %+.4f |"
              % (k, dur[k]["all"], dur[k]["H1"], dur[k]["H2"],
                 dur[k]["by_year"].get("2024", 0), dur[k]["by_year"].get("2025", 0),
                 dur[k]["by_year"].get("2026", 0)))

    print("\n=== 4. PROP EVAL, ROLLING START DATE ($50k eval, defaults) ===")
    starts = list(range(0, n - 120, 20))
    print("| arm | %s |" % " | ".join("$%d" % s for s in SIZES))
    print("|---|%s" % ("---:|" * len(SIZES)))
    grid = {}
    for k in list(SHAPES) + ["shipped"]:
        cells, row = [], []
        for s in SIZES:
            passes = [days[o] for o in starts
                      if om.evaluate_prop_challenge(
                          [(days[i], arms[k][i] * s) for i in range(o, n)],
                          account_size=50000.0)["passed"]]
            cells.append("%d/%d" % (len(passes), len(starts)))
            row.append({"size": s, "n_pass": len(passes),
                        "n_starts": len(starts),
                        "last_passing_start": max(passes) if passes else None})
        grid[k] = row
        print("| %-16s | %s |" % (k, " | ".join(cells)))
    latest = [c["last_passing_start"] for v in grid.values() for c in v
              if c["last_passing_start"]]
    print("LATEST START DATE THAT EVER PASSES, any arm, any size: %s"
          % (max(latest) if latest else "none"))

    print("\n=== 5. PAIRED PERMUTATION (same 444 rows) ===")
    random.seed(11)
    perm = {}
    for a, c in (("20/20/20+40run", "one_target"), ("30/30/30/10", "one_target"),
                 ("20/20/20+40run", "30/30/30/10"), ("25/25/25/25", "50/20/20/10")):
        diff = [x - y for x, y in zip(arms[a], arms[c])]
        obs = statistics.fmean(diff)
        p = sum(1 for _ in range(20000)
                if abs(statistics.fmean([x if random.random() < .5 else -x
                                         for x in diff])) >= abs(obs)) / 20000
        perm["%s vs %s" % (a, c)] = {"diff_R": round(obs, 4), "p": p}
        print("  %-18s vs %-14s  %+.4fR  p=%.4f" % (a, c, obs, p))

    json.dump({"n": n, "gated": gated, "days": days, "arms": arms,
               "durability": dur, "prop_grid": grid, "permutation": perm},
              open(OUT, "w", encoding="utf-8"), indent=2, default=str)
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
