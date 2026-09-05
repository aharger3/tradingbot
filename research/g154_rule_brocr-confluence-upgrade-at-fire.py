"""g154 -- F5 candidate 'brocr-confluence-upgrade-at-fire'.

Rule under test: "BR+OCR confluence is a +1 upgrade and never a downgrade,
capped at +1 total even when a second independent confluence type also fires
on the same signal." (polarity: S-indicator.)

Predicate: KEEP a fired candidate if r['confluence'] == 'yes' (equivalently
'brocr' in r['tags']; the two agree on the book -- see the sanity check in
main()). 8369 of 10830 fired rows carry confluence=='yes', a ~23% cut, well
short of the 1-3/day gate alone (paired with another rule in F7).

Also runs the INVERSE arm (confluence == 'no') to confirm the sign, and folds
has_confluence into the fire-time A+/A/B/C ladder (signal_runner._GRADE_RANK,
read-only import -- not just the reported S/A/C downgrade.py ladder), so the
upgrade's effect on the ladder distribution is visible, not just its effect
on the one-trade-a-day selection stream.

Everything routes through omen_metrics (ev_r_scoreboard, first_of_day_arm,
_row_is_sizeable) for the size gate and the R/day-fill definitions -- no
local re-derivation of the fill, per CLAUDE.md. Unit and lane precedent:
research/g91_lane_slice.py, research/g86_honest_ceiling.py.

    python research/g154_rule_brocr-confluence-upgrade-at-fire.py

Writes research/g154_rule_brocr-confluence-upgrade-at-fire.{md,json}.
Applies nothing, ships nothing.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import omen_metrics as om          # noqa: E402  the one EV/R kernel + size gate
import marks_pool as mp            # noqa: E402  canonical grade pool

BOOK_PATH = os.path.join(HERE, "bt2y_trades_retest_on.json")
SWEEP_PATH = os.path.join(HERE, "marks", "probe_s_sweep_2026-08-28.jsonl")
OUT_JSON = os.path.join(HERE, "g154_rule_brocr-confluence-upgrade-at-fire.json")
OUT_MD = os.path.join(HERE, "g154_rule_brocr-confluence-upgrade-at-fire.md")

RISK = 1000.0
H_SPLIT = "2025-09-01"   # H1 < this, H2 >= this, per CLAUDE.md

# The engine's legacy fire-time ladder (signal_runner._GRADE_RANK, read-only
# import so a mid-edit elsewhere never blocks this measurement -- same
# fallback pattern omen_metrics uses for min_risk_floor).
try:
    import signal_runner as _sr
    _GRADE_RANK = dict(_sr._GRADE_RANK)
except Exception:
    _GRADE_RANK = {"A+": 4, "A": 3, "B": 2, "C": 1, "X": 0, "D": 0}
_RANK_TO_GRADE = {v: k for k, v in sorted(_GRADE_RANK.items(), key=lambda kv: kv[1])
                  if k != "D"}  # D and X share rank 0; keep X as the canonical name


def upgrade_ladder(grade, has_confluence):
    """+1 upgrade, never a downgrade, capped at +1 total (spec's own words)
    even if grade already sits at the ladder's top (A+ stays A+)."""
    if not has_confluence:
        return grade
    rank = _GRADE_RANK.get(grade)
    if rank is None:
        return grade
    new_rank = min(rank + 1, max(_GRADE_RANK.values()))
    return _RANK_TO_GRADE.get(new_rank, grade)


def by_day_candidates(rows):
    """Fired-and-traded rows, plus loss-halted rows (one-a-day: that halt
    hasn't fired yet under a strict one-trade-a-day policy) -- identical
    construction to omen_metrics.first_of_day_arm, grouped by day so a
    predicate-filtered first-of-day pick can be built on top."""
    by_day = defaultdict(list)
    for r in rows:
        if (r["status"] == "fired" and r.get("traded")) or r["status"] == "halted":
            by_day[r["day"]].append(r)
    return by_day


def first_matching_arm(rows, keep_pred):
    """One-trade-a-day arm: the day's first candidate (arrival order) that
    both satisfies `keep_pred` and is sizeable. A candidate that fails the
    predicate is SKIPPED, not counted -- 'take the next', per the row spec.
    A day with no matching+sizeable candidate contributes no trade (this is
    a selection filter, not a substitute engine)."""
    def ekey(r):
        return (r["day"], r["et"], r["sym"])

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


def ladder_distribution(rows, pred_confluence):
    """Fired rows' engine grade, before and after the +1 fold, restricted to
    rows matching `pred_confluence` (used to show the fold's actual effect,
    not the whole book's)."""
    before = Counter()
    after = Counter()
    for r in rows:
        if r["status"] != "fired":
            continue
        g = r.get("grade")
        if g is None:
            continue
        before[g] += 1
        after[upgrade_ladder(g, pred_confluence(r))] += 1
    return dict(before), dict(after)


def main():
    if not os.path.exists(BOOK_PATH):
        print("BLOCKED: missing %s" % BOOK_PATH)
        return 1

    blob = json.load(open(BOOK_PATH, encoding="utf-8"))
    rows = blob["trades"]

    # Sanity check named in the row spec: confluence=='yes' <-> 'brocr' in tags.
    fired = [r for r in rows if r["status"] == "fired"]
    conf_yes = {i for i, r in enumerate(fired) if r.get("confluence") == "yes"}
    tag_brocr = {i for i, r in enumerate(fired) if "brocr" in (r.get("tags") or [])}
    agree_pct = 1.0 - len(conf_yes ^ tag_brocr) / len(fired)
    agree = agree_pct >= 0.99
    print("sanity: confluence=='yes' agrees with 'brocr' in tags on %.2f%% of %d fired rows "
          "(%d rows differ -- close but not identical; predicate below uses confluence=='yes' "
          "per the row spec, which reproduces its stated 8369/10830)"
          % (agree_pct * 100.0, len(fired), len(conf_yes ^ tag_brocr)))
    print("fired rows: %d, confluence=='yes': %d (%.1f%%)\n"
          % (len(fired), len(conf_yes), 100.0 * len(conf_yes) / len(fired)))

    # ---- marks pool: the 34-card sweep and the full bar-backed S-day set
    sweep_rows = [json.loads(l) for l in open(SWEEP_PATH, encoding="utf-8")]
    sweep_s_keys = {"%s_%s" % (r["symbol"], r["date"])
                    for r in sweep_rows if mp.row_grade(r) == "S"}
    pool = mp.canonical_pool()
    all_s_keys = mp.s_days(pool)
    print("marks: %d/%d S in the 100-card sweep, %d bar-backed S days total\n"
          % (len(sweep_s_keys), len(sweep_rows), len(all_s_keys)))

    # ---- arms
    baseline_firsts = om.first_of_day_arm(rows)
    arm_firsts = first_matching_arm(rows, lambda r: r.get("confluence") == "yes")
    inverse_firsts = first_matching_arm(rows, lambda r: r.get("confluence") == "no")

    total_sessions = blob["meta"].get("sessions") or len({r["day"] for r in rows})

    results = {}
    for label, firsts in (("baseline", baseline_firsts),
                          ("arm_s_indicator", arm_firsts),
                          ("arm_inverse", inverse_firsts)):
        overall = scoreboard_row(firsts, total_sessions)
        h1 = scoreboard_row([r for r in firsts if half(r["day"]) == "H1"],
                             sessions_in_half(rows, "H1"))
        h2 = scoreboard_row([r for r in firsts if half(r["day"]) == "H2"],
                             sessions_in_half(rows, "H2"))
        rp = recall_and_precision(firsts, pool, sweep_s_keys, all_s_keys)
        results[label] = {
            "overall": overall, "H1": h1, "H2": h2,
            "fires_per_day": round(len(firsts) / total_sessions, 4),
            **rp,
        }

    # ---- candidates/day for the S-indicator predicate (pre-selection rate,
    # not the one-a-day fire rate): how many fired candidates per session
    # satisfy confluence=='yes', across the whole fired pool (not just the
    # picked first-of-day).
    cand_days = defaultdict(int)
    for r in fired:
        if r.get("confluence") == "yes":
            cand_days[r["day"]] += 1
    candidates_per_day = round(sum(cand_days.values()) / total_sessions, 4)

    # ---- ladder fold: distribution among rows the S-indicator predicate
    # keeps, before vs after the +1-capped upgrade.
    ladder_before, ladder_after = ladder_distribution(
        fired, lambda r: r.get("confluence") == "yes")

    base = results["baseline"]
    arm = results["arm_s_indicator"]
    inv = results["arm_inverse"]

    def better(a, b):
        return (a is not None and b is not None and a > b)

    h1_delta = (arm["H1"]["usd_day"] - base["H1"]["usd_day"]
                if arm["H1"]["usd_day"] is not None and base["H1"]["usd_day"] is not None
                else None)
    h2_delta = (arm["H2"]["usd_day"] - base["H2"]["usd_day"]
                if arm["H2"]["usd_day"] is not None and base["H2"]["usd_day"] is not None
                else None)

    h1_improves = (h1_delta is not None and h1_delta > 0) or \
        better(arm["precision"], base["precision"])
    h2_improves = (h2_delta is not None and h2_delta > 0) or \
        better(arm["precision"], base["precision"])
    recall_ok = (arm["recall_100"] is not None and base["recall_100"] is not None
                 and arm["recall_100"] >= base["recall_100"])
    survivor = bool(h1_improves and h2_improves and recall_ok)

    out = {
        "candidate": "brocr-confluence-upgrade-at-fire",
        "row": "F5",
        "predicate": "confluence == 'yes' (== 'brocr' in tags)",
        "book": os.path.basename(BOOK_PATH),
        "sessions_total": total_sessions,
        "fired_rows_total": len(fired),
        "fired_rows_confluence_yes": len(conf_yes),
        "sanity_confluence_matches_brocr_tag_pct": round(agree_pct, 4),
        "candidates_per_day_confluence_yes": candidates_per_day,
        "results": results,
        "ladder_fold": {
            "note": "engine A+/A/B/C/X ladder on fired rows where confluence=='yes', "
                    "before vs after a +1-capped (never-downgrade) upgrade -- "
                    "reporting only, not wired into selection",
            "before": ladder_before,
            "after": ladder_after,
        },
        "h1_delta_usd_day": round(h1_delta, 2) if h1_delta is not None else None,
        "h2_delta_usd_day": round(h2_delta, 2) if h2_delta is not None else None,
        "survivor": survivor,
    }

    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=2)

    lines = []
    lines.append("# g154 -- brocr-confluence-upgrade-at-fire (F5)\n")
    lines.append("One sentence: filtering the one-trade-a-day arm to fired candidates with "
                  "BR+OCR confluence (%d of %d fired rows, %.1f%%) %s vs the unfiltered baseline "
                  "on both halves, so this candidate %s a survivor.\n"
                  % (len(conf_yes), len(fired), 100.0 * len(conf_yes) / len(fired),
                     "improves $/day or precision" if (h1_improves and h2_improves) else
                     "does NOT clearly improve $/day or precision",
                     "IS" if survivor else "is NOT"))

    def fmt_row(label, r):
        o = r["overall"]
        return ("| %s | $%s | %s | %s | %s | %s | %s | %s | %s |"
                % (label, o["usd_day"], o["mean_r"], o["win_rate"], o["months_green"],
                   o["max_dd_usd"], r["fires_per_day"], r["precision"], r["recall_100"]))

    lines.append("| arm | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    lines.append(fmt_row("baseline (first-of-day)", results["baseline"]))
    lines.append(fmt_row("S-indicator (confluence==yes)", results["arm_s_indicator"]))
    lines.append(fmt_row("inverse (confluence==no)", results["arm_inverse"]))
    lines.append("")
    lines.append("recall_all_s_days (all bar-backed S days, marks_pool.s_days()): baseline %s, arm %s, inverse %s\n"
                  % (results["baseline"]["recall_all_s_days"],
                     results["arm_s_indicator"]["recall_all_s_days"],
                     results["arm_inverse"]["recall_all_s_days"]))

    lines.append("## H1 (< %s) / H2 (>= %s) split\n" % (H_SPLIT, H_SPLIT))
    lines.append("| arm | H1 $/day | H2 $/day | H1 green | H2 green |")
    lines.append("|---|---:|---:|---:|---:|")
    for label, key in (("baseline", "baseline"), ("S-indicator", "arm_s_indicator"),
                       ("inverse", "arm_inverse")):
        r = results[key]
        lines.append("| %s | $%s | $%s | %s | %s |"
                      % (label, r["H1"]["usd_day"], r["H2"]["usd_day"],
                         r["H1"]["months_green"], r["H2"]["months_green"]))
    lines.append("")
    lines.append("H1/H2 delta vs baseline (S-indicator arm): $%s / $%s\n"
                  % (out["h1_delta_usd_day"], out["h2_delta_usd_day"]))

    lines.append("## fire-time ladder fold (confluence=='yes' fired rows, engine A+/A/B/C/X)\n")
    lines.append("before: %s" % ladder_before)
    lines.append("")
    lines.append("after +1-capped upgrade: %s\n" % ladder_after)

    lines.append("candidates/day (pre-selection, confluence=='yes' fired rows): %s\n"
                  % candidates_per_day)
    lines.append("sanity check -- confluence=='yes' agrees with 'brocr' in tags on %.2f%% "
                  "of fired rows (not literally identical; predicate uses confluence=='yes')\n"
                  % (agree_pct * 100.0))
    lines.append("survivor = %s (H1 and H2 both improve $/day or precision, "
                  "recall_100 not below baseline)\n" % survivor)

    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines))

    print("wrote %s" % OUT_JSON)
    print("wrote %s" % OUT_MD)
    print("\nsurvivor: %s" % survivor)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
