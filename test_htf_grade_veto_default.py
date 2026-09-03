"""OMEN 8.0 R4 checks. Plain asserts, no pytest:  python test_htf_grade_veto_default.py

`omen-rulebook.md:855`: "`HTF_BIAS_VETO` shipped ON and gated 47.0% of the
two-year book on a formula (SMA20-of-hourly) nobody wrote. Deleted 2026-08-28.
The value is still computed and reported, so it can be re-gated on the day he
defines the rule." The NAMED flag really is gone from omen_bot.py -- but the
veto BEHAVIOR it named survived, unconditional and un-flagged, inside
`PriceActionAnalyzer.grade_trade`: an opposed `htf_bias` hard-returned D no
matter what, live and backtest both. `HTF_GRADE_VETO` (omen_bot.py) is that
behavior re-flagged under its actual current name and location, default OFF.

This file asserts the SHIPPED DEFAULT explicitly, which is what R4's verify
requires: import omen_bot fresh (no env var set) and check
1. HTF_GRADE_VETO reads False by default.
2. grade_trade with an OPPOSED htf_bias does NOT hard-veto to D by default --
   it grades on PA alone, same as htf_bias=None.
3. Turning HTF_GRADE_VETO on (patched directly, since the module already
   imported) restores the exact old behavior -- D on an opposed bias -- so the
   "re-gate on the day he defines the rule" path still exists and works.
4. The `neutral` cap-at-B softening (never part of the deleted veto, not in
   scope for this row) is unaffected by the flag either way.
"""
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

# HTF_GRADE_VETO is read at import time -- assert the default BEFORE anything
# could have set the env var, then import.
assert os.environ.get("HTF_GRADE_VETO") is None, \
    "test assumes HTF_GRADE_VETO is unset in the environment"

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
check(ob.HTF_GRADE_VETO is False, "(1) HTF_GRADE_VETO reads False by default")

# 2. an OPPOSED bias must NOT veto to D by default
opposed_default = PriceActionAnalyzer.grade_trade(
    CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bearish")
check(opposed_default == baseline,
      "(2) opposed htf_bias does not hard-veto to D by default (matches PA-alone grade)")
check(opposed_default != TradeGrade.D,
      "(2b) opposed htf_bias is not D by default")

# 3. explicitly re-gating restores the old (pre-R4) veto behavior
ob.HTF_GRADE_VETO = True
try:
    opposed_gated = PriceActionAnalyzer.grade_trade(
        CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bearish")
    check(opposed_gated == TradeGrade.D,
          "(3) HTF_GRADE_VETO=True restores the D-veto on an opposed bias")
    aligned_gated = PriceActionAnalyzer.grade_trade(
        CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="bullish")
    check(aligned_gated == baseline,
          "(3b) HTF_GRADE_VETO=True does not touch an ALIGNED bias")
finally:
    ob.HTF_GRADE_VETO = False  # restore the shipped default for the next check

# 4. the neutral-caps-at-B softening is untouched by the flag, both ways
A_PLUS_CANDLE = c(100.30, 100.60, 99.70, 100.55)  # hammer at the level -> A+ on PA alone
a_plus_baseline = PriceActionAnalyzer.grade_trade(
    A_PLUS_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias=None)
neutral_default = PriceActionAnalyzer.grade_trade(
    A_PLUS_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="neutral")
check(a_plus_baseline == TradeGrade.A_PLUS,
      "(setup) hammer at the level grades A+ on PA alone")
check(neutral_default == TradeGrade.B,
      "(4) htf_bias='neutral' still caps A+ to B with HTF_GRADE_VETO off (unchanged, out of scope)")
ob.HTF_GRADE_VETO = True
try:
    neutral_gated = PriceActionAnalyzer.grade_trade(
        A_PLUS_CANDLE, LOOKBACK, OR_HIGH, OR_LOW, is_long=True, htf_bias="neutral")
    check(neutral_gated == TradeGrade.B,
          "(4b) htf_bias='neutral' still caps A+ to B with HTF_GRADE_VETO on (unchanged)")
finally:
    ob.HTF_GRADE_VETO = False

# 5. the short side is symmetric -- is_long=False, opposed bias = "bullish"
SHORT_CANDLE = c(98.50, 98.60, 97.90, 98.00)  # bearish retest at the level -> C on PA alone
OR_LOW_SHORT = 98.00
short_baseline = PriceActionAnalyzer.grade_trade(
    SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW_SHORT, is_long=False, htf_bias=None)
check(short_baseline == TradeGrade.C, "(setup, short) htf_bias=None grades on PA alone -> C")

short_opposed_default = PriceActionAnalyzer.grade_trade(
    SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW_SHORT, is_long=False, htf_bias="bullish")
check(short_opposed_default == short_baseline,
      "(5) short: opposed (bullish) htf_bias does not hard-veto to D by default")

ob.HTF_GRADE_VETO = True
try:
    short_opposed_gated = PriceActionAnalyzer.grade_trade(
        SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW_SHORT, is_long=False, htf_bias="bullish")
    check(short_opposed_gated == TradeGrade.D,
          "(5b) short: HTF_GRADE_VETO=True restores the D-veto on an opposed (bullish) bias")
    short_aligned_gated = PriceActionAnalyzer.grade_trade(
        SHORT_CANDLE, LOOKBACK, OR_HIGH, OR_LOW_SHORT, is_long=False, htf_bias="bearish")
    check(short_aligned_gated == short_baseline,
          "(5c) short: HTF_GRADE_VETO=True does not touch an ALIGNED (bearish) bias")
finally:
    ob.HTF_GRADE_VETO = False

print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    sys.exit(1)
print("all checks passed")
