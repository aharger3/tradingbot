"""DXLink websocket client for tastytrade real-time quotes.

Minimal one-shot fetcher: connect, AUTH with an api-quote-token, open a FEED
channel, subscribe to Quote events for one or more dxfeed streamer symbols,
collect the first bid/ask for each, then disconnect.

DXLink protocol handshake:
    SETUP -> AUTH_STATE(UNAUTHORIZED) -> AUTH -> AUTH_STATE(AUTHORIZED)
    -> CHANNEL_REQUEST -> CHANNEL_OPENED -> FEED_SETUP -> FEED_SUBSCRIPTION
    -> FEED_DATA (Quote events)

Streamer symbols are the dxfeed symbology (e.g. ".TSLA260612C440"), NOT the
OCC symbol. Get them from the nested option chain's *-streamer-symbol fields.
"""

import json
import time
from typing import Dict, Iterable, List, Optional

from websocket import create_connection


# COMPACT Quote event field order we request from the feed.
_QUOTE_FIELDS = ["eventType", "eventSymbol", "bidPrice", "askPrice"]


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and v == v  # rejects None and NaN


def fetch_quotes(
    url: str,
    token: str,
    symbols: Iterable[str],
    timeout: float = 10.0,
) -> Dict[str, dict]:
    """Fetch one Quote (bid/ask/mid) per streamer symbol via DXLink.

    Returns {streamer_symbol: {"bid": float, "ask": float, "mid": float}}.
    Symbols with no usable bid/ask before timeout are omitted.
    """
    symbols = list(symbols)
    if not symbols:
        return {}

    out: Dict[str, dict] = {}
    deadline = time.time() + timeout
    ws = create_connection(url, timeout=timeout)
    try:
        ws.send(json.dumps({
            "type": "SETUP",
            "channel": 0,
            "version": "0.1-vanquish/1.0",
            "keepaliveTimeout": 60,
            "acceptKeepaliveTimeout": 60,
        }))

        authorized = False
        channel_open = False

        while time.time() < deadline and len(out) < len(symbols):
            ws.settimeout(max(0.1, deadline - time.time()))
            try:
                msg = json.loads(ws.recv())
            except Exception:
                break
            mtype = msg.get("type")

            if mtype == "AUTH_STATE":
                if msg.get("state") == "UNAUTHORIZED":
                    ws.send(json.dumps({"type": "AUTH", "channel": 0, "token": token}))
                elif msg.get("state") == "AUTHORIZED":
                    authorized = True
                    ws.send(json.dumps({
                        "type": "CHANNEL_REQUEST",
                        "channel": 1,
                        "service": "FEED",
                        "parameters": {"contract": "AUTO"},
                    }))

            elif mtype == "CHANNEL_OPENED" and msg.get("channel") == 1:
                channel_open = True
                ws.send(json.dumps({
                    "type": "FEED_SETUP",
                    "channel": 1,
                    "acceptAggregationPeriod": 0.1,
                    "acceptDataFormat": "COMPACT",
                    "acceptEventFields": {"Quote": _QUOTE_FIELDS},
                }))
                ws.send(json.dumps({
                    "type": "FEED_SUBSCRIPTION",
                    "channel": 1,
                    "add": [{"type": "Quote", "symbol": s} for s in symbols],
                }))

            elif mtype == "FEED_DATA":
                _parse_feed_data(msg.get("data", []), out)

            elif mtype == "KEEPALIVE":
                ws.send(json.dumps({"type": "KEEPALIVE", "channel": 0}))

            elif mtype == "ERROR":
                raise RuntimeError(f"DXLink error: {msg.get('error')} {msg.get('message')}")

        return out
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _parse_feed_data(data, out: Dict[str, dict]) -> None:
    """Parse COMPACT FEED_DATA payload, filling out[symbol] with bid/ask/mid.

    COMPACT format: data = [eventTypeName, flatValues, eventTypeName, flatValues, ...]
    where flatValues is a flat list of field values, _QUOTE_FIELDS per event.
    """
    n = len(_QUOTE_FIELDS)
    i = 0
    while i < len(data) - 1:
        event_name, values = data[i], data[i + 1]
        i += 2
        if event_name != "Quote" or not isinstance(values, list):
            continue
        for j in range(0, len(values), n):
            chunk = values[j:j + n]
            if len(chunk) < n:
                break
            _, sym, bid, ask = chunk
            if not (_is_num(bid) and _is_num(ask)):
                continue
            if bid <= 0 and ask <= 0:
                continue
            out[sym] = {"bid": float(bid), "ask": float(ask), "mid": round((bid + ask) / 2, 2)}


