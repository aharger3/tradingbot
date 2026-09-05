"""omen-3.7 T5 checks. Plain asserts, no pytest:  python test_detect_wide.py

Covers the three changes in the row:
  1. DETECT_WIDE — the retest-proximity widening at `no_break_retest`, the top
     cause of S-blindness in research/miss_autopsy.md (27 of 77 S marks).
  2. The D -> X skip-grade rename (+ the always-None austin_tier slot).
  3. FAIR_VALUE_GAP / FLAG split out of ONE_CANDLE_RULE.
"""
import pathlib
import sys

# Run correctly from any working directory: resolve imports and the source-text
# read against this file's own directory, not the caller's cwd.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import signal_runner as sr
from omen_bot import Candle, SignalType, TradeGrade, detect_break_retest

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def c(o, h, l, cl, ts="09:30:00", v=100000):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=v)


# --------------------------------------------------------------------------
# Fixtures: the ordered BREAK -> LEAVE -> RETEST -> CONFIRM sequence, long side.
# LEVEL = 100.0. Candle range is ~0.40 throughout, so the DETECT_WIDE band at
# 1.0x avg range is ~0.40 wide — a retest low of 99.98 touches; 100.25 does not
# touch but sits inside the band; 101.60 is outside it.
# --------------------------------------------------------------------------
LEVEL = 100.0


def sequence(retest_low: float):
    """Break above 100, clear it, come back to `retest_low`, close back through.
    Every candle keeps a ~0.40 range so avg-range arithmetic is predictable."""
    return [
        c(99.20, 99.40, 99.00, 99.10),   # below the level
        c(99.10, 99.40, 99.00, 99.20),   # below (prior close for the break test)
        c(99.20, 100.80, 99.20, 100.70),  # 1. BREAK — closes through 100 + eps
        c(100.70, 101.20, 100.60, 101.10),  # 2. LEAVE — low 100.60 fully clears
        c(101.10, 101.30, 101.00, 101.10),  # still clear
        # 3. RETEST — pulls back to `retest_low`
        c(101.10, 101.20, retest_low, retest_low + 0.20),
        # 4. CONFIRM — closes back through the level, bullish, small upper wick
        c(retest_low + 0.20, 100.95, retest_low + 0.15, 100.90),
    ]


TOUCH = sequence(99.98)     # low tags the level exactly -> valid today
NEAR = sequence(100.25)     # low stops 0.25 SHORT of the level -> discarded today
FAR = sequence(101.60)      # low never comes near -> must stay rejected


print("1. DETECT_WIDE — the widening at `no_break_retest`")

# Sanity: the fixtures behave as the strict FSM says they should.
check(detect_break_retest(TOUCH, LEVEL, is_long=True) is not None,
      "strict path still accepts an exact-touch retest (no regression)")
check(detect_break_retest(NEAR, LEVEL, is_long=True) is None,
      "strict path rejects a retest that stops short of the level")

# ACCEPTS: the near-miss retest is what the widening is for.
check(detect_break_retest(NEAR, LEVEL, is_long=True, retest_tol_mult=1.0) is not None,
      "widened path ACCEPTS a retest inside 1.0x avg range of the level")

# REJECTS: widening is a band, not an amnesty.
check(detect_break_retest(FAR, LEVEL, is_long=True, retest_tol_mult=1.0) is None,
      "widened path still REJECTS a retest far outside the band")

# The default must reproduce today's exact-touch test byte-for-byte.
check(detect_break_retest(NEAR, LEVEL, is_long=True, retest_tol_mult=0.0) is None,
      "retest_tol_mult=0.0 is identical to the exact-touch test")

# A widened fire says so, so the A/B can separate it.
note = detect_break_retest(NEAR, LEVEL, is_long=True, retest_tol_mult=1.0)
check("WIDE" in note, "widened fire is tagged WIDE in the note")
check("WIDE" not in (detect_break_retest(TOUCH, LEVEL, is_long=True) or ""),
      "an exact-touch fire is NOT tagged WIDE")

# The flag itself.
check(sr.DETECT_WIDE is False, "DETECT_WIDE defaults to False (shipped = today)")
check(sr._retest_tol() == 0.0, "_retest_tol() is 0.0 while the flag is off")
_prev = sr.DETECT_WIDE
try:
    sr.DETECT_WIDE = True
    check(sr._retest_tol() == sr.DETECT_WIDE_RETEST_MULT,
          "harness can flip DETECT_WIDE at runtime, as with BNR_DISPLACEMENT_GATE")
finally:
    sr.DETECT_WIDE = _prev
check(sr.DETECT_WIDE is False, "DETECT_WIDE restored to False after the flip")

# Short side mirrors the long side.
def short_sequence(retest_high):
    return [
        c(100.80, 101.00, 100.60, 100.90),
        c(100.90, 101.00, 100.60, 100.80),
        c(100.80, 100.80, 99.20, 99.30),                  # BREAK down
        c(99.30, 99.40, 98.80, 98.90),                    # LEAVE
        c(98.90, 99.00, 98.70, 98.90),
        c(98.90, retest_high, 98.80, retest_high - 0.20),  # RETEST
        c(retest_high - 0.20, retest_high - 0.15, 99.05, 99.10),  # CONFIRM
    ]

