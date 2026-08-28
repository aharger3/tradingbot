"""T4/G14 internal helper -- never imported, only invoked as a subprocess.

Installs a parameterised replacement for `SignalRunner._calibration_grade`'s
first-with-trend-signal-of-the-day floor (`signal_runner.py:1516-1520`), then
runs the SHIPPED `backtest_2y.main()` unmodified. This lets T4 sweep the
floor's three conditions (count, trend, window) one at a time to find which
is load-bearing, WITHOUT adding a new flag to `signal_runner.py` -- the patch
lives in this process's memory only and `signal_runner.py` is never edited.
The shipped ON/OFF arms of the primary A/B do NOT use this file; they use the
real `ENABLE_KILL_B_FLOOR` flag that already ships in `signal_runner.py`.

Usage (always via `research/t4_g14_calibration_ab.py`, never directly):

    T4_SEQ_UNCAP=1 python research/_t4_variant_wrapper.py --days 730 --out X

Env config, each independently defaulted to the SHIPPED floor's own value so
a variant run with nothing set reproduces the shipped floor:

    T4_TREND_REQ   "1" (default, shipped) require with_trend to promote;
                   "0" drop the requirement -- a counter-trend C can promote
    T4_SEQ_UNCAP   "0" (default, shipped) only the FIRST eligible C per
                   direction promotes; "1" every eligible C in the direction
                   promotes, not just the first
    T4_WINDOW_MIN  "90" (default, shipped); "none" removes the 0-90 minute
                   cap entirely

Every promoted row's reason tag records the exact config it ran under, so a
downstream reader can tell a variant row from a shipped-floor row by string
alone, and the four numbers are always visible together.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import signal_runner as sr  # noqa: E402

TREND_REQ = os.environ.get("T4_TREND_REQ", "1") == "1"
SEQ_UNCAP = os.environ.get("T4_SEQ_UNCAP", "0") == "1"
_win = os.environ.get("T4_WINDOW_MIN", "90")
WINDOW_MIN = None if _win.strip().lower() == "none" else int(_win)

_TAG = " [floor B: t4 variant trend_req=%s seq_uncap=%s window=%s]" % (
    TREND_REQ, SEQ_UNCAP, WINDOW_MIN)


def _variant_calibration_grade(self, sig):
    """Same shape as the shipped `_calibration_grade` (signal_runner.py:1491),
    with the floor's three conditions individually switchable. The
    counter-day-trend cap above it is IDENTICAL in every variant -- only the
    elif's own three tests are parameterised, exactly as the ticket asks
    ("seq==1/2/>=3", "with/without the trend condition", "the window
    varied") -- so a variant isolates one axis at a time."""
    d = sig["direction"]
    if not hasattr(self, "_dir_fired"):
        self._dir_fired = {"call": 0, "put": 0}
    with_trend = (self.candles[-1].close >= self.candles[0].open) == (d == "call")
    t = self.candles[-1].timestamp[:5]
    mins = int(t[:2]) * 60 + int(t[3:5]) - 570
    if not with_trend and sr._GRADE_RANK.get(sig["grade"], 0) > sr._GRADE_RANK["C"]:
        sig["grade"] = sr.TradeGrade.C.value
        sig["reason"] += " [capped C: counter day trend]"
    elif ((with_trend or not TREND_REQ)
          and (SEQ_UNCAP or self._dir_fired[d] == 0)
          and (WINDOW_MIN is None or 0 <= mins <= WINDOW_MIN)
          and sig["grade"] == "C" and "capped C" not in sig["reason"]):
        sig["grade"] = sr.TradeGrade.B.value
        sig["reason"] += _TAG


assert sr.SignalRunner._calibration_grade is not _variant_calibration_grade
sr.SignalRunner._calibration_grade = _variant_calibration_grade

import backtest_2y  # noqa: E402

if __name__ == "__main__":
    backtest_2y.main()
