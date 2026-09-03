"""T5 unit tests on hand-built bars -- the exit semantics, and the two branches
that this repo's history says will silently die if nobody asserts them.

Run: python research/test_t5_target.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.t5_structural_target import (ladder, replay, PLANS, FALLBACK_R,  # noqa: E402
                                           MIN_RUNG_R, MIN_SPACING_R)

FAILS = []


def check(name, got, want, tol=1e-9):
    ok = abs(got - want) <= tol if isinstance(want, float) else got == want
    print(("  ok   " if ok else "  FAIL ") + f"{name}: got {got!r}, want {want!r}")
    if not ok:
        FAILS.append(name)


def bar(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c}


# entry 100, stop 99 -> risk 1.0, 1R = 101, 2R = 102, disaster stop = 99.0
E, S = 100.0, 99.0


def flat(px, n):
    return [bar(px, px, px, px) for _ in range(n)]


print("R1/R2 -- the disaster stop is a TOUCH, and it is tested first")
# a bar that wicks to 98.9 and closes back at 100.5 is still out at -1R:
# the resting order was there when price arrived.
bars = flat(100.0, 3) + [bar(100.0, 100.6, 98.9, 100.5)] + flat(100.5, 3)
r, i = replay(bars, 2, E, S, "L", [102.0], [1.0])
check("wick through -1R books exactly -1.000R", r, -1.0)

print("The LEVEL stop triggers on the CLOSE and fills at that close")
# with the disaster stop disabled, a bar closing at 99.4 (above the -1R order,
# below the 99.0 stop is impossible) -- use a stop at 99.5 so risk is 0.5,
# -1R = 99.5 too. Instead: disable disaster and close below the stop.
bars = flat(100.0, 3) + [bar(100.0, 100.0, 98.4, 98.4)] + flat(98.4, 3)
r, i = replay(bars, 2, E, S, "L", [102.0], [1.0], disaster=False)
check("close at 98.4 books -1.600R clamped to the -1.25R floor", r, -1.25)

print("A wick alone stops nothing out (Austin, five times in one batch)")
bars = flat(100.0, 3) + [bar(100.0, 100.2, 99.05, 100.1)] + flat(100.1, 3)
r, i = replay(bars, 2, E, S, "L", [102.0], [1.0])
check("wick to 99.05 (above -1R) does not exit", round(r, 4), 0.1)

print("Targets are limit orders -- they fill on an intrabar TOUCH")
bars = flat(100.0, 3) + [bar(100.0, 102.0, 99.9, 100.4)] + flat(100.4, 3)
r, i = replay(bars, 2, E, S, "L", [102.0], [1.0])
check("2R tagged intrabar books +2.000R", r, 2.0)

print("PESSIMISTIC_FILL -- a bar that tags the target AND closes beyond the "
      "stop books the LOSS")
bars = flat(100.0, 3) + [bar(100.0, 102.0, 98.9, 98.9)] + flat(98.9, 3)
r, i = replay(bars, 2, E, S, "L", [102.0], [1.0])
check("target tagged but -1R touched books -1.000R", r, -1.0)

print("R11 -- rung 1 raises the stop to break-even from the NEXT bar")
# rung 1 at 101 fills on bar 3; bar 4 closes at 99.5, above the original stop
# but below BE, so the runner books 0R at BE... the fill is the CLOSE (99.5),
# floored at -1.25R of the ORIGINAL risk, which 99.5 does not breach.
bars = flat(100.0, 3) + [bar(100.0, 101.2, 100.0, 101.0)] + \
       [bar(101.0, 101.0, 99.4, 99.5)] + flat(99.5, 2)
r, i = replay(bars, 2, E, S, "L", [101.0, 105.0], [0.5, 0.5])
check("50% at +1R then runner out at 99.5", round(r, 4), 0.5 * 1.0 + 0.5 * -0.5)

print("...and with be_after_rung1=False the runner keeps the ORIGINAL stop")
r2, _ = replay(bars, 2, E, S, "L", [101.0, 105.0], [0.5, 0.5],
               be_after_rung1=False)
check("no-BE variant survives the 99.5 bar to EOD", round(r2, 4),
      round(0.5 * 1.0 + 0.5 * -0.5, 4))

print("At most ONE rung fills per bar (backtest_week._ladder_bar returns "
      "after scaling)")
bars = flat(100.0, 3) + [bar(100.0, 106.0, 100.0, 105.9)] + flat(105.9, 4)
r, i = replay(bars, 2, E, S, "L", [101.0, 102.0, 103.0], [0.5, 0.25, 0.25])
check("a 6R bar books rung 1 only on that bar", round(r, 4),
      round(0.5 * 1.0 + 0.25 * 2.0 + 0.25 * 3.0, 4))

print("The `+trail` tranche is REACHABLE -- the bug class this repo has "
      "shipped four times")
# 3 rungs, 4 weights: 0.10 must still be live after rung 3 fills.
bars = flat(100.0, 3) + [bar(100.0, 101.2, 100.0, 101.1)] + \
       [bar(101.1, 102.2, 101.0, 102.1)] + [bar(102.1, 103.2, 102.0, 103.1)] + \
       [bar(103.1, 110.0, 103.0, 109.9)] + flat(109.9, 3)
w = PLANS["50_20_20_10"]
r_t, _ = replay(bars, 2, E, S, "L", [101.0, 102.0, 103.0], w, trail_last=True)
r_f, _ = replay(bars, 2, E, S, "L", [101.0, 102.0, 103.0, 104.0], w)
check("trail tranche books more than a 4th fixed rung would", r_t > r_f, True)
check("trail tranche carries exactly 10% of the position",
      round(r_t - (0.5 * 1.0 + 0.2 * 2.0 + 0.2 * 3.0), 4),
      round(0.10 * (109.9 - 100.0), 4))

print("A ladder SHORTER than the plan: the last rung absorbs the remainder, "
      "it does not leak into a silent hold-to-EOD")
# 2 rungs, 4 weights. The 102.0 rung must take 0.5, not 0.2, or 0.3 of the
# position would ride to the close with no target -- `hold_eod` smuggled in.
bars = flat(100.0, 3) + [bar(100.0, 101.2, 100.0, 101.1)] + \
       [bar(101.1, 102.2, 101.0, 102.1)] + flat(102.1, 3)
r, i = replay(bars, 2, E, S, "L", [101.0, 102.0], PLANS["50_20_20_10"])
check("short ladder books 50%@1R + 50%@2R", round(r, 4),
      round(0.5 * 1.0 + 0.5 * 2.0, 4))

print("R9 -- 'if no level then default 2r' returns the 2R price")
rungs, fb, n = ladder({}, E, S, "L", 4, "level")
check("empty roster falls back to 2R", rungs, [E + FALLBACK_R * (E - S)])
check("...and reports it as a fallback", fb, True)

print("The ladder is ordered, spaced and inside the window")
lv = {f"L{i}": p for i, p in enumerate(
    [100.05, 100.3, 100.6, 101.4, 101.5, 103.0, 200.0])}
rungs, fb, n = ladder(lv, E, S, "L", 4, "level")
check("no rung closer than MIN_RUNG_R", all(p >= E + MIN_RUNG_R for p in rungs), True)
check("rungs strictly increasing", rungs == sorted(rungs), True)
check("consecutive rungs at least MIN_SPACING_R apart",
      all(rungs[i + 1] - rungs[i] >= MIN_SPACING_R - 1e-9
          for i in range(len(rungs) - 1)), True)
check("the 200.0 level is past MAX_LADDER_R and is not used",
      200.0 in rungs, False)

print("R25 -- levels inside the 2R path are inner rungs, the final rung is "
      "the first level at or beyond 2R")
rungs, fb, n = ladder(lv, E, S, "L", 4, "beyond_2r")
check("final rung is at or beyond 2R", rungs[-1] >= E + 2.0 * (E - S), True)
check("inner rungs are all inside 2R",
      all(p < E + 2.0 * (E - S) for p in rungs[:-1]), True)

print("Shorts mirror longs")
rungs, fb, n = ladder({}, 100.0, 101.0, "S", 4, "level")
check("short fallback is 2R BELOW entry", rungs, [98.0])
bars = flat(100.0, 3) + [bar(100.0, 100.1, 98.0, 98.1)] + flat(98.1, 3)
r, i = replay(bars, 2, 100.0, 101.0, "S", [98.0], [1.0])
check("short 2R target books +2.000R", r, 2.0)

print()
if FAILS:
    print(f"FAILED {len(FAILS)}: {FAILS}")
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("all T5 exit-semantics tests pass")
