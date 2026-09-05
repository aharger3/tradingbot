"""g154 F5 -- candidate "standalone-ocr-no-br".

Austin's claim (theme: setups): a one-candle-rule (OCR) level with no
break-and-retest event on the same symbol-day can still be a full, clean S
setup on its own -- it does not need a prior break-and-retest to be valid.

Polarity: S-INDICATOR. Predicate, exactly as specced: treat
r['setup']=='one_candle_rule' (6803 of 127152 rows) as its own stream and
report its $/day, mean R and S rate (precision) against the
break_and_retest stream (119806 rows), on the one-trade-a-day unit
(research/omen_metrics.first_of_day_arm, size-gated). Separately, a bars
scan for how often a clean standalone OCR appears with no accompanying
break -- that count decides whether a detector is worth building, since
today BOTH BreakAndRetestDetector and RuleOf84Detector arm only off a
level-break event.

Two arm constructions over the honest, retest-on book
(research/bt2y_trades_retest_on.json), both reported, primary = S-indicator:

    S-INDICATOR arm ("keep")  -- per day, take the first arrival-order
                                   candidate whose setup=='one_candle_rule'
                                   (size-gated). A day with no OCR candidate
                                   trades nothing.
    REFUSAL-INDICATOR arm ("skip") -- per day, SKIP any one_candle_rule
                                   candidate and take the first surviving
                                   non-OCR candidate (size-gated). Tests the
                                   opposite reading: does dropping OCR help.

A third stream, break_and_retest-only ("br_stream"), is built the same way
as "keep" but filtered to setup=='break_and_retest' -- this is the direct
comparison the row asks for (OCR stream vs BR stream, same construction).

n=1 card note (spec): a single graded card on this predicate is a sizing
exercise, not a rule -- recall/precision below are reported honestly with
their n, never oversold as more than that.

    python research/g154_rule_standalone-ocr-no-br.py

Writes research/g154_rule_standalone-ocr-no-br.json and .md. Nothing here is
applied; ships nothing.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import omen_metrics as om              # noqa: E402  reuse, do not re-derive
from research import marks_pool as mp  # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
PROBE_S_SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_standalone-ocr-no-br.json")
OUT_MD = os.path.join(HERE, "g154_rule_standalone-ocr-no-br.md")

SPLIT_DAY = "2025-09-01"          # H1/H2 split, per row spec
BAR = 397.0                        # Austin's stated bar, for context only
OCR = "one_candle_rule"
BR = "break_and_retest"


# --------------------------------------------------------------------- rule

def _ekey(r):
    return (r["day"], r["et"], r["sym"])


def _candidate_stream(rows):
    """fired&traded or halted, grouped by day, arrival order -- identical
    construction to g86_honest_ceiling.candidates / omen_metrics.first_of_day_arm."""
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    for v in by_day.values():
        v.sort(key=_ekey)
    return by_day


def _keep_arm(by_day, keep_fn):
    """S-indicator construction: per day, first arrival-order sizeable row
    for which keep_fn(row) is True. A day with no surviving row trades
    nothing that day (arm's own stream, not a fallback to the mixed book)."""
    picks = []
    for day in sorted(by_day):
        pick = next((r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False and keep_fn(r)), None)
        if pick is not None:
            picks.append(pick)
    return picks


def _skip_arm(by_day, skip_fn):
    """Refusal-indicator construction: per day, skip any sizeable row
    matching skip_fn, take the first surviving row that does not match."""
    picks = []
    for day in sorted(by_day):
        pick = next((r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False and not skip_fn(r)), None)
        if pick is not None:
            picks.append(pick)
    return picks


# --------------------------------------------------------------- day stats

def _daily_pnl(picks, all_days):
    d = {day: 0.0 for day in all_days}
    for r in picks:
        d[r["day"]] += r["pnl"]
    return d


def _months_green(daily):
    m = defaultdict(float)
    for day, v in daily.items():
        m[day[:7]] += v
    g = sum(1 for v in m.values() if v > 0)
    return g, len(m)


def _max_dd(daily):
    peak = cum = worst = 0.0
    for day in sorted(daily):
        cum += daily[day]
        peak = max(peak, cum)
        worst = max(worst, peak - cum)
    return worst


def arm_stats(picks, all_days, label):
    daily = _daily_pnl(picks, all_days)
    n_days = len(all_days)
    total = sum(r["pnl"] for r in picks)
    rs = [r["r"] for r in picks]
    wins = sum(1 for v in rs if v > 0)
    losses = sum(1 for v in rs if v < 0)
    g, m = _months_green(daily)
    return {
        "label": label,
        "sessions": n_days,
        "trades": len(picks),
        "fires_per_day": round(len(picks) / n_days, 4) if n_days else 0.0,
        "usd_day": round(total / n_days, 2) if n_days else 0.0,
        "mean_r": round(statistics.fmean(rs), 4) if rs else 0.0,
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": "%d/%d" % (g, m),
        "months_green_n": g, "months_total": m,
        "max_dd_usd": round(_max_dd(daily), 2),
        "pct_of_bar": round((total / n_days) / BAR * 100, 1) if n_days else None,
    }


# ------------------------------------------------------------ S recall

def _symday_survivors(rows_by_symday, sym, day, keep_fn):
    rows = rows_by_symday.get((sym, day), [])
    sizeable = [r for r in rows if om._row_is_sizeable(r) is not False]
    if keep_fn is None:
        return sizeable
    return [r for r in sizeable if keep_fn(r)]


def recall(keys, rows_by_symday, keep_fn):
    """keys: iterable of 'SYM_YYYY-MM-DD'. Returns (baseline_recall,
    arm_recall, n) -- fraction of those symbol-days where the book still
    fires at all (baseline, keep_fn=None) vs still fires after the arm's
    keep predicate is applied."""
    n = 0
    base_hit = arm_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        base = _symday_survivors(rows_by_symday, sym, day, None)
        arm = _symday_survivors(rows_by_symday, sym, day, keep_fn)
        if base:
            base_hit += 1
        if arm:
            arm_hit += 1
    return (round(base_hit / n * 100, 1) if n else None,
            round(arm_hit / n * 100, 1) if n else None, n)


def load_probe_s_days():
    keys = []
    with open(PROBE_S_SWEEP, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if mp.row_grade(row) == "S":
                keys.append(row["card_id"])
    return keys


# ----------------------------------------------------------- precision

def precision(picks, pool):
    graded_at_all = 0
    graded_s = 0
    for r in picks:
        key = "%s_%s" % (r["sym"], r["day"])
        e = pool.get(key)
        if e is None:
            continue
        graded_at_all += 1
        if e.grade == "S":
            graded_s += 1
    return (round(graded_s / graded_at_all * 100, 1) if graded_at_all else None,
            graded_s, graded_at_all)


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    meta = blob["meta"]
    all_days = sorted({r["day"] for r in rows})
    h1_days = [d for d in all_days if d < SPLIT_DAY]
    h2_days = [d for d in all_days if d >= SPLIT_DAY]

    # -- raw setup base rates, all rows (not one-a-day)
    ocr_rows_total = sum(1 for r in rows if r.get("setup") == OCR)
    br_rows_total = sum(1 for r in rows if r.get("setup") == BR)

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)   # mixed book

    by_day_stream = _candidate_stream(rows)
    cand_stream_by_symday = defaultdict(list)
    for day, v in by_day_stream.items():
        for r in v:
            cand_stream_by_symday[(r["sym"], day)].append(r)
    total_cands = sum(len(v) for v in by_day_stream.values())
    cands_per_day = round(total_cands / len(all_days), 2)

    keep_fn = lambda r: r.get("setup") == OCR       # S-indicator: keep OCR only
    skip_fn = lambda r: r.get("setup") == OCR       # refusal-indicator: skip OCR
    br_fn = lambda r: r.get("setup") == BR           # comparison stream

    keep_picks = _keep_arm(by_day_stream, keep_fn)        # S-indicator arm
    skip_picks = _skip_arm(by_day_stream, skip_fn)        # refusal-indicator arm
    br_picks = _keep_arm(by_day_stream, br_fn)            # BR-only comparison stream

    def split(picks, days):
        dset = set(days)
        return [r for r in picks if r["day"] in dset]

    baseline_all = arm_stats(baseline_picks, all_days, "baseline (whole book)")
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days, "baseline H1")
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days, "baseline H2")
    keep_all = arm_stats(keep_picks, all_days, "S-indicator (OCR-only)")
    keep_h1 = arm_stats(split(keep_picks, h1_days), h1_days, "S-indicator H1")
    keep_h2 = arm_stats(split(keep_picks, h2_days), h2_days, "S-indicator H2")
    skip_all = arm_stats(skip_picks, all_days, "refusal-indicator (skip OCR)")
    skip_h1 = arm_stats(split(skip_picks, h1_days), h1_days, "refusal-indicator H1")
    skip_h2 = arm_stats(split(skip_picks, h2_days), h2_days, "refusal-indicator H2")
    br_all = arm_stats(br_picks, all_days, "BR-only stream")
    br_h1 = arm_stats(split(br_picks, h1_days), h1_days, "BR-only H1")
    br_h2 = arm_stats(split(br_picks, h2_days), h2_days, "BR-only H2")

    # -- recall on the 34-S-card probe sweep
    probe_keys = load_probe_s_days()
    probe_base_recall, probe_keep_recall, probe_n = recall(
        probe_keys, cand_stream_by_symday, keep_fn)
    _, probe_skip_recall, _ = recall(
        probe_keys, cand_stream_by_symday, lambda r: not skip_fn(r))

    # -- recall on all bar-backed S days (canonical pool)
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]
    pool_base_recall, pool_keep_recall, pool_n = recall(
        bar_backed_s_keys, cand_stream_by_symday, keep_fn)
    _, pool_skip_recall, _ = recall(
        bar_backed_s_keys, cand_stream_by_symday, lambda r: not skip_fn(r))

    # -- precision (fired days graded S / fired days graded at all)
    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)
    keep_prec, keep_prec_s, keep_prec_n = precision(keep_picks, pool)
    skip_prec, skip_prec_s, skip_prec_n = precision(skip_picks, pool)
    br_prec, br_prec_s, br_prec_n = precision(br_picks, pool)

    h1_delta = keep_h1["usd_day"] - baseline_h1["usd_day"]
    h2_delta = keep_h2["usd_day"] - baseline_h2["usd_day"]
    h1_improves = (keep_h1["usd_day"] > baseline_h1["usd_day"]) or (
        (keep_prec or 0) > (base_prec or 0))
    h2_improves = (keep_h2["usd_day"] > baseline_h2["usd_day"]) or (
        (keep_prec or 0) > (base_prec or 0))
    recall_ok = (probe_keep_recall is None or probe_base_recall is None
                 or probe_keep_recall >= probe_base_recall) and (
        pool_keep_recall is None or pool_base_recall is None
        or pool_keep_recall >= pool_base_recall)
    survivor = bool(h1_improves and h2_improves and recall_ok)

    # -- the standalone-occurrence scan: how often does a fired OCR level
    # appear on a symbol-day with NO fired break_and_retest event at all
    # (fired = status=='fired', regardless of traded -- this asks whether the
    # setup even ARMED, not whether it was taken). That count decides whether
    # a detector is worth building: today both BreakAndRetestDetector and
    # RuleOf84Detector arm only off a level-break event, so a standalone OCR
    # with no break is, by construction, invisible to the engine's own arm
    # logic unless OCR fires it directly.
    fired = [r for r in rows if r["status"] == "fired"]
    ocr_fired_symdays = {(r["sym"], r["day"]) for r in fired if r.get("setup") == OCR}
    br_fired_symdays = {(r["sym"], r["day"]) for r in fired if r.get("setup") == BR}
    standalone_symdays = ocr_fired_symdays - br_fired_symdays
    n_ocr_fired_symdays = len(ocr_fired_symdays)
    n_standalone = len(standalone_symdays)
    pct_standalone = (round(n_standalone / n_ocr_fired_symdays * 100, 1)
                       if n_ocr_fired_symdays else None)

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "standalone-ocr-no-br",
        "polarity": "s-indicator",
        "predicate": {
            "s_indicator_arm": "KEEP only, per day, the first arrival-order "
                                "sizeable candidate with setup=='one_candle_rule'",
            "refusal_indicator_arm": "SKIP any sizeable one_candle_rule "
                                      "candidate, take the first surviving "
                                      "non-OCR candidate",
        },
        "raw_row_counts": {
            "one_candle_rule_total": ocr_rows_total,
            "break_and_retest_total": br_rows_total,
            "denominator": "all %d rows, not one-a-day" % len(rows),
        },
        "candidates_per_day_mixed_stream": cands_per_day,
        "baseline_mixed": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "s_indicator_ocr_only": {"all": keep_all, "h1": keep_h1, "h2": keep_h2},
        "refusal_indicator_skip_ocr": {"all": skip_all, "h1": skip_h1, "h2": skip_h2},
        "br_only_stream": {"all": br_all, "h1": br_h1, "h2": br_h2},
        "h1_delta_usd_day": round(h1_delta, 2),
        "h2_delta_usd_day": round(h2_delta, 2),
        "recall": {
            "probe_s_sweep_34": {
                "n": probe_n, "baseline_pct": probe_base_recall,
                "s_indicator_pct": probe_keep_recall,
                "refusal_indicator_pct": probe_skip_recall,
            },
            "bar_backed_s_days_canonical_pool": {
                "n": pool_n, "baseline_pct": pool_base_recall,
                "s_indicator_pct": pool_keep_recall,
                "refusal_indicator_pct": pool_skip_recall,
            },
        },
        "precision": {
            "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
            "s_indicator_ocr_only": {"pct": keep_prec, "s": keep_prec_s, "graded": keep_prec_n},
            "refusal_indicator_skip_ocr": {"pct": skip_prec, "s": skip_prec_s, "graded": skip_prec_n},
            "br_only_stream": {"pct": br_prec, "s": br_prec_s, "graded": br_prec_n},
        },
        "standalone_scan": {
            "definition": "status=='fired' rows only (regardless of traded); "
                           "a symbol-day counts as standalone if it fired an "
                           "OCR level and fired NO break_and_retest level that "
                           "same day",
            "ocr_fired_symdays": n_ocr_fired_symdays,
            "br_fired_symdays": len(br_fired_symdays),
            "standalone_ocr_symdays": n_standalone,
            "pct_of_ocr_fired_symdays_standalone": pct_standalone,
        },
        "survivor": survivor,
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline "
                          "(measured on the S-indicator OCR-only arm vs "
                          "baseline mixed arm)",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- standalone-ocr-no-br")
    md.append("")
    verdict_line = ("SURVIVOR" if survivor else "not a survivor") + \
        (" -- H1 %+.0f/day, H2 %+.0f/day" % (h1_delta, h2_delta))
    md.append("**One sentence: %s** on the honest, retest-on book, one-trade-"
               "a-day unit, size-gated." % verdict_line)
    md.append("")
    md.append("Claim: a one-candle-rule (OCR) level with no break-and-retest "
               "event on the same symbol-day can still be a full, clean S "
               "setup on its own. S-indicator arm: KEEP only OCR candidates "
               "(per day, first arrival-order sizeable OCR row). "
               "Refusal-indicator arm: SKIP OCR candidates, take the first "
               "surviving non-OCR row. n=1 card note: any single-card read "
               "below is a sizing exercise, not a rule.")
    md.append("")
    md.append("Raw row counts (all %d rows, NOT one-a-day): one_candle_rule "
               "**%d**, break_and_retest **%d**."
               % (len(rows), ocr_rows_total, br_rows_total))
    md.append("")
    md.append("candidates/day (mixed arrival stream, whole pool): **%.2f**"
               % cands_per_day)
    md.append("")
    md.append("## Money -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| arm | split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for label, s in (("baseline (mixed)", baseline_all), ("baseline (mixed)", baseline_h1),
                     ("baseline (mixed)", baseline_h2),
                     ("S-indicator (OCR-only)", keep_all), ("S-indicator (OCR-only)", keep_h1),
                     ("S-indicator (OCR-only)", keep_h2),
                     ("refusal-indicator (skip OCR)", skip_all), ("refusal-indicator (skip OCR)", skip_h1),
                     ("refusal-indicator (skip OCR)", skip_h2),
                     ("BR-only stream", br_all), ("BR-only stream", br_h1), ("BR-only stream", br_h2)):
        split_label = s["label"].split(" ", 1)[-1] if " " in s["label"] else "all"
        md.append("| %s | %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                   % (label, split_label if split_label != label else "all",
                      s["usd_day"], s["mean_r"], s["win_pct"],
                      s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
    md.append("")
    md.append("H1/H2 split at **%s**. delta $/day (S-indicator OCR-only arm "
               "vs baseline): H1 %+.2f, H2 %+.2f." % (SPLIT_DAY, h1_delta, h2_delta))
    md.append("")
    md.append("## OCR stream vs BR stream (the row's own comparison)")
    md.append("")
    md.append("| stream | $/day | mean R | win | precision (S rate) |")
    md.append("|---|---:|---:|---:|---:|")
    md.append("| OCR-only (S-indicator) | $%.2f | %+.3f | %.1f%% | %s%% (%d/%d) |"
               % (keep_all["usd_day"], keep_all["mean_r"], keep_all["win_pct"],
                  keep_prec, keep_prec_s, keep_prec_n))
    md.append("| break_and_retest-only | $%.2f | %+.3f | %.1f%% | %s%% (%d/%d) |"
               % (br_all["usd_day"], br_all["mean_r"], br_all["win_pct"],
                  br_prec, br_prec_s, br_prec_n))
    md.append("")
    md.append("## Is a standalone-OCR detector worth building?")
    md.append("")
    md.append("Scan over status=='fired' rows (regardless of traded): "
               "**%d** symbol-days fired an OCR level; of those, **%d** "
               "(**%s%%**) fired NO break_and_retest level that same "
               "symbol-day. %d symbol-days fired a break_and_retest level. "
               "%s"
               % (n_ocr_fired_symdays, n_standalone, pct_standalone,
                  len(br_fired_symdays),
                  ("A non-trivial share of OCR fires arrive with no "
                   "accompanying break -- BreakAndRetestDetector and "
                   "RuleOf84Detector both arm only off a level-break event "
                   "today, so a standalone-OCR detector is worth scoping."
                   if (pct_standalone or 0) >= 30
                   else "Most OCR fires already co-occur with a "
                   "break-and-retest event on the same symbol-day, so a "
                   "dedicated standalone-OCR detector would catch a small "
                   "slice on top of what break-triggered arming already "
                   "sees.")))
    md.append("")
    md.append("## S recall")
    md.append("")
    md.append("| set | n | baseline | S-indicator (OCR-only) | refusal-indicator (skip OCR) |")
    md.append("|---|---:|---:|---:|---:|")
    md.append("| probe_s_sweep (34 S cards) | %d | %s%% | %s%% | %s%% |"
               % (probe_n, probe_base_recall, probe_keep_recall, probe_skip_recall))
    md.append("| bar-backed S days (canonical_pool) | %d | %s%% | %s%% | %s%% |"
               % (pool_n, pool_base_recall, pool_keep_recall, pool_skip_recall))
    md.append("")
    md.append("## Precision (fired days graded S / fired days graded at all)")
    md.append("")
    md.append("| arm | precision | S / graded |")
    md.append("|---|---:|---:|")
    md.append("| baseline (mixed) | %s%% | %d / %d |" % (base_prec, base_prec_s, base_prec_n))
    md.append("| S-indicator (OCR-only) | %s%% | %d / %d |" % (keep_prec, keep_prec_s, keep_prec_n))
    md.append("| refusal-indicator (skip OCR) | %s%% | %d / %d |" % (skip_prec, skip_prec_s, skip_prec_n))
    md.append("| BR-only stream | %s%% | %d / %d |" % (br_prec, br_prec_s, br_prec_n))
    md.append("")
    md.append("Survivor rule: H1 AND H2 both improve $/day or precision "
               "(S-indicator OCR-only arm vs baseline), and recall on both "
               "S-day panels does not fall below baseline. **Result: %s.**"
               % ("SURVIVOR" if survivor else "NOT a survivor"))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day (mixed): %.2f" % cands_per_day)
    print("baseline $/day: %.2f  S-indicator (OCR-only) $/day: %.2f  "
          "refusal-indicator (skip OCR) $/day: %.2f  BR-only $/day: %.2f"
          % (baseline_all["usd_day"], keep_all["usd_day"], skip_all["usd_day"], br_all["usd_day"]))
    print("standalone OCR (fired, no same-day BR fire): %d / %d OCR-fired "
          "symbol-days (%s%%)" % (n_standalone, n_ocr_fired_symdays, pct_standalone))
    print("survivor: %s" % survivor)


if __name__ == "__main__":
    main()
