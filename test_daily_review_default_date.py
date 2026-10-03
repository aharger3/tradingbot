from datetime import datetime
from zoneinfo import ZoneInfo

import daily_review


def test_default_is_today_et_not_yesterday():
    # Tuesday 16:10 ET (20:10 UTC) must review Tuesday.
    now = datetime(2026, 7, 14, 16, 10, tzinfo=ZoneInfo("America/New_York"))
    assert daily_review.default_review_date(now) == "2026-07-14"


def test_main_without_date_uses_today(monkeypatch, capsys):
    monkeypatch.setattr(daily_review, "default_review_date", lambda now=None: "2026-07-14")
    seen = []
    monkeypatch.setattr(daily_review, "build_embed", lambda d: seen.append(d) or {})
    monkeypatch.setattr("sys.argv", ["daily_review.py", "--dry-run"])
    daily_review.main()
    assert seen == ["2026-07-14"]
