"""Fragility sweep for g71_faraway's `or_mmove`.

MMOVE_LOOKBACK=30 and a strength-1 swing are UNSWEPT free parameters in
research/g71_faraway.py. If the +0.0228R paired move is real it should survive
a neighbourhood of both. Also reports a Bonferroni-corrected bar for the
number of arms the g71_faraway report actually tabled.

Outputs research/g71_advrefute_faraway_sweep.json.
"""
from __future__ import annotations
import json
import math
import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import polygon_feed as pf                          # noqa: E402
import research.t5_structural_target as t5         # noqa: E402
import research.p21_target_availability as p21     # noqa: E402

MIN_RUNG_R = 0.25
LOOKBACKS = (10, 15, 20, 25, 30, 35, 40, 45, 60)
STRENGTHS = (1, 2)
LIMIT = int(os.getenv("ADV_LIMIT", "0")) or None


def is_sw(b, j, s, low):
    if not (s <= j < len(b) - s):
        return False
    k = "l" if low else "h"
    v = b[j][k]
    for d in range(1, s + 1):
        if low:
            if not (v < b[j - d][k] and v < b[j + d][k]):
                return False
        else:
            if not (v > b[j - d][k] and v > b[j + d][k]):
                return False
    return True


def mmove(bars, i, entry, long, lookback, strength):
    lo = max(1, i - lookback)
    origin = None
    # a strength-s swing at j is confirmed by bar j+s; g71 allows confirmation
    # up to bar i, so j <= i - s
    for j in range(i - strength, lo - 1, -1):
        if is_sw(bars, j, strength, long):
            origin = bars[j]["l"] if long else bars[j]["h"]
            break
    if origin is None:
        return None
    if long:
        leg = max(b["h"] for b in bars[lo:i + 1]) - origin
        return entry + leg if leg > 0 else None
    leg = origin - min(b["l"] for b in bars[lo:i + 1])
    return entry - leg if leg > 0 else None


def main():
    raw = json.load(open(ROOT / "research/bt2y_trades.json"))
    rows = [t for t in raw["trades"] if t.get("traded")]
    if LIMIT:
        rows = rows[:LIMIT]
    by_day = defaultdict(list)
    for t in rows:
        by_day[(t["sym"], t["day"])].append(t)

    keys = [(lb, s) for s in STRENGTHS for lb in LOOKBACKS]
    ship_r, arm_r = [], {k: [] for k in keys}
    meta = []
    t0 = time.time()
    for n, (sym, day) in enumerate(sorted(by_day)):
        try:
            full = pf.fetch_day(sym, day)
            rth = pf.rth(full)
        except Exception:
            continue
        if not rth:
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close} for c in rth]
        pmh, pml = pf.premarket_hi_lo(full)
        pdh, pdl = p21._pdh_pdl(sym, day)
        for t in by_day[(sym, day)]:
            i = t.get("entry_i")
            if i is None or i >= len(bars) - 1:
                continue
            entry, stop, side = t["entry"], t["stop"], t["side"]
            risk = abs(entry - stop)
            if risk <= 0:
                continue
            long = side == "L"
            seg = bars[:i + 1]
            if long:
                scale = max(b["h"] for b in seg)
                named = [x for x in (pdh, pmh) if x is not None and x > scale]
                ship = min(named + [math.floor(scale) + 1.0])
            else:
                scale = min(b["l"] for b in seg)
                named = [x for x in (pdl, pml) if x is not None and x < scale]
                ship = max(named + [math.ceil(scale) - 1.0])
            sgn = 1.0 if long else -1.0
            ship_r.append(t5.replay(bars, i, entry, stop, side, [scale, ship],
                                    [0.5, 0.5], be_after_rung1=True)[0])
            meta.append((t["ym"], t["day"]))
            for (lb, s) in keys:
                mm = mmove(bars, i, entry, long, lb, s)
                if mm is not None and sgn * (mm - entry) / risk < MIN_RUNG_R:
                    mm = None
                tgt = ship if mm is None else (max(ship, mm) if long else min(ship, mm))
                arm_r[(lb, s)].append(
                    t5.replay(bars, i, entry, stop, side, [scale, tgt],
                              [0.5, 0.5], be_after_rung1=True)[0])
        if n % 400 == 0:
            print("  %d/%d %.0fs" % (n, len(by_day), time.time() - t0), flush=True)

    out = {"n": len(ship_r), "ship_meanR": statistics.fmean(ship_r), "arms": {}}
    import datetime as dt
    for k in keys:
        a = arm_r[k]
        d = [x - y for x, y in zip(a, ship_r)]
        mu = statistics.fmean(d)
        sd = statistics.stdev(d)
        bar = 1.96 * sd / math.sqrt(len(d))
        mg = defaultdict(float)
        wg = defaultdict(float)
        for (ym, day), r in zip(meta, a):
            mg[ym] += r
            wg[dt.date.fromisoformat(day).isocalendar()[:2]] += r
        out["arms"]["lb%d_s%d" % k] = {
            "meanR": statistics.fmean(a), "mu": mu, "bar95": bar,
            "t": mu / (sd / math.sqrt(len(d))),
            "moved": sum(1 for x, y in zip(a, ship_r) if abs(x - y) > 1e-12),
            "months_green": sum(1 for v in mg.values() if v > 0),
            "months": len(mg),
            "weeks_green": sum(1 for v in wg.values() if v > 0),
            "weeks": len(wg),
            "outside_bar": abs(mu) > bar,
        }
    json.dump(out, open(ROOT / "research/g71_advrefute_faraway_sweep.json", "w"),
              indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
