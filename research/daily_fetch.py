"""Fill data_archive/<SYM>/<day>.csv for recent sessions, from yfinance.

WHY THIS EXISTS. The archive is Polygon-fed (`polygon_feed.fetch_day`), and this
box's Polygon plan returns **403 NOT_AUTHORIZED** for recent timeframes -- the
archive therefore stops at 2026-08-27 and can never reach today. Tastytrade,
which the live scanner prefers, is returning **HTTP 401 invalid_credentials**
(see journal/scanner-2026-09-01.log: every one of the 29 symbols fell through to
yfinance today, with `HTF unknown` on all of them). yfinance is the only source
on this box that currently reaches the current session, and it keeps ~30 days of
1-minute history.

So: same bars, same archive layout, same column header as `polygon_feed`, written
into the same files. Everything downstream -- `polygon_feed.fetch_day` (cache
-first), `g80_ordertype_grid.day_pack`, `backtest_week.simulate_day` -- then works
on today with no code change at all.

    python research/daily_fetch.py                # last 5 sessions, full universe
    python research/daily_fetch.py --day 2026-09-01
    python research/daily_fetch.py --day 2026-09-01 --force

Premarket matters and is NOT optional: `day_pack` derives PMH/PML from the
pre-09:30 bars of the day's own file, so `prepost=True` and the 04:00 start are
load-bearing. A file written without premarket silently produces `pmh=pml=None`
and every PMH/PML setup vanishes from the day.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import universe                                    # noqa: E402
from polygon_feed import ARCHIVE                   # noqa: E402

HEADER = ["Datetime", "Open", "High", "Low", "Close", "Adj Close", "Volume"]


def _frame(symbol: str, period: str):
    """yfinance 1-minute frame including premarket, columns flattened."""
    import yfinance as yf
    df = yf.download(symbol, period=period, interval="1m", prepost=True,
                     progress=False, auto_adjust=False, threads=False)
    if df is None or df.empty:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        # yfinance returns a (field, ticker) MultiIndex for a single ticker too.
        df.columns = df.columns.get_level_values(0)
    return df.tz_convert("America/New_York")


def write_day(symbol: str, day_iso: str, df, force: bool = False) -> int:
    """Write one symbol-day to the archive in polygon_feed's exact format.

    Returns rows written; 0 means "nothing to do" (already present, or the day
    is not in this frame). Never overwrites a Polygon-written file unless
    --force: Polygon is the higher-fidelity source and stays authoritative
    wherever it reached.
    """
    out = ARCHIVE / symbol / f"{day_iso}.csv"
    if out.exists() and not force:
        return 0
    day = df[df.index.strftime("%Y-%m-%d") == day_iso]
    if day.empty:
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for ts, r in day.iterrows():
            o, h, lo, c, v = (r["Open"], r["High"], r["Low"], r["Close"],
                              r.get("Volume", 0))
            if any(x != x for x in (o, h, lo, c)):   # NaN gap bar
                continue
            w.writerow([ts.isoformat(), round(float(o), 4), round(float(h), 4),
                        round(float(lo), 4), round(float(c), 4),
                        round(float(c), 4), float(v or 0)])
            n += 1
    if n == 0:
        out.unlink(missing_ok=True)   # never leave a header-only file behind
    return n


def fill(symbols, period="5d", day=None, force=False) -> dict:
    got = {}
    for i, sym in enumerate(symbols, 1):
        try:
            df = _frame(sym, period)
        except Exception as e:
            print(f"  [{sym}] fetch failed: {type(e).__name__}: {e}")
            continue
        if df is None:
            print(f"  [{sym}] empty frame")
            continue
        days = [day] if day else sorted({d for d in df.index.strftime("%Y-%m-%d")})
        for d in days:
            n = write_day(sym, d, df, force=force)
            if n:
                got.setdefault(d, []).append(sym)
                print(f"  [{sym}] {d}: {n} bars")
        if i % 10 == 0:
            print(f"  ... {i}/{len(symbols)}")
    return got


def demo():
    """Self-check: the written file must round-trip through the real reader.

    The failure this guards is silent and expensive -- a file that parses but
    carries no premarket makes PMH/PML None and drops every premarket-level
    setup out of the day without erroring anywhere.
    """
    import polygon_feed as pf
    sym, day = "TSLA", None
    for d in sorted((ARCHIVE / sym).glob("*.csv"), reverse=True):
        day = d.stem
        break
    assert day, "no TSLA archive to check"
    raw = pf.fetch_day(sym, day)
    assert raw, f"reader returned nothing for {sym} {day}"
    rth = pf.rth(raw)
    assert len(rth) >= 300, f"{day}: only {len(rth)} RTH bars"
    pre = [c for c in raw if c.timestamp < "09:30:00"]
    assert pre, f"{day}: no premarket bars -- PMH/PML would be None"
    pmh, pml = pf.premarket_hi_lo(raw)
    assert pmh and pml and pmh >= pml, f"{day}: bad premarket hi/lo {pmh}/{pml}"
    for c in rth[:50]:
        assert c.low <= c.open <= c.high and c.low <= c.close <= c.high, \
            f"{day} {c.timestamp}: OHLC inconsistent"
    print(f"demo OK -- {sym} {day}: {len(raw)} bars, {len(rth)} RTH, "
          f"{len(pre)} premarket, PMH {pmh} / PML {pml}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", help="only this session (YYYY-MM-DD)")
    ap.add_argument("--period", default="5d", help="yfinance lookback (max 8d for 1m)")
    ap.add_argument("--sym", help="one symbol instead of the universe")
    ap.add_argument("--force", action="store_true", help="overwrite existing files")
    ap.add_argument("--demo", action="store_true", help="run the self-check only")
    a = ap.parse_args()

    if a.demo:
        demo()
        return

    syms = [a.sym] if a.sym else universe.ALL_SYMS
    print(f"filling archive from yfinance: {len(syms)} symbols, period={a.period}")
    got = fill(syms, period=a.period, day=a.day, force=a.force)
    if not got:
        print("nothing written (already archived, or no data)")
    for d in sorted(got):
        print(f"{d}: {len(got[d])} symbols")
    demo()


if __name__ == "__main__":
    main()
