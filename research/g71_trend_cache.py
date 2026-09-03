"""G71/trend — archive-derived trend context, cached.

Builds, per (symbol, day), the causal inputs every trend definition in
research/g71_trend.py needs:

  rth_open, rth_close          today's 09:30 open and 16:00 close
  or15_open, or15_close        09:30 open and the 09:44 close (opening range)
  ema5m                        [(bar_end_HH:MM, ema20_of_5m_closes)], EMA
                               carried ACROSS sessions so it is defined from
                               the first bar of the day instead of needing 100
                               minutes of warm-up inside the session
  pd_dir_close/open            the PRIOR archived session's close and open
  dsma20                       mean of the 20 daily closes ENDING on the prior
                               session (so nothing here can see today)

Cache: research/_g71_trend_cache.json.  Rebuild with --rebuild.
"""
from __future__ import annotations
import csv, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ARCHIVE = os.path.join(ROOT, "data_archive")
CACHE = os.path.join(HERE, "_g71_trend_cache.json")


def _day_rows(path):
    """(hhmm, open, high, low, close) for the RTH session only."""
    out = []
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            hhmm = row["Datetime"][11:16]
            if not ("09:30" <= hhmm < "16:00"):
                continue
            try:
                out.append((hhmm, float(row["Open"]), float(row["High"]),
                            float(row["Low"]), float(row["Close"])))
            except (TypeError, ValueError):
                continue
    return out


def build(symbols=None):
    syms = sorted(symbols or os.listdir(ARCHIVE))
    out = {}
    for sym in syms:
        d = os.path.join(ARCHIVE, sym)
        if not os.path.isdir(d):
            continue
        days = sorted(f[:-4] for f in os.listdir(d) if f.endswith(".csv"))
        ema = None
        closes = []           # daily closes, in order
        prev = None           # (day, open, close)
        per = {}
        for day in days:
            bars = _day_rows(os.path.join(d, "%s.csv" % day))
            if len(bars) < 30:
                continue
            rec = {"o": bars[0][1], "c": bars[-1][4],
                   "hi": max(b[2] for b in bars), "lo": min(b[3] for b in bars)}
            or15 = [b for b in bars if "09:30" <= b[0] <= "09:44"]
            if len(or15) >= 10:
                rec["or_o"], rec["or_c"] = or15[0][1], or15[-1][4]
            # 5-minute closes, RTH, and a 20-period EMA carried across sessions
            fives, series = [], []
            for b in bars:
                mins = int(b[0][:2]) * 60 + int(b[0][3:])
                series.append((mins, b[4]))
            bucket, last_close, bstart = None, None, None
            for mins, c in series:
                b0 = mins - (mins % 5)
                if bucket is None:
                    bucket, bstart = b0, b0
                if b0 != bucket:
                    fives.append((bucket + 5, last_close))
                    bucket = b0
                last_close = c
            if bucket is not None and last_close is not None:
                fives.append((bucket + 5, last_close))
            k = 2.0 / 21.0
            emas = []
            for end_min, c in fives:
                ema = c if ema is None else (c - ema) * k + ema
                emas.append(["%02d:%02d" % (end_min // 60, end_min % 60), round(ema, 4)])
            rec["ema5m"] = [e for e in emas if e[0] <= "11:30"]
            if prev is not None:
                rec["pd_o"], rec["pd_c"] = prev[1], prev[2]
            if len(closes) >= 20:
                rec["dsma20"] = sum(closes[-20:]) / 20.0
            per[day] = rec
            closes.append(rec["c"])
            prev = (day, rec["o"], rec["c"])
        out[sym] = per
        print("  %-6s %4d days" % (sym, len(per)), flush=True)
    return out


def load(rebuild=False, symbols=None):
    if not rebuild and os.path.exists(CACHE):
        return json.load(open(CACHE, encoding="utf-8"))
    data = build(symbols)
    json.dump(data, open(CACHE, "w", encoding="utf-8"))
    return data


if __name__ == "__main__":
    load(rebuild="--rebuild" in sys.argv)
