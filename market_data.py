"""Fetch index/symbol daily data from cached Polygon 1m bars.
Avoids yfinance rate limits and works 100% offline after first cache fill.
"""

import csv
import requests
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from polygon_feed import ARCHIVE, _api_key, _throttle, _read_csv


def _read_daily_close(symbol: str, iso: str):
    """Read the last RTH candle close from a cached 1m CSV. Returns None if missing."""
    cached = ARCHIVE / symbol / f"{iso}.csv"
    if not cached.exists():
        return None
    try:
        candles = _read_csv(cached)
        rth = [c for c in candles if "09:30:00" <= c.timestamp < "16:00:00"]
        if rth:
            return rth[-1].close
    except Exception:
        return None
    return None


def _fetch_and_cache(symbol: str, day_iso: str):
    """Fetch one day of 1m Polygon data and cache to CSV."""
    _throttle()
    url = (f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/"
           f"{day_iso}/{day_iso}")
    r = requests.get(url, params={"adjusted": "true", "sort": "asc",
                                  "limit": 50000, "apiKey": _api_key()},
                     timeout=30)
    r.raise_for_status()
    rows = r.json().get("results") or []
    if not rows:
        return
    cached = ARCHIVE / symbol / f"{day_iso}.csv"
    cached.parent.mkdir(parents=True, exist_ok=True)
    with open(cached, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Datetime", "Open", "High", "Low", "Close", "Adj Close", "Volume"])
        from zoneinfo import ZoneInfo
        et = ZoneInfo("America/New_York")  # DST-safe (UTC-4 hardcode broke Nov-Mar)
        for b in rows:
            ts = datetime.fromtimestamp(b["t"] / 1000, tz=timezone.utc).astimezone(et)
            w.writerow([ts.isoformat(), b["o"], b["h"], b["l"], b["c"], b["c"], b["v"]])


def fetch_daily_closes(symbol: str, days_back: int = 400) -> dict:
    """Return {day_iso: close} from cached Polygon 1m data (read-only, no API calls)."""
    out = {}
    cached_dir = ARCHIVE / symbol
    if not cached_dir.exists():
        return out
    today = date.today()
    oldest = (today - timedelta(days=days_back)).isoformat()
    for f in cached_dir.glob("*.csv"):
        iso = f.stem
        if iso >= oldest:
            close = _read_daily_close(symbol, iso)
            if close is not None:
                out[iso] = close
    return out


def fetch_spy_daily_closes(days_back: int = 400) -> dict:
    """Alias: fetch_daily_closes('SPY', days_back)."""
    return fetch_daily_closes("SPY", days_back)


def fetch_vix_daily(days_back: int = 400) -> dict:
    """Return {day_iso: vix_close} from cached data (read-only, no API calls).

    Checks data_archive/VIX/ and data_archive/_I_VIX/ directories.
    Returns empty dict if no VIX data is cached (the VIX regime mode
    gracefully falls back to ACTION_NORMAL).
    """
    out = {}
    for prefix in ("VIX", "_I_VIX"):
        cached_dir = ARCHIVE / prefix
        if not cached_dir.exists():
            continue
        today = date.today()
        oldest = (today - timedelta(days=days_back)).isoformat()
        for f in cached_dir.glob("*.csv"):
            iso = f.stem
            if iso >= oldest:
                close = _read_daily_close(prefix, iso)
                if close is not None:
                    out[iso] = close
        if out:
            break
    return out
