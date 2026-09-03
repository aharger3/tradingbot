"""G71/trend - the live/backtest divergence in `_calibration_grade`'s with_trend.

signal_runner.py:2020
    with_trend = (self.candles[-1].close >= self.candles[0].open) == (d == "call")

`self.candles[0]` is whatever the caller loaded.

  backtest / recall harness  backtest_week.py:_run / t4_engine_recall.run_day:196
      runner.candles = candles[:i+1] from the RTH start -> candles[0].open IS
      the 09:30 open.
  live                       live_scanner.py:378,422
      candles = tasty_feed.fetch_recent_bars(symbol, lookback_minutes=60)
      runner.candles = candles                 -> a ROLLING 60-minute window.

So the predicate that floors 95.3% of the traded book to `B` measures
"price vs the 09:30 open" offline and "price vs the open 60 minutes ago"
live. This script prices the disagreement on the two-year book: for every
traded row it recomputes with_trend against the RTH bar 60 minutes back
(clamped at 09:30, the most GENEROUS reading of the live buffer -- if the feed
returns premarket bars the drift is larger) and counts the flips.

Usage: python research/g71_trend_livegap.py
"""
from __future__ import annotations
import csv, json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
BOOK = os.path.join(HERE, "bt2y_trades.json")


def opens(sym, day):
    """hhmm -> open, RTH only."""
    p = os.path.join(ARCHIVE, sym, "%s.csv" % day)
    if not os.path.exists(p):
        return None
    out = {}
    with open(p, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hhmm = row["Datetime"][11:16]
            if "09:30" <= hhmm < "16:00":
                out[hhmm] = float(row["Open"])
    return out or None


def main():
    book = json.load(open(BOOK, encoding="utf-8"))
    rows = [r for r in book["trades"] if r["traded"]]
    cache, tally, late = {}, Counter(), Counter()
    for r in rows:
        k = (r["sym"], r["day"])
        if k not in cache:
            cache[k] = opens(*k)
        o = cache[k]
        if not o:
            tally["no_bars"] += 1
            continue
        et = r["et"]
        m = int(et[:2]) * 60 + int(et[3:])
        ref_m = max(570, m - 60)                       # 570 = 09:30
        ref = o.get("%02d:%02d" % (ref_m // 60, ref_m % 60))
        day_open = o.get("09:30")
        if ref is None or day_open is None:
            tally["no_bars"] += 1
            continue
        px = r["entry"]
        bt = (px >= day_open) == (r["dir"] == "call")   # what every rig computes
        lv = (px >= ref) == (r["dir"] == "call")        # what live computes
        tally["same" if bt == lv else "flip"] += 1
        if m > 630:                                     # after 10:30
            late["same" if bt == lv else "flip"] += 1
    n = tally["same"] + tally["flip"]
    print("traded rows scored: %d  (%d without bars)" % (n, tally["no_bars"]))
    print("with_trend agrees between the backtest and the live buffer: "
          "%d/%d = %.1f%%" % (tally["same"], n, tally["same"] / n * 100))
    print("  FLIPS: %d (%.1f%% of the traded book)" % (tally["flip"], tally["flip"] / n * 100))
    ln = late["same"] + late["flip"]
    print("after 10:30, where the 60-min window can no longer reach 09:30: "
          "%d rows, %d flips = %.1f%%" % (ln, late["flip"], late["flip"] / ln * 100 if ln else 0))


if __name__ == "__main__":
    main()
