"""g154 F5 -- candidate "or-break-without-retest".

Austin's claim (theme: levels): a break of the opening range that fires
WITHOUT a subsequent retest of ORH/ORL is a lower-probability setup /
fakeout, even though the opening range is one of his six levels.

Polarity: REFUSAL-INDICATOR. This measures it as a DROP-only predicate over
the honest, retest-on book (research/bt2y_trades_retest_on.json), on the
one-trade-a-day unit (research/omen_metrics.first_of_day_arm, size-gated).

Predicate, exactly as specced:

    ARM (OR-specific)  -- DROP r if r['level'] in ('OR high', 'OR low')
                            and 'no_retest' in r['downgrades']
    CONTROL (blanket)  -- DROP r if 'no_retest' in r['downgrades']
                            regardless of level

The row spec's own question: if the OR-specific arm is no better than the
blanket one, the OR specificity claimed in the theme note is not real -- the
"no retest" penalty would just be a level-blind fact about the retest flag,
not something special about the opening range. Both arms are measured and
compared; the OR-specific arm is the one that gates SURVIVOR.

Fired base (status=='fired', all 10830 rows, not the one-a-day unit):
OR high 1140, OR low 1037. 2711 fired rows carry 'no_retest' in downgrades
regardless of level, even with RETEST_REQUIRED on -- the flag caps grade at
fire time, it does not veto the fire. Both counts are reproduced below.

Recall is scored per SYMBOL-DAY (same construction as g154's other rule
scripts): does the book's fired/traded/halted candidate stream for that
symbol-day still produce a survivor after the DROP predicate is applied.
Precision is scored on the global one-a-day arm's own picks against
research/marks_pool.canonical_pool().

    python research/g154_rule_or-break-without-retest.py

Writes research/g154_rule_or-break-without-retest.json and .md. Nothing
here is applied; ships nothing.
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
OUT_JSON = os.path.join(HERE, "g154_rule_or-break-without-retest.json")
OUT_MD = os.path.join(HERE, "g154_rule_or-break-without-retest.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"          # H1/H2 split, per row spec
BAR = 397.0                        # Austin's stated bar, for context only
OR_LEVELS = ("OR high", "OR low")


# --------------------------------------------------------------------- rule

def drop_or_specific(r):
    """ARM: refusal-indicator -- OR level break firing without a retest."""
    return r.get("level") in OR_LEVELS and "no_retest" in r.get("downgrades", [])


def drop_blanket(r):
    """CONTROL: refusal-indicator -- any level firing without a retest."""
    return "no_retest" in r.get("downgrades", [])


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


def candidate_arm(rows, drop_fn):
    """Pure refusal-indicator walk: skip DROP-matching sizeable rows, take
    the first surviving row in arrival order. A day where nothing survives
    produces no trade that day."""
    by_day = _candidate_stream(rows)
    picks = []
    for day in sorted(by_day):
        survivors = [r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False
                     and not drop_fn(r)]
        if not survivors:
            continue
        picks.append(survivors[0])
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

def _symday_survivors(rows_by_symday, sym, day, drop_fn):
    rows = rows_by_symday.get((sym, day), [])
    sizeable = [r for r in rows if om._row_is_sizeable(r) is not False]
    if drop_fn is None:
        return sizeable
    return [r for r in sizeable if not drop_fn(r)]


def recall(keys, rows_by_symday, drop_fn):
    """keys: iterable of 'SYM_YYYY-MM-DD'. Returns (baseline_recall,
    arm_recall, n) -- fraction of those symbol-days where the book still
    fires at all (baseline) vs still fires after the DROP predicate
    (candidate)."""
    n = 0
    base_hit = arm_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        base = _symday_survivors(rows_by_symday, sym, day, None)
        arm = _symday_survivors(rows_by_symday, sym, day, drop_fn)
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

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)
    arm_picks = candidate_arm(rows, drop_or_specific)
    control_picks = candidate_arm(rows, drop_blanket)

    by_day_stream = _candidate_stream(rows)
    cand_stream_by_symday = defaultdict(list)
    for day, v in by_day_stream.items():
        for r in v:
            cand_stream_by_symday[(r["sym"], day)].append(r)
    total_cands = sum(len(v) for v in by_day_stream.values())

    def split(picks, days):
        dset = set(days)
        return [r for r in picks if r["day"] in dset]

    baseline_all = arm_stats(baseline_picks, all_days, "baseline (whole book)")
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days, "baseline H1")
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days, "baseline H2")
    arm_all = arm_stats(arm_picks, all_days, "candidate (whole book)")
    arm_h1 = arm_stats(split(arm_picks, h1_days), h1_days, "candidate H1")
    arm_h2 = arm_stats(split(arm_picks, h2_days), h2_days, "candidate H2")
    control_all = arm_stats(control_picks, all_days, "control (whole book)")
    control_h1 = arm_stats(split(control_picks, h1_days), h1_days, "control H1")
    control_h2 = arm_stats(split(control_picks, h2_days), h2_days, "control H2")

    cands_per_day = round(total_cands / len(all_days), 2)

    # -- fired base rates (status=='fired', 10830 rows, NOT the one-a-day unit)
    fired = [r for r in rows if r["status"] == "fired"]
    fired_or_high = sum(1 for r in fired if r.get("level") == "OR high")
    fired_or_low = sum(1 for r in fired if r.get("level") == "OR low")
    fired_no_retest_total = sum(1 for r in fired if "no_retest" in r.get("downgrades", []))

    # -- recall on the 34-S-card probe sweep
    probe_keys = load_probe_s_days()
    probe_base_recall, probe_arm_recall, probe_n = recall(
        probe_keys, cand_stream_by_symday, drop_or_specific)
    _, probe_control_recall, _ = recall(
        probe_keys, cand_stream_by_symday, drop_blanket)

    # -- recall on all bar-backed S days (canonical pool)
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]
    pool_base_recall, pool_arm_recall, pool_n = recall(
        bar_backed_s_keys, cand_stream_by_symday, drop_or_specific)
    _, pool_control_recall, _ = recall(
        bar_backed_s_keys, cand_stream_by_symday, drop_blanket)

    # -- precision on the global one-a-day arm's own picks
    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)
    arm_prec, arm_prec_s, arm_prec_n = precision(arm_picks, pool)
    control_prec, control_prec_s, control_prec_n = precision(control_picks, pool)

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

    # -- is the OR specificity real? arm vs control on $/day and precision
    or_specificity_real = (
        (arm_all["usd_day"] > control_all["usd_day"])
        or ((arm_prec or 0) > (control_prec or 0))
    )

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "or-break-without-retest",
        "polarity": "refusal-indicator",
        "predicate": {
            "arm": "DROP r if level in ('OR high','OR low') and "
                   "'no_retest' in downgrades",
            "control": "DROP r if 'no_retest' in downgrades regardless of level",
        },
        "fired_base_rates": {
            "or_high_fired": fired_or_high,
            "or_low_fired": fired_or_low,
            "no_retest_fired_total": fired_no_retest_total,
            "denominator": "status=='fired', all %d rows (not one-a-day)" % len(fired),
        },
        "candidates_per_day": cands_per_day,
        "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
        "candidate": {"all": arm_all, "h1": arm_h1, "h2": arm_h2},
        "control_blanket": {"all": control_all, "h1": control_h1, "h2": control_h2},
        "h1_delta_usd_day": round(h1_delta, 2),
        "h2_delta_usd_day": round(h2_delta, 2),
        "recall": {
            "probe_s_sweep_34": {
                "n": probe_n, "baseline_pct": probe_base_recall,
                "candidate_pct": probe_arm_recall,
                "control_pct": probe_control_recall,
            },
            "bar_backed_s_days_canonical_pool": {
                "n": pool_n, "baseline_pct": pool_base_recall,
                "candidate_pct": pool_arm_recall,
                "control_pct": pool_control_recall,
            },
        },
        "precision": {
            "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
            "candidate": {"pct": arm_prec, "s": arm_prec_s, "graded": arm_prec_n},
            "control_blanket": {"pct": control_prec, "s": control_prec_s,
                                 "graded": control_prec_n},
        },
        "or_specificity_real": or_specificity_real,
        "survivor": survivor,
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall_100 (both recall panels) not below baseline "
                          "(measured on the OR-specific arm vs baseline)",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- or-break-without-retest")
    md.append("")
    verdict_line = ("SURVIVOR" if survivor else "not a survivor") + \
        (" -- H1 %+.0f/day, H2 %+.0f/day" % (h1_delta, h2_delta))
    md.append("**One sentence: %s** on the honest, retest-on book, one-trade-"
               "a-day unit, size-gated." % verdict_line)
    md.append("")
    md.append("Predicate (ARM, OR-specific): DROP if level in (OR high, OR "
               "low) AND 'no_retest' in downgrades. Predicate (CONTROL, "
               "blanket): DROP if 'no_retest' in downgrades, any level. Pure "
               "refusal-indicator -- there is no keep/S-indicator half.")
    md.append("")
    md.append("Fired base (status=='fired', %d rows, NOT the one-a-day "
               "unit): OR high **%d**, OR low **%d**. **%d** fired rows carry "
               "'no_retest' in downgrades regardless of level -- "
               "RETEST_REQUIRED caps grade at fire time, it does not veto "
               "the fire."
               % (len(fired), fired_or_high, fired_or_low, fired_no_retest_total))
    md.append("")
    md.append("candidates/day (raw arrival stream, whole pool): **%.2f**"
               % cands_per_day)
    md.append("")
    md.append("## Money -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| arm | split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for label, s in (("baseline", baseline_all), ("baseline", baseline_h1),
                     ("baseline", baseline_h2), ("candidate (OR-specific)", arm_all),
                     ("candidate (OR-specific)", arm_h1), ("candidate (OR-specific)", arm_h2),
                     ("control (blanket)", control_all), ("control (blanket)", control_h1),
                     ("control (blanket)", control_h2)):
        split_label = s["label"].split(" ", 1)[-1] if " " in s["label"] else "all"
        md.append("| %s | %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                   % (label, split_label if split_label != label else "all",
                      s["usd_day"], s["mean_r"], s["win_pct"],
                      s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
    md.append("")
    md.append("H1/H2 split at **%s**. delta $/day (OR-specific arm vs "
               "baseline): H1 %+.2f, H2 %+.2f." % (SPLIT_DAY, h1_delta, h2_delta))
    md.append("")
    md.append("## Is the OR specificity real?")
    md.append("")
    md.append("OR-specific arm $/day **$%.2f** vs blanket control $/day "
               "**$%.2f**; OR-specific precision **%s%%** vs blanket "
               "precision **%s%%**. **%s** -- the OR-specific arm %s the "
               "blanket one, so the claimed OR specificity is %s."
               % (arm_all["usd_day"], control_all["usd_day"],
                  arm_prec, control_prec,
                  "OR SPECIFICITY REAL" if or_specificity_real else "OR SPECIFICITY NOT REAL",
                  "beats" if or_specificity_real else "does not beat",
                  "supported" if or_specificity_real else "NOT supported -- 'no retest' "
                  "reads as a level-blind fact, not something special about the opening range"))
    md.append("")
    md.append("## S recall")
    md.append("")
    md.append("| set | n | baseline | candidate (OR-specific) | control (blanket) |")
    md.append("|---|---:|---:|---:|---:|")
    md.append("| probe_s_sweep (34 S cards) | %d | %s%% | %s%% | %s%% |"
               % (probe_n, probe_base_recall, probe_arm_recall, probe_control_recall))
    md.append("| bar-backed S days (canonical_pool) | %d | %s%% | %s%% | %s%% |"
               % (pool_n, pool_base_recall, pool_arm_recall, pool_control_recall))
    md.append("")
    md.append("## Precision (fired days graded S / fired days graded at all)")
    md.append("")
    md.append("| arm | precision | S / graded |")
    md.append("|---|---:|---:|")
    md.append("| baseline | %s%% | %d / %d |" % (base_prec, base_prec_s, base_prec_n))
    md.append("| candidate (OR-specific) | %s%% | %d / %d |" % (arm_prec, arm_prec_s, arm_prec_n))
    md.append("| control (blanket) | %s%% | %d / %d |" % (control_prec, control_prec_s, control_prec_n))
    md.append("")
    md.append("Survivor rule: H1 AND H2 both improve $/day or precision "
               "(OR-specific arm vs baseline), and recall on both S-day "
               "panels does not fall below baseline. **Result: %s.**"
               % ("SURVIVOR" if survivor else "NOT a survivor"))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day: %.2f" % cands_per_day)
    print("baseline $/day: %.2f  candidate $/day: %.2f  control $/day: %.2f"
          % (baseline_all["usd_day"], arm_all["usd_day"], control_all["usd_day"]))
    print("survivor: %s  or_specificity_real: %s" % (survivor, or_specificity_real))


if __name__ == "__main__":
    main()
