"""g93 -- what RETEST_REQUIRED is worth, on the honest book.

`signal_runner.RETEST_REQUIRED` (default OFF) caps a candidate to C when
`research/downgrade.py::no_retest` trips: the level was broken and never
retested. Austin, four separate cards and one ballot:

    "you seem to enter on breaks which is a halucination we never trade that and
     you know it"                                            PLTR_2024-09-20
    "you entered off no break and retest or anything"        HOOD_2025-12-23
    "same problem as previous just entering on a break"      TSLA_2025-03-25
    "you entered on an overextended break candle"            QQQ_2024-08-23
    rule_03 (yes): "should always be entering while the restest is occuring"

    python research/g93_retest_gate_ab.py
    python research/g93_retest_gate_ab.py --lane index

WHAT THIS MEASURES, AND WHAT IT DOES NOT. This is a SELECTION arm over the
2-year book's own recorded, causal `downgrade.score()` fields: it removes capped
candidates from the day's candidate list and re-picks the first one, exactly as
`g86_honest_ceiling.candidates` defines "first". Detection is not re-run. So
this prices the gate's effect on WHICH candidate is taken first, which is the
only thing a C cap can change for a one-trade-a-day policy.

**That makes the backtest_2y re-run the pass test, not a formality.** If wiring
the flag and re-running the book does not reproduce these numbers, the wiring is
wrong -- detection is unchanged, so only the pick can move.

THE REACHABILITY CHECK IS THE FIRST THING PRINTED, on purpose. `no_retest` trips
on 37,455 of 127,188 book rows, but the population that matters is the
fired-and-traded rows a one-a-day policy can actually pick. If that count were
zero the gate would be another entry in this repo's long list of real rules
encoded as branches that can never be true, and no money column below it would
mean anything. Read that line before any dollar figure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86                  # noqa: E402
import g91_lane_slice as g91                      # noqa: E402

HONEST = os.path.join(HERE, "bt2y_trades.json")
OUT_JSON = os.path.join(HERE, "g93_retest_gate_ab.json")
OUT_MD = os.path.join(HERE, "g93_retest_gate_ab.md")

LANES = {
    "full": (lambda r: True, "full pool, 28 symbols"),
    "index": (lambda r: r["sym"] in g91.INDEX, "QQQ/SPY/IWM"),
}


def trips(r, var: str) -> bool:
    d = r.get("downgrades")
    if isinstance(d, str):
        return var in [x.strip() for x in d.split(",")]
    return var in (d or ())


def arm(rows, drop_vars) -> dict:
    """One trade a day after removing every candidate that trips `drop_vars`.

    Removal, not re-grading: a C cap makes a candidate alert-only, and an
    alert-only candidate is not `fired and traded`, so it leaves the pool
    `g86.candidates` builds. That is the same thing the C cap does live.
    """
    keep = [r for r in rows if not any(trips(r, v) for v in drop_vars)]
    byday = g86.candidates(keep)
    firsts = [v[0] for day in sorted(byday) for v in (byday[day],) if v]
    daily = defaultdict(float)
    for r in firsts:
        daily[r["day"]] += r["pnl"]
    n_days = len(daily)
    if not n_days:
        return {}
    g, m = g91.months_green(daily)
    path = g91.path_risk(daily, 2000.0, 2500.0)
    return {
        "cands_per_day": round(sum(len(v) for v in byday.values()) / n_days, 1),
        "days": n_days,
        "stats": g86.stats(firsts, n_days),
        "green": "%d/%d" % (g, m),
        "green_n": g,
        "max_dd": path["max_dd"],
        "max_r_for_dd": path["max_r_for_dd"],
        "funded_per_day": path["funded_per_day"],
    }


def reachability(rows, pred) -> dict:
    """Does no_retest ever trip on a row a one-a-day policy could pick?"""
    sub = [r for r in rows if pred(r)]
    pickable = [r for r in sub
                if (r["status"] == "fired" and r.get("traded"))
                or r["status"] == "halted"]
    hit = [r for r in pickable if trips(r, "no_retest")]
    byday = g86.candidates(sub)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    first_hit = [r for r in firsts if trips(r, "no_retest")]
    return {
        "book_rows": len(sub),
        "pickable": len(pickable),
        "pickable_no_retest": len(hit),
        "pickable_pct": round(len(hit) / len(pickable) * 100, 1) if pickable else 0,
        "firsts": len(firsts),
        "firsts_no_retest": len(first_hit),
        "firsts_pct": round(len(first_hit) / len(firsts) * 100, 1) if firsts else 0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lane", choices=sorted(LANES), default=None)
    a = ap.parse_args()

    book = json.load(open(HONEST, encoding="utf-8"))
    rows = book["trades"] if isinstance(book, dict) else book
    lanes = [a.lane] if a.lane else ["full", "index"]

    out, md = {}, ["# g93 -- RETEST_REQUIRED, priced", "",
                   "Honest book (`research/bt2y_trades.json`), one trade a day = "
                   "the first fired-and-traded candidate of the session "
                   "(`g86_honest_ceiling.candidates`). 1R = $1,000. Selection "
                   "arm over the book's recorded causal `downgrade.score()` "
                   "fields -- detection is NOT re-run.", ""]

    for lane in lanes:
        pred, why = LANES[lane]
        sub = [r for r in rows if pred(r)]
        reach = reachability(rows, pred)
        print("\n=== %s (%s) ===" % (lane, why))
        print("  REACHABILITY: no_retest trips on %d/%d pickable rows (%.1f%%) "
              "and on %d/%d of the days' FIRST picks (%.1f%%)"
              % (reach["pickable_no_retest"], reach["pickable"],
                 reach["pickable_pct"], reach["firsts_no_retest"],
                 reach["firsts"], reach["firsts_pct"]))
        if reach["firsts_no_retest"] == 0:
            print("  ^^ THE GATE IS A NO-OP ON THIS LANE. It can never change a "
                  "pick. Do not ship it here; the money columns below are "
                  "identical by construction, not by merit.")

        arms = {
            "baseline": arm(sub, ()),
            "retest": arm(sub, ("no_retest",)),
            "retest+chase": arm(sub, ("no_retest", "chase")),
        }
        for k, v in arms.items():
            if not v:
                continue
            s = v["stats"]
            print("  %-14s %5.1f cand/day  $%6.0f/day  %.1f%% win  %-6s green  "
                  "maxDD $%-7.0f  funded $%.2f/day"
                  % (k, v["cands_per_day"], s["per_day"], s["win_pct"],
                     v["green"], v["max_dd"], v["funded_per_day"]))
        out[lane] = {"reachability": reach, "arms": arms}

        md += ["## %s -- %s" % (lane, why), "",
               "`no_retest` trips on **%d of %d** pickable rows (%.1f%%) and on "
               "**%d of %d** of the days' first picks (%.1f%%)."
               % (reach["pickable_no_retest"], reach["pickable"],
                  reach["pickable_pct"], reach["firsts_no_retest"],
                  reach["firsts"], reach["firsts_pct"]), "",
               "| arm | cand/day | $/day | win | green | max DD | funded $/day |",
               "|---|---:|---:|---:|---:|---:|---:|"]
        for k, v in arms.items():
            if not v:
                continue
            s = v["stats"]
            md.append("| %s | %.1f | $%.0f | %.1f%% | %s | $%.0f | $%.2f |"
                      % (k, v["cands_per_day"], s["per_day"], s["win_pct"],
                         v["green"], v["max_dd"], v["funded_per_day"]))
        md.append("")

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))

    # Self-check: the baseline arm must still be g86's published number, or the
    # deltas above are measured against a book nobody has seen.
    base = out.get("full", {}).get("arms", {}).get("baseline")
    if base:
        ref = g86.arm(HONEST, "honest")
        assert abs(base["stats"]["per_day"] - ref["first"]["per_day"]) < 0.01, \
            "baseline drifted from g86: %s vs %s" % (base["stats"]["per_day"],
                                                     ref["first"]["per_day"])
        print("demo OK -- full-pool baseline reproduces g86: $%.0f/day"
              % base["stats"]["per_day"])


if __name__ == "__main__":
    main()
