"""g154 -- F5: "ocr-strict-definition" (S-indicator), measured over the honest book.

Austin's claim: "OCR means literally one candle opposite-coloured to the
prevailing trend, and the operational test for whether a candle counts is
whether it is usable as the stop -- not its distance from entry."

This is exactly the sentence `signal_runner.OCR_STRICT` already encodes
(default OFF, `signal_runner.py:63`) via `omen_bot.ocr_is_his`: clear break +
quick + strong PA, computed from the block/break anatomy `omen_bot.
detect_order_block_setup` already derives. No engine re-run: this script
recomputes that ONE structural feature, per fired row, from `data_archive`
bars up to (and including) the signal bar, and applies it as a POST-HOC
selection filter over the committed book -- reproducing the OCR_STRICT=1
semantic without re-running signal_runner.

Rows touched: every book row with `setup == 'one_candle_rule'` (the pure OCR
detector) OR `confluence == 'yes'` (BR+OCR confluence -- the OCR half of that
combo signal). Every other row (break_and_retest / reentry_84_rule with no
OCR confluence) passes through untouched.

For a touched row:
  1. Read RTH+premarket 1-min bars for (sym, day) from data_archive
     (polygon_feed.fetch_day, cache-only -- no live fetch, no lookahead: the
     book's own signal bar is bar index `entry_i`, already fully printed).
  2. Slice bars[:entry_i + 1] -- candles available AT the signal bar, nothing
     later.
  3. direction = "bullish" if row['dir'] == 'call' else "bearish".
  4. block, retest, note = omen_bot.detect_order_block_setup(candles,
     direction, out=info) -- the SAME anatomy detector `signal_runner.py`
     calls behind OCR_STRICT.
  5. If no block (structure/anatomy not reproducible from this bar slice, or
     the row's OB no longer resolves the same way standalone), the row
     cannot be confirmed as "his" OCR -- treated as DROP (ocr_is_his=False),
     the conservative reading of a strict definition: unconfirmed is not
     confirmed.
  6. Else: ocr_is_his(candles, block, info['block_idx'], info['break_idx'],
     direction) -- the exact function named in the row spec, called with the
     anatomy this script derived (the same shape `signal_runner.py:3030`
     already uses; the predicate's "(bars, i)" shorthand collapses to this
     richer call because that IS `ocr_is_his`'s real signature).

Arm (S-indicator, DROP polarity): a touched row survives only if ocr_is_his
is True. An untouched row always survives. First-of-day selection then runs
over the surviving stream exactly like `omen_metrics.first_of_day_arm`
(pick-then-gate fixed: a dropped/unsizeable first candidate falls through to
the next survivor on the same day, never skips the day).

PRIOR ART, reused not re-derived:
  - research/g86_honest_ceiling.py -- candidates(), stats(), ekey(), RISK.
  - research/g91_lane_slice.py -- the lane-slice selection-arm pattern.
  - research/omen_metrics.py -- first_of_day_arm, _row_is_sizeable (size
    gate on signal_runner.min_risk_floor).
  - omen_bot.py -- detect_order_block_setup, ocr_is_his (both imported, not
    reimplemented).
  - polygon_feed.py -- fetch_day/rth, cache-only bar reads.

    python research/g154_rule_ocr-strict-definition.py

Writes research/g154_rule_ocr-strict-definition.{json,md}.
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

import g86_honest_ceiling as g86                    # noqa: E402  candidates/stats/ekey/RISK
import signal_runner as sr                          # noqa: E402  min_risk_floor
import polygon_feed as pf                           # noqa: E402  cache-only bar reads
from omen_bot import detect_order_block_setup, ocr_is_his  # noqa: E402  imported, not reimplemented
from research import marks_pool as mp               # noqa: E402
from research import build_deck as bd               # noqa: E402  mark-file reader

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g154_rule_ocr-strict-definition.json")
OUT_MD = os.path.join(HERE, "g154_rule_ocr-strict-definition.md")
SWEEP = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")

H_SPLIT = "2025-09-01"

_bars_cache = {}


def get_bars(sym, day):
    k = (sym, day)
    if k not in _bars_cache:
        try:
            _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bars_cache[k] = []
    return _bars_cache[k]


def is_ocr_touched(r):
    return r["setup"] == "one_candle_rule" or r.get("confluence") == "yes"


def ocr_survives(r, cache={}):
    """True/False for whether row r passes the strict OCR definition. Only
    meaningful for is_ocr_touched(r) rows -- caller handles the pass-through
    for everything else. Cached per (sym, day, entry_i, dir) since the same
    signal bar can appear more than once across corpora reads."""
    key = (r["sym"], r["day"], r.get("entry_i"), r["dir"])
    if key in cache:
        return cache[key]
    ok = _compute_ocr_survives(r)
    cache[key] = ok
    return ok


def _compute_ocr_survives(r):
    i = r.get("entry_i")
    if i is None or i < 0:
        return False
    bars = get_bars(r["sym"], r["day"])
    if not bars or i >= len(bars):
        return False
    candles = bars[: i + 1]
    if len(candles) < 3:
        return False
    direction = "bullish" if r["dir"] == "call" else "bearish"
    info = {}
    block, retest, note = detect_order_block_setup(candles, direction, out=info)
    if block is None or "block_idx" not in info or "break_idx" not in info:
        return False
    try:
        return bool(ocr_is_his(candles, block, info["block_idx"], info["break_idx"], direction))
    except Exception:
        return False


def sized(r):
    return abs(r["entry"] - r["stop"]) >= sr.min_risk_floor(r["entry"])


def filtered_day_rows(v):
    """Rows of one day's candidate stream after the OCR-strict drop."""
    out = []
    for r in v:
        if is_ocr_touched(r) and not ocr_survives(r):
            continue
        out.append(r)
    return out


