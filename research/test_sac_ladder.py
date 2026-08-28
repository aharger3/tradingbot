"""W1 -- assert-based check on `signal_runner.ENABLE_SAC_LADDER`.

Four claims, none of which needs the archive or the engine:

  1. the flag ships **OFF**, and `SAC_TIER` has no `B` in its range
  2. the mapping round-trips against `research/t70_test1_score.LADDER`
  3. with the flag OFF `_calibration_grade` still floors the first with-trend
     `C` of the day to `B` -- the behaviour the 2-year byte-identity claim rests
     on, checked here rather than only inferred from a sha256
  4. with the flag ON that floor does not run, the grade comes off the NET
     downgrade count (0/1/2/3+ -> S/A/C/X), and the counter-day-trend cap is
     still applied

    python research/test_sac_ladder.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)


class _Bar:
    """The two fields `_calibration_grade` reads, plus what `_dg_bars` needs."""

    def __init__(self, o, h, l, c, ts, v=1000):
        self.open, self.high, self.low, self.close = o, h, l, c
        self.timestamp, self.volume = ts, v


def _runner(bars):
    """A SignalRunner with only the state `_calibration_grade` touches.

    `__init__` reaches for feeds and level maps, so the object is built without
    it -- this test is about one method, not about construction."""
    import signal_runner as sr
    r = sr.SignalRunner.__new__(sr.SignalRunner)
    r.candles = bars
    r.htf_bias = None
    r._dir_fired = {"call": 0, "put": 0}
    return r


def _bars(n=40, up=True):
    """A plain trending ramp. Enough bars for `downgrade.py` to have an ATR."""
    out = []
    for i in range(n):
        base = 100.0 + (i * 0.10 if up else -i * 0.10)
        hh, mm = divmod(570 + i, 60)          # 09:30 onward
        out.append(_Bar(base, base + 0.06, base - 0.06, base + 0.04,
                        "%02d:%02d:00" % (hh, mm)))
    return out


def _sig(grade="C", direction="call", stop=101.0):
    return {"grade": grade, "direction": direction, "stop": stop, "reason": ""}


def test_default_off_and_no_b():
    import signal_runner as sr
    assert sr.ENABLE_SAC_LADDER is False, "W1 must ship OFF"
    assert sr.SAC_LADDER_REGRADE_ALL is False, "the second arm must ship OFF too"
    assert "B" not in set(sr.SAC_TIER.values()), sr.SAC_TIER
    assert set(sr.SAC_TIER) == {"S", "A", "C", "X"}, sr.SAC_TIER


def test_round_trip_against_the_held_out_scorer():
    """His grade -> engine tier -> his grade is the identity, so the A/B and
    `research/t70_test1_score.py` are counting the same thing."""
    import signal_runner as sr
    from research.t70_test1_score import LADDER
    for his, tier in sr.SAC_TIER.items():
        if his == "X":
            assert tier in ("X", "D"), (his, tier)   # X is a skip, never scored
            continue
        assert LADDER[tier] == his, (his, tier, LADDER.get(tier))


def test_off_arm_still_floors_to_b():
    """The behaviour the byte-identity claim rests on."""
    import signal_runner as sr
    assert sr.ENABLE_SAC_LADDER is False
    r = _runner(_bars())
    s = _sig(grade="C")
    r._calibration_grade(s)
    assert s["grade"] == "B", s
    assert "floor B" in s["reason"], s


def test_on_arm_kills_the_floor_and_grades_off_the_net():
    """Flag ON: no `B`, and the grade is the ladder off `downgrade.score`."""
    import signal_runner as sr
    from research import downgrade as dg
    saved = sr.ENABLE_SAC_LADDER
    sr.ENABLE_SAC_LADDER = True
    try:
        bars = _bars()
        r = _runner(bars)
        s = _sig(grade="C", stop=101.0)
        r._calibration_grade(s)
        assert "floor B" not in s["reason"], s
        assert s["grade"] != "B", s
        assert s["grade"] in ("A+", "A", "C", "X"), s

        # the grade the engine wrote IS the ladder read off the same score()
        rows = [{"o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
                for b in bars]
        rec = dg.score(rows, len(rows) - 1, 101.0, True, htf_bias=None)
        net = rec["net"]
        want = "S" if net <= 0 else ("A" if net == 1 else ("C" if net == 2 else "X"))
        assert s["sac_net"] == net, (s, net)
        assert s["sac_grade"] == want, (s, want)
        assert s["grade"] == sr.SAC_TIER[want], (s, want)
    finally:
        sr.ENABLE_SAC_LADDER = saved


def test_on_arm_leaves_an_incumbent_x_alone():
    """The W1 arm regrades what was TRADEABLE. A `_grade_pa` veto stays vetoed --
    resurrecting those 42,937 signals is R3's lever, not this one."""
    import signal_runner as sr
    saved = (sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL)
    sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL = True, False
    try:
        r = _runner(_bars())
        s = _sig(grade="X")
        r._calibration_grade(s)
        assert s["grade"] == "X", s
        assert "W1" not in s["reason"], s
        assert "sac_grade" not in s, s
    finally:
        sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL = saved


def test_regrade_all_does_touch_an_incumbent_x():
    """...and the second arm is genuinely a different arm, not a dead branch."""
    import signal_runner as sr
    saved = (sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL)
    sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL = True, True
    try:
        r = _runner(_bars())
        s = _sig(grade="X")
        r._calibration_grade(s)
        assert "sac_grade" in s, s
        assert s["grade"] == sr.SAC_TIER[s["sac_grade"]], s
    finally:
        sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_REGRADE_ALL = saved


