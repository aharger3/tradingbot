"""g75_trendfilter_cache.py -- one pass over data_archive, so the threshold
sweep does not re-read 15,000 CSVs per arm.

For every symbol-day in the two-year book's universe (plus 25 sessions of
run-up, which the daily-chart scores need) this stores:

  win_closes  09:30-11:00 closes, so ER up to any entry minute is a slice
  er_session  ER of those closes                       -- HINDSIGHT
  pm_er_*     ER of the premarket                      -- known 09:29
  rth_close   the 16:00 close, for the daily-chart ER  -- known 09:29 (prior days)
  rth_hi/lo   prior-day range, for the gap score       -- known 09:29
  open0930    first RTH open, for the gap score

Writes research/g75_trendfilter_cache.json (~30MB, regenerable, gitignored).
Read-only on data_archive.
"""
from __future__ import annotations
import json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import g75_trendfilter_lib as L  # noqa: E402

BOOK = os.path.join(HERE, "bt2y_trades.json")
OUT = os.path.join(HERE, "g75_trendfilter_cache.json")
CORPUS = os.path.join(HERE, "g71_samplesize_corpus.json")


def main():
    meta = json.load(open(BOOK, encoding="utf-8"))["meta"]
    syms = set(meta["symbols"])
    # Austin's graded corpus reaches symbols the book's universe does not.
    corpus = json.load(open(CORPUS, encoding="utf-8"))["rows"]
    syms |= {r["symbol"] for r in corpus if r["bars"]}
    cache, t0 = {}, time.time()
    for si, sym in enumerate(sorted(syms)):
        days = L.sessions(sym)
        d = {}
        for day in days:
            b = L.bars(sym, day)
            if not b:
                continue
            win = [x for x in b if "09:30" <= x[0] < "11:00"]
            rth = [x for x in b if "09:30" <= x[0] < "16:00"]
            pm = [x for x in b if "04:00" <= x[0] < "09:30"]
            if not win or not rth:
                continue
            d[day] = {
                "wt": [x[0] for x in win],
                "wc": [round(x[4], 4) for x in win],
                "er": L.er([x[4] for x in win]),
                "pm_full": L.er([x[4] for x in pm]),
                "pm_0800": L.er([x[4] for x in pm if x[0] >= "08:00"]),
                "pm_0900": L.er([x[4] for x in pm if x[0] >= "09:00"]),
                "late": L.er([x[4] for x in rth if x[0] >= "15:00"]),
                "rc": round(rth[-1][4], 4),
                "hi": round(max(x[2] for x in rth), 4),
                "lo": round(min(x[3] for x in rth), 4),
                "o": round(rth[0][1], 4),
            }
            L.bars.cache_clear()
        cache[sym] = d
        print("  %2d/%d %-6s %4d sessions  (%.0fs)"
              % (si + 1, len(syms), sym, len(d), time.time() - t0), flush=True)
    json.dump(cache, open(OUT, "w", encoding="utf-8"))
    print("wrote %s  (%.1f MB)" % (OUT, os.path.getsize(OUT) / 1e6))


if __name__ == "__main__":
    main()
