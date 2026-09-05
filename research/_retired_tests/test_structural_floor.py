"""G13 -- the minimum-risk floor reads PRE-fill geometry on, POST-fill off.

`signal_runner.ENABLE_STRUCTURAL_RISK_FLOOR` (default False) changes exactly one
thing: which risk the minimum-risk floor at `signal_runner.py:1657` / `:1892` is
compared against. Everything else -- the price paid, the R denominator, the
selection score -- keeps reading the post-fill number. This asserts both halves
of that sentence.

Not a framework: plain asserts, exits non-zero on failure, same shape as
`research/test_sample_floor.py`.

    python research/test_structural_floor.py

Two legs, because either alone would be a lie:

  1. the pure function, on the REAL numbers `research/g12_recall_regression.md`
     tabulated for two of the six dropped marks -- one long, one short.
  2. the CALL SITES, end to end, through the same `t4_engine_recall.run_day`
     replay `research/regression_gate.py` runs. Leg 1 alone would still pass if
     `floor_reference_risk` were never wired into `detect_signals`.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr          # noqa: E402
import t4_engine_recall as t4       # noqa: E402

# `GOOGL|2024-10-15|32`, the first row of g12_recall_regression.md §4. A long
# break-and-retest: the fill moved 166.825 -> 166.515 (the bar's own low, a
# SQUEEZE `intrabar_stop` cannot see), the stop stayed on the broken level, and
# the risk fell 0.425 -> 0.115 through a floor of max(0.10, 0.0015*166.825).
LONG = dict(entry=166.515, stop=166.40, close=166.825, structural_stop=166.40,
            is_long=True, floor=max(0.10, 0.0015 * 166.825))
# `QQQ|2025-02-25|16`, same table. The short mirror: 516.65 -> 517.26, stop
# 517.75, risk 1.10 -> 0.49 against a floor of max(0.10, 0.0015*516.65).
SHORT = dict(entry=517.26, stop=517.75, close=516.65, structural_stop=517.75,
             is_long=False, floor=max(0.10, 0.0015 * 516.65))

# The end-to-end probe: LONG's own symbol-day, and the bar Austin marked.
DAY = ("GOOGL", "2024-10-15", 32)


def risk(row):
    return sr.floor_reference_risk(row["entry"], row["stop"], row["close"],
                                   row["structural_stop"], row["is_long"])


def fired_near(sym, day, bar):
    """Did the engine take an entry within t4.TOL bars of `bar`? The gate's own
    join, through the gate's own replay."""
    ent, _sigs, _raw = t4.run_day(sym, day)
    assert ent is not None, (
        "no archived bars for %s %s -- data_archive/ is required to run this "
        "check; it cannot be answered from code alone" % (sym, day))
    return sorted({e["bar"] for e in ent if abs(e["bar"] - bar) <= t4.TOL})


def main():
    assert sr.ENABLE_STRUCTURAL_RISK_FLOOR is False, (
        "the shipped default must be False -- flipping it changes what trades "
        "and re-freezing the engine voids research/omen6_forward.py")

    was = sr.ENABLE_STRUCTURAL_RISK_FLOOR
    try:
        # ---- leg 1: the pure function ------------------------------------
        sr.ENABLE_STRUCTURAL_RISK_FLOOR = False
        off_l, off_s = risk(LONG), risk(SHORT)
        # POST-fill, and float-IDENTICAL to the `stock_risk` the call sites
        # compute -- the same subtraction of the same two floats. This is the
        # whole byte-identity claim, stated as an assert.
        assert off_l == LONG["entry"] - LONG["stop"], off_l
        assert off_s == SHORT["stop"] - SHORT["entry"], off_s
        assert off_l < LONG["floor"], (
            "off-arm long risk %.4f should be UNDER its floor %.4f -- that is "
            "why the mark is dropped at HEAD" % (off_l, LONG["floor"]))
        assert off_s < SHORT["floor"], (off_s, SHORT["floor"])

        sr.ENABLE_STRUCTURAL_RISK_FLOOR = True
        on_l, on_s = risk(LONG), risk(SHORT)
        # PRE-fill: the bar CLOSE against the structural stop, not the fill.
        assert on_l == LONG["close"] - LONG["structural_stop"], on_l
        assert on_s == SHORT["structural_stop"] - SHORT["close"], on_s
        assert on_l >= LONG["floor"], (
            "on-arm long risk %.4f should CLEAR its floor %.4f" % (on_l, LONG["floor"]))
        assert on_s >= SHORT["floor"], (on_s, SHORT["floor"])
        # and the two arms must actually disagree, or the flag is inert
        assert on_l > off_l and on_s > off_s

        # ---- leg 2: the call sites, end to end ---------------------------
        sym, day, bar = DAY
        sr.ENABLE_STRUCTURAL_RISK_FLOOR = False
        silent = fired_near(sym, day, bar)
        sr.ENABLE_STRUCTURAL_RISK_FLOOR = True
        heard = fired_near(sym, day, bar)
        assert silent == [], (
            "%s %s bar %d should be SILENT with the flag off (it is one of "
            "g12's six dropped marks); got %s" % (sym, day, bar, silent))
        assert bar in heard, (
            "%s %s bar %d should FIRE with the flag on -- if it does not, "
            "floor_reference_risk is not wired into the B&R call sites; got %s"
            % (sym, day, bar, heard))
    finally:
        sr.ENABLE_STRUCTURAL_RISK_FLOOR = was

    print("structural floor ok: off -> post-fill risk (long %.4f, short %.4f), "
          "on -> pre-fill risk (long %.4f, short %.4f); %s %s bar %d silent "
          "off / fires on" % (off_l, off_s, on_l, on_s, DAY[0], DAY[1], DAY[2]))


if __name__ == "__main__":
    main()
