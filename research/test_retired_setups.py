"""RETIRED_SETUPS selftest (2026-08-24).

Austin, 2026-08-24: "I don't trade FVG or FLAG. Those are not setups
anymore." Detection stays on -- the historical numbers stay comparable --
only routing stops. TRADE_RETIRED_SETUPS=1 is the one-variable-away reversal.

The veto sits in SignalRunner._emit (not _route): _route is overridden by
BacktestRunner and the research replays, so a veto placed there would be
silently absent from exactly the runs that measure it. This test exercises
_emit directly, the same way test_no_repeat.py exercises _route directly.

    python research/test_retired_setups.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import signal_runner as sr                                     # noqa: E402
from signal_runner import SignalRunner                          # noqa: E402
from omen_bot import Candle, SignalType                         # noqa: E402

FAILURES = []


def check(cond, label):
    if cond:
        print("  ok    %s" % label)
    else:
        print("  FAIL  %s" % label)
        FAILURES.append(label)


def _bullish_candles(n=15):
    """Flat-ish bullish series, small ranges so a 5%-wide stop clears
    _min_viable_stop cleanly -- same shape as test_no_repeat.py."""
    bars = []
    for i in range(n):
        ts = f"09:{30 + i:02d}:00"
        bars.append(Candle(timestamp=ts, open=100.0, high=100.4,
                           low=99.9, close=100.1 + i * 0.01, volume=1000))
    return bars


def _sig(stype, level=95.0, direction="call"):
    """A B-grade signal that would otherwise be accepted by _route."""
    return {
        "signal_type": stype,
        "reason": "test signal",
        "entry": 100.0,
        "stop": level,
        "direction": direction,
        "grade": "B",
        "stop_level_name": "OR high",
        "stop_width_pct": 5.0,
    }


def _runner():
    r = SignalRunner(post_to_discord=False, symbol="TST", log_signals=True)
    r.candles = _bullish_candles()
    r._active_levels = []          # _grade_for_levels no-op
    r.htf_bias = None              # no HTF opposition
    r._bar_setups = {}             # normally seeded by detect_signals()
    return r


class _LogCapture:
    """Stands in for signal_tracker.log_signal so tests never touch the
    journal/ directory on disk."""

    def __init__(self):
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return kwargs


# ---------------------------------------------------------------------------
print("module constants")

check(sr.RETIRED_SETUPS == frozenset({SignalType.FAIR_VALUE_GAP, SignalType.FLAG}),
      "RETIRED_SETUPS is exactly {FAIR_VALUE_GAP, FLAG}")
check(sr.TRADE_RETIRED_SETUPS is False,
      "TRADE_RETIRED_SETUPS defaults off")

# ---------------------------------------------------------------------------
print("\n_emit skips retired setups")

for stype, label in ((SignalType.FAIR_VALUE_GAP, "FVG"), (SignalType.FLAG, "FLAG")):
    capture = _LogCapture()
    old_log = sr.log_signal
    sr.log_signal = capture
    try:
        r = _runner()
        signals = []
        r._emit(signals, _sig(stype))
        check(signals == [], "%s: never routes (signals list stays empty)" % label)
        check(len(capture.calls) == 1, "%s: still captured (one log call)" % label)
        if capture.calls:
            check(capture.calls[0]["status"] == "skipped",
                  "%s: logged status is skipped" % label)
            check(capture.calls[0]["skip_reason"] == "retired setup",
                  "%s: logged skip_reason is 'retired setup'" % label)
    finally:
        sr.log_signal = old_log

# ---------------------------------------------------------------------------
print("\n_emit does not affect live setups")

for stype, label in ((SignalType.BREAK_AND_RETEST, "BREAK_AND_RETEST"),
                      (SignalType.ONE_CANDLE_RULE, "ONE_CANDLE_RULE")):
    capture = _LogCapture()
    old_log = sr.log_signal
    sr.log_signal = capture
    try:
        r = _runner()
        signals = []
        r._emit(signals, _sig(stype))
        check(len(signals) == 1, "%s: still routes (fires normally)" % label)
        got_retired_skip = any(c.get("skip_reason") == "retired setup" for c in capture.calls)
        check(not got_retired_skip, "%s: never logged as a retired-setup skip" % label)
    finally:
        sr.log_signal = old_log

# ---------------------------------------------------------------------------
print("\nTRADE_RETIRED_SETUPS=1 restores routing")

old_flag = sr.TRADE_RETIRED_SETUPS
try:
    sr.TRADE_RETIRED_SETUPS = True
    for stype, label in ((SignalType.FAIR_VALUE_GAP, "FVG"), (SignalType.FLAG, "FLAG")):
        capture = _LogCapture()
        old_log = sr.log_signal
        sr.log_signal = capture
        try:
            r = _runner()
            signals = []
            r._emit(signals, _sig(stype))
            check(len(signals) == 1,
                  "%s: TRADE_RETIRED_SETUPS=1 routes it through" % label)
        finally:
            sr.log_signal = old_log
finally:
    sr.TRADE_RETIRED_SETUPS = old_flag
check(sr.TRADE_RETIRED_SETUPS is old_flag, "the flag was restored after the A/B")

# ---------------------------------------------------------------------------
print("\ndetection counts are identical either way")

# Retiring a setup only changes its DISPOSITION (fired vs skipped), never
# whether it was detected at all. So the same _emit() call must be accounted
# for exactly once -- either routed (appended to signals) or captured
# (logged skipped) -- and that total must not move when the flag flips.
for stype, label in ((SignalType.FAIR_VALUE_GAP, "FVG"), (SignalType.FLAG, "FLAG")):
    handled = {}
    for flag in (False, True):
        old_flag = sr.TRADE_RETIRED_SETUPS
        sr.TRADE_RETIRED_SETUPS = flag
        capture = _LogCapture()
        old_log = sr.log_signal
        sr.log_signal = capture
        try:
            r = _runner()
            signals = []
            r._emit(signals, _sig(stype))
            skipped_retired = any(c.get("skip_reason") == "retired setup" for c in capture.calls)
            handled[flag] = len(signals) + (1 if skipped_retired else 0)
        finally:
            sr.log_signal = old_log
            sr.TRADE_RETIRED_SETUPS = old_flag
    check(handled[False] == handled[True] == 1,
          "%s: detection count (fired + skipped) is 1 whether traded or not" % label)

print()
if FAILURES:
    print("RETIRED SETUPS SELFTEST FAILED: %d check(s)" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("retired setups selftest ok")