check(detect_break_retest(short_sequence(99.75), LEVEL, is_long=False) is None,
      "short: strict path rejects a retest that stops short of the level")
check(detect_break_retest(short_sequence(99.75), LEVEL, is_long=False,
                          retest_tol_mult=1.0) is not None,
      "short: widened path ACCEPTS a near-miss retest")
check(detect_break_retest(short_sequence(98.40), LEVEL, is_long=False,
                          retest_tol_mult=1.0) is None,
      "short: widened path still REJECTS a far retest")


print("2. D -> X skip-grade rename + austin_tier (computed since omen-3.9 T4)")

check(TradeGrade.X.value == "X", "a skip grade serialises as 'X'")
check(TradeGrade.D is TradeGrade.X, "TradeGrade.D is an alias of TradeGrade.X")
check(TradeGrade.D.value == "X", "the old letter D serialises as 'X' too")
check(TradeGrade("D") is TradeGrade.X, "TradeGrade('D') still resolves (old readers)")
check(TradeGrade("X") is TradeGrade.X, "TradeGrade('X') resolves")
check(sr._GRADE_RANK["X"] == 0 and sr._GRADE_RANK["D"] == 0,
      "_GRADE_RANK ranks both spellings of skip at 0")
check(sr._GRADE_RANK["C"] > sr._GRADE_RANK["X"], "C outranks the skip grade")

# _route must drop a skip-grade signal and keep a tradeable one, and must stamp
# austin_tier on both. omen-3.9 T4: the slot became a computed S/A/C — it is
# still a REPORTED field, so routing must be identical either side of it.
runner = sr.SignalRunner("TEST")
runner.log_signals = False
runner.candles = TOUCH

skipped = []
skip_sig = {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t", "entry": 100.9,
            "stop": 100.0, "direction": "call", "grade": TradeGrade.X.value,
            "stop_level_name": "OR high", "stop_width_pct": 0.9}
runner._route(skipped, skip_sig)
check(skipped == [], "_route drops an X-grade (skip) signal")
check(skip_sig.get("austin_tier") in ("S", "A", "C"),
      "austin_tier is on the signal dict, computed even on a skipped signal")

kept = []
keep_sig = {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t", "entry": 100.9,
            "stop": 100.0, "direction": "call", "grade": TradeGrade.B.value,
            "stop_level_name": "OR high", "stop_width_pct": 0.9}
runner._route(kept, keep_sig)
check(len(kept) == 1, "_route keeps a B-grade signal")
check(kept[0]["austin_tier"] in ("S", "A", "C"),
      "austin_tier is computed on a fired signal too")
check(kept[0]["austin_tier"] != "X",
      "compute_austin_tier never emits X — that is Austin's own marker")

# Still no A+/A/B/C -> S/A/C mapping: the tier is computed from the four
# clauses, not translated from an engine grade.
check(all(g.value not in ("S",) for g in TradeGrade),
      "no engine grade claims to be an Austin S tier")
check(sr.TRADE_S_ONLY is False and sr.HTF_OPPOSITION_VETO == "hard",
      "the S-only switch is off and clause 4 defaults to hard")


print("3. FAIR_VALUE_GAP / FLAG split out of ONE_CANDLE_RULE")

check(SignalType.FAIR_VALUE_GAP != SignalType.ONE_CANDLE_RULE,
      "SignalType.FAIR_VALUE_GAP and ONE_CANDLE_RULE are distinct values")
check(SignalType.FLAG != SignalType.ONE_CANDLE_RULE,
      "SignalType.FLAG and ONE_CANDLE_RULE are distinct values")
check(SignalType.FAIR_VALUE_GAP != SignalType.FLAG,
      "SignalType.FAIR_VALUE_GAP and FLAG are distinct values")
check(len({s.value for s in SignalType}) == len(list(SignalType)),
      "every SignalType has a unique value (no accidental aliasing)")
check(SignalType.FAIR_VALUE_GAP.value == "fair_value_gap"
      and SignalType.FLAG.value == "flag",
      "the new types serialise under their own names")

src = (pathlib.Path(__file__).resolve().parent / "signal_runner.py").read_text(
    encoding="utf-8")
check("Flag long" in src and 'SignalType.FLAG,\n                    "reason": f"Flag long' in src,
      "the flag long branch routes to SignalType.FLAG")
check('SignalType.FAIR_VALUE_GAP,\n                            "reason": f"B&R long — FVG retest' in src,
      "the FVG long branch routes to SignalType.FAIR_VALUE_GAP")
# Counts ROUTING uses only ("signal_type": ...), not every mention: omen-3.9 T4
# also names ONE_CANDLE_RULE in S_ELIGIBLE_SETUPS, which routes nothing.
check(src.count('"signal_type": SignalType.ONE_CANDLE_RULE') == 2,
      "ONE_CANDLE_RULE is left to the order block alone (long + short)")


print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("all checks passed")
