"""T4/G14 internal helper -- never imported, only invoked as a subprocess.

Same monkeypatch as `_t4_variant_wrapper.py`, applied before scoring the 100
held-out OMEN Test 1 cards (`research/t70_test1_score.py`) instead of before
`backtest_2y.py`. Prints the scored rows as one JSON line to stdout.

Read this before trusting a variant's held-out recall number: promoting a
signal to `B` lets it skip the tight-stop-C check (signal_runner.py:1891), so
a variant CAN change whether the engine fires at all on a day, not only which
grade it fires at -- recall is not guaranteed identical across variants and
must be measured, not assumed.

Usage: `T4_SEQ_UNCAP=1 python research/_t4_variant_test1.py`
"""
import json
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


def _variant_calibration_grade(self, sig):
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
        sig["reason"] += " [floor B: t4 variant]"


sr.SignalRunner._calibration_grade = _variant_calibration_grade

import research.t70_test1_score as t70  # noqa: E402

if __name__ == "__main__":
    print(json.dumps(t70.score_all(t70.load_cards())))