# ---------------------------------------------------------------------------
# Candle (OHLC bar) events — added 2026-06-13 to replace Alpaca as the
# 1-min bar source for live_scanner.py / backtest_window.py.
#
# *** NEW / UNTESTED-AGAINST-LIVE-API ***
# This sandbox has no network access to api.tastyworks.com or any DXLink
# websocket endpoint, so this code has only been reviewed for correctness
# against the dxfeed/DXLink Candle protocol as documented — it has NOT been
# exercised against a real feed. Verify against live data before relying on
# it for trading decisions. If it doesn't return bars, the scanner will log
# "only 0 bars, skipping" for every symbol (same failure mode as the old
# Alpaca-stub fallback) rather than crash, but it will not fire signals.
#
# Candle symbol format is "{symbol}{=1m}" (e.g. "AAPL{=1m}") for 1-minute
# bars. The "HISTORY" contract + "fromTime" (epoch ms) parameter requests
# a backfill of past candles in addition to live updates.
# ---------------------------------------------------------------------------

_CANDLE_FIELDS = ["eventType", "eventSymbol", "time", "open", "high", "low", "close", "volume"]


def fetch_candles(
    url: str,
    token: str,
    symbol: str,
    from_time_ms: int,
    period: str = "1m",
    timeout: float = 10.0,
) -> List[dict]:
    """Fetch recent Candle (OHLCV bar) events for one symbol via DXLink.

    `symbol` is the plain dxfeed/underlying symbol (e.g. "AAPL"); `period`
    is appended as DXLink's candle-symbol suffix, producing e.g. "AAPL{=1m}".
    `from_time_ms` is the start of the lookback window (epoch milliseconds);
    DXLink streams backfill candles from that point plus live updates until
    `timeout` elapses.

    Returns a list of dicts {"time": ms, "open", "high", "low", "close",
    "volume"} sorted by time ascending. Empty list on any failure (caller
    treats this the same as "no bars yet").
    """
    candle_symbol = f"{symbol}{{={period}}}"
    out: List[dict] = []
    deadline = time.time() + timeout
    ws = create_connection(url, timeout=timeout)
    try:
        ws.send(json.dumps({
            "type": "SETUP",
            "channel": 0,
            "version": "0.1-vanquish/1.0",
            "keepaliveTimeout": 60,
            "acceptKeepaliveTimeout": 60,
        }))

        while time.time() < deadline:
            ws.settimeout(max(0.1, deadline - time.time()))
            try:
                msg = json.loads(ws.recv())
            except Exception:
                break
            mtype = msg.get("type")

            if mtype == "AUTH_STATE":
                if msg.get("state") == "UNAUTHORIZED":
                    ws.send(json.dumps({"type": "AUTH", "channel": 0, "token": token}))
                elif msg.get("state") == "AUTHORIZED":
                    ws.send(json.dumps({
                        "type": "CHANNEL_REQUEST",
                        "channel": 1,
                        "service": "FEED",
                        "parameters": {"contract": "HISTORY"},
                    }))

            elif mtype == "CHANNEL_OPENED" and msg.get("channel") == 1:
                ws.send(json.dumps({
                    "type": "FEED_SETUP",
                    "channel": 1,
                    "acceptAggregationPeriod": 0.1,
                    "acceptDataFormat": "COMPACT",
                    "acceptEventFields": {"Candle": _CANDLE_FIELDS},
                }))
                ws.send(json.dumps({
                    "type": "FEED_SUBSCRIPTION",
                    "channel": 1,
                    "add": [{"type": "Candle", "symbol": candle_symbol, "fromTime": from_time_ms}],
                }))

            elif mtype == "FEED_DATA":
                _parse_candle_feed_data(msg.get("data", []), out)

            elif mtype == "KEEPALIVE":
                ws.send(json.dumps({"type": "KEEPALIVE", "channel": 0}))

            elif mtype == "ERROR":
                raise RuntimeError(f"DXLink error: {msg.get('error')} {msg.get('message')}")

        out.sort(key=lambda c: c["time"])
        return out
    finally:
        try:
            ws.close()
        except Exception:
            pass


def _parse_candle_feed_data(data, out: List[dict]) -> None:
    """Parse COMPACT FEED_DATA payload, appending Candle events to `out`.

    COMPACT format: data = [eventTypeName, flatValues, eventTypeName, flatValues, ...]
    where flatValues is a flat list of field values, _CANDLE_FIELDS per event.
    """
    n = len(_CANDLE_FIELDS)
    i = 0
    while i < len(data) - 1:
        event_name, values = data[i], data[i + 1]
        i += 2
        if event_name != "Candle" or not isinstance(values, list):
            continue
        for j in range(0, len(values), n):
            chunk = values[j:j + n]
            if len(chunk) < n:
                break
            _, _sym, t, o, h, l, c, v = chunk
            if not (_is_num(t) and _is_num(c)):
                continue
            out.append({
                "time": int(t),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v if _is_num(v) else 0,
            })
# end of file
