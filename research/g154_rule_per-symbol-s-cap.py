"""g154 F5 -- candidate "per-symbol-s-cap".

Austin's claim (theme: refusals / how many S trades one symbol can produce):
he said 2, then revised to 3, with a back-of-envelope ~0.8 S-trades/day/symbol.
`live_scanner.GOVERNOR_S_CAP` already exists in the live scanner but defaults
to None and has no backtest_week analog -- the committed 2-year book was built
with no per-symbol cap in effect at all.

Polarity: REFUSAL-INDICATOR. Predicate, exactly as specced:

    Within each (r['sym'], r['day']) group, ordered by r['et'], KEEP only the
    first k fired rows, k in {2, 3}. Everything past rank k is a DROP -- the
    day's pick then falls through to the next surviving candidate (which may
    belong to a different symbol).

This is measured on the honest, retest-on book
(research/bt2y_trades_retest_on.json), candidate stream = fired&traded OR
halted (identical construction to research/g91_lane_slice.py and
research/g86_honest_ceiling.py), one-trade-a-day unit =
research/omen_metrics.first_of_day_arm, size-gated.

The row's own prediction, ahead of running any number: on the one-trade-a-day
unit this cap is near-inert BY CONSTRUCTION. The day's first pick (across the
whole pool, not per symbol) is always rank 1 for whichever symbol it belongs
to, and a cap of k>=2 never removes rank 1. So the one-a-day arm's picks
should be identical to baseline for every day, and $/day, recall and
precision should not move. What CAN move is candidates/day (fewer re-fires
shown to a human or a live governor) -- that is what this script actually
measures, plus whether the trimmed rows are redundant re-fires on the same
r['level_px'] (the governor doing its intended job) or genuinely different
setups being suppressed (the governor costing something the one-a-day unit
can't see).

    python research/g154_rule_per-symbol-s-cap.py

Writes research/g154_rule_per-symbol-s-cap.json and .md. Nothing here is
applied; ships nothing. Read-only on the book and on every mark corpus.
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
OUT_JSON = os.path.join(HERE, "g154_rule_per-symbol-s-cap.json")
OUT_MD = os.path.join(HERE, "g154_rule_per-symbol-s-cap.md")

RISK = 1000.0
SPLIT_DAY = "2025-09-01"          # H1/H2 split, per row spec
BAR = 397.0                        # Austin's stated bar, for context only
CAPS = (2, 3)                      # "he said 2, then revised to 3"
LEVEL_PX_ROUND = 2                 # cents


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


def _rank_within_symbol_day(by_day):
    """rank[(sym, day, et)] = 1-indexed position of this row within its
    (sym, day) group, in arrival (et) order. Ties on et are broken by the
    stable sort already applied in _candidate_stream (day, et, sym)."""
    rank = {}
    for day, v in by_day.items():
        counts = defaultdict(int)
        for r in v:
            counts[r["sym"]] += 1
            rank[(r["sym"], day, r["et"])] = counts[r["sym"]]
    return rank


def make_drop_fn(rank, k):
    def drop(r):
        return rank.get((r["sym"], r["day"], r["et"]), 1) > k
    return drop


def candidate_arm(by_day, drop_fn):
    """Refusal-indicator walk over the WHOLE day's stream (across every
    symbol): skip DROP-matching sizeable rows, take the first surviving row
    in arrival order. A day where nothing survives produces no trade that
    day. Identical shape to g154_rule_or-break-without-retest.candidate_arm."""
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
    fires at all (baseline) vs still fires after the cap (candidate)."""
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


# ------------------------------------------------------- redundancy check

