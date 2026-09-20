"""test_bar_picks_landing.py -- omen-bar-pick-mock-test (2026-09-21).

Bar-pick marks (sm_deck.py --mark-bar's *_bars.jsonl export, {symbol, date,
his_letter, ...}) are read by marks_pool.py via the `_bars_key`/`_bars_opinion`
schema match (see research/marks_pool.py). Real bar-pick marks sit at 0 rows
today (roadmap 2026-09-20: "0 of the 3 nightly bar-deck cards have a filed
A/B/C mark yet"), so this test cannot wait on real data -- it mocks one
bar-pick row and asserts marks_pool.canonical_pool() picks it up: the pool
grows by exactly one symbol-day, keyed SYMBOL_DATE, graded 'A' (per
_bars_opinion: a bar pick is entry-timing feedback on an already-A/S
candidate, never read as S).

Does not touch any real mark file -- the mock row is injected by monkeypatching
build_deck.mark_sources() to add one extra temp file, never by writing into
research/marks/.

Run: `python -m pytest test_bar_picks_landing.py::test_bars_feed_pool -q`
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE / "research"))

import build_deck as bd  # noqa: E402
import marks_pool  # noqa: E402


def test_bars_feed_pool(monkeypatch):
    real_sources = bd.mark_sources()
    baseline_pool = marks_pool.canonical_pool()
    baseline_n = len(baseline_pool)

    mock_row = {
        "symbol": "ZZMOCK",
        "date": "2026-01-01",
        "his_letter": "A",
        "his_bar": "09:35",
        "engine_bar": "09:40",
        "minutes_early": 5,
    }
    # A repo-local scratch dir, not pytest's tmp_path -- the shared
    # C:\Users\...\Temp\pytest-of-aharg base dir is permission-denied in
    # this environment.
    scratch_dir = HERE / "_test_scratch"
    scratch_dir.mkdir(exist_ok=True)
    fd, mock_path = tempfile.mkstemp(
        suffix="_bars.jsonl", dir=str(scratch_dir)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(mock_row) + "\n")

        # Real sources plus the one mock file -- nothing on disk in
        # research/ is touched.
        monkeypatch.setattr(
            bd, "mark_sources", lambda: real_sources + [mock_path]
        )

        new_pool = marks_pool.canonical_pool()
    finally:
        os.remove(mock_path)
        try:
            scratch_dir.rmdir()
        except OSError:
            pass

    assert len(new_pool) == baseline_n + 1, (
        "pool should grow by exactly 1 (the mocked bar-pick row): "
        "baseline %d -> new %d" % (baseline_n, len(new_pool))
    )
    key = "ZZMOCK_2026-01-01"
    assert key in new_pool
    assert new_pool[key].grade == "A"
