"""g113 -- best 2-way and 3-way combinations of downgrade vetoes, by EV/R.

Sweep brief, 2026-09-03: "The best 2-way and 3-way combinations of downgrade
vetoes by EV/R." Headline is EV/R (research/omen_metrics.ev_r_scoreboard),
never $/day. Every arm is size-gated on signal_runner.min_risk_floor via that
same scoreboard, and n_dropped_size_gate is always reported.

WHAT A "DOWNGRADE VETO" MEANS HERE
-----------------------------------
Every row in the committed book already carries `downgrades` -- the list of
downgrade.py variable names that tripped on that candidate, computed causally
(bars up to the entry bar only, R1-R4/CLAUDE.md-legal, no lookahead). A veto
combo is a SET of those variable names. Applying it to the honest "first
candidate of the day" arm (research/g86_honest_ceiling.py::candidates, the
same fired-and-traded-or-halted stream every other g-series sweep uses):
walk each day's candidates in arrival order (day, et, sym) and skip any
candidate whose tripped set intersects the veto set. The first survivor is
that day's trade; a day with no survivor contributes no trade. This is a
CLASSIFIER gate on the existing arrival-order policy, not a ranker -- it
never looks at a later candidate's own downgrades to decide, and it never
looks past the entry bar. No day's selection depends on any other day.

UNIVERSE OF VARIABLES
----------------------
The 8 names in downgrade.VARIABLES plus "chase" (R22, ships on in this
book's flags) = 9. `break_then_rejection` never trips in this book (0 of
8,227 candidates) so any combo containing it is identical to the same combo
without it -- reported, not hidden, and flagged as a no-op.

    9 vars -> C(9,2) = 36 two-way combos, C(9,3) = 84 three-way combos.
    120 combos total. Exhaustive within this slice -- every combo is scored,
    none sampled.

OVERFITTING GUARD
------------------
The top arms by full-book EV/R are re-scored on two held-out halves of the
SAME already-built (causal, no-reselection) trade stream: first year
(2024-09-03..2025-08-29, 249 sessions) vs second year (2025-09-02..
2026-09-02, 249 sessions). The split is descriptive, not a train/test
refit -- the per-day selection rule never used which half a day falls into,
so this only exposes an arm whose apparent edge lives in one regime and
inverts or vanishes in the other, without re-fitting anything.

    python research/g113_filters_combo.py
"""
from __future__ import annotations

import itertools
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from research.omen_metrics import ev_r_scoreboard, MIN_RISK_FLOOR_SOURCE   # noqa: E402
import g86_honest_ceiling as g86                                          # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
OUT_JSON = os.path.join(HERE, "g113_filters_combo.json")
OUT_MD = os.path.join(HERE, "g113_filters_combo.md")

VETO_VARS = (
    "no_displacement", "stale_retest", "level_not_respected", "exhausted",
    "counter_trend_not_respected", "break_then_rejection", "no_retest",
    "ocr_not_respected", "chase",
)

FIRST_YEAR_LAST_DAY = "2025-08-29"   # inclusive; 249 sessions each side
SECOND_YEAR_FIRST_DAY = "2025-09-02"


def load_candidates():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, rows = blob["meta"], blob["trades"]
    byday = g86.candidates(rows)   # fired&traded, or halted; sorted by ekey
    return meta, byday


def pick_trades(byday, veto_set):
    """First survivor per day under `veto_set`, in arrival order. Causal:
    each day's pick only reads that day's own candidates, in the order they
    actually arrived; no candidate's downgrades are read past its own bar."""
    trades = []
    days_with_trade = 0
    days_all_vetoed = 0
    for day in sorted(byday):
        survivor = None
        for r in byday[day]:
            if not (set(r.get("downgrades", ())) & veto_set):
                survivor = r
                break
        if survivor is not None:
            trades.append(survivor)
            days_with_trade += 1
        else:
            days_all_vetoed += 1
    return trades, days_with_trade, days_all_vetoed


def half_split(trades):
    first = [t for t in trades if t["day"] <= FIRST_YEAR_LAST_DAY]
    second = [t for t in trades if t["day"] >= SECOND_YEAR_FIRST_DAY]
    return first, second


def score(trades, sessions):
    return ev_r_scoreboard(trades, sessions=sessions)


