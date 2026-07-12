"""Polygon.io 1-min bars — 2 years of history on the free tier (5 req/min).

Fills the yfinance 30-day gap for historical replays/backtests. Bars cached to
data_archive/<SYM>/<YYYY-MM-DD>.csv (same layout archive_1m.py writes), so each
(symbol, day) costs one API call ever.
"""
import csv
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from omen_bot import Candle

ARCHIVE = Path(__file__).parent / "data_archive"
ET = ZoneInfo("America/New_York")
_last_call = [0.0]


def _api_key() -> str:
    key = os.environ.get("POLYGON_API_KEY", "")
    if not key:  # standalone runs don't go through signal_runner's .env loader
        for line in (Path(__file__).parent / ".env").read_text().splitlines():
            if line.startswith("POLYGON_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise RuntimeError("POLYGON_API_KEY not set (add to tradingbot/.env)")
    return key


def _throttle():
    # Stocks Starter (2026-07-08): unlimited calls, no rate cap. No-op kept so
    # callers don't change. ponytail: restore 12.5s wait here if we ever drop to free.
    pass


def fetch_day(symbol: str, day_iso: str) -> list:
    """RTH+premarket 1-min Candles for one day, cache-first."""
    cached = ARCHIVE / symbol / f"{day_iso}.csv"
    if cached.exists():
        return _read_csv(cached)
    _throttle()
    url = (f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/"
           f"{day_iso}/{day_iso}")
    r = requests.get(url, params={"adjusted": "true", "sort": "asc",
                                  "limit": 50000, "apiKey": _api_key()},
                     timeout=30)
    r.raise_for_status()
    rows = r.json().get("results") or []
    if not rows:
        return []
    cached.parent.mkdir(parents=True, exist_ok=True)
    with open(cached, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Datetime", "Open", "High", "Low", "Close", "Adj Close", "Volume"])
        for b in rows:
            ts = datetime.fromtimestamp(b["t"] / 1000, tz=timezone.utc).astimezone(ET)
            w.writerow([ts.isoformat(), b["o"], b["h"], b["l"], b["c"], b["c"], b["v"]])
    return _read_csv(cached)


def _read_csv(path: Path) -> list:
    out = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = datetime.fromisoformat(row["Datetime"])
            out.append(Candle(timestamp=ts.strftime("%H:%M:%S"),
                              open=float(row["Open"]), high=float(row["High"]),
                              low=float(row["Low"]), close=float(row["Close"]),
                              volume=int(float(row["Volume"] or 0))))
    return out


def rth(candles: list) -> list:
    return [c for c in candles if "09:30:00" <= c.timestamp < "16:00:00"]


def premarket_hi_lo(candles: list):
    pm = [c for c in candles if c.timestamp < "09:30:00"]
    if not pm:
        return None, None
    return max(c.high for c in pm), min(c.low for c in pm)


if __name__ == "__main__":
    c = rth(fetch_day("TSLA", "2026-06-12"))
    print(f"TSLA 2026-06-12: {len(c)} RTH bars, open {c[0].open}" if c else "no data")
