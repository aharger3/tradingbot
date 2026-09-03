"""G7.2 (suppress) — the failing test for the suppression bug, in the
research/test_*.py style already in this repo.

The claim under test, one sentence: A SETUP THE ENGINE REJECTED MUST NOT SILENCE
THE ONE IT WOULD HAVE TRADED ONE BAR LATER ON THE SAME LEVEL.

It drives backtest_week.simulate_day with a scripted detector so the only thing
moving is the dedupe window — no bars, no market data, no engine grading. Three
cases:

  1. reject on bar 10, FIRE on bar 11, same level  -> the fire must survive
  2. FIRE on bar 10, fire on bar 11, same level    -> the second is one idea, dropped
  3. FIRE on bar 10, FIRE on bar 13, same level    -> two bars quiet, both survive

Run:  python research/g72_suppress_test.py     (exit 0 = pass)
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import backtest_week as bw
from backtest_week import Candle, simulate_day
from signal_runner import SignalType, TradeGrade

FAILS = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def candles(n=25):
    """Flat 1-minute bars from 09:35. Prices never matter: the scripted detector
    below decides what is seen, and every scripted trade is left open to EOD."""
    out = []
    for i in range(n):
        t = 9 * 60 + 35 + i
        out.append(Candle(timestamp="%02d:%02d:00" % (t // 60, t % 60),
                          open=100.0, high=100.1, low=99.9, close=100.0, volume=1000))
    return out


def sig(status, level="OR high"):
    return {"signal_type": SignalType.BREAK_AND_RETEST, "direction": "call",
            "entry": 100.0, "stop": 99.0, "grade": TradeGrade.B.value,
            "status": status, "reason": "test", "stop_level_name": level,
            "level_price": 99.0}


def run(script):
    """script: {bar_index: [status, ...]} -> the SimTrade rows simulate_day keeps."""
    class Stub:
        def __init__(self, symbol):
            self.captured = []
            self.candles = []

        def detect_signals(self):
            i = len(self.candles) - 1
            for st in script.get(i, []):
                self.captured.append(sig(st))

        def __setattr__(self, k, v):   # simulate_day sets pdh/pmh/qqq_breaks/...
            object.__setattr__(self, k, v)

    real = bw.BacktestRunner
    bw.BacktestRunner = Stub
    try:
        return simulate_day("TEST", "2026-01-05", candles(), None, None, None)
    finally:
        bw.BacktestRunner = real


def statuses(rows):
    return [r.status for r in rows]


for fires_only, label in ((False, "DEDUPE_FIRES_ONLY=0 (the old, buggy window)"),
                          (True, "DEDUPE_FIRES_ONLY=1 (shipped)")):
    bw.DEDUPE_FIRES_ONLY = fires_only
    print("\n%s" % label)

    # 1. a reject, then the real trade one bar later on the same level
    rows = run({10: ["skipped_tight_stop"], 11: ["fired"]})
    got = statuses(rows)
    if fires_only:
        check(got.count("fired") == 1,
              "reject then fire: the fire survives  (statuses=%s)" % got)
    else:
        check(got.count("fired") == 0,
              "reject then fire: the bug eats the fire  (statuses=%s)" % got)

    # 2. the same level firing on consecutive bars is ONE idea, both arms
    rows = run({10: ["fired"], 11: ["fired"]})
    got = statuses(rows)
    check(got.count("fired") == 1,
          "fire then fire next bar: still one idea  (statuses=%s)" % got)

    # 3. three bars apart is a second trade, both arms
    rows = run({10: ["fired"], 13: ["fired"]})
    got = statuses(rows)
    check(got.count("fired") == 2,
          "fire, quiet, fire: two trades  (statuses=%s)" % got)

bw.DEDUPE_FIRES_ONLY = True   # leave the module on the shipped default

print()
if FAILS:
    print("FAIL: %d check(s)" % len(FAILS))
    sys.exit(1)
print("PASS: a reject no longer claims the level; a fire still does.")
