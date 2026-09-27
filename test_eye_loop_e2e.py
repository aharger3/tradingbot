"""End-to-end coverage for the eye-loop pipeline: candidates -> card -> label -> paper.

Wires eye_runner's own conversion helpers (to_chart_candidate/to_paper_candidate/
read_new_labels) together with eye_card.labels and eye_paper against synthetic
fixtures -- no network, no live feed, no real orders. Runs from repo root like
the other root-level test_*.py files.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import numpy as np
import pytest

import eye_runner
from eye_card.labels import append_label

eye2 = eye_runner.eye2
eye_paper = eye_runner.eye_paper


@pytest.fixture
def fixture_candidate():
    return eye2.Candidate(
        time="2026-01-05T09:31:00-04:00",
        instrument="MNQ",
        direction="long",
        level=100.0,
        entry=100.25,
        stop=99.0,
        target_1r=101.5,
        target_2r=102.75,
        features={"or_high": 100.5, "or_low": 99.5, "minutes_after_open": 0},
        grade_hint="S",
        missing=[],
    )


@pytest.fixture
def fixture_bars():
    """61 minutes of synthetic MNQ bars (index 0 = 09:30). Uptrend clears the
    long fixture's +2R target well before its 60-minute cutoff and never
    revisits the stop, so the paper stage has an unambiguous fill regardless
    of exact fill-rule internals."""
    n = 61
    o = np.full(n, 100.0)
    h = np.full(n, 100.5)
    l = np.full(n, 99.8)
    c = np.full(n, 100.0)
    h[2:12] = 103.0  # clears the 102.75 (+2R) target
    l[2:12] = 100.0  # never comes back near the 99.0 stop
    c[2:12] = 102.9
    return {"open": o, "high": h, "low": l, "close": c}


def test_candidate_to_card(fixture_candidate):
    """candidates -> card: eye_runner's converters carry the candidate's
    numbers through unchanged into the chart/paper shapes."""
    chart_cand = eye_runner.to_chart_candidate(fixture_candidate, "C1")
    assert chart_cand.direction == "LONG"
    assert chart_cand.entry == fixture_candidate.entry
    assert chart_cand.targets == [fixture_candidate.target_1r, fixture_candidate.target_2r]

    sent_ts = datetime(2026, 1, 5, 9, 31, 0, tzinfo=timezone.utc)
    paper_cand = eye_runner.to_paper_candidate(fixture_candidate, "C1", "2026-01-05", sent_ts)
    assert paper_cand["id"] == "C1"
    assert paper_cand["side"] == 1
    assert paper_cand["signal_minute"] == 0
    assert paper_cand["card_sent_ts"] == sent_ts.isoformat()


def test_card_to_label_roundtrip(tmp_path):
    """card -> label: an S tap appended by eye_card.labels is picked back up
    by eye_runner.read_new_labels exactly once (dedup on candidate_id+logged_at)."""
    labels_csv = tmp_path / "labels.csv"
    row = append_label(labels_csv, "C1", "S")

    seen = set()
    first = eye_runner.read_new_labels(labels_csv, seen)
    again = eye_runner.read_new_labels(labels_csv, seen)

    assert len(first) == 1
    assert first[0]["candidate_id"] == "C1"
    assert first[0]["label"] == "S"
    assert again == []  # already-seen row is not replayed
    assert row["mode"] == "PAPER"


def test_label_to_paper_confirmed_trade(fixture_candidate, fixture_bars, tmp_path):
    """label -> paper: an S tap inside the confirm window turns into a
    simulated fill, and only confirmed rows land in the journal."""
    sent_ts = datetime.now(timezone.utc) - timedelta(seconds=5)
    paper_cand = eye_runner.to_paper_candidate(fixture_candidate, "C1", "2026-01-05", sent_ts)

    labels_csv = tmp_path / "labels.csv"
    label_row = append_label(labels_csv, "C1", "S")
    tap = {"candidate_id": "C1", "grade": "S", "tap_ts": label_row["logged_at"]}

    ok, reason, latency = eye_paper.confirm(paper_cand, tap)
    assert ok is True
    assert reason == "confirmed"
    assert latency is not None and 0 <= latency <= eye_paper.DEFAULT_CONFIRM_WINDOW_S

    result_row = eye_paper.run_confirmed(paper_cand, tap, day_array=fixture_bars)
    assert result_row["confirmed"] is True
    assert "r" in result_row and isinstance(result_row["r"], float)

    journal = tmp_path / "acks_test.jsonl"
    written = eye_paper.append_journal([result_row], path=journal)
    assert written == 1
    lines = journal.read_text().splitlines()
    assert len(lines) == 1
    saved = json.loads(lines[0])
    assert saved["id"] == "C1" and saved["confirmed"] is True

    summary = eye_paper.daily_summary("2026-01-05", path=journal)
    assert summary["n"] == 1


def test_notS_tap_never_reaches_journal(fixture_candidate, fixture_bars, tmp_path):
    """A notS tap is a real path through the same pipeline: it must confirm
    False, and append_journal must refuse to write it (paper-trades only)."""
    sent_ts = datetime.now(timezone.utc) - timedelta(seconds=5)
    paper_cand = eye_runner.to_paper_candidate(fixture_candidate, "C1", "2026-01-05", sent_ts)

    labels_csv = tmp_path / "labels.csv"
    label_row = append_label(labels_csv, "C1", "notS")
    tap = {"candidate_id": "C1", "grade": "notS", "tap_ts": label_row["logged_at"]}

    result_row = eye_paper.run_confirmed(paper_cand, tap, day_array=fixture_bars)
    assert result_row["confirmed"] is False
    assert result_row["reason"] == "grade_notS"

    journal = tmp_path / "acks_test2.jsonl"
    written = eye_paper.append_journal([result_row], path=journal)
    assert written == 0
    assert not journal.exists()
