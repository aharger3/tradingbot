"""Journal row schema contract + validator.

One shape for every writer that appends to journal/*.jsonl or
research/paper_journal/*.jsonl (paper, eye, scanner). See IDEAS.md
"omen-infrastructure" for why: 3 writers currently emit 3 different
row shapes and daily_report.py has to guess.

Usage:
    python research/journal_schema.py                 # scan default dirs
    python research/journal_schema.py path/to/*.jsonl  # scan explicit files
"""
from __future__ import annotations

import glob
import json
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

# --- Contract -----------------------------------------------------------

REQUIRED_FIELDS = {
    "ts": str,
    "symbol": str,
    "setup": str,
    "side": str,
    "entry_fill_px": (int, float),
    "stop": (int, float),
    "target": (int, float),
    "R": (int, float),
    "source": str,
    "config_hash": str,
}

VALID_SIDES = {"buy", "sell", "long", "short", "call", "put"}


@dataclass
class JournalRow:
    """Canonical paper/eye/scanner journal row. Extra fields are allowed
    (writers may carry their own extras); these ten are the contract."""

    ts: str
    symbol: str
    setup: str
    side: str
    entry_fill_px: float
    stop: float
    target: float
    R: float
    source: str
    config_hash: str


REQUIRED_FIELD_NAMES = [f.name for f in fields(JournalRow)]


class RowError(Exception):
    pass


def validate_row(row: dict[str, Any]) -> list[str]:
    """Return a list of contract violations for one parsed row (empty = valid)."""
    errors: list[str] = []
    if not isinstance(row, dict):
        return [f"row is not a JSON object: {type(row).__name__}"]

    for name in REQUIRED_FIELD_NAMES:
        if name not in row:
            errors.append(f"missing required field '{name}'")
            continue
        expected = REQUIRED_FIELDS[name]
        value = row[name]
        if not isinstance(value, expected) or isinstance(value, bool):
            errors.append(
                f"field '{name}' has wrong type: expected {expected}, got {type(value).__name__}"
            )

    if "side" in row and isinstance(row.get("side"), str) and row["side"] not in VALID_SIDES:
        errors.append(f"field 'side' has invalid value '{row['side']}' (expected one of {sorted(VALID_SIDES)})")

    return errors


def validate_line(line: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse + validate one jsonl line. Returns (row_or_None, errors)."""
    line = line.strip()
    if not line:
        return None, []
    try:
        row = json.loads(line)
    except json.JSONDecodeError as e:
        return None, [f"invalid JSON: {e}"]
    return row, validate_row(row)


def validate_file(path: Path) -> tuple[int, int, list[tuple[int, list[str]]]]:
    """Scan one jsonl file. Returns (valid_count, invalid_count, [(lineno, errors), ...])."""
    valid = 0
    invalid = 0
    bad_lines: list[tuple[int, list[str]]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        _row, errors = validate_line(line)
        if errors:
            invalid += 1
            bad_lines.append((lineno, errors))
        else:
            valid += 1
    return valid, invalid, bad_lines


DEFAULT_GLOBS = ["journal/*.jsonl", "research/paper_journal/*.jsonl"]


def scan(globs: list[str]) -> dict[str, tuple[int, int, list[tuple[int, list[str]]]]]:
    results: dict[str, tuple[int, int, list[tuple[int, list[str]]]]] = {}
    for pattern in globs:
        for path_str in sorted(glob.glob(pattern)):
            path = Path(path_str)
            results[str(path)] = validate_file(path)
    return results


def format_report(results: dict[str, tuple[int, int, list[tuple[int, list[str]]]]], verbose: bool = False) -> str:
    lines = []
    total_valid = total_invalid = 0
    for name, (valid, invalid, bad_lines) in results.items():
        lines.append(f"{name}: {valid} valid, {invalid} invalid")
        total_valid += valid
        total_invalid += invalid
        if verbose:
            for lineno, errors in bad_lines[:5]:
                lines.append(f"    line {lineno}: {'; '.join(errors)}")
    lines.append(f"TOTAL: {total_valid} valid, {total_invalid} invalid across {len(results)} file(s)")
    return "\n".join(lines)


def warning_line(globs: list[str] | None = None) -> str:
    """One-line summary for daily_report.py to print as a warning.
    Kept dependency-free so any report script can `from research.journal_schema
    import warning_line` without importing the CLI machinery."""
    results = scan(globs or DEFAULT_GLOBS)
    total_valid = sum(v for v, _i, _b in results.values())
    total_invalid = sum(i for _v, i, _b in results.values())
    if total_invalid == 0:
        return f"journal schema: {total_valid} rows valid, 0 invalid"
    return f"WARNING: journal schema: {total_invalid} invalid rows ({total_valid} valid) across {len(results)} file(s) -- run `python research/journal_schema.py` for detail"


def main(argv: list[str]) -> int:
    verbose = "-v" in argv or "--verbose" in argv
    argv = [a for a in argv if a not in ("-v", "--verbose")]
    globs = argv if argv else DEFAULT_GLOBS
    results = scan(globs)
    print(format_report(results, verbose=verbose))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