def test_varset_default_is_shipped_and_w9c_is_a_real_set():
    """W9's set (c) drops the one wrong-signed variable and adds the sequence
    gate. The default must still be the shipped eight, and turning on "w9c" must
    NOT mutate `downgrade.ENABLE_SEQUENCE_GATE`'s committed default."""
    import signal_runner as sr
    from research import downgrade as dg
    assert sr.SAC_LADDER_VARSET == "shipped", sr.SAC_LADDER_VARSET
    assert sr.SAC_VARSET_DROP["shipped"] == frozenset()
    assert sr.SAC_VARSET_DROP["w9c"] == frozenset({"level_not_respected"})
    assert sr.SAC_VARSET_SEQ == {"shipped": False, "w9c": True}
    # every dropped name is a real variable, so a typo cannot silently drop nothing
    for name in sr.SAC_VARSET_DROP["w9c"]:
        assert name in dg.CHECKS, name

    saved = (sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET)
    sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = True, "w9c"
    try:
        r = _runner(_bars())
        s = _sig(grade="C")
        r._calibration_grade(s)
        assert "W1/w9c" in s["reason"], s
        assert dg.ENABLE_SEQUENCE_GATE is False, "the committed default moved"
    finally:
        sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = saved


def test_w9c_actually_drops_the_wrong_signed_variable():
    """A bar set where `level_not_respected` trips must score one lower under
    `w9c` than under `shipped`, or the drop is a no-op wearing a name."""
    import signal_runner as sr
    from research import downgrade as dg
    # a flat tape: many closes sit ON the level, which is what
    # `level_not_respected` means (closes chopping on it, not reacting off it)
    bars = []
    for i in range(40):
        hh, mm = divmod(570 + i, 60)
        bars.append(_Bar(100.0, 100.30, 99.70, 100.0, "%02d:%02d:00" % (hh, mm)))
    rows = [{"o": b.open, "h": b.high, "l": b.low, "c": b.close, "v": b.volume}
            for b in bars]
    level = 100.0
    assert dg.level_not_respected(rows, len(rows) - 1, level, True), \
        "fixture no longer trips the variable this test is about"
    rec = dg.score(rows, len(rows) - 1, level, True)
    shipped_net = rec["net"]
    w9c_net = len([t for t in rec["tripped"] if t != "level_not_respected"]) \
        - (1 if rec["confluence"] else 0)
    assert w9c_net == shipped_net - 1, (shipped_net, w9c_net, rec["tripped"])

    saved = (sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET)
    sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = True, "w9c"
    try:
        r = _runner(bars)
        s = _sig(grade="C", stop=level)
        r._calibration_grade(s)
        # the engine's own net matches the hand-computed one (sequence_gate does
        # not trip on the first entry of the day, so the sets differ by exactly
        # the dropped variable here)
        assert s["sac_net"] == w9c_net, (s, w9c_net)
    finally:
        sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = saved


def test_sequence_gate_counts_every_signal_including_the_vetoed_ones():
    """`_sac_seq` is `annotate_sequence`'s population: every signal that reaches
    the grader on this symbol-day, whatever its incumbent grade."""
    import signal_runner as sr
    saved = (sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET)
    sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = True, "w9c"
    try:
        r = _runner(_bars())
        r._calibration_grade(_sig(grade="X"))       # vetoed, still counted
        r._calibration_grade(_sig(grade="X"))
        s = _sig(grade="C")
        r._calibration_grade(s)
        assert r._sac_seq == 3, r._sac_seq
        assert s["sac_net"] is not None
    finally:
        sr.ENABLE_SAC_LADDER, sr.SAC_LADDER_VARSET = saved


def test_on_arm_x_is_a_skip():
    """3+ net downgrades is `X`, and `X` is in `_SKIP_GRADES` -- the whole
    reason the book shrinks."""
    import signal_runner as sr
    assert "X" in sr._SKIP_GRADES
    assert sr.SAC_TIER["X"] in sr._SKIP_GRADES


def test_on_arm_ungradeable_is_x_not_a_guess():
    import signal_runner as sr
    saved = sr.ENABLE_SAC_LADDER
    sr.ENABLE_SAC_LADDER = True
    try:
        r = _runner(_bars())
        s = _sig(grade="C", stop=None)
        r._calibration_grade(s)
        assert s["grade"] == "X", s
        assert "ungradeable" in s["reason"], s
    finally:
        sr.ENABLE_SAC_LADDER = saved


def test_on_arm_still_caps_counter_day_trend():
    """The cap is a SEPARATE rule and is reapplied in both arms, so the flag
    isolates the ladder."""
    import signal_runner as sr
    saved = sr.ENABLE_SAC_LADDER
    sr.ENABLE_SAC_LADDER = True
    try:
        # a rising tape with a PUT signal = counter day trend
        r = _runner(_bars(up=True))
        s = _sig(grade="C", direction="put", stop=99.0)
        r._calibration_grade(s)
        assert sr._GRADE_RANK[s["grade"]] <= sr._GRADE_RANK["C"], s
        if s["grade"] == "C":
            assert "capped C: counter day trend" in s["reason"], s
    finally:
        sr.ENABLE_SAC_LADDER = saved


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok  %s" % t.__name__)
    print("%d/%d passed" % (len(tests), len(tests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
