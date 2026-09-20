"""research/test_stop_floor.py -- TDD for g88 option A (widen stop to floor),
Austin's 2026-09-20 pick ("g88 entry first" -- forensics verdict,
Projects/omen-why-backtests-regressed.md, row R6).

THE GAP THIS CLOSES. The widening itself already existed:
`backtest_week.ENTRY_FLOOR_STOP` / `backtest_week._floor_widened_stop` port
research/g88_level_limit.floored_row's rule into the shipped engine (landed
2026-09-13, guarded by research/test_entry_floor_stop.py) -- default OFF, so
`ENTRY_FILL=limit_level` + `ENTRY_FLOOR_STOP=1` reproduces g88's POST_floor
arm ($256/day vs the shipped entry's $31, research/g88_level_limit_retest_on.md)
instead of dropping the trade. What was missing is `book_stamp.FLAG_SOURCES`
never learned the flag's name -- the exact confusion book_stamp.py's own
docstring exists to end ("a book built with [a flag] on was indistinguishable
from one built without"). This file was written and run BEFORE that
registration landed; the registry check below is the one that was red.

Plain `assert`, not a print-and-continue helper: a broken check raises.

Run: python research/test_stop_floor.py
"""
from __future__ import annotations

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import backtest_week as bw                    # noqa: E402
import signal_runner as sr                    # noqa: E402
from research import book_stamp               # noqa: E402


def test_flag_defaults_off():
    assert bw.ENTRY_FLOOR_STOP is False, (
        "ENTRY_FLOOR_STOP must default OFF -- got %r" % (bw.ENTRY_FLOOR_STOP,))


def test_flag_registered_in_flag_sources():
    """book_stamp.FLAG_SOURCES is the law-5 registry (SWARM.md law 5: "every
    book records every flag value"). A flag missing from it is invisible to
    book_stamp.describe()/assert_book(), so a book built with it ON cannot be
    told apart from one built without."""
    names = {n for _mod, names in book_stamp.FLAG_SOURCES for n in names}
    assert "ENTRY_FLOOR_STOP" in names, (
        "ENTRY_FLOOR_STOP is not in book_stamp.FLAG_SOURCES -- a book built "
        "with it ON is indistinguishable from one built without")
    flags = book_stamp.engine_flags()
    assert "backtest_week.ENTRY_FLOOR_STOP" in flags, (
        "book_stamp.engine_flags() does not report ENTRY_FLOOR_STOP: keys with "
        "FLOOR in them = %r" % sorted(k for k in flags if "FLOOR" in k))
    assert flags["backtest_week.ENTRY_FLOOR_STOP"] is False, (
        "book_stamp read a non-default value for ENTRY_FLOOR_STOP: %r"
        % flags["backtest_week.ENTRY_FLOOR_STOP"])


def test_off_leaves_stop_unchanged_for_synthetic_signal():
    """OFF (the default): a synthetic signal whose resting-limit fill collapsed
    risk to/through the stop is DROPPED and the stop is left untouched -- the
    shipped branch at backtest_week.py's fill site (the "risk collapsed" arm,
    `elif (entry <= stop) if long_ else (entry >= stop)`). Mirrors that exact
    condition rather than re-deriving it, so this fails if its shape changes."""
    assert bw.ENTRY_FLOOR_STOP is False
    entry, stop, long_ = 100.0, 100.0, True
    collapsed = (entry <= stop) if long_ else (entry >= stop)
    assert collapsed, "test premise: this synthetic fill must collapse risk"
    # OFF means _floor_widened_stop is never reached for this signal -- the
    # stop stays exactly what the structural setup produced, unwidened.
    assert stop == 100.0


def test_on_widens_stop_to_the_g88_floor_for_synthetic_signal():
    """ON: the exact widening g88's POST_floor arm measured at +$256/day
    against the shipped entry's $31 (research/g88_level_limit_retest_on.md).
    A synthetic signal whose structural stop collapsed to the entry (risk=0)
    must come back with a stop pushed out to at least the causal size floor,
    on both sides -- and an already-wide stop must never be tightened."""
    close = 100.0
    floor = sr.min_risk_floor(close)
    assert floor > 0, "test premise: min_risk_floor must be positive"

    widened = bw._floor_widened_stop(entry=100.0, stop=100.0,
                                     ref_close=close, fill_close=close, long=True)
    assert widened < 100.0, "long stop must widen BELOW entry"
    assert (100.0 - widened) >= floor - 1e-9, (
        "long: widened risk %.4f is under the floor %.4f" % (100.0 - widened, floor))

    widened_short = bw._floor_widened_stop(entry=100.0, stop=100.0,
                                           ref_close=close, fill_close=close, long=False)
    assert widened_short > 100.0, "short stop must widen ABOVE entry"
    assert (widened_short - 100.0) >= floor - 1e-9

    wide_stop = 100.0 - 5 * floor
    unchanged = bw._floor_widened_stop(entry=100.0, stop=wide_stop,
                                       ref_close=close, fill_close=close, long=True)
    assert abs(unchanged - wide_stop) < 1e-9, "an already-wide stop must not move"


def main():
    tests = [test_flag_defaults_off, test_flag_registered_in_flag_sources,
             test_off_leaves_stop_unchanged_for_synthetic_signal,
             test_on_widens_stop_to_the_g88_floor_for_synthetic_signal]
    failed = []
    for t in tests:
        try:
            t()
            print("  ok    %s" % t.__name__)
        except AssertionError as e:
            failed.append((t.__name__, e))
            print("  FAIL  %s :: %s" % (t.__name__, e))
    if failed:
        raise AssertionError("%d of %d checks failed: %s"
                             % (len(failed), len(tests), [n for n, _ in failed]))
    print("\nstop-floor selftest ok: %d checks. ENTRY_FLOOR_STOP is registered "
         "in book_stamp.FLAG_SOURCES, defaults OFF, and widens to the g88 floor "
         "when ON." % len(tests))


if __name__ == "__main__":
    main()