def pick_first_of_day(v):
    for r in v:
        if _row_is_sizeable_ok(r):
            return r
    return None


def _row_is_sizeable_ok(r):
    from omen_metrics import _row_is_sizeable
    return _row_is_sizeable(r) is not False


def build_arm(byday, keep):
    """keep=True -> arm (drop OCR-unconfirmed); keep=False -> baseline (no drop)."""
    picks = {}
    for day in sorted(byday):
        v = byday[day]
        stream = filtered_day_rows(v) if keep else v
        pick = pick_first_of_day(stream)
        if pick is not None:
            picks[day] = pick
    return picks


def n_days_in(rows, lo=None, hi=None):
    days = {r["day"] for r in rows}
    if lo is not None:
        days = {d for d in days if d >= lo}
    if hi is not None:
        days = {d for d in days if d < hi}
    return len(days)


def half_stats(picks, lo=None, hi=None, n_days=None):
    sub = [r for d, r in picks.items() if (lo is None or d >= lo) and (hi is None or d < hi)]
    return g86.stats(sub, n_days)


def s_sweep_keys():
    rows = list(bd._rows(SWEEP))
    return {"%s_%s" % (r["symbol"], r["date"]) for r in rows if mp.row_grade(r) == "S"}, len(rows)


def recall_and_precision(bysd, keep, pool, s100_keys, bar_backed_s_all, picks_global):
    def fires(key):
        rs = bysd.get(key, [])
        if keep:
            rs = [r for r in rs if not (is_ocr_touched(r) and not ocr_survives(r))]
        return any(_row_is_sizeable_ok(r) for r in rs)

    hit100 = sum(1 for k in s100_keys if fires(k))
    hitall = sum(1 for k in bar_backed_s_all if fires(k))

    grade_num = grade_den = 0
    for day, r in picks_global.items():
        key = "%s_%s" % (r["sym"], day)
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


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    n_days = meta.get("sessions") or len({r["day"] for r in rows})
    n_days_h1 = n_days_in(rows, hi=H_SPLIT)
    n_days_h2 = n_days_in(rows, lo=H_SPLIT)
    print("book: %s -- %d sessions (H1 %d, H2 %d)"
          % (os.path.basename(BOOK), n_days, n_days_h1, n_days_h2))

    byday = g86.candidates(rows)   # day -> sorted candidate rows (fired&traded, or halted)
    pop = [r for v in byday.values() for r in v]
    touched = [r for r in pop if is_ocr_touched(r)]
    print("candidate population (first_of_day_arm's stream): %d rows, %d OCR-touched "
          "(setup=one_candle_rule or confluence=yes)" % (len(pop), len(touched)))

    bysd = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            bysd["%s_%s" % (r["sym"], r["day"])].append(r)
    for v in bysd.values():
        v.sort(key=g86.ekey)

    pool = mp.canonical_pool()
    s100_keys, s100_n_rows = s_sweep_keys()
    bar_backed_s_all = {k for k in mp.s_days(pool) if pool[k].has_bars}
    print("34-card sweep: %d rows, %d graded S -- bar-backed S days corpus-wide: %d"
          % (s100_n_rows, len(s100_keys), len(bar_backed_s_all)))

    # -------- evaluate ocr_is_his over every touched row (bars features) --------
    survived = 0
    n_no_bars = 0
    n_no_block = 0
    for r in touched:
        i = r.get("entry_i")
        bars = get_bars(r["sym"], r["day"])
        if i is None or not bars or i >= len(bars) or i < 0:
            n_no_bars += 1
        if ocr_survives(r):
            survived += 1
        elif not (i is None or not bars or i >= len(bars) or i < 0):
            n_no_block += 1
    print("\nOCR-touched rows in the candidate population: %d -- ocr_is_his True: %d "
          "(%.1f%%), no readable bars: %d, bars readable but block/anatomy failed "
          "or PA/clear-break/quick clause failed: %d"
          % (len(touched), survived, 100.0 * survived / len(touched) if touched else 0.0,
             n_no_bars, n_no_block))

    # -------- baseline: first sized candidate of the day, no OCR filter --------
    base_picks = build_arm(byday, keep=False)
    base_full = g86.stats(list(base_picks.values()), n_days)
    base_h1 = half_stats(base_picks, hi=H_SPLIT, n_days=n_days_h1)
    base_h2 = half_stats(base_picks, lo=H_SPLIT, n_days=n_days_h2)
    base_cand_per_day = round(len(pop) / n_days, 2)
    base_fires_per_day = round(len(base_picks) / n_days, 3)
    base_rp = recall_and_precision(bysd, False, pool, s100_keys, bar_backed_s_all, base_picks)

    print("\nBASELINE first-of-day (no OCR filter): $%d/day, mean R %.3f, win %.1f%%, "
          "months green %d/%d, maxDD $%d, cand/day %.1f, fires/day %.3f"
          % (base_full["per_day"], base_full["mean_r"], base_full["win_pct"],
             base_full["months_green"], base_full["months"], base_full["worst_drawdown"],
             base_cand_per_day, base_fires_per_day))
    print("  recall_100 %s/%d  recall_all %s/%d  precision %s/%d"
          % (base_rp["recall_100_hits"], base_rp["recall_100_n"],
             base_rp["recall_all_hits"], base_rp["recall_all_n"],
             base_rp["precision_num"], base_rp["precision_den"]))

    # -------- S-indicator arm: drop OCR-touched rows failing ocr_is_his --------
    arm_picks = build_arm(byday, keep=True)
    arm_full = g86.stats(list(arm_picks.values()), n_days)
    arm_h1 = half_stats(arm_picks, hi=H_SPLIT, n_days=n_days_h1)
    arm_h2 = half_stats(arm_picks, lo=H_SPLIT, n_days=n_days_h2)
    dropped = sum(1 for r in touched if not ocr_survives(r))
    surviving_pop = len(pop) - dropped
    arm_cand_per_day = round(surviving_pop / n_days, 2)
    arm_fires_per_day = round(len(arm_picks) / n_days, 3)
    arm_rp = recall_and_precision(bysd, True, pool, s100_keys, bar_backed_s_all, arm_picks)

    print("\nARM (drop OCR-touched rows failing ocr_is_his): $%d/day, mean R %.3f, "
          "win %.1f%%, months green %d/%d, maxDD $%d, cand/day %.1f, fires/day %.3f"
          % (arm_full["per_day"], arm_full["mean_r"], arm_full["win_pct"],
             arm_full["months_green"], arm_full["months"], arm_full["worst_drawdown"],
             arm_cand_per_day, arm_fires_per_day))
    print("  H1 $/day $%d (base $%d)  H2 $/day $%d (base $%d)"
          % (arm_h1.get("per_day", 0), base_h1.get("per_day", 0),
             arm_h2.get("per_day", 0), base_h2.get("per_day", 0)))
    print("  recall_100 %s/%d  recall_all %s/%d  precision %s/%d"
          % (arm_rp["recall_100_hits"], arm_rp["recall_100_n"],
             arm_rp["recall_all_hits"], arm_rp["recall_all_n"],
             arm_rp["precision_num"], arm_rp["precision_den"]))

    h1_delta = arm_h1.get("per_day", 0) - base_h1.get("per_day", 0)
    h2_delta = arm_h2.get("per_day", 0) - base_h2.get("per_day", 0)
    prec_delta = (arm_rp["precision"] or 0) - (base_rp["precision"] or 0)
    survivor = (
        (h1_delta > 0 or prec_delta > 0) and (h2_delta > 0 or prec_delta > 0)
        and (arm_rp["recall_100"] or 0) >= (base_rp["recall_100"] or 0)
    )
    print("\nH1 delta $/day: %+d  H2 delta $/day: %+d  precision delta: %+.4f  "
          "survivor: %s" % (h1_delta, h2_delta, prec_delta, survivor))

    out = {
        "book": os.path.basename(BOOK), "sessions": n_days,
        "sessions_h1": n_days_h1, "sessions_h2": n_days_h2,
        "candidate_population": len(pop), "ocr_touched_rows": len(touched),
        "ocr_touched_survived": survived,
        "ocr_touched_no_readable_bars": n_no_bars,
        "ocr_touched_bars_ok_but_failed": n_no_block,
        "baseline": {
            "full": base_full, "h1": base_h1, "h2": base_h2,
            "candidates_per_day": base_cand_per_day, "fires_per_day": base_fires_per_day,
            "recall_precision": base_rp,
        },
        "arm": {
            "full": arm_full, "h1": arm_h1, "h2": arm_h2,
            "candidates_per_day": arm_cand_per_day, "fires_per_day": arm_fires_per_day,
            "recall_precision": arm_rp,
            "dropped_rows": dropped,
        },
        "h1_delta_usd_day": round(h1_delta, 2), "h2_delta_usd_day": round(h2_delta, 2),
        "precision_delta": round(prec_delta, 4),
        "survivor": survivor,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = ["# g154/F5 -- ocr-strict-definition", "",
          "**What is different now:** applied `signal_runner`'s own strict OCR "
          "definition (`OCR_STRICT`, default OFF, `signal_runner.py:63` -> "
          "`omen_bot.ocr_is_his`: clear break + quick + strong PA) as a post-hoc "
          "filter over the committed book's OCR-derived rows -- no engine re-run, "
          "just the same feature computed from `data_archive` bars up to the "
          "signal bar.", "",
          "Book `%s`, %d sessions (H1 %d / H2 %d), size-gated on "
          "`signal_runner.min_risk_floor`. 1R = $%d. H1/H2 split at %s."
          % (os.path.basename(BOOK), n_days, n_days_h1, n_days_h2, int(g86.RISK), H_SPLIT),
          "",
          "## OCR-touched rows in the one-trade-a-day candidate population", "",
          "%d rows in the candidate population match `setup == 'one_candle_rule' "
          "or confluence == 'yes'` (%d total candidates). Of those, **%d survive** "
          "`ocr_is_his` (%.1f%%); %d had no readable `data_archive` bars for that "
          "(sym, day, entry_i); %d had readable bars but failed the anatomy "
          "detector or one of clear-break/quick/strong-PA."
          % (len(touched), len(pop), survived,
             100.0 * survived / len(touched) if touched else 0.0,
             n_no_bars, n_no_block),
          "", "## Baseline vs arm (first-of-day, size-gated)", "",
          "| arm | $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD | "
          "cand/day | fires/day | recall_100 | recall_all | precision |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
          "| baseline (no OCR filter) | $%d | $%d | $%d | %+.3f | %.1f%% | %d/%d | $%d | "
          "%.1f | %.3f | %s/%d | %s/%d | %s/%d |"
          % (base_full["per_day"], base_h1.get("per_day", 0), base_h2.get("per_day", 0),
             base_full["mean_r"], base_full["win_pct"], base_full["months_green"],
             base_full["months"], base_full["worst_drawdown"], base_cand_per_day,
             base_fires_per_day, base_rp["recall_100_hits"], base_rp["recall_100_n"],
             base_rp["recall_all_hits"], base_rp["recall_all_n"],
             base_rp["precision_num"], base_rp["precision_den"]),
          "| **arm** (drop OCR-touched failing ocr_is_his) | $%d | $%d | $%d | %+.3f | "
          "%.1f%% | %d/%d | $%d | %.1f | %.3f | %s/%d | %s/%d | %s/%d |"
          % (arm_full["per_day"], arm_h1.get("per_day", 0), arm_h2.get("per_day", 0),
             arm_full["mean_r"], arm_full["win_pct"], arm_full["months_green"],
             arm_full["months"], arm_full["worst_drawdown"], arm_cand_per_day,
             arm_fires_per_day, arm_rp["recall_100_hits"], arm_rp["recall_100_n"],
             arm_rp["recall_all_hits"], arm_rp["recall_all_n"],
             arm_rp["precision_num"], arm_rp["precision_den"]),
          "", "## Verdict", "",
          "H1 delta $/day: %+d. H2 delta $/day: %+d. Precision delta: %+.4f. "
          "Survivor (H1 and H2 both improve $/day or precision, recall_100 not "
          "below baseline): **%s**." % (h1_delta, h2_delta, prec_delta, survivor)]
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
