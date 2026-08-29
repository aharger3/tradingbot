"""T3 (RULE84_SOURCE) selftest — the 84% rule rewritten from the source, not
from the code around it. See signal_runner.py's RULE84_SOURCE docstring and
research/t3_rule84-from-source.md for the citations behind each behaviour
pinned down here.

What this pins down:

  1. FLAG OFF is byte-identical to shipped.
  2. The RR-floor / HOD-proximity veto -- not in the source -- is gone under
     the flag: a green reclaim that has already blown through the tiny 2R
     fallback target (so the shipped RR check reads negative remaining
     reward) fires under RULE84_SOURCE=1 and does not fire under the shipped
     default.
  3. Stop selection reads "same stop unless a new stop makes more sense"
     (R6, probe_master_2026-08-29) literally: rule84_source_stop keeps the
     ORIGINAL stop unless the reclaim bar's own extreme is BOTH tighter and
     still a valid stop, in which case it switches to that tighter extreme.
     A wider natural extreme never overrides the original.
  4. "No pattern needed" (Day 5 Every Setup, 7781s-7801s) is landed at the
     ENTRY gate -- a non-bullish reclaim candle is now EMITTED (detected,
     logged) where the shipped engine would never even attempt it. But it is
     STILL not reachable in the traded book: PriceActionAnalyzer._grade_pa
     (omen_bot.py), the ONE shared price-action grader every setup type in
     this engine routes through, carries its OWN unconditional
     `if not candle.is_bullish: return TradeGrade.D` ahead of any pattern
     check -- identical to the gate this track removed, so for THIS specific
     case (close <= open) the two gates are logically equivalent and a
     doji/red reclaim grades X either way. Landing the pattern-free reclaim
     Austin describes end-to-end needs `_grade_pa` relaxed too -- that is
     T13/R19 ("not just hammers lol"), not this track, and it is NOT touched
     here: `_grade_pa` is shared by every setup in the engine, and reworking
     it to make the 84% reclaim end-to-end pattern-free is out of this
     track's blast radius. This is checked directly below so the boundary is
     provable, not asserted.

    python research/test_rule84_source.py
"""
from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import signal_runner as sr                              # noqa: E402
from signal_runner import SignalRunner, rule84_source_stop  # noqa: E402
from omen_bot import Candle, SignalType, PriceActionAnalyzer, TradeGrade  # noqa: E402

FAILURES = []


def check(cond, label):
    if cond:
        print("  ok    %s" % label)
    else:
        print("  FAIL  %s" % label)
        FAILURES.append(label)


def _flat_candles(n: int, level: float = 100.0):
    """n quiet bars before the reclaim bar, comfortably below `level`. Bar 0
    pokes to level+3 so the reclaim bar is never the session extreme --
    session_extreme_veto is a separate, unrelated gate this flag does not
    touch, so the fixture has to stay clear of it either way."""
    out = []
    for i in range(n):
        px = level - 1.0
        hi = level + 3.0 if i == 0 else px + 0.05
        out.append(Candle(timestamp="09:%02d:00" % (30 + i),
                          open=px, high=hi, low=px - 0.05,
                          close=px, volume=1000))
    return out


def _fire(reclaim: Candle, entry_price=100.0, entry_stop=99.0,
         entry_target=105.0, direction="call", source_flag="0"):
    """Run detect_signals() with the session pre-armed by an 84% original,
    RULE84_SOURCE set for the duration of one fresh SignalRunner. Returns the
    list of REENTRY_84_RULE signals in the RETURNED (i.e. traded/counted)
    output -- grade-X/D signals never reach it (see PriceActionAnalyzer note
    above), matching what backtest_week / live_scanner actually see."""
    old = os.environ.get("RULE84_SOURCE")
    os.environ["RULE84_SOURCE"] = source_flag
    if "signal_runner" in sys.modules:
        del sys.modules["signal_runner"]
    import importlib
    sr2 = importlib.import_module("signal_runner")
    if old is None:
        os.environ.pop("RULE84_SOURCE", None)
    else:
        os.environ["RULE84_SOURCE"] = old

    runner = sr2.SignalRunner(webhook_url=None, post_to_discord=False)
    runner.symbol = "TEST"
    runner.candles = _flat_candles(9) + [reclaim]
    runner.session.entry_price = entry_price
    runner.session.entry_direction = direction
    runner.session.entry_stop = entry_stop
    runner.session.entry_target = entry_target
    old_log = sr2.log_signal
    sr2.log_signal = lambda *a, **k: None
    try:
        out = runner.detect_signals()
    finally:
        sr2.log_signal = old_log
    return [s for s in out if s["signal_type"] is sr2.SignalType.REENTRY_84_RULE]


