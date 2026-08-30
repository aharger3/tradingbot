"""R3 -- the flag routes grading to downgrade.score() on, _grade_pa off.

`signal_runner.ENABLE_DOWNGRADE_GRADER` (default False) changes exactly one
thing: which grader the ten detection sites ask for a base grade. This asserts
that sentence in both directions, and that nothing else moved.

Not a framework: plain asserts, exits non-zero on failure, same shape as
`research/test_structural_floor.py`.

    python research/test_downgrade_grader.py

Four legs, because any one alone would still pass on a broken wiring:

  1. THE ROUTING. Both graders are wrapped with a call recorder. With the flag
     off, `PriceActionAnalyzer._grade_pa` is called and `downgrade.score` is
     not; with it on, exactly the reverse. This is the check the ticket asks
     for, and it is an observation of who ran, not of what came back.
  2. THE DEFAULT is False, and the ON arm's tier alphabet is the same one
     `_grade_pa` can emit -- so no downstream `grade.value in ("A+", "A")` cap
     ever sees a tier the shipped grader never makes.
  3. THE LADDER round-trips against `research/t70_test1_score.py`'s own
     declared engine->his mapping. `DOWNGRADE_TIER` is its inverse or the two
     reports are counting different things.
  4. THE CALL SITES, end to end, through the same `t4_engine_recall.run_day`
     replay `research/regression_gate.py` runs. Legs 1-3 would all pass if
     `_grade_trade` were never wired into `detect_signals`.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import omen_bot                                          # noqa: E402
import signal_runner as sr                               # noqa: E402
import t4_engine_recall as t4                            # noqa: E402
from omen_bot import Candle, TradeGrade                  # noqa: E402
from research import downgrade as dg                     # noqa: E402
from research.t70_test1_score import LADDER              # noqa: E402

# A plain rising staircase with one pullback: enough bars for downgrade.py's
# 30-bar break scan and _grade_pa's lookback, and no claim is made about what
# grade either grader SHOULD return on it. Leg 1 asks who was called, never
# what they said -- a fixture chosen to produce a particular letter would be
# this test grading the grader instead of checking the wire.
def _fixture(n=40, base=100.0):
    bars = []
    for i in range(n):
        o = base + 0.10 * i
        c = o + (0.08 if i % 5 else -0.06)
        bars.append(Candle(timestamp="2026-01-01T09:%02d:00" % (30 + i % 29),
                           open=round(o, 4), high=round(max(o, c) + 0.05, 4),
                           low=round(min(o, c) - 0.05, 4), close=round(c, 4),
                           volume=1000 + i))
    return bars


BARS = _fixture()
LEVEL_HI = BARS[-6].high
LEVEL_LO = BARS[-6].low

# The end-to-end probe. Any archived symbol-day the gate already replays does;
# this one is `research/g13_floor_fix_ab.md`'s own worked example, so the bars
# are known to exist wherever that report could be reproduced.
DAY = ("GOOGL", "2024-10-15")


class Spy:
    """Wrap a callable and remember whether it ran. Returns the real answer --
    the routing must be observed on the live path, not on a stub of it."""

    def __init__(self, fn):
        self.fn, self.calls = fn, 0

    def __call__(self, *a, **kw):
        self.calls += 1
        return self.fn(*a, **kw)


def _route_once(flag: bool):
    """One `_grade_trade` call with the flag forced, both graders watched."""
    runner = sr.SignalRunner(post_to_discord=False, symbol="TEST",
                             log_signals=False)
    runner.candles = BARS
    pa = Spy(omen_bot.PriceActionAnalyzer._grade_pa)
    score = Spy(dg.score)
    was_flag = sr.ENABLE_DOWNGRADE_GRADER
    try:
        omen_bot.PriceActionAnalyzer._grade_pa = staticmethod(pa)
        dg.score = score
        sr.ENABLE_DOWNGRADE_GRADER = flag
        grade = runner._grade_trade(BARS[-1], BARS[-6:-1], LEVEL_HI, LEVEL_LO,
                                    is_long=True, htf_bias=None)
    finally:
        sr.ENABLE_DOWNGRADE_GRADER = was_flag
        omen_bot.PriceActionAnalyzer._grade_pa = staticmethod(pa.fn)
        dg.score = score.fn
    return grade, pa.calls, score.calls


def fired_tiers(sym, day):
    """The engine tiers fired on a symbol-day, through the gate's own replay."""
    ent, _sigs, _raw = t4.run_day(sym, day)
    assert ent is not None, (
        "no archived bars for %s %s -- data_archive/ is required to run this "
        "check; it cannot be answered from code alone" % (sym, day))
    return sorted(e.get("grade") for e in ent)


