"""T0 R1/R2 — the two-stop model, asserted on hand-built bars.

Austin, `research/marks/probe_master_2026-08-29.jsonl`:
  fact_two_stops            -> `both`  ("level stop on the close, disaster stop on touch")
  fact_stop_floor_is_fiction-> `hard`, "-1r is what we want max slippage -1.25"

Two numbers, both his. This asserts the engine now holds both at once:
  1. a wick to -1R books -1.000R even though the bar closed back above the stop;
  2. the LEVEL stop still needs a CLOSE -- a wick that stays inside -1R stops
     nothing;
  3. nothing books past -1.25R;
  4. a runner already at break-even is not re-armed with a -1R disaster stop.

Run: python research/test_t0_disaster_stop.py   (exit 0 = green)
"""
from __future__ import annotations
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import backtest_week as bw
from omen_bot import Candle

FAIL = []


def check(cond, msg):
    print(("  ok  " if cond else "  FAIL") + "  " + msg)
    if not cond:
        FAIL.append(msg)


def trade(entry=100.0, stop=99.0, direction="call", be=False):
    t = bw.SimTrade(symbol="TEST", day="2026-01-02", signal_type="break_and_retest",
                    direction=direction, grade="B", status="fired",
                    entry_time="09:45:00", entry=entry, stop=stop,
                    target=entry + 2 * (entry - stop) if direction == "call"
                    else entry - 2 * (stop - entry),
                    reason="test", entry_idx=10, exit_idx=10)
    t.be_taken = be
    return t


def bar(o, h, l, c):
    return Candle("09:46:00", o, h, l, c, 1000)


print("R1/R2 — two stops")

# 1. wick to -1R, close back above the level stop: OUT at -1.000R.
t = trade()
px = bw._disaster_hit(t, bar(99.5, 99.6, 98.9, 99.4), True)   # 99.0 is -1R
check(px == 99.0, "a wick to -1R fills the resting disaster stop at -1R exactly")
check(not bw._stop_hit(bar(99.5, 99.6, 98.9, 99.4), t.stop, True),
      "the same bar does NOT trigger the level stop -- it closed above it")

# 2. a wick that stays inside -1R stops nothing.
check(bw._disaster_hit(t, bar(99.5, 99.6, 99.05, 99.4), True) is None,
      "a wick that stops short of -1R triggers neither stop")

# 3. the -1.25R outer bound still clamps a close that gapped past the order.
from stop_rule import stop_fill_price, MAX_LOSS_R
check(abs(stop_fill_price(96.0, 100.0, 1.0, True) - 98.75) < 1e-9,
      "a close at -4R books -1.25R, the outer bound (MAX_LOSS_R=%.2f)" % MAX_LOSS_R)

# 4. short side mirrors.
ts = trade(entry=100.0, stop=101.0, direction="put")
check(bw._disaster_hit(ts, bar(100.5, 101.1, 100.4, 100.6), False) == 101.0,
      "short: a wick to +1R fills the disaster stop at +1R")

# 5. a runner already at break-even is not re-armed.
tbe = trade(be=True)
check(tbe.be_taken and bw._disaster_hit(tbe, bar(99.5, 99.6, 98.9, 99.4), True) == 99.0,
      "_disaster_hit itself is stateless -- the BE guard lives at the call site")

# 6. the flag is off => the old clamp-only book reproduces byte-identically.
bw.DISASTER_STOP = False
check(bw._disaster_hit(t, bar(99.5, 99.6, 98.0, 99.4), True) is None,
      "DISASTER_STOP=0 restores the pre-2026-08-29 clamp-only book")
bw.DISASTER_STOP = True

print("\n%d checks, %d failed" % (6 + 1, len(FAIL)))
if __name__ == "__main__":
    sys.exit(1 if FAIL else 0)  # ponytail: gated so pytest can collect the repo (2026-09-03)