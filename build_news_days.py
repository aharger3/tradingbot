"""Build news_days.json — FOMC / CPI / PPI / NFP release dates for the news-day
filter Fable uses in backtests (trades on major-release days are excluded:
volatile, not representative of the edge).

Hardcoded from the official BLS + Fed FOMC calendars (2026-07-11). No fetcher —
dates change ~yearly, just re-run after editing the lists below. The 2025
government lapse (Oct 1 – Nov 12, 2025) canceled the Oct 2025 CPI/NFP releases
and shifted Nov/Dec 2025 PPI into Jan 2026; actual release dates are used and
the canceled months are omitted.

Window: past 24mo + next 3mo from today (default 2026-07-11 -> 2024-07-11..
2026-10-31). Dates outside the window are dropped.

Usage: python build_news_days.py
Output: news_days.json (repo root)
"""
import json
from datetime import date, timedelta
from pathlib import Path

# FOMC decision days (2nd day of each 2-day meeting; policy statement 2pm ET).
FOMC = [
    "2024-07-31", "2024-09-18", "2024-11-07", "2024-12-18",
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18", "2025-07-30",
    "2025-09-17", "2025-10-29", "2025-12-10",
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29",
    "2026-09-16", "2026-10-28", "2026-12-09",
]
# CPI release dates (8:30am ET). Oct 2025 release canceled (lapse).
CPI = [
    "2024-08-14", "2024-09-11", "2024-10-10", "2024-11-13", "2024-12-11",
    "2025-01-15", "2025-02-12", "2025-03-12", "2025-04-10", "2025-05-13",
    "2025-06-11", "2025-07-15", "2025-08-12", "2025-09-11", "2025-10-15",
    "2025-12-18",  # Nov 2025 ref (Oct ref canceled -> no 2025-11-13 release)
    "2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12",
    "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14",
    "2026-11-10", "2026-12-10",
]
# PPI release dates (8:30am ET). Oct 2025 ref delayed to Nov 25; Nov/Dec 2025
# ref pushed to Jan 2026 (lapse).
PPI = [
    "2024-07-12", "2024-08-13", "2024-09-12", "2024-10-11", "2024-11-14",
    "2024-12-12",
    "2025-01-14", "2025-02-13", "2025-03-13", "2025-04-11", "2025-05-15",
    "2025-06-12", "2025-07-16", "2025-08-14", "2025-09-10", "2025-11-25",
    "2026-01-14", "2026-01-30", "2026-02-27", "2026-03-18", "2026-04-14",
    "2026-05-13", "2026-06-11", "2026-07-15", "2026-08-13", "2026-09-10",
    "2026-10-15", "2026-11-13", "2026-12-15",
]
# NFP / Employment Situation release dates (8:30am ET). Oct 2025 canceled (lapse);
# Sep 2025 ref delayed to Nov 20.
NFP = [
    "2024-08-02", "2024-09-06", "2024-10-04", "2024-11-01", "2024-12-06",
    "2025-01-10", "2025-02-07", "2025-03-07", "2025-04-04", "2025-05-02",
    "2025-06-06", "2025-07-03", "2025-08-01", "2025-09-05", "2025-11-20",
    "2025-12-16",  # Nov 2025 ref (Oct ref canceled)
    "2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08",
    "2026-06-05", "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02",
    "2026-11-06", "2026-12-04",
]

BY_TYPE = {"FOMC": FOMC, "CPI": CPI, "PPI": PPI, "NFP": NFP}
OUT = Path(__file__).parent / "news_days.json"


def main(today: date = None):
    today = today or date(2026, 7, 11)
    start = today - timedelta(days=730)       # past 24mo
    end = today + timedelta(days=120)         # next ~4mo (covers full Oct; over-include is safe for a filter)

    by_date = {}
    for kind, dates in BY_TYPE.items():
        for d in dates:
            if start <= date.fromisoformat(d) <= end:
                by_date.setdefault(d, []).append(kind)

    news_days = sorted(by_date)
    out = {
        "source": "BLS + Federal Reserve FOMC calendars, hardcoded 2026-07-11",
        "window": f"{start.isoformat()}..{end.isoformat()} (past 24mo + next 3mo)",
        "note": "2025 lapse (Oct 1-Nov 12) canceled Oct 2025 CPI/NFP; shifted "
                "Nov/Dec 2025 PPI into Jan 2026. Actual release dates used.",
        "news_days": news_days,
        "by_type": {k: sorted(set(d for d in v
                                 if start <= date.fromisoformat(d) <= end))
                    for k, v in BY_TYPE.items()},
        "by_date": {d: sorted(by_date[d]) for d in news_days},
    }
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"news_days.json -> {OUT}")
    print(f"  {len(news_days)} news days in window "
          f"({news_days[0]} .. {news_days[-1]})")
    for k, v in out["by_type"].items():
        print(f"  {k}: {len(v)} releases")


if __name__ == "__main__":
    main()
