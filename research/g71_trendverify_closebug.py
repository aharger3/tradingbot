"""Does t4_engine_recall.htf_bias read the 16:00 RTH close, as its docstring and
research/g71_trend.md:#4 both say?

levels.load_rth_bars filters `>= 09:30` with NO upper bound, and the archive CSVs
run 04:00 -> 19:59, so bars[-1]['c'] is the POST-MARKET close. This quantifies it.
"""
from __future__ import annotations
import csv, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import levels                                                    # noqa: E402
ARCHIVE = os.path.join(ROOT, "data_archive")

SYMS = ["NVDA", "TSLA", "AAPL", "SPY", "QQQ", "PLTR", "MSFT", "COIN"]


def bias(closes):
    if len(closes) < 20:
        return None
    sma = sum(closes[-20:]) / 20
    last = closes[-1]
    return "bullish" if last > sma * 1.001 else "bearish" if last < sma * 0.999 else "neutral"


tot = Counter()
for sym in SYMS:
    d = os.path.join(ARCHIVE, sym)
    days = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))
    lc_any, lc_rth = {}, {}
    for day in days:
        a = r = None
        with open(os.path.join(d, "%s.csv" % day), encoding="utf-8") as f:
            for row in csv.DictReader(f):
                hhmm = row["Datetime"][11:16]
                if hhmm >= "09:30":
                    a = row["Close"]
                if "09:30" <= hhmm < "16:00":
                    r = row["Close"]
        lc_any[day], lc_rth[day] = (float(a) if a else None), (float(r) if r else None)
    n_post = sum(1 for k in days if lc_any[k] is not None and lc_rth[k] is not None
                 and abs(lc_any[k] - lc_rth[k]) > 1e-9)
    flips = 0
    for i, day in enumerate(days):
        w = days[max(0, i - 40):i]
        ba = bias([lc_any[x] for x in w if lc_any.get(x) is not None])
        br = bias([lc_rth[x] for x in w if lc_rth.get(x) is not None])
        if ba != br:
            flips += 1
        tot["same" if ba == br else "flip"] += 1
    # prove it against the real function on one day
    real = levels.load_rth_bars(sym, days[-1])
    print("  %-5s %4d days | post-mkt close differs from 16:00 close on %d (%.0f%%) "
          "| bias flips %d | load_rth_bars last bar t=%s"
          % (sym, len(days), n_post, n_post / len(days) * 100, flips, real[-1]["t"]))
print("TOTAL over %d symbols: %s  -> %.1f%% of days the 19:59-anchored daily bias "
      "differs from the 16:00-anchored one"
      % (len(SYMS), dict(tot), tot["flip"] / (tot["same"] + tot["flip"]) * 100))
