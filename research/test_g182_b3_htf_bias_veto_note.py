"""B3 (bug B-03): live_scanner.py's item-4 blocker note named the wrong flag.

It said `HTF_BIAS_GATE` (a different flag in signal_runner.py, default OFF)
gated the top grades and that this "changes nothing on its own" without
saying why. The flag the veto actually routes through is
`omen_bot.HTF_BIAS_VETO` (default ON), which grades 1,699 of 4,022 traded
backtest rows (42.2%, aligned=='against') to D
(research/bt2y_trades_retest_on.json) but can never fire live because
live_scanner's yfinance fallback hardcodes htf_bias=None, and
HTF_BIAS_VETO's `opposed` check (omen_bot.py:255) requires
htf_bias in ('bullish', 'bearish').

This test fails on the pre-fix note (wrong flag name, no 42.2% figure) and
passes on the corrected one. No runtime behaviour changes: HTF_BIAS_VETO's
default and omen_bot.py:255's guard are untouched, so live signal counts and
backtest grades are identical before and after.
"""
import os
import re

import omen_bot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIVE_SCANNER_PATH = os.path.join(ROOT, "live_scanner.py")


def _item4_note():
    with open(LIVE_SCANNER_PATH, "r", encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"^# 4\. HTF bias.*?(?=^# [A-Za-z]|\Z)", text, re.S | re.M)
    assert m, "could not find live_scanner.py's item-4 HTF bias blocker note"
    return m.group(0)


def test_htf_bias_veto_defaults_on():
    # The flag the note must name defaults ON — this is the flag doing the
    # backtest grading, unlike HTF_BIAS_GATE (signal_runner.py, default OFF).
    assert omen_bot.HTF_BIAS_VETO is True


def test_blocker_note_names_the_real_veto_flag_and_its_impact():
    note = _item4_note()
    assert "HTF_BIAS_VETO" in note, (
        "item-4 note must name omen_bot.HTF_BIAS_VETO, the flag that "
        "actually grades traded rows to D"
    )
    assert "42.2%" in note or "42.2" in note, (
        "item-4 note must state the 42.2% traded-row backtest impact"
    )
    # The old wrong claim was that HTF_BIAS_GATE (a different, OFF-by-default
    # flag) is why "this changes nothing" — that reasoning is wrong even
    # though the live conclusion (no live change) is right. The corrected
    # note must attribute the live no-op to the hardcoded None bias /
    # opposed-check guard, not to HTF_BIAS_GATE defaulting off.
    if "HTF_BIAS_GATE" in note:
        gate_sentence = re.search(r"[^.]*HTF_BIAS_GATE[^.]*\.", note).group(0)
        assert "different" in gate_sentence or "unrelated" in gate_sentence, (
            "any mention of HTF_BIAS_GATE in this note must clarify it is "
            "a different flag from the one being vetoed on"
        )
