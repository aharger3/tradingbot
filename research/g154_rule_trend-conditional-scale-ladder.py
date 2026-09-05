"""g154/F5 -- "trend-conditional scale-out ladder" (candidate:
trend-conditional-scale-ladder). polarity: S-indicator (exit-side).

Austin's own words (row F5): "The scale-out ladder should vary with the
day's regime -- on a trending day run a smaller first scale and let more
ride (50/20/10/10); on a choppy day take profit earlier and heavier
(30/30/30/10)."

THIS IS AN EXIT-SIDE ARM. It cannot change which day is traded: the
one-trade-a-day pick (`omen_metrics.first_of_day_arm`, arrival order, size
gate on `signal_runner.min_risk_floor`) is computed ONCE from the committed
book's own status/traded fields and is IDENTICAL for baseline and
candidate -- recall and precision are reported once, not per arm.

READ FIRST -- `research/g151_rules_6.json` claim #3 (the rulebook's own
"trendiness" finding, ratified 2026-08-29): on the FINISHED chart, session
trendiness (first-close-to-last-close / summed 1-min absolute moves)
separates his yes/no at p=0.014 across the full 812-day corpus -- but nine
CAUSAL (pre-entry-observable) proxies were swept and "every one is a coin
flip, and two lean backwards". This row's predicate is a causal proxy of
that exact family (a partial-session, entry-anchored trendiness ratio, not
the finished-chart version). Treat any apparent win here as SUSPECT until F6
checks the split point was not implicitly fit on H2 -- which is why the
split threshold below is computed on H1 ONLY and then applied, unchanged,
out of sample to H2.

PREDICATE, exactly as specced, causal (reads data_archive only up to the
signal/entry bar `entry_i`, via the book's own RTH bar pack):

    trendiness_i = |Close[entry_i] - Open[bars[0]]|
                   / sum_{j=1}^{entry_i} |Close[j] - Close[j-1]|

  over that day's own RTH 1-minute bars (`research.g80_ordertype_grid.day_pack`,
  the same causal bar reader `g101_open_and_ladder.py` and
  `g113_ladder_shapes_sweep.py` already use). The split threshold is the
  MEDIAN trendiness value across H1 (day < 2025-09-01) picks only --
  in-sample on H1, held fixed and applied unchanged to H2. A day at or above
  the H1 median is "trending" (ladder 50/20/10/10); below it is "choppy"
  (ladder 30/30/30/10, the g99/g101 control shape -- also this script's
  BASELINE, applied uniformly to every day regardless of regime, so the A/B
  isolates the conditioning on regime alone, not the ladder shapes
  themselves).

Ladder mechanics reused verbatim, not re-derived: `g101_open_and_ladder`'s
`build_rungs` (plan "4": PT1 extreme / PT2 next named level beyond it / PT3
2R / PT4 max(4R, next named level) -- causal inputs only) and `walk_ladder`
(bar-ordered fill, trail="be" -- stop moves to entry after the first rung
fills -- the shipped BE_TRIGGER default), both of which route every fill
through `stop_rule.stop_fill_price` / `disaster_stop_price` and
`backtest_week._target_hit` / `_stop_hit`. Nothing is re-implemented
locally.

PRIOR ART reused: `research/g86_honest_ceiling.py` (stats(), RISK),
`research/g91_lane_slice.py` (lane-slice reporting pattern),
`research/omen_metrics.py` (first_of_day_arm, the size gate),
`research/marks_pool.py` (canonical grade pool), `research/build_deck.py`
(mark-file reader, 34-card sweep), `research/g80_ordertype_grid.py`
(day_pack -- the causal RTH bar reader), `research/g101_open_and_ladder.py`
(build_rungs, walk_ladder, r_of, the 30/30/30/10 control shape),
`research/g113_ladder_shapes_sweep.py` (the shape-sweep skeleton this script
is directly modeled on), `stop_rule.py` (the one stop trigger + fill).

    python research/g154_rule_trend-conditional-scale-ladder.py

Writes research/g154_rule_trend-conditional-scale-ladder.{md,json}.
Applies nothing, ships nothing. Read-only on the book and every mark corpus.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86             # noqa: E402  stats(), RISK
import g101_open_and_ladder as g101          # noqa: E402  build_rungs, walk_ladder, r_of
import omen_metrics as om                    # noqa: E402  first_of_day_arm, the size gate
import marks_pool as mp                      # noqa: E402  canonical grade pool
import build_deck as bd                      # noqa: E402  mark-file reader (34-card sweep)
from research import g80_ordertype_grid as G  # noqa: E402  day_pack, causal RTH bars

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_trend-conditional-scale-ladder.json")
OUT_MD = os.path.join(HERE, "g154_rule_trend-conditional-scale-ladder.md")

H_SPLIT = "2025-09-01"      # CLAUDE.md-mandated H1/H2 boundary
CHOPPY_WEIGHTS = (.30, .30, .30, .10)     # baseline everywhere; candidate below threshold
TRENDING_WEIGHTS = (.50, .20, .10, .10)   # candidate at/above the H1-in-sample median


def n_days_in(rows, lo=None, hi=None):
    days = {r["day"] for r in rows}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def trendiness(row, bars):
    """Causal, entry-anchored trendiness ratio. Reads bars[0 .. entry_i] only
    -- nothing past the signal bar. None if entry_i is unusable or the move
    sum is zero (flat tape, undefined ratio -- excluded from the split-point
    median and treated as "choppy" by convention, the more conservative
    branch, since it never separated from noise)."""
    i = row.get("entry_i")
    if i is None or i < 0 or i >= len(bars):
        return None
    seg = bars[:i + 1]
    if len(seg) < 2:
        return None
    move = sum(abs(seg[j].close - seg[j - 1].close) for j in range(1, len(seg)))
    if move <= 0:
        return None
    return abs(seg[-1].close - seg[0].open) / move


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

    # ---- causal trendiness per pick, entry-anchored, bars via day_pack ----
    trend_vals = {}       # key -> trendiness or None
    named_by_key = {}     # key -> (bars, extreme, named) for rung building
    n_nobars = 0
    for r in firsts:
        key = "%s_%s" % (r["sym"], r["day"])
        bars, pdh, pdl, pmh, pml = G.day_pack(r["sym"], r["day"])
        i = r.get("entry_i")
        if not bars or i is None or i >= len(bars):
            n_nobars += 1
            trend_vals[key] = None
            named_by_key[key] = None
            continue
        long = r["dir"] == "call"
        extreme = (max(c.high for c in bars[:i + 1]) if long
                   else min(c.low for c in bars[:i + 1]))
        named = ({"PDH": pdh, "PMH": pmh} if long else {"PDL": pdl, "PML": pml})
        named_by_key[key] = (bars, extreme, named)
        trend_vals[key] = trendiness(r, bars)

    # ---- H1-IN-SAMPLE split point, held fixed, applied unchanged to H2 ----
    h1_vals = [trend_vals["%s_%s" % (r["sym"], r["day"])] for r in firsts
               if r["day"] < H_SPLIT and trend_vals["%s_%s" % (r["sym"], r["day"])] is not None]
    threshold = statistics.median(h1_vals) if h1_vals else None
    print("H1-in-sample trendiness median (split point, applied unchanged to "
          "H2): %s over %d H1 picks with a readable ratio"
          % ("%.4f" % threshold if threshold is not None else "n/a", len(h1_vals)))

    # ---- walk both arms: baseline = fixed 30/30/30/10 everywhere; ----
    # ---- candidate = 50/20/10/10 if trendiness >= threshold else 30/30/30/10
    base_rows, cand_rows = [], []
    n_trending = n_choppy = 0
    for r in firsts:
        key = "%s_%s" % (r["sym"], r["day"])
        pack = named_by_key.get(key)
        base_row, cand_row = dict(r), dict(r)
        if pack is None:
            # no bars: leave the book's own r/pnl untouched for both arms
            base_rows.append(base_row)
            cand_rows.append(cand_row)
            n_regime_missing += 1
            continue
        bars, extreme, named = pack
        entry, stop = r["entry"], r["stop"]
        long = r["dir"] == "call"
        tv = trend_vals[key]
        trending = (threshold is not None and tv is not None and tv >= threshold)
        if trending:
            n_trending += 1
        else:
            n_choppy += 1

        base_rungs = g101.build_rungs(entry, stop, long, extreme, named,
                                       CHOPPY_WEIGHTS, "4")
        base_fills = g101.walk_ladder(r, bars, base_rungs, trail="be")
        base_r = g101.r_of(base_fills, entry, stop, long)
        base_row["r"] = base_r
        base_row["pnl"] = base_r * g86.RISK

        cand_weights = TRENDING_WEIGHTS if trending else CHOPPY_WEIGHTS
        cand_rungs = g101.build_rungs(entry, stop, long, extreme, named,
                                       cand_weights, "4")
        cand_fills = g101.walk_ladder(r, bars, cand_rungs, trail="be")
        cand_r = g101.r_of(cand_fills, entry, stop, long)
        cand_row["r"] = cand_r
        cand_row["pnl"] = cand_r * g86.RISK

        base_rows.append(base_row)
        cand_rows.append(cand_row)

    print("bar walk: %d/%d picks had no bars/entry_i (fell back to the "
          "book's own r for both arms), %d trending / %d choppy by regime"
          % (n_nobars, len(firsts), n_trending, n_choppy))

    pool = mp.canonical_pool()
    s100_rows = list(bd._rows(SWEEP_PATH))
    s100_keys = {"%s_%s" % (row["symbol"], row["date"]) for row in s100_rows
                 if mp.row_grade(row) == "S"}
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}

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
    recall_100 = round(hit100 / len(s100_keys), 4) if s100_keys else None
    recall_all = round(hitall / len(bar_backed_s_all), 4) if bar_backed_s_all else None
    precision = round(grade_num / grade_den, 4) if grade_den else None
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (len(s100_rows), len(s100_keys), len(bar_backed_s_all)))
    print("recall_100 %d/%d  recall_all %d/%d  precision %d/%d (identical for "
          "baseline and candidate -- exit-side predicate, day selection unchanged)"
          % (hit100, len(s100_keys), hitall, len(bar_backed_s_all), grade_num, grade_den))

    def half_stats(rows, lo=None, hi=None, n_days=None):
        sub = [r for r in rows if (lo is None or r["day"] >= lo) and (hi is None or r["day"] < hi)]
        return g86.stats(sub, n_days)

    base_full = g86.stats(base_rows, n_days)
    base_h1 = half_stats(base_rows, hi=H_SPLIT, n_days=n_days_h1)
    base_h2 = half_stats(base_rows, lo=H_SPLIT, n_days=n_days_h2)
    print("\nBASELINE (fixed 30/30/30/10 every day): $%d/day (H1 $%d, H2 $%d), "
          "mean R %.3f, win %.1f%%, months green %d/%d, maxDD $%d"
          % (base_full["per_day"], base_h1.get("per_day", 0), base_h2.get("per_day", 0),
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["worst_drawdown"]))

    cand_full = g86.stats(cand_rows, n_days)
    cand_h1 = half_stats(cand_rows, hi=H_SPLIT, n_days=n_days_h1)
    cand_h2 = half_stats(cand_rows, lo=H_SPLIT, n_days=n_days_h2)
    h1_delta = cand_h1.get("per_day", 0) - base_h1.get("per_day", 0)
    h2_delta = cand_h2.get("per_day", 0) - base_h2.get("per_day", 0)
    h1_improves = h1_delta > 0
    h2_improves = h2_delta > 0
    recall_ok = (recall_100 or 0) >= (recall_100 or 0)  # identical by construction, exit-side
    survivor = bool(h1_improves and h2_improves and recall_ok)
    print("\nCANDIDATE (50/20/10/10 trending >= H1 median, 30/30/30/10 "
          "choppy): $%d/day (H1 $%d [%+d], H2 $%d [%+d]), mean R %.3f, win "
          "%.1f%%, months green %d/%d, maxDD $%d -- survivor=%s"
          % (cand_full["per_day"], cand_h1.get("per_day", 0), h1_delta,
             cand_h2.get("per_day", 0), h2_delta, cand_full["mean_r"],
             cand_full["win_pct"], cand_full["months_green"], cand_full["months"],
             cand_full["worst_drawdown"], survivor))

    out = {
        "book": os.path.basename(BOOK_PATH), "sessions": n_days,
        "sessions_h1": n_days_h1, "sessions_h2": n_days_h2,
        "rule": "trend-conditional-scale-ladder",
        "polarity": "S-indicator",
        "predicate": "Causal entry-anchored trendiness = |Close[entry_i] - "
                     "Open[bars[0]]| / sum(|Close[j]-Close[j-1]|) over RTH "
                     "bars up to entry_i. Split at the H1-in-sample median, "
                     "held fixed and applied unchanged to H2. Ladder "
                     "50/20/10/10 at/above the threshold (trending), "
                     "30/30/30/10 below it (choppy) or when the ratio is "
                     "unreadable. Built via g101.build_rungs (plan 4) and "
                     "filled via g101.walk_ladder (trail=be).",
        "h1_split_threshold": threshold,
        "candidates_per_day": candidates_per_day, "fires_per_day": fires_per_day,
        "n_picks": len(firsts), "n_nobars": n_nobars,
        "n_trending": n_trending, "n_choppy": n_choppy,
        "recall_100": recall_100, "recall_100_n": len(s100_keys), "recall_100_hits": hit100,
        "recall_all": recall_all, "recall_all_n": len(bar_backed_s_all), "recall_all_hits": hitall,
        "precision": precision, "precision_num": grade_num, "precision_den": grade_den,
        "baseline_fixed_30_30_30_10": {"full": base_full, "h1": base_h1, "h2": base_h2},
        "candidate_trend_conditional": {"full": cand_full, "h1": cand_h1, "h2": cand_h2},
        "h1_delta_usd_day": round(h1_delta, 2),
        "h2_delta_usd_day": round(h2_delta, 2),
        "survivor": survivor,
        "survivor_rule": "H1 AND H2 both improve $/day vs. the fixed "
                         "30/30/30/10 baseline, recall_100 not below "
                         "baseline (identical by construction for an "
                         "exit-side predicate).",
        "caveat": "SUSPECT per g151_rules_6.json#3: nine causal proxies of "
                  "this same 'trendiness' family were swept to a coin flip "
                  "(two leaning backwards) on the finished-chart version of "
                  "this exact measure. F6 must check the H1 split threshold "
                  "was not implicitly fit to H2 before this counts as a real "
                  "survivor.",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g154/F5 -- trend-conditional-scale-ladder", "",
          "**What is different now:** measured Austin's claim that the "
          "scale-out ladder should vary with the day's regime -- a smaller "
          "first scale, more left to ride (50/20/10/10) on a trending day; "
          "earlier, heavier profit-taking (30/30/30/10) on a choppy day -- "
          "against a fixed 30/30/30/10 baseline applied every day, on the "
          "honest book.", "",
          "Book `%s`, %d sessions (H1 %d / H2 %d), size-gated on "
          "`signal_runner.min_risk_floor`. 1R = $%d. H1/H2 split at %s. "
          "Regime split point = the H1-IN-SAMPLE median trendiness (%s), "
          "held fixed and applied unchanged to H2 -- %d trending / %d "
          "choppy picks by that threshold, %d/%d picks had no bars/entry_i "
          "and fell back to the book's own recorded r for both arms."
          % (os.path.basename(BOOK_PATH), n_days, n_days_h1, n_days_h2,
             int(g86.RISK), H_SPLIT,
             ("%.4f" % threshold if threshold is not None else "n/a"),
             n_trending, n_choppy, n_nobars, len(firsts)), "",
          "This is an EXIT-SIDE arm: it cannot change which day trades. "
          "candidates/day %.2f, fires/day %.3f, recall_100 %d/%d, recall_all "
          "%d/%d, precision %d/%d -- identical for baseline and candidate by "
          "construction."
          % (candidates_per_day, fires_per_day, hit100, len(s100_keys),
             hitall, len(bar_backed_s_all), grade_num, grade_den), "",
          "**CAVEAT (read before trusting a green number):** "
          "`research/g151_rules_6.json` claim #3 already swept nine causal "
          "proxies of this exact 'trendiness' family and found every one a "
          "coin flip (two leaning backwards) on the finished-chart version "
          "of this measure. This row's predicate is another causal proxy of "
          "that family. Any improvement below is SUSPECT until F6 verifies "
          "the H1 split threshold was not implicitly fit to H2.", "",
          "| arm | split | $/day | mean R | win | months green | max DD |",
          "|---|---|---:|---:|---:|---:|---:|",
          "| baseline (fixed 30/30/30/10) | all | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_full["per_day"], base_full["mean_r"], base_full["win_pct"],
             base_full["months_green"], base_full["months"], base_full["worst_drawdown"]),
          "| baseline (fixed 30/30/30/10) | H1 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_h1.get("per_day", 0), base_h1.get("mean_r", 0), base_h1.get("win_pct", 0),
             base_h1.get("months_green", 0), base_h1.get("months", 0),
             base_h1.get("worst_drawdown", 0)),
          "| baseline (fixed 30/30/30/10) | H2 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (base_h2.get("per_day", 0), base_h2.get("mean_r", 0), base_h2.get("win_pct", 0),
             base_h2.get("months_green", 0), base_h2.get("months", 0),
             base_h2.get("worst_drawdown", 0)),
          "| candidate (trend-conditional) | all | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (cand_full["per_day"], cand_full["mean_r"], cand_full["win_pct"],
             cand_full["months_green"], cand_full["months"], cand_full["worst_drawdown"]),
          "| candidate (trend-conditional) | H1 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (cand_h1.get("per_day", 0), cand_h1.get("mean_r", 0), cand_h1.get("win_pct", 0),
             cand_h1.get("months_green", 0), cand_h1.get("months", 0),
             cand_h1.get("worst_drawdown", 0)),
          "| candidate (trend-conditional) | H2 | $%d | %+.3f | %.1f%% | %d/%d | $%d |"
          % (cand_h2.get("per_day", 0), cand_h2.get("mean_r", 0), cand_h2.get("win_pct", 0),
             cand_h2.get("months_green", 0), cand_h2.get("months", 0),
             cand_h2.get("worst_drawdown", 0)),
          "", "H1 delta $%+.2f/day, H2 delta $%+.2f/day. **survivor = %s** "
          "(H1 and H2 both improve $/day vs. the fixed baseline, "
          "recall_100 not below baseline -- identical by construction here)."
          % (h1_delta, h2_delta, survivor), "",
          "Full arm data: `%s`." % os.path.basename(OUT_JSON)]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\nwrote %s and %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
