import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import daily_report as dr  # noqa: E402


def test_binom_sigma_flag_no_signal_not_flagged():
    z = dr.binom_sigma_flag(0, dr.FIRE_RATE_BASELINE)
    assert abs(z) < dr.SIGMA_THRESHOLD, "a single no-signal day must not trip the 2-sigma gate"


def test_binom_sigma_flag_direction():
    z_up = dr.binom_sigma_flag(1, dr.FIRE_RATE_BASELINE)
    z_down = dr.binom_sigma_flag(0, dr.FIRE_RATE_BASELINE)
    assert z_up > z_down


def test_load_baseline_has_required_keys():
    b = dr.load_baseline()
    for k in ("n", "hit_rate", "mean_r", "sigma_r"):
        assert k in b
    assert b["n"] > 0
    assert 0 <= b["hit_rate"] <= 1


def test_load_today_signals_empty_when_no_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(dr, "JOURNAL", tmp_path / "does_not_exist.jsonl")
    assert dr.load_today_signals("2026-09-26") == []


def test_load_today_signals_filters_by_date(tmp_path, monkeypatch):
    j = tmp_path / "acks.jsonl"
    j.write_text(
        json.dumps({"date": "2026-09-26", "id": "S1", "r": 2.0}) + "\n"
        + json.dumps({"date": "2026-09-25", "id": "S0", "r": -1.0}) + "\n"
    )
    monkeypatch.setattr(dr, "JOURNAL", j)
    rows = dr.load_today_signals("2026-09-26")
    assert len(rows) == 1
    assert rows[0]["id"] == "S1"


def test_main_runs_end_to_end_no_journal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(dr, "JOURNAL", tmp_path / "nope.jsonl")
    monkeypatch.setattr(dr, "REPORTS_DIR", tmp_path / "reports")
    dr.main()
    out = capsys.readouterr().out
    assert "Report:" in out
    reports = list((tmp_path / "reports").glob("daily_*.md"))
    assert len(reports) == 1


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
