"""W12 selftest: the grade-and-gate path's six regression guards.

One assert per finding in `research/w12_bug_sweep.md`. No framework, synthetic
bars only, no archive. Run:

    python research/test_w12_grade_gates.py

Two of these guard a bug that is FIXED and must stay fixed. Four guard a
DEFECT THAT IS STILL SHIPPED on purpose -- it changes which trade is taken, so
it is Austin's call, and the test pins the current behaviour so that when the
S/A/C ladder lands the failure is loud instead of silent. A failing test here
after the ladder change is not a bug in the test: it is the decision arriving.
"""
from __future__ import annotations

import inspect
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from research import downgrade as dg                       # noqa: E402
import omen_bot                                            # noqa: E402
import signal_runner as sr                                 # noqa: E402
import backtest_week as bw                                 # noqa: E402

FAILURES: list = []


def check(name: str, fn) -> None:
    try:
        fn()
    except AssertionError as e:
        FAILURES.append("%s: %s" % (name, e))
        print("FAIL  %s\n      %s" % (name, e))
    else:
        print("ok    %s" % name)


def _bar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


# ---------------------------------------------------------------------------
# W12-1  break_then_rejection is unsatisfiable when the graded bar closes
#        beyond the level -- which is 45,039 of the 45,193 rows of the 2-year
#        book (research/w12_dg_probe.py). FLAGGED, still shipped.
# ---------------------------------------------------------------------------

def _break_give_back_bars():
    """Broke at bar 2, gave it back at bar 3, reclaimed at bar 5, entry at 6.

    This is exactly the shape `break_then_rejection`'s docstring describes --
    "it broke, then immediately gave it back" -- on a bar the engine would
    grade, because a B&R long only fires with the close above the level."""
    lv = 100.0
    return lv, [
        _bar(99.0, 99.5, 98.5, 99.0),     # 0  below
        _bar(99.0, 99.6, 98.6, 99.2),     # 1  below
        _bar(99.2, 101.0, 99.1, 100.8),   # 2  BREAK (close through)
        _bar(100.8, 101.0, 98.9, 99.1),   # 3  gave it straight back
        _bar(99.1, 99.8, 98.8, 99.4),     # 4  still below
        _bar(99.4, 101.2, 99.3, 100.9),   # 5  reclaimed
        _bar(100.9, 101.6, 100.4, 101.3),  # 6  entry bar, closes beyond
    ]


def w12_1_break_then_rejection_cannot_fire():
    lv, bars = _break_give_back_bars()
    i = len(bars) - 1
    assert bars[i]["c"] > lv, "fixture must close beyond the level"
    assert dg._break_bar(bars, i, lv, True) == 5, (
        "_break_bar must return the MOST RECENT cross; it returned %r"
        % dg._break_bar(bars, i, lv, True))
    assert dg.break_then_rejection(bars, i, lv, True) is False, (
        "break_then_rejection FIRED on the give-back fixture -- if this is "
        "deliberate the ladder just gained a ninth live variable and "
        "research/w12_bug_sweep.md finding 1 must be re-priced")


# ---------------------------------------------------------------------------
# W12-2  find_ocr's `j + 1 > i` guard: 0 hits in 853,010 evaluations over
#        the 2-year book, dead by construction. FIXED (deleted).
# ---------------------------------------------------------------------------

def w12_2_find_ocr_has_no_dead_guard():
    src = inspect.getsource(dg.find_ocr)
    assert "j + 1 > i" not in src, (
        "the `if j + 1 > i: continue` guard is back in find_ocr. The loop "
        "starts at j = i - 1, so j + 1 <= i always and the guard cannot be "
        "true -- 0 hits in 853,010 evaluations (research/w12_dg_probe.py)")
    # and the function still finds the isolated counter candle it always did
    bars = [_bar(10, 10.5, 9.9, 10.4),    # 0 up
            _bar(10.4, 10.9, 10.3, 10.8),  # 1 up
            _bar(10.8, 10.9, 10.2, 10.3),  # 2 DOWN, isolated
            _bar(10.3, 10.8, 10.2, 10.7),  # 3 up
            _bar(10.7, 11.2, 10.6, 11.1)]  # 4 up
    assert dg.find_ocr(bars, 4, True) == 2, dg.find_ocr(bars, 4, True)


# ---------------------------------------------------------------------------
# W12-3  HTF_BIAS_VETO ships ON. The record said OFF in four places; the
#        docstring on the function that READS it is now corrected. FIXED.
# ---------------------------------------------------------------------------

def w12_3_htf_veto_doc_matches_code():
    doc = omen_bot.PriceActionAnalyzer.grade_trade.__doc__ or ""
    assert "default 0" not in doc, (
        "grade_trade's docstring says HTF_BIAS_VETO defaults to 0; "
        "omen_bot.py's module comment and the code both ship it ON")
    default = os.getenv("HTF_BIAS_VETO")
    if default is None:
        assert omen_bot.HTF_BIAS_VETO is True, (
            "HTF_BIAS_VETO's shipped default changed. It gates 21,257 of "
            "45,193 signals (47.0%%) of the 2-year book -- that is a decision, "
            "not a tidy-up")


