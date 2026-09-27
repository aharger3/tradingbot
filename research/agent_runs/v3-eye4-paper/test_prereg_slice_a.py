"""Tests for the frozen slice-A pre-registration config (R06).

Asserts the config matches life-plan/07-money/omen-paper-trade-prereg.md
section 1 (slice A) exactly, and that the filter helpers eye_runner.py
wires in behave per section 2's rules.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from prereg_slice_a import (
    PREREG_SLICE_A,
    PreregConfig,
    allowed,
    concurrent_slot_free,
    day_cap_hit,
    day_stop_hit,
    should_halt_day,
)


def test_frozen_values_match_prereg_doc():
    assert PREREG_SLICE_A.slice_id == "A"
    assert PREREG_SLICE_A.allowed_grades == ("S", "A")
    assert PREREG_SLICE_A.max_concurrent_trades == 1
    assert PREREG_SLICE_A.max_trades_per_day == 5
    assert PREREG_SLICE_A.day_stop_r == 1.0


def test_grade_filter_is_s_and_a_only():
    assert allowed("S")
    assert allowed("A")
    assert not allowed("one-off")
    assert not allowed("two-off")
    assert not allowed("candidate")
    assert not allowed("B")


def test_one_at_a_time():
    assert concurrent_slot_free(0)
    assert not concurrent_slot_free(1)
    assert not concurrent_slot_free(2)


def test_max_five_trades_per_day():
    for n in range(5):
        assert not day_cap_hit(n)
    assert day_cap_hit(5)
    assert day_cap_hit(6)


def test_day_stop_at_plus_or_minus_1r():
    assert not day_stop_hit(0.99)
    assert not day_stop_hit(-0.99)
    assert day_stop_hit(1.0)
    assert day_stop_hit(-1.0)
    assert day_stop_hit(1.5)
    assert day_stop_hit(-2.0)


def test_should_halt_day_combines_cap_and_stop():
    assert not should_halt_day(trades_taken_today=2, daily_r=0.3)
    assert should_halt_day(trades_taken_today=5, daily_r=0.3)
    assert should_halt_day(trades_taken_today=2, daily_r=1.0)
    assert should_halt_day(trades_taken_today=2, daily_r=-1.0)


def test_config_hash_is_deterministic_and_sensitive_to_rule_changes():
    h1 = PREREG_SLICE_A.config_hash()
    h2 = PreregConfig().config_hash()
    assert h1 == h2
    assert len(h1) == 12

    changed = PreregConfig(max_trades_per_day=6)
    assert changed.config_hash() != h1
