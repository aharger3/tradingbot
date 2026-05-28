"""Alpaca live market data feed for 1-min candles.

Free paper account works for IEX real-time data on US stocks.
Sign up: https://alpaca.markets → Generate API Keys.
Set in .env:
    ALPACA_API_KEY=...
    ALPACA_SECRET_KEY=...
"""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import requests

from vanquish_bot import Candle


ALPACA_DATA_URL = "https://data.alpaca.markets/v2"
ALPACA_OPTIONS_URL = "https://data.alpaca.markets/v1beta1"


class AlpacaFeed:
    """Fetch recent 1-min bars from Alpaca."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "Alpaca creds missing. Set ALPACA_API_KEY + ALPACA_SECRET_KEY in .env."
            )
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def fetch_option_snapshot(
        self,
        underlying: str,
        expiration: str,   # "YYYY-MM-DD"
        strike: float,
        right: str,         # "call" or "put"
    ) -> Optional[dict]:
        """Fetch latest snapshot (bid/ask/mid) for a specific option contract.

        Alpaca options snapshots endpoint takes underlying + filter params.
        Free tier = OPRA delayed 15min.
        """
        exp_compact = expiration.replace("-", "")[2:]  # YYMMDD
        right_char = "C" if right.lower() == "call" else "P"
        strike_int = int(round(strike * 1000))
        occ = f"{underlying.upper()}{exp_compact}{right_char}{strike_int:08d}"

        url = f"{ALPACA_OPTIONS_URL}/options/snapshots/{underlying.upper()}"
        # Query ±$5 around target strike — TSLA/NVDA have $5 increments at high prices.
        # Picks contract with strike closest to requested.
        params = {
            "feed": "indicative",
            "strike_price_gte": strike - 5,
            "strike_price_lte": strike + 5,
            "expiration_date": expiration,
            "type": "call" if right.lower() == "call" else "put",
        }
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()

        snapshots = data.get("snapshots") or {}
        if not snapshots:
            return None

        # Pick the contract whose strike is closest to requested
        def _strike_from_occ(s: str) -> float:
            # last 8 chars = strike × 1000, padded
            return int(s[-8:]) / 1000.0

        best_occ = min(snapshots.keys(), key=lambda s: abs(_strike_from_occ(s) - strike))
        snap = snapshots[best_occ]
        occ = best_occ

        quote = snap.get("latestQuote") or {}
        bid = quote.get("bp")
        ask = quote.get("ap")
        mid = round(((bid or 0) + (ask or 0)) / 2, 2) if (bid and ask) else None
        return {
            "occ_symbol": occ,
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "raw": snap,
        }

    def fetch_recent_bars(self, symbol: str, lookback_minutes: int = 60) -> List[Candle]:
        """Get last N minutes of 1-min bars for symbol. Returns oldest-first."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes + 5)  # buffer for clock skew

        params = {
            "timeframe": "1Min",
            "start": start.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "end": end.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "limit": lookback_minutes + 10,
            "adjustment": "raw",
            "feed": "iex",  # free tier feed
        }

        url = f"{ALPACA_DATA_URL}/stocks/{symbol}/bars"
        resp = requests.get(url, headers=self.headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        bars = data.get("bars") or []
        candles: List[Candle] = []
        for b in bars:
            # Alpaca timestamp is ISO8601 UTC. Convert to HH:MM:SS ET-ish display.
            ts = b["t"]
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                # Convert UTC -> ET (UTC-4 during DST; market hours always ET)
                et = dt - timedelta(hours=4)
                ts_display = et.strftime("%H:%M:%S")
            except Exception:
                ts_display = ts

            candles.append(Candle(
                timestamp=ts_display,
                open=float(b["o"]),
                high=float(b["h"]),
                low=float(b["l"]),
                close=float(b["c"]),
                volume=int(b["v"]),
            ))
        return candles


if __name__ == "__main__":
    # Quick test: load env, fetch TSLA, print candle count
    from pathlib import Path
    env = Path(__file__).parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

    try:
        feed = AlpacaFeed()
        bars = feed.fetch_recent_bars("TSLA", lookback_minutes=30)
        print(f"Fetched {len(bars)} TSLA 1-min bars")
        if bars:
            print(f"  First: {bars[0].timestamp} O={bars[0].open} C={bars[0].close}")
            print(f"  Last:  {bars[-1].timestamp} O={bars[-1].open} C={bars[-1].close}")
    except ValueError as e:
        print(f"Setup error: {e}")
    except requests.HTTPError as e:
        print(f"Alpaca API error: {e.response.status_code} {e.response.text}")
