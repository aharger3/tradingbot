"""w12_dg_probe.py -- W12: is any of the eight downgrade variables unreachable?

WHY THIS EXISTS
---------------
The ladder is about to become a pure function of the downgrade count
(0=S, 1=A, 2=C, 3+=X, `Specs/omen6-h2-master-spec.md` 1.2). Every variable that
cannot fire is a variable the new ladder silently does not have, and this repo
has a documented history of exactly that failure -- `before11`, the 84%
re-entry, `break_then_rejection`.

`research/g3_arm_ow1.json` already carries a `downgrades` list per row for all
45,193 signals of the 2-year book, so the FIRING rate of each variable is a
count away. What it does NOT carry is why: a variable can read 0 because the
tape never showed the pattern (dead by data, and a wider threshold would fix
it) or because the caller's own precondition makes the predicate unsatisfiable
(dead by construction, and no threshold will ever fix it). Those need the bars.

So this file re-derives each variable from `data_archive/` on the exact bar
`backtest_2y.py` graded, and counts the INTERNAL branch each one took:

  * how often `_break_bar` finds no break at all -- the input three of the
    eight variables share, and the one that decides whether they can speak
  * `break_then_rejection`'s rejection scan, against the most-recent break
    (shipped) and against the FIRST break of the session (the reading that
    makes the rule mean what its docstring says)
  * `find_ocr`'s `j + 1 > i` guard, which the loop bounds make unreachable
  * the net-downgrade histogram under the 2026-08-28 ladder, including the
    3+ bucket `downgrade.score()` currently floors away

PROVENANCE
----------
Bars: `data_archive/` via `polygon_feed`, RTH only, index 0 = the 09:30 bar --
the same convention `backtest_2y.py` writes into each row's `entry_i`. Level:
the row's own `stop`, the level proxy `_label_confluence`, `backtest_2y.py` and
`signal_runner._sac_ladder_grade` all already use. Nothing is fetched.

    python research/w12_dg_probe.py            # ~5 min, writes _w12/dg.json
"""
from __future__ import annotations

import collections
import json
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polygon_feed as pf                                      # noqa: E402
from research import downgrade as dg                           # noqa: E402

BOOK = os.path.join(ROOT, "research", "g3_arm_ow1.json")
OUT = os.path.join(ROOT, "research", "_w12", "dg.json")


def bars_for(sym: str, day: str):
    rth = pf.rth(pf.fetch_day(sym, day))
    return [{"o": c.open, "h": c.high, "l": c.low, "c": c.close, "v": c.volume}
            for c in rth]


def first_break_bar(bars, i, level, is_long):
    """The EARLIEST bar that closed through the level, scanning forward.

    `downgrade._break_bar` returns the MOST RECENT one. That choice is what
    makes `break_then_rejection` unsatisfiable: if any bar after the most
    recent up-cross had closed back below the level, getting back above it by
    bar `i` requires a LATER cross, which would then have been the most recent
    one. This function is the other reading -- 'it broke, then immediately gave
    it back' measured from the break that actually happened -- and exists only
    to PRICE the dead rule. It is not wired into anything."""
    for j in range(1, i + 1):
        prev, cur = bars[j - 1], bars[j]
        crossed = ((prev["c"] <= level < cur["c"]) if is_long
                   else (prev["c"] >= level > cur["c"]))
        if crossed:
            return j
    return None


def rejection_after(bars, i, level, is_long, br):
    if br is None:
        return False
    for j in range(br + 1, min(br + 1 + dg.REJECT_BARS, i + 1)):
        if (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level):
            return True
    return False


def main():
    rows = json.load(open(BOOK, encoding="utf-8"))["trades"]
    cache = {}
    c = collections.Counter()
    net_hist = collections.Counter()
    r_by_net = collections.defaultdict(list)
    net_fixed = collections.Counter()
    r_by_net_fixed = collections.defaultdict(list)
    ocr_guard_hits = 0
    missing = 0

    for n, r in enumerate(rows):
        if n and n % 5000 == 0:
            print("  %d / %d" % (n, len(rows)), flush=True)
        key = (r["sym"], r["day"])
        if key not in cache:
            try:
                cache[key] = bars_for(*key)
            except Exception:
                cache[key] = []
        bars = cache[key]
        i = r["entry_i"]
        level = r["stop"]
        is_long = r["dir"] == "call"
        if not bars or i is None or i >= len(bars) or level is None:
            missing += 1
            continue
        c["rows"] += 1

        br = dg._break_bar(bars, i, level, is_long)
        c["break_bar_none"] += br is None
        fb = first_break_bar(bars, i, level, is_long)
        c["first_break_none"] += fb is None
        c["break_bar_differs"] += (br is not None and fb is not None and br != fb)

        c["btr_shipped"] += rejection_after(bars, i, level, is_long, br)
        c["btr_first_break"] += rejection_after(bars, i, level, is_long, fb)

        # the caller's precondition, which is what makes the shipped reading
        # unsatisfiable: the graded bar closes BEYOND the level
        beyond = (bars[i]["c"] > level) if is_long else (bars[i]["c"] < level)
        c["closes_beyond_level"] += beyond

        # find_ocr's `j + 1 > i` guard: the loop starts at j = i - 1, so j + 1
        # is at most i and the guard can never be true. Counted, not asserted.
        for j in range(i - 1, max(1, i - 20) - 1, -1):
            c["ocr_guard_evals"] += 1
            if j + 1 > i:
                ocr_guard_hits += 1

        for v in dg.VARIABLES:
            if getattr(dg, v)(bars, i, level, is_long):
                c["fire_" + v] += 1

        rec = dg.score(bars, i, level, is_long)
        if rec is not None:
            net_hist[min(rec["net"], 8)] += 1
            if r.get("traded") and r.get("r") is not None:
                r_by_net[min(rec["net"], 8)].append(r["r"])
            # what the ladder does once `break_then_rejection` can actually
            # speak: the same net, plus one where the first-break reading
            # trips and the shipped one cannot.
            bump = (rejection_after(bars, i, level, is_long, fb)
                    and not rejection_after(bars, i, level, is_long, br))
            fixed = rec["net"] + (1 if bump else 0)
            net_fixed[min(fixed, 8)] += 1
            if r.get("traded") and r.get("r") is not None:
                r_by_net_fixed[min(fixed, 8)].append(r["r"])

    res = {"rows_scored": c["rows"], "rows_missing_bars": missing,
           "counts": dict(c), "net_hist": {str(k): v for k, v in sorted(net_hist.items())},
           "ocr_guard_hits": ocr_guard_hits,
           "net_hist_btr_fixed": {str(k): v for k, v in sorted(net_fixed.items())},
           "traded_r_by_net_btr_fixed": {
               str(k): {"n": len(v), "mean": round(statistics.fmean(v), 4),
                        "median": round(statistics.median(v), 4)}
               for k, v in sorted(r_by_net_fixed.items()) if v},
           "traded_r_by_net": {str(k): {"n": len(v),
                                        "mean": round(statistics.fmean(v), 4),
                                        "median": round(statistics.median(v), 4)}
                               for k, v in sorted(r_by_net.items()) if v}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
