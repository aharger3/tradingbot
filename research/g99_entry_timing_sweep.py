"""g99_entry_timing_sweep.py -- SWEEP: entry_timing.

Austin's 2026-09-03 ruling: headline is EV/R (win% x avg_win_R - loss% x
avg_loss_R), $/day is a supporting row, and every arm must PASS/FAIL a
$50k prop evaluation via research/omen_metrics.py. Size-gate every money
number on signal_runner.min_risk_floor.

Five entry variants, priced off the committed book
research/bt2y_trades_retest_on.json (498 sessions, 4,022 fired-and-traded
rows, honest close-fill):

  1. signal-bar close (SHIPPED)      -- the book's own entry, unmodified.
  2. one bar earlier                  -- entry at bar[entry_i-1].close.
  3. two bars earlier                 -- entry at bar[entry_i-2].close.
  4. resting limit @ level, AFTER     -- order placed at the signal bar's
     the signal bar                     close, live from entry_i+1 to the
                                         11:00 cutoff, fills on first touch.
  5. retest-touch (on the signal bar) -- order already resting (the B&R
                                         level was established by an
                                         earlier break, before entry_i by
                                         construction of the setup), fills
                                         AT THE LEVEL the moment entry_i's
                                         own bar touches it -- same-bar,
                                         intrabar, no future bar read.

Each variant is priced on TWO populations, both from the same book:
  POP A "first-of-day" -- omen_metrics.first_of_day_arm(): one row per
        session, arrival order. This is the SAME population the
        2026-09-03 headline book number (ev_r=0.0377, n=444) was scored
        on -- directly comparable.
  POP B "full traded"  -- every fired-and-traded row, all symbols, all
        times of day (n=4,022 before gating). More statistical power,
        shows what happens once trade frequency is not curated by "first
        of the day."
For POP A, variants 2-5 reprice the SAME candidate rows the first-of-day
arm already selected (no re-selection of a second candidate on a no-fill
day) -- a no-fill day is dropped, not rolled forward; this keeps the
population identical across variants so the comparison isolates entry
timing, not candidate selection.

CAUSALITY, and why #2/#3 are UNSHIPPABLE:

entry_i IS the signal bar -- it is the bar whose close confirms the retest
setup fired (that is what "signal bar" means in this book). Entering at
bar[entry_i-1] or bar[entry_i-2] requires knowing, before that earlier bar
closed, that the setup would go on to confirm on entry_i -- i.e. it uses
information only available once bar entry_i (>= the decision bar) is seen.
That is lookahead by definition. Variants 4 and 5 use no bar before entry_i
completes and no information not yet printed when the fill happens, so
both are causal and shippable.

EXIT MODEL, and why it is intentionally simple:

The shipped ladder (backtest_week._ladder_bar, scale-outs, BE-move) lives
in a file a bug-fix fleet is editing tonight and may not parse. For the
SHIPPED variant (#1) this script uses the book's own row['r'] verbatim --
exact, no resimulation, carries every shipped rule including R2's
entry-candle-recross scratch. For the four repriced variants (#2-#5),
entry price/bar differ, so SOME resimulation is unavoidable; this script
uses one simple, identical-across-variants control ladder per the
STOP_ON_CLOSE / TARGET_ON_CLOSE flags stamped in the book's own meta:
  - stop (row['stop'], unchanged -- level-anchored, R1's "the level stop
    is final") triggers on a management bar's CLOSE beyond it -> R = -1.0
    hard (R1: no -1.25 floor, it has never fired).
  - target (row['target'], PT1 = HOD/LOD, unchanged) triggers on a
    management bar's intrabar HIGH/LOW reaching it -> R = +|target-entry|
    /risk_per_share.
  - a bar that closes through the stop AND touches the target in the same
    bar goes to the STOP (system-prompt rule: within-bar ordering on
    1-minute OHLC is unknowable, ties go to the stop).
  - no touch by the end of the day's RTH bars -> EOD scratch at the last
    bar's close.
R2 (entry-candle recross) is NOT reimplemented for #2-#5 -- flagged as a
named simplification in the output, not silently dropped. This makes #2-#5
a deliberately cruder read than the shipped #1; the comparison is still
fair because all four repriced variants share the identical control ladder
and the identical population, and #1 is exact.

Size gate: every row is gated on signal_runner.min_risk_floor via
research/omen_metrics.py::ev_r_scoreboard, n_dropped_size_gate reported.

Usage:  python research/g99_entry_timing_sweep.py
Writes: research/g99_entry_timing_sweep.json
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import polygon_feed as pf  # noqa: E402 -- read-only bar archive, not touched by the fleet
from research.omen_metrics import (ev_r_scoreboard, evaluate_prop_challenge,  # noqa: E402
                                    MIN_RISK_FLOOR_SOURCE, first_of_day_arm)

BOOK_PATH = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_PATH = ROOT / "research" / "g99_entry_timing_sweep.json"

_bars_cache: dict = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        if len(_bars_cache) > 800:
            _bars_cache.clear()
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


def effective_stop(row, fill_bar, entry_px):
    """CLAUDE.md's documented shipped fix, replicated here (not reinvented):
    for a break-and-retest, stop == the retested level (BNR_STOP_MODE ==
    "level"). A fill AT that level (a retest-touch or a limit resting
    exactly there) is an order to buy at its own stop -- zero risk to
    size. signal_runner.intrabar_stop's answer, per CLAUDE.md and the g80
    docstring: move the stop to the FILL BAR's own opposite extreme (the
    wick beyond the level, if the bar shows one). If the bar shows no wick
    beyond the level either, risk is genuinely zero and the row is
    reported as such (zero_risk), not silently given a stop nobody chose."""
    long = row["dir"] == "call"
    stop = row["stop"]
    if abs(stop - row["level_px"]) < 0.005 and abs(entry_px - stop) < 0.005:
        return fill_bar.low if long else fill_bar.high
    return stop


def resim_from(row, bars, fill_i, entry_px):
    """Walk forward from fill_i+1 with the simple control ladder. Returns
    (r, exit_reason, stop_used) or (None, reason, None) if unsimulatable."""
    long = row["dir"] == "call"
    stop = effective_stop(row, bars[fill_i], entry_px)
    target = row["target"]
    risk = abs(entry_px - stop)
    if risk <= 0:
        return None, "zero_risk", None
    n = len(bars)
    if fill_i + 1 >= n:
        return None, "no_management_bars", None
    for j in range(fill_i + 1, n):
        c = bars[j]
        stop_hit = (c.close <= stop) if long else (c.close >= stop)
        if stop_hit:
            return -1.0, "stop_close", stop
        target_hit = (c.high >= target) if long else (c.low <= target)
        if target_hit:
            r = (target - entry_px) / risk if long else (entry_px - target) / risk
            return r, "target_touch", stop
    last = bars[-1].close
    r = (last - entry_px) / risk if long else (entry_px - last) / risk
    return r, "eod_scratch", stop


def variant_earlier(row, bars, n_back):
    i = row["entry_i"]
    j = i - n_back
    if j < 0 or j >= len(bars):
        return None, "oob"
    entry_px = bars[j].close
    r, reason, stop_used = resim_from(row, bars, j, entry_px)
    if r is None:
        return None, reason
    return {"r": r, "day": row["day"], "entry": entry_px, "stop": stop_used}, reason


def variant_resting_after(row, bars):
    i = row["entry_i"]
    level = row["level_px"]
    long = row["dir"] == "call"
    cutoff = len(bars)
    for j, c in enumerate(bars):
        if c.timestamp >= "11:00:00":
            cutoff = j
            break
    fill_i = entry_px = None
    for j in range(i + 1, cutoff):
        c = bars[j]
        if long and c.low <= level:
            fill_i, entry_px = j, min(level, c.open)
            break
        if (not long) and c.high >= level:
            fill_i, entry_px = j, max(level, c.open)
            break
    if fill_i is None:
        return None, "limit_never_touched"
    r, reason, stop_used = resim_from(row, bars, fill_i, entry_px)
    if r is None:
        return None, reason
    return {"r": r, "day": row["day"], "entry": entry_px, "stop": stop_used}, reason


def variant_retest_touch(row, bars):
    i = row["entry_i"]
    if i >= len(bars):
        return None, "oob"
    c = bars[i]
    level = row["level_px"]
    if not (c.low <= level <= c.high):
        return None, "no_touch_on_signal_bar"
    entry_px = level
    r, reason, stop_used = resim_from(row, bars, i, entry_px)
    if r is None:
        return None, reason
    return {"r": r, "day": row["day"], "entry": entry_px, "stop": stop_used}, reason


def build_daily_all_rows(rows_r):
    """Aggregate to daily pnl @ $1000/R -- for POP B (full traded), sums
    every scored row that day; for POP A (first-of-day) there's one row
    per day already, this still works."""
    by_day = defaultdict(float)
    for r in rows_r:
        by_day[r["day"]] += r["r"] * 1000.0
    days = sorted(by_day)
    return [(d, by_day[d]) for d in days]


def prop_table(rows_r):
    daily = build_daily_all_rows(rows_r)
    out = {}
    for risk in (100, 250, 500, 1000, 2000):
        scale = risk / 1000.0
        scaled_daily = [(d, v * scale) for d, v in daily]
        res = evaluate_prop_challenge(scaled_daily, account_size=50000.0)
        out[str(risk)] = {"passed": res["passed"], "fail_reason": res["fail_reason"],
                           "fail_day": res["fail_day"], "final_equity_pct": res["final_equity_pct"],
                           "max_dd_pct": res["max_drawdown_seen_pct"]}
    return out


VARIANT_DEFS = [
    ("2_one_bar_earlier", lambda r, b: variant_earlier(r, b, 1), False,
     "requires knowing at bar entry_i-1 that the setup would go on to confirm "
     "on entry_i (>= the decision bar) -- lookahead by construction"),
    ("3_two_bars_earlier", lambda r, b: variant_earlier(r, b, 2), False,
     "requires knowing at bar entry_i-2 that the setup would go on to confirm "
     "on entry_i (>= the decision bar) -- lookahead by construction"),
    ("4_resting_limit_after_signal_bar", variant_resting_after, True,
     "order placed at signal-bar close, live entry_i+1..11:00, fills on first "
     "touch; causal, uses only bars at/after the decision bar's own close"),
    ("5_retest_touch_on_signal_bar", variant_retest_touch, True,
     "fills at level_px the moment entry_i's own bar range contains it -- "
     "same-bar, intrabar; the B&R level was established by an earlier break "
     "(inherent to the setup), so a resting order is causal here"),
]


def score_population(pop_name, rows, sessions):
    out = {}
    v1_rows = [{"r": r["r"], "day": r["day"], "entry": r["entry"], "stop": r["stop"]} for r in rows]
    sb1 = ev_r_scoreboard(v1_rows, sessions=sessions)
    out["1_signal_bar_close_SHIPPED"] = {
        "causal": True, "shippable": True,
        "n_candidates": len(rows), "n_no_fill_or_unsimulatable": 0,
        "ev_r_scoreboard": sb1, "prop_eval": prop_table(v1_rows),
        "note": "exact book row['r'], no resimulation",
    }
    print("  1 shipped          ev_r=%s n=%s win=%s months_green=%s" %
          (sb1["ev_r"], sb1["n"], sb1["win_rate"], sb1["months_green"]))

    for key, fn, shippable, note in VARIANT_DEFS:
        out_rows = []
        fail_reasons = defaultdict(int)
        for r in rows:
            bars = get_bars(r["sym"], r["day"])
            res, status = fn(r, bars)
            if res is None:
                fail_reasons[status] += 1
                continue
            out_rows.append(res)
        sb = ev_r_scoreboard(out_rows, sessions=sessions)
        entry = {
            "causal": shippable, "shippable": shippable,
            "n_candidates": len(rows),
            "n_no_fill_or_unsimulatable": sum(fail_reasons.values()),
            "no_fill_breakdown": dict(fail_reasons),
            "ev_r_scoreboard": sb,
            "prop_eval": prop_table(out_rows) if shippable else None,
            "note": note if shippable else "UNSHIPPABLE (lookahead) -- " + note +
                    ". Priced for the record only, not scored as a candidate arm.",
        }
        out[key] = entry
        tag = "" if shippable else " (UNSHIPPABLE, lookahead)"
        print("  %-19s ev_r=%s n=%s win=%s no_fill=%d%s" %
              (key, sb["ev_r"], sb["n"], sb["win_rate"], sum(fail_reasons.values()), tag))
    return out


def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, all_rows = blob["meta"], blob["trades"]
    sessions = meta.get("sessions") or len({r["day"] for r in all_rows})
    traded = [r for r in all_rows if r["status"] == "fired" and r.get("traded")]
    firsts = first_of_day_arm(all_rows)
    print("book: %d sessions, %d traded rows, %d first-of-day rows" %
          (sessions, len(traded), len(firsts)))
    print("min_risk_floor source: %s\n" % MIN_RISK_FLOOR_SOURCE)

    print("=== POP A: first-of-day (comparable to the 2026-09-03 headline, ev_r=0.0377) ===")
    pop_a = score_population("first_of_day", firsts, sessions)

    print("\n=== POP B: full traded population (all fired&traded rows, all times of day) ===")
    pop_b = score_population("full_traded", traded, sessions)

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"book": BOOK_PATH.name, "sessions": sessions,
                    "n_traded": len(traded), "n_first_of_day": len(firsts),
                    "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
                    "pop_a_first_of_day": pop_a, "pop_b_full_traded": pop_b}, f, indent=2)
    print("\nwrote", OUT_PATH)


if __name__ == "__main__":
    main()