def main():
    meta, byday = load_candidates()
    sessions = meta["sessions"]
    risk_dollars = meta.get("risk_dollars", 1000.0)
    print("book: %s (%d sessions, %d candidate days, %d candidates)"
          % (os.path.basename(BOOK), sessions, len(byday),
             sum(len(v) for v in byday.values())))
    print("min_risk_floor source: %s" % MIN_RISK_FLOOR_SOURCE)
    print("risk_dollars: %s\n" % risk_dollars)

    # baseline: no veto at all -- must reproduce the ruling's own number.
    base_trades, base_days, _ = pick_trades(byday, frozenset())
    base_sb = score(base_trades, sessions)
    print("=== baseline: first candidate of the day, no veto ===")
    print("  ev_r=%s n=%d n_dropped_size_gate=%d win_rate=%s avg_win_R=%s "
          "avg_loss_R=%s months_green=%s"
          % (base_sb["ev_r"], base_sb["n"], base_sb["n_dropped_size_gate"],
             base_sb["win_rate"], base_sb["avg_win_R"], base_sb["avg_loss_R"],
             base_sb["months_green"]))
    sanity = abs(base_sb["ev_r"] - 0.0377) < 0.0005 and base_sb["n"] == 444
    print("  matches ruling's stated ev_r=0.0377, n=444: %s\n"
          % ("YES" if sanity else "NO -- investigate before trusting combos"))

    trip_counts = defaultdict(int)
    for v in byday.values():
        for r in v:
            for d in r.get("downgrades", ()):
                trip_counts[d] += 1
    noop_vars = {v for v in VETO_VARS if trip_counts.get(v, 0) == 0}
    if noop_vars:
        print("no-op variables (never trip in this book's candidate stream): %s\n"
              % sorted(noop_vars))

    results = {"2way": [], "3way": []}
    n_tested = {"2way": 0, "3way": 0}
    for k, label in ((2, "2way"), (3, "3way")):
        for combo in itertools.combinations(VETO_VARS, k):
            n_tested[label] += 1
            veto_set = frozenset(combo)
            trades, days_with_trade, days_all_vetoed = pick_trades(byday, veto_set)
            sb = score(trades, sessions)
            results[label].append({
                "combo": list(combo),
                "is_noop": bool(veto_set & noop_vars) and len(veto_set - noop_vars) == 0,
                "contains_noop_var": bool(veto_set & noop_vars),
                "days_with_trade": days_with_trade,
                "days_all_vetoed": days_all_vetoed,
                **sb,
            })

    print("combinations tested: %d two-way + %d three-way = %d total "
          "(exhaustive over %d variables, C(9,2)+C(9,3))\n"
          % (n_tested["2way"], n_tested["3way"],
             n_tested["2way"] + n_tested["3way"], len(VETO_VARS)))

    MIN_N = 30  # below this, EV/R on this book is noise -- flag, don't hide
    top_n = 10

    for label in ("2way", "3way"):
        arms = results[label]
        scoreable = [a for a in arms if a["ev_r"] is not None]
        scoreable.sort(key=lambda a: a["ev_r"], reverse=True)
        print("=== top %d %s combos by EV/R ===" % (top_n, label))
        print("| combo | ev_r | n | n_dropped_gate | win% | avg_win_R | "
              "avg_loss_R | PF | months_green | flag |")
        print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for a in scoreable[:top_n]:
            flag = []
            if a["n"] < MIN_N:
                flag.append("LOW-N(<%d)" % MIN_N)
            if a["contains_noop_var"]:
                flag.append("contains no-op var")
            print("| %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |"
                  % (" & ".join(a["combo"]), a["ev_r"], a["n"],
                     a["n_dropped_size_gate"],
                     round(a["win_rate"] * 100, 1) if a["win_rate"] is not None else None,
                     a["avg_win_R"], a["avg_loss_R"], a["profit_factor"],
                     a["months_green"], ", ".join(flag) or "-"))
        print()

    # ---- overfitting guard: re-score top arms on held-out halves --------
    print("=== held-out check: same trade stream, split first year / "
          "second year (no reselection) ===")
    print("first year: 2024-09-03..%s (249 sessions)  |  second year: "
          "%s..2026-09-02 (249 sessions)\n" % (FIRST_YEAR_LAST_DAY, SECOND_YEAR_FIRST_DAY))

    holdout = {"2way": [], "3way": []}
    for label in ("2way", "3way"):
        arms = sorted([a for a in results[label] if a["ev_r"] is not None],
                       key=lambda a: a["ev_r"], reverse=True)[:top_n]
        print("--- %s ---" % label)
        print("| combo | full ev_r (n) | year1 ev_r (n) | year2 ev_r (n) | "
              "sign-consistent | flag |")
        print("|---|---:|---:|---:|---|---|")
        for a in arms:
            veto_set = frozenset(a["combo"])
            trades, _, _ = pick_trades(byday, veto_set)
            first, second = half_split(trades)
            sb1 = score(first, 249)
            sb2 = score(second, 249)
            consistent = (sb1["ev_r"] is not None and sb2["ev_r"] is not None
                          and (sb1["ev_r"] > 0) == (sb2["ev_r"] > 0) == (a["ev_r"] > 0))
            flag = []
            if not consistent:
                flag.append("REGIME-DEPENDENT: sign flips across the split")
            if sb1["n"] < MIN_N or sb2["n"] < MIN_N:
                flag.append("one half n<%d" % MIN_N)
            print("| %s | %s (%d) | %s (%d) | %s (%d) | %s | %s |"
                  % (" & ".join(a["combo"]), a["ev_r"], a["n"],
                     sb1["ev_r"], sb1["n"], sb2["ev_r"], sb2["n"],
                     "yes" if consistent else "NO", ", ".join(flag) or "-"))
            holdout[label].append({
                "combo": a["combo"], "full": {"ev_r": a["ev_r"], "n": a["n"]},
                "year1": {"ev_r": sb1["ev_r"], "n": sb1["n"]},
                "year2": {"ev_r": sb2["ev_r"], "n": sb2["n"]},
                "sign_consistent": consistent,
            })
        print()

    # ---- full scan: which of ALL 120 combos are sign-consistent, and     --
    # ---- which are actually ROBUST (positive full + both halves, n>=30) --
    print("=== full scan (all %d combos, not just the top-ranked-by-full-EV/R "
          "ones): which survive the split? ===\n" % (n_tested["2way"] + n_tested["3way"]))
    b1, b2 = half_split(base_trades)
    base_sb1, base_sb2 = score(b1, 249), score(b2, 249)
    print("baseline itself is regime-dependent: full ev_r=%s, year1 ev_r=%s "
          "(n=%d), year2 ev_r=%s (n=%d) -- the sign flip is NOT caused by any "
          "veto combo; it is a property of the unfiltered first-of-day arm.\n"
          % (base_sb["ev_r"], base_sb1["ev_r"], base_sb1["n"],
             base_sb2["ev_r"], base_sb2["n"]))

    all_scan = []
    for label in ("2way", "3way"):
        for a in results[label]:
            veto_set = frozenset(a["combo"])
            trades, _, _ = pick_trades(byday, veto_set)
            first, second = half_split(trades)
            sb1, sb2 = score(first, 249), score(second, 249)
            if a["ev_r"] is None or sb1["ev_r"] is None or sb2["ev_r"] is None:
                continue
            sign_consistent = (a["ev_r"] > 0) == (sb1["ev_r"] > 0) == (sb2["ev_r"] > 0)
            robust = (sign_consistent and a["ev_r"] > 0
                      and sb1["n"] >= MIN_N and sb2["n"] >= MIN_N)
            all_scan.append({
                "label": label, "combo": a["combo"], "full_ev_r": a["ev_r"],
                "full_n": a["n"], "year1_ev_r": sb1["ev_r"], "year1_n": sb1["n"],
                "year2_ev_r": sb2["ev_r"], "year2_n": sb2["n"],
                "sign_consistent": sign_consistent, "robust_positive": robust,
            })

    n_sign_consistent = sum(1 for a in all_scan if a["sign_consistent"])
    robust_arms = [a for a in all_scan if a["robust_positive"]]
    robust_arms.sort(key=lambda a: min(a["year1_ev_r"], a["year2_ev_r"]), reverse=True)
    print("sign-consistent across full+both halves (any sign): %d of %d combos"
          % (n_sign_consistent, len(all_scan)))
    print("ROBUST (positive in full AND both halves, n>=%d each half): %d of %d combos\n"
          % (MIN_N, len(robust_arms), len(all_scan)))
    if robust_arms:
        print("| combo | full ev_r (n) | year1 ev_r (n) | year2 ev_r (n) | "
              "beats baseline full ev_r (%s)? |" % base_sb["ev_r"])
        print("|---|---:|---:|---:|---|")
        for a in robust_arms:
            beats = "yes" if a["full_ev_r"] > base_sb["ev_r"] else "no"
            print("| %s | %s (%d) | %s (%d) | %s (%d) | %s |"
                  % (" & ".join(a["combo"]), a["full_ev_r"], a["full_n"],
                     a["year1_ev_r"], a["year1_n"], a["year2_ev_r"], a["year2_n"], beats))
        print()
    else:
        print("no combo is robust by this bar.\n")

    out = {
        "book": os.path.basename(BOOK),
        "sessions": sessions,
        "risk_dollars": risk_dollars,
        "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
        "baseline_no_veto": base_sb,
        "baseline_matches_ruling": sanity,
        "vars": list(VETO_VARS),
        "noop_vars": sorted(noop_vars),
        "n_tested": n_tested,
        "results": results,
        "holdout_top_arms": holdout,
        "baseline_year1": base_sb1,
        "baseline_year2": base_sb2,
        "n_sign_consistent": n_sign_consistent,
        "robust_arms": robust_arms,
        "full_scan": all_scan,
    }
    json.dump(out, open(OUT_JSON, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT_JSON)


if __name__ == "__main__":
    main()