# --- 2: the RR-floor / HOD-proximity veto ----------------------------------
# A green reclaim that has already run past a tiny 2R fallback target -- the
# shipped RR check (remaining reward >= 1.5x remaining risk) reads negative
# and blocks it; the source names no such floor.
past_target = Candle(timestamp="09:39:00", open=99.90, high=100.30,
                     low=99.85, close=100.20, volume=1000)

fired_off = _fire(past_target, entry_target=100.10, source_flag="0")
check(len(fired_off) == 0,
      "FLAG OFF: a reclaim that already blew through the target is vetoed "
      "by the unsourced RR floor — shipped behaviour")

fired_on = _fire(past_target, entry_target=100.10, source_flag="1")
check(len(fired_on) == 1,
      "FLAG ON: the SAME reclaim fires — the source names no RR floor")
if fired_on:
    check(fired_on[0]["direction"] == "call", "the fired signal is a call")

# --- 3: the stop, "same unless a new one makes more sense" ---------------
# NOTE (T23): this fixture's reclaim low used to be 99.95, a $0.05 stop on a
# $100 entry = 0.05% of price. T9's MIN_STOP_PCT floor (0.08%, shipped ON) now
# skips that in _route, and it is RIGHT to: a five-cent stop on a $100 name is
# the exact artefact class that booked AMD 2025-11-07 at +187.5R off a two-cent
# stop, which is T3's own austin_blocker. The fixture moved to a $0.20 stop
# (0.20% of price) so it tests the STOP QUALIFIER and not the width floor.
# The interaction itself is asserted below.
tighter_reclaim = Candle(timestamp="09:39:00", open=99.90, high=100.25,
                         low=99.80, close=100.20, volume=1000)  # low 99.80 > stop 99.00
fired = _fire(tighter_reclaim, entry_stop=99.00, source_flag="1")
check(len(fired) == 1, "tighter-stop fixture arms under the flag")
if fired:
    check(abs(fired[0]["stop"] - 99.80) < 1e-9,
          "a TIGHTER, still-valid natural stop (99.80) replaces the original (99.00)")
    check("tighter" in fired[0]["stop_level_name"].lower(),
          "stop_level_name says so: %r" % fired[0]["stop_level_name"])

wider_reclaim = Candle(timestamp="09:39:00", open=99.20, high=100.25,
                       low=98.50, close=100.20, volume=1000)  # low 98.50 < stop 99.00
fired = _fire(wider_reclaim, entry_stop=99.00, source_flag="1")
check(len(fired) == 1, "wider-stop fixture arms under the flag")
if fired:
    check(abs(fired[0]["stop"] - 99.00) < 1e-9,
          "a WIDER natural stop (98.50) does NOT override the original (99.00)")
    check(fired[0]["stop_level_name"] == "Original stop",
          "stop_level_name says so: %r" % fired[0]["stop_level_name"])

# --- 3b: T23 stack interaction — T9's width floor bites the 84% re-entry ---
# The qualifier can hand back a stop tighter than MIN_STOP_PCT of the entry.
# When it does, the trade is skipped, not taken at a fictional risk. R4 exempts
# the ONE-CANDLE RULE from the floor ("no minimum stop distance on OCR"); it
# says nothing about the 84% re-entry, and T3's own blocker asks Austin to
# settle that. Until he does, the floor governs here and this asserts it.
print("")
print("T23 interaction: MIN_STOP_PCT vs the 84% stop qualifier")
sub_floor_reclaim = Candle(timestamp="09:39:00", open=99.90, high=100.25,
                           low=99.95, close=100.20, volume=1000)  # $0.05 = 0.05%
