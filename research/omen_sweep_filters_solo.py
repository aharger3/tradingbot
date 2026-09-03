"""omen_sweep_filters_solo.py -- SWEEP: filters_solo.

Every downgrade variable in research/downgrade.py, each applied ALONE as a
veto: no_retest, no_displacement, level_not_respected, counter_trend_not_respected,
ocr_not_respected, exhausted, chase, stale_retest. Read-only measurement over
the committed book (research/bt2y_trades_retest_on.json). Nothing is applied;
nothing in downgrade.py or signal_runner.py is touched.

WHAT "SOLO VETO" MEANS
-----------------------
The baseline arm is the honest one-trade-a-day book: for each session, the
FIRST fired-and-traded signal of the day (earliest entry time, across every
symbol) -- same selection g86_honest_ceiling.candidates() uses, and the same
arm CLAUDE.md's book result ($28/day, now ev_r=0.0377) is measured on.

Each traded row in the committed book already carries `downgrades`: the list
of downgrade.py variables that tripped on that exact signal, baked in at
book-build time by the same score() this file must not re-run (a bug-fix
fleet owns signal_runner.py/backtest_week.py tonight). A "solo veto" arm for
variable X does not touch the ladder or re-grade anything -- it just asks: of
the one-trade-a-day candidate stream, if a day's first candidate has X in its
`downgrades` list, SKIP that day (no trade) instead of taking it. Every other
downgrade variable is ignored. That is "alone" -- not X stacked on the other
seven, X versus nothing.

Skipping a day is not free: a day with no trade contributes R=0, not a
dropped row, to the ev_r_scoreboard's day-level reads (months_green,
yearly_R) -- but it also is not thrown into the `n` denominator, since
ev_r_scoreboard.n counts trades taken, not sessions. Both the "trades taken"
table (comparable to the book headline) and the full-calendar "sessions"
context (n_days, days_skipped) are reported for each arm so neither reading
hides the other.

REACHABILITY
------------
Two rows in this table are already documented as reachability failures
elsewhere: `break_then_rejection` fires on 0 of 127,152 signals in this same
book (research/MASTER_SPEC.md:190, research/p2_threshold_sweep.md) and is
NOT one of the eight variables in this sweep's brief -- it is excluded from
`downgrade.CHECKS`'s practical ladder for that reason and is reported here
only as a cross-check, not scored. `stale_retest` IS in the brief and is the
one variable inside it MASTER_SPEC.md already flags "near-unreachable" (6 of
4,022 traded). This script recomputes both counts fresh against the
retest-on book (MASTER_SPEC's 4,022 is the same book) and additionally
reports the count AFTER the one-trade-a-day + size-gate reduction, which is
the population that actually decides whether a solo-veto arm can move a
single dollar. A variable that tripped on zero of the ~444 sizeable
first-of-day trades cannot veto anything in this arm even if it trips
elsewhere in the full 4,022 -- that is "unreachable IN THIS ARM" and is
called out explicitly, separately from the full-book count.

    python research/omen_sweep_filters_solo.py
"""
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from omen_metrics import ev_r_scoreboard, evaluate_prop_challenge, MIN_RISK_FLOOR_SOURCE

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")

VARIABLES = [
    "no_retest",
    "no_displacement",
    "level_not_respected",
    "counter_trend_not_respected",
    "ocr_not_respected",
    "exhausted",
    "chase",
    "stale_retest",
]

# reported for context only -- not part of the brief's eight, known dead
# (research/MASTER_SPEC.md:190, research/p2_threshold_sweep.md)
CROSS_CHECK_ONLY = "break_then_rejection"


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def load_book():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    return blob["meta"], blob["trades"]


def first_of_day_candidates(rows):
    """Exactly g86_honest_ceiling.candidates(), scoped to this book: fired
    and traded, plus rows the account-wide two-loss halt caught (irrelevant
    to the FIRST signal of a day, since that halt cannot yet have fired --
    kept for parity with the established selection rule, not because it
    changes this arm's outcome). Sorted (day, et, sym); index 0 per day is
    the candidate."""
    byday = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday[r["day"]].append(r)
    for v in byday.values():
        v.sort(key=ekey)
    return byday


