"""T3 - run engine entry detection over every covered (symbol, day).

Detection entry point: backtest_week.simulate_day -- the exact function
backtest_12mo.py calls internally (it wraps SignalRunner.detect_signals). We do
NOT reimplement detection; we wire the same inputs backtest_12mo builds per day
(rth, prev-day PDH/PDL/pd_open/pd_close, htf bias from resampled hourly closes,
premarket hi/lo, QQQ key-level breaks) and call simulate_day for every covered
(symbol, day).

PERFORMANCE (attempt-2 fix). Attempt 1 timed out fetching every weekday in a
~2-year window per symbol (~3800 uncached Polygon calls). simulate_day only
consumes the inputs passed in (prev-day levels, bias, qqq, premkt, the day's
RTH bars). bias = htf_bias_for, an SMA20 of the prior hourly closes -- it only
needs the last ~3 trading days of hourly closes before the session. So we fetch
a minimal-correct context set instead of the whole window: for each covered day
D, fetch D plus the 6 trading days before it. That guarantees (a) the real
prior trading day is available as `prev` for prev-day PDH/PDL/pdo/pdc, and
(b) >=20 hourly closes precede D so htf_bias_for matches the full-window value
(the last 20 closes before D come from the same last ~3 trading days either
way). This cuts uncached API calls ~3800 -> ~620 while keeping every simulate_day
input bit-identical to backtest_12mo.py.

Outputs research/corpus_engine_entries.jsonl + .md
"""
import json, os, datetime
from pathlib import Path
from collections import Counter, defaultdict

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
import polygon_feed as pf
from backtest_week import simulate_day, htf_bias_for

OPEN_MIN = 9 * 60 + 30  # 09:30
LOOKBACK = 6            # trading days fetched before each covered day

# ---- covered pairs from T1 (denominator source) ----
pairs = set()
for line in open("research/corpus_instances.jsonl"):
    r = json.loads(line)
    pairs.add((r["symbol"], r["day"]))
covered_by_sym = defaultdict(set)
for s, d in pairs:
    if (Path("data_archive") / s / (d + ".csv")).exists():
        covered_by_sym[s].add(d)
all_syms = sorted(covered_by_sym)
print(f"covered symbol-days: {sum(len(v) for v in covered_by_sym.values())} "
      f"across {len(all_syms)} symbols", flush=True)

# ---- global weekday index (for prior-trading-day lookups) ----
g_min = min(min(v) for v in covered_by_sym.values())
g_max = max(max(v) for v in covered_by_sym.values())
def trading_days(d0_iso, d1_iso):
    out = []
    d = datetime.date.fromisoformat(d0_iso)
    end = datetime.date.fromisoformat(d1_iso)
    while d <= end:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out
all_weekdays = trading_days(
    (datetime.date.fromisoformat(g_min) - datetime.timedelta(days=120)).isoformat(),
    g_max)
wd_index = {d: i for i, d in enumerate(all_weekdays)}

def context_days_for(day_iso):
    """day + the LOOKBACK trading days before it (for prev levels + htf bias)."""
    di = wd_index[day_iso]
    return [all_weekdays[k] for k in range(max(0, di - LOOKBACK), di + 1)]

def hourly_from_1m(day_iso, rth):
    y, m, dd = map(int, day_iso.split("-"))
    by_hour = {}
    for c in rth:
        h = int(c.timestamp[:2])
        by_hour[h] = c.close
    return [(datetime.datetime(y, m, dd, h), close) for h, close in sorted(by_hour.items())]

# ---- QQQ key-level breaks over the needed day set ----
qqq_need = set()
for ds in covered_by_sym.values():
    for d in ds:
        qqq_need.update(context_days_for(d))
qqq_day_bars = {}
for d in sorted(qqq_need):
    try:
        b = pf.fetch_day("QQQ", d)
    except Exception:
        continue
    if not b:
        continue
    rth = pf.rth(b)
    if len(rth) >= 30:
        qqq_day_bars[d] = (b, rth)
