"""Why does first-B+-of-day lose? Time buckets, per-slot win rates, governor picks."""
from collections import defaultdict
from datetime import date, timedelta

from backtest_week import htf_bias_for, simulate_day
from backtest_sweep import load_data


def stats(ts):
    w = sum(1 for t in ts if t.outcome == "win")
    return len(ts), w, sum(t.pnl for t in ts)


def line(lbl, ts):
    n, w, p = stats(ts)
    print(f"  {lbl:14s} {n:3d}tr {w/max(1,n)*100:3.0f}% ${p:+8,.0f}")


days = 29
ws = (date.today() - timedelta(days=days)).isoformat()
we = (date.today() - timedelta(days=1)).isoformat()
data = load_data(days)
allt = []
for sym, d in data.items():
    prev = None
    for dy in sorted(d["days"]):
        c = d["days"][dy]
        if ws <= dy <= we and len(c) >= 30:
            if prev:
                pc = d["days"][prev]
                pdh, pdl = max(x.high for x in pc), min(x.low for x in pc)
            else:
                pdh = pdl = None
            pmh, pml = d.get("premkt", {}).get(dy, (None, None))
            allt += simulate_day(sym, dy, c, pdh, pdl,
                                 htf_bias_for(d["hourly"], dy), pmh, pml)
        prev = dy
tr = [t for t in allt if t.counted and t.outcome in ("win", "loss")
      and t.grade in ("A+", "A", "B")]

print("BY ENTRY TIME (B+ only):")
for lo, hi in (("09:30", "09:40"), ("09:40", "09:50"), ("09:50", "10:00"),
               ("10:00", "10:15"), ("10:15", "10:30"), ("10:30", "11:00")):
    line(f"{lo}-{hi}", [t for t in tr if lo <= t.entry_time < hi])

print("\nBY CHRONOLOGICAL SLOT WITHIN DAY (across all symbols):")
byday = defaultdict(list)
for t in tr:
    byday[t.day].append(t)
slots = defaultdict(list)
for dy, ts in byday.items():
    ts.sort(key=lambda t: t.entry_time)
    for i, t in enumerate(ts):
        slots[min(i, 4)].append(t)
for i in range(5):
    line(f"slot {i}{'+' if i == 4 else ''}", slots[i])

print("\nGOVERNOR PICKS (first B+ of day):")
for dy, ts in sorted(byday.items()):
    t = min(ts, key=lambda t: t.entry_time)
    print(f"  {dy} {t.entry_time} {t.symbol:5s} {t.grade:2s} {t.signal_type:18s} "
          f"{t.direction:4s} {t.outcome:4s} ${t.pnl:+,.0f}")
