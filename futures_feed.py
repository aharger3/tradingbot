"""Omen futures data feed — ES/NQ/RTY candles in the same Candle format
as the stock feed, so the strategy engine doesn't care what it's trading.

Source: yfinance continuous front-month contracts (ES=F etc). Free, ~15min
delayed on some exchanges but fine for signal generation and paper trading.
# ponytail: yfinance delayed feed; swap to Tradier/databento when going live on futures
"""
from typing import List, Optional

import yfinance as yf

from omen_bot import Candle

YF_SYMBOLS = {"ES": "ES=F", "NQ": "NQ=F", "RTY": "RTY=F"}

# Contract economics
POINT_VALUE = {"ES": 50.0, "NQ": 20.0, "RTY": 50.0}   # $ per full point, 1 contract
TICK_SIZE = {"ES": 0.25, "NQ": 0.25, "RTY": 0.10}


class FuturesFeed:
    """Real-time-ish futures data (ES, NQ, RTY) as Candle lists."""

    def __init__(self):
        self.contracts = list(YF_SYMBOLS)

    def get_candles(self, contract: str, timeframe: str = "1m", count: int = 100) -> List[Candle]:
        """timeframe: yfinance interval ('1m','5m','15m'). Returns newest-last."""
        sym = YF_SYMBOLS[contract.upper()]
        period = "1d" if timeframe == "1m" else "5d"
        df = yf.Ticker(sym).history(period=period, interval=timeframe)
        candles = [
            Candle(
                timestamp=ts.isoformat(),
                open=float(r["Open"]),
                high=float(r["High"]),
                low=float(r["Low"]),
                close=float(r["Close"]),
                volume=int(r["Volume"]),
            )
            for ts, r in df.iterrows()
        ]
        return candles[-count:]

    def get_current_price(self, contract: str) -> Optional[float]:
        candles = self.get_candles(contract, "1m", 1)
        return candles[-1].close if candles else None

    # --- TastytradeFeed-compatible interface so live_scanner can swap feeds ---

    def validate_credentials(self):
        return True  # public data, no auth

    def fetch_recent_bars(self, symbol: str, lookback_minutes: int = 60) -> List[Candle]:
        return self.get_candles(symbol, "1m", lookback_minutes)

    def fetch_daily_levels(self, symbol: str, timeout: float = 10.0):
        """(pdh, pdl, pd_open, pd_close) from daily candles."""
        sym = YF_SYMBOLS[symbol.upper()]
        df = yf.Ticker(sym).history(period="5d", interval="1d")
        if len(df) < 2:
            return None
        prev = df.iloc[-2]
        return (float(prev["High"]), float(prev["Low"]),
                float(prev["Open"]), float(prev["Close"]))

    def fetch_htf_bias(self, symbol: str, timeout: float = 10.0) -> Optional[str]:
        """'bullish'/'bearish' from 1h close vs 20-period SMA."""
        candles = self.get_candles(symbol, "1h", 40)
        if len(candles) < 20:
            return None
        closes = [c.close for c in candles]
        sma20 = sum(closes[-20:]) / 20
        return "bullish" if closes[-1] > sma20 else "bearish"


if __name__ == "__main__":
    feed = FuturesFeed()
    for c in ("ES", "NQ"):
        candles = feed.get_candles(c, "1m", 5)
        assert candles, f"no candles for {c}"
        assert candles[-1].close > 0
        print(f"{c}: {len(candles)} candles, last close {candles[-1].close}")
    print("futures feed self-check OK")
