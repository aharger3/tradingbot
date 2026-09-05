"""g140 / L1 verify: the batched yfinance bar fetch.

Asserts (mocking yf.download, no network):
  1. Exactly ONE yf.download() call is made per scan for the whole symbol
     set that needs the fallback (not one per symbol).
  2. Each symbol gets its own slice of candles back out of the batched frame.
  3. A second call inside the 55s cache window makes no further yf.download
     call (cache hit); a call after the TTL re-fetches.

No network, no Tastytrade, no real market data -- pandas MultiIndex frame
built by hand to match what `yf.download(..., group_by="ticker")` returns.
"""
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

import live_scanner as ls


def _make_frame(symbols, n=10):
    """MultiIndex (symbol, field) frame like yf.download(group_by='ticker')."""
    idx = pd.date_range("2026-09-04 09:30", periods=n, freq="1min",
                         tz="America/New_York")
    cols = pd.MultiIndex.from_product(
        [symbols, ["Open", "High", "Low", "Close", "Volume"]],
        names=["Ticker", "Price"])
    data = {}
    for s in symbols:
        for j, field in enumerate(["Open", "High", "Low", "Close"]):
            data[(s, field)] = [100.0 + j + k * 0.1 for k in range(n)]
        data[(s, "Volume")] = [1000 + k for k in range(n)]
    return pd.DataFrame(data, index=idx, columns=cols)


class BatchFetchTest(unittest.TestCase):
    def setUp(self):
        ls._YF_BATCH_CACHE.update(ts=0.0, frames=None, symbols=frozenset())

    def test_one_call_per_scan_multi_symbol(self):
        symbols = ["AAPL", "MSFT", "TSLA"]
        frame = _make_frame(symbols)
        with patch("yfinance.download", return_value=frame) as mock_dl:
            out = ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        mock_dl.assert_called_once()
        _, kwargs = mock_dl.call_args
        self.assertEqual(kwargs.get("group_by"), "ticker")
        self.assertEqual(kwargs.get("threads"), False)
        self.assertEqual(set(out.keys()), set(symbols))

    def test_per_symbol_slicing(self):
        symbols = ["AAPL", "MSFT"]
        frame = _make_frame(symbols, n=5)
        with patch("yfinance.download", return_value=frame):
            out = ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        for s in symbols:
            self.assertEqual(len(out[s]), 5)
            first, last = out[s][0], out[s][-1]
            self.assertAlmostEqual(first.open, 100.0)
            self.assertGreater(last.close, first.open)  # frame counts up
            self.assertTrue(last.timestamp)  # HH:MM:SS string, non-empty

    def test_missing_symbol_maps_to_empty(self):
        symbols = ["AAPL", "MSFT"]
        frame = _make_frame(["AAPL"])  # MSFT absent from the returned frame
        with patch("yfinance.download", return_value=frame):
            out = ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        self.assertEqual(out["MSFT"], [])
        self.assertGreater(len(out["AAPL"]), 0)

    def test_cache_hit_inside_55s(self):
        symbols = ["AAPL", "MSFT"]
        frame = _make_frame(symbols)
        with patch("yfinance.download", return_value=frame) as mock_dl:
            ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
            ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        mock_dl.assert_called_once()  # second call served from cache

    def test_cache_miss_after_ttl(self):
        symbols = ["AAPL", "MSFT"]
        frame = _make_frame(symbols)
        with patch("yfinance.download", return_value=frame) as mock_dl:
            ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
            ls._YF_BATCH_CACHE["ts"] = time.time() - 56  # force TTL expiry
            ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        self.assertEqual(mock_dl.call_count, 2)

    def test_retries_once_on_rate_limit_then_gives_up(self):
        symbols = ["AAPL"]
        with patch("yfinance.download",
                   side_effect=Exception("Too Many Requests")) as mock_dl:
            out = ls._yf_batch_recent_bars(symbols, lookback_minutes=60)
        self.assertEqual(mock_dl.call_count, 2)  # one retry, then give up
        self.assertEqual(out["AAPL"], [])

    def test_scan_once_uses_one_batched_call_for_all_tasty_failures(self):
        """Integration: tasty_feed fails for every symbol -> scan_once should
        route them all through exactly one _yf_batch_recent_bars call."""
        from signal_runner import SignalRunner
        symbols = ["AAPL", "MSFT", "TSLA"]
        runner = SignalRunner(post_to_discord=False)

        class DeadTastyFeed:
            def fetch_recent_bars(self, *a, **kw):
                raise RuntimeError("device challenge")

        frame = _make_frame(symbols, n=10)
        with patch("yfinance.download", return_value=frame) as mock_dl:
            ls.scan_once(runner, DeadTastyFeed(), symbols, set(), paper=None)
        mock_dl.assert_called_once()


if __name__ == "__main__":
    unittest.main()
