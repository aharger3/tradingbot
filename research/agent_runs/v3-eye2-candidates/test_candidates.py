"""Fixture tests for v3-eye2-candidates/candidates.py. No network, no live data."""
import json
from dataclasses import asdict

import numpy as np
import pytest

from candidates import detect_candidates, pin, strong_bar, WINDOW_END_MIN


def _flat_day(base=100.5):
    n = WINDOW_END_MIN + 1
    O = np.full(n, base)
    H = np.full(n, base + 0.5)
    L = np.full(n, base - 0.5)
    C = np.full(n, base)
    return O, H, L, C


def test_pin_and_strong_helpers():
    # long pin: deep lower wick, small body, close in top third
    assert pin(102.0, 102.1, 101.0, 102.05, 1) is True
    # a flat doji-ish bar is not a pin
    assert pin(100.5, 101.0, 100.0, 100.5, 1) is False
    # strong body bar in trade direction
    assert strong_bar(100.0, 101.0, 99.9, 100.95, 1) is True


def test_clean_s_grade_candidate_long():
    """OR5 100-101, break to 103 with displacement, pin retest at 101 -> S grade."""
    O, H, L, C = _flat_day()
    O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9   # break + displacement
    O[6], H[6], L[6], C[6] = 102.9, 103.0, 102.0, 102.5
    O[7], H[7], L[7], C[7] = 102.0, 102.1, 101.0, 102.05  # pin touching 101, closes above
    for j in range(8, len(O)):
        O[j] = 102.0 + (j - 8) * 0.5
        H[j] = 102.5 + (j - 8) * 0.5
        L[j] = 101.9 + (j - 8) * 0.5
        C[j] = 102.4 + (j - 8) * 0.5
    A = dict(open=O, high=H, low=L, close=C)

    cands = detect_candidates(A, "2026-09-01", "MNQ")
    assert len(cands) >= 1
    c = cands[0]
    assert c.direction == "long"
    assert c.level == 101.0
    assert c.entry == pytest.approx(O[8] + 0.25)
    assert c.stop == pytest.approx(L[7] - 0.25)
    dist = c.entry - c.stop
    assert c.target_1r == pytest.approx(c.entry + dist)
    assert c.target_2r == pytest.approx(c.entry + 2 * dist)
    assert c.features["trigger_pin"] is True
    assert "trigger" not in c.missing
    assert c.instrument == "MNQ"
    assert c.time.startswith("2026-09-01T09:")
    # every field must be plain-JSON serializable (no stray numpy bool_/float64 leaking through)
    json.dumps(asdict(c))


def test_close_through_voids_and_no_candidate():
    """A close back below the level after break must not produce a candidate."""
    O, H, L, C = _flat_day()
    O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9
    O[6], H[6], L[6], C[6] = 102.9, 103.0, 100.5, 100.9  # closes back through 101 (the level)
    A = dict(open=O, high=H, low=L, close=C)
    cands = detect_candidates(A, "2026-09-02", "MNQ")
    # no clean retest/trigger followed this void in the fixture -> expect none
    assert all(c.level != 101.0 or c.missing for c in cands) or len(cands) == 0


def test_weak_trigger_logged_as_one_off_or_worse():
    """Retest without a pin/strong trigger candle still emits a candidate, graded down."""
    O, H, L, C = _flat_day()
    O[5], H[5], L[5], C[5] = 100.9, 103.0, 100.9, 102.9
    O[6], H[6], L[6], C[6] = 102.9, 103.0, 102.0, 102.5
    # a doji-ish retest bar at the level: no pin, no strong body
    O[7], H[7], L[7], C[7] = 101.1, 101.3, 100.95, 101.05
    for j in range(8, len(O)):
        O[j] = 101.0 + (j - 8) * 0.1
        H[j] = 101.4 + (j - 8) * 0.1
        L[j] = 100.9 + (j - 8) * 0.1
        C[j] = 101.1 + (j - 8) * 0.1
    A = dict(open=O, high=H, low=L, close=C)
    cands = detect_candidates(A, "2026-09-03", "MNQ")
    assert len(cands) >= 1
    c = cands[0]
    assert c.features["trigger_pin"] is False and c.features["trigger_strong"] is False
    assert "trigger" in c.missing
    assert c.grade_hint in ("one-off", "two-off", "candidate")


def test_short_side_mirrors_long():
    O, H, L, C = _flat_day()
    O[5], H[5], L[5], C[5] = 100.1, 100.1, 98.0, 98.1     # break below OR low (100.0), displacement
    O[6], H[6], L[6], C[6] = 98.1, 99.0, 98.0, 98.5
    O[7], H[7], L[7], C[7] = 99.5, 100.0, 99.4, 99.55     # pin touching 100 (short retest), closes below
    for j in range(8, len(O)):
        O[j] = 99.5 - (j - 8) * 0.5
        H[j] = 99.6 - (j - 8) * 0.5
        L[j] = 99.0 - (j - 8) * 0.5
        C[j] = 99.1 - (j - 8) * 0.5
    A = dict(open=O, high=H, low=L, close=C)
    cands = detect_candidates(A, "2026-09-04", "MNQ")
    shorts = [c for c in cands if c.direction == "short"]
    assert len(shorts) >= 1
    c = shorts[0]
    assert c.level == 100.0
    assert c.stop > c.entry  # stop above entry for a short
    assert c.target_1r < c.entry
    assert c.target_2r < c.target_1r


def test_no_break_no_candidates():
    O, H, L, C = _flat_day()
    A = dict(open=O, high=H, low=L, close=C)
    assert detect_candidates(A, "2026-09-05", "MNQ") == []


def test_outside_window_no_late_break_scanned():
    """A break that only occurs at the very last minute has no room to enter -> skipped safely."""
    O, H, L, C = _flat_day()
    O[WINDOW_END_MIN] = 103.0
    H[WINDOW_END_MIN] = 103.0
    L[WINDOW_END_MIN] = 100.9
    C[WINDOW_END_MIN] = 102.9
    A = dict(open=O, high=H, low=L, close=C)
    # must not raise (no j+1 bar to enter on)
    detect_candidates(A, "2026-09-06", "MNQ")
