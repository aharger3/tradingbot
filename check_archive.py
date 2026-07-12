"""Data completeness check for the Polygon 1m archive.

For each watchlist symbol x the last 251 trading days, report % of days with
cached data_archive/<SYM>/<YYYY-MM-DD>.csv and list the gaps. Gaps silently
shrink backtests (a missing day just isn't simulated) — run this before any
12mo/24mo replay to see what's missing.

A weekday with zero coverage across ALL symbols is almost certainly a market
holiday (Polygon returns no bars, no csv is written) — reported separately so
real per-symbol gaps aren't buried in holiday noise.

Usage: python check_archive.py [DAYS]   (default 251 ~= one trading year)
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from backtest_week import SYMBOLS
from polygon_feed import ARCHIVE

GAPS_OUT = Path(__file__).parent / "research" / "archive_gaps.jsonl"


def last_weekdays(n: int) -> list:
    """Last n Mon-Fri dates as ISO strings (holidays included; filtered below)."""
    out, d = [], date.today()
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d -= timedelta(days=1)
    return out  # newest-first


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 251
    days = last_weekdays(n)
    print(f"Checking {len(SYMBOLS)} symbols x {n} trading days "
          f"({days[-1]} .. {days[0]})\n")

    gaps = []
    no_data_days = []  # weekdays where no symbol has cache (holiday or all-gap)
    for d in days:
        if not any((ARCHIVE / s / f"{d}.csv").exists() for s in SYMBOLS):
            no_data_days.append(d)
    no_data = set(no_data_days)
    real_trading_days = [d for d in days if d not in no_data]
    n_real = len(real_trading_days)

    print(f"{'Symbol':<7} {'cached':>7} {'gaps':>5} {'coverage':>9}")
    print("-" * 32)
    for s in SYMBOLS:
        cached = 0
        missing = []
        for d in real_trading_days:
            if (ARCHIVE / s / f"{d}.csv").exists():
                cached += 1
            else:
                missing.append(d)
        cov = cached / n_real * 100 if n_real else 0
        print(f"{s:<7} {cached:>7} {len(missing):>5} {cov:>8.1f}%")
        for d in missing:
            gaps.append({"symbol": s, "date": d})

    print(f"\nNo-data weekdays (holiday or all-symbol gap): {len(no_data_days)}")
    for d in no_data_days[:20]:
        print(f"  {d}")
    if len(no_data_days) > 20:
        print(f"  ... +{len(no_data_days) - 20} more")

    print(f"\nTotal real per-symbol gaps: {len(gaps)} "
          f"across {n_real} real trading days")

    GAPS_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(GAPS_OUT, "w", encoding="utf-8") as f:
        for g in gaps:
            f.write(json.dumps(g) + "\n")
    print(f"Gaps list -> {GAPS_OUT}")


if __name__ == "__main__":
    main()
