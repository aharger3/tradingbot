"""Weekly receipt must cover 7 calendar days, not the last 7 nightly rows."""
from datetime import date, timedelta

from research import sunday_summary as ss


def _write(tmp_path, monkeypatch, weeks=3, start=date(2026, 8, 31)):
    rows = ["# nightly loop receipts", "", "| date | flag | decision | $/day a->b | green a->b | off_book_id -> on_book_id |", "|---|---|---|---|---|---|"]
    for w in range(weeks):
        for d in range(5):
            rows.append(f"| {start + timedelta(days=7 * w + d)} | - | ship | - | - | - |")
    p = tmp_path / "nightly.md"
    p.write_text("\n".join(rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(ss, "NIGHTLY", p)


def test_week_two_sunday_covers_only_five_nights(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    sunday = date(2026, 9, 13)  # Sunday after week 2 (weeks start 08-31, 09-07)
    lines = ss.read_nightly_lines(today=sunday)
    row = ss.make_summary_row(lines, {})
    assert "week of 2026-09-07" in row
    assert "tried 5" in row


def test_week_three_sunday(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch)
    row = ss.make_summary_row(ss.read_nightly_lines(today=date(2026, 9, 20)), {})
    assert "week of 2026-09-14" in row and "tried 5" in row
