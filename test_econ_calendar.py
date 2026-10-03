import json
from pathlib import Path

import econ_calendar as ec

FX = Path(__file__).parent / "tests" / "fixtures"
EVS = json.loads((FX / "ff_week_2026-09-27.json").read_text())
HTML = (FX / "fomc_calendar_snippet.html").read_text()


def test_et_conversion_and_ism_flag():
    w = ec.window_events(EVS)
    flags = ec.news_flag("2026-10-01", w)
    assert "10:00 ISM Manufacturing PMI (Medium)" in flags
    assert all(e["et_time"] >= "08:00" and e["et_time"] <= "11:00" for e in w)


def test_et_from_utc_offset():
    e = [{"title": "X", "country": "USD", "impact": "High", "date": "2026-10-01T14:00:00+00:00"}]
    assert ec.window_events(e)[0]["et_time"] == "10:00"


def test_low_and_non_usd_excluded():
    w = ec.window_events(EVS)
    titles = [e["title"] for e in w]
    assert "Construction Spending m/m" not in titles  # Low
    assert all(e["country"] == "USD" for e in w)
    e = [{"title": "Y", "country": "EUR", "impact": "High", "date": "2026-10-01T10:00:00-04:00"}]
    assert ec.window_events(e) == []


def test_fomc_parse():
    d = ec.fetch_fomc_dates(lambda url: HTML)
    assert "2026-10-28" in d and "2026-12-09" in d
    assert any(x.startswith("2027") for x in d)


def test_cross_month_range():
    assert ec._decision_day(2026, "Apr/May", "30-1") == "2026-05-01"
    assert ec._decision_day(2026, "March", "17-18*") == "2026-03-18"


def test_stale_report_planted_missing():
    nd = {"window": "2024-07-11..2026-11-08", "by_type": {"FOMC": ["2026-10-28"]}}
    r = ec.stale_report(["2026-10-28", "2026-09-16", "2026-12-09"], nd)
    assert r["missing_in_news_days"] == ["2026-09-16"]
    assert r["beyond_window"] == ["2026-12-09"]
    assert r["window_end"] == "2026-11-08"