def build_arms(meta, rows):
    """Returns (all_sessions, baseline_firsts, trip_counts_full_book)."""
    n_sessions = meta.get("sessions") or len({r["day"] for r in rows})
    byday = first_of_day_candidates(rows)
    # the day's FIRST candidate, whether or not it ultimately trades (a
    # skipped/untraded first candidate still occupies "the first setup of
    # the day" -- it is a day with no trade either way under one-a-day)
    firsts = {day: v[0] for day, v in byday.items()}

    traded_rows = [r for r in rows if r.get("traded")]
    trip_full = defaultdict(int)
    for r in traded_rows:
        for d in (r.get("downgrades") or []):
            trip_full[d] += 1

    return n_sessions, firsts, trip_full, len(traded_rows)


def arm_rows(firsts, veto_var):
    """The trade stream for one solo-veto arm: for each session's first
    candidate, keep it (as a book row, for the scoreboard) if `veto_var` is
    None (baseline) or not in that candidate's `downgrades`; otherwise the
    day contributes no trade."""
    kept = []
    days_skipped = 0
    days_total = len(firsts)
    for day in sorted(firsts):
        cand = firsts[day]
        if not cand.get("traded"):
            # the day's first candidate never actually filled (e.g. tight
            # stop) -- no trade under one-a-day regardless of veto
            days_skipped += 1
            continue
        tripped = veto_var is not None and veto_var in (cand.get("downgrades") or [])
        if tripped:
            days_skipped += 1
            continue
        kept.append(cand)
    return kept, days_total, days_skipped


def score_arm(rows, n_sessions, risk_dollars=1000.0):
    sb = ev_r_scoreboard(rows, risk_dollars=risk_dollars, sessions=n_sessions)
    return sb


def prop_eval_from_rows(rows, account_size=50000.0):
    """Build a daily equity curve (one trade/day, so day pnl == trade pnl)
    from the (already size-gated inside ev_r_scoreboard, but we re-gate here
    since evaluate_prop_challenge takes raw pnls) sizeable trades, then
    PASS/FAIL the default modern-eval shape Austin specified 2026-09-03."""
    from omen_metrics import _row_is_sizeable
    daily = []
    for r in sorted(rows, key=lambda r: r["day"]):
        sizeable = _row_is_sizeable(r)
        if sizeable is False:
            continue  # unsizeable rows do not enter the equity curve either
        daily.append({"day": r["day"], "pnl": r["pnl"]})
    return evaluate_prop_challenge(daily, account_size=account_size), len(daily)


def fmt_pf(pf):
    if pf is None:
        return "n/a"
    if pf == float("inf"):
        return "inf"
    return "%.2f" % pf


