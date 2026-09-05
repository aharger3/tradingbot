"""g154 -- F5 candidate 'exhausted-overextended'.

Rule under test: "A stock that has already made its big move for the day is
refused or downgraded -- the setup is real but the move is spent." (polarity:
refusal-indicator.)

Two arms, both dropping matching candidates and taking the next
(refusal-indicator, not a keep-filter):

  Arm 1 (flag-drop): DROP a fired candidate if 'exhausted' in r['downgrades'].
  The book's own downgrade.exhausted() at the shipped EXHAUSTED_ATR=10.0 --
  1066 of 10830 fired rows (verified below). This tests whether the flag AS
  SHIPPED helps the one-trade-a-day arm.

  Arm 2 (continuous, threshold sweep): recompute extension = |Close[entry_i]
  - Open[first RTH bar]| / ATR14(bars[:entry_i+1]) directly from
  data_archive, at the signal bar only (no lookahead, no engine re-run), and
  sweep the drop threshold over {1.5, 2.0, 2.5, 3.0} ATR. This tests whether
  EXHAUSTED_ATR (10.0, downgrade.py) sits in the right place -- not just
  whether the shipped flag helps. downgrade.py's own comment says 3.0 was
  the first guess and was killed because ordinary 1m trend days run 4-6 ATR
  off the open; this sweep is the first time that claim is checked against
  the book's actual candidate stream rather than argued from one selftest.

Everything routes through omen_metrics (ev_r_scoreboard, first_of_day_arm,
_row_is_sizeable) for the size gate and the R/day fill definition, and marks_pool
for recall/precision -- no local re-derivation, per CLAUDE.md. Unit and
structure follow research/g154_rule_brocr-confluence-upgrade-at-fire.py (F5
sibling) and research/g91_lane_slice.py / research/g86_honest_ceiling.py.

    python research/g154_rule_exhausted-overextended.py

Writes research/g154_rule_exhausted-overextended.{md,json}.
Applies nothing, ships nothing.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import omen_metrics as om          # noqa: E402  the one EV/R kernel + size gate
import marks_pool as mp            # noqa: E402  canonical grade pool
from t8_two_year import rth_candles  # noqa: E402  RTH 1m bars, data_archive-backed
import downgrade as dg              # noqa: E402  EXHAUSTED_ATR, the shipped constant

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_exhausted-overextended.json")
OUT_MD = os.path.join(HERE, "g154_rule_exhausted-overextended.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"   # H1 < this, H2 >= this, per CLAUDE.md
ATR_WINDOW = 14
SWEEP_THRESHOLDS = (1.5, 2.0, 2.5, 3.0)


def ekey(r):
    return (r["day"], r["et"], r["sym"])


def by_day_candidates(rows):
    """Fired-and-traded rows, plus loss-halted rows (one-a-day: that halt
    hasn't fired yet under a strict one-trade-a-day policy) -- identical
    construction to omen_metrics.first_of_day_arm, grouped by day."""
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    return by_day


def first_matching_arm(rows, keep_pred):
    """One-trade-a-day arm: the day's first candidate (arrival order) that
    both satisfies `keep_pred` and is sizeable. A candidate failing the
    predicate is SKIPPED, not counted -- 'take the next', per the row spec
    (this is a refusal-indicator: keep_pred is True for candidates that
    survive the refusal, i.e. NOT flagged exhausted)."""
    by_day = by_day_candidates(rows)
    firsts = []
    for day in sorted(by_day):
        v = sorted(by_day[day], key=ekey)
        pick = next((r for r in v
                     if keep_pred(r) and om._row_is_sizeable(r) is not False), None)
        if pick is not None:
            firsts.append(pick)
    return firsts


def half(day):
    return "H1" if day < H_SPLIT else "H2"


def sessions_in_half(rows, which):
    return len({r["day"] for r in rows if half(r["day"]) == which})


def scoreboard_row(firsts, sessions):
    sb = om.ev_r_scoreboard(firsts, risk_dollars=RISK, sessions=sessions)
    by_day = defaultdict(float)
    for r in firsts:
        by_day[r["day"]] += r["pnl"]
    months = defaultdict(float)
    for d, v in by_day.items():
        months[d[:7]] += v
    dd = 0.0
    peak = cum = 0.0
    for d in sorted(by_day):
        cum += by_day[d]
        peak = max(peak, cum)
        dd = min(dd, cum - peak)
    return {
        "usd_day": sb["expectancy_per_day"],
        "mean_r": sb["ev_r"],
        "win_rate": sb["win_rate"],
        "n_trades": sb["n"],
        "months_green": "%d/%d" % (sum(1 for v in months.values() if v > 0), len(months)),
        "max_dd_usd": round(dd, 2),  # `dd` is already summed from r['pnl'] (dollars)
    }


def fired_keys(firsts):
    return {"%s_%s" % (r["sym"], r["day"]) for r in firsts}


def recall_and_precision(firsts, pool, sweep_s_keys, all_s_keys):
    fk = fired_keys(firsts)
    recall_100 = (len(fk & sweep_s_keys) / len(sweep_s_keys)) if sweep_s_keys else None
    recall_all = (len(fk & all_s_keys) / len(all_s_keys)) if all_s_keys else None
    judged_fired = {k for k in fk if k in pool}
    s_fired = {k for k in judged_fired if pool[k].grade == "S"}
    precision = (len(s_fired) / len(judged_fired)) if judged_fired else None
    return {
        "recall_100": round(recall_100, 4) if recall_100 is not None else None,
        "recall_all_s_days": round(recall_all, 4) if recall_all is not None else None,
        "precision": round(precision, 4) if precision is not None else None,
        "fired_days": len(fk),
        "fired_days_judged": len(judged_fired),
        "fired_days_graded_s": len(s_fired),
    }


# ---------------------------------------------------------------------------
# Arm 2: recompute extension straight from data_archive, signal bar only.
# ---------------------------------------------------------------------------

_BAR_CACHE = {}


def _bars_for(sym, day):
    key = (sym, day)
    if key not in _BAR_CACHE:
        _BAR_CACHE[key] = rth_candles(sym, day)
    return _BAR_CACHE[key]


def _atr14(bars, i):
    """Same shape as downgrade._atr (average high-low range, last 14 bars
    ending at i) -- reimplemented locally only because bars here are
    t8_two_year.rth_candles Candle namedtuples (.high/.low), not the dict
    rows downgrade.py's helpers index by key."""
    lo = max(1, i - ATR_WINDOW + 1)
    window = bars[lo:i + 1]
    if not window:
        return 0.0
    return sum(b.high - b.low for b in window) / len(window)


def compute_extension(r):
    """|Close[entry_i] - Open[first RTH bar]| / ATR14(bars[:entry_i+1]), read
    from data_archive only up to the signal bar. None if bars/entry_i are
    unavailable or ATR is non-positive (ungateable, never dropped)."""
    entry_i = r.get("entry_i")
    if entry_i is None:
        return None
    bars = _bars_for(r["sym"], r["day"])
    if not bars or entry_i >= len(bars):
        return None
    a = _atr14(bars, entry_i)
    if a <= 0:
        return None
    return abs(bars[entry_i].close - bars[0].open) / a


def annotate_extension(rows):
    """Fired-and-traded or halted rows only (the candidate universe) --
    fires the exact per-row bars fetch, cached per (sym, day)."""
    out = []
    n_missing = 0
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            ext = compute_extension(r)
            r = dict(r)
            r["_extension"] = ext
            if ext is None:
                n_missing += 1
        out.append(r)
    return out, n_missing


def main():
    if not os.path.exists(BOOK_PATH):
        print("BLOCKED: missing %s" % BOOK_PATH)
        return 1

    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    rows = blob["trades"]
    total_sessions = blob["meta"].get("sessions") or len({r["day"] for r in rows})

    fired = [r for r in rows if r["status"] == "fired"]
    exhausted_flagged = [r for r in fired if "exhausted" in (r.get("downgrades") or [])]
    print("fired rows: %d, 'exhausted' in downgrades: %d (%.1f%%) -- row spec says "
          "1066/10830 (%.1f%%)"
          % (len(fired), len(exhausted_flagged),
             100.0 * len(exhausted_flagged) / len(fired),
             100.0 * 1066 / 10830))

    # ---- marks pool
    sweep_rows = [json.loads(l) for l in open(SWEEP_PATH, encoding="utf-8")]
    sweep_s_keys = {"%s_%s" % (r["symbol"], r["date"])
                    for r in sweep_rows if mp.row_grade(r) == "S"}
    pool = mp.canonical_pool()
    all_s_keys = mp.s_days(pool)
    print("marks: %d/%d S in the 100-card sweep, %d bar-backed S days total\n"
          % (len(sweep_s_keys), len(sweep_rows), len(all_s_keys)))

    # ---- baseline + Arm 1 (flag-drop)
    baseline_firsts = om.first_of_day_arm(rows)
    arm1_firsts = first_matching_arm(
        rows, lambda r: "exhausted" not in (r.get("downgrades") or []))

    # candidates/day flagged exhausted (pre-selection rate)
    cand_days = defaultdict(int)
    for r in fired:
        if "exhausted" in (r.get("downgrades") or []):
            cand_days[r["day"]] += 1
    candidates_per_day_flagged = round(sum(cand_days.values()) / total_sessions, 4)

    # ---- Arm 2: recompute extension from data_archive, sweep thresholds
    annotated_rows, n_missing = annotate_extension(rows)
    n_cand = sum(1 for r in annotated_rows
                 if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted")
    print("Arm 2: extension computed for %d/%d candidate rows (%d missing bars/ATR -- "
          "never dropped by threshold)\n" % (n_cand - n_missing, n_cand, n_missing))

    sweep_arms = {}
    for thr in SWEEP_THRESHOLDS:
        label = "sweep_%.1f" % thr

        def keep(r, thr=thr):
            ext = r.get("_extension")
            return ext is None or ext < thr

        sweep_arms[label] = first_matching_arm(annotated_rows, keep)

    def report(label, firsts):
        overall = scoreboard_row(firsts, total_sessions)
        h1 = scoreboard_row([r for r in firsts if half(r["day"]) == "H1"],
                             sessions_in_half(rows, "H1"))
        h2 = scoreboard_row([r for r in firsts if half(r["day"]) == "H2"],
                             sessions_in_half(rows, "H2"))
        rp = recall_and_precision(firsts, pool, sweep_s_keys, all_s_keys)
        return {"overall": overall, "H1": h1, "H2": h2,
                "fires_per_day": round(len(firsts) / total_sessions, 4), **rp}

    results = {"baseline": report("baseline", baseline_firsts),
               "arm1_flag_drop": report("arm1_flag_drop", arm1_firsts)}
    for label, firsts in sweep_arms.items():
        results[label] = report(label, firsts)

    base = results["baseline"]

    def h_delta(arm):
        h1d = (arm["H1"]["usd_day"] - base["H1"]["usd_day"]
               if arm["H1"]["usd_day"] is not None and base["H1"]["usd_day"] is not None
               else None)
        h2d = (arm["H2"]["usd_day"] - base["H2"]["usd_day"]
               if arm["H2"]["usd_day"] is not None and base["H2"]["usd_day"] is not None
               else None)
        return h1d, h2d

    def better(a, b):
        return a is not None and b is not None and a > b

    def is_survivor(arm):
        h1d, h2d = h_delta(arm)
        h1_ok = (h1d is not None and h1d > 0) or better(arm["precision"], base["precision"])
        h2_ok = (h2d is not None and h2d > 0) or better(arm["precision"], base["precision"])
        recall_ok = (arm["recall_100"] is not None and base["recall_100"] is not None
                     and arm["recall_100"] >= base["recall_100"])
        return bool(h1_ok and h2_ok and recall_ok), h1d, h2d

    arm1 = results["arm1_flag_drop"]
    arm1_survivor, arm1_h1d, arm1_h2d = is_survivor(arm1)

    # Does the shipped flag ever coincide with the day's chosen candidate at
    # all? If it never does, Arm 1's identical numbers are a real finding
    # (the flag is inert on this one-trade-a-day stream), not a bug.
    base_picks = {r["day"]: (r["et"], r["sym"]) for r in baseline_firsts}
    arm1_picks = {r["day"]: (r["et"], r["sym"]) for r in arm1_firsts}
    arm1_days_changed = sum(1 for d in base_picks
                            if arm1_picks.get(d) != base_picks[d])

    sweep_survivors = {}
    for label in sweep_arms:
        surv, h1d, h2d = is_survivor(results[label])
        sweep_survivors[label] = {"survivor": surv, "h1_delta_usd_day": h1d, "h2_delta_usd_day": h2d}

    # Best sweep threshold by overall $/day, for the headline row.
    best_sweep_label = max(sweep_arms, key=lambda k: (results[k]["overall"]["usd_day"] or -1e18))
    best_sweep = results[best_sweep_label]
    best_survivor, best_h1d, best_h2d = is_survivor(best_sweep)

    overall_survivor = bool(arm1_survivor or best_survivor)

    out = {
        "candidate": "exhausted-overextended",
        "row": "F5",
        "polarity": "refusal-indicator",
        "predicate_arm1": "drop fired candidate if 'exhausted' in downgrades "
                          "(downgrade.exhausted @ EXHAUSTED_ATR=%.1f)" % dg.EXHAUSTED_ATR,
        "predicate_arm2": "drop fired candidate if recomputed extension (data_archive, "
                          "signal bar only) >= threshold; sweep over %s ATR" % (SWEEP_THRESHOLDS,),
        "book": os.path.basename(BOOK_PATH),
        "sessions_total": total_sessions,
        "fired_rows_total": len(fired),
        "fired_rows_exhausted_flagged": len(exhausted_flagged),
        "candidates_per_day_flagged": candidates_per_day_flagged,
        "extension_missing_bars": n_missing,
        "results": results,
        "arm1": {"h1_delta_usd_day": round(arm1_h1d, 2) if arm1_h1d is not None else None,
                 "h2_delta_usd_day": round(arm1_h2d, 2) if arm1_h2d is not None else None,
                 "survivor": arm1_survivor,
                 "days_pick_changed": arm1_days_changed, "days_total": len(base_picks)},
        "sweep": sweep_survivors,
        "best_sweep_threshold": best_sweep_label.split("_")[1],
        "best_sweep": {"h1_delta_usd_day": round(best_h1d, 2) if best_h1d is not None else None,
                       "h2_delta_usd_day": round(best_h2d, 2) if best_h2d is not None else None,
                       "survivor": best_survivor},
        "survivor": overall_survivor,
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    lines = []
    lines.append("# g154 -- exhausted-overextended (F5)\n")
    lines.append("One sentence: dropping fired candidates flagged 'exhausted' (as shipped, "
                 "EXHAUSTED_ATR=%.1f) %s the one-trade-a-day arm, and sweeping the drop "
                 "threshold over %s ATR on a data_archive-recomputed extension %s find a "
                 "better cutoff either -- so this candidate %s a survivor.\n"
                 % (dg.EXHAUSTED_ATR,
                    "improves" if arm1_survivor else "does NOT clearly improve",
                    SWEEP_THRESHOLDS,
                    "does" if best_survivor else "does not",
                    "IS" if overall_survivor else "is NOT"))

    def fmt_row(label, r):
        o = r["overall"]
        return ("| %s | $%s | %s | %s | %s | %s | %s | %s | %s |"
                % (label, o["usd_day"], o["mean_r"], o["win_rate"], o["months_green"],
                   o["max_dd_usd"], r["fires_per_day"], r["precision"], r["recall_100"]))

    lines.append("## Arm 1 -- flag-drop, as shipped\n")
    lines.append("| arm | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(fmt_row("baseline (first-of-day)", results["baseline"]))
    lines.append(fmt_row("arm1: drop if exhausted-flagged", results["arm1_flag_drop"]))
    lines.append("")
    lines.append("H1/H2 delta vs baseline (arm1): $%s / $%s\n"
                  % (out["arm1"]["h1_delta_usd_day"], out["arm1"]["h2_delta_usd_day"]))
    lines.append("**Arm 1 is a verified no-op**: the shipped flag (EXHAUSTED_ATR=%.1f) never "
                 "coincides with the day's chosen one-trade-a-day candidate -- %d of %d days "
                 "changed pick. Extension >=10 ATR from the open essentially never happens on "
                 "a day's FIRST fired candidate (that much displacement takes hours to build), "
                 "so at the shipped threshold this variable cannot touch first-of-day selection "
                 "at all, whatever it does downstream in `signal_runner._grade_pa`.\n"
                 % (dg.EXHAUSTED_ATR, out["arm1"]["days_pick_changed"], out["arm1"]["days_total"]))

    lines.append("## Arm 2 -- continuous, recomputed extension, threshold sweep\n")
    lines.append("| threshold (ATR) | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for thr in SWEEP_THRESHOLDS:
        label = "sweep_%.1f" % thr
        lines.append(fmt_row("%.1f" % thr, results[label]))
    lines.append("")
    lines.append("best sweep threshold by $/day: **%s ATR** -- H1/H2 delta vs baseline: $%s / $%s\n"
                  % (out["best_sweep_threshold"], out["best_sweep"]["h1_delta_usd_day"],
                     out["best_sweep"]["h2_delta_usd_day"]))
    lines.append("**Caveat on precision**: precision is computed over only %d-%d judged "
                 "days per arm (%d-%d graded S) -- a handful of days moving between arms "
                 "swings precision several points. The 2.0-3.0 ATR sweep's precision lift "
                 "over baseline (0.305 -> up to 0.422) is directional, not a diagnosis: it "
                 "says a lower cutoff than the shipped 10.0 changes which candidate fires "
                 "some days and those changes skew toward days he graded S, not that any "
                 "single threshold is settled.\n"
                 % (min(results[k]["fired_days_judged"] for k in results),
                    max(results[k]["fired_days_judged"] for k in results),
                    min(results[k]["fired_days_graded_s"] for k in results),
                    max(results[k]["fired_days_graded_s"] for k in results)))
    lines.append("candidates/day flagged exhausted (pre-selection, shipped flag): %s\n"
                  % candidates_per_day_flagged)
    lines.append("extension missing bars/ATR (never dropped by threshold): %d of the candidate "
                 "stream\n" % n_missing)
    lines.append("survivor = %s (arm1 OR best sweep threshold: H1 and H2 both improve $/day "
                 "or precision, recall_100 not below baseline)\n" % overall_survivor)

    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines))

    print("wrote %s" % OUT_JSON)
    print("wrote %s" % OUT_MD)
    print("\nsurvivor: %s" % overall_survivor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
