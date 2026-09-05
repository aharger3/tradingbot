"""g154 -- F5 candidate: round-number-targets (OMEN 9.0).

Austin's claim (theme: levels, EXIT-SIDE): "Targets should include whole
psychological round numbers (188, 189), not only chart levels (HOD/LOD/PDH/
PDL/pivots)." Polarity: S-INDICATOR.

THE PREDICATE, exactly as specced for this row:

    round_grid = whole dollars, or HALF dollars when r['entry'] < 20
    cand = the nearest round_grid price strictly between r['entry'] and
           r['target'], in the trade direction
    -- where cand exists: replace the target with cand and REPLAY the exit
       from data_archive (stops via stop_rule.stop_fill_price)
    -- otherwise: leave the row untouched (original target/exit/pnl/r stand)

"nearest" is read as nearest-to-ENTRY -- the first round-number level price
would actually reach walking from entry toward the original target, i.e. a
CLOSER, more conservative target than the chart level the book already used.
That is the trading read of "targets should include round numbers": stop
running past 188 for a level at 190 if 188 is there first.

REPLAY MECHANICS (stop_rule.py, current shipped default, unabbreviated
ladder -- no scale/BE/gave-it-back legs; this is a single-target replay,
which is what the row asks for and what these book rows already are before
the substitution):

  for each bar j > entry_i (bars strictly AFTER the signal bar -- entry
  itself fills at entry_i's close, so replay starts one bar later, same
  convention as g154_rule_entry-earlier-satisfiable-bar's "no bar after the
  signal is read" but mirrored: here no bar AT OR BEFORE the signal is
  replayed, only after):
    1. disaster stop (touch, entry -/+ DISASTER_STOP_R x risk) -- tested
       FIRST, per stop_rule.py's R1/R2 ordering.
    2. level stop (CLOSE-triggered, `stop_rule.stop_fill_price`, floored at
       DISASTER_STOP_R=1.0 -- Austin, 2026-09-03: "1R is simpler... no
       stocks should be running to -10R").
    3. new target (TOUCH -- "targets are not stops", stop_rule.py's own
       words; a resting limit fills the moment price arrives).
  session runs out with none of the three true -> scratch at the last RTH
  bar's close (same treatment backtest_week.py gives an end-of-session
  open position).

Rows with no data_archive bars for that (sym, day), or no entry_i, cannot be
replayed -- FALLBACK is to leave the row untouched (same "no fabricated
number" rule the row's own "Bars features read data_archive only up to the
signal bar" line implies for every other g154 script; this is the mirror
case, reading bars strictly after it).

THE ARM (S-indicator, one-trade-a-day, `omen_metrics.first_of_day_arm`
shape): use the (possibly re-priced) BOOK -- rows where cand existed get
their pnl/r replaced by the replay; everything else is verbatim off the
committed book. `_row_is_sizeable` runs on the ORIGINAL entry/stop (risk is
unchanged by this predicate -- only the exit moves), so the size gate is
identical to baseline's.

Fraction of rows touched is reported BEFORE any R figure, per the row's own
instruction ("Report the fraction of rows the substitution touches before
reporting its R").

Recall: probe_s_sweep (34 S cards) + all bar-backed S days
(marks_pool.s_days, canonical_pool, has_bars filter) -- per-symbol-day, does
the candidate stream (post-substitution) still produce a survivor.
Precision: fired days graded S / fired days graded at all
(marks_pool.canonical_pool()), on the arm's own one-a-day picks.

Prior art for the unit: research/g91_lane_slice.py (one-trade-a-day,
months-green, max-DD path); research/g86_honest_ceiling.py (stats()/
candidates() shape). Neither re-derived.

Reads only: data_archive/<SYM>/<day>.csv (via polygon_feed, cache-first, no
network hit for archived days), research/bt2y_trades_retest_on.json,
research/marks/probe_s_sweep_2026-08-28.jsonl, research/marks_pool.py,
stop_rule.py, research/omen_metrics.py. Writes only its own two report
files. No engine file is edited.

    python research/g154_rule_round-number-targets.py
"""
from __future__ import annotations