def main():
    meta, rows = load_book()
    n_sessions, firsts, trip_full, n_traded_full = build_arms(meta, rows)
    n_days = len(firsts)

    print("=" * 100)
    print("SWEEP: filters_solo -- research/bt2y_trades_retest_on.json (%d sessions, %d fired-and-traded)"
          % (n_sessions, n_traded_full))
    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    print("=" * 100)

    # -- reachability on the full traded book (context) --
    print("\n-- reachability, full traded book (%d rows) --" % n_traded_full)
    for v in VARIABLES + [CROSS_CHECK_ONLY]:
        n = trip_full.get(v, 0)
        pct = (n / n_traded_full * 100) if n_traded_full else 0.0
        tag = ""
        if v == CROSS_CHECK_ONLY:
            tag = "  (not in brief's 8 -- cross-check only)"
        print("  %-30s %5d / %5d  (%5.1f%%)%s" % (v, n, n_traded_full, pct, tag))

    # -- baseline arm: no veto --
    base_rows, base_total, base_skipped = arm_rows(firsts, None)
    base_sb = score_arm(base_rows, n_sessions)
    base_prop, base_prop_n = prop_eval_from_rows(base_rows)

    print("\n-- BASELINE (first-of-day, no veto) --")
    print("  days_total=%d  days_no_trade(untraded first candidate)=%d  trades=%d"
          % (base_total, base_skipped, len(base_rows)))
    print("  ev_r=%.4f  n=%d(n_dropped_size_gate=%d)  win=%.2f%%  avg_win=%.3fR  avg_loss=%.3fR  pf=%s"
          % (base_sb["ev_r"] or 0.0, base_sb["n"], base_sb["n_dropped_size_gate"],
             (base_sb["win_rate"] or 0.0) * 100, base_sb["avg_win_R"] or 0.0,
             base_sb["avg_loss_R"] or 0.0, fmt_pf(base_sb["profit_factor"])))
    print("  months_green=%s  yearly_R=%.3f  $/day=%.2f  max_dd_R=%.3f"
          % (base_sb["months_green"], base_sb["yearly_R"] or 0.0,
             base_sb["expectancy_per_day"] or 0.0, base_sb["max_drawdown_R"]))
    print("  prop-eval: %s  fail_reason=%s  (n=%d sizeable daily rows)"
          % ("PASS" if base_prop["passed"] else "FAIL", base_prop["fail_reason"], base_prop_n))

    # -- each solo-veto arm --
    print("\n-- SOLO-VETO ARMS --")
    header = ("%-28s %6s %6s %6s | %8s %5s %7s %7s %7s %6s | %8s %10s | %-9s %s"
              % ("variable", "trip", "n_v", "n_kept", "ev_r", "n", "win%",
                 "avgW_R", "avgL_R", "pf", "months_g", "$/day", "prop", "fail_reason"))
    print(header)
    print("-" * len(header))

    results = {}
    for v in VARIABLES:
        rows_v, total_v, skipped_v = arm_rows(firsts, v)
        n_vetoed = sum(1 for day in firsts if firsts[day].get("traded")
                       and v in (firsts[day].get("downgrades") or []))
        sb = score_arm(rows_v, n_sessions)
        prop, prop_n = prop_eval_from_rows(rows_v)
        results[v] = dict(sb=sb, prop=prop, n_vetoed=n_vetoed, n_kept=len(rows_v),
                           trip_full=trip_full.get(v, 0))
        print("%-28s %6d %6d %6d | %8.4f %5d %7.2f %7.3f %7.3f %6s | %8s %10.2f | %-9s %s"
              % (v, trip_full.get(v, 0), n_vetoed, len(rows_v),
                 sb["ev_r"] if sb["ev_r"] is not None else 0.0, sb["n"],
                 (sb["win_rate"] or 0.0) * 100, sb["avg_win_R"] or 0.0,
                 sb["avg_loss_R"] or 0.0, fmt_pf(sb["profit_factor"]),
                 sb["months_green"], sb["expectancy_per_day"] or 0.0,
                 "PASS" if prop["passed"] else "FAIL", prop["fail_reason"]))

    # -- reachability inside the one-trade-a-day arm --
    print("\n-- reachability INSIDE the one-trade-a-day arm (%d first-of-day candidates) --" % n_days)
    unreachable = []
    for v in VARIABLES:
        n_vetoed = results[v]["n_vetoed"]
        print("  %-30s vetoes %4d / %4d first-of-day candidates (%.1f%%)  [%d trips in full book]"
              % (v, n_vetoed, n_days, n_vetoed / n_days * 100 if n_days else 0.0,
                 results[v]["trip_full"]))
        if n_vetoed == 0:
            unreachable.append(v)

    print("\n-- UNREACHABLE (0 vetoes in the one-trade-a-day arm) --")
    if unreachable:
        for v in unreachable:
            print("  %s -- 0 of %d first-of-day candidates ever carry it in `downgrades`" % (v, n_days))
    else:
        print("  none by the strict 0-veto test above")

    out = {
        "meta": {"book": os.path.basename(BOOK_PATH), "n_sessions": n_sessions,
                 "n_traded_full_book": n_traded_full, "n_first_of_day_candidates": n_days,
                 "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE},
        "reachability_full_book": {v: trip_full.get(v, 0) for v in VARIABLES + [CROSS_CHECK_ONLY]},
        "baseline": {"scoreboard": base_sb, "prop_eval": base_prop,
                     "days_total": base_total, "days_no_trade": base_skipped},
        "arms": {v: {"scoreboard": results[v]["sb"], "prop_eval": results[v]["prop"],
                      "n_vetoed_first_of_day": results[v]["n_vetoed"],
                      "n_kept": results[v]["n_kept"],
                      "trip_full_book": results[v]["trip_full"]}
                 for v in VARIABLES},
        "unreachable_in_arm": unreachable,
    }
    out_path = os.path.join(HERE, "omen_sweep_filters_solo.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print("\nwrote %s" % out_path)


if __name__ == "__main__":
    main()
