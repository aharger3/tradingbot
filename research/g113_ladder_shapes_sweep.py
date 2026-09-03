"""g113 -- SWEEP: ladder_shapes. Does scaling out beat one-shot on EV/R?

Austin's 2026-09-03 ruling: the bar is PASS ONE PROP EVALUATION within 12
months, not a dollar figure. EV PER TRADE IN R leads every table; $/day is a
supporting row. This sweep tests six scale-out SHAPES against the derived
ladder (PT1 = his HOD/LOD, PT2-PT5 derived in MASTER_SPEC.md section 3) on
the same 444 size-gated first-of-day rows every g9x/g10x script uses.

Shapes requested:
  100% one target | 50/50 | 30/30/30/10 | 50/20/20/10 | 25/25/25/25 |
  20/20/20/40 (runner-heavy)

Mapping shape -> rungs (no invention, reuses g101's own machinery):
  A shape of length N is assigned to the N rungs NEAREST in R (PT1, PT2, PT3,
  PT4 in that order when all survive; a missing rung -- PT2 is absent on
  50.5% of rows -- is dropped and the next one takes its slot, exactly the
  behaviour g99/g101 already ship). weights[0] -> nearest rung ... weights[-1]
  -> furthest. This makes "30/30/30/10" identically g101's own "4-rung
  30/30/30/10 (g99 control)" arm -- reused, not reproduced.

  20/20/20/40 is run TWICE because "runner-heavy" is ambiguous between two
  readings and both are defensible:
    (a) PRICED  -- PT1/PT2/PT3 at 20% each, PT4 (4R or next level) at 40%.
    (b) TRAILING -- PT1/PT2/PT3 at 20% each (renormalised), the last 40%
        held with NO price and trailed to 11:00 -- this is what MASTER_SPEC
        section 3 actually calls "the runner" (its PT5).

  100% one target has two readings too, both reported:
    (a) REPLICA -- 100% on the single nearest ladder rung (mostly PT1), this
        script's own bar-walk.
    (b) SHIPPED -- the book's own committed 'r' field: the book's stamp
        (bt2y_trades_retest_on.json meta.stamp.flags) carries
        backtest_week.SCALE_PLAN='hod_then_runner_be', so this is NOT a
        flat single target -- it is the currently-shipped HOD/LOD-then-
        runner-to-breakeven exit, real engine output rather than a
        replica. Kept as the trustworthy reference row, correctly labelled.

All rungs are built causally (bar i's own high/low never inform its own
entry) via g101.build_rungs; fills walk forward from entry_i+1 via
g101.walk_ladder, which routes through stop_rule.stop_fill_price /
disaster_stop_price and backtest_week._target_hit/_stop_hit -- nothing is
re-implemented locally (CLAUDE.md: "never re-implement a fill locally").
Trail mode is fixed at "be" (breakeven after first fill, the shipped
default, BE_TRIGGER=pt1 in the book's own stamp) for every shape so the
comparison isolates the SHAPE variable only.

A grid of sizing points is prop-evaluated per shape (RISK_LEVELS): $1,000
(the book's own historical unit), $500, $300, $200, $100, $50/trade -- to
find, per shape, whether ANY size clears the eval and where the crossover
sits. Every number is size-gated on signal_runner.min_risk_floor before it
is scored; n_dropped_size_gate is always reported.

    python research/g113_ladder_shapes_sweep.py
"""
from __future__ import annotations

import json
import os
import sys

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
OUT_JSON = os.path.join(HERE, "g113_ladder_shapes_sweep.json")

# shape label -> (weights, plan, runner_w)
SHAPES = {
    "100% one target (replica, nearest rung)": ((1.0,), "4", 0.0),
    "50/50":                                    ((.50, .50), "4", 0.0),
    "30/30/30/10":                              ((.30, .30, .30, .10), "4", 0.0),
    "50/20/20/10":                              ((.50, .20, .20, .10), "4", 0.0),
    "25/25/25/25":                              ((.25, .25, .25, .25), "4", 0.0),
    "20/20/20/40 runner-heavy (PRICED PT4)":    ((.20, .20, .20, .40), "4", 0.0),
    "20/20/20 + 40% free runner (TRAILING)":    ((1/3, 1/3, 1/3), "4", 0.40),
}

RISK_LEVELS = (1000.0, 500.0, 300.0, 200.0, 100.0, 50.0)


