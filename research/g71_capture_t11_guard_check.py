"""G7.1 / track `capture` -- prove the proposed t11 guard fix, without editing it.

`research/t11_stop_fill_fix.py` exits 1 at HEAD (12 of 64 checks). Cause: the
R1/R2 disaster stop (`68e276ca`) ships ON at DISASTER_STOP_R = 1.0, and for
BNR_STOP_MODE="level" it rests at exactly the level stop's price and fills on an
intrabar TOUCH -- so the level stop's close-fill and the -1.25R floor became
unobservable and a wick alone ends the trade.

This script runs the guard's own module with `backtest_week.DISASTER_STOP`
forced OFF, which is what the proposed diff does inside `run()`, and separately
asserts the shipped default's behaviour (proposed new section 6).

Usage:  python research/g71_capture_t11_guard_check.py
"""
from __future__ import annotations
import os, runpy, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import backtest_week as bw   # noqa: E402


def part_a():
    """Sections 1-6 of the guard with the disaster stop off == the proposed fix."""
    print("== A: t11_stop_fill_fix.py with backtest_week.DISASTER_STOP = False ==")
    bw.DISASTER_STOP = False
    try:
        runpy.run_path(os.path.join(HERE, "t11_stop_fill_fix.py"),
                       run_name="__main__")
    except SystemExit as e:
        print("guard exit code:", e.code)
        return e.code
    return 0


def part_b():
    """Proposed new section: the SHIPPED default, asserted rather than ignored."""
    print("\n== B: shipped default (DISASTER_STOP=1, DISASTER_STOP_R=1.0) ==")
    import importlib
    t11 = importlib.import_module("t11_stop_fill_fix")
    bw.DISASTER_STOP = True
    fails = []

    def close_to(got, want, msg, eps=1e-4):
        ok = abs(got - want) < eps
        print(("  PASS  " if ok else "  FAIL  ") + msg
              + "  (got %+.4fR, want %+.4fR)" % (got, want))
        if not ok:
            fails.append(msg)

    def check(cond, msg):
        print(("  PASS  " if cond else "  FAIL  ") + msg)
        if not cond:
            fails.append(msg)

    for label, mk_day in (("long", t11.long_day), ("short", t11.short_day)):
        t = t11.only(t11.run(mk_day(t11.crater(15, 1.6))))
        close_to(t.pnl / bw.RISK_DOLLARS, -1.0,
                 "%s: the resting -1R order takes the bar that closes 1.6R past"
                 % label)
        t = t11.only(t11.run(mk_day(t11.crater(15, 1.1))))
        close_to(t.pnl / bw.RISK_DOLLARS, -1.0,
                 "%s: and the bar that closes 1.1R past" % label)
        t = t11.only(t11.run(mk_day(t11.wick_only(15))))
        check(t.outcome == "loss" and t.exit_idx == 15,
              "%s: a WICK alone ends the trade at the shipped default -- the "
              "level stop's close rule is unobservable below -1R "
              "(outcome=%s, exit_idx=%d)" % (label, t.outcome, t.exit_idx))
    return fails


if __name__ == "__main__":
    rc = part_a()
    fails = part_b()
    print("\nA (level-stop convention, disaster off) exit:", rc)
    print("B (shipped default) failures:", fails or "none")
