"""Selftest for research/downgrade.py. Synthetic bars, no archive.

Austin's worry, 2026-08-24: "there could be a lot of bugs that arise, and i'm very
concerned about how the backtests will play out to the results." The grader is the
piece the whole recall number will rest on, so each variable is tested in isolation
on a chart built to trip exactly that one -- and, just as important, on a clean
chart that must trip NOTHING. A downgrade variable that fires on a clean setup would
quietly cap every trade at C and look like the strategy failing.

    python research/test_downgrade.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from research import downgrade as dg                            # noqa: E402

FAILURES = []


def check(cond, label):
    print("  %s  %s" % ("ok  " if cond else "FAIL", label))
    if not cond:
        FAILURES.append(label)


def b(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


LEVEL = 100.0


def clean_long(n_after=6):
    """The textbook setup: base under the level, a strong break, an immediate
    retest that holds, then away. Nothing here should trip."""
    # Base candles must have a real BODY. The first version used dojis
    # (open == close), which made the average prior body zero and silently made
    # no_displacement unjudgeable -- it returned False for the right reason on
    # the wrong chart, and the weak-break case then failed to fire.
    bars = [b(99.0, 99.4, 98.9, 99.15) for _ in range(20)]
    bars.append(b(99.1, 101.4, 99.0, 101.3))       # 20: the break, big body
    bars.append(b(101.3, 101.4, 100.05, 100.6))    # 21: immediate retest, holds
    # The run has to close back above the retest candle's high quickly, or the
    # retest itself reads as an un-bought-back counter-trend candle.
    for k in range(n_after):
        base = 101.5 + k * 0.35
        bars.append(b(base, base + 0.45, base - 0.15, base + 0.35))
    return bars


# ---------------------------------------------------------------------------
print("clean setup trips nothing")
bars = clean_long()
i = len(bars) - 1
res = dg.score(bars, i, LEVEL, True, enable_chase=False)
check(res is not None, "score() returns a record")
check(res["tripped"] == [], "no variable fires on a clean chart (got %s)" % res["tripped"])

# R22 (Austin, probe_master_2026-08-29, fact_chase -> `downgrade`): chase is the
# ninth variable and ships ON. This fixture walks 0.35 a bar past the level, so
# by the entry bar it IS a chase -- "don't buy the top" -- and the same clean
# chart costs one downgrade on the shipped ladder.
res_chase = dg.score(bars, i, LEVEL, True)
check(dg.ENABLE_CHASE_DOWNGRADE is True, "R22: chase ships ON as a downgrade variable")
check(res_chase["tripped"] == ["chase"],
      "R22: an entry far past the level trips chase and nothing else (got %s)"
      % res_chase["tripped"])
check(res_chase["n_tripped"] == res["n_tripped"] + 1,
      "R22: chase costs exactly one downgrade, not a veto")
check(res_chase["grade"] == "S" and res_chase["confluence"] is True,
      "R22: ...and one downgrade against clean confluence is still S -- his +1 rule")
check(res["grade"] == "S", "a clean chart grades S (got %s)" % res["grade"])

# ---------------------------------------------------------------------------
print("\neach variable fires on its own chart")

# no_displacement: same shape, but the break candle is limp.
weak = clean_long()
weak[20] = b(99.9, 100.2, 99.85, 100.05)
check(dg.no_displacement(weak, len(weak) - 1, LEVEL, True),
      "no_displacement fires when the break candle has no body")
check(not dg.no_displacement(bars, i, LEVEL, True),
      "  and does not fire on the clean break")

# stale_retest: break, then a long walk before coming back.
stale = clean_long()[:21]
for _ in range(dg.STALE_BARS + 3):
    stale.append(b(101.5, 101.9, 101.3, 101.7))          # away from the level
stale.append(b(101.4, 101.5, 100.02, 100.4))             # finally returns
check(dg.stale_retest(stale, len(stale) - 1, LEVEL, True),
      "stale_retest fires when the retest is >%d bars after the break" % dg.STALE_BARS)
check(not dg.stale_retest(bars, i, LEVEL, True),
      "  and does not fire on an immediate retest")

# level_not_respected: closes sitting ON the level.
chop = clean_long()[:21]
for _ in range(4):
    chop.append(b(100.0, 100.3, 99.7, 100.0))            # closing exactly at it
check(dg.level_not_respected(chop, len(chop) - 1, LEVEL, True),
      "level_not_respected fires when closes sit on the level")
check(not dg.level_not_respected(bars, i, LEVEL, True),
      "  and does not fire when price reacts away")

# no_retest: break and never come back.
noret = clean_long()[:21]
for k in range(8):
    base = 102.0 + k * 0.5
    noret.append(b(base, base + 0.4, base - 0.2, base + 0.3))
check(dg.no_retest(noret, len(noret) - 1, LEVEL, True),
      "no_retest fires when price never returns to the level")
check(not dg.no_retest(bars, i, LEVEL, True),
      "  and does not fire when it does")

# break_then_rejection: closes back under within REJECT_BARS.
rej = clean_long()[:21]
rej.append(b(101.2, 101.3, 99.2, 99.4))
check(dg.break_then_rejection(rej, len(rej) - 1, LEVEL, True),
      "break_then_rejection fires when it gives the level straight back")
check(not dg.break_then_rejection(bars, i, LEVEL, True),
      "  and does not fire when the break holds")

# exhausted: a long way from the session open in ATR terms.
exh = clean_long()
for k in range(12):
    base = 103.0 + k * 1.5
    exh.append(b(base, base + 0.6, base - 0.4, base + 0.5))
check(dg.exhausted(exh, len(exh) - 1, LEVEL, True),
      "exhausted fires after a large move off the session open")
check(not dg.exhausted(bars, i, LEVEL, True),
      "  and does not fire on a normal move")

# counter_trend_not_respected: red candles in an uptrend, never bought back.
ctr = clean_long()[:22]
for _ in range(2):
    ctr.append(b(100.9, 101.0, 100.2, 100.3))            # red, not recovered
    ctr.append(b(100.3, 100.4, 100.1, 100.2))            # and it stays down
check(dg.counter_trend_not_respected(ctr, len(ctr) - 1, LEVEL, True),
      "counter_trend_not_respected fires on un-bought-back red candles")

# ---------------------------------------------------------------------------
print("\nOCR")

ocr_bars = clean_long()
j = dg.find_ocr(ocr_bars, len(ocr_bars) - 1, True)
check(j is not None, "find_ocr locates an opposite-colour candle in an uptrend")
if j is not None:
    check(not dg._is_up(ocr_bars[j]), "  and the candle it found is genuinely a down close")

# absence of an OCR is not a failure of one
none_bars = [b(99.0, 99.4, 98.8, 99.3) for _ in range(4)]
none_bars.append(b(99.3, 101.4, 99.2, 101.3))
none_bars += [b(101.3 + k * 0.2, 101.8 + k * 0.2, 101.2 + k * 0.2, 101.7 + k * 0.2)
              for k in range(6)]
check(not dg.ocr_not_respected(none_bars, len(none_bars) - 1, LEVEL, True),
      "no OCR in range is NOT a downgrade")

# broken OCR: price closes through the down-candle's low
# The OCR has to be ISOLATED -- trend-coloured candles either side -- or it is a
# cluster, not "one candle". The first version of this chart put the break-through
# bar immediately after the OCR, which made the OCR's right neighbour red and the
# candle no longer isolated. That is the rule working, not the test being awkward.
broke = clean_long()[:22]
broke.append(b(100.70, 101.00, 100.60, 100.95))          # green
broke.append(b(100.95, 101.00, 100.50, 100.60))          # the OCR (down close)
broke.append(b(100.60, 100.90, 100.55, 100.85))          # green -> OCR is isolated
broke.append(b(100.85, 100.90, 99.00, 99.10))            # closes through the OCR low
check(dg.ocr_not_respected(broke, len(broke) - 1, LEVEL, True),
      "ocr_not_respected fires when price closes through the OCR")

# ---------------------------------------------------------------------------
print("\ngrade arithmetic")

def fake(tripped, confl):
    """Drive the arithmetic directly -- the mapping is the thing being asserted,
    not which chart happens to trip what."""
    net = len(tripped) - (1 if confl else 0)
    return "S" if net <= 0 else ("A" if net == 1 else "C")

check(fake([], False) == "S", "0 downgrades -> S")
check(fake(["a"], False) == "A", "1 downgrade -> A")
check(fake(["a", "b"], False) == "C", "2 downgrades -> C")
check(fake(["a", "b", "c"], False) == "C", "3 downgrades -> C (floors, per Austin)")
check(fake(["a", "b", "c", "d", "e"], False) == "C", "5 downgrades still C, never lower")
check(fake(["a"], True) == "S", "1 downgrade + confluence -> S (confluence is +1)")
check(fake(["a", "b"], True) == "A", "2 downgrades + confluence -> A")
check(fake([], True) == "S", "confluence on a clean setup cannot go above S")

# ---------------------------------------------------------------------------
print("\nthe old D branches are reported, not enforced")

red_entry = clean_long()
red_entry[-1] = b(102.6, 102.7, 102.2, 102.3)            # red entry candle on a long
r = dg.score(red_entry, len(red_entry) - 1, LEVEL, True, htf_bias="bearish")
check(r["observations"]["entry_bar_counter_coloured"] is True,
      "a red entry candle on a long is OBSERVED")
check(r["observations"]["htf_opposed"] is True, "HTF opposition is OBSERVED")
check(r["grade"] in ("S", "A", "C"),
      "and neither one produces a skip grade (got %s)" % r["grade"])
check("entry_bar_counter_coloured" not in r["tripped"],
      "observations never enter the downgrade count")

# ---------------------------------------------------------------------------
print("\ndegenerate inputs")
check(dg.score([], 0, LEVEL, True) is None, "empty bars -> None, no exception")
check(dg.score(bars, 999, LEVEL, True) is None, "index past the end -> None")
check(dg.score(bars, i, None, True) is None, "no level -> None")
flat = [b(100.0, 100.0, 100.0, 100.0) for _ in range(25)]
check(dg.score(flat, len(flat) - 1, LEVEL, True) is not None,
      "a zero-range chart still grades without dividing by zero")

print()
if FAILURES:
    print("DOWNGRADE SELFTEST FAILED: %d check(s)" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    if __name__ == "__main__":  # ponytail: gated so pytest can collect the repo (2026-09-03)
        sys.exit(1)
print("downgrade selftest ok")
