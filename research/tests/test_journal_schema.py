"""pytest for research/journal_schema.py -- 1 good row, 3 bad rows."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from journal_schema import validate_row, validate_file, warning_line  # noqa: E402

GOOD_ROW = {
    "ts": "2026-09-27T10:35:00Z",
    "symbol": "ORCL",
    "setup": "g88",
    "side": "buy",
    "entry_fill_px": 323.66,
    "stop": 324.46,
    "target": 320.0,
    "R": 1.5,
    "source": "paper",
    "config_hash": "abc123",
}

# missing required field
BAD_ROW_MISSING = {k: v for k, v in GOOD_ROW.items() if k != "stop"}

# wrong type (entry_fill_px is a string, not a number)
BAD_ROW_TYPE = {**GOOD_ROW, "entry_fill_px": "323.66"}

# invalid side value
BAD_ROW_ENUM = {**GOOD_ROW, "side": "sideways"}


def test_good_row_has_no_errors():
    assert validate_row(GOOD_ROW) == []


def test_missing_field_is_caught():
    errors = validate_row(BAD_ROW_MISSING)
    assert any("stop" in e for e in errors)


def test_wrong_type_is_caught():
    errors = validate_row(BAD_ROW_TYPE)
    assert any("entry_fill_px" in e for e in errors)


def test_invalid_enum_is_caught():
    errors = validate_row(BAD_ROW_ENUM)
    assert any("side" in e for e in errors)


def test_validate_file_counts_good_and_bad(tmp_path):
    p = tmp_path / "sample.jsonl"
    lines = [GOOD_ROW, BAD_ROW_MISSING, BAD_ROW_TYPE, BAD_ROW_ENUM]
    p.write_text("\n".join(json.dumps(r) for r in lines) + "\n")
    valid, invalid, bad_lines = validate_file(p)
    assert valid == 1
    assert invalid == 3
    assert len(bad_lines) == 3


def test_validate_file_handles_malformed_json(tmp_path):
    p = tmp_path / "malformed.jsonl"
    p.write_text(json.dumps(GOOD_ROW) + "\nnot json at all\n")
    valid, invalid, bad_lines = validate_file(p)
    assert valid == 1
    assert invalid == 1


def test_warning_line_mentions_warning_when_invalid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "x.jsonl").write_text(json.dumps(BAD_ROW_MISSING) + "\n")
    line = warning_line()
    assert "WARNING" in line
