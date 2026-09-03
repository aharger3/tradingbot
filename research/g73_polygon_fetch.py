"""G7.3 / polygon - pull REAL option minute bars for book rows, from the key already in .env.

What this proves, and it is the whole point: the option contracts the book's trades would
have bought are downloadable TODAY, at 1-minute granularity, for EXPIRED contracts, two
years back, with the Polygon key already sitting in tradingbot/.env. No new purchase.

What the key is NOT entitled to (measured 2026-08-29, see g73_polygon.md):
  /v3/quotes/O:...   403   -> no bid/ask, no NBBO, no spread. Options Advanced, $199/mo.
  /v3/trades/O:...   403   -> no tick tape.
  /v3/snapshot/...   403   -> no greeks, no IV, no open interest.
  1-second aggs      403
  minute aggs before (today - 2 years)  403  "Your plan doesn't include this data timeframe"

Rate limit measured on this key: FIVE calls per minute, on options AND stocks. That is the
free "Options Basic" signature, not the paid Starter (Starter = unlimited calls + snapshot
+ second aggs + greeks). Everything here is therefore paced and cached to disk so a re-run
costs zero calls.

Cache:  research/g73_polygon_cache/{catalog,aggs}/*.json
Usage:  python research/g73_polygon_fetch.py            # resumable, safe to re-run
        python research/g73_polygon_fetch.py --probe    # entitlement probe only, 6 calls
"""
import datetime as dt
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from polygon_feed import _api_key  # noqa: E402

CACHE = ROOT / "research" / "g73_polygon_cache"
(CACHE / "catalog").mkdir(parents=True, exist_ok=True)
(CACHE / "aggs").mkdir(parents=True, exist_ok=True)

FOCUS = ("COIN", "TSLA", "PLTR")     # the three most-traded symbols in the book
WINDOW_START = "2024-08-29"          # measured entitlement floor: exactly 2y, rolling
BOOK = ROOT / "research" / "bt2y_trades.json"
SAMPLE_PER_SYM = int(os.environ.get("G73_SAMPLE", "80"))
ET = ZoneInfo("America/New_York")

_K = _api_key()
_S = requests.Session()
_bucket = []
_window = 31.0   # seconds per 5 calls; widened automatically on a 429


def _scrub(s):
    return str(s).replace(_K, "<KEY>")


def _get(path, **params):
    """One paced GET. 5 calls/min token bucket + 429 backoff. Never prints the key."""
    global _bucket, _window
    params["apiKey"] = _K
    for _ in range(10):
        while True:
            now = time.time()
            _bucket = [t for t in _bucket if now - t < _window]
            if len(_bucket) >= 5:
                time.sleep(max(0.5, _window - (now - _bucket[0])))
                continue
            break
        _bucket.append(time.time())
        try:
            r = _S.get("https://api.polygon.io" + path, params=params, timeout=45)
        except Exception as e:
            print(_scrub("  net error " + str(e)), flush=True)
            time.sleep(10)
            continue
        if r.status_code == 429:
            # widen the window and retry: the documented free-tier cap is "5 calls per
            # minute" but the observed bucket refills faster than that, so this walks
            # the pace down to whatever the server actually allows instead of guessing.
            _window = min(70.0, _window * 1.4)
            time.sleep(5)
            continue
        if r.status_code != 200:
            return {"_status": r.status_code, "_body": _scrub(r.text[:200])}
        return r.json()
    return {"_status": 429, "_body": "gave up after backoff"}


# ---------------------------------------------------------------- catalog
def catalog(sym, month):
    """Every listed contract for `sym` expiring in `month` (YYYY-MM), expired included.

    One API call per (symbol, month) rather than one per trading day: at 5 calls/min,
    call economy is the binding constraint on this whole exercise.
    """
    f = CACHE / "catalog" / (sym + "_" + month + ".json")
    if f.exists():
        return json.loads(f.read_text())
    y, m = int(month[:4]), int(month[5:7])
    lo = month + "-01"
    hi = "%04d-%02d-01" % (y + (1 if m == 12 else 0), (m % 12) + 1)
    kw = {"expiration_date.gte": lo, "expiration_date.lt": hi}
    j = _get("/v3/reference/options/contracts", underlying_ticker=sym,
             expired="true", limit=1000, **kw)
    if "_status" in j:
        print(_scrub("  catalog %s %s: HTTP %s" % (sym, month, j["_status"])), flush=True)
        return []
    out = list(j.get("results") or [])
    while j.get("next_url") and len(out) < 6000:
        nxt = j["next_url"].replace("https://api.polygon.io", "")
        base, _, qs = nxt.partition("?")
        kw2 = dict(p.split("=", 1) for p in qs.split("&") if p and "apiKey" not in p)
        j = _get(base, **kw2)
        if "_status" in j:
            break
        out += list(j.get("results") or [])
    f.write_text(json.dumps(out))
    return out


