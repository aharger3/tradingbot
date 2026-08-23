"""Bank today's 1-min bars via Polygon.io — replaces yfinance (socket timeouts).

Runs after the daily scan (run_daily.ps1). Grows data_archive/ so backtests
can eventually cover months, not the yfinance 30-day cap.
One CSV per symbol per day: data_archive/<SYM>/<YYYY-MM-DD>.csv (RTH+premarket).

Uses polygon_feed.fetch_day() which caches to the same CSV layout — subsequent
calls are disk reads, zero API cost.
"""
import sys
import argparse
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import polygon_feed
from universe import ALL_SYMS

ARCHIVE = Path(__file__).parent / "data_archive"
# Symbols from universe.py (single source of truth, 2026-08-11)
# ALL_SYMS combines MAJOR_15 + INDEX_POOL + OTHER_POOL


def archive_day(day: str) -> int:
    """Archive one date for every symbol. Returns the number of symbols fetched.

    Polygon returns 403 for the CURRENT day on this plan (no real-time
    entitlement), so an unattended job must ask for completed sessions --
    see --back. A 403 or an empty day is logged and skipped rather than
    killing the run, because one bad symbol must not cost the other 28.
    """
    fetched = 0
    for sym in ALL_SYMS:
        out = ARCHIVE / sym / f"{day}.csv"
        if out.exists():
            continue
        try:
            candles = polygon_feed.fetch_day(sym, day)
        except Exception as e:
            print(f"{sym} {day}: skipped ({type(e).__name__})")
            continue
        if candles:
            fetched += 1
            print(f"{sym} {day}: {len(candles)} bars archived")
    return fetched


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="single date YYYY-MM-DD (default: today)")
    ap.add_argument("--back", type=int, default=0,
                    help="also archive the N calendar days before --date; "
                         "weekends are attempted and simply come back empty")
    a = ap.parse_args()

    end = date.fromisoformat(a.date) if a.date else date.today()
    days = [(end - timedelta(days=i)).isoformat() for i in range(a.back + 1)]
    total = 0
    for day in sorted(days):
        total += archive_day(day)
    print(f"Done — {len(ALL_SYMS)} symbols x {len(days)} day(s), {total} fetched.")


if __name__ == "__main__":
    main()
