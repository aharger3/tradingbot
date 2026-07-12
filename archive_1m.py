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

ARCHIVE = Path(__file__).parent / "data_archive"
# keep in sync with live_scanner.DEFAULT_SYMBOLS (no import: this job must not
# drag in the scanner's discord/tastytrade deps)
SYMBOLS = [
    "TSLA", "NVDA", "AAPL", "AMD", "META",
    "GOOGL", "AMZN", "MSFT", "PLTR", "SPY", "QQQ",
    "SOFI", "ORCL", "COIN", "HOOD", "IREN", "INTC", "SMCI",
    "MSTR", "NFLX", "AVGO", "MU", "UBER", "BABA", "CRM",
    "TSM", "MARA", "RIVN",
]


def main() -> None:
    today = date.today().isoformat()
    for sym in SYMBOLS:
        out = ARCHIVE / sym / f"{today}.csv"
        if out.exists():
            print(f"{sym}: already archived")
            continue
        candles = polygon_feed.fetch_day(sym, today)
        print(f"{sym}: {len(candles)} bars archived")
    print(f"Done — {len(SYMBOLS)} symbols checked.")


if __name__ == "__main__":
    main()
