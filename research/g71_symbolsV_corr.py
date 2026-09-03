"""ADVERSARIAL VERIFY of the g71/symbols correlation claim.

Independent re-implementation. Differences from research/g71_symbols_corr.py,
all deliberate:
  * scans EVERY archived symbol, not a hand-picked 16 -- the claim says
    "most SPY-redundant single name IN THE UNIVERSE".
  * uses numpy-free Pearson on the same 09:30-11:00 window return.
  * reports the SPY-correlation ranking so "most/least" is checkable.
  * also reports a beta and an r^2 so "levered SPY" is testable, and a
    bootstrap CI on the SPY correlation so "highest" can be separated from
    "highest by noise".

    python research/g71_symbolsV_corr.py
"""
from __future__ import annotations
import csv, os, statistics, sys, json, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from universe import ALL_SYMS  # noqa

ARCHIVE = os.path.join(ROOT, "data_archive")
MIN_DAYS = 300


def window_returns(sym, end="11:00"):
    d = os.path.join(ARCHIVE, sym)
    if not os.path.isdir(d):
        return {}
    out = {}
    for f in sorted(x for x in os.listdir(d) if x.endswith(".csv")):
        o = c = None
        with open(os.path.join(d, f), newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                t = row["Datetime"][11:16]
                if not ("09:30" <= t < end):
                    continue
                try:
                    v_o, v_c = float(row["Open"]), float(row["Close"])
                except (TypeError, ValueError):
                    continue
                if o is None:
                    o = v_o
                c = v_c
        if o and c:
            out[f[:-4]] = (c - o) / o
    return out


def pearson(xs, ys):
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    return num / (dx * dy) if dx and dy else None


def pair(a, b):
    days = sorted(set(a) & set(b))
    if len(days) < MIN_DAYS:
        return None, len(days)
    return pearson([a[d] for d in days], [b[d] for d in days]), len(days)


def boot_ci(a, b, n=2000, seed=7):
    days = sorted(set(a) & set(b))
    xs = [a[d] for d in days]; ys = [b[d] for d in days]
    rng = random.Random(seed); N = len(days); rs = []
    for _ in range(n):
        idx = [rng.randrange(N) for _ in range(N)]
        r = pearson([xs[i] for i in idx], [ys[i] for i in idx])
        if r is not None:
            rs.append(r)
    rs.sort()
    return rs[int(.025 * len(rs))], rs[int(.975 * len(rs))]


def main():
    syms = sorted(set(ALL_SYMS) | set(os.listdir(ARCHIVE)))
    rets = {}
    for s in syms:
        r = window_returns(s)
        if len(r) >= MIN_DAYS:
            rets[s] = r
    print("archived symbols with >=%d window days: %d" % (MIN_DAYS, len(rets)))
    print("in universe.ALL_SYMS but excluded from g71_symbols_corr CANDIDATES:")
    CAND = ["SPY","QQQ","IWM","TSLA","NVDA","AAPL","MU","AMD","PLTR","META",
            "GOOGL","MSFT","AMZN","INTC","COIN","AVGO"]
    print("  ", sorted(set(rets) - set(CAND)))
    print()
    spy = rets["SPY"]
    rows = []
    for s in sorted(rets):
        if s == "SPY":
            continue
        r, n = pair(spy, rets[s])
        if r is None:
            continue
        rq, _ = pair(rets.get("QQQ", {}), rets[s])
        days = sorted(set(spy) & set(rets[s]))
        xs = [spy[d] for d in days]; ys = [rets[s][d] for d in days]
        vx = statistics.pvariance(xs)
        beta = (sum((x - statistics.fmean(xs)) * (y - statistics.fmean(ys))
                    for x, y in zip(xs, ys)) / len(days)) / vx if vx else None
        lo, hi = boot_ci(spy, rets[s])
        rows.append((s, r, rq, n, beta, r * r, lo, hi,
                     100 * statistics.stdev(rets[s].values()), len(rets[s])))
    rows.sort(key=lambda t: -t[1])
    print("%-6s %6s %8s %6s %6s %6s %16s %7s %5s" %
          ("sym", "rSPY", "rQQQ", "n", "beta", "r2", "rSPY 95% CI", "sd%", "days"))
    for s, r, rq, n, b, r2, lo, hi, sd, nd in rows:
        print("%-6s %6.3f %8s %6d %6.2f %6.3f  [%+.3f,%+.3f] %7.2f %5d" %
              (s, r, ("%.3f" % rq) if rq is not None else "-", n, b or 0, r2,
               lo, hi, sd, nd))

    # the specific pairs the claim cites
    print("\ncited pairs:")
    for a, b in [("SPY","NVDA"),("QQQ","NVDA"),("SPY","TSLA"),("SPY","AAPL"),
                 ("TSLA","AAPL"),("TSLA","NVDA"),("SPY","QQQ"),("SPY","IWM")]:
        r, n = pair(rets[a], rets[b])
        print("  %-5s-%-5s r=%.3f n=%d" % (a, b, r, n))

    # sensitivity: does the ranking hold on a 09:30-10:30 window?
    print("\nsensitivity, 09:30-10:30 window, top-6 rSPY:")
    r30 = {s: window_returns(s, "10:30") for s in list(rets)}
    alt = []
    for s in r30:
        if s == "SPY":
            continue
        r, n = pair(r30["SPY"], r30[s])
        if r is not None:
            alt.append((s, r, n))
    alt.sort(key=lambda t: -t[1])
    for s, r, n in alt[:6]:
        print("  %-6s %.3f n=%d" % (s, r, n))
    json.dump({"rows": [list(x) for x in rows]},
              open(os.path.join(HERE, "g71_symbolsV_corr.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
