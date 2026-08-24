"""ON WATCH fill-rule selftest (OMEN 6 ticket 18, corrected 2026-08-23).

Austin, on the two pieces added most recently:

    concerns are the on-watch and scratch pieces we've added ... there could be
    a lot of bugs that arise, and i'm very concerned about how the backtests
    will play out to the results

Fair. The -12.46R defect was exactly this shape: a rule that read correctly and
was wired wrong, sitting under every published number for a version. So the fill
rule gets a test before it gets trusted, and the test asserts the INVARIANTS
rather than restating the implementation.

The rule under test, in his words (2026-08-23):

    you can't make your decision based on the previous candle, but you can enter
    on the candle you want to enter at candle close if it's one of those that
    are too close to the high for the day

So: the close still decides WHETHER. This decides whether the close is a fair
FILL. Synthetic candles only, no archive.

    python research/test_onwatch_fill.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from omen_bot import Candle                                    # noqa: E402
import signal_runner as sr                                     # noqa: E402

FAILURES = []


def check(cond, label):
    if cond:
        print("  ok    %s" % label)
    else:
        print("  FAIL  %s" % label)
        FAILURES.append(label)


def bar(o, h, l, c):
    return Candle(timestamp="09:45:00", open=o, high=h, low=l, close=c, volume=1000)


# ---------------------------------------------------------------------------
# near_session_extreme -- the trigger for the whole rule
# ---------------------------------------------------------------------------
print("near_session_extreme")

# Session 100-110, band = 25% of 10 = 2.5, so a long is "near" at close >= 107.5
LO, HI = 100.0, 110.0

check(sr.near_session_extreme(bar(107, 109, 106, 108.0), True, HI, LO),
      "long: close 108 inside the top 25% of the session is near")
check(not sr.near_session_extreme(bar(103, 105, 102, 104.0), True, HI, LO),
      "long: close 104 mid-session is not near")
check(sr.near_session_extreme(bar(108, 109, 107, 107.5), True, HI, LO),
      "long: exactly on the band edge counts as near")
check(not sr.near_session_extreme(bar(108, 109, 107, 107.49), True, HI, LO),
      "long: a hair outside the band does not")

check(sr.near_session_extreme(bar(103, 104, 101, 102.0), False, HI, LO),
      "short: close 102 inside the bottom 25% is near")
check(not sr.near_session_extreme(bar(107, 108, 105, 106.0), False, HI, LO),
      "short: close 106 mid-session is not near")

# Degenerate inputs must be quiet, not explosive: a missing session extreme or a
# zero-range session cannot say where the close sits, so it never triggers.
check(not sr.near_session_extreme(bar(107, 109, 106, 108.0), True, None, LO),
      "no session high -> not near, no exception")
check(not sr.near_session_extreme(bar(107, 109, 106, 108.0), True, HI, None),
      "no session low -> not near, no exception")
check(not sr.near_session_extreme(bar(100, 100, 100, 100.0), True, 100.0, 100.0),
      "zero-range session -> not near, no divide-by-zero")

# ---------------------------------------------------------------------------
# fill_price -- what the rule actually changes
# ---------------------------------------------------------------------------
print("\nfill_price")

LEVEL = 103.0

# Mid-session bar whose close is NOT at its own extreme: nothing fires, and the
# fill is the close exactly as before ON WATCH existed. This is the regression
# guard -- the new rule must be invisible on ordinary bars.
mid = bar(103.2, 105.0, 102.0, 103.4)
check(sr.fill_price(LEVEL, mid, True, session_hi=HI, session_lo=LO) == mid.close,
      "ordinary mid-session bar still fills at the close")
check(sr.fill_price(LEVEL, mid, True) == mid.close,
      "and does so when no session extremes are passed at all")

# Bar closing hard against the SESSION high. Its close sits mid-bar, so the old
# bar-extreme veto would NOT have fired -- only ON WATCH catches this one.
at_hod = bar(107.6, 109.6, 107.4, 108.4)
check(not sr.bar_extreme_veto({"entry": at_hod.close, "direction": "call"}, at_hod),
      "the session-high bar does NOT trip the old bar-extreme veto")
filled = sr.fill_price(LEVEL, at_hod, True, session_hi=HI, session_lo=LO)
check(filled != at_hod.close, "so ON WATCH is what moves this fill")
check(filled == at_hod.low,
      "fill clamps to the bar's low: the level is below everything this bar traded")

# The clamp is the safety property that matters: Austin can never be filled at a
# price the bar never printed, whatever the level says.
far = bar(107.6, 109.6, 107.4, 108.4)
for lvl in (50.0, 103.0, 108.0, 200.0):
    f = sr.fill_price(lvl, far, True, session_hi=HI, session_lo=LO)
    check(far.low <= f <= far.high,
          "level %.0f -> fill %.2f stays inside the bar's range" % (lvl, f))

# Short side, closing on the session low.
at_lod = bar(102.4, 102.6, 100.4, 101.6)
f_short = sr.fill_price(107.0, at_lod, False, session_hi=HI, session_lo=LO)
check(f_short != at_lod.close, "short: a close on the session low moves the fill")
check(at_lod.low <= f_short <= at_lod.high, "short: fill stays inside the bar")

# ON_WATCH=0 must restore the old behaviour byte for byte.
old = sr.ON_WATCH
try:
    sr.ON_WATCH = False
    check(sr.fill_price(LEVEL, at_hod, True, session_hi=HI, session_lo=LO) == at_hod.close,
          "ON_WATCH=0 restores the pre-2026-08-23 fill (the close)")
finally:
    sr.ON_WATCH = old
check(sr.ON_WATCH is old, "the flag was restored after the A/B")

# ---------------------------------------------------------------------------
# scratch -- the other piece he flagged
# ---------------------------------------------------------------------------
print("\nscratch semantics")

import backtest_week as bw                                     # noqa: E402

# omen-5.0 T4(c): only a close-based FULL stop-out arms the 84% rule. A scratch
# is Austin deciding the setup was never there, not the market taking him out,
# so it must never arm a re-entry. If this ever flips, the 84% rule starts
# firing on days he simply changed his mind.
class _Session:
    def __init__(self):
        self.entry_price = None
        self.entry_direction = None
        self.entry_target = None
        self.entry_stop = None


class _Runner:
    def __init__(self):
        self.session = _Session()


for outcome in ("scratch", "win", "open"):
    t = bw.SimTrade(symbol="TSLA", signal_type=None, grade="A", status="fired",
                    day="2026-08-24", entry_time="09:45:00", entry=100.0,
                    stop=99.0, target=102.0,
                    reason="test", direction="call")
    t.outcome = outcome
    r = _Runner()
    bw._arm_84(t, r)
    check(r.session.entry_price is None,
          "outcome=%-8s does not arm the 84%% rule" % outcome)

print()
if FAILURES:
    print("ON WATCH / SCRATCH SELFTEST FAILED: %d check(s)" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("on-watch/scratch selftest ok")
