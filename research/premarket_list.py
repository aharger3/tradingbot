"""research/premarket_list.py -- OMEN 10.0 V1: the 09:25 ET premarket list.

The 2026-09-05 call gives Austin one job in the reconcile-era lane: "HTF
levels premarket." He needs PDH/PDL/PMH/PML on the core book before the open,
on his phone, no jargon, so he can pencil in his own levels. This pushes ONE
ntfy message at 09:25 ET with exactly that, for every symbol in
`universe.CORE_SYMBOLS` (the same 11-symbol book the reconcile spec calls
"core 11").

Fetch path mirrors live_scanner.py's own fallback shape (see its L1 batch,
lines ~607-632: try the primary source per symbol, and whatever it can't
deliver falls into ONE batched call for the rest):

  * yesterday's daily bar (PDH/PDL) -- `polygon_feed.fetch_day`, cache-first.
    That session is closed, so caching it is exactly what the archive is for
    (same path `research/daily_fetch.py` and the overnight archiver use).
  * today's premarket bars (PMH/PML) -- a raw Polygon aggs call, in-memory
    ONLY, never written to `data_archive/`: the day isn't closed yet, and
    `research/daily_fetch.py`'s `write_day` never overwrites a file that
    already exists, so a partial-day file cached here would silently block
    tonight's full-day fill.

Whatever Polygon can't deliver for either leg (403 on a too-recent day is the
live, confirmed case as of 2026-09-05 -- see CLAUDE.md "Data sources") falls
back to ONE batched `yfinance` call for the whole remainder, the same
`yf.download(..., group_by="ticker")` shape `live_scanner._yf_batch_recent_bars`
uses, extended with `prepost=True` (needed for premarket bars; the scanner's
own batch is RTH-only) per `research/daily_fetch.py`'s `_frame`.

Usage:
    python research/premarket_list.py --dry-run     # prints, pushes nothing
    python research/premarket_list.py                # real push
    python research/premarket_list.py --test-push    # real push, title
                                                       # prefixed "[test]"

Never prints POLYGON_API_KEY: `polygon_feed` builds it into the request URL,
so every error string that might carry that URL is scrubbed first.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from signal_runner import _load_env_file   # noqa: E402
_load_env_file(ROOT / ".env")              # POLYGON_API_KEY, OMEN_NTFY_TOPIC

import universe                    # noqa: E402
import notify_ntfy                 # noqa: E402
import polygon_feed                # noqa: E402
from omen_bot import Candle        # noqa: E402

ET = ZoneInfo("America/New_York")
_APIKEY_RE = re.compile(r"apiKey=[^&\s]+", re.IGNORECASE)


def _scrub(err) -> str:
    """Never let POLYGON_API_KEY reach a log line (it rides in the URL)."""
    return _APIKEY_RE.sub("apiKey=***", str(err))


def _prev_trading_day(today: dt.date) -> dt.date:
    """Weekend-safe, not holiday-safe -- same gap PDH/PDL already carries
    everywhere else in this engine (see live_scanner._yf_daily_context)."""
    d = today - dt.timedelta(days=1)
    while d.weekday() >= 5:   # Sat=5, Sun=6
        d -= dt.timedelta(days=1)
    return d


def _polygon_today_candles(symbol: str, day_iso: str) -> list:
    """One Polygon aggs call for `day_iso`, in-memory Candles, no disk cache.

    Only ever called with TODAY's date -- see module docstring for why an
    incomplete day must never touch data_archive/.
    """
    import requests
    url = (f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/minute/"
           f"{day_iso}/{day_iso}")
    r = requests.get(url, params={"adjusted": "true", "sort": "asc",
                                  "limit": 50000, "apiKey": polygon_feed._api_key()},
                     timeout=15)
    r.raise_for_status()
    rows = r.json().get("results") or []
    out = []
    for b in rows:
        ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
        out.append(Candle(timestamp=ts.strftime("%H:%M:%S"), open=float(b["o"]),
                          high=float(b["h"]), low=float(b["l"]), close=float(b["c"]),
                          volume=int(b.get("v") or 0)))
    return out


def _yf_batch_premarket_today(symbols: list) -> dict:
    """One yf.download() for every symbol still needing today's PMH/PML.

    Mirrors live_scanner._yf_batch_recent_bars's shape, with prepost=True --
    daily_fetch.py's own note: "Premarket matters and is NOT optional."
    """
    out = {s: (None, None) for s in symbols}
    if not symbols:
        return out
    try:
        import yfinance as yf
        data = yf.download(symbols, period="1d", interval="1m", prepost=True,
                            group_by="ticker", threads=False, progress=False)
    except Exception as e:
        print(f"  [batch] yfinance premarket fetch failed: {_scrub(e)[:160]}")
        return out
    if data is None or data.empty:
        return out
    import pandas as pd
    multi = isinstance(data.columns, pd.MultiIndex)
    for s in symbols:
        try:
            df = data[s] if multi else data
        except KeyError:
            continue
        if df is None or df.empty:
            continue
        df = df.dropna(how="all")
        if df.empty:
            continue
        if df.index.tz is None:
            df = df.tz_localize("UTC")
        df = df.tz_convert(ET)
        pm = df[df.index.time < dt.time(9, 30)]
        if pm.empty:
            continue
        out[s] = (float(pm["High"].max()), float(pm["Low"].min()))
    return out


def _yf_batch_prevday(symbols: list, prev_iso: str) -> dict:
    """One yf.download() daily bar for every symbol still needing PDH/PDL."""
    out = {s: (None, None) for s in symbols}
    if not symbols:
        return out
    try:
        import yfinance as yf
        data = yf.download(symbols, period="5d", interval="1d",
                            group_by="ticker", threads=False, progress=False)
    except Exception as e:
        print(f"  [batch] yfinance daily fetch failed: {_scrub(e)[:160]}")
        return out
    if data is None or data.empty:
        return out
    import pandas as pd
    multi = isinstance(data.columns, pd.MultiIndex)
    for s in symbols:
        try:
            df = data[s] if multi else data
        except KeyError:
            continue
        if df is None or df.empty:
            continue
        df = df.dropna(how="all")
        row = None
        for ts, r in df.iterrows():
            if ts.strftime("%Y-%m-%d") == prev_iso:
                row = r
                break
        if row is None:
            row = df.iloc[-1]      # last close before today -- holiday-safe
        out[s] = (float(row["High"]), float(row["Low"]))
    return out


def fetch_levels(symbols: list, today: dt.date | None = None) -> dict:
    """{symbol: {"pdh", "pdl", "pmh", "pml"}}.

    Polygon first per symbol (both legs), whatever it can't deliver falls
    into one batched yfinance call for the remainder -- see module docstring.
    """
    today = today or dt.datetime.now(ET).date()
    today_iso = today.isoformat()
    prev_iso = _prev_trading_day(today).isoformat()

    levels = {s: {"pdh": None, "pdl": None, "pmh": None, "pml": None}
              for s in symbols}

    # -- yesterday's daily bar: PDH/PDL. fetch_day is cache-first and safe --
    # prev_iso is a closed session, so this is the archive's own fetch path.
    need_pd = []
    for s in symbols:
        try:
            day = polygon_feed.fetch_day(s, prev_iso)
            rth = polygon_feed.rth(day) if day else []
            if rth:
                levels[s]["pdh"] = max(c.high for c in rth)
                levels[s]["pdl"] = min(c.low for c in rth)
            else:
                need_pd.append(s)
        except Exception as e:
            print(f"  [{s}] polygon prev-day fetch failed ({_scrub(e)[:80]}), "
                  f"queued for yfinance")
            need_pd.append(s)
    if need_pd:
        yf_pd = _yf_batch_prevday(need_pd, prev_iso)
        for s in need_pd:
            levels[s]["pdh"], levels[s]["pdl"] = yf_pd.get(s, (None, None))

    # -- today so far: PMH/PML. Never cached -- see module docstring.
    need_pm = []
    for s in symbols:
        try:
            candles = _polygon_today_candles(s, today_iso)
            pmh, pml = polygon_feed.premarket_hi_lo(candles)
            if pmh is not None:
                levels[s]["pmh"], levels[s]["pml"] = pmh, pml
            else:
                need_pm.append(s)
        except Exception as e:
            print(f"  [{s}] polygon premarket fetch failed ({_scrub(e)[:80]}), "
                  f"queued for yfinance")
            need_pm.append(s)
    if need_pm:
        yf_pm = _yf_batch_premarket_today(need_pm)
        for s in need_pm:
            levels[s]["pmh"], levels[s]["pml"] = yf_pm.get(s, (None, None))

    return levels


def format_message(levels: dict, symbols: list) -> str:
    def fmt(x):
        return f"{x:.2f}" if x is not None else "n/a"
    return "\n".join(
        f"{s}  PDH {fmt(levels[s]['pdh'])}  PDL {fmt(levels[s]['pdl'])}  "
        f"PMH {fmt(levels[s]['pmh'])}  PML {fmt(levels[s]['pml'])}"
        for s in symbols
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                     help="print the message, push nothing")
    ap.add_argument("--test-push", action="store_true",
                     help="push for real, but prefix the title '[test]'")
    args = ap.parse_args()

    today = dt.datetime.now(ET).date()
    symbols = universe.CORE_SYMBOLS
    print(f"premarket list: {len(symbols)} symbols ({', '.join(symbols)}), "
          f"{today.isoformat()}")

    levels = fetch_levels(symbols, today)
    body = format_message(levels, symbols)
    title = f"OMEN premarket {today.isoformat()}"
    if args.test_push:
        title = f"[test] {title}"

    if args.dry_run:
        print(f"--- {title} ---")
        print(body)
        return

    ok = notify_ntfy.push(title, body, priority="default", tags="sunrise")
    print("pushed" if ok else "push failed, or ntfy not configured "
                              "(see notify_ntfy.TOPIC_ENV)")


if __name__ == "__main__":
    main()
