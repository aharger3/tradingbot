"""G71/symbols -- redundancy check. Two companions that move together are one
companion. Correlates the 09:30-11:00 return (the only window OMEN trades) across
every archived symbol, then reports each candidate's correlation to SPY and to
the other candidates.

    python research/g71_symbols_corr.py
"""
from __future__ import annotations

import csv
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

ARCHIVE = os.path.join(ROOT, "data_archive")
CANDIDATES = ["SPY", "QQQ", "IWM", "TSLA", "NVDA", "AAPL", "MU", "AMD",
              "PLTR", "META", "GOOGL", "MSFT", "AMZN", "INTC", "COIN", "AVGO"]
MIN_DAYS = 300


def window_returns(sym):
    """day -> (close@11:00 - open@09:30) / open@09:30, the OMEN window only."""
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        return {}
    out = {}
    for f in sorted(x for x in os.listdir(d) if x.endswith(".csv")):
        o = c = None
        with open(os.path.join(d, f), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = row["Datetime"][11:16]
                if not ("09:30" <= t < "11:00"):
                    continue
                try:
                    if o is None:
                        o = float(row["Open"])
                    c = float(row["Close"])
                except (TypeError, ValueError):
                    continue
        if o and c:
            out[f[:-4]] = (c - o) / o
    return out


def corr(a, b):
    days = sorted(set(a) & set(b))
    if len(days) < MIN_DAYS:
        return None, len(days)
    xs = [a[d] for d in days]
    ys = [b[d] for d in days]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return (num / (dx * dy) if dx and dy else None), len(days)


def main():
    rets = {s: window_returns(s) for s in CANDIDATES}
    rets = {s: v for s, v in rets.items() if len(v) >= MIN_DAYS}
    syms = [s for s in CANDIDATES if s in rets]
    print("09:30-11:00 return correlation, overlapping archived sessions (min %d)"
          % MIN_DAYS)
    print("      " + " ".join("%6s" % s for s in syms))
    for a in syms:
        cells = []
        for b in syms:
            r, n = corr(rets[a], rets[b])
            cells.append("%6.2f" % r if r is not None else "     -")
        print("%-5s " % a + " ".join(cells))
    print()
    print("sd of the 09:30-11:00 return (%):")
    for s in syms:
        print("  %-5s %.2f%%  n=%d" % (s, 100 * statistics.stdev(rets[s].values()),
                                       len(rets[s])))


if __name__ == "__main__":
    main()