qqq_keys = sorted(qqq_day_bars)
qqq_brk = {}
for prev, d in zip(qqq_keys, qqq_keys[1:]):
    _, prth = qqq_day_bars[prev]
    pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
    b, rth = qqq_day_bars[d]
    pmh, pml = pf.premarket_hi_lo(b)
    ups = [l for l in (pdh, pmh) if l is not None]
    dns = [l for l in (pdl, pml) if l is not None]
    qqq_brk[d] = {
        "up": next((c.timestamp for c in rth if any(c.close > l for l in ups)), None),
        "dn": next((c.timestamp for c in rth if any(c.close < l for l in dns)), None),
    }
print(f"QQQ key-level break days: {len(qqq_brk)}", flush=True)

# ---- per-symbol engine run ----
OUT = open("research/corpus_engine_entries.jsonl", "w")
total_entries = 0
grade_dist = Counter()
symdays_with_entry = set()
sym_stats = Counter()

def minute_i_from_ts(ts):
    hh, mm, ss = ts.split(":")
    return int(hh) * 60 + int(mm) - OPEN_MIN

for si, sym in enumerate(all_syms):
    covered = covered_by_sym[sym]
    # fetch the covered days + their LOOKBACK context; walking these sorted
    # keeps prev-day levels and hourly bias correct for every covered day.
    need = set()
    for d in covered:
        need.update(context_days_for(d))
    day_bars = {}
    for d in sorted(need):
        try:
            b = pf.fetch_day(sym, d)
        except Exception:
            continue
        if not b:
            continue
        rth = pf.rth(b)
        if len(rth) < 30:
            continue
        day_bars[d] = (b, rth)
    day_keys = sorted(day_bars)
    hourly = []
    prev = None
    sym_entries = 0
    for d in day_keys:
        b, rth = day_bars[d]
        if prev:
            _, prth = day_bars[prev]
            pdh = max(c.high for c in prth)
            pdl = min(c.low for c in prth)
            pdo = prth[0].open
            pdc = prth[-1].close
        else:
            pdh = pdl = pdo = pdc = None
        pmh, pml = pf.premarket_hi_lo(b)
        bias = htf_bias_for(hourly, d)
        if d in covered:
            trades = simulate_day(sym, d, rth, pdh, pdl, bias, pmh, pml, pdo, pdc,
                                  qqq=qqq_brk.get(d))
            for t in trades:
                if t.status != "fired":
                    continue
                mi = minute_i_from_ts(t.entry_time)
                rec = {
                    "symbol": t.symbol,
                    "day": t.day,
                    "minute_i": mi,
                    "direction": t.direction,
                    "grade": t.grade,
                    "entry": t.entry,
                    "stop": t.stop,
                    "target": t.target,
                    "setup": t.signal_type,
                }
                OUT.write(json.dumps(rec, ensure_ascii=False) + "\n")
                total_entries += 1
                grade_dist[t.grade] += 1
                symdays_with_entry.add((sym, d))
                sym_entries += 1
        hourly += hourly_from_1m(d, rth)
        prev = d
    sym_stats[sym] = sym_entries
    print(f"[{si+1}/{len(all_syms)} {sym}] covered={len(covered)} fetched_days={len(day_keys)} entries={sym_entries}", flush=True)

OUT.close()
print(f"\nTOTAL entries: {total_entries}", flush=True)
print(f"distinct symbol-days with >=1 entry: {len(symdays_with_entry)}", flush=True)
print(f"grade dist: {dict(grade_dist)}", flush=True)

with open("/tmp/t3_engine_stats.json", "w") as fh:
    json.dump({"total_entries": total_entries,
               "symdays_with_entry": len(symdays_with_entry),
               "grade_dist": dict(grade_dist),
               "sym_stats": dict(sym_stats)}, fh)
print("wrote /tmp/t3_engine_stats.json", flush=True)
