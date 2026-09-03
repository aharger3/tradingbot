"""g99 -- rung recon for the exit-ladder spec. Measures ONLY, applies nothing.

Austin's four rungs (anatomy cards, 2026-09-01) are PT1 = the near session
extreme, PT2 = a structural level, PT3 = 2R, PT4 = a runner. Before any of that
is built, four facts about the honest book have to be on the table:

  1. how often TODAY's runner target lands INSIDE the 2R target
     (backtest_week.py:1032-1043 computes the two and never compares them),
  2. where PT1 actually sits, in R, at the entry bar,
  3. whether a named level (PDH/PDL, PMH/PML, OR high/low) even EXISTS beyond
     PT1 to serve as PT2, and
  4. whether the level the setup is keyed to (`level_px`) is ahead of price --
     it is not, on any row, which is why PT2 cannot be "the retest level".

Same population as research/g97_mfe.py: `bt2y_trades_retest_on.json`,
first-of-day, size-gated on `signal_runner.min_risk_floor`, bars from
research/g80_ordertype_grid.day_pack (causal slices only, bars[:entry_i+1]).

    python research/g99_rung_recon.py
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g97_mfe as g97                             # noqa: E402
import signal_runner as sr                        # noqa: E402
from research import g80_ordertype_grid as G      # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")


def firsts():
    rows = json.load(open(BOOK, encoding="utf-8"))
    rows = rows["trades"] if isinstance(rows, dict) else rows
    byday = g86.candidates(rows)
    return [byday[d][0] for d in sorted(byday) if byday[d]]


def main():
    rows = firsts()
    print("first-of-day rows: %d" % len(rows))
    n = inside = gated = nobars = lvl_ahead = no_pt2 = 0
    rt_r, pt1_r, pt2_r, mfe = [], [], [], []
    rt_src, pt2_src = Counter(), Counter()

    for r in rows:
        entry, stop = r["entry"], r["stop"]
        risk = abs(entry - stop)
        if risk < sr.min_risk_floor(entry):
            gated += 1
            continue
        i = r.get("entry_i")
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        if not bars or i is None or i >= len(bars):
            nobars += 1
            continue
        n += 1
        long = r["dir"] == "call"
        orh = max(c.high for c in bars[:5])
        orl = min(c.low for c in bars[:5])
        lv = r.get("level_px") or r.get("level")
        if lv and ((lv > entry) if long else (lv < entry)):
            lvl_ahead += 1

        # --- today's engine, verbatim from backtest_week.py:1032-1043 ---
        if long:
            scale = max(c.high for c in bars[:i + 1])
            cands = [x for x in (pdh, pmh) if x is not None and x > scale]
            cands.append(math.floor(scale) + 1.0)
            rt = min(cands)
            tgt = entry + 2 * risk
            hit_inside = rt < tgt
            named = {"PDH": pdh, "PMH": pmh, "ORH": orh}
            beyond = {k: v for k, v in named.items() if v is not None and v > scale}
            pick = min(beyond, key=lambda k: beyond[k]) if beyond else None
            sgn = 1.0
        else:
            scale = min(c.low for c in bars[:i + 1])
            cands = [x for x in (pdl, pml) if x is not None and x < scale]
            cands.append(math.ceil(scale) - 1.0)
            rt = max(cands)
            tgt = entry - 2 * risk
            hit_inside = rt > tgt
            named = {"PDL": pdl, "PML": pml, "ORL": orl}
            beyond = {k: v for k, v in named.items() if v is not None and v < scale}
            pick = max(beyond, key=lambda k: beyond[k]) if beyond else None
            sgn = -1.0

        inside += 1 if hit_inside else 0
        rt_r.append(sgn * (rt - entry) / risk)
        pt1_r.append(sgn * (scale - entry) / risk)
        rt_src[({v: k for k, v in (("pdh", pdh), ("pmh", pmh), ("pdl", pdl),
                                   ("pml", pml)) if v is not None}).get(rt, "whole$")] += 1
        if pick is None:
            no_pt2 += 1
        else:
            pt2_src[pick] += 1
            pt2_r.append(sgn * (beyond[pick] - entry) / risk)
        w = g97.walk(r, bars)
        if w is not None:
            mfe.append(w[0])

    def band(vals, edges):
        c = Counter()
        for v in vals:
            lab = "<%.1f" % edges[0]
            for e in edges:
                if v >= e:
                    lab = ">=%.1f" % e
            c[lab] += 1
        return dict(c)

    print("measured %d  (%d below min_risk_floor, %d no bars)" % (n, gated, nobars))
    print("\n1. TODAY's runner target vs the 2R target")
    print("   INSIDE 2R: %d / %d = %.1f%%" % (inside, n, 100.0 * inside / n))
    print("   runner target  mean %.3fR  median %.3fR" % (statistics.mean(rt_r),
                                                          statistics.median(rt_r)))
    print("   bands %s" % band(rt_r, [0.5, 1.0, 1.5, 2.0, 3.0]))
    print("   source %s" % dict(rt_src))
    print("\n2. PT1 (session extreme as of the entry bar)")
    print("   mean %.3fR  median %.3fR  at-or-behind entry %d  >=2R %d"
          % (statistics.mean(pt1_r), statistics.median(pt1_r),
             sum(1 for x in pt1_r if x <= 0), sum(1 for x in pt1_r if x >= 2)))
    print("   bands %s" % band(pt1_r, [0.0, 0.5, 1.0, 2.0]))
    print("\n3. PT2 candidate (nearest named level strictly beyond PT1)")
    print("   available %d, MISSING %d (%.1f%%)" % (len(pt2_r), no_pt2,
                                                    100.0 * no_pt2 / n))
    if pt2_r:
        print("   mean %.3fR  median %.3fR  bands %s"
              % (statistics.mean(pt2_r), statistics.median(pt2_r),
                 band(pt2_r, [1.0, 2.0, 3.0])))
    print("   source %s   (OR high/low never wins: the session extreme "
          "subsumes it by construction)" % dict(pt2_src))
    print("\n4. the setup's own keyed level (`level_px`)")
    print("   ahead of price in the trade's direction on %d / %d rows"
          % (lvl_ahead, n))
    print("\n5. PT4 sizing input -- MFE while alive, conditional on reaching 2R")
    for c in (2.0, 2.5, 3.0):
        s = [x for x in mfe if x >= c]
        print("   >=%.1fR: n=%d (%.1f%%)  mean %.2fR  median %.2fR"
              % (c, len(s), 100.0 * len(s) / len(mfe), statistics.mean(s),
                 statistics.median(s)))


if __name__ == "__main__":
    main()
