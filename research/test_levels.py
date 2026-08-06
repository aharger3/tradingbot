"""Tests for research/levels.py node generators.

Covers the omen-3.5 T3 fix: hod_lod_nodes must compute the session extreme
from bars *before* the entry bar (bars[: entry_i]), not through it. A
break-and-retest entry is by construction a new session extreme, so including
the entry bar makes HOD/LOD the entry bar's own extreme ~always (96.9% of
trades) — see research/v34_verdict.md §2.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from levels import hod_lod_nodes


def _bar(t, o, h, l, c):
    return {"t": t, "o": float(o), "h": float(h), "l": float(l), "c": float(c)}


def test_hod_excludes_entry_bar():
    """Entry bar makes a new session high; HOD must be the *prior* high."""
    bars = [
        _bar("09:30", 100, 102, 99, 101),
        _bar("09:31", 101, 105, 100, 104),
        _bar("09:32", 104, 110, 103, 109),   # prior session high 110
        _bar("09:33", 109, 108, 106, 107),
        _bar("09:34", 107, 106, 104, 105),
        _bar("09:35", 105, 120, 105, 118),   # entry bar: NEW session high 120
    ]
    entry_i = 5
    nodes = hod_lod_nodes(bars, entry_i)
    hod = next(n for n in nodes if n["type"] == "HOD")
    assert hod["price"] == 110.0, (
        f"HOD should be prior high 110 (excluding entry bar), got {hod['price']}")
    assert hod["price"] != 120.0, "HOD must not be the entry bar's own high"
    assert hod["available_from"] < entry_i, (
        "HOD must be established before the entry bar")


def test_lod_excludes_entry_bar():
    """Entry bar makes a new session low; LOD must be the *prior* low."""
    bars = [
        _bar("09:30", 100, 102, 95, 101),
        _bar("09:31", 101, 105, 90, 104),    # prior session low 90
        _bar("09:32", 104, 108, 100, 107),
        _bar("09:33", 107, 106, 102, 105),
        _bar("09:34", 105, 106, 104, 105),
        _bar("09:35", 105, 106, 80, 82),     # entry bar: NEW session low 80
    ]
    entry_i = 5
    nodes = hod_lod_nodes(bars, entry_i)
    lod = next(n for n in nodes if n["type"] == "LOD")
    assert lod["price"] == 90.0, (
        f"LOD should be prior low 90 (excluding entry bar), got {lod['price']}")
    assert lod["price"] != 80.0, "LOD must not be the entry bar's own low"
    assert lod["available_from"] < entry_i, (
        "LOD must be established before the entry bar")


def test_entry_bar_at_open_has_no_session_extreme():
    """entry_i == 0: no bars before the entry bar -> no HOD/LOD node."""
    bars = [_bar("09:30", 100, 120, 80, 110)]
    assert hod_lod_nodes(bars, 0) == [], (
        "With no bars before the entry bar, HOD/LOD must be empty")


def _run():
    test_hod_excludes_entry_bar()
    print("test_hod_excludes_entry_bar: PASS")
    test_lod_excludes_entry_bar()
    print("test_lod_excludes_entry_bar: PASS")
    test_entry_bar_at_open_has_no_session_extreme()
    print("test_entry_bar_at_open_has_no_session_extreme: PASS")
    print("all tests passed")


if __name__ == "__main__":
    _run()
    sys.exit(0)
