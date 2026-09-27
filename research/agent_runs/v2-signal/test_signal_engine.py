"""Tests for the OMEN v2 live paper signal (research/agent_runs/v2-signal/).

Run: python test_signal_engine.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signal_engine import BarWindow, check_for_signal
from discord_format import build_card, SizedCard, PAPER_LABEL
import live_paper_signal as lps


def test_frozen_engine_parity_on_demo_fixture():
    """Same synthetic day orb1m.py's own __main__ test asserts on
    (signal == (8, 1, 100.75)) must fire through the streaming wrapper too --
    proves signal_engine.py did not drift from the frozen t01 engine."""
    window = BarWindow()
    fired = None
    src = lps.DemoBarSource()
    while True:
        bar = src.next_bar()
        if bar is None:
            break
        i, o, h, l, c = bar
        window.update(i, o, h, l, c)
        sig = check_for_signal(window, cutoff="11:00")
        if sig is not None:
            fired = sig
            break
    assert fired is not None, "engine did not fire on its own synthetic fixture"
    assert fired.entry_minute == 8, fired
    assert fired.side == 1, fired
    assert fired.stop == 100.75, fired
    print("PASS: frozen-engine parity (entry_minute=8, side=1, stop=100.75)")


def test_no_signal_before_the_retest_bar_closes():
    """Nothing fires on any bar before bar 8 -- no early/duplicate pushes."""
    window = BarWindow()
    src = lps.DemoBarSource()
    seen_before_8 = []
    for _ in range(8):
        i, o, h, l, c = src.next_bar()
        window.update(i, o, h, l, c)
        seen_before_8.append(check_for_signal(window, cutoff="11:00"))
    assert all(s is None for s in seen_before_8), seen_before_8
    print("PASS: no premature signal")


def test_card_always_labeled_paper():
    card_src = SizedCard(
        symbol="MNQ", contract="MNQZ6", side=1, setup_grade="S", time_et="09:47:00",
        entry=24812.50, stop=24791.25, target=24855.00,
        contracts={"Lucid 50K": 12, "Topstep 50K": 12},
        stop_level_desc="OR5 high retest wick (0.09%)",
        reason="[MNQ] ORB5 high broken, displacement 1.4 ATR, wick retest, pin bar",
        valid_until_et="09:49 open", cutoff_et="10:30", signal_id="S0947-1",
    )
    card = build_card(card_src)
    assert PAPER_LABEL in card["title"]
    assert PAPER_LABEL in card["body"]
    assert "Setup: ORB5" in card["body"]
    assert "Cutoff 10:30 flat" in card["body"]
    assert "Max Loss / Reward" in card["body"]
    # parity with example card msg 1550153955668004945 (#signals 2026-09-17 ORCL S)
    lines = card["body"].splitlines()
    order = ["Setup:", "Contract:", "Entry:", "Stop level:", "Max Loss / Reward:", "TRADE ·",
             "Valid until:", "Omen Signal Bot · Grade S"]
    assert [next(i for i, ln in enumerate(lines) if ln.startswith(k)) for k in order] == list(range(8)), lines
    assert "MNQZ6" in lines[1] and "Target (2R)" in lines[2]
    assert card["priority"] == "urgent" and "green_circle" in card["tags"]
    assert card["click"].endswith("CME_MINI:MNQ1!")
    print("PASS: card always carries PAPER / EXPERIMENTAL label + example field order")


def test_short_side_max_loss_positive_sign():
    card_src = SizedCard(
        symbol="MNQ", contract="MNQZ6", side=-1, setup_grade="S", time_et="09:47:00",
        entry=100.0, stop=104.0, target=92.0,
        contracts={"Lucid 50K": 12}, stop_level_desc="OR5 low retest wick",
        reason="test", valid_until_et="09:49 open", signal_id="S0947-1",
    )
    card = build_card(card_src)
    assert "Max Loss / Reward: -$" in card["body"]
    # position total, like the example card: 12 x (4pt x $2 + 1.24) = $111; 12 x (8pt x $2 - 1.24) = $177
    assert "Max Loss / Reward: -$111 / +$177 (12 cons" in card["body"], card["body"]
    assert "green_circle" in card["tags"]  # color by grade, not side
    print("PASS: short-side sizing formats cleanly")


def test_end_to_end_demo_run_sends_exactly_one_paper_push():
    sent_calls = []

    def fake_push(title, body, priority="default", tags=None, click=None, topic=None):
        sent_calls.append((title, body))
        return True

    lps.ntfy_push = fake_push
    sent = lps.run(lps.DemoBarSource(), symbol="MNQ", cutoff="11:00")
    assert len(sent) == 1, sent
    assert len(sent_calls) == 1, sent_calls
    assert PAPER_LABEL in sent_calls[0][0]
    print("PASS: end-to-end demo run -> exactly one PAPER push")


def test_replay_bar_source_reads_json(tmp_path=None):
    import json
    import tempfile
    n = 91
    arr = {
        "open": [None] * n, "high": [None] * n,
        "low": [None] * n, "close": [None] * n,
    }
    arr["open"][5], arr["high"][5], arr["low"][5], arr["close"][5] = 100.9, 103.0, 100.9, 102.9
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(arr, f)
        path = f.name
    try:
        src = lps.ReplayBarSource(path)
        first = src.next_bar()
        assert first[0] == 0
        assert first[1] != first[1]  # NaN
        for _ in range(4):
            src.next_bar()  # consume indices 1,2,3,4
        sixth = src.next_bar()  # index 5
        assert sixth == (5, 100.9, 103.0, 100.9, 102.9), sixth
    finally:
        os.unlink(path)
    print("PASS: ReplayBarSource reads a bar file correctly")


if __name__ == "__main__":
    test_frozen_engine_parity_on_demo_fixture()
    test_no_signal_before_the_retest_bar_closes()
    test_card_always_labeled_paper()
    test_short_side_max_loss_positive_sign()
    test_end_to_end_demo_run_sends_exactly_one_paper_push()
    test_replay_bar_source_reads_json()
    print("ALL TESTS PASSED")
