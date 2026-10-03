"""Tests for eye_runner.py's LEGOLAND work-day skip gate (skip_dates.txt).

eye_runner.py imports `candidates` and `eye_paper` from research/agent_runs/*
(which in turn import a gitignored, untracked orb1m.py that isn't present in
a fresh clone/worktree), plus a root `omen_data` module that does not exist
in this repo at all as of 2026-09-27. Those are pre-existing gaps in the
"eye loop" pipeline, unrelated to the skip-date gate under test here, so all
three are stubbed in sys.modules before importing eye_runner: Python's
`import` statement uses the cached module instead of re-executing/looking up
the real file.
"""
import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

for _name, _attrs in (
    ("candidates", {
        "Candidate": object,
        "run": lambda *a, **k: (None, []),
        "day_arrays": lambda *a, **k: None,
        "detect_candidates": lambda *a, **k: [],
    }),
    ("eye_paper", {
        "DEFAULT_CUTOFF_MINUTE": 0,
        "run_confirmed": lambda *a, **k: {},
        "append_journal": lambda *a, **k: 0,
        "daily_summary": lambda *a, **k: {},
    }),
    ("omen_data", {"load_fut": lambda *a, **k: None}),
):
    if _name not in sys.modules:
        _mod = types.ModuleType(_name)
        for _k, _v in _attrs.items():
            setattr(_mod, _k, _v)
        sys.modules[_name] = _mod

import eye_runner  # noqa: E402

ET = ZoneInfo("America/New_York")


def test_load_skip_dates_reads_file_and_ignores_comments(tmp_path):
    p = tmp_path / "skip_dates.txt"
    p.write_text("# comment\n2026-10-12\n\n2026-11-06\n", encoding="utf-8")
    assert eye_runner.load_skip_dates(p) == {"2026-10-12", "2026-11-06"}


def test_load_skip_dates_missing_file_is_empty(tmp_path):
    assert eye_runner.load_skip_dates(tmp_path / "nope.txt") == set()


def test_check_skip_date_true_on_listed_date(tmp_path):
    p = tmp_path / "skip_dates.txt"
    p.write_text("2026-10-12\n", encoding="utf-8")
    now = datetime(2026, 10, 12, 9, 28, tzinfo=ET)
    assert eye_runner.check_skip_date(p, now=now) == "2026-10-12"


def test_check_skip_date_false_on_other_date(tmp_path):
    p = tmp_path / "skip_dates.txt"
    p.write_text("2026-10-12\n", encoding="utf-8")
    now = datetime(2026, 10, 13, 9, 28, tzinfo=ET)
    assert eye_runner.check_skip_date(p, now=now) is None


def test_main_sends_no_ntfy_on_skip_date(monkeypatch, capsys):
    """On a listed date, main() exits 0, logs 'skipped: work day', and never
    reaches send_card (no ntfy push)."""
    monkeypatch.setattr(eye_runner, "check_skip_date", lambda *a, **k: "2026-10-12")

    def boom(*a, **k):
        raise AssertionError("send_card must not be called on a skip date")

    monkeypatch.setattr(eye_runner, "send_card", boom)

    rc = eye_runner.main(["--title-prefix", "OMEN TEST -- ignore"])

    assert rc == 0
    assert "skipped: work day" in capsys.readouterr().out


def test_main_runs_normally_on_a_non_skip_date(monkeypatch):
    """When it's not a skip date, main() proceeds past the gate into the
    normal replay path instead of short-circuiting."""
    monkeypatch.setattr(eye_runner, "check_skip_date", lambda *a, **k: None)

    def proceeded(*a, **k):
        raise RuntimeError("proceeded past skip gate")

    monkeypatch.setattr(eye_runner, "pick_replay_date", proceeded)

    with pytest.raises(RuntimeError, match="proceeded past skip gate"):
        eye_runner.main(["--title-prefix", "OMEN TEST -- ignore"])
