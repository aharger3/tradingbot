import csv
from datetime import datetime

import pytest

from stock_cards import alpaca_bars, config
from stock_cards.config import ET


def test_to_candles_converts_utc_to_et_bar_start():
    rows = [{"t": "2026-10-02T13:30:00Z", "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10},
            {"t": "2026-10-02T13:31:00Z", "o": 1.5, "h": 2, "l": 1, "c": 1.8, "v": 7},
            {"t": "2026-10-02T13:31:00Z", "o": 9, "h": 9, "l": 9, "c": 9, "v": 1}]       # duplicate minute ignored
    cs = alpaca_bars.to_candles(rows)
    assert [c.timestamp for c in cs] == ["09:30:00", "09:31:00"] and cs[1].close == 1.8


def test_fetch_follows_pages_and_never_leaks_keys():
    pages = [{"bars": {"A": [{"t": "2026-10-02T13:30:00Z"}]}, "next_page_token": "p2"},
             {"bars": {"A": [{"t": "2026-10-02T13:31:00Z"}], "B": [{"t": "2026-10-02T13:30:00Z"}]},
              "next_page_token": None}]
    seen = []

    class R:
        def __init__(self, j, code=200):
            self._j, self.status_code = j, code

        def json(self):
            return self._j

    class S:
        def get(self, url, params=None, headers=None, timeout=0):
            seen.append((params.get("page_token"), params["feed"]))
            return R(pages[len(seen) - 1])

    start, end = datetime(2026, 10, 2, 4, tzinfo=ET), datetime(2026, 10, 2, 11, tzinfo=ET)
    out = alpaca_bars.fetch_bars(["A", "B"], start, end, session=S(), hdrs={"k": "v"})
    assert [len(out["A"]), len(out["B"])] == [2, 1] and seen == [(None, "iex"), ("p2", "iex")]

    class Bad:
        def get(self, *a, **k):
            return R({}, 401)

    with pytest.raises(RuntimeError) as e:
        alpaca_bars.fetch_bars(["A"], start, end, session=Bad(), hdrs={"APCA-API-KEY-ID": "SECRETKEY"})
    assert "SECRETKEY" not in str(e.value)


def test_headers_need_both_keys():
    with pytest.raises(alpaca_bars.AlpacaConfigError):
        alpaca_bars.headers(lambda n: "")
    assert alpaca_bars.headers(lambda n: "x")["APCA-API-KEY-ID"] == "x"


def test_the_only_endpoint_is_market_data():
    assert alpaca_bars.DATA_URL.startswith("https://data.alpaca.markets/") and "order" not in alpaca_bars.DATA_URL


def test_vault_secret_ignores_a_stale_environment_variable(monkeypatch):
    monkeypatch.setenv("ALPACA_PAPER_KEY", "stale-env-value")
    assert alpaca_bars.vault_secret("ALPACA_PAPER_KEY") == ""          # the test keys.py path does not exist: vault only


def test_watchlist_from_s_trades_and_fallback(tmp_path):
    p = tmp_path / "s_trades.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["sym", "grade"])
        w.writerows([["tsla", "S"], ["AAPL", "S"], ["TSLA", "A"]])
    assert config.load_watchlist(p) == ["AAPL", "TSLA"]
    assert config.load_watchlist(tmp_path / "missing.csv") == list(config.FALLBACK_WATCHLIST)
    assert len(config.FALLBACK_WATCHLIST) == 28


def test_send_flag(tmp_path):
    assert config.send_enabled(tmp_path) is False
    (tmp_path / config.SEND_FLAG_NAME).write_text("")
    assert config.send_enabled(tmp_path) is True