def main():
    # ---- leg 2: the default, and the alphabet ----------------------------
    assert sr.ENABLE_DOWNGRADE_GRADER is False, (
        "the shipped default must be False -- R3 is Austin's call, and "
        "re-freezing the engine voids research/omen6_forward.py")
    assert set(sr.DOWNGRADE_TIER) == {"S", "A", "C"}, (
        "downgrade.score() floors at C and has no X; every grade it can emit "
        "must have a tier here: %s" % sr.DOWNGRADE_TIER)
    pa_alphabet = {"A", "B", "C", "X"}       # every return of _grade_pa (A+ retired 2026-08-30)
    assert set(sr.DOWNGRADE_TIER.values()) <= pa_alphabet, (
        "the ON arm must emit from the same alphabet as the shipped grader, or "
        "a downstream cap sees a tier _grade_pa never makes: %s"
        % sorted(set(sr.DOWNGRADE_TIER.values()) - pa_alphabet))
    for letter in sr.DOWNGRADE_TIER.values():
        TradeGrade(letter)                   # every tier must be a real grade

    # ---- leg 3: the ladder round-trips against t70's own mapping ---------
    for his, tier in sr.DOWNGRADE_TIER.items():
        assert LADDER[tier] == his, (
            "DOWNGRADE_TIER must be the inverse of t70_test1_score.LADDER, or "
            "the A/B and the held-out scorer are counting different things: "
            "his %s -> engine %s -> his %s" % (his, tier, LADDER[tier]))
    assert sr.DOWNGRADE_TIER["A"] != sr.DOWNGRADE_TIER["S"], (
        "his A and his S must land on different engine letters or they are "
        "no longer distinguishable to a downstream cap reading sig['grade']; "
        "got A -> %s, S -> %s" % (sr.DOWNGRADE_TIER["A"], sr.DOWNGRADE_TIER["S"]))

    # ---- leg 1: THE ROUTING ---------------------------------------------
    off_grade, off_pa, off_score = _route_once(False)
    on_grade, on_pa, on_score = _route_once(True)

    assert off_pa == 1 and off_score == 0, (
        "flag OFF must grade through PriceActionAnalyzer._grade_pa and must "
        "NOT call downgrade.score: _grade_pa x%d, score x%d" % (off_pa, off_score))
    assert on_score == 1 and on_pa == 0, (
        "flag ON must grade through downgrade.score and must NOT call "
        "_grade_pa: _grade_pa x%d, score x%d" % (on_pa, on_score))
    assert isinstance(off_grade, TradeGrade) and isinstance(on_grade, TradeGrade)
    assert on_grade.value in pa_alphabet, on_grade

    # the wrapper grade_trade puts around _grade_pa is reapplied on the ON arm,
    # so the arm is a swap of the GRADER and not also a lift of the veto
    was = sr.ENABLE_DOWNGRADE_GRADER
    try:
        sr.ENABLE_DOWNGRADE_GRADER = True
        runner = sr.SignalRunner(post_to_discord=False, symbol="TEST",
                                 log_signals=False)
        runner.candles = BARS
        opposed = runner._grade_trade(BARS[-1], BARS[-6:-1], LEVEL_HI, LEVEL_LO,
                                      is_long=True, htf_bias="bearish")
        if omen_bot.HTF_BIAS_VETO:
            assert opposed is TradeGrade.D, (
                "with HTF_BIAS_VETO on, an opposed bias must still skip on the "
                "ON arm -- the veto is grade_trade's wrapper, not _grade_pa, "
                "and this flag replaces only the base grade; got %s" % opposed)
        neutral = runner._grade_trade(BARS[-1], BARS[-6:-1], LEVEL_HI, LEVEL_LO,
                                      is_long=True, htf_bias="neutral")
        assert neutral.value not in ("A+", "A"), (
            "a neutral HTF hour must cap at B on the ON arm exactly as it does "
            "on the OFF arm; got %s" % neutral)
        # and downgrade.score() has no X: the base can never be a skip
        base = runner._downgrade_grade(LEVEL_HI, True, None)
        assert base.value in ("A", "B", "C"), (
            "downgrade.py floors at C -- the base grade is never a skip; got %s"
            % base)
        # score() cannot judge without a level, and that is a skip, not a guess
        assert runner._downgrade_grade(None, True, None) is TradeGrade.D
    finally:
        sr.ENABLE_DOWNGRADE_GRADER = was

    # ---- leg 4: the call sites, end to end -------------------------------
    sym, day = DAY
    sr.ENABLE_DOWNGRADE_GRADER = False
    off_tiers = fired_tiers(sym, day)
    sr.ENABLE_DOWNGRADE_GRADER = True
    try:
        on_tiers = fired_tiers(sym, day)
    finally:
        sr.ENABLE_DOWNGRADE_GRADER = was
    assert off_tiers != on_tiers, (
        "%s %s fires identically in both arms -- if a whole session cannot "
        "tell the two graders apart, _grade_trade is not wired into "
        "detect_signals. off=%s on=%s" % (sym, day, off_tiers, on_tiers))

    print("downgrade grader ok: flag OFF -> _grade_pa x%d / score x%d (%s), "
          "flag ON -> _grade_pa x%d / score x%d (%s); ladder %s round-trips; "
          "%s %s fires %s off vs %s on"
          % (off_pa, off_score, off_grade.value, on_pa, on_score, on_grade.value,
             sr.DOWNGRADE_TIER, sym, day, off_tiers or "nothing",
             on_tiers or "nothing"))


if __name__ == "__main__":
    main()
