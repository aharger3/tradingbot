"""massive_futures.py -- tracked MNQ/NQ 1-min fetcher + volume-roll stitcher.

Source: Massive REST  GET /futures/v1/aggs/{ticker}
  (https://massive.com/docs/rest/futures/aggregates.md). results[] carry
  open/high/low/close/volume/transactions/window_start (ns); a 1session bar's
  window_start is the day BEFORE its session_end_date.

Key: read ONLY from env POLYGON_API_KEY at call time, sent as a Bearer header
(never placed in a URL, never logged). Missing -> CLI exits 2.
Rate: <=5 calls/min (a 429 was seen beyond that) -> default throttle 12.5s.

Output CSV schema == omen_data.load_fut input: {ROOT}{M}{Y}_{YYYY}.csv with
columns ts_ns (UTC ns),open,high,low,close,volume. Note omen_data globs by data
root ("NQ*"), so MNQ files are named with the root you pass; point load_fut at
them (or pass root NQ) -- this module does not edit omen_data.py.
Roll rule: per session the contract with max 1session volume; never back to an
earlier expiry. Series is unadjusted. No orders, no engine files touched.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
import urllib.request
from datetime import date as Date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = "https://api.massive.com"
ET = ZoneInfo("America/New_York")
MONTH_CODE = {3: "H", 6: "M", 9: "U", 12: "Z"}   # same cycle as research/front_month.py (PR #82)
CODE_MONTH = {v: k for k, v in MONTH_CODE.items()}
MIN_INTERVAL = 12.5                               # 60s / 5 calls, plus margin
KEY_ENV = "POLYGON_API_KEY"
CSV_COLS = ["ts_ns", "open", "high", "low", "close", "volume"]


def contract_ticker(root: str, year: int, month: int) -> str:
    """('MNQ', 2026, 12) -> 'MNQZ6'."""
    if month not in MONTH_CODE:
        raise ValueError(f"not a quarterly month: {month}")
    return f"{root}{MONTH_CODE[month]}{year % 10}"


def _d(x) -> Date:
    return x if isinstance(x, Date) and not isinstance(x, datetime) else Date.fromisoformat(str(x)[:10])


def third_friday(year: int, month: int) -> Date:
    first = Date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def quarterly_contracts(root: str, start, end) -> list[str]:
    """Quarterlies needed for [start, end]: every contract with expiry >= start up to
    and including the first one with expiry > end (the next contract, for the roll)."""
    start, end = _d(start), _d(end)
    out = []
    for y in range(start.year, end.year + 2):
        for m in (3, 6, 9, 12):
            exp = third_friday(y, m)
            if exp < start:
                continue
            out.append(contract_ticker(root, y, m))
            if exp > end:
                return out
    return out


def expiry_key(ticker: str, ref_year: int) -> tuple[int, int]:
    """Sortable (year, month) from e.g. 'MNQZ6'; the one-digit year resolves to the
    earliest year >= ref_year-1 with that last digit."""
    digit, code = int(ticker[-1]), ticker[-2]
    y = next(y for y in range(ref_year - 1, ref_year + 10) if y % 10 == digit)
    return (y, CODE_MONTH[code])


def build_url(ticker: str, resolution: str, gte, lt, limit: int = 50000) -> str:
    return (f"{BASE}/futures/v1/aggs/{ticker}?resolution={resolution}"
            f"&window_start.gte={gte}&window_start.lt={lt}&limit={limit}")


class Throttle:
    def __init__(self, interval: float = MIN_INTERVAL, sleep=time.sleep, clock=time.monotonic):
        self.interval, self.sleep, self.clock, self.last = interval, sleep, clock, None

    def __call__(self):
        now = self.clock()
        if self.last is not None and now - self.last < self.interval:
            self.sleep(self.interval - (now - self.last))
        self.last = self.clock()


def http_fetch(url: str) -> dict:
    key = os.environ.get(KEY_ENV)
    if not key:
        raise RuntimeError(f"{KEY_ENV} not set")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def fetch_aggs(ticker, resolution, gte, lt, fetch, throttle=None, limit: int = 50000) -> list[dict]:
    """All results[] for the window, following next_url. fetch(url)->dict."""
    throttle = throttle or Throttle()
    url, rows = build_url(ticker, resolution, gte, lt, limit), []
    while url:
        throttle()
        page = fetch(url)
        rows.extend(page.get("results") or [])
        url = page.get("next_url")
    return rows


def pick_front_by_volume(session_bars_by_contract: dict[str, list[dict]]) -> dict[str, str]:
    """{session_end_date: contract}: max 1session volume per date, never switching
    back to an earlier expiry than the one already chosen."""
    vol: dict[str, dict[str, float]] = {}
    for c, bars in session_bars_by_contract.items():
        for b in bars:
            vol.setdefault(b["session_end_date"], {})[c] = b.get("volume", 0) or 0
    if not vol:
        return {}
    ref = int(min(vol)[:4])
    key = {c: expiry_key(c, ref) for c in session_bars_by_contract}
    front, cur = {}, None
    for day in sorted(vol):
        cands = vol[day]
        best = max(cands, key=lambda c: (cands[c], key[c]))
        if cur is not None and key[best] < key[cur]:
            best = cur if cur in cands else min((c for c in cands if key[c] >= key[cur]), key=key.get, default=best)
        front[day] = best
        cur = best if cur is None or key[best] >= key[cur] else cur
    return front


def session_date(ts_ns: int) -> str:
    """CME session_end_date of a bar: the session opens 18:00 ET the evening before."""
    et = datetime.fromtimestamp(ts_ns / 1e9, ET)
    return (et.date() + timedelta(days=1) if et.hour >= 18 else et.date()).isoformat()


def stitch(minute_bars_by_contract: dict[str, list[dict]], front_map: dict[str, str]) -> list[dict]:
    """One unadjusted 1-min series: each bar kept only if its contract is the front
    contract for its session. Sorted by time, one bar per timestamp, 'contract' column."""
    out: dict[int, dict] = {}
    for c, bars in minute_bars_by_contract.items():
        for b in bars:
            if front_map.get(session_date(b["window_start"])) == c:
                out.setdefault(b["window_start"], {**b, "contract": c})
    return [out[t] for t in sorted(out)]


def write_csv(path, bars: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLS)
        for b in bars:
            w.writerow([b["window_start"], b["open"], b["high"], b["low"], b["close"], b.get("volume", 0)])


def run(root, start, end, out_dir, fetch=http_fetch, throttle=None) -> list[Path]:
    throttle = throttle or Throttle()
    start, end = _d(start), _d(end)
    gte, lt = (start - timedelta(days=1)).isoformat(), (end + timedelta(days=1)).isoformat()
    contracts = quarterly_contracts(root, start, end)
    sess = {c: fetch_aggs(c, "1session", gte, lt, fetch, throttle) for c in contracts}
    front = pick_front_by_volume(sess)
    needed = sorted(set(front.values()))
    mins = {c: fetch_aggs(c, "1min", gte, lt, fetch, throttle) for c in needed}
    bars = stitch(mins, front)
    paths = []
    for c in needed:
        cb = [b for b in bars if b["contract"] == c]
        if cb:
            year = datetime.fromtimestamp(cb[0]["window_start"] / 1e9, ET).year
            p = Path(out_dir) / f"{c}_{year}.csv"
            write_csv(p, cb)
            paths.append(p)
    return paths


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("root")
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if not os.environ.get(KEY_ENV):
        print(f"{KEY_ENV} not set", file=sys.stderr)
        return 2
    for p in run(a.root, a.start, a.end, a.out):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
