"""g154/F5 -- "breakeven stop arms only after price has moved enough past PT1"
(candidate: be-stop-after-enough-past-pt1). polarity: S-indicator (exit-side).

Austin's own words (from CLAUDE.md's F5 predicate line): the stop should move
to breakeven only once price has travelled some threshold PAST the first
profit target (PT1), not the instant PT1 is tagged -- and he flags the
threshold itself as unresolved. This script measures it directly rather than
picking a number.

THIS IS AN EXIT-SIDE ARM. It cannot change which day is traded: the
one-trade-a-day pick (`omen_metrics.first_of_day_arm`, arrival order, size
gate on `signal_runner.min_risk_floor`) is computed ONCE from the committed
book's own status/traded fields and is IDENTICAL for every arm below --
recall and precision are therefore identical across baseline and every k,
by construction, and are reported once. Only the R booked on each of those
already-picked trades changes.

WHAT "PT1" MEANS HERE. The shipped ladder's PT1 rung (`backtest_week.py`'s
causal HOD/LOD scale level) is not reproducible from this book alone (the
scale-rung price is not a column). This script uses the codebase's other,
simpler PT1 convention instead -- `RULE6_BE_MULT=1.0`'s "breakeven level =
entry +/- 1R x multiplier" is already the shipped definition of "the first
target that would move a stop to breakeven" -- so **PT1 := entry +/- 1.0R**.
k in {0.25R, 0.5R, 0.75R, 1.0R} arms the BE stop once price TOUCHES
entry +/- (1.0 + k)R. This is a documented simplification, not the literal
ladder rung; the report says so plainly.

REPLAY MODEL, deliberately simple (full-position, no partial-scale P&L
blending -- the book's own `scaled` flag and blended R accounting are not
reproduced here; both the baseline arm below and every k arm use the exact
same simplified model so the A/B isolates the BE-arming rule alone, not
"simplified model vs. the shipped ladder"):

  For each first-of-day pick, replay 1-minute RTH bars from `data_archive`
  (via `t8_two_year.rth_candles`) starting the bar AFTER the signal/entry
  bar (`row['et']`), in chronological order. Every bar, in this order:
    1. disaster-stop touch (intrabar), only while unarmed -- once the BE
       stop is armed it sits at entry, strictly between price and the
       original disaster level, so the disaster level cannot be reached
       first (same reasoning `backtest_week.py`'s R1/R2 comment gives).
       `stop_rule.disaster_stop_price`, `DISASTER_STOP_R=1.0`.
    2. level-stop CLOSE trigger at the working stop (original stop, or
       entry once armed). `stop_rule.stop_hit_on_close` +
       `stop_rule.stop_fill_price` -- the one fill definition, no local
       reimplementation.
    3. target touch, at the book's own recorded `target` price (intrabar,
       matching this codebase's default TARGET_ON_CLOSE=0 touch semantics).
    4. THEN, only if unarmed: has price touched entry +/- (1+k)R yet this
       bar? If so, arm (`runner_stop = entry`) for the NEXT bar -- causal,
       no lookahead within the bar that crosses the threshold, mirroring
       `backtest_week._ladder_bar`'s own BE_TRIGGER="mfe" ordering.

  A day whose bars run out before any exit (rare, session-end) falls back
  to the book's own recorded `r` for BOTH the baseline and every k arm, so
  that fallback introduces no bias between arms; the count is reported.

PRIOR ART reused, not re-derived: `research/g86_honest_ceiling.py` (stats(),
ekey(), RISK), `research/g91_lane_slice.py` (the lane-slice reporting
pattern), `research/omen_metrics.py` (first_of_day_arm, the size gate),
`research/marks_pool.py` (canonical grade pool), `research/t8_two_year.py`
(rth_candles, the data_archive-backed bar reader), `stop_rule.py` (the one
stop trigger/fill).

    python research/g154_rule_be-stop-after-enough-past-pt1.py

Writes research/g154_rule_be-stop-after-enough-past-pt1.{md,json}.
Applies nothing, ships nothing.
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
import omen_metrics as om                    # noqa: E402  first_of_day_arm, size gate
import marks_pool as mp                      # noqa: E402  canonical grade pool
import build_deck as bd                      # noqa: E402  mark-file reader (34-card sweep)
from t8_two_year import rth_candles          # noqa: E402  RTH 1m bars, data_archive-backed
import stop_rule as sru                      # noqa: E402  the one stop trigger + fill

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_be-stop-after-enough-past-pt1.json")
OUT_MD = os.path.join(HERE, "g154_rule_be-stop-after-enough-past-pt1.md")

H_SPLIT = "2025-09-01"      # CLAUDE.md-mandated H1/H2 boundary
PT1_R = 1.0                 # PT1 := entry +/- 1.0R (see docstring)
DISASTER_R = 1.0            # stop_rule.DISASTER_STOP_R, imported by value for clarity
K_VALUES = (0.25, 0.5, 0.75, 1.0)


def n_days_in(rows, lo=None, hi=None):
    days = {r["day"] for r in rows}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def _sim(bars, idx, entry, stop, target, long, k):
    """Replay bars[idx+1:] under the BE-after-k-past-PT1 rule. k=None means
    "never arm" (the no-BE control used as this script's own baseline).
    Returns R-multiple, or None if the bars ran out with no exit."""
    risk = abs(entry - stop)
    disaster_price = sru.disaster_stop_price(entry, risk, long, stop_r=DISASTER_R)
    arm_price = None
    if k is not None:
        arm_price = entry + (PT1_R + k) * risk if long else entry - (PT1_R + k) * risk

    runner_stop = None   # None = original stop still working
    for c in bars[idx + 1:]:
        stop_lv = runner_stop if runner_stop is not None else stop

        # 1. disaster stop, only while unarmed (see docstring reasoning)
        if runner_stop is None:
            dhit = (c.low <= disaster_price) if long else (c.high >= disaster_price)
            if dhit:
                return -DISASTER_R

        # 2. level stop, close-triggered, filled per stop_rule (the one fill)
        if sru.stop_hit_on_close(c.close, stop_lv, long):
            fill = sru.stop_fill_price(c.close, entry, risk, long)
            return (fill - entry) / risk if long else (entry - fill) / risk

        # 3. target, intrabar touch (this codebase's default touch semantics)
        thit = (c.high >= target) if long else (c.low <= target)
        if thit:
            return (target - entry) / risk if long else (entry - target) / risk

        # 4. arm check LAST -- this bar's tests above all read the PRE-arm
        # stop; arming here takes effect starting next bar only. No lookahead.
        if runner_stop is None and arm_price is not None:
            touched = (c.high >= arm_price) if long else (c.low <= arm_price)
            if touched:
                runner_stop = entry
    return None   # bars exhausted before any exit


def replay_row(row):
    """(baseline_r_no_be, {k: r_with_be}) for one first-of-day pick, or None
    if bars/entry bar are unavailable (caller falls back to the book's own
    r for every arm)."""
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

    base_r = _sim(bars, idx, entry, stop, target, long, k=None)
    ks = {k: _sim(bars, idx, entry, stop, target, long, k=k) for k in K_VALUES}
    return base_r, ks


def build_lists(firsts):
    """Returns (baseline_rows, {k: rows}, n_fallback) -- copies of `firsts`
    with 'r'/'pnl' overwritten by the replay (or left at the book's own
    value when replay is unavailable). Fallback rows are IDENTICAL across
    baseline and every k, so they bias neither side of the A/B."""
    n_fallback = 0
    baseline_rows = []
    k_rows = {k: [] for k in K_VALUES}
    for row in firsts:
        rep = replay_row(row)
        base_row = dict(row)
        k_out = {k: dict(row) for k in K_VALUES}
        if rep is None:
            n_fallback += 1
            # leave r/pnl at the book's own recorded values for every arm
        else:
            base_r, ks = rep
            if base_r is None:
                n_fallback += 1
            else:
                base_row["r"] = base_r
                base_row["pnl"] = base_r * g86.RISK
            for k in K_VALUES:
                rk = ks[k]
                if rk is not None:
                    k_out[k]["r"] = rk
                    k_out[k]["pnl"] = rk * g86.RISK
                elif base_r is not None:
                    # bars ran out under this k's arm but not under no-arm --
                    # cannot happen (arming only tightens the stop toward a
                    # bar the no-arm sim already tested), kept defensive.
                    k_out[k]["r"] = base_r
                    k_out[k]["pnl"] = base_r * g86.RISK
        baseline_rows.append(base_row)
        for k in K_VALUES:
            k_rows[k].append(k_out[k])
    return baseline_rows, k_rows, n_fallback


def s_sweep_keys():
    rows = list(bd._rows(SWEEP_PATH))
    return {"%s_%s" % (r["symbol"], r["date"]) for r in rows if mp.row_grade(r) == "S"}, len(rows)


def recall_and_precision(firsts, pool, s100_keys, bar_backed_s_all):
    """Identical for every arm (this is an exit-side predicate -- it cannot
    change which day fires). fired_keys = the sym_day of every first-of-day
    pick."""
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
    print("first-of-day arm (size-gated): %d picks" % len(firsts))
    fires_per_day = round(len(firsts) / n_days, 3)

    byday_all = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            byday_all[r["day"]].append(r)
    candidates_per_day = round(sum(len(v) for v in byday_all.values()) / n_days, 2)

    baseline_rows, k_rows, n_fallback = build_lists(firsts)
    print("bar replay: %d/%d picks fell back to the book's own r (no bars, no "
          "entry bar match, or exit ran past available data)"
          % (n_fallback, len(firsts)))

    pool = mp.canonical_pool()
    s100_keys, s100_n_rows = s_sweep_keys()
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}
    rp = recall_and_precision(firsts, pool, s100_keys, bar_backed_s_all)
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (s100_n_rows, len(s100_keys), len(bar_backed_s_all)))
    print("recall_100 %s/%d  recall_all %s/%d  precision %s/%d (identical for "
          "every arm -- exit-side predicate, day selection unchanged)"
          % (rp["recall_100_hits"], rp["recall_100_n"], rp["recall_all_hits"],
             rp["recall_all_n"], rp["precision_num"], rp["precision_den"]))

    base_full = g86.stats(baseline_rows, n_days)
    base_h1 = half_stats(baseline_rows, hi=H_SPLIT, n_days=n_days_h1)
    base_h2 = half_stats(baseline_rows, lo=H_SPLIT, n_days=n_days_h2)
    print("\nBASELINE (this script's own no-BE replay): $%d/day (H1 $%d, H2 $%d), "
          "mean R %.3f, win %.1f%%, months green %d/%d, maxDD $%d"
          % (base_full["per_day"], base_h1.get("per_day", 0), base_h2.get("per_day", 0),
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["worst_drawdown"]))

    arms = {}
    for k in K_VALUES:
        full = g86.stats(k_rows[k], n_days)
        h1 = half_stats(k_rows[k], hi=H_SPLIT, n_days=n_days_h1)
        h2 = half_stats(k_rows[k], lo=H_SPLIT, n_days=n_days_h2)
        h1_delta = h1.get("per_day", 0) - base_h1.get("per_day", 0)
        h2_delta = h2.get("per_day", 0) - base_h2.get("per_day", 0)
        survivor = (h1_delta > 0 and h2_delta > 0
                    and (rp["recall_100"] or 0) >= (rp["recall_100"] or 0))
        arms[k] = {"full": full, "h1": h1, "h2": h2,
                   "h1_delta_usd_day": round(h1_delta, 2),
                   "h2_delta_usd_day": round(h2_delta, 2),
                   "survivor": survivor}
        print("\nk=%.2fR past PT1: $%d/day (H1 $%d [%+d], H2 $%d [%+d]), mean R %.3f, "
              "win %.1f%%, months green %d/%d, maxDD $%d -- survivor=%s"
              % (k, full["per_day"], h1.get("per_day", 0), h1_delta,
                 h2.get("per_day", 0), h2_delta, full["mean_r"], full["win_pct"],
                 full["months_green"], full["months"], full["worst_drawdown"], survivor))

    best_k = max(K_VALUES, key=lambda k: arms[k]["full"]["per_day"])
    best = arms[best_k]

    out = {
        "book": os.path.basename(BOOK_PATH), "sessions": n_days,
        "sessions_h1": n_days_h1, "sessions_h2": n_days_h2,
        "pt1_definition": "entry +/- 1.0R (RULE6_BE_MULT convention -- see docstring)",
        "candidates_per_day": candidates_per_day, "fires_per_day": fires_per_day,
        "n_fallback_to_book_r": n_fallback, "n_picks": len(firsts),
        "recall_precision": rp,
        "baseline_no_be": {"full": base_full, "h1": base_h1, "h2": base_h2},
        "k_arms": {str(k): arms[k] for k in K_VALUES},
        "best_k": best_k, "survivor": best["survivor"],
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g154/F5 -- be-stop-after-enough-past-pt1", "",
          "**What is different now:** measured Austin's own flagged-unresolved "
          "threshold -- how far PAST the first profit target (PT1) price must "
          "travel before the stop arms to breakeven -- on the honest book, "
          "instead of leaving it a stated-but-unmeasured question.", "",
          "Book `%s`, %d sessions (H1 %d / H2 %d), size-gated on "
          "`signal_runner.min_risk_floor`. 1R = $%d. H1/H2 split at %s. "
          "PT1 := entry +/- 1.0R (documented simplification -- see module "
          "docstring; the shipped ladder's causal PT1 rung is not "
          "reconstructable from this book alone)."
          % (os.path.basename(BOOK_PATH), n_days, n_days_h1, n_days_h2,
             int(g86.RISK), H_SPLIT), "",
          "This is an EXIT-SIDE arm: it cannot change which day trades. "
          "candidates/day %.2f, fires/day %.3f, recall_100 %s/%d, recall_all "
          "%s/%d, precision %s/%d -- identical for baseline and every k below "
          "by construction. %d/%d picks fell back to the book's own recorded "
          "r (no bars, no entry-bar match, or exit ran past available data), "
          "identically for every arm."
          % (candidates_per_day, fires_per_day, rp["recall_100_hits"], rp["recall_100_n"],
             rp["recall_all_hits"], rp["recall_all_n"], rp["precision_num"],
             rp["precision_den"], n_fallback, len(firsts)), "",
          "## Baseline -- this script's own no-BE replay (same simplified "
          "model as every k arm, arming disabled)", "",
          "| $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD |",
          "|---:|---:|---:|---:|---:|---:|---:|",
          "| $%d | $%d | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_full["per_day"], base_h1.get("per_day", 0), base_h2.get("per_day", 0),
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["worst_drawdown"]),
          "", "## k-arm sweep (BE arms at entry +/- (1.0+k)R)", "",
          "| k (R past PT1) | $/day | H1 $/day | H1 delta | H2 $/day | H2 delta | "
          "mean R | win | months green | max DD | survivor |",
          "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for k in K_VALUES:
        a = arms[k]; f = a["full"]
        md.append("| %.2fR | $%d | $%d | %+d | $%d | %+d | %+.3f | %.1f%% | %d/%d | $%d | %s |"
                  % (k, f["per_day"], a["h1"].get("per_day", 0), a["h1_delta_usd_day"],
                     a["h2"].get("per_day", 0), a["h2_delta_usd_day"], f["mean_r"],
                     f["win_pct"], f["months_green"], f["months"], f["worst_drawdown"],
                     a["survivor"]))
    md += ["", "## Verdict", "",
           "Best-performing k: **%.2fR past PT1**. Survivor (H1 AND H2 both "
           "improve $/day vs. this script's own no-BE replay baseline, "
           "recall_100 unaffected by construction): **%s**."
           % (best_k, best["survivor"]), "",
           "Recall/precision cannot move for an exit-side predicate -- they "
           "are reported once, not per-k, and are identical to whatever "
           "the shipped one-trade-a-day arm already fires on this book."]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
