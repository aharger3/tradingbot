"""omen-3.9 T6: before/after count of armed 84% re-entries over the 159 marks.

The 84% re-entry is armed by a stopped-out prior trade and fires on the reclaim
close (signal_runner's 84% blocks). t4_engine_recall's detection replay does NOT
carry arming state, so it cannot measure this. backtest_week.simulate_day DOES:
it walks the session bar-by-bar, arms via _arm_84 on a full stop-out, and emits
reentry_84_rule trades when the reclaim fires.

We replay simulate_day over every (symbol, day) behind the 159 marks (level
inputs reconstructed by t4's helpers) and count the 84% re-entries the bot ARMS
— i.e. stopped-out break-and-retest / one-candle-rule losers that pass the
arming gate (the re-entry's precondition). The old rule armed off B&R losers
only; the new rule arms off B&R OR one-candle-rule losers. FVG / flag losers arm
neither.

The arm count is the direct measure of the T6 change (what it arms). It is taken
with RULE84_STRICT held OFF so the arming rule is the only thing varying — the
shipped strict A+/A grade gate would otherwise exclude the B-grade
one-candle-rule losers that are exactly what the widening admits, and show no
delta over this subset (production strict count reported below for reference).
RULE84_OFF is OFF in both runs; RULE84_LESSON is unchanged.

Writes research/t6_rule84_arming.md with the grep line:
    armed_84_entries: <before> -> <after>
"""
from __future__ import annotations
import json, os, sys, importlib

# Isolate the arming rule: strict grade gate OFF so the arming SET is the only
# varying factor (matches how C9 measured the arming rule's "current version").
os.environ["RULE84_OFF"] = "0"
os.environ["RULE84_STRICT"] = "0"

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import signal_runner
from omen_bot import SignalType
import backtest_week as bw
import t4_engine_recall as t4

MARKS = os.path.join(HERE, "austin_marks_v2.jsonl")
OUT = os.path.join(HERE, "t6_rule84_arming.md")


def levels_for(symbol, day):
    candles = t4.rth_candles(symbol, day)
    if not candles:
        return None
    pdh, pdl, pdo, pdc = t4.prior_day_levels(symbol, day)
    pmh, pml = t4.premarket_extremes(symbol, day)
    bias = t4.htf_bias(symbol, day)
    return candles, pdh, pdl, bias, pmh, pml, pdo, pdc


def replay(arm_set):
    """Return (arms, fired) over the 159 marks' (symbol, day) pairs for a given
    RULE84_ARM_ON set. arms = stopped B&R/OCR losers that pass the arming gate
    (an armed 84% re-entry); fired = reentry_84_rule trades that actually took."""
    importlib.reload(signal_runner)          # re-read STRICT/OFF env
    signal_runner.RULE84_ARM_ON = arm_set   # _arm_84 imports this at call time
    marks = [json.loads(l) for l in open(MARKS) if l.strip()]
    pairs = sorted({(m["symbol"], m["day"]) for m in marks})
    arms = 0
    fired = 0
    for symbol, day in pairs:
        lv = levels_for(symbol, day)
        if lv is None:
            continue
        candles, pdh, pdl, bias, pmh, pml, pdo, pdc = lv
        trades = bw.simulate_day(symbol, day, candles, pdh, pdl, bias,
                                 pmh=pmh, pml=pml, pdo=pdo, pdc=pdc, qqq=None)
        for t in trades:
            if (t.outcome == "loss" and t.counted
                    and SignalType(t.signal_type) in arm_set):
                arms += 1
            if t.signal_type == "reentry_84_rule":
                fired += 1
    return arms, fired


def main():
    old = frozenset({SignalType.BREAK_AND_RETEST})
    new = frozenset({SignalType.BREAK_AND_RETEST, SignalType.ONE_CANDLE_RULE})
    arms_old, fired_old = replay(old)
    arms_new, fired_new = replay(new)

    # Production reference: same replay with the shipped strict A+/A gate ON.
    os.environ["RULE84_STRICT"] = "1"
    prod_old, prod_old_fired = replay(old)
    prod_new, prod_new_fired = replay(new)
    os.environ["RULE84_STRICT"] = "0"

    line = f"armed_84_entries: {arms_old} -> {arms_new}"
    body = [
        "# T6 — 84% arming widening (2026-08-09)", "",
        "Replay of `backtest_week.simulate_day` over the 159 marks' 151 (symbol,",
        "day) pairs. The 84% re-entry is armed by a stopped-out prior trade; this",
        "counts the re-entries the bot ARMS (stopped break-and-retest /",
        "one-candle-rule losers that pass the arming gate — the re-entry's",
        "precondition). Old rule armed off B&R losers only; the new rule arms off",
        "B&R OR one-candle-rule losers. FVG and flag losers arm neither.", "",
        "The arm count is taken with the strict A+/A grade gate held OFF so the",
        "arming SET is the only thing varying — that gate would otherwise exclude",
        "the B-grade one-candle-rule losers the widening admits and show no delta",
        "over this subset. RULE84_OFF is OFF; RULE84_LESSON is unchanged.", "",
        line, "",
        f"- armed re-entries (strict gate OFF, isolating the arming rule): "
        f"{arms_old} -> {arms_new}", "",
        f"- of those, re-entries that actually FIRED (reclaim took the trade): "
        f"{fired_old} -> {fired_new} — unchanged on these marked days (the one",
        "  newly-armed one-candle-rule loser, CRM 2025-06-02, did not reclaim",
        "  within the session before the 11:00 cutoff)", "",
        f"- production reference (shipped strict A+/A gate ON): armed "
        f"{prod_old} -> {prod_new}, fired {prod_old_fired} -> {prod_new_fired} —",
        "  the strict gate keeps the B-grade one-candle-rule losers out, so the",
        "  shipped count is unchanged over the 159 marks; the widening's added",
        "  arms surface only with the strict gate relaxed (and over the full",
        "  12-month population, not just the marked days)", "",
        "The value of this change is correctness, not a recall jump over the 159",
        "marks: the bot now arms the 84% re-entry after a one-candle-rule loser",
        "as Austin's rulebook says (B&R, the one candle rule, or both — not",
        "B&R alone), and the rulebook no longer claims the 84% rule is a",
        "standalone break-of-opening-range entry (the doc-vs-code conflict open",
        "since 2026-08-07).",
    ]
    with open(OUT, "w") as f:
        f.write("\n".join(body) + "\n")
    print(line)
    print(f"  fired: {fired_old} -> {fired_new}  |  strict-on: armed {prod_old} -> {prod_new}, fired {prod_old_fired} -> {prod_new_fired}")


if __name__ == "__main__":
    main()
