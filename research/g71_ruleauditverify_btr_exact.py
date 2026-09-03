"""Exact re-run: does break_then_rejection fire with the UNROUNDED t.stop?

research/g71_btrverify_book.py had to use the book's 2dp-rounded stop. This
re-runs backtest_week.simulate_day on a slice of symbol-days and calls
dg.score exactly the way backtest_2y.py:151 does, with the live t.stop.
Usage: python research/g71_btrverify_exact.py SYM [SYM...]
"""
import sys, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research import downgrade as dg
from backtest_2y import dg_bars, archive_days
from backtest_week import simulate_day, htf_bias_for
from backtest_12mo import hourly_from_1m

SYMS = sys.argv[1:] or ["AAPL"]
stat = collections.Counter()
hits = []
for sym in SYMS:
    days = archive_days(sym)
    day_bars = {}
    for d in days:
        try:
            b = pf.fetch_day(sym, d)
        except Exception:
            continue
        r = pf.rth(b)
        if len(r) >= 30:
            day_bars[d] = (b, r)
    hourly = []
    for d in sorted(day_bars):
        hourly += hourly_from_1m(d, day_bars[d][1])
    prev = None
    for d in sorted(day_bars):
        bars, rth = day_bars[d]
        if prev:
            prth = day_bars[prev][1]
            pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
            pdo, pdc = prth[0].open, prth[-1].close
        else:
            pdh = pdl = pdo = pdc = None
        pmh, pml = pf.premarket_hi_lo(bars)
        bias = htf_bias_for(hourly, d)
        try:
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc)
        except Exception as e:
            stat["simfail"] += 1
            prev = d
            continue
        db = dg_bars(rth) if trades else None
        for t in trades:
            rec = dg.score(db, t.entry_idx, t.stop, t.direction == "call", bias)
            if not rec:
                stat["norec"] += 1
                continue
            stat["n"] += 1
            if "break_then_rejection" in rec["tripped"]:
                stat["btr"] += 1
                hits.append((sym, d, t.entry_time, t.direction, t.stop, t.entry, rec["grade"], t.status))
        prev = d
print("syms=%s  signals scored=%d  simfail=%d" % (",".join(SYMS), stat["n"], stat["simfail"]))
print("break_then_rejection trips (exact unrounded stop): %d" % stat["btr"])
for h in hits[:15]:
    print("  ", h)
