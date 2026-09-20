"""B3 B-07: `_min_viable_stop` estimated premium risk with a hardcoded 0.5
delta while `options_sizer.DEFAULT_DELTA` is 0.42. Failing input from the
ticket: entry=100.00, stop=99.58 (stock_risk=0.42, risk_pct=0.0042 < the
0.005 arm). At 0.5, premium_risk = $0.21 >= $0.20 -> viable (wrong, admits
the signal). At the measured 0.42, premium_risk = $0.1764 < $0.20 -> not
viable (correct, gate rejects it).

Run: python research/test_min_viable_stop_delta.py

Confirmed but NOT fixed: commit 8a2def5b (2026-09-05) "B3 B-07:
_min_viable_stop's hardcoded 0.5 delta confirmed, deferred (moves live fire
counts on the 159-mark corpus)". Changing `_min_viable_stop` is a trading-
logic change to the fire gate, not a test-only fix -- SWARM.md's law 2
requires it to clear the regression gate (green months unchanged, $/day
within 5%, both halves) before it ships as a default. Left `xfail` here,
tracked, rather than silently fixed or deleted, until that measurement
lands.
"""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from signal_runner import SignalRunner
from options_sizer import DEFAULT_DELTA


@pytest.mark.xfail(
    reason="B3 B-07 (commit 8a2def5b): fix confirmed but deferred -- moves "
           "live fire counts, ships only through SWARM.md law 2's "
           "regression gate, not as a standalone test fix.",
    strict=False,
)
def test_min_viable_stop_uses_default_delta_not_hardcoded_half():
    assert DEFAULT_DELTA == 0.42, "ticket assumes options_sizer.DEFAULT_DELTA == 0.42"
    runner = SignalRunner(post_to_discord=False, symbol="TEST", log_signals=False)
    runner.candles = []  # empty -> the STOP_RANGE_MULT human-proof guard no-ops

    entry, stop = 100.00, 99.58
    stock_risk = abs(entry - stop)
    assert abs(stock_risk - 0.42) < 1e-9
    risk_pct = stock_risk / entry
    assert risk_pct < 0.005, "risk_pct must be below the 0.005 arm for this to test the premium branch"

    result = runner._min_viable_stop(entry, stop, "long")

    # At the correct 0.42 delta: premium_risk = 0.42 * 0.42 = 0.1764 < 0.20 -> False.
    # The bug (hardcoded 0.5) computed 0.42 * 0.5 = 0.21 >= 0.20 -> True.
    assert result is False, (
        "expected the gate to REJECT this signal (premium_risk=$0.1764 < $0.20 "
        "at the measured 0.42 delta); got True, meaning the hardcoded 0.5 "
        "estimate is still in use"
    )


if __name__ == "__main__":
    test_min_viable_stop_uses_default_delta_not_hardcoded_half()
    print("PASS: research/test_min_viable_stop_delta.py")
