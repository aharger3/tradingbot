"""G7.1 / drawdown — concurrent open risk, the part the R curve cannot show.

The cumulative-R curve advances one trade at a time, in exit order. A real
account does not. The book fires up to 22 entries in a single 09:30-11:00
window across 28 symbols, and an intraday-trailing prop account ratchets its
floor on the *unrealized* high-water mark, so what matters there is how much
risk is open AT ONCE, not the tidy sum after everything closed.

This reconstructs the minute-by-minute open book from (day, et, bars):
  * max simultaneously open positions, and the day it happened,
  * worst-case simultaneous open risk in R (every open position at its stop),
  * the worst intraday realized excursion per day, floor -1.25R per trade
    (stop_rule.stop_fill_price is the one fill definition; nothing is
    re-implemented here — the book's own `r` column is used as given).

Read-only. No engine file touched.

Usage: python research/g71_drawdown_concurrency.py
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0


def usd(x):
    return ("-$" if x < 0 else "$") + format(abs(x), ",.0f")


def mins(et):
    h, m = et.split(":")
    return int(h) * 60 + int(m)


def main():
    d = json.loads((ROOT / "research/bt2y_trades.json").read_text(encoding="utf-8"))
    tr = [t for t in d["trades"] if t.get("traded")]
    tr.sort(key=lambda t: (t["day"], t["et"]))

    byday = defaultdict(list)
    for t in tr:
        byday[t["day"]].append(t)

    best_conc, best_day, best_min = 0, None, None
    conc_hist = Counter()
    worst_open_r, worst_open_day = 0.0, None
    day_worst_excursion = {}

    for day, rows in byday.items():
        # minute -> which trades are open
        span = defaultdict(list)
        for t in rows:
            a = mins(t["et"])
            b = a + max(1, int(t.get("bars") or 1))
            for m in range(a, b):
                span[m].append(t)
        peak = 0
        for m, open_ts in span.items():
            n = len(open_ts)
            conc_hist[n] += 1
            if n > peak:
                peak = n
            if n > best_conc:
                best_conc, best_day, best_min = n, day, m
            # worst case: every open position is sitting at its -1.25R floor
            risk = 1.25 * n
            if risk > worst_open_r:
                worst_open_r, worst_open_day = risk, day
        # realized intraday excursion: walk the day's closes in exit order
        seq = sorted(rows, key=lambda t: mins(t["et"]) + max(1, int(t.get("bars") or 1)))
        run = lo = 0.0
        for t in seq:
            run += t["r"]
            lo = min(lo, run)
        day_worst_excursion[day] = lo

    print("=" * 74)
    print("CONCURRENT OPEN RISK  (book research/bt2y_trades.json, %d traded)" % len(tr))
    print()
    print("  max simultaneously OPEN positions : %d  (%s around %02d:%02d ET)"
          % (best_conc, best_day, best_min // 60, best_min % 60))
    print("  worst-case open risk at that moment: %.2fR = %s"
          % (1.25 * best_conc, usd(1.25 * best_conc * RISK)))
    print("  (every open position at the -1.25R stop floor, all at once)")
    print()
    print("  distribution of concurrency over all open minutes:")
    tot = sum(conc_hist.values())
    for n in sorted(conc_hist)[:12]:
        print("    %2d open : %6d min (%5.1f%%)"
              % (n, conc_hist[n], 100 * conc_hist[n] / tot))
    hi = [n for n in conc_hist if n >= 6]
    if hi:
        print("    >=6 open: %d min (%.1f%%) across %d minutes total"
              % (sum(conc_hist[n] for n in hi),
                 100 * sum(conc_hist[n] for n in hi) / tot, tot))

    ex = sorted(day_worst_excursion.items(), key=lambda kv: kv[1])
    print()
    print("  worst INTRADAY realized excursions (cumulative R inside one day):")
    for day, v in ex[:10]:
        print("    %s  %+7.2fR  %-9s  (%d trades that day)"
              % (day, v, usd(v * RISK), len(byday[day])))
    print()
    n_bad = sum(1 for _, v in ex if v <= -4.0)
    print("  %d of %d sessions (%.1f%%) dipped to -4.00R or worse INTRADAY,"
          % (n_bad, len(ex), 100 * n_bad / len(ex)))
    print("  which is the whole Apex $150K EOD floor at $1,000/R in one session.")
    for thr in (3, 4, 4.5, 6, 7.5, 9):
        c = sum(1 for _, v in ex if v <= -thr)
        print("    dipped to -%.2fR or worse intraday: %3d sessions (%.1f%%)"
              % (thr, c, 100 * c / len(ex)))


if __name__ == "__main__":
    main()