# ---------------------------------------------------------------------------
# W12-4  `C` is tradeable in the 2026-08-28 ladder (master spec 1.2) and is
#        excluded from the traded book by SimTrade.counted. 377 fired-C rows,
#        mean +0.4487R, are booked as alerts. FLAGGED, still shipped.
# ---------------------------------------------------------------------------

def _simtrade(grade: str) -> bw.SimTrade:
    return bw.SimTrade(symbol="TEST", day="2026-01-02",
                       signal_type=sr.SignalType.BREAK_AND_RETEST.value,
                       direction="call", grade=grade, status="fired",
                       entry_time="09:45:00", entry=100.0, stop=99.0,
                       target=102.0, outcome="loss", exit_price=99.0)


def w12_4_c_grade_is_still_alert_only():
    assert _simtrade("C").counted is False, (
        "C now counts toward the traded book. Master spec 1.2 says it should "
        "-- but every 2-year number in the repo was measured with C excluded, "
        "so re-run the book before quoting one (research/w12_bug_sweep.md #2)")
    assert _simtrade("C").is_alert is True
    assert _simtrade("A").counted is True


# ---------------------------------------------------------------------------
# W12-5  The 84%-rule arm gate reads the LEGACY ladder (A+/A). The shipped
#        grader produces 17 A+/A rows in 45,193 signals, of which 7 are
#        arm-eligible stop-outs, and the rule fires 3 times in two years.
#        FLAGGED, still shipped.
# ---------------------------------------------------------------------------

class _FakeSession:
    entry_price = None
    entry_direction = None
    entry_target = None
    entry_stop = None


class _FakeRunner:
    def __init__(self):
        self.session = _FakeSession()
        self.candles = []
        self.htf_bias = None


def w12_5_arm84_gate_is_keyed_to_the_legacy_ladder():
    if not sr.RULE84_STRICT:
        return                       # gate deliberately lifted in this process
    for grade, want_armed in (("B", False), ("C", False), ("A", True)):
        r = _FakeRunner()
        bw._arm_84(_simtrade(grade), r, None)
        got = r.session.entry_price is not None
        assert got is want_armed, (
            "grade %s armed=%s, expected %s. The arm gate is `t.counted and "
            "t.grade in ('A+','A')`; killing B moves 1,000 of the 1,017 traded "
            "rows across it and takes the arm population from 7 to 156 "
            "(research/w12_bug_sweep.md #3)" % (grade, got, want_armed))


# ---------------------------------------------------------------------------
# W12-6  The minimum-viable-stop gate is consulted on ONE grade, `C`, and its
#        sign is backwards: over the 1,017 traded rows of the 2-year book it
#        rejects 732 worth mean +1.0861R and keeps 285 worth mean +0.6188R
#        (research/w12_tight_stop.py). Killing `B` sends 331 rows into `C` and
#        247 of them into this gate. FLAGGED, still shipped.
# ---------------------------------------------------------------------------

def w12_6_tight_stop_gate_is_c_only_and_still_backwards():
    src = inspect.getsource(sr.SignalRunner._route)
    assert 'sig["grade"] != "C" or self._min_viable_stop(' in src, (
        "the tight-stop gate is no longer keyed to grade C. Whatever it is "
        "keyed to now, re-price it: on the 2-year book the rows it REJECTS "
        "earn +1.0861R mean and the rows it keeps earn +0.6188R "
        "(research/w12_tight_stop.py)")
    r = sr.SignalRunner(post_to_discord=False, log_signals=False, symbol="TEST")
    # ten $1.00-range bars, then a stop $0.10 wide: 0.10 < 0.75 x 1.00
    r.candles = [omen_bot.Candle(timestamp="09:%02d:00" % (31 + k), open=100.0,
                                 high=100.5, low=99.5, close=100.0, volume=1000)
                 for k in range(11)]
    assert r._min_viable_stop(100.0, 99.90, "call") is False, (
        "STOP_RANGE_MULT=%s no longer rejects a stop inside one typical "
        "candle's range" % sr.STOP_RANGE_MULT)
    # a stop wider than the bar range, and >= 0.5% of entry, is viable
    assert r._min_viable_stop(100.0, 98.50, "call") is True


def main():
    check("W12-1 break_then_rejection cannot fire", w12_1_break_then_rejection_cannot_fire)
    check("W12-2 find_ocr has no dead guard", w12_2_find_ocr_has_no_dead_guard)
    check("W12-3 HTF_BIAS_VETO doc matches code", w12_3_htf_veto_doc_matches_code)
    check("W12-4 C grade is still alert-only", w12_4_c_grade_is_still_alert_only)
    check("W12-5 arm84 gate keyed to legacy ladder",
          w12_5_arm84_gate_is_keyed_to_the_legacy_ladder)
    check("W12-6 tight-stop gate is C-only and backwards",
          w12_6_tight_stop_gate_is_c_only_and_still_backwards)
    print()
    if FAILURES:
        print("W12 GRADE-GATE SELFTEST FAILED: %d of 6" % len(FAILURES))
        sys.exit(1)
    print("w12 grade-gate selftest ok: 6 checks")


if __name__ == "__main__":
    main()
