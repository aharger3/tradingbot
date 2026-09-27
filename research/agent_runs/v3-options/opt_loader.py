"""v3 options loader (paper research only).
load_option_bars(signal_ts, direction, underlying, mode='atm'|'otm1', spot=None)
 -> (meta dict, DataFrame of that contract's 1-min trade bars, ET index)
Picks 0DTE if listed, else nearest expiry >= signal date. Greeks are NOT on this key
(snapshot 403, and historical greeks never exist), so the 0.30-0.40 delta target is
approximated by 'otm1' = nearest strike strictly OTM. Key: POLYGON_API_KEY (never printed).
Rate: key allows 5 calls/min -> 12.5 s spacing + 429 backoff; everything disk-cached."""
import os, json, time, pathlib
import pandas as pd, requests

B = "https://api.polygon.io"
HERE = pathlib.Path(__file__).resolve().parent
CACHE = HERE / "cache"; CACHE.mkdir(exist_ok=True)
ARCH = HERE.parents[2] / "data_archive"          # tradingbot\data_archive\{SYM}\{date}.csv
ET = "America/New_York"
_S = requests.Session(); _last = [0.0]
MIN_GAP = float(os.environ.get("POLY_MIN_GAP", "12.5"))

def cache_key(path, **p):
    """Cache filename for a Polygon endpoint call. Maps both '/' and ':' to '_':
    a raw ':' inside a Windows filename (e.g. ticker 'O:SPXW250326P05745000')
    opens an NTFS alternate data stream instead of a regular file -- invisible to
    plain directory listings/copies, and git never stores them (2026-09-26 data
    loss). Old entries written before this fix are found via find_cached()."""
    name = path.strip("/").replace("/", "_").replace(":", "_")
    return CACHE / (name + "_" + "_".join(f"{k}-{v}" for k, v in sorted(p.items())) + ".json")

def _cache_key_legacy(path, **p):
    """Pre-fix (':'-preserving) cache filename. Read fallback only; never written."""
    name = path.strip("/").replace("/", "_")
    return CACHE / (name + "_" + "_".join(f"{k}-{v}" for k, v in sorted(p.items())) + ".json")

def find_cached(path, **p):
    """Existing cache file for this call: new-style ('_') preferred, else legacy
    (':') name. Returns None if neither exists."""
    key = cache_key(path, **p)
    if key.exists():
        return key
    legacy = _cache_key_legacy(path, **p)
    return legacy if legacy != key and legacy.exists() else None

def _get(path, **p):
    hit = find_cached(path, **p)
    if hit is not None:
        return json.loads(hit.read_text())
    key = cache_key(path, **p)
    p["apiKey"] = os.environ["POLYGON_API_KEY"]
    for attempt in range(6):
        wait = MIN_GAP - (time.time() - _last[0])
        if wait > 0: time.sleep(wait)
        r = _S.get(B + path, params=p, timeout=30); _last[0] = time.time()
        if r.status_code == 429:
            time.sleep(15 * (attempt + 1)); continue
        j = r.json()
        if r.status_code != 200:
            raise RuntimeError(f"{r.status_code} {path}: {str(j.get('message',''))[:120]}")
        key.write_text(json.dumps(j)); return j
    raise RuntimeError(f"429 x6 {path}")

def spot_at(underlying, ts):
    """Close of the 1-min bar that opens at ts (signal bar), from archive, else API (SPY/QQQ only)."""
    d = ts.strftime("%Y-%m-%d"); f = ARCH / underlying / f"{d}.csv"
    if f.exists():
        df = pd.read_csv(f)
        idx = pd.to_datetime(df["Datetime"], format="mixed", utc=True).dt.tz_convert(ET)
        s = pd.Series(df["Close"].values, index=idx)
        s = s[s.index <= ts]
        if len(s): return float(s.iloc[-1]), "archive"
    j = _get(f"/v2/aggs/ticker/{underlying}/range/1/minute/{d}/{d}", adjusted="true", sort="asc", limit=50000)
    b = _bars(j); b = b[b.index <= ts]
    if not len(b): raise RuntimeError(f"no spot for {underlying} {ts}")
    return float(b["c"].iloc[-1]), "api"

def _bars(j):
    r = j.get("results") or []
    if not r: return pd.DataFrame(columns=["o","h","l","c","v","vw","n"])
    df = pd.DataFrame(r)
    df.index = pd.to_datetime(df.pop("t"), unit="ms", utc=True).dt.tz_convert(ET)
    return df[[c for c in ["o","h","l","c","v","vw","n"] if c in df]]

def chain(underlying, date, ctype):
    """Contracts listed for this date: 0DTE first, else nearest expiry within 7 days."""
    ref = "SPX" if underlying in ("SPX", "SPXW") else underlying
    for exp_kw in ({"expiration_date": date}, {"expiration_date.gte": date, "expiration_date.lte": (pd.Timestamp(date)+pd.Timedelta(days=7)).strftime("%Y-%m-%d")}):
        j = _get("/v3/reference/options/contracts", underlying_ticker=ref, contract_type=ctype,
                 as_of=date, limit=1000, sort="expiration_date", order="asc", **exp_kw)
        res = j.get("results") or []
        if ref == "SPX":   # SPXW = PM-settled dailies; prefer them
            w = [c for c in res if c["ticker"].startswith("O:SPXW")]; res = w or res
        if res:
            exp = min(c["expiration_date"] for c in res)
            return [c for c in res if c["expiration_date"] == exp], exp
    return [], None

def load_option_bars(signal_ts, direction, underlying="SPY", mode="atm", spot=None):
    ts = pd.Timestamp(signal_ts); ts = ts.tz_localize(ET) if ts.tzinfo is None else ts.tz_convert(ET)
    d = ts.strftime("%Y-%m-%d"); ctype = "call" if direction > 0 else "put"
    src = "given"
    if spot is None: spot, src = spot_at(underlying, ts)
    cons, exp = chain(underlying, d, ctype)
    if not cons: raise RuntimeError(f"no {ctype} contracts {underlying} {d}")
    ks = sorted({c["strike_price"] for c in cons})
    atm = min(ks, key=lambda k: (abs(k - spot), k))
    if mode == "atm": k = atm
    else:  # nearest strictly-OTM strike (proxy for delta 0.30-0.40, no greeks on key)
        otm = [x for x in ks if (x > spot if ctype == "call" else x < spot)]
        k = min(otm, key=lambda x: abs(x - spot))
    tk = next(c["ticker"] for c in cons if c["strike_price"] == k)
    j = _get(f"/v2/aggs/ticker/{tk}/range/1/minute/{d}/{d}", adjusted="true", sort="asc", limit=50000)
    bars = _bars(j)
    meta = dict(ticker=tk, strike=k, expiry=exp, dte=(pd.Timestamp(exp) - pd.Timestamp(d)).days,
                spot=spot, spot_src=src, n_strikes=len(ks), mode=mode, n_bars_day=len(bars),
                n_bars_after_signal=int((bars.index > ts).sum()))
    return meta, bars

if __name__ == "__main__":
    import sys
    m, b = load_option_bars(sys.argv[1], int(sys.argv[2]), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "atm")
    print(m); print(b.head())
