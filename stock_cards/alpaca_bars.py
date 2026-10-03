"""Alpaca market data, read only: 1-minute bars on the free IEX feed. No order endpoint is ever called.

Keys come from the keys vault (ALPACA_PAPER_KEY / ALPACA_PAPER_SECRET); they are never logged or written.
IEX is one venue, not the consolidated tape: thin names miss minutes and volumes are a few percent of the total.
The engine tape and the archive are Polygon (consolidated); the difference is measured in the dry-run log.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Iterable

from omen_bot import Candle

from .config import ET, UTC

DATA_URL = "https://data.alpaca.markets/v2/stocks/bars"
PAGE_LIMIT = 10000


class AlpacaConfigError(RuntimeError):
    pass


def vault_secret(name: str) -> str:
    """Vault only, never the process environment: on this PC the Machine-level ALPACA_PAPER_KEY/SECRET env vars are
    stale copies of the live-account keys (401 on market data), while the vault entries work. Checked 2026-10-03."""
    import os
    import subprocess
    import sys
    from eye_card.vault import KEYS_PY
    if not os.path.exists(KEYS_PY):
        return ""
    r = subprocess.run([sys.executable, KEYS_PY, "get", name], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def headers(secret: Callable[[str], str] | None = None) -> dict:
    secret = secret or vault_secret
    kid, sec = secret("ALPACA_PAPER_KEY"), secret("ALPACA_PAPER_SECRET")
    if not (kid and sec):
        raise AlpacaConfigError("ALPACA_PAPER_KEY / ALPACA_PAPER_SECRET missing")
    return {"APCA-API-KEY-ID": kid, "APCA-API-SECRET-KEY": sec}


def _rfc3339(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_bars(symbols: Iterable[str], start: datetime, end: datetime, *, session=None, hdrs: dict | None = None,
               feed: str = "iex", timeout: float = 20.0) -> dict[str, list[dict]]:
    """{symbol: [raw Alpaca bar dicts, ascending]} for [start, end). Follows next_page_token."""
    import requests
    sess = session or requests
    hdrs = hdrs if hdrs is not None else headers()
    syms = sorted({s.upper() for s in symbols})
    out: dict[str, list[dict]] = {s: [] for s in syms}
    token = None
    for _ in range(200):                      # hard bound on pages
        params = {"symbols": ",".join(syms), "timeframe": "1Min", "start": _rfc3339(start), "end": _rfc3339(end),
                  "feed": feed, "limit": PAGE_LIMIT, "adjustment": "split", "sort": "asc"}
        if token:
            params["page_token"] = token
        r = sess.get(DATA_URL, params=params, headers=hdrs, timeout=timeout)
        if r.status_code != 200:
            raise RuntimeError(f"alpaca bars HTTP {r.status_code}")      # never echo headers or the body
        j = r.json()
        for s, rows in (j.get("bars") or {}).items():
            out.setdefault(s, []).extend(rows)
        token = j.get("next_page_token")
        if not token:
            break
    return out


def to_candles(rows: list[dict]) -> list[Candle]:
    """Raw bars -> engine Candles. timestamp = 'HH:MM:SS' ET of the bar START, as in the Polygon archive."""
    out, seen = [], set()
    for b in rows:
        t = datetime.fromisoformat(b["t"].replace("Z", "+00:00")).astimezone(ET)
        ts = t.strftime("%H:%M:%S")
        if ts in seen:
            continue
        seen.add(ts)
        out.append(Candle(timestamp=ts, open=float(b["o"]), high=float(b["h"]), low=float(b["l"]),
                          close=float(b["c"]), volume=int(b.get("v") or 0)))
    out.sort(key=lambda c: c.timestamp)
    return out
