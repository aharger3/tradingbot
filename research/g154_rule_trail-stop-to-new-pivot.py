"""g154/F5 -- "trail stop to new pivot" (candidate: trail-stop-to-new-pivot).
polarity: S-indicator (exit-side).

Austin's own words (row F5): "Once a trade has moved favourably -- the second
push after an initial hold -- the stop should be raised to the newly formed,
tighter pivot level rather than left at the original structural stop."

THIS IS AN EXIT-SIDE ARM. It cannot change which day is traded: the
one-trade-a-day pick (`omen_metrics.first_of_day_arm`, arrival order, size
gate on `signal_runner.min_risk_floor`) is computed ONCE from the committed
book's own status/traded fields and is IDENTICAL for every arm -- recall and
precision are therefore identical for baseline and candidate, by
construction, and are reported once.

PREDICATE, exactly as specced: after entry, replay bars one at a time. On
each CLOSED bar (i.e. once its neighbours exist), look for the most recent
3-bar pivot in the trade's favour -- a bar whose Low is below both immediate
neighbours (for a call) or whose High is above both immediate neighbours
(for a put). The instant such a pivot is confirmed (its right-neighbour bar
has closed, i.e. one bar AFTER the pivot bar -- no lookahead: you cannot
know a bar is a pivot until the bar after it exists), move the working stop
to that pivot's price (Low for a call, High for a put) if it is TIGHTER than
the current working stop (closer to price / further from the original risk)
and still on the SAFE side of entry (never trails past entry into a stop
that would produce a *better* than break-even floor before price has earned
it -- i.e. the new stop may not exceed entry). This is a strict tightening
predicate: the stop only ever moves toward price, never back out, and never
past entry.

Replayed through `stop_rule.stop_fill_price` -- the one fill definition, no
local reimplementation. Reported on ALL traded rows (the whole first-of-day
book), not winners only: restricting to winners is the look-ahead that makes
a trailing-stop arm look free (a rule that only tightens winners' stops and
is silently never applied to losers would show no downside by construction).

REPLAY MODEL (deliberately simple, full position, no partial-scale P&L
blending -- matching the convention of g154_rule_be-stop-after-enough-past-
pt1.py so this A/B isolates the trailing rule alone):

  For each first-of-day pick, replay 1-minute RTH bars from `data_archive`
  (via `t8_two_year.rth_candles`), starting the bar AFTER the signal/entry
  bar (`row['et']`), in chronological order. Every bar, in this order:
    1. disaster-stop touch (intrabar) at the book's own recorded original
       stop-derived disaster level, only while the working stop has not yet
       moved past it favourably enough to make the disaster level
       unreachable -- mirrors `backtest_week.py`'s R1/R2 reasoning: once the
       working stop sits at or past the disaster price on the safe side,
       the disaster order cannot fire first. `stop_rule.disaster_stop_price`,
       `DISASTER_STOP_R=1.0`.
    2. level-stop CLOSE trigger at the current working stop.
       `stop_rule.stop_hit_on_close` + `stop_rule.stop_fill_price`.
    3. target touch, at the book's own recorded `target` price (intrabar
       touch, this codebase's default TARGET_ON_CLOSE=0 semantics).
    4. THEN: pivot detection using this bar as the "middle" of a 3-bar
       window (bars[i-1], bars[i], bars[i+1] must all exist -- i.e. this
       bar's neighbour ahead has already closed by the time we act, so
       detection happens one bar AFTER the candidate pivot bar closes; no
       lookahead). If bars[i-1] is a favourable pivot (Low below both
       neighbours for a call / High above both neighbours for a put), and
       its price is TIGHTER than the working stop and does not exceed
       entry (safe side), move the working stop there -- effective from
       the NEXT bar onward (the bar that confirmed the pivot has already
       been tested against the OLD stop above, so no lookahead within the
       bar).

  A day whose bars run out before any exit (rare, session-end) falls back to
  the book's own recorded `r` for both baseline and candidate, identically,
  so the fallback biases neither arm; the count is reported.

BASELINE here is this script's own no-trail replay (identical replay model,
pivot search disabled) -- not the book's own recorded r -- so the A/B
isolates the trailing rule from any difference between this simplified
replay and the shipped ladder.

PRIOR ART reused, not re-derived: `research/g86_honest_ceiling.py` (stats(),
ekey(), RISK), `research/g91_lane_slice.py` (lane-slice reporting pattern),
`research/omen_metrics.py` (first_of_day_arm, the size gate),
`research/marks_pool.py` (canonical grade pool), `research/build_deck.py`
(mark-file reader, 34-card sweep), `research/t8_two_year.py` (rth_candles,
the data_archive-backed bar reader), `stop_rule.py` (the one stop trigger +
fill), and directly modeled on
`research/g154_rule_be-stop-after-enough-past-pt1.py`'s replay skeleton.

    python research/g154_rule_trail-stop-to-new-pivot.py

Writes research/g154_rule_trail-stop-to-new-pivot.{md,json}.
Applies nothing, ships nothing. Read-only on the book and every mark corpus.
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86             # noqa: E402  stats(), ekey(), RISK
import omen_metrics as om                    # noqa: E402  first_of_day_arm, the size gate
import marks_pool as mp                      # noqa: E402  canonical grade pool
import build_deck as bd                      # noqa: E402  mark-file reader (34-card sweep)
from t8_two_year import rth_candles          # noqa: E402  RTH 1m bars, data_archive-backed
import stop_rule as sru                      # noqa: E402  the one stop trigger + fill

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_trail-stop-to-new-pivot.json")
OUT_MD = os.path.join(HERE, "g154_rule_trail-stop-to-new-pivot.md")

H_SPLIT = "2025-09-01"      # CLAUDE.md-mandated H1/H2 boundary
DISASTER_R = 1.0            # stop_rule.DISASTER_STOP_R, imported by value for clarity


def n_days_in(rows, lo=None, hi=None):
    days = {r["day"] for r in rows}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def _is_pivot(prev_c, mid_c, next_c, long):
    """3-bar pivot in the trade's favour: Low below both neighbours (call),
    High above both neighbours (put)."""
    if long:
        return mid_c.low < prev_c.low and mid_c.low < next_c.low
    return mid_c.high > prev_c.high and mid_c.high > next_c.high


def _safe_tighter(candidate_stop, working_stop, entry, long):
    """Tighter = closer to price / further from the original risk, i.e.
    further in the trade's favour than the current working stop. Safe side
    = may not exceed entry (never trails past breakeven by construction --
    the predicate is a tightening rule, not an aggressive-lock rule)."""
    if long:
        return working_stop < candidate_stop <= entry
    return entry <= candidate_stop < working_stop


def _sim(bars, idx, entry, stop, target, long, use_trail):
    """Replay bars[idx+1:]. use_trail=False is this script's own no-trail
    control (identical replay model, pivot search disabled). Returns
    R-multiple, or None if bars ran out with no exit."""
    risk = abs(entry - stop)
    disaster_price = sru.disaster_stop_price(entry, risk, long, stop_r=DISASTER_R)
    working_stop = stop
    tail = bars[idx + 1:]

    for i, c in enumerate(tail):
        # 1. disaster stop -- only reachable while the working stop has not
        # moved past it on the safe side (mirrors backtest_week's R1/R2
        # reasoning: once the working stop sits between price and the
        # disaster level, the disaster order cannot fire first).
        disaster_superseded = (working_stop >= disaster_price if long
                                else working_stop <= disaster_price)
        if not disaster_superseded:
            dhit = (c.low <= disaster_price) if long else (c.high >= disaster_price)
            if dhit:
                return -DISASTER_R

        # 2. level stop, close-triggered, filled per stop_rule (the one fill)
        if sru.stop_hit_on_close(c.close, working_stop, long):
            fill = sru.stop_fill_price(c.close, entry, risk, long)
            return (fill - entry) / risk if long else (entry - fill) / risk

        # 3. target, intrabar touch
        thit = (c.high >= target) if long else (c.low <= target)
        if thit:
            return (target - entry) / risk if long else (entry - target) / risk

        # 4. pivot detection, one bar after the candidate pivot bar closes
        # (no lookahead: bars[i-1] is confirmed a pivot only once bars[i]
        # -- its right neighbour -- has already closed and been tested
        # above against the OLD stop).
        if use_trail and i >= 2:
            prev_c, mid_c, next_c = tail[i - 2], tail[i - 1], c
            if _is_pivot(prev_c, mid_c, next_c, long):
                cand = mid_c.low if long else mid_c.high
                if _safe_tighter(cand, working_stop, entry, long):
                    working_stop = cand
    return None   # bars exhausted before any exit


def replay_row(row):
    """(baseline_r_no_trail, trail_r) for one first-of-day pick, or None if
    bars/entry bar are unavailable (caller falls back to the book's own r
    for both arms)."""
    bars = rth_candles(row["sym"], row["day"])
    if not bars:
        return None
    entry_ts = row["et"] + ":00"
    idx = next((i for i, c in enumerate(bars) if c.timestamp == entry_ts), None)
    if idx is None:
        return None
    entry, stop, target = row["entry"], row["stop"], row.get("target")
    if target is None:
        return None
    long = row["dir"] == "call"
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    base_r = _sim(bars, idx, entry, stop, target, long, use_trail=False)
    trail_r = _sim(bars, idx, entry, stop, target, long, use_trail=True)
    return base_r, trail_r


def build_lists(firsts):
    """Returns (baseline_rows, trail_rows, n_fallback) -- copies of `firsts`
    with 'r'/'pnl' overwritten by the replay (or left at the book's own
    value when replay is unavailable). Fallback rows are IDENTICAL across
    both arms, so they bias neither side of the A/B. ALL traded rows are
    included -- winners and losers alike (never restrict to winners)."""
    n_fallback = 0
    baseline_rows, trail_rows = [], []
    for row in firsts:
        rep = replay_row(row)
        base_row, trail_row = dict(row), dict(row)
        if rep is None:
            n_fallback += 1
            # leave r/pnl at the book's own recorded values for both arms
        else:
            base_r, trail_r = rep
            if base_r is None or trail_r is None:
                n_fallback += 1
            else:
                base_row["r"] = base_r
                base_row["pnl"] = base_r * g86.RISK
                trail_row["r"] = trail_r
                trail_row["pnl"] = trail_r * g86.RISK
        baseline_rows.append(base_row)
        trail_rows.append(trail_row)
    return baseline_rows, trail_rows, n_fallback


def s_sweep_keys():
    rows = list(bd._rows(SWEEP_PATH))
    return {"%s_%s" % (r["symbol"], r["date"]) for r in rows if mp.row_grade(r) == "S"}, len(rows)


def recall_and_precision(firsts, pool, s100_keys, bar_backed_s_all):
    """Identical for baseline and candidate (exit-side predicate -- it
    cannot change which day fires). fired_keys = the sym_day of every
    first-of-day pick."""
    fired_keys = {"%s_%s" % (r["sym"], r["day"]) for r in firsts}
    hit100 = sum(1 for k in s100_keys if k in fired_keys)
    hitall = sum(1 for k in bar_backed_s_all if k in fired_keys)

    grade_num = grade_den = 0
    for r in firsts:
        key = "%s_%s" % (r["sym"], r["day"])
        e = pool.get(key)
        if e is None:
            continue
        grade_den += 1
        if e.grade == "S":
            grade_num += 1

    return {
        "recall_100": round(hit100 / len(s100_keys), 4) if s100_keys else None,
        "recall_100_n": len(s100_keys), "recall_100_hits": hit100,
        "recall_all": round(hitall / len(bar_backed_s_all), 4) if bar_backed_s_all else None,
        "recall_all_n": len(bar_backed_s_all), "recall_all_hits": hitall,
        "precision": round(grade_num / grade_den, 4) if grade_den else None,
        "precision_num": grade_num, "precision_den": grade_den,
    }


def half_stats(rows, lo=None, hi=None, n_days=None):
    sub = [r for r in rows if (lo is None or r["day"] >= lo) and (hi is None or r["day"] < hi)]
    return g86.stats(sub, n_days)


def main():
    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or len({r["day"] for r in rows})
    n_days_h1 = n_days_in(rows, hi=H_SPLIT)
    n_days_h2 = n_days_in(rows, lo=H_SPLIT)
    print("book: %s -- %d sessions (H1 %d, H2 %d)"
          % (os.path.basename(BOOK_PATH), n_days, n_days_h1, n_days_h2))

    firsts = om.first_of_day_arm(rows, size_gate=True)
    print("first-of-day arm (size-gated): %d picks (ALL traded rows, winners "
          "and losers alike)" % len(firsts))
    fires_per_day = round(len(firsts) / n_days, 3)

    byday_all = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday_all[r["day"]].append(r)
    candidates_per_day = round(sum(len(v) for v in byday_all.values()) / n_days, 2)

    baseline_rows, trail_rows, n_fallback = build_lists(firsts)
    print("bar replay: %d/%d picks fell back to the book's own r (no bars, no "
          "entry bar match, or exit ran past available data) -- identically "
          "for both arms" % (n_fallback, len(firsts)))

    pool = mp.canonical_pool()
    s100_keys, s100_n_rows = s_sweep_keys()
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}
    rp = recall_and_precision(firsts, pool, s100_keys, bar_backed_s_all)
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (s100_n_rows, len(s100_keys), len(bar_backed_s_all)))
    print("recall_100 %s/%d  recall_all %s/%d  precision %s/%d (identical for "
          "baseline and candidate -- exit-side predicate, day selection unchanged)"
          % (rp["recall_100_hits"], rp["recall_100_n"], rp["recall_all_hits"],
             rp["recall_all_n"], rp["precision_num"], rp["precision_den"]))

    base_full = g86.stats(baseline_rows, n_days)
    base_h1 = half_stats(baseline_rows, hi=H_SPLIT, n_days=n_days_h1)
    base_h2 = half_stats(baseline_rows, lo=H_SPLIT, n_days=n_days_h2)
    print("\nBASELINE (this script's own no-trail replay): $%d/day (H1 $%d, H2 $%d), "
          "mean R %.3f, win %.1f%%, months green %d/%d, maxDD $%d"
          % (base_full["per_day"], base_h1.get("per_day", 0), base_h2.get("per_day", 0),
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["worst_drawdown"]))

    trail_full = g86.stats(trail_rows, n_days)
    trail_h1 = half_stats(trail_rows, hi=H_SPLIT, n_days=n_days_h1)
    trail_h2 = half_stats(trail_rows, lo=H_SPLIT, n_days=n_days_h2)
    h1_delta = trail_h1.get("per_day", 0) - base_h1.get("per_day", 0)
    h2_delta = trail_h2.get("per_day", 0) - base_h2.get("per_day", 0)
    h1_improves = h1_delta > 0
    h2_improves = h2_delta > 0
    recall_ok = (rp["recall_100"] or 0) >= (rp["recall_100"] or 0)  # identical by construction
    survivor = bool(h1_improves and h2_improves and recall_ok)
    print("\nCANDIDATE (trail stop to newest favourable 3-bar pivot, tighter "
          "and safe-side only): $%d/day (H1 $%d [%+d], H2 $%d [%+d]), mean R "
          "%.3f, win %.1f%%, months green %d/%d, maxDD $%d -- survivor=%s"
          % (trail_full["per_day"], trail_h1.get("per_day", 0), h1_delta,
             trail_h2.get("per_day", 0), h2_delta, trail_full["mean_r"],
             trail_full["win_pct"], trail_full["months_green"], trail_full["months"],
             trail_full["worst_drawdown"], survivor))

    out = {
        "book": os.path.basename(BOOK_PATH), "sessions": n_days,
        "sessions_h1": n_days_h1, "sessions_h2": n_days_h2,
        "rule": "trail-stop-to-new-pivot",
        "polarity": "S-indicator",
        "predicate": "After entry, on each new bar find the most recent "
                     "3-bar pivot in the trade's favour (Low below both "
                     "neighbours for a call, High above both neighbours for "
                     "a put); move the working stop there when it is "
                     "TIGHTER than the current stop and still on the safe "
                     "side of entry (may not exceed entry). Replayed "
                     "through stop_rule.stop_fill_price.",
        "candidates_per_day": candidates_per_day, "fires_per_day": fires_per_day,
        "n_fallback_to_book_r": n_fallback, "n_picks": len(firsts),
        "recall_precision": rp,
        "baseline_no_trail": {"full": base_full, "h1": base_h1, "h2": base_h2},
        "candidate_trail": {"full": trail_full, "h1": trail_h1, "h2": trail_h2},
        "h1_delta_usd_day": round(h1_delta, 2),
        "h2_delta_usd_day": round(h2_delta, 2),
        "survivor": survivor,
        "survivor_rule": "H1 AND H2 both improve $/day vs. this script's own "
                          "no-trail replay baseline, recall_100 not below "
                          "baseline (identical by construction for an "
                          "exit-side predicate).",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g154/F5 -- trail-stop-to-new-pivot", "",
          "**What is different now:** measured Austin's trailing-stop claim "
          "-- once a trade has pushed favourably a second time after an "
          "initial hold, raise the stop to the newest, tighter 3-bar pivot "
          "rather than leaving it at the original structural stop -- on the "
          "honest book, reported on ALL traded rows (winners and losers), "
          "not winners only.", "",
          "Book `%s`, %d sessions (H1 %d / H2 %d), size-gated on "
          "`signal_runner.min_risk_floor`. 1R = $%d. H1/H2 split at %s."
          % (os.path.basename(BOOK_PATH), n_days, n_days_h1, n_days_h2,
             int(g86.RISK), H_SPLIT), "",
          "This is an EXIT-SIDE arm: it cannot change which day trades. "
          "candidates/day %.2f, fires/day %.3f, recall_100 %s/%d, recall_all "
          "%s/%d, precision %s/%d -- identical for baseline and candidate by "
          "construction. %d/%d picks fell back to the book's own recorded r "
          "(no bars, no entry-bar match, or exit ran past available data), "
          "identically for both arms."
          % (candidates_per_day, fires_per_day, rp["recall_100_hits"], rp["recall_100_n"],
             rp["recall_all_hits"], rp["recall_all_n"], rp["precision_num"],
             rp["precision_den"], n_fallback, len(firsts)), "",
          "| arm | split | $/day | mean R | win | months green | max DD |",
          "|---|---|---:|---:|---:|---:|---:|",
          "| baseline (no trail) | all | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_full["per_day"], base_full["mean_r"], base_full["win_pct"],
             base_full["months_green"], base_full["months"], base_full["worst_drawdown"]),
          "| baseline (no trail) | H1 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_h1.get("per_day", 0), base_h1.get("mean_r", 0), base_h1.get("win_pct", 0),
             base_h1.get("months_green", 0), base_h1.get("months", 0),
             base_h1.get("worst_drawdown", 0)),
          "| baseline (no trail) | H2 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_h2.get("per_day", 0), base_h2.get("mean_r", 0), base_h2.get("win_pct", 0),
             base_h2.get("months_green", 0), base_h2.get("months", 0),
             base_h2.get("worst_drawdown", 0)),
          "| candidate (trail to pivot) | all | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (trail_full["per_day"], trail_full["mean_r"], trail_full["win_pct"],
             trail_full["months_green"], trail_full["months"], trail_full["worst_drawdown"]),
          "| candidate (trail to pivot) | H1 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (trail_h1.get("per_day", 0), trail_h1.get("mean_r", 0), trail_h1.get("win_pct", 0),
             trail_h1.get("months_green", 0), trail_h1.get("months", 0),
             trail_h1.get("worst_drawdown", 0)),
          "| candidate (trail to pivot) | H2 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (trail_h2.get("per_day", 0), trail_h2.get("mean_r", 0), trail_h2.get("win_pct", 0),
             trail_h2.get("months_green", 0), trail_h2.get("months", 0),
             trail_h2.get("worst_drawdown", 0)),
          "", "delta $/day vs baseline: H1 %+.2f, H2 %+.2f." % (h1_delta, h2_delta), "",
          "## Verdict", "",
          "Survivor (H1 AND H2 both improve $/day vs. this script's own "
          "no-trail replay baseline, recall_100 not below baseline -- "
          "identical by construction for an exit-side predicate): **%s**."
          % survivor, "",
          "Recall/precision cannot move for an exit-side predicate -- they "
          "are reported once, not per-arm, and are identical to whatever the "
          "shipped one-trade-a-day arm already fires on this book."]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
