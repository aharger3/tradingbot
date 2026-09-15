"""Unit tests for research/candidates_writer.py (row V5, 2026-09-14).

Cap-at-3, arrival order, and idempotency-on-id -- the three properties the
stage-manager's contract (docs/rows/v5-contract.md) depends on. Chart
rendering is monkeypatched out (`render_chart` -> False) so this runs without
archived bars on disk.

Run: python research/test_candidates_writer.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import research.candidates_writer as cw  # noqa: E402


def _record(day, symbol, ts, cw_mod):
    return cw_mod.record_candidate(
        day=day, symbol=symbol, ts=ts, setup="break_and_retest",
        level_name="PDH", direction="call", entry=100.0, stop=99.5,
        pt1=101.0, grade="S")


def test_cap_at_three_arrival_order():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with mock.patch.object(cw, "JOURNAL_DIR", tmp), \
             mock.patch.object(cw, "render_chart", return_value=False):
            _record("2026-09-14", "AAPL", "09:31:00", cw)
            _record("2026-09-14", "TSLA", "09:35:00", cw)
            _record("2026-09-14", "NVDA", "09:40:00", cw)
            fourth = _record("2026-09-14", "MSFT", "09:45:00", cw)
            doc = json.loads((tmp / "candidates_2026-09-14.json").read_text())
        assert fourth is None, "a 4th candidate must be refused, not appended"
        assert [c["symbol"] for c in doc["candidates"]] == ["AAPL", "TSLA", "NVDA"]
    print("PASS: cap at 3, arrival order preserved, 4th refused")


def test_idempotent_same_id_returns_existing():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with mock.patch.object(cw, "JOURNAL_DIR", tmp), \
             mock.patch.object(cw, "render_chart", return_value=False):
            first = _record("2026-09-14", "AAPL", "09:31:00", cw)
            second = _record("2026-09-14", "AAPL", "09:31:00", cw)
            doc = json.loads((tmp / "candidates_2026-09-14.json").read_text())
        assert first["id"] == second["id"] == "AAPL_2026-09-14_0931"
        assert len(doc["candidates"]) == 1, "re-recording the same id must not duplicate"
    print("PASS: same id is idempotent, no duplicate row")


def test_outside_window_is_skipped():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with mock.patch.object(cw, "JOURNAL_DIR", tmp), \
             mock.patch.object(cw, "render_chart", return_value=False):
            out = _record("2026-09-14", "AAPL", "10:45:00", cw)  # after 10:30
        assert out is None
    print("PASS: a candidate outside 09:30-10:30 is not recorded")


if __name__ == "__main__":
    test_cap_at_three_arrival_order()
    test_idempotent_same_id_returns_existing()
    test_outside_window_is_skipped()
    print("ALL PASS")
