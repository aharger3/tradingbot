#!/usr/bin/env python3
"""test_no_repeat.py -- plain asserts, no pytest. Run: `python3 test_no_repeat.py`.

Covers the no-repeat-entries rule shipped in omen-4.0 / T6:
  * NO_REPEAT_ENTRIES defaults True (engine enforces it in production).
  * a second accepted entry on the same symbol+direction+level is suppressed
    when the flag is on; both fire when it is off.
  * an armed 84% re-entry (SignalType.REENTRY_84_RULE) is EXEMPT -- it is by
    definition the sanctioned second bite at the same idea, so it fires on a
    level already taken even with the flag on.

Exercises signal_runner.SignalRunner._route directly with crafted signals so
the no-repeat branch is reached in isolation (a real B&R FSM fire is not needed
to prove the routing rule).
"""
import signal_runner
from signal_runner import SignalRunner
from omen_bot import Candle, SignalType


def _bullish_candles(n=15):
    """Flat-ish bullish series: last close >= first open, timestamps 9:30-9:44,
    small ranges so a 5%-wide stop clears _min_viable_stop cleanly."""
    bars = []
    for i in range(n):
        ts = f"09:{30 + i:02d}:00"
        bars.append(Candle(timestamp=ts, open=100.0, high=100.4,
                           low=99.9, close=100.1 + i * 0.01, volume=1000))
    return bars


def _sig(level=95.0, stype=SignalType.BREAK_AND_RETEST, direction="call"):
    """A B-grade accepted signal retesting `level` (stop == the level price)."""
    return {
        "signal_type": stype,
        "reason": "test signal",
        "entry": 100.0,
        "stop": level,
        "direction": direction,
        "grade": "B",
        "stop_level_name": "OR high",
        "stop_width_pct": 5.0,
    }


def _runner():
    r = SignalRunner(post_to_discord=False, symbol="TST", log_signals=False)
    r.candles = _bullish_candles()
    r._active_levels = []          # _grade_for_levels no-op
    r.htf_bias = None              # no HTF opposition
    return r


# --- default is ON (the rule is settled and ships enforced) ---
assert signal_runner.NO_REPEAT_ENTRIES is True, \
    "NO_REPEAT_ENTRIES must default True (settled 2026-08-09)"


# --- flag OFF: two entries on the same level both fire ---
signal_runner.NO_REPEAT_ENTRIES = False
r = _runner()
sigs = []
r._route(sigs, _sig(level=95.0))
r._route(sigs, _sig(level=95.0))   # same symbol+direction+level
assert len(sigs) == 2, f"flag OFF: both must fire, got {len(sigs)}"


# --- flag ON: the second same-level entry is suppressed ---
signal_runner.NO_REPEAT_ENTRIES = True
r = _runner()
sigs = []
r._route(sigs, _sig(level=95.0))
r._route(sigs, _sig(level=95.0))   # duplicate -> suppressed
assert len(sigs) == 1, f"flag ON: duplicate must be suppressed, got {len(sigs)}"
assert ("call", 95.0) in {(k[1], k[2]) for k in r._fired_levels}, \
    "the accepted entry must record its level price"


# --- a DIFFERENT level on the same side still fires (different idea) ---
r = _runner()
sigs = []
r._route(sigs, _sig(level=95.0))
r._route(sigs, _sig(level=90.0))   # different level price -> different idea
assert len(sigs) == 2, f"different level must still fire, got {len(sigs)}"


# --- the other DIRECTION on the same level still fires (different idea) ---
r = _runner()
sigs = []
r._route(sigs, _sig(level=95.0, direction="call"))
r._route(sigs, _sig(level=95.0, direction="put"))
assert len(sigs) == 2, f"other direction must still fire, got {len(sigs)}"


# --- armed 84% re-entry is EXEMPT: fires on a level already taken ---
r = _runner()
sigs = []
r._route(sigs, _sig(level=95.0))                              # first, claims level
r._route(sigs, _sig(level=95.0,
                     stype=SignalType.REENTRY_84_RULE))       # 84% second bite
assert len(sigs) == 2, f"84% re-entry must be exempt, got {len(sigs)}"

signal_runner.NO_REPEAT_ENTRIES = True   # restore default
print("OK: no-repeat-entries suppresses duplicates, exempts 84% re-entry")