import json
import math
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import polygon_feed as pf                                              # noqa: E402
from stop_rule import (stop_hit_on_close, stop_fill_price,              # noqa: E402
                       disaster_stop_price, disaster_stop_hit,
                       DISASTER_STOP_R)
from research import omen_metrics as om                                 # noqa: E402
from research import marks_pool as mp                                   # noqa: E402

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT_JSON = ROOT / "research" / "g154_rule_round-number-targets.json"
OUT_MD = ROOT / "research" / "g154_rule_round-number-targets.md"
PROBE_S34 = ROOT / "research" / "marks" / "probe_s_sweep_2026-08-28.jsonl"

RISK = 1000.0
BAR_PER_DAY = 397.0            # Austin's stated bar, $/day, one-trade-a-day
SPLIT_DAY = "2025-09-01"       # THE LAW's H1/H2 split


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def is_candidate(r):
    return (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted"


# --------------------------------------------------------------- bar access

_bars_cache: dict = {}


def bars_for(sym, day):
    """data_archive only -- never falls through to a network fetch."""
    k = (sym, day)
    if k not in _bars_cache:
        if len(_bars_cache) > 800:
            _bars_cache.clear()
        csv_path = pf.ARCHIVE / sym / ("%s.csv" % day)
        if not csv_path.exists():
            _bars_cache[k] = []
        else:
            try:
                _bars_cache[k] = pf.rth(pf.fetch_day(sym, day))
            except Exception:
                _bars_cache[k] = []
    return _bars_cache[k]


# ----------------------------------------------------------- the predicate

def round_grid_step(entry):
    return 0.5 if entry < 20 else 1.0


def nearest_round_between(entry, target, step):
    """The round_grid price strictly between entry and target, nearest to
    ENTRY (the first one price reaches walking toward the original target).
    None if no grid price is strictly between them."""
    lo, hi = (entry, target) if target > entry else (target, entry)
    k0 = math.floor(lo / step) + 1
    cands = []
    k = k0
    while True:
        v = round(k * step, 4)
        if v >= hi - 1e-9:
            break
        if v > lo + 1e-9:
            cands.append(v)
        k += 1
    if not cands:
        return None
    return min(cands, key=lambda v: abs(v - entry))


_touch_cache: dict = {}


def touched_cand(r):
    """cand price, or None if no round-grid price sits strictly between
    entry and target for this row. Cached per (sym, day, et) key."""
    key = ekey(r)
    if key in _touch_cache:
        return _touch_cache[key]
    step = round_grid_step(r["entry"])
    cand = nearest_round_between(r["entry"], r["target"], step)
    _touch_cache[key] = cand
    return cand


_replay_cache: dict = {}


def replay_exit(r, cand):
    """Re-price the trade with target -> cand, replayed off data_archive
    bars strictly after the signal bar. Returns (exit_px, r_mult, outcome)
    or None if it cannot be replayed (no bars / no entry_i)."""
    key = ekey(r)
    if key in _replay_cache:
        return _replay_cache[key]

    entry_i = r.get("entry_i")
    out = None
    if entry_i is not None:
        bars = bars_for(r["sym"], r["day"])
        if bars and entry_i + 1 < len(bars):
            entry = r["entry"]
            stop = r["stop"]
            risk = abs(entry - stop)
            long = r["dir"] == "call"
            if risk > 0:
                dpx = disaster_stop_price(entry, risk, long, DISASTER_STOP_R)
                for j in range(entry_i + 1, len(bars)):
                    bj = bars[j]
                    if disaster_stop_hit(bj.high, bj.low, dpx, long):
                        r_mult = -DISASTER_STOP_R
                        out = (dpx, r_mult, "loss")
                        break
                    if stop_hit_on_close(bj.close, stop, long):
                        fill = stop_fill_price(bj.close, entry, risk, long,
                                               DISASTER_STOP_R)
                        r_mult = ((fill - entry) / risk if long
                                 else (entry - fill) / risk)
                        outcome = ("loss" if r_mult < 0 else
                                  ("win" if r_mult > 0 else "scratch"))
                        out = (fill, r_mult, outcome)
                        break
                    touched = (bj.high >= cand) if long else (bj.low <= cand)
                    if touched:
                        r_mult = ((cand - entry) / risk if long
                                 else (entry - cand) / risk)
                        out = (cand, r_mult, "win")
                        break
                if out is None:
                    last = bars[-1]
                    r_mult = ((last.close - entry) / risk if long
                             else (entry - last.close) / risk)
                    outcome = ("win" if r_mult > 0 else
                              ("loss" if r_mult < 0 else "scratch"))
                    out = (last.close, r_mult, outcome)
    _replay_cache[key] = out
    return out


def repriced_rows(rows):
    """Returns (new_rows, n_touched, n_candidates) -- a copy of `rows` where
    every candidate row (fired&traded or halted) with a valid `cand` and a
    successful replay has its exit/pnl/r substituted; all other rows are
    passed through verbatim (same dict objects, since nothing else reads
    them destructively)."""
    out_rows = []
    n_touched = 0
    n_cand = 0
    for r in rows:
        if not is_candidate(r):
            out_rows.append(r)
            continue
        n_cand += 1
        cand = touched_cand(r)
        if cand is None:
            out_rows.append(r)
            continue
        replay = replay_exit(r, cand)
        if replay is None:
            out_rows.append(r)
            continue
        exit_px, r_mult, outcome = replay
        r2 = dict(r)
        r2["target"] = cand
        r2["exit"] = round(exit_px, 4)
        r2["out"] = outcome
        r2["r"] = round(r_mult, 4)
        r2["pnl"] = round(r_mult * RISK, 2)
        out_rows.append(r2)
        n_touched += 1
    return out_rows, n_touched, n_cand


# --------------------------------------------------------------------- arms

def one_a_day(rows):
    """omen_metrics.first_of_day_arm shape, size-gated, on whichever rows
    list is passed (baseline or re-priced)."""
    return om.first_of_day_arm(rows, size_gate=True)


# ------------------------------------------------------------------ stats

def half(day):
    return "H1" if day < SPLIT_DAY else "H2"


def arm_stats(picks, all_days):
    dset = {d: 0.0 for d in all_days}
    for r in picks:
        dset[r["day"]] = dset.get(r["day"], 0.0) + r["pnl"]
    n_days = len(all_days)
    total = sum(r["pnl"] for r in picks)
    rs = [r["r"] for r in picks]
    wins = sum(1 for v in rs if v > 0)
    losses = sum(1 for v in rs if v < 0)
    by_m = defaultdict(float)
    for d, v in dset.items():
        by_m[d[:7]] += v
    g = sum(1 for v in by_m.values() if v > 0)
    m = len(by_m)
    cum = peak = dd = 0.0
    for d in sorted(dset):
        cum += dset[d]
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return {
        "trades": len(picks),
        "sessions": n_days,
        "fires_per_day": round(len(picks) / n_days, 4) if n_days else 0.0,
        "usd_day": round(total / n_days, 2) if n_days else 0.0,
        "mean_r": round(statistics.fmean(rs), 4) if rs else 0.0,
        "win_pct": round(wins / (wins + losses) * 100, 1) if wins + losses else 0.0,
        "months_green": "%d/%d" % (g, m),
        "months_green_n": g, "months_total": m,
        "max_dd_usd": round(dd, 2),
        "pct_of_bar": round((total / n_days) / BAR_PER_DAY * 100, 1) if n_days else None,
    }


def split(picks, days):
    dset = set(days)
    return [r for r in picks if r["day"] in dset]


# ------------------------------------------------------------ S recall

def candidate_stream_by_symday(rows):
    out = defaultdict(list)
    for r in rows:
        if is_candidate(r):
            out[(r["sym"], r["day"])].append(r)
    return out


def _symday_survivors(stream, sym, day):
    rows = stream.get((sym, day), [])
    return [r for r in rows if om._row_is_sizeable(r) is not False]


def recall(keys, stream):
    n = base_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        if _symday_survivors(stream, sym, day):
            base_hit += 1
    return (round(base_hit / n * 100, 1) if n else None, n)


def load_probe_s_days():
    keys = []
    with open(PROBE_S34, encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if mp.row_grade(row) == "S":
                keys.append(row["card_id"])
    return keys


# ----------------------------------------------------------- precision

def precision(picks, pool):
    graded_at_all = graded_s = 0
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

    new_rows, n_touched, n_cand = repriced_rows(rows)
    touched_frac = round(n_touched / n_cand * 100, 2) if n_cand else 0.0

    baseline_picks = one_a_day(rows)
    arm_picks = one_a_day(new_rows)

    baseline_all = arm_stats(baseline_picks, all_days)
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days)
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days)
    arm_all = arm_stats(arm_picks, all_days)
    arm_h1 = arm_stats(split(arm_picks, h1_days), h1_days)
    arm_h2 = arm_stats(split(arm_picks, h2_days), h2_days)

    stream_baseline = candidate_stream_by_symday(rows)
    stream_arm = candidate_stream_by_symday(new_rows)

    total_cands = sum(1 for r in rows if is_candidate(r))
    cands_per_day = round(total_cands / len(all_days), 2)

    probe_keys = load_probe_s_days()
    probe_base_recall, probe_n = recall(probe_keys, stream_baseline)
    probe_arm_recall, _ = recall(probe_keys, stream_arm)

    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]
    pool_base_recall, pool_n = recall(bar_backed_s_keys, stream_baseline)
    pool_arm_recall, _ = recall(bar_backed_s_keys, stream_arm)

    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)
    arm_prec, arm_prec_s, arm_prec_n = precision(arm_picks, pool)

    h1_delta = arm_h1["usd_day"] - baseline_h1["usd_day"]
    h2_delta = arm_h2["usd_day"] - baseline_h2["usd_day"]
    h1_improves = (arm_h1["usd_day"] > baseline_h1["usd_day"]) or (
        (arm_prec or 0) > (base_prec or 0))
    h2_improves = (arm_h2["usd_day"] > baseline_h2["usd_day"]) or (
        (arm_prec or 0) > (base_prec or 0))
    recall_ok = (probe_arm_recall is None or probe_base_recall is None
                 or probe_arm_recall >= probe_base_recall) and (
        pool_arm_recall is None or pool_base_recall is None
        or pool_arm_recall >= pool_base_recall)
    survivor = bool(h1_improves and h2_improves and recall_ok)

    out = {
        "book": os.path.basename(str(BOOK)),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "round-number-targets",
        "polarity": "S-indicator (exit-side)",
        "predicate": {
            "round_grid": "whole dollars; half dollars when entry < 20",
            "cand": "nearest round_grid price strictly between entry and "
                    "target, nearest to entry, in the trade direction",
            "action": "where cand exists: target -> cand, replay exit from "
                       "data_archive (disaster stop touch, level stop close "
                       "via stop_rule.stop_fill_price floored at "
                       "DISASTER_STOP_R=%.1f, new target touch); else leave "
                       "row untouched" % DISASTER_STOP_R,
        },
        "substitution": {
            "candidates_total": n_cand,
            "touched": n_touched,
            "touched_pct": touched_frac,
        },
        "candidates_per_day": cands_per_day,
        "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "candidate": {"all": arm_all, "h1": arm_h1, "h2": arm_h2},
        "h1_delta_usd_day": round(h1_delta, 2),
        "h2_delta_usd_day": round(h2_delta, 2),
        "recall": {
            "probe_s_sweep_34": {
                "n": probe_n, "baseline_pct": probe_base_recall,
                "candidate_pct": probe_arm_recall,
            },
            "bar_backed_s_days_canonical_pool": {
                "n": pool_n, "baseline_pct": pool_base_recall,
                "candidate_pct": pool_arm_recall,
            },
        },
        "precision": {
            "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
            "candidate": {"pct": arm_prec, "s": arm_prec_s, "graded": arm_prec_n},
        },
        "survivor": survivor,
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    _write_md(baseline_all, baseline_h1, baseline_h2, arm_all, arm_h1, arm_h2,
              h1_delta, h2_delta, probe_n, probe_base_recall, probe_arm_recall,
              pool_n, pool_base_recall, pool_arm_recall,
              base_prec, base_prec_s, base_prec_n, arm_prec, arm_prec_s, arm_prec_n,
              survivor, n_cand, n_touched, touched_frac, cands_per_day)

    print("candidates: %d  touched: %d (%.2f%%)" % (n_cand, n_touched, touched_frac))
    print("baseline $/day: %.2f  candidate $/day: %.2f" % (baseline_all["usd_day"], arm_all["usd_day"]))
    print("survivor: %s" % survivor)


def _write_md(baseline_all, baseline_h1, baseline_h2, arm_all, arm_h1, arm_h2,
             h1_delta, h2_delta, probe_n, probe_base_recall, probe_arm_recall,
             pool_n, pool_base_recall, pool_arm_recall,
             base_prec, base_prec_s, base_prec_n, arm_prec, arm_prec_s, arm_prec_n,
             survivor, n_cand, n_touched, touched_frac, cands_per_day):
    md = []
    md.append("# g154 F5 -- round-number-targets")
    md.append("")
    verdict = ("SURVIVOR" if survivor else "not a survivor")
    md.append("**One sentence: the round-number-target substitution touches "
              "%.2f%% of the book's %d candidate rows (%d of them), and is "
              "%s** on the honest, retest-on book, one-trade-a-day unit, "
              "size-gated -- H1 %+.0f/day, H2 %+.0f/day."
              % (touched_frac, n_cand, n_touched, verdict, h1_delta, h2_delta))
    md.append("")
    md.append("Predicate: round_grid = whole dollars, or half dollars when "
              "entry < $20. cand = the round_grid price strictly between "
              "entry and target, nearest to ENTRY (the first round number "
              "price reaches walking from entry toward the original "
              "target), in the trade direction. Where cand exists, the "
              "target is replaced with cand and the exit is replayed off "
              "data_archive bars strictly after the signal bar: disaster "
              "stop (touch, -%.1fR), level stop (close, "
              "stop_rule.stop_fill_price, floored at %.1fR), new target "
              "(touch). Rows with no cand, or that cannot be replayed (no "
              "data_archive bars / no entry_i), are left untouched."
              % (DISASTER_STOP_R, DISASTER_STOP_R))
    md.append("")
    md.append("## Substitution rate (reported before any R figure, per the row spec)")
    md.append("")
    md.append("| candidates (fired&traded or halted) | touched | fraction |")
    md.append("|---:|---:|---:|")
    md.append("| %d | %d | %.2f%% |" % (n_cand, n_touched, touched_frac))
    md.append("")
    md.append("candidates/day (raw arrival stream, whole pool): **%.2f**" % cands_per_day)
    md.append("")
    md.append("## Money -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| arm | split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for label, sp, s in (("baseline", "all", baseline_all), ("baseline", "H1", baseline_h1),
                        ("baseline", "H2", baseline_h2), ("candidate", "all", arm_all),
                        ("candidate", "H1", arm_h1), ("candidate", "H2", arm_h2)):
        md.append("| %s | %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                  % (label, sp, s["usd_day"], s["mean_r"], s["win_pct"],
                     s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
    md.append("")
    md.append("H1/H2 split at **%s**. delta $/day (candidate vs baseline): "
              "H1 %+.2f, H2 %+.2f." % (SPLIT_DAY, h1_delta, h2_delta))
    md.append("")
    md.append("## S recall")
    md.append("")
    md.append("| set | n | baseline | candidate |")
    md.append("|---|---:|---:|---:|")
    md.append("| probe_s_sweep (34 S cards) | %d | %s%% | %s%% |"
              % (probe_n, probe_base_recall, probe_arm_recall))
    md.append("| bar-backed S days (canonical_pool) | %d | %s%% | %s%% |"
              % (pool_n, pool_base_recall, pool_arm_recall))
    md.append("")
    md.append("## Precision (fired days graded S / fired days graded at all)")
    md.append("")
    md.append("| arm | precision | S / graded |")
    md.append("|---|---:|---:|")
    md.append("| baseline | %s%% | %d / %d |" % (base_prec, base_prec_s, base_prec_n))
    md.append("| candidate | %s%% | %d / %d |" % (arm_prec, arm_prec_s, arm_prec_n))
    md.append("")
    md.append("Survivor rule: H1 AND H2 both improve $/day or precision, "
              "and recall on both S-day panels does not fall below "
              "baseline. **Result: %s.**" % verdict)
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
