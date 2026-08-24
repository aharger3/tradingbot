"""downgrade_tune -- one-factor-at-a-time sweeps of every constant in downgrade.py.

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
`research/downgrade.py` carries seven numbers plus one structural choice, and its
own header says Austin never set any of them. T66 measured the grader at those
guesses: S-day recall 12/28, and a grade distribution of S/A/C = 168/304/778
against Austin's own corpus of 28/27/3. The shape is right and the numbers are
wrong.

This sweeps **one parameter at a time**, holding every other one at its current
default. It is deliberately NOT a grid:

  * Seven parameters over 120 day-cards is a licence to overfit the only data the
    gate will ever be scored on. A grid finds the corner of the cube that flatters
    this corpus and nothing else.
  * **Interactions are unmeasured.** Two settings that each look good alone may be
    measuring the same thing twice, or may cancel. Nothing in this report tells you
    what happens when you move two knobs together. If a combination is adopted it
    has to be re-measured as a combination.

**No default in `downgrade.py` is changed by this script.** Globals are patched in
memory for the duration of one evaluation and restored afterwards. The report is a
menu for Austin to choose from, not a decision.

SCORING
-------
Exactly T66's arithmetic, with `TRADEABLE = ("S",)` -- Austin, asked directly,
2026-08-24: "S only".

    S recall     his 28 S-days on which at least one signal grades S
    false fire   his 61 refused ("none") days on which at least one signal grades S
    score        S_recall - false_fire_rate           <- primary ranking
    shape        distance from his own 28/27/3 grade mix   <- secondary ranking

Two answers from 2026-08-24 constrain the sweep and are reported explicitly:

  1. Confluence currently fires on ~65% of signals. Austin: it must be **under 1 in
     5**. The find_ocr sweeps (proximity + isolation strictness) carry a confluence
     column and every setting under 20% is flagged.
  2. The distribution should end up looking like **28/27/3**, not 168/304/778. That
     is the second ranking column, not an afterthought.

    python research/downgrade_tune.py

Writes research/downgrade_tune.md.
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (HERE, ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from research import downgrade as dg                                   # noqa: E402
from research.t66_downgrade_measure import replay, TRADEABLE, TOL      # noqa: E402
from research.t60_baseline import load_day_cards                       # noqa: E402

OUT = os.path.join(HERE, "downgrade_tune.md")

# Austin's own corpus, the shape the grader is supposed to end up looking like.
AUSTIN_MIX = {"S": 28, "A": 27, "C": 3}
CONFLUENCE_CAP = 0.20        # Austin 2026-08-24: "under 1 in 5"

DEFAULTS = {
    "STALE_BARS": 15,
    "CHOP_TOUCHES": 2,
    "EXHAUSTED_ATR": 10.0,
    "DISP_BODY_MULT": 1.5,
    "REJECT_BARS": 2,
    "UNRESPECTED_COUNTER": 2,
}
OCR_LOOKBACK_DEFAULT = 20
OCR_ISOLATION_DEFAULT = "both"

SWEEPS = [
    ("STALE_BARS", [3, 5, 8, 10, 15, 20, 30, 60]),
    ("CHOP_TOUCHES", [1, 2, 3, 4, 5, 6, 8]),
    ("EXHAUSTED_ATR", [2.0, 3.0, 5.0, 8.0, 10.0, 15.0, 20.0, 30.0]),
    ("DISP_BODY_MULT", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]),
    ("REJECT_BARS", [1, 2, 3, 5, 8, 12]),
    ("UNRESPECTED_COUNTER", [1, 2, 3, 4, 5, 6, 8]),
    ("ocr_lookback", [2, 3, 5, 8, 10, 15, 20, 30]),
    ("ocr_isolation", ["none", "left", "right", "both", "both2"]),
]

# The ONE place this script crosses two knobs, and only because Austin's 1-in-5
# confluence cap is a hard yes/no constraint rather than something to fit. Both
# knobs live inside `find_ocr` and are the same mechanism -- how hard is it to be
# an OCR -- so sweeping them singly cannot answer "is the cap reachable at all".
# It is still reported separately from the one-factor tables, and it is still not
# a recommendation.
CONFLUENCE_CROSS = ([2, 3, 5, 8, 10], ["both", "both2"])

ISOLATION_NOTE = {
    "none": "any counter-coloured candle counts (no isolation test at all)",
    "left": "the candle before it must be trend-coloured",
    "right": "the candle after it must be trend-coloured",
    "both": "both neighbours trend-coloured  <- current",
    "both2": "two trend-coloured candles on each side",
}


# ---------------------------------------------------------------------------
# find_ocr variants -- proximity (lookback) and isolation strictness
# ---------------------------------------------------------------------------

def make_find_ocr(lookback, isolation):
    """A drop-in for `downgrade.find_ocr` with the isolation test parameterised.

    `ocr_not_respected` and `has_confluence` both look `find_ocr` up as a module
    global at call time, so patching `dg.find_ocr` reaches every caller.
    """
    def _iso(bars, j, i, is_long):
        def trend(k):
            return dg._is_up(bars[k]) if is_long else (not dg._is_up(bars[k]))
        if isolation == "none":
            return True
        if isolation == "left":
            return trend(j - 1)
        if isolation == "right":
            return trend(j + 1)
        if isolation == "both":
            return trend(j - 1) and trend(j + 1)
        if isolation == "both2":
            if j - 2 < 0 or j + 2 > i:
                return False
            return trend(j - 1) and trend(j + 1) and trend(j - 2) and trend(j + 2)
        raise ValueError(isolation)

    def find_ocr(bars, i, is_long, lookback=lookback):
        for j in range(i - 1, max(1, i - lookback) - 1, -1):
            if j + 1 > i:
                continue
            b = bars[j]
            counter = (not dg._is_up(b)) if is_long else dg._is_up(b)
            if not counter:
                continue
            if _iso(bars, j, i, is_long):
                return j
        return None

    return find_ocr


# ---------------------------------------------------------------------------
# the corpus, replayed once
# ---------------------------------------------------------------------------

def build_corpus():
    """Detection is UNCHANGED by every setting swept here, so the engine replay
    happens once and every evaluation re-grades the same signals."""
    days, marks = load_day_cards()
    corpus = []
    for key in sorted(days):
        sigs, bars = replay(*key)
        if sigs is None:
            continue
        corpus.append((key, sigs, bars))
    return days, corpus


def shape_distance(counts):
    """Total-variation distance between this grade mix and Austin's 28/27/3.

    0.0 = identical shape, 1.0 = no overlap. Shares, not counts -- he graded 58
    cards and the engine emits ~1250 signals, so only the proportions compare.
    """
    n = sum(counts.get(g, 0) for g in ("S", "A", "C"))
    m = sum(AUSTIN_MIX.values())
    if n == 0:
        return 1.0
    return 0.5 * sum(abs(counts.get(g, 0) / n - AUSTIN_MIX[g] / m)
                     for g in ("S", "A", "C"))


def evaluate(days, corpus):
    """One pass of `downgrade.score` over the replayed corpus at whatever the
    module globals currently say."""
    grades = Counter()
    confluence = 0
    n_sigs = 0
    fired = set()
    for key, sigs, bars in corpus:
        for s in sigs:
            rec = dg.score(bars, s["bar"], s["stop"], s["dir"] == "call",
                           htf_bias=s["bias"])
            if rec is None:
                continue
            n_sigs += 1
            grades[rec["grade"]] += 1
            confluence += 1 if rec["confluence"] else 0
            if rec["grade"] in TRADEABLE:
                fired.add(key)

    graded = {k: (v.get("grade") or "").strip() for k, v in days.items()}
    s_days = {k for k, g in graded.items() if g == "S"}
    none_days = {k for k, g in graded.items() if g == "none"}
    s_hit = len(fired & s_days)
    ff = len(fired & none_days)
    return {
        "s_hit": s_hit, "s_tot": len(s_days),
        "ff": ff, "ff_tot": len(none_days),
        "s_recall": s_hit / max(len(s_days), 1),
        "false_fire": ff / max(len(none_days), 1),
        "S": grades["S"], "A": grades["A"], "C": grades["C"],
        "n_sigs": n_sigs,
        "confluence": confluence / max(n_sigs, 1),
        "shape": shape_distance(grades),
    }


def apply_setting(param, value):
    """Patch one knob. Returns a callable that puts everything back."""
    if param in DEFAULTS:
        old = getattr(dg, param)
        setattr(dg, param, value)
        return lambda: setattr(dg, param, old)
    old_fn = dg.find_ocr
    if param == "ocr_lookback":
        dg.find_ocr = make_find_ocr(value, OCR_ISOLATION_DEFAULT)
    elif param == "ocr_isolation":
        dg.find_ocr = make_find_ocr(OCR_LOOKBACK_DEFAULT, value)
    else:
        raise ValueError(param)
    return lambda: setattr(dg, "find_ocr", old_fn)


def is_default(param, value):
    if param in DEFAULTS:
        return value == DEFAULTS[param]
    if param == "ocr_lookback":
        return value == OCR_LOOKBACK_DEFAULT
    return value == OCR_ISOLATION_DEFAULT


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def row(r, label):
    return ("| %s | %d/%d = %.3f | %d/%d = %.3f | **%+.3f** | %d/%d/%d | %.3f | %.1f%%%s |"
            % (label,
               r["s_hit"], r["s_tot"], r["s_recall"],
               r["ff"], r["ff_tot"], r["false_fire"],
               r["s_recall"] - r["false_fire"],
               r["S"], r["A"], r["C"], r["shape"],
               100.0 * r["confluence"],
               " ✅" if r["confluence"] < CONFLUENCE_CAP else ""))


HEAD = ("| setting | S recall | false fire | score | S/A/C | shape dist | confluence |\n"
        "|---|---|---|---:|---|---:|---|")


def main():
    t0 = time.time()
    days, corpus = build_corpus()
    print("replayed %d day-cards in %.1fs" % (len(corpus), time.time() - t0))

    base = evaluate(days, corpus)
    print("baseline: S %d/%d  false %d/%d  S/A/C %d/%d/%d  confl %.1f%%"
          % (base["s_hit"], base["s_tot"], base["ff"], base["ff_tot"],
             base["S"], base["A"], base["C"], 100 * base["confluence"]))

    results = []       # (param, value, rec)
    for param, values in SWEEPS:
        for v in values:
            restore = apply_setting(param, v)
            try:
                rec = evaluate(days, corpus)
            finally:
                restore()
            rec["param"], rec["value"] = param, v
            rec["default"] = is_default(param, v)
            results.append(rec)
            print("  %-20s %-8s  S %2d/%2d  ff %2d/%2d  %d/%d/%d  shape %.3f  confl %.1f%%"
                  % (param, v, rec["s_hit"], rec["s_tot"], rec["ff"], rec["ff_tot"],
                     rec["S"], rec["A"], rec["C"], rec["shape"],
                     100 * rec["confluence"]))

    # the one cross-sweep: find_ocr proximity x isolation, for the cap question only
    cross = []
    _old_fn = dg.find_ocr
    for lb in CONFLUENCE_CROSS[0]:
        for iso in CONFLUENCE_CROSS[1]:
            dg.find_ocr = make_find_ocr(lb, iso)
            try:
                rec = evaluate(days, corpus)
            finally:
                dg.find_ocr = _old_fn
            rec["param"], rec["value"] = "find_ocr cross", (lb, iso)
            rec["default"] = False
            cross.append(rec)
            print("  cross lookback=%-3s iso=%-6s  S %2d/%2d  ff %2d/%2d  %d/%d/%d  confl %.1f%%"
                  % (lb, iso, rec["s_hit"], rec["s_tot"], rec["ff"], rec["ff_tot"],
                     rec["S"], rec["A"], rec["C"], 100 * rec["confluence"]))

    def label(r):
        return "`%s = %s`%s" % (r["param"], r["value"], "  *(current)*" if r["default"] else "")

    L = ["# downgrade_tune — one-factor sweeps of the grader's seven guesses", ""]
    L.append("Generated by `research/downgrade_tune.py` over **%d** graded day-cards. "
             "Detection is unchanged; only the grade is recomputed. Trading set is "
             "`%s`." % (len(corpus), " / ".join(TRADEABLE)))
    L.append("")
    L.append("## Read this before reading the tables")
    L.append("")
    L.append("- **These are one-factor-at-a-time sweeps.** Each row moves ONE constant and "
             "holds the other six at their current value. **Interactions are unmeasured.** "
             "Nothing here says what happens when two knobs move together — two settings that "
             "each look good alone may be measuring the same failure twice, or may cancel. A "
             "combination has to be re-measured as a combination before it is believed.")
    L.append("- **This is not a grid, on purpose.** Seven parameters over 120 day-cards is a "
             "licence to overfit the only data the gate is ever scored on.")
    L.append("- **No default in `downgrade.py` was changed.** Globals are patched in memory "
             "for one evaluation and restored. This is a menu, not a decision.")
    L.append("- `score` = S recall − false-fire rate. `shape dist` = total-variation distance "
             "from Austin's own **28 S / 27 A / 3 C** mix (0.000 = identical shape, lower is "
             "better). ✅ marks confluence under Austin's **1-in-5** cap.")
    L.append("")
    L.append("## Baseline — `downgrade.py` exactly as committed")
    L.append("")
    L.append(HEAD)
    L.append(row(base, "current defaults"))
    L.append("")
    L.append("Austin's corpus mix is **28 / 27 / 3** = %.1f%% S, %.1f%% A, %.1f%% C. "
             "The baseline is %.1f%% / %.1f%% / %.1f%%."
             % (100 * 28 / 58, 100 * 27 / 58, 100 * 3 / 58,
                100.0 * base["S"] / max(base["n_sigs"], 1),
                100.0 * base["A"] / max(base["n_sigs"], 1),
                100.0 * base["C"] / max(base["n_sigs"], 1)))
    L.append("")

    # --- ranking 1: score -------------------------------------------------
    L.append("## Ranking 1 — by `S_recall − false_fire_rate`")
    L.append("")
    L.append("The ranking Austin asked for first. Every swept setting, best score at the top.")
    L.append("")
    L.append(HEAD)
    for r in sorted(results, key=lambda r: -(r["s_recall"] - r["false_fire"])):
        L.append(row(r, label(r)))
    L.append("")

    # --- ranking 2: shape -------------------------------------------------
    L.append("## Ranking 2 — by resemblance to his 28 / 27 / 3")
    L.append("")
    L.append("Same rows, re-sorted by how close the grade mix sits to his own corpus. A "
             "setting that wins ranking 1 by grading almost everything S is not a win.")
    L.append("")
    L.append(HEAD)
    for r in sorted(results, key=lambda r: r["shape"]):
        L.append(row(r, label(r)))
    L.append("")

    # --- confluence -------------------------------------------------------
    L.append("## The 1-in-5 confluence cap")
    L.append("")
    L.append("Austin, 2026-08-24: confluence must fire on **under 1 in 5** signals. At the "
             "committed defaults it fires on **%.1f%%**." % (100 * base["confluence"]))
    L.append("")
    under = [r for r in results
             if r["param"] in ("ocr_lookback", "ocr_isolation")
             and r["confluence"] < CONFLUENCE_CAP]
    L.append("Only `find_ocr` moves this number — nothing else in the grader touches "
             "confluence. Settings that clear the cap:")
    L.append("")
    if under:
        L.append(HEAD)
        for r in sorted(under, key=lambda r: -(r["s_recall"] - r["false_fire"])):
            L.append(row(r, label(r)))
    else:
        L.append("**None.** No single-factor change to `find_ocr`'s proximity or isolation "
                 "gets confluence under 20% on its own.")
    L.append("")
    L.append("### Can the cap be reached at all? — the one cross-sweep in this file")
    L.append("")
    L.append("Proximity and isolation are the same mechanism (how hard is it to be an OCR) "
             "and both live inside `find_ocr`, so sweeping them one at a time cannot answer "
             "whether Austin's cap is reachable. This crosses **only those two**, because the "
             "cap is a yes/no constraint he stated, not a number being fitted. It is still not "
             "a recommendation, and the interaction caveat above still applies to everything "
             "else in the grader.")
    L.append("")
    L.append(HEAD)
    for r in sorted(cross, key=lambda r: -(r["s_recall"] - r["false_fire"])):
        L.append(row(r, "`lookback=%s, isolation=%s`" % (r["value"][0], r["value"][1])))
    L.append("")
    cross_ok = [r for r in cross if r["confluence"] < CONFLUENCE_CAP]
    if cross_ok:
        lowest = min(cross_ok, key=lambda r: r["confluence"])
        best_ok = max(cross_ok, key=lambda r: r["s_recall"] - r["false_fire"])
        L.append("**%d of these clear the 1-in-5 cap**, and only with the strictest isolation "
                 "(`both2` — two trend-coloured candles on each side). Lowest confluence: "
                 "`lookback=%s, isolation=%s` at **%.1f%%**. Best-scoring of the ones that "
                 "clear: `lookback=%s, isolation=%s` at **%.1f%%** confluence, score %+.3f."
                 % (len(cross_ok), lowest["value"][0], lowest["value"][1],
                    100 * lowest["confluence"], best_ok["value"][0], best_ok["value"][1],
                    100 * best_ok["confluence"],
                    best_ok["s_recall"] - best_ok["false_fire"]))
        L.append("")
        L.append("Read the cost, not just the tick: every row that clears the cap does it by "
                 "finding almost no OCR at all, and S-day recall falls to **%d/%d** doing it. "
                 "Confluence stops being a free +1 because confluence stops existing. That may "
                 "still be the right answer — his cap is his cap — but it is not free."
                 % (best_ok["s_hit"], best_ok["s_tot"]))
    else:
        L.append("**None of these clear the cap either.** The floor over this cross is "
                 "**%.1f%%** (`lookback=%s, isolation=%s`). Getting confluence under 1 in 5 "
                 "needs a change to what counts as an OCR that is not in `find_ocr`'s current "
                 "shape at all — a size, distance-to-level, or stop-usability test — not a "
                 "smaller lookback."
                 % ((lambda b: (100 * b["confluence"], b["value"][0], b["value"][1]))(
                     min(cross, key=lambda r: r["confluence"]))))
    L.append("")
    L.append("Isolation strictness, in words:")
    L.append("")
    L.append("| mode | test |")
    L.append("|---|---|")
    for k, v in ISOLATION_NOTE.items():
        L.append("| `%s` | %s |" % (k, v))
    L.append("")

    # --- per-parameter ----------------------------------------------------
    L.append("## Every sweep, parameter by parameter")
    L.append("")
    for param, _ in SWEEPS:
        rows = [r for r in results if r["param"] == param]
        L.append("### `%s`" % param)
        L.append("")
        L.append(HEAD)
        for r in rows:
            L.append(row(r, "`%s`%s" % (r["value"], "  *(current)*" if r["default"] else "")))
        L.append("")
        flat = len({(r["s_hit"], r["ff"], r["S"], r["A"], r["C"]) for r in rows}) == 1
        if flat:
            L.append("**Dead knob over this range** — every value produces an identical "
                     "grade distribution and an identical gate. Either the variable never "
                     "binds, or the range swept is entirely on one side of where it does.")
            L.append("")

    L.append("## What this does not tell you")
    L.append("")
    L.append("1. **Interactions.** One-factor sweeps only. Any two-knob combination is "
             "unmeasured and must be re-run as a combination.")
    L.append("2. **Whether the winner generalises.** Every number here is computed on the "
             "same 120 day-cards the gate is scored on. A setting that wins by 0.02 is "
             "noise; only large, monotone moves should be believed.")
    L.append("3. **Trade quality.** This measures whether a day fires, not what the trade "
             "made. Recall and false fires move together and there is no precision credit "
             "banked — head-to-head came back 0 for 9.")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s  (%.1fs)" % (OUT, time.time() - t0))

    best_score = max(results, key=lambda r: r["s_recall"] - r["false_fire"])
    best_shape = min(results, key=lambda r: r["shape"])
    print("BEST by score : %s = %s  -> %+.3f  (S %d/%d, ff %d/%d, %d/%d/%d)"
          % (best_score["param"], best_score["value"],
             best_score["s_recall"] - best_score["false_fire"],
             best_score["s_hit"], best_score["s_tot"], best_score["ff"], best_score["ff_tot"],
             best_score["S"], best_score["A"], best_score["C"]))
    print("BEST by shape : %s = %s  -> %.3f  (%d/%d/%d)"
          % (best_shape["param"], best_shape["value"], best_shape["shape"],
             best_shape["S"], best_shape["A"], best_shape["C"]))
    lo = min(cross + results, key=lambda r: r["confluence"])
    print("confluence under 20%%, one-factor: %s"
          % (", ".join("%s=%s (%.1f%%)" % (r["param"], r["value"], 100 * r["confluence"])
                       for r in under) or "NONE"))
    print("confluence under 20%%, find_ocr cross: %s"
          % (", ".join("%s (%.1f%%)" % (r["value"], 100 * r["confluence"])
                       for r in cross if r["confluence"] < CONFLUENCE_CAP) or "NONE"))
    print("lowest confluence anywhere: %s %s = %.1f%%"
          % (lo["param"], lo["value"], 100 * lo["confluence"]))


if __name__ == "__main__":
    main()
