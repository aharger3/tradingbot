"""Bank today's 1-min bars via Polygon.io — replaces yfinance (socket timeouts).

Runs after the daily scan (run_daily.ps1). Grows data_archive/ so backtests
can eventually cover months, not the yfinance 30-day cap.
One CSV per symbol per day: data_archive/<SYM>/<YYYY-MM-DD>.csv (RTH+premarket).

Uses polygon_feed.fetch_day() which caches to the same CSV layout — subsequent
calls are disk reads, zero API cost.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import polygon_feed
from universe import ALL_SYMS

ARCHIVE = Path(__file__).parent / "data_archive"
# Symbols from universe.py (single source of truth, 2026-08-11)
# ALL_SYMS combines MAJOR_15 + INDEX_POOL + OTHER_POOL


def main() -> None:
    today = date.today().isoformat()
    for sym in ALL_SYMS:
        out = ARCHIVE / sym / f"{today}.csv"
        if out.exists():
            print(f"{sym}: already archived")
            continue
        candles = polygon_feed.fetch_day(sym, today)
        print(f"{sym}: {len(candles)} bars archived")
    print(f"Done — {len(SYMBOLS)} symbols checked.")


if __name__ == "__main__":
    main()
