"""sweep_targets_flat.py -- one arm of the 2026-09-03 backtest fleet.

Question: sweep a FLAT target (entry +/- N*R, N = 1.00R .. 6.00R in 0.25R
steps) against the committed honest-fill book, holding entry and stop fixed
at the book's own values, and report EV/R (the headline, per Austin's
2026-09-03 ruling), hit rate, and prop-eval PASS/FAIL at each N. Find the
EV-maximising N and the prop-eval-maximising N and say whether they match.

READ-ONLY. Does not import backtest_week, stop_rule, live_scanner or
research/test_runner_stop -- those are being edited live by other agents in
this same fleet run. Bars come straight from polygon_feed (cache-first, the
same data_archive/<SYM>/<DAY>.csv the rest of the project reads) so this
script has no dependency on the module a bug-fix agent might be mid-editing.

POPULATION: the first-of-day arm (one trade a day, arrival order), exactly
research/omen_metrics.py::first_of_day_arm -- the same 498-session honest
book main() already headlines. Entry and stop are the book's own (already
walked once by the shipped engine to fire); only the TARGET moves.

MECHANICS (this sweep's own rules, stated once, applied at every N):
  - stop is fixed at the book's stop; risk = |entry - stop| is unchanged by N,
    so the min_risk_floor size gate drops the exact same rows at every N --
    the arms are comparable on an identical n.
  - both stop and target are TOUCH based (bar high/low), because the
    fleet-wide rule for this sweep is explicit: "A bar touching both a
    target and the stop goes to the STOP. Within-bar ordering is unknowable
    on 1-minute OHLC." A stop touch fills AT THE STOP PRICE, never worse
    (Austin R1: max loss is -1R hard, the level stop is final -- this is
    also what the book's own rows do: every stop-out in bt2y_trades_retest_on
    fills at exactly the stop price).
  - walk starts at entry_i + 1 (management starts the bar AFTER the fill bar,
    the shipped convention) and stops at the 11:00 SESSION_END cutoff or the
    end of the day's RTH bars, whichever is first.
  - no touch by the cutoff: flat exit at the last in-window bar's close.
  - NOT modelled here: R2 (the entry-candle-revisit "dead trade" exit). That
    is an exit-management rule orthogonal to the target LEVEL question this
    slice answers, and its exact trigger point is not specified precisely
    enough to encode without guessing. Flagged as a gap, not silently
    folded in.

Usage:
    python research/sweep_targets_flat.py
Writes:
    research/sweep_targets_flat.json
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import polygon_feed as pf                      # noqa: E402  (not being edited)
from omen_metrics import (                      # noqa: E402
    ev_r_scoreboard, evaluate_prop_challenge, first_of_day_arm, min_risk_floor,
    MIN_RISK_FLOOR_SOURCE,
)

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_PATH = os.path.join(HERE, "sweep_targets_flat.json")
CUTOFF_TS = "11:00:00"
RISK_DOLLARS = 1000.0
ACCOUNT = 50000.0
RISK_LEVELS = (100, 250, 500, 1000, 2000, 5000)

# 1.00R .. 6.00R inclusive, 0.25R steps -> 21 arms
TARGETS = [round(1.0 + 0.25 * i, 2) for i in range(21)]

_day_cache: dict = {}


def day_bars(sym, day):
    k = (sym, day)
    if k in _day_cache:
        return _day_cache[k]
    if len(_day_cache) > 600:
        _day_cache.clear()
    try:
        bars = pf.rth(pf.fetch_day(sym, day))
    except Exception:
        bars = []
    _day_cache[k] = bars
    return bars


def cutoff_idx(bars):
    for j, c in enumerate(bars):
        if c.timestamp >= CUTOFF_TS:
            return j
    return len(bars)


def resim_r(row, bars, target_mult):
    """R-multiple for `row` under a flat target of `target_mult` * R, walking
    `bars` causally from entry_i+1. Returns (r, exit_reason)."""
    entry_i = row["entry_i"]
    if entry_i is None or entry_i >= len(bars):
        return None, "no_entry_bar"
    entry_px = row["entry"]
    stop_px = row["stop"]
    risk = abs(entry_px - stop_px)
    if risk <= 0:
        return None, "zero_risk"
    long = row["side"] == "L"
    target_px = entry_px + target_mult * risk if long else entry_px - target_mult * risk

    cut = cutoff_idx(bars)
    start = entry_i + 1
    if start >= min(cut, len(bars)):
        return 0.0, "no_bars_after_entry"

    last_close = bars[min(cut, len(bars)) - 1].close
    for j in range(start, min(cut, len(bars))):
        c = bars[j]
        hit_stop = (c.low <= stop_px) if long else (c.high >= stop_px)
        hit_tgt = (c.high >= target_px) if long else (c.low <= target_px)
        if hit_stop:
            return -1.0, "stop"
        if hit_tgt:
            return float(target_mult), "target"
        last_close = c.close

    r = (last_close - entry_px) / risk if long else (entry_px - last_close) / risk
    return r, "eod_flat"


def main():
    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in rows})
    firsts = first_of_day_arm(rows)
    print("book: %s -- %d sessions, %d first-of-day candidates"
          % (os.path.basename(BOOK_PATH), sessions, len(firsts)))

    # pre-fetch bars once per (sym, day) present in the first-of-day arm
    need = sorted({(r["sym"], r["day"]) for r in firsts})
    print("fetching/loading %d symbol-day bar sets (cache-first)..." % len(need))
    for i, (sym, day) in enumerate(need):
        day_bars(sym, day)
        if i and i % 100 == 0:
            print("  %d / %d" % (i, len(need)))

    reasons_by_n = {n: {} for n in TARGETS}
    arms = {}
    for n in TARGETS:
        scored_rows = []
        exit_reasons = {}
        for row in firsts:
            bars = day_bars(row["sym"], row["day"])
            r, reason = resim_r(row, bars, n)
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
            if r is None:
                continue
            scored_rows.append({
                "r": r, "day": row["day"], "entry": row["entry"],
                "stop": row["stop"], "close": row["entry"],
            })
        reasons_by_n[n] = exit_reasons
        sb = ev_r_scoreboard(scored_rows, risk_dollars=RISK_DOLLARS, sessions=sessions)

        # prop-eval: same R stream, several risk-per-trade dollar levels
        sizeable = [row for row in scored_rows]
        # ev_r_scoreboard already applied the size gate internally to produce
        # sb; rebuild the identical sizeable subset here (same gate fn) so
        # the prop-eval curve is scored on exactly the trades sb counted.
        from omen_metrics import _row_is_sizeable
        gated = [row for row in scored_rows if _row_is_sizeable(row)]

        prop_results = {}
        best_pass = None
        for risk_per_trade in RISK_LEVELS:
            daily = [(row["day"], row["r"] * risk_per_trade) for row in gated]
            res = evaluate_prop_challenge(daily, account_size=ACCOUNT)
            prop_results[risk_per_trade] = {
                "passed": res["passed"], "fail_reason": res["fail_reason"],
                "fail_day": res["fail_day"],
                "final_equity_pct": res["final_equity_pct"],
                "max_drawdown_seen_pct": res["max_drawdown_seen_pct"],
            }
            if res["passed"] and best_pass is None:
                best_pass = risk_per_trade

        hit_rate = (sum(1 for row in gated if row["r"] > 0) / len(gated)
                    if gated else None)

        arms[n] = {
            "target_R": n,
            "ev_r": sb["ev_r"],
            "n": sb["n"],
            "n_dropped_size_gate": sb["n_dropped_size_gate"],
            "win_rate": sb["win_rate"],
            "hit_rate": round(hit_rate, 4) if hit_rate is not None else None,
            "avg_win_R": sb["avg_win_R"],
            "avg_loss_R": sb["avg_loss_R"],
            "profit_factor": sb["profit_factor"],
            "total_R": sb["total_R"],
            "yearly_R": sb["yearly_R"],
            "max_drawdown_R": sb["max_drawdown_R"],
            "months_green": sb["months_green"],
            "expectancy_per_day": sb["expectancy_per_day"],
            "prop_eval_at_1000": prop_results[1000],
            "prop_eval_any_pass_risk": best_pass,
            "prop_eval_by_risk": prop_results,
            "exit_reasons": exit_reasons,
        }
        print("  N=%4.2fR  ev_r=%+.4f  n=%3d  win=%5.1f%%  hit=%5.1f%%  "
              "PF=%s  months=%s  $1000/trade PASS=%s (%s)  any-size PASS=%s"
              % (n, sb["ev_r"], sb["n"], (sb["win_rate"] or 0) * 100,
                 (hit_rate or 0) * 100, sb["profit_factor"], sb["months_green"],
                 prop_results[1000]["passed"], prop_results[1000]["fail_reason"],
                 best_pass))

    ev_best = max(arms.values(), key=lambda a: (a["ev_r"] if a["ev_r"] is not None else -99))
    passers = [a for a in arms.values() if a["prop_eval_at_1000"]["passed"]]
    any_size_passers = [a for a in arms.values() if a["prop_eval_any_pass_risk"] is not None]

    out = {
        "book": os.path.basename(BOOK_PATH), "sessions": sessions,
        "n_first_of_day": len(firsts), "targets_swept": TARGETS,
        "n_arms": len(TARGETS), "risk_dollars": RISK_DOLLARS,
        "account_size": ACCOUNT, "risk_levels_swept": list(RISK_LEVELS),
        "arms": arms,
        "ev_maximizing_target": ev_best["target_R"],
        "ev_maximizing_ev_r": ev_best["ev_r"],
        "prop_eval_maximizing_at_1000": [a["target_R"] for a in passers],
        "prop_eval_maximizing_any_size": [
            (a["target_R"], a["prop_eval_any_pass_risk"]) for a in any_size_passers
        ],
        "same_target": (bool(passers) and ev_best["target_R"] in
                        [a["target_R"] for a in passers]),
        "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
        "not_modelled": ["R2 entry-candle-revisit exit"],
    }
    json.dump(out, open(OUT_PATH, "w", encoding="utf-8"), indent=1)
    print("\nwrote %s" % OUT_PATH)
    print("EV-maximising target: %.2fR (ev_r=%+.4f)" % (ev_best["target_R"], ev_best["ev_r"]))
    print("prop-eval PASS at $1000/trade: %s" % ([a["target_R"] for a in passers] or "NONE"))
    print("prop-eval PASS at ANY swept size: %s" %
          ([(a["target_R"], a["prop_eval_any_pass_risk"]) for a in any_size_passers] or "NONE"))


if __name__ == "__main__":
    main()
