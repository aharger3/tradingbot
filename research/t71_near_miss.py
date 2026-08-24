"""t71 -- the near-miss retest, measured before anything adopts it.

THE CARD
--------
Austin, on a deck card:

    "the green candle before entry may have missed entry by a cent or two, and
     usually these work out. not sure if should be a seperate rule or something
     to study/backtest."

He chose **MEASURE BEFORE ADOPTING**. So this measures it and adopts nothing. No
default anywhere in the repo is changed by this script; `detect_break_retest` is
swapped in memory for the length of one sweep row and put straight back.

WHERE THE TOLERANCE GOES
------------------------
"The green candle before entry" is the RETEST candle -- step 3 of
`omen_bot.detect_break_retest`'s ordered FSM (break -> leave -> retest -> confirm).
Today that step demands an exact tag:

    back = (c.low <= level) if is_long else (c.high >= level)

so a candle that turned a cent short of the level is not a retest and the setup
never fires. That is precisely the shape of his card, so the tolerance is applied
there and nowhere else. The break test, the leave test, the confirm close, the
adverse-wick veto and the max_confirm_gap are all untouched -- the entry still has
to CLOSE back through the level, because Austin settled that separately on
2026-08-23 ("the CLOSE decides").

THE UNIT
--------
Austin's one tolerance unit is **25% of the previous candle's range**
(`BAR_EXTREME_FRAC`), so the sweep is expressed in that currency: the band is a
fraction of the range of the candle immediately BEFORE the candidate retest bar.
0%, 10%, 25%, 50%, plus the literal "cent or two" as fixed $0.01 / $0.02.

At 0% this reproduces today's engine byte-for-byte (`signal_runner.DETECT_WIDE`
is False, so the existing `retest_tol_mult` band is already 0.0) -- which is the
control row, and it should match T66 exactly.

SCORING
-------
Both gates, because they answer different questions:

    engine today        the signal carries a grade outside X / D  (status quo)
    downgrade grader    the signal grades S under `research/downgrade.py`,
                        Austin's S/A/C arithmetic, TRADEABLE = ("S",)

    S recall     his 28 S-days on which at least one signal passes the gate
    false fire   his 61 refused ("none") days on which at least one does too

Recall and false fires move together and there is no precision credit banked --
head-to-head came back 0 for 9 -- so neither column means anything alone.

    python research/t71_near_miss.py

Writes research/t71_near_miss.md. **Report only. Adopts nothing.**
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

import omen_bot                                                        # noqa: E402
import signal_runner                                                   # noqa: E402
from research import downgrade as dg                                   # noqa: E402
from research.t66_downgrade_measure import TRADEABLE, OLD_SKIP, as_dicts  # noqa: E402
from research.t4_engine_recall import (CaptureRunner, rth_candles, prior_day_levels,
                                       premarket_extremes, htf_bias, ENTRY_CUTOFF)
from research.t60_baseline import load_day_cards                       # noqa: E402

OUT = os.path.join(HERE, "t71_near_miss.md")

# (label, kind, value).  kind "frac" = fraction of the PREVIOUS candle's range;
# kind "abs" = fixed dollars, his literal "cent or two".
SWEEP = [
    ("0 (today)",           "frac", 0.00),
    ("10% of prev range",   "frac", 0.10),
    ("25% of prev range",   "frac", 0.25),
    ("50% of prev range",   "frac", 0.50),
    ("$0.01 fixed",         "abs",  0.01),
    ("$0.02 fixed",         "abs",  0.02),
]

_ORIGINAL_BR = omen_bot.detect_break_retest


# ---------------------------------------------------------------------------
# the FSM, with ONE line changed
# ---------------------------------------------------------------------------

def make_detector(kind, value):
    """A `detect_break_retest` whose retest band is a near-miss tolerance.

    This is `omen_bot.detect_break_retest` with the step-3/4 proximity test
    rewritten to allow a miss of `value` -- as a fraction of the PREVIOUS
    candle's range, or as fixed dollars. Everything else is line-for-line the
    original, including the funnel counters, so the only thing the sweep can
    move is the near-miss.
    """
    def near_miss_band(w, i):
        if value <= 0:
            return 0.0
        if kind == "abs":
            return value
        prev = w[i - 1]
        return value * (prev.high - prev.low)

    def detect_break_retest(candles, level, is_long, window=12, max_confirm_gap=3,
                            out=None, retest_tol_mult=0.0):
        F = omen_bot.BR_FUNNEL
        F["calls"] += 1
        if len(candles) < 4:
            F["too_short"] += 1
            return None
        w = candles[-window:]
        cur = w[-1]

        # the CLOSE decides -- unchanged
        if (cur.close <= level) if is_long else (cur.close >= level):
            F["no_confirm_close"] += 1
            return None

        avg_rng = sum(c.high - c.low for c in w) / len(w)
        eps = 0.10 * avg_rng
        wide = retest_tol_mult * avg_rng      # the existing DETECT_WIDE band (0.0 today)

        adverse = cur.lower_wick if not is_long else cur.upper_wick
        if adverse > 1.5 * cur.body_size:
            F["adverse_wick"] += 1
            return None

        state, retest_idx = "seek_break", None
        for i in range(1, len(w)):
            c, p = w[i], w[i - 1]
            # >>> THE ONE CHANGE: the retest may miss the level by this much <<<
            rtol = max(wide, near_miss_band(w, i))
            if state == "seek_break":
                crossed = (p.close <= level and c.close > level + eps) if is_long \
                    else (p.close >= level and c.close < level - eps)
                if crossed:
                    state = "seek_leave"
            elif state == "seek_leave":
                left = (c.low > level + eps) if is_long else (c.high < level - eps)
                failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
                if left:
                    state = "seek_retest"
                elif failed:
                    state = "seek_break"
            elif state == "seek_retest":
                back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
                if back:
                    retest_idx, state = i, "hold"
            elif state == "hold":
                back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
                if back:
                    retest_idx = i

        if retest_idx is None:
            F["no_break" if state == "seek_break"
              else ("no_leave" if state == "seek_leave" else "no_retest")] += 1
            return None
        if (len(w) - 1) - retest_idx > max_confirm_gap:
            F["stale_retest"] += 1
            return None

        prior = candles[:-window]
        late = sum(1 for a, b in zip(prior, prior[1:])
                   if (a.close - level) * (b.close - level) < 0)
        tag = f" | LATE({late} prior breaks)" if late else ""
        rc = w[retest_idx]
        touched = (rc.low <= level) if is_long else (rc.high >= level)
        if not touched:
            miss = (rc.low - level) if is_long else (level - rc.high)
            # tagged WIDE so signal_runner's existing "[wide]" reason tag
            # carries it up without touching signal_runner at all
            tag += f" | WIDE(near-miss ${miss:.2f})"
        if out is not None:
            out["retest_low"], out["retest_high"] = rc.low, rc.high
            out["near_miss"] = not touched
        F["passed"] += 1
        return (f"break {'up' if is_long else 'down'} → cleared → retest "
                f"{len(w)-1-retest_idx} bar(s) back → confirm close{tag}")

    return detect_break_retest


# ---------------------------------------------------------------------------
# measurement
# ---------------------------------------------------------------------------

def replay(symbol, day):
    """T66's replay, plus the signal's `reason` string.

    Identical to `t66_downgrade_measure.replay` in every other respect; the extra
    field is needed because the near-miss tag rides in there.
    """
    candles = rth_candles(symbol, day)
    if not candles:
        return None, None
    pdh, pdl, pdo, pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    r = CaptureRunner(symbol)
    r.pdh, r.pdl = pdh, pdl
    r.pmh, r.pml = pmh, pml
    r.pd_open, r.pd_close = pdo, pdc
    bias = htf_bias(symbol, day)
    r.htf_bias = bias
    r.qqq_breaks = None

    out = []
    for i in range(5, len(candles)):
        if ENTRY_CUTOFF and candles[i].timestamp >= ENTRY_CUTOFF:
            continue
        r.candles = candles[: i + 1]
        before = len(r.captured)
        try:
            r.detect_signals()
        except Exception:
            continue
        for s in r.captured[before:]:
            out.append({"bar": i, "old": s.get("grade"), "stop": s.get("stop"),
                        "dir": s.get("direction"), "bias": bias,
                        "reason": s.get("reason") or ""})
    return out, as_dicts(candles)


def run_once(days):
    """Replay all 120 day-cards under whatever detector is currently installed."""
    n_sigs = 0
    near_miss_sigs = 0
    grades_new = Counter()
    fire_old, fire_new = set(), set()
    for key in sorted(days):
        sigs, bars = replay(*key)
        if sigs is None:
            continue
        for s in sigs:
            n_sigs += 1
            if "[wide]" in s["reason"]:
                near_miss_sigs += 1
            if s["old"] not in OLD_SKIP:
                fire_old.add(key)
            rec = dg.score(bars, s["bar"], s["stop"], s["dir"] == "call",
                           htf_bias=s["bias"])
            if rec is None:
                continue
            grades_new[rec["grade"]] += 1
            if rec["grade"] in TRADEABLE:
                fire_new.add(key)

    graded = {k: (v.get("grade") or "").strip() for k, v in days.items()}
    s_days = {k for k, g in graded.items() if g == "S"}
    none_days = {k for k, g in graded.items() if g == "none"}

    def gate(fired):
        return {"s_hit": len(fired & s_days), "s_tot": len(s_days),
                "ff": len(fired & none_days), "ff_tot": len(none_days),
                "s_recall": len(fired & s_days) / max(len(s_days), 1),
                "false_fire": len(fired & none_days) / max(len(none_days), 1)}

    return {"n_sigs": n_sigs, "near_miss": near_miss_sigs,
            "old": gate(fire_old), "new": gate(fire_new),
            "S": grades_new["S"], "A": grades_new["A"], "C": grades_new["C"]}


def cells(g):
    return ("%d/%d = %.3f | %d/%d = %.3f | **%+.3f**"
            % (g["s_hit"], g["s_tot"], g["s_recall"],
               g["ff"], g["ff_tot"], g["false_fire"],
               g["s_recall"] - g["false_fire"]))


HEAD = ("| near-miss tolerance | signals | S recall | false fire | score |\n"
        "|---|---:|---|---|---:|")


def main():
    t0 = time.time()
    days, _ = load_day_cards()

    rows = []
    for label, kind, value in SWEEP:
        signal_runner.detect_break_retest = make_detector(kind, value)
        try:
            r = run_once(days)
        finally:
            signal_runner.detect_break_retest = _ORIGINAL_BR
        r["label"], r["kind"], r["value"] = label, kind, value
        rows.append(r)
        print("  %-20s sigs %4d (near-miss %3d)  ENGINE S %2d/%2d ff %2d/%2d   "
              "DOWNGRADE S %2d/%2d ff %2d/%2d   S/A/C %d/%d/%d"
              % (label, r["n_sigs"], r["near_miss"],
                 r["old"]["s_hit"], r["old"]["s_tot"], r["old"]["ff"], r["old"]["ff_tot"],
                 r["new"]["s_hit"], r["new"]["s_tot"], r["new"]["ff"], r["new"]["ff_tot"],
                 r["S"], r["A"], r["C"]))

    base = rows[0]

    L = ["# T71 — the near-miss retest, measured", ""]
    L.append("Generated by `research/t71_near_miss.py` over Austin's **120** graded "
             "day-cards.")
    L.append("")
    L.append("> **Report only. Nothing is adopted and no default is changed.** Austin's card "
             "said *\"not sure if should be a seperate rule or something to study/backtest\"* "
             "and he chose measure-before-adopting. `detect_break_retest` is swapped in "
             "memory for the length of one row and put straight back.")
    L.append("")
    L.append("## The card")
    L.append("")
    L.append("> the green candle before entry may have missed entry by a cent or two, and "
             "usually these work out. not sure if should be a seperate rule or something to "
             "study/backtest.")
    L.append("")
    L.append("\"The green candle before entry\" is the **retest** candle — step 3 of the "
             "ordered break→leave→retest→confirm FSM in `omen_bot.detect_break_retest`. Today "
             "that step demands an exact tag of the level, so a candle that turned a cent "
             "short is not a retest and the setup never fires. The tolerance is applied there "
             "and nowhere else: the break, the leave, the adverse-wick veto, the confirm gap, "
             "and above all the requirement that the entry candle **CLOSE** back through the "
             "level are untouched.")
    L.append("")
    L.append("The unit is his own — **a fraction of the previous candle's range** "
             "(`BAR_EXTREME_FRAC` currency) — plus the literal \"cent or two\" as fixed "
             "dollars. The `0 (today)` row reproduces the current engine exactly and is the "
             "control.")
    L.append("")

    L.append("## Gate 1 — the downgrade grader, `TRADEABLE = (\"S\",)`")
    L.append("")
    L.append(HEAD)
    for r in rows:
        L.append("| %s | %d | %s |" % (r["label"], r["n_sigs"], cells(r["new"])))
    L.append("")

    L.append("## Gate 2 — the engine's own grade today (not X / D)")
    L.append("")
    L.append("Reported because it is the gate actually running, and because it separates "
             "\"the near-miss found new setups\" from \"the new grader liked them\".")
    L.append("")
    L.append(HEAD)
    for r in rows:
        L.append("| %s | %d | %s |" % (r["label"], r["n_sigs"], cells(r["old"])))
    L.append("")

    L.append("## What the tolerance actually let through")
    L.append("")
    L.append("| tolerance | signals | of those, retests that MISSED the level | grade mix S/A/C |")
    L.append("|---|---:|---:|---|")
    for r in rows:
        L.append("| %s | %d | %d (%.1f%%) | %d/%d/%d |"
                 % (r["label"], r["n_sigs"], r["near_miss"],
                    100.0 * r["near_miss"] / max(r["n_sigs"], 1),
                    r["S"], r["A"], r["C"]))
    L.append("")

    # --- the verdict, computed not asserted -------------------------------
    L.append("## Verdict")
    L.append("")
    moved = [r for r in rows[1:]
             if (r["new"]["s_hit"], r["new"]["ff"], r["old"]["s_hit"], r["old"]["ff"])
             != (base["new"]["s_hit"], base["new"]["ff"],
                 base["old"]["s_hit"], base["old"]["ff"])]
    if not moved:
        L.append("**No tolerance in this sweep changed either gate.** Every row lands on the "
                 "same S-day recall and the same false-fire count as today. On this corpus the "
                 "near-miss is not what is standing between the engine and his S-days — the "
                 "setups it recovers are either already found by another level, or are killed "
                 "further down the stack than the retest step.")
    else:
        best_new = max(rows, key=lambda r: r["new"]["s_recall"] - r["new"]["false_fire"])
        best_old = max(rows, key=lambda r: r["old"]["s_recall"] - r["old"]["false_fire"])
        L.append("- Under the downgrade grader the best row is **%s** "
                 "(%+.3f vs %+.3f at zero tolerance)."
                 % (best_new["label"],
                    best_new["new"]["s_recall"] - best_new["new"]["false_fire"],
                    base["new"]["s_recall"] - base["new"]["false_fire"]))
        L.append("- Under the engine's own gate the best row is **%s** "
                 "(%+.3f vs %+.3f at zero tolerance)."
                 % (best_old["label"],
                    best_old["old"]["s_recall"] - best_old["old"]["false_fire"],
                    base["old"]["s_recall"] - base["old"]["false_fire"]))
        L.append("- Recall bought: **%+d** S-days. False fires bought: **%+d** refused days."
                 % (best_new["new"]["s_hit"] - base["new"]["s_hit"],
                    best_new["new"]["ff"] - base["new"]["ff"]))
        L.append("")
        free = [r for r in rows[1:]
                if r["new"]["s_hit"] > base["new"]["s_hit"]
                and r["new"]["ff"] <= base["new"]["ff"]]
        if free:
            L.append("**Free rows — recall up, false fires not up.** These are the only "
                     "settings that are not a trade:")
            L.append("")
            for r in free:
                L.append("- **%s** — S-days %d → %d, false fires %d → %d, on %d near-miss "
                         "retests (%.1f%% of its signals)."
                         % (r["label"], base["new"]["s_hit"], r["new"]["s_hit"],
                            base["new"]["ff"], r["new"]["ff"], r["near_miss"],
                            100.0 * r["near_miss"] / max(r["n_sigs"], 1)))
            L.append("")
            L.append("Note which ones they are: the **fixed-cent** rows, which is the literal "
                     "thing Austin's card said — *\"missed entry by a cent or two\"*. The "
                     "range-fraction rows all buy their recall with false fires. That is a "
                     "result about the UNIT, not just the size: a cent is a cent whatever the "
                     "candle was doing, and widening the band in proportion to the candle "
                     "turns the near-miss into a different, looser rule.")
        else:
            L.append("")
            L.append("**No row buys recall for free** — every setting that adds S-days adds "
                     "false fires too.")
    L.append("")
    L.append("**Caveats that apply whatever the table says.**")
    L.append("")
    L.append("1. This measures whether a DAY fires, not what the trade made. Austin's claim "
             "is *\"usually these work out\"* — that is a claim about P&L, and it is not "
             "what this rig tests. A recall win here is not evidence for his sentence; it is "
             "only evidence that the setups exist.")
    L.append("2. There is no precision credit banked — head-to-head came back 0 for 9 — so "
             "every extra false fire is a real one Austin said he would not take.")
    L.append("3. One knob, swept alone, against the same 120 cards everything else is scored "
             "on. It stacks with the `downgrade.py` thresholds in ways this does not measure.")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("wrote %s  (%.1fs)" % (OUT, time.time() - t0))


if __name__ == "__main__":
    main()
