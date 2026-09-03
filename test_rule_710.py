"""omen-3.8 T5 checks. Plain asserts, no pytest:  python test_rule_710.py

Covers the Rule 7 / Rule 10 rewrite:
  1. TOTALITY — both features return a number on every bar, for every level.
     This is the whole point of the row: research/rule7_rule10.md's versions are
     null on 76/159 and 56/159 marks because they start at a "break candle".
  2. The conditions actually discriminate (fast retest passes, slow fails;
     clean level passes, chewed-up level fails).
  3. RULE_710_ENABLED defaults OFF and is a no-op in _route while OFF.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import signal_runner as sr
from omen_bot import Candle, SignalType, TradeGrade

FAILS = []


def check(cond, label):
    if cond:
        print(f"  ok   {label}")
    else:
        print(f"  FAIL {label}")
        FAILS.append(label)


def c(o, h, l, cl, ts="09:30:00", v=100000):
    return Candle(timestamp=ts, open=o, high=h, low=l, close=cl, volume=v)


LEVEL = 100.0

# Away for 2 bars, retest on the last bar -> rule 7 value 2.
FAST = [c(99.2, 99.4, 99.0, 99.1), c(99.2, 100.8, 99.2, 100.7),
        c(100.7, 101.2, 100.6, 101.1), c(101.1, 101.3, 101.0, 101.1),
        c(101.1, 101.2, 99.95, 100.3)]

# Same break, then 12 bars that never come back near the level -> saturates high.
SLOW = FAST[:4] + [c(101.1, 101.4, 101.0, 101.2) for _ in range(12)]

# Price never touches the level anywhere in the window -> the no-touch case that
# used to be `null`; it must be a number (the window cap), not None.
NEVER = [c(105.0, 105.4, 104.8, 105.2) for _ in range(25)]


print("1. TOTALITY — no null branch anywhere")

for name, bars in (("fast", FAST), ("slow", SLOW), ("never-touched", NEVER),
                   ("one bar", FAST[:1]), ("empty", [])):
    v = sr.rule7_retest_bars(bars, LEVEL)
    check(isinstance(v, int) and 0 <= v <= sr.RULE7_WINDOW,
          f"rule7_retest_bars({name}) = {v}: an int in [0, {sr.RULE7_WINDOW}]")
    cnt, at = sr.rule10_left_pivots(bars, LEVEL)
    check(isinstance(cnt, int) and isinstance(at, int) and cnt >= 0 and at >= 0,
          f"rule10_left_pivots({name}) = ({cnt}, {at}): two ints, no None")

check(sr.rule7_retest_bars(NEVER, LEVEL) == sr.RULE7_WINDOW,
      "a window with no touch saturates at the cap (replaces the old null)")
check(sr.rule7_retest_bars(FAST, LEVEL) == 2,
      "away-leg of 2 bars then a retest on the current bar = 2")
check(sr.rule7_retest_bars([], None) == sr.RULE7_WINDOW,
      "no candles and no level still returns a number")


print("2. The conditions discriminate")

check(sr.rule_710_reject(FAST, LEVEL) is None,
      "a fast retest on a clean level passes both rules")
slow_why = sr.rule_710_reject(SLOW, LEVEL)
check(slow_why is not None and "rule7" in slow_why,
      f"a slow/absent retest is rejected by rule 7 ({slow_why})")
check(sr.rule_710_reject(NEVER, LEVEL) is not None,
      "a level price never reached is rejected, not skipped as undefined")
check(sr.rule_710_reject(FAST, None) is None,
      "no level = nothing to measure against = abstain (never blocks)")

# Rule 10: same fast retest, but the run-up is pivot noise sitting ON the level.
noise = []
for i in range(12):
    if i % 2:
        noise.append(c(100.0, 100.05, 99.85, 99.95))   # pivot low at the level
    else:
        noise.append(c(99.95, 100.15, 99.90, 100.05))  # pivot high at the level
NOISY = noise + FAST[1:]
cnt, at = sr.rule10_left_pivots(NOISY, LEVEL)
check(at > sr.RULE10_MAX_PIVOTS_AT_LEVEL,
      f"chewed-up level counts {at} pivots within 0.2% (> {sr.RULE10_MAX_PIVOTS_AT_LEVEL})")
noisy_why = sr.rule_710_reject(NOISY, LEVEL)
check(noisy_why is not None and "rule10" in noisy_why,
      f"a level with pivot noise on it is rejected by rule 10 ({noisy_why})")
check(sr.rule10_left_pivots(FAST, LEVEL)[1] <= sr.RULE10_MAX_PIVOTS_AT_LEVEL,
      "the clean fixture has no pivot pile-up on the level")


print("3. The flag")

check(sr.RULE_710_ENABLED is False, "RULE_710_ENABLED defaults to False (shipped = today)")

runner = sr.SignalRunner("TEST")
runner.log_signals = False
runner.candles = SLOW          # would FAIL rule 7 if the flag were on


def route_once():
    out = []
    sig = {"signal_type": SignalType.BREAK_AND_RETEST, "reason": "t",
           "entry": 101.2, "stop": LEVEL, "direction": "call",
           "grade": TradeGrade.B.value, "stop_level_name": "OR high",
           "stop_width_pct": 1.2}
    runner._route(out, sig)
    return sig


off = route_once()
check(off["grade"] == "B" and "capped C" not in off["reason"],
      "flag OFF: a rule-7-failing signal is untouched (byte-identical to today)")

_prev = sr.RULE_710_ENABLED
try:
    sr.RULE_710_ENABLED = True
    on = route_once()
    check(on["grade"] == "C" and "rule7" in on["reason"],
          "flag ON: the same signal is capped to C and says which rule capped it")
finally:
    sr.RULE_710_ENABLED = _prev
check(sr.RULE_710_ENABLED is False, "RULE_710_ENABLED restored to False after the flip")

rules = (pathlib.Path(__file__).resolve().parent / "Trading-Bot-Rulesets.md").read_text()
check(rules.count("**Detection condition:**") >= 2,
      "both rewritten rules name a detection condition in the ruleset doc")


print()
if FAILS:
    print(f"{len(FAILS)} FAILED:")
    for f in FAILS:
        print(f"  - {f}")
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("all checks passed")