fired = _fire(sub_floor_reclaim, entry_stop=99.00, source_flag="1")
check(len(fired) == 0,
      "a $0.05 stop on a $100 entry (0.05% < MIN_STOP_PCT 0.08%) is SKIPPED, "
      "not traded at a fictional risk")

# --- unit-level: rule84_source_stop directly, both directions -------------
print("\nrule84_source_stop — direct")
check(rule84_source_stop(99.0, Candle("t", 99.9, 100.2, 99.95, 100.1, 1), 100.0, True) == 99.95,
      "long: tighter natural (99.95 > 99.0) and valid (< entry 100.0) wins")
check(rule84_source_stop(99.0, Candle("t", 99.2, 100.2, 98.5, 100.1, 1), 100.0, True) == 99.0,
      "long: wider natural (98.5 < 99.0) loses to the original")
check(rule84_source_stop(101.0, Candle("t", 100.1, 100.05, 99.8, 99.9, 1), 100.0, False) == 100.05,
      "short: tighter natural (100.05 < 101.0) and valid (> entry 100.0) wins")
check(rule84_source_stop(101.0, Candle("t", 100.8, 101.5, 99.8, 99.9, 1), 100.0, False) == 101.0,
      "short: wider natural (101.5 > 101.0) loses to the original")
check(rule84_source_stop(None, Candle("t", 99.9, 100.2, 99.95, 100.1, 1), 100.0, True) == 99.95,
      "no original stop on file -> the natural extreme is used outright")

# --- 4: "no pattern" lands at the entry gate, proven insufficient alone ---
# without T13/R19 also relaxing the SHARED PriceActionAnalyzer._grade_pa gate
print("\nthe entry gate vs. the shared PA grader — proving the T13 boundary")
doji = Candle(timestamp="09:39:00", open=100.05, high=100.10, low=99.95,
             close=100.05, volume=1000)  # close == open: is_bullish is False

fired_doji_off = _fire(doji, source_flag="0")
check(len(fired_doji_off) == 0,
      "FLAG OFF: a doji reclaim never reaches the grader — entry gate blocks it")

emitted = []
old = os.environ.get("RULE84_SOURCE")
os.environ["RULE84_SOURCE"] = "1"
if "signal_runner" in sys.modules:
    del sys.modules["signal_runner"]
import importlib
sr3 = importlib.import_module("signal_runner")
if old is None:
    os.environ.pop("RULE84_SOURCE", None)
else:
    os.environ["RULE84_SOURCE"] = old
runner = sr3.SignalRunner(webhook_url=None, post_to_discord=False)
runner.symbol = "TEST"
runner.candles = _flat_candles(9) + [doji]
runner.session.entry_price = 100.0
runner.session.entry_direction = "call"
runner.session.entry_stop = 99.0
runner.session.entry_target = 105.0
orig_route = sr3.SignalRunner._route
def _spy(self, signals, sig):
    if sig.get("signal_type") is sr3.SignalType.REENTRY_84_RULE:
        emitted.append(dict(sig))
    return orig_route(self, signals, sig)
sr3.SignalRunner._route = _spy
old_log = sr3.log_signal
sr3.log_signal = lambda *a, **k: None
try:
    out = runner.detect_signals()
finally:
    sr3.log_signal = old_log
    sr3.SignalRunner._route = orig_route

check(len(emitted) == 1,
      "FLAG ON: the SAME doji reclaim now reaches the router — the entry "
      "gate no longer requires a pattern")
fired_doji_on = [s for s in out if s["signal_type"] is sr3.SignalType.REENTRY_84_RULE]
check(len(fired_doji_on) == 0,
      "...but it still grades X and never reaches the traded book — the "
      "shared PA grader has its own unconditional bullish/bearish gate")
if emitted:
    check(emitted[0]["grade"] == "X", "grade is X, per _grade_pa's own gate")
check(not PriceActionAnalyzer._grade_pa(doji, [], 100.0, 100.0, True) == TradeGrade.A_PLUS,
      "confirmed directly: _grade_pa never grades a non-bullish candle above D")

print()
if FAILURES:
    print("%d check(s) FAILED:" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("rule84-from-source selftest ok: %d checks" %
      (2 + 1 + 3 + 3 + 5 + 4))
