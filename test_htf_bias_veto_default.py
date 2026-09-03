"""HTF veto default check. Plain asserts, no pytest:  python test_htf_bias_veto_default.py

Adapted from the cloud branch's `test_htf_grade_veto_default.py` (OMEN 8.0 R4),
which asserted a flag named `HTF_GRADE_VETO` defaulting OFF. That flag does not
exist on this history: P16 had already re-flagged the same behaviour under the
name `HTF_BIAS_VETO` in `omen_bot.py`, and it ships **ON** -- the record, not
the code, was what had been wrong (see `grade_trade`'s W12 docstring note and
`research/p16_htf_bias.md`). The merge kept the local flag and dropped the
cloud's, so this file keeps the cloud's *idea* -- pin the SHIPPED DEFAULT
explicitly, in a test, so it can never drift back to being documented one way
and coded another -- retargeted at the flag this repo actually has.

Asserted:
  1. `HTF_BIAS_VETO` reads True by default (no env var set).
  2. An OPPOSED htf_bias hard-vetoes to D at that default.
  3. `HTF_BIAS_VETO=False` lifts the veto: grades on PA alone, same as
     htf_bias=None -- the "re-gate on the day he defines the rule" escape
     hatch is real and works in both directions.
  4. The `neutral` cap-at-B softening is a separate rule and is untouched by
     the flag either way.
  5. The short side is symmetric.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# HTF_BIAS_VETO is read from the environment at import time -- assert the
# default BEFORE anything could have set the env var, then import.
assert os.environ.get("HTF_BIAS_VETO") is None, \
    "test assumes HTF_BIAS_VETO is unset in the environment"

import omen_bot as ob
from omen_bot import Candle, PriceActionAnalyzer, TradeGrade

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def c(o, h, l, cl, ts="09:45:00", v=100000):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=v)


# A plain bullish retest candle at the key level -- textbook C-grade PA
# (bullish, touches or_high, no hammer/large-lower-wick) with no htf_bias:
# this is the PA-alone baseline every htf_bias case is compared against.
CANDLE = c(100.00, 100.60, 99.90, 100.50)
LOOKBACK = [c(99.00, 99.50, 98.80, 99.20, ts=f"09:{30+i}:00") for i in range(10)]
OR_HIGH, OR_LOW = 100.00, 98.00

baseline = PriceActionAnalyzer.grade_trade(CANDLE, LOOKBACK, OR_HIGH, OR_LOW,
                                           is_long=True, htf_bias=None)
check(baseline == TradeGrade.C, "(setup) htf_bias=None grades on PA alone -> C")

# 1. shipped default
check(ob.HTF_BIAS_VETO is True, "(1) HTF_BIAS_VETO reads True by default")

# 2. an OPPOSED bias vetoes to D at the shipped default
opposed_default = PriceActionAnalyzer.grade_trade(
    CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bearish")
check(opposed_default == TradeGrade.D,
      "(2) opposed htf_bias hard-vetoes to D at the shipped default")
aligned_default = PriceActionAnalyzer.grade_trade(
    CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bullish")
check(aligned_default == baseline,
      "(2b) an ALIGNED bias is untouched (matches the PA-alone grade)")

# 3. turning the flag off lifts the veto
ob.HTF_BIAS_VETO = False
try:
    opposed_lifted = PriceActionAnalyzer.grade_trade(
        CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bearish")
    check(opposed_lifted == baseline,
          "(3) HTF_BIAS_VETO=False grades an opposed bias on PA alone")
    check(opposed_lifted != TradeGrade.D,
          "(3b) HTF_BIAS_VETO=False is not D")
finally:
    ob.HTF_BIAS_VETO = True  # restore the shipped default

# 4. the neutral-caps-at-B softening is untouched by the flag, both ways
A_CANDLE = c(100.30, 100.60, 99.70, 100.55)  # hammer at the level -> A on PA alone
a_baseline = PriceActionAnalyzer.grade_trade(
    A_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias=None)
check(a_baseline == TradeGrade.A, "(setup) hammer at the level grades A on PA alone")
check(PriceActionAnalyzer.grade_trade(
          A_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True,
          htf_bias="neutral") == TradeGrade.B,
      "(4) htf_bias='neutral' caps A to B with the veto ON (unchanged, out of scope)")
ob.HTF_BIAS_VETO = False
try:
    check(PriceActionAnalyzer.grade_trade(
              A_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True,
              htf_bias="neutral") == TradeGrade.B,
          "(4b) htf_bias='neutral' still caps A to B with the veto OFF (unchanged)")
finally:
    ob.HTF_BIAS_VETO = True

# 5. the short side is symmetric -- is_long=False, opposed bias = "bullish"
SHORT_CANDLE = c(98.50, 98.60, 97.90, 98.00)  # bearish retest at the level -> C
short_baseline = PriceActionAnalyzer.grade_trade(
    SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=False, htf_bias=None)
check(short_baseline == TradeGrade.C, "(setup, short) htf_bias=None -> C")
check(PriceActionAnalyzer.grade_trade(
          SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=False,
          htf_bias="bullish") == TradeGrade.D,
      "(5) short: opposed (bullish) htf_bias vetoes to D at the shipped default")
check(PriceActionAnalyzer.grade_trade(
          SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=False,
          htf_bias="bearish") == short_baseline,
      "(5b) short: an ALIGNED (bearish) bias is untouched")
ob.HTF_BIAS_VETO = False
try:
    check(PriceActionAnalyzer.grade_trade(
              SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=False,
              htf_bias="bullish") == short_baseline,
          "(5c) short: HTF_BIAS_VETO=False grades an opposed bias on PA alone")
finally:
    ob.HTF_BIAS_VETO = True

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("all checks passed")