def main():
    b = json.load(open(BOOK, encoding="utf-8"))
    rows_all = b["trades"] if isinstance(b, dict) else b
    byday = g86.candidates(rows_all)
    firsts = [byday[d][0] for d in sorted(byday) if byday[d]]
    print("first-of-day rows (pre-gate): %d" % len(firsts))
    print("min_risk_floor source: %s\n" % om.MIN_RISK_FLOOR_SOURCE)

    arm_rows = {label: [] for label in SHAPES}
    arm_rows["SHIPPED (book's committed fill, scale_plan=hod_then_runner_be)"] = []
    n_gated = n_nobars = n_scored = 0

    for k, r in enumerate(firsts, 1):
        entry, stop = r["entry"], r["stop"]
        risk = abs(entry - stop)
        if risk < sr.min_risk_floor(entry):
            n_gated += 1
            continue
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            n_nobars += 1
            continue
        long = r["dir"] == "call"
        w = g97.walk(r, bars)
        if w is None:
            n_gated += 1
            continue
        extreme = (max(c.high for c in bars[:i + 1]) if long
                   else min(c.low for c in bars[:i + 1]))
        named = ({"PDH": pdh, "PMH": pmh} if long else {"PDL": pdl, "PML": pml})

        day = r["day"]
        arm_rows["SHIPPED (book's committed fill, scale_plan=hod_then_runner_be)"].append(
            {"day": day, "r": r["r"], "entry": entry, "stop": stop})

        for label, (weights, plan, rw) in SHAPES.items():
            rungs = g101.build_rungs(entry, stop, long, extreme, named,
                                      weights, plan)
            fills = g101.walk_ladder(r, bars, rungs, trail="be", runner_w=rw)
            tot = sum(x for x, _ in fills)
            assert abs(tot - 1.0) < 1e-6, "%s weights sum %.6f" % (label, tot)
            rr = g101.r_of(fills, entry, stop, long)
            arm_rows[label].append(
                {"day": day, "r": rr, "entry": entry, "stop": stop})
        n_scored += 1
        if k % 150 == 0:
            print("  ... %d/%d" % (k, len(firsts)))

    print("\nscored %d  (%d below min_risk_floor / no MFE, %d no bars)"
          % (n_scored, n_gated, n_nobars))

    order = ["SHIPPED (book's committed fill, scale_plan=hod_then_runner_be)"] + list(SHAPES)
    results = {}
    print("\n=== EV/R SCOREBOARD (headline), size-gated, n=%d candidate rows ===" % len(firsts))
    print("| shape | EV/R | n | win%% | avg_win_R | avg_loss_R | PF | max_DD_R | months_green | yearly_R |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label in order:
        rows = arm_rows[label]
        sb = om.ev_r_scoreboard(rows, risk_dollars=1000.0)
        results[label] = {"scoreboard": sb}
        print("| %-42s | %+.4f | %3d | %5.1f%% | %.3f | %.3f | %5s | %+.3f | %8s | %+.3f |"
              % (label, sb["ev_r"] or 0.0, sb["n"],
                 (sb["win_rate"] or 0) * 100, sb["avg_win_R"] or 0,
                 sb["avg_loss_R"] or 0,
                 "%.2f" % sb["profit_factor"] if isinstance(sb["profit_factor"], float) else sb["profit_factor"],
                 sb["max_drawdown_R"] or 0, sb["months_green"] or "-",
                 sb["yearly_R"] or 0))

    print("\n=== PROP-EVAL PASS/FAIL, sizing grid ($50k default eval) ===")
    for risk_dollars in RISK_LEVELS:
        print("\n-- risk_dollars = $%d/trade --" % risk_dollars)
        print("| shape | pass? | broke on | detail |")
        print("|---|---|---|---|")
        for label in order:
            rows = arm_rows[label]
            by_day = {}
            for row in rows:
                by_day.setdefault(row["day"], 0.0)
                by_day[row["day"]] += row["r"] * risk_dollars
            daily = [(d, by_day[d]) for d in sorted(by_day)]
            ev = om.evaluate_prop_challenge(daily, account_size=50000.0)
            results[label].setdefault("prop_eval", {})["$%d" % risk_dollars] = ev
            broke = ev.get("fail_reason") or "-"
            detail = "day %s, equity %.1f%% of target, days_traded=%d" % (
                ev.get("fail_day") or "-", ev.get("final_equity_pct") or 0,
                ev.get("days_traded") or 0)
            print("| %-42s | %-5s | %-22s | %s |"
                  % (label, "PASS" if ev.get("passed") else "FAIL", broke, detail))

    json.dump({"n_candidates": len(firsts), "n_scored": n_scored,
                "n_gated": n_gated, "n_nobars": n_nobars,
                "results": results}, open(OUT_JSON, "w", encoding="utf-8"),
               indent=2, default=str)
    print("\nwrote %s" % OUT_JSON)


if __name__ == "__main__":
    main()