def pick_contract(sym, day, entry_px, is_call):
    """The contract a robot would actually buy: nearest listed expiry on/after `day`,
    strike nearest the entry price. Listing record only -- no look-ahead into prices."""
    cands = catalog(sym, day[:7])
    if not any(c.get("expiration_date", "") >= day for c in cands):
        y, m = int(day[:4]), int(day[5:7])
        cands = cands + catalog(sym, "%04d-%02d" % (y + (1 if m == 12 else 0), (m % 12) + 1))
    want = "call" if is_call else "put"
    cands = [c for c in cands
             if c.get("contract_type") == want
             and c.get("expiration_date", "") >= day
             and c.get("shares_per_contract", 100) == 100]
    if not cands:
        return None
    exp = min(c["expiration_date"] for c in cands)
    same = [c for c in cands if c["expiration_date"] == exp]
    best = min(same, key=lambda c: abs(c["strike_price"] - entry_px))
    dte = (dt.date.fromisoformat(exp) - dt.date.fromisoformat(day)).days
    return {"ticker": best["ticker"], "strike": best["strike_price"],
            "expiry": exp, "dte": dte}


# ---------------------------------------------------------------- aggs
def option_minutes(ticker, day):
    """{'HH:MM': OHLCV} of REAL 1-minute option bars. Cached; one call ever per pair."""
    f = CACHE / "aggs" / (ticker.replace(":", "_") + "_" + day + ".json")
    if f.exists():
        return json.loads(f.read_text())
    j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (ticker, day, day),
             adjusted="true", sort="asc", limit=50000)
    if "_status" in j:
        out = {"_error": j["_status"]}
    else:
        out = {}
        for b in (j.get("results") or []):
            ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
            out[ts.strftime("%H:%M")] = {"o": b["o"], "h": b["h"], "l": b["l"],
                                         "c": b["c"], "v": b["v"]}
    f.write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------- sample
def sample_rows():
    b = json.loads(BOOK.read_text())
    tr = [r for r in b["trades"] if r.get("traded") and r["sym"] in FOCUS
          and r["day"] >= WINDOW_START]
    buckets = defaultdict(list)
    for r in tr:
        q = "%sQ%d" % (r["day"][:4], (int(r["day"][5:7]) - 1) // 3 + 1)
        buckets[(r["sym"], q)].append(r)
    out = []
    for sym in FOCUS:
        qs = sorted(q for (s, q) in buckets if s == sym)
        per = max(1, SAMPLE_PER_SYM // max(1, len(qs)))
        for q in qs:
            rows = sorted(buckets[(sym, q)], key=lambda r: (r["day"], r["et"]))
            step = max(1, len(rows) // per)
            out += rows[::step][:per]
    return out


def main():
    if "--probe" in sys.argv:
        t = "O:NVDA250613C00141000"
        checks = [
            ("minute aggs (expired 0DTE)",
             "/v2/aggs/ticker/%s/range/1/minute/2025-06-13/2025-06-13" % t),
            ("NBBO quotes", "/v3/quotes/%s" % t),
            ("trades", "/v3/trades/%s" % t),
            ("snapshot chain", "/v3/snapshot/options/NVDA"),
            ("1-second aggs",
             "/v2/aggs/ticker/%s/range/1/second/2025-06-13/2025-06-13" % t),
            ("aggs 1 day before the 2y floor",
             "/v2/aggs/ticker/%s/range/1/minute/2024-08-28/2024-08-28" % t),
        ]
        for label, path in checks:
            j = _get(path, limit=1)
            got = "HTTP " + str(j["_status"]) if "_status" in j else "OK 200"
            print("%-34s -> %s" % (label, got), flush=True)
        return

    rows = sample_rows()
    # Fetch in a FIXED-SEED SHUFFLED order. At 5 calls/min this pull is measured in hours,
    # so whatever is cached when someone looks is a prefix of this list -- and a prefix in
    # natural order would be one symbol, one quarter, and worthless. Shuffled, any prefix
    # is a random subsample of the whole two years and all three symbols.
    import random
    random.Random(20260829).shuffle(rows)
    print("sample: %d traded rows across %s" % (len(rows), ",".join(FOCUS)), flush=True)
    ok = 0
    for i, r in enumerate(rows):
        c = pick_contract(r["sym"], r["day"], r["entry"], r["dir"] == "call")
        if not c:
            continue
        m = option_minutes(c["ticker"], r["day"])
        if "_error" not in m and m:
            ok += 1
        if i % 10 == 0:
            n = "ERR" if "_error" in m else str(len(m))
            print("  [%d/%d] %s %s %s dte=%d bars=%s"
                  % (i + 1, len(rows), r["sym"], r["day"], c["ticker"], c["dte"], n),
                  flush=True)
    print("done: %d/%d rows have a real option tape" % (ok, len(rows)), flush=True)


if __name__ == "__main__":
    main()
