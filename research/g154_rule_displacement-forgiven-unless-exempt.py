"""g154 F5 -- candidate "displacement-forgiven-unless-exempt".

Austin's claim (rule ballot): a break-and-retest with no displacement on the
break leg is forgiven ~90% of the time when he grades S; the other ~10% only
via three named exemptions -- BR+OCR confluence, a bull/bear flag at the open,
or an HTF thesis.

This measures it as an S-INDICATOR (keep-favoring) / REFUSAL-INDICATOR
(drop-forcing) pair over the honest, retest-on book
(research/bt2y_trades_retest_on.json), on the one-trade-a-day unit
(research/omen_metrics.first_of_day_arm, size-gated).

Predicate, exactly as specced:

    KEEP r if ('disp' in r['tags']) or (r['confluence'] == 'yes')
              or (r['et'] <= '09:45')
    DROP r if (('nodisp' in r['tags']) or ('no_displacement' in r['downgrades']))
              and (r['confluence'] == 'no') and (r['et'] > '09:45')

`et <= '09:45'` stands in for the "bull/bear flag at the open" exemption --
there is no flag-at-open field in the book, so this is a TIME PROXY, not a
pattern match. The HTF-thesis exemption has NO field anywhere in the book
(`bias_tf` names a timeframe, not a thesis judgement) and is NOT modeled --
this measurement is blind to it, and that gap is reported, not hidden.

Two arms, both one-trade-a-day, size-gated via
`omen_metrics.ev_r_scoreboard`'s own `_row_is_sizeable` predicate (imported,
never re-derived):

  * baseline -- omen_metrics.first_of_day_arm: first sizeable candidate of the
    day, arrival order, whole pool.
  * candidate -- same arrival-order walk, but a row matching DROP is skipped
    outright (refusal-indicator), and among what is left the first row
    matching KEEP wins (S-indicator); if nothing in the remaining set matches
    KEEP, the first surviving (non-dropped, sizeable) row is taken instead --
    ambiguous is not the same as refused. A day where every sizeable
    candidate is DROPped produces no trade that day.

Recall is scored the way research/g71_router_recall.py scores it: per
SYMBOL-DAY, not per the global one-a-day pick -- "did the book still produce
a survivor for THIS symbol on THIS day", using the book's own fired-and-
traded/halted candidate stream for that symbol-day. Precision is scored on
the global one-a-day arm's own picks (one per day, whole pool), against
research/marks_pool.canonical_pool().

    python research/g154_rule_displacement-forgiven-unless-exempt.py

Writes research/g154_rule_displacement-forgiven-unless-exempt.json and .md.
Nothing here is applied; ships nothing.
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
OUT_JSON = os.path.join(HERE, "g154_rule_displacement-forgiven-unless-exempt.json")
OUT_MD = os.path.join(HERE, "g154_rule_displacement-forgiven-unless-exempt.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"          # H1/H2 split, per row spec
BAR = 397.0                        # Austin's stated bar, for context only


# --------------------------------------------------------------------- rule

def keep_s_indicator(r):
    """S-indicator: forgiven-unless-exempt fires -- keep this candidate."""
    return (("disp" in r.get("tags", []))
            or (r.get("confluence") == "yes")
            or (r.get("et", "") <= "09:45"))


def drop_refusal_indicator(r):
    """Refusal-indicator: no exemption applies -- do not take this one."""
    tags = r.get("tags", [])
    downgrades = r.get("downgrades", [])
    return (("nodisp" in tags or "no_displacement" in downgrades)
            and r.get("confluence") == "no"
            and r.get("et", "") > "09:45")


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


def candidate_arm(rows):
    """The classifier's one-trade-a-day pick: skip DROP, prefer KEEP among
    what survives, else fall back to the first surviving (ambiguous) row.
    A day where nothing survives has no trade."""
    by_day = _candidate_stream(rows)
    picks = []
    for day in sorted(by_day):
        survivors = [r for r in by_day[day]
                     if om._row_is_sizeable(r) is not False
                     and not drop_refusal_indicator(r)]
        if not survivors:
            continue
        keepers = [r for r in survivors if keep_s_indicator(r)]
        picks.append(keepers[0] if keepers else survivors[0])
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

def _symday_survivors(rows_by_symday, sym, day, apply_predicate):
    rows = rows_by_symday.get((sym, day), [])
    sizeable = [r for r in rows if om._row_is_sizeable(r) is not False]
    if not apply_predicate:
        return sizeable
    return [r for r in sizeable if not drop_refusal_indicator(r)]


def recall(keys, rows_by_symday):
    """keys: iterable of 'SYM_YYYY-MM-DD'. Returns (baseline_recall, arm_recall,
    n) -- fraction of those symbol-days where the book still fires at all
    (baseline) vs still fires after the candidate arm's refusal-indicator
    (candidate). KEEP is a preference among survivors, not a further recall
    cut -- it never drops a symbol-day to zero candidates on its own."""
    n = 0
    base_hit = arm_hit = 0
    for key in keys:
        sym, day = key.split("_", 1)
        n += 1
        base = _symday_survivors(rows_by_symday, sym, day, apply_predicate=False)
        arm = _symday_survivors(rows_by_symday, sym, day, apply_predicate=True)
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
    arm_picks = candidate_arm(rows)

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

    cands_per_day = round(total_cands / len(all_days), 2)

    # -- recall on the 34-S-card probe sweep
    probe_keys = load_probe_s_days()
    probe_base_recall, probe_arm_recall, probe_n = recall(probe_keys, cand_stream_by_symday)

    # -- recall on all bar-backed S days (canonical pool)
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]
    pool_base_recall, pool_arm_recall, pool_n = recall(bar_backed_s_keys, cand_stream_by_symday)

    # -- precision on the global one-a-day arm's own picks
    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)
    arm_prec, arm_prec_s, arm_prec_n = precision(arm_picks, pool)

    def better_usd(h1a, h1b, h2a, h2b):
        return h1b["usd_day"] > h1a["usd_day"] and h2b["usd_day"] > h2a["usd_day"]

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
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "displacement-forgiven-unless-exempt",
        "polarity": "S-indicator",
        "predicate": {
            "keep": "('disp' in tags) or (confluence=='yes') or (et<='09:45')",
            "drop": "(('nodisp' in tags) or ('no_displacement' in downgrades)) "
                    "and confluence=='no' and et>'09:45'",
            "notes": "et<='09:45' is the flag-at-open exemption's TIME PROXY, "
                     "not a pattern match -- no flag-at-open field exists in "
                     "the book. The HTF-thesis exemption has NO field anywhere "
                     "in the book (bias_tf names a timeframe, not a thesis "
                     "judgement) and is OMITTED -- this measurement is blind "
                     "to it.",
        },
        "fired_base_rates": {
            "nodisp_tag": 8014, "disp_tag": 2285, "confluence_yes": 8369,
            "denominator": "status=='fired', all 10830 rows (not one-a-day)",
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

    md = []
    md.append("# g154 F5 -- displacement-forgiven-unless-exempt")
    md.append("")
    verdict_line = ("SURVIVOR" if survivor else "not a survivor") + \
        (" -- H1 %+.0f/day, H2 %+.0f/day" % (h1_delta, h2_delta))
    md.append("**One sentence: %s** on the honest, retest-on book, one-trade-"
               "a-day unit, size-gated." % verdict_line)
    md.append("")
    md.append("Predicate: KEEP if disp tag / confluence=yes / et<=09:45 "
               "(flag-at-open proxy). DROP if nodisp (tag or downgrade) AND "
               "confluence=no AND et>09:45. **HTF-thesis exemption has no "
               "field and is not modeled** -- this measurement is blind to it.")
    md.append("")
    md.append("Fired base rates (status=='fired', 10830 rows, NOT the one-a-"
               "day unit): nodisp tag %d, disp tag %d, confluence=yes %d."
               % (out["fired_base_rates"]["nodisp_tag"],
                  out["fired_base_rates"]["disp_tag"],
                  out["fired_base_rates"]["confluence_yes"]))
    md.append("")
    md.append("candidates/day (raw arrival stream, whole pool): **%.2f**"
               % cands_per_day)
    md.append("")
    md.append("## Money -- one trade a day, whole pool, size-gated")
    md.append("")
    md.append("| arm | split | $/day | mean R | win | months green | max DD | fires/day |")
    md.append("|---|---|---:|---:|---:|---:|---:|---:|")
    for label, s in (("baseline", baseline_all), ("baseline", baseline_h1),
                     ("baseline", baseline_h2), ("candidate", arm_all),
                     ("candidate", arm_h1), ("candidate", arm_h2)):
        split_label = s["label"].split(" ", 1)[-1] if " " in s["label"] else "all"
        md.append("| %s | %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                   % (label, split_label if split_label != label else "all",
                      s["usd_day"], s["mean_r"], s["win_pct"],
                      s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
    md.append("")
    md.append("H1/H2 split at **%s**. delta $/day: H1 %+.2f, H2 %+.2f."
               % (SPLIT_DAY, h1_delta, h2_delta))
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
    md.append("Survivor rule: H1 AND H2 both improve $/day or precision, and "
               "recall on both S-day panels does not fall below baseline. "
               "**Result: %s.**" % ("SURVIVOR" if survivor else "NOT a survivor"))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day: %.2f" % cands_per_day)
    print("baseline: $%.2f/day  mean R %+.3f  win %.1f%%  months %s  maxDD $%.0f  fires/day %.3f"
          % (baseline_all["usd_day"], baseline_all["mean_r"], baseline_all["win_pct"],
             baseline_all["months_green"], baseline_all["max_dd_usd"], baseline_all["fires_per_day"]))
    print("candidate: $%.2f/day  mean R %+.3f  win %.1f%%  months %s  maxDD $%.0f  fires/day %.3f"
          % (arm_all["usd_day"], arm_all["mean_r"], arm_all["win_pct"],
             arm_all["months_green"], arm_all["max_dd_usd"], arm_all["fires_per_day"]))
    print("H1 delta $%+.2f/day  H2 delta $%+.2f/day" % (h1_delta, h2_delta))
    print("recall probe34: base %s%% -> arm %s%%   recall bar-backed-S: base %s%% -> arm %s%%"
          % (probe_base_recall, probe_arm_recall, pool_base_recall, pool_arm_recall))
    print("precision: base %s%% -> arm %s%%" % (base_prec, arm_prec))
    print("SURVIVOR = %s" % survivor)
    print("-> %s\n-> %s" % (OUT_JSON, OUT_MD))


if __name__ == "__main__":
    main()
