"""G7.1 adversarial verify (router claim), measurement rig.

Replicates backtest_week.simulate_day's DETECTION+DEDUPE loop exactly
(backtest_week.py:751 `seen = {}`, :818-833) with no trade simulation, and
scores two arms side by side on the same captured stream:

  A  as-shipped : `seen[key] = i` written for EVERY captured signal
  B  claimed fix: `seen[key] = i` written only when sig["status"] == "fired"
                  (the research/t4_engine_recall.py:212-216 shape)

Reports the entries each arm would take and every fired signal arm A loses to a
non-fired predecessor.  Publishes: python research/g71_router_dedupe_count.py
"""
import sys, json, argparse
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import polygon_feed as pf
import backtest_week as bw
from backtest_week import BacktestRunner, htf_bias_for, ENTRY_CUTOFF, dedupe_window
from backtest_2y import archive_days
from backtest_12mo import hourly_from_1m, qqq_level_breaks
from universe import ALL_SYMS, has_archive

ap = argparse.ArgumentParser()
ap.add_argument("--syms", type=int, default=0)
ap.add_argument("--days", type=int, default=730)
a = ap.parse_args()

syms = [s for s in ALL_SYMS if has_archive(s, 100)]
if a.syms:
    syms = syms[:a.syms]
last = max((archive_days(s) or ["1970-01-01"])[-1] for s in syms)
start = (date.fromisoformat(last) - timedelta(days=a.days)).isoformat()
window = sorted({d for s in syms for d in archive_days(s) if d >= start})
qqq_brk = qqq_level_breaks(window)

W = dedupe_window()
TOT = Counter()
LOST = []      # fired rows arm A drops that arm B keeps
GAINED = []    # fired rows arm B drops that arm A keeps (should be empty)


def day_loop(symbol, day_iso, candles, pdh, pdl, bias, pmh, pml, pdo, pdc, qqq):
    runner = BacktestRunner(symbol)
    runner.pdh, runner.pdl, runner.htf_bias = pdh, pdl, bias
    runner.pmh, runner.pml = pmh, pml
    runner.pd_open, runner.pd_close = pdo, pdc
    runner.qqq_breaks = qqq
    runner.min_risk_dollars = None
    seenA, seenB, seenC = {}, {}, {}   # C = t4 shape: fired-only map, 30-bar window
    lastA = {}          # key -> status of the row that last wrote seenA
    for i in range(5, len(candles)):
        c = candles[i]
        if ENTRY_CUTOFF and c.timestamp >= ENTRY_CUTOFF:
            continue
        runner.candles = candles[: i + 1]
        before = len(runner.captured)
        runner.detect_signals()
        for sig in runner.captured[before:]:
            idea = (sig.get("stop_level_name")
                    if sig["signal_type"].value == "break_and_retest"
                    else round(sig["stop"], 2))
            key = (sig["signal_type"].value, sig["direction"], idea)
            st = sig["status"]
            TOT["captured"] += 1
            TOT["captured_" + st] += 1

            # ---- arm A: as shipped (backtest_week.py:830-833)
            supA = key in seenA and i - seenA[key] < W
            killer = lastA.get(key)
            seenA[key] = i
            lastA[key] = st
            takeA = not supA

            # ---- arm B: seen written only on a fire (t4 shape)
            supB = key in seenB and i - seenB[key] < W
            takeB = True
            if st == "fired":
                if supB:
                    takeB = False
                seenB[key] = i

            takeC = True
            if st == "fired":
                if key in seenC and i - seenC[key] < bw.DEDUPE_BARS:
                    takeC = False
                seenC[key] = i
            if st == "fired":
                TOT["C_entries" if takeC else "C_suppressed"] += 1
                TOT["A_entries" if takeA else "A_suppressed"] += 1
                TOT["B_entries" if takeB else "B_suppressed"] += 1
                if takeB and not takeA:
                    LOST.append({"sym": symbol, "day": day_iso, "bar": i,
                                 "gap": i - seenA[key] if False else None,
                                 "key": str(key), "grade": sig["grade"],
                                 "killer": killer})
                    TOT["killer_" + str(killer)] += 1
                if takeA and not takeB:
                    GAINED.append({"sym": symbol, "day": day_iso, "bar": i})
            else:
                TOT["A_row" if takeA else "A_row_dropped"] += 1


for sym in syms:
    days = [d for d in archive_days(sym) if d >= start]
    day_bars, hourly = {}, []
    for d in days:
        try:
            bars = pf.fetch_day(sym, d)
        except Exception:
            continue
        if not bars:
            continue
        r = pf.rth(bars)
        if len(r) < 30:
            continue
        day_bars[d] = (bars, r)
        hourly += hourly_from_1m(d, r)
    prev = None
    for d in sorted(day_bars):
        bars, rth = day_bars[d]
        if prev:
            _, prth = day_bars[prev]
            pdh, pdl = max(c.high for c in prth), min(c.low for c in prth)
            pdo, pdc = prth[0].open, prth[-1].close
        else:
            pdh = pdl = pdo = pdc = None
        pmh, pml = pf.premarket_hi_lo(bars)
        day_loop(sym, d, rth, pdh, pdl, htf_bias_for(hourly, d), pmh, pml,
                 pdo, pdc, qqq_brk.get(d))
        prev = d
    print("  %-6s ok" % sym, flush=True)

print(json.dumps({"window": W, "syms": len(syms), "sessions": len(window),
                  "counts": dict(TOT),
                  "fired_lost_by_A": len(LOST),
                  "fired_lost_by_B": len(GAINED),
                  "grade_mix_lost": dict(Counter(x["grade"] for x in LOST)),
                  "sample": LOST[:5]}, indent=1))