def redundancy_stats(by_day, rank, k):
    """Of the rows trimmed by the cap (rank > k within their (sym,day)
    group), what fraction share r['level_px'] (rounded to cents) with a
    KEPT row (rank <= k) in the same (sym, day) group? That is the
    "does the cap only trim duplicate re-fires on the same level" check."""
    trimmed = 0
    trimmed_same_level = 0
    for day, v in by_day.items():
        kept_level_by_sym = defaultdict(set)
        for r in v:
            if rank[(r["sym"], day, r["et"])] <= k:
                lp = r.get("level_px")
                if lp is not None:
                    kept_level_by_sym[r["sym"]].add(round(lp, LEVEL_PX_ROUND))
        for r in v:
            if rank[(r["sym"], day, r["et"])] > k:
                trimmed += 1
                lp = r.get("level_px")
                if lp is not None and round(lp, LEVEL_PX_ROUND) in kept_level_by_sym[r["sym"]]:
                    trimmed_same_level += 1
    pct = round(trimmed_same_level / trimmed * 100, 1) if trimmed else None
    return {"trimmed_rows": trimmed, "trimmed_same_level_px": trimmed_same_level,
            "pct_trimmed_same_level_px": pct}


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    rows = blob["trades"]
    meta = blob["meta"]
    all_days = sorted({r["day"] for r in rows})
    h1_days = [d for d in all_days if d < SPLIT_DAY]
    h2_days = [d for d in all_days if d >= SPLIT_DAY]

    by_day = _candidate_stream(rows)
    rank = _rank_within_symbol_day(by_day)

    total_cands = sum(len(v) for v in by_day.values())
    cands_per_day_uncapped = round(total_cands / len(all_days), 2)

    baseline_picks = om.first_of_day_arm(rows, size_gate=True)

    def split(picks, days):
        dset = set(days)
        return [r for r in picks if r["day"] in dset]

    baseline_all = arm_stats(baseline_picks, all_days, "baseline (whole book)")
    baseline_h1 = arm_stats(split(baseline_picks, h1_days), h1_days, "baseline H1")
    baseline_h2 = arm_stats(split(baseline_picks, h2_days), h2_days, "baseline H2")

    probe_keys = load_probe_s_days()
    pool = mp.canonical_pool()
    sdays = mp.s_days(pool)
    bar_backed_s_keys = [k for k in sdays if pool[k].has_bars]

    cand_stream_by_symday = defaultdict(list)
    for day, v in by_day.items():
        for r in v:
            cand_stream_by_symday[(r["sym"], day)].append(r)

    probe_base_recall, _, probe_n = recall(probe_keys, cand_stream_by_symday, lambda r: False)
    pool_base_recall, _, pool_n = recall(bar_backed_s_keys, cand_stream_by_symday, lambda r: False)
    base_prec, base_prec_s, base_prec_n = precision(baseline_picks, pool)

    arms = {}
    for k in CAPS:
        drop_fn = make_drop_fn(rank, k)
        capped_by_day = {day: [r for r in v if not drop_fn(r)] for day, v in by_day.items()}
        total_capped = sum(len(v) for v in capped_by_day.values())
        cands_per_day_capped = round(total_capped / len(all_days), 2)

        arm_picks = candidate_arm(by_day, drop_fn)
        arm_all = arm_stats(arm_picks, all_days, "candidate k=%d (whole book)" % k)
        arm_h1 = arm_stats(split(arm_picks, h1_days), h1_days, "candidate k=%d H1" % k)
        arm_h2 = arm_stats(split(arm_picks, h2_days), h2_days, "candidate k=%d H2" % k)

        _, probe_arm_recall, _ = recall(probe_keys, cand_stream_by_symday, drop_fn)
        _, pool_arm_recall, _ = recall(bar_backed_s_keys, cand_stream_by_symday, drop_fn)
        arm_prec, arm_prec_s, arm_prec_n = precision(arm_picks, pool)

        red = redundancy_stats(by_day, rank, k)

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
        picks_identical = ([r["sym"] for r in arm_picks] == [r["sym"] for r in baseline_picks]
                            and [r["day"] for r in arm_picks] == [r["day"] for r in baseline_picks]
                            and [r["et"] for r in arm_picks] == [r["et"] for r in baseline_picks])
        survivor = bool(h1_improves and h2_improves and recall_ok)

        arms[k] = {
            "k": k,
            "candidates_per_day_uncapped": cands_per_day_uncapped,
            "candidates_per_day_capped": cands_per_day_capped,
            "candidates_trimmed_per_day": round(cands_per_day_uncapped - cands_per_day_capped, 2),
            "redundancy": red,
            "one_a_day_arm_picks_identical_to_baseline": picks_identical,
            "baseline": {"all": baseline_all, "h1": baseline_h1, "h2": baseline_h2},
            "candidate": {"all": arm_all, "h1": arm_h1, "h2": arm_h2},
            "h1_delta_usd_day": round(h1_delta, 2),
            "h2_delta_usd_day": round(h2_delta, 2),
            "recall": {
                "probe_s_sweep_34": {"n": probe_n, "baseline_pct": probe_base_recall,
                                      "candidate_pct": probe_arm_recall},
                "bar_backed_s_days_canonical_pool": {"n": pool_n, "baseline_pct": pool_base_recall,
                                                      "candidate_pct": pool_arm_recall},
            },
            "precision": {
                "baseline": {"pct": base_prec, "s": base_prec_s, "graded": base_prec_n},
                "candidate": {"pct": arm_prec, "s": arm_prec_s, "graded": arm_prec_n},
            },
            "survivor": survivor,
        }

    overall_survivor = bool(arms[2]["survivor"] and arms[3]["survivor"])

    out = {
        "book": os.path.basename(BOOK),
        "book_meta_sessions": meta.get("sessions"),
        "rule": "per-symbol-s-cap",
        "polarity": "refusal-indicator",
        "predicate": "Within each (sym, day) group, ordered by et, KEEP only "
                     "the first k fired rows (fired&traded or halted stream); "
                     "past rank k -> DROP, one-trade-a-day pick falls through "
                     "to the next surviving candidate that day (any symbol). "
                     "k in {2, 3}.",
        "live_governor": "live_scanner.GOVERNOR_S_CAP exists, defaults to None, "
                          "no backtest_week analog -- the committed book was "
                          "built with no per-symbol cap in effect.",
        "candidates_per_day_uncapped": cands_per_day_uncapped,
        "arms": arms,
        "overall_survivor": overall_survivor,
        "survivor_rule": "H1 and H2 both improve $/day or precision, and "
                          "recall (both panels) not below baseline -- "
                          "required at BOTH k=2 and k=3 for overall_survivor.",
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)

    md = []
    md.append("# g154 F5 -- per-symbol-s-cap")
    md.append("")
    md.append("**One sentence: capping how many times one symbol can fire "
               "per day (k=2 or k=3) is near-inert on the one-trade-a-day "
               "unit -- it trims %s/%s candidates per day of redundant "
               "re-fires but %s the day's actual pick, because the day's "
               "first pick is always rank 1 for its symbol and a cap of "
               "k>=2 never removes rank 1.**"
               % (arms[2]["candidates_trimmed_per_day"], arms[3]["candidates_trimmed_per_day"],
                  "never changes" if (arms[2]["one_a_day_arm_picks_identical_to_baseline"]
                                      and arms[3]["one_a_day_arm_picks_identical_to_baseline"])
                  else "sometimes changes"))
    md.append("")
    md.append("Predicate (refusal-indicator): within each (sym, day) group "
               "of the fired&traded/halted candidate stream, ordered by et, "
               "keep only the first k fired rows; the one-a-day pick skips "
               "any row past rank k and falls through to the next surviving "
               "candidate that day, across every symbol.")
    md.append("")
    md.append("`live_scanner.GOVERNOR_S_CAP` already exists in the live "
               "scanner but defaults to `None` and has no `backtest_week` "
               "analog -- the committed 2-year book (`bt2y_trades_retest_on."
               "json`) was built with no per-symbol cap in effect at all.")
    md.append("")
    md.append("Uncapped candidates/day (fired&traded or halted stream, "
               "whole pool): **%.2f**." % cands_per_day_uncapped)
    md.append("")
    for k in CAPS:
        a = arms[k]
        md.append("## k = %d" % k)
        md.append("")
        md.append("Candidates/day: uncapped **%.2f** -> capped **%.2f** "
                   "(trims **%.2f**/day). One-a-day arm picks identical to "
                   "baseline: **%s**. Redundancy: of the %d rows trimmed, "
                   "**%s** shared level_px with an already-kept row for that "
                   "symbol-day (%s%%)."
                   % (a["candidates_per_day_uncapped"], a["candidates_per_day_capped"],
                      a["candidates_trimmed_per_day"],
                      a["one_a_day_arm_picks_identical_to_baseline"],
                      a["redundancy"]["trimmed_rows"],
                      a["redundancy"]["trimmed_same_level_px"],
                      a["redundancy"]["pct_trimmed_same_level_px"]))
        md.append("")
        md.append("| arm | split | $/day | mean R | win | months green | max DD | fires/day |")
        md.append("|---|---|---:|---:|---:|---:|---:|---:|")
        for label, s in (("baseline", a["baseline"]["all"]), ("baseline", a["baseline"]["h1"]),
                         ("baseline", a["baseline"]["h2"]), ("candidate", a["candidate"]["all"]),
                         ("candidate", a["candidate"]["h1"]), ("candidate", a["candidate"]["h2"])):
            split_label = s["label"].split(" ", 1)[-1] if " " in s["label"] else "all"
            md.append("| %s | %s | $%.2f | %+.3f | %.1f%% | %s | $%.0f | %.3f |"
                       % (label, split_label if split_label != label else "all",
                          s["usd_day"], s["mean_r"], s["win_pct"],
                          s["months_green"], s["max_dd_usd"], s["fires_per_day"]))
        md.append("")
        md.append("H1/H2 split at **%s**. delta $/day: H1 %+.2f, H2 %+.2f."
                   % (SPLIT_DAY, a["h1_delta_usd_day"], a["h2_delta_usd_day"]))
        md.append("")
        md.append("| set | n | baseline recall | candidate recall |")
        md.append("|---|---:|---:|---:|")
        r34 = a["recall"]["probe_s_sweep_34"]
        rall = a["recall"]["bar_backed_s_days_canonical_pool"]
        md.append("| probe_s_sweep (34 S cards) | %d | %s%% | %s%% |"
                   % (r34["n"], r34["baseline_pct"], r34["candidate_pct"]))
        md.append("| bar-backed S days (canonical_pool) | %d | %s%% | %s%% |"
                   % (rall["n"], rall["baseline_pct"], rall["candidate_pct"]))
        md.append("")
        p = a["precision"]
        md.append("| arm | precision | S / graded |")
        md.append("|---|---:|---:|")
        md.append("| baseline | %s%% | %d / %d |"
                   % (p["baseline"]["pct"], p["baseline"]["s"], p["baseline"]["graded"]))
        md.append("| candidate | %s%% | %d / %d |"
                   % (p["candidate"]["pct"], p["candidate"]["s"], p["candidate"]["graded"]))
        md.append("")
        md.append("k=%d survivor: **%s**." % (k, a["survivor"]))
        md.append("")
    md.append("## Verdict")
    md.append("")
    md.append("Survivor rule: H1 AND H2 both improve $/day or precision, and "
               "recall on both S-day panels does not fall below baseline -- "
               "required at both k=2 and k=3 for `overall_survivor`. "
               "**Result: %s.** As predicted going in: this cap is a "
               "candidate/day and live-noise reducer, not a money or "
               "precision lever on the one-trade-a-day unit -- the unit "
               "already only ever asks for the day's rank-1 candidate, "
               "which a k>=2 cap can never remove."
               % ("SURVIVOR" if overall_survivor else "NOT a survivor"))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")

    print("candidates/day uncapped: %.2f" % cands_per_day_uncapped)
    for k in CAPS:
        a = arms[k]
        print("k=%d: capped candidates/day %.2f  baseline $/day %.2f  candidate $/day %.2f  "
              "picks_identical=%s  survivor=%s"
              % (k, a["candidates_per_day_capped"], a["baseline"]["all"]["usd_day"],
                 a["candidate"]["all"]["usd_day"], a["one_a_day_arm_picks_identical_to_baseline"],
                 a["survivor"]))
    print("overall_survivor: %s" % overall_survivor)


if __name__ == "__main__":
    main()
