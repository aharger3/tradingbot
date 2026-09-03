"""ADVERSARIAL VERIFY of the G71/trend `htf_bias` definition-drift claim.

Recomputes BOTH shipped bias functions from the archive, exactly as their own
callers call them, and cross-tabs them over the two-year book.

  hourly : backtest_week.htf_bias_for fed backtest_2y's own hourly series
           (backtest_2y.py:105-117 -> backtest_12mo.hourly_from_1m over pf.rth)
  daily  : research/t4_engine_recall.htf_bias, reimplemented EXACTLY
           (levels.load_rth_bars keeps every bar >= 09:30, i.e. through 19:59)
           and spot-checked against the real function.

Usage: python research/g71_trendverify_agree.py
"""
from __future__ import annotations
import csv, json, os, random, sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)

import polygon_feed as pf                                  # noqa: E402
from backtest_week import htf_bias_for                     # noqa: E402
from backtest_12mo import hourly_from_1m                   # noqa: E402
import t4_engine_recall as t4                              # noqa: E402

ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(HERE, "bt2y_trades.json")
START = "2024-08-21"


def archive_days(sym):
    d = os.path.join(ARCHIVE, sym)
    return sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv")) if os.path.isdir(d) else []


def last_close_ge_0930(sym, day):
    """levels.load_rth_bars(...)[-1]['c'] without 40x re-parsing."""
    p = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    last = None
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["Datetime"][11:16] >= "09:30":
                last = row["Close"]
    return float(last) if last not in (None, "") else None


def daily_bias_series(sym):
    """t4_engine_recall.htf_bias for every archived day, incrementally."""
    names = archive_days(sym)
    lc = {}
    for d in names:
        try:
            lc[d] = last_close_ge_0930(sym, d)
        except Exception:
            lc[d] = None
    out = {}
    for i, day in enumerate(names):
        closes = [lc[d] for d in names[max(0, i - 40):i] if lc.get(d) is not None]
        if len(closes) < 20:
            out[day] = None
            continue
        sma = sum(closes[-20:]) / 20
        last = closes[-1]
        out[day] = ("bullish" if last > sma * 1.001
                    else "bearish" if last < sma * 0.999 else "neutral")
    return out


def hourly_bias_series(sym, days):
    hourly = []
    for d in days:
        try:
            bars = pf.rth(pf.fetch_day(sym, d))
        except Exception:
            continue
        if len(bars) < 30:
            continue
        hourly += hourly_from_1m(d, bars)
    return {d: htf_bias_for(hourly, d) for d in days}


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    rows = book["trades"]
    syms = sorted({r["sym"] for r in rows})
    print("book: %d signals, %d traded, %d symbols" %
          (len(rows), sum(1 for r in rows if r["traded"]), len(syms)))

    H, D = {}, {}
    for s in syms:
        days = [d for d in archive_days(s) if d >= START]
        H[s] = hourly_bias_series(s, days)
        D[s] = daily_bias_series(s)
        print("  %-6s %d days" % (s, len(days)), flush=True)

    # --- sanity 1: does my hourly recompute match the book's own `bias` column?
    mm = Counter()
    for r in rows:
        mine = H[r["sym"]].get(r["day"])
        mm["match" if (mine or "none") == r["bias"] else "MISMATCH"] += 1
    print("\nSANITY hourly-vs-book['bias'] column: %s" % dict(mm))

    # --- sanity 2: my daily reimpl vs the REAL t4_engine_recall.htf_bias
    random.seed(7)
    pairs = random.sample([(r["sym"], r["day"]) for r in rows], 120)
    bad = 0
    for s, d in pairs:
        if t4.htf_bias(s, d) != D[s].get(d):
            bad += 1
    print("SANITY daily reimpl vs t4.htf_bias on 120 random pairs: %d mismatches" % bad)

    # --- the agreement matrix
    def tab(sel):
        c, drift = Counter(), Counter()
        for r in sel:
            h, d = H[r["sym"]].get(r["day"]), D[r["sym"]].get(r["day"])
            drift["%s|%s" % (h, d)] += 1
            if h is None or d is None:
                c["uncomputable"] += 1
            elif h in ("bullish", "bearish") and d in ("bullish", "bearish"):
                c["same" if h == d else "flip"] += 1
            else:
                c["neutral_side"] += 1
        return c, drift

    for name, sel in (("ALL signals", rows),
                      ("TRADED rows", [r for r in rows if r["traded"]])):
        c, drift = tab(sel)
        n = c["same"] + c["flip"]
        print("\n%s (n=%d)" % (name, len(sel)))
        print("  directional-both: %d  same %d  flip %d  agree %.1f%%"
              % (n, c["same"], c["flip"], c["same"] / n * 100 if n else 0))
        print("  neutral-on-one-side: %d   uncomputable: %d"
              % (c["neutral_side"], c["uncomputable"]))
        strict_n = len(sel) - c["uncomputable"]
        strict_same = c["same"] + sum(v for k, v in drift.items()
                                      if k.split("|")[0] == k.split("|")[1]
                                      and k.startswith("neutral"))
        print("  STRICT (incl. neutral, exact string match): %d/%d = %.1f%%"
              % (strict_same, strict_n, strict_same / strict_n * 100 if strict_n else 0))
        print("  drift: %s" % dict(sorted(drift.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
