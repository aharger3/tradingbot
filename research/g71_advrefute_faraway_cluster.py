"""Cluster-robust error bar for or_mmove.

g71_faraway.py::paired treats all 2,437 traded rows as independent. They are
not: the book holds up to several trades per symbol-day (2,154 symbol-days) and
28 correlated symbols per session (500 sessions). The honest bar resamples
whole SESSIONS. Also dumps per-row diffs for leave-one-symbol-out.

Outputs research/g71_advrefute_faraway_cluster.json.
"""
from __future__ import annotations
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))
import polygon_feed as pf                          # noqa: E402
import research.t5_structural_target as t5         # noqa: E402
import research.p21_target_availability as p21     # noqa: E402

MIN_RUNG_R = 0.25
LOOKBACK = 30


def sl(b, j):
    return 0 < j < len(b) - 1 and b[j]["l"] < b[j - 1]["l"] and b[j]["l"] < b[j + 1]["l"]


def sh(b, j):
    return 0 < j < len(b) - 1 and b[j]["h"] > b[j - 1]["h"] and b[j]["h"] > b[j + 1]["h"]


def mmove(bars, i, entry, long):
    lo = max(1, i - LOOKBACK)
    origin = None
    for j in range(i - 1, lo - 1, -1):
        if (sl(bars, j) if long else sh(bars, j)):
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
    by_day = defaultdict(list)
    for t in rows:
        by_day[(t["sym"], t["day"])].append(t)

    diffs = []          # (day, sym, diff)
    for sym, day in sorted(by_day):
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
            mm = mmove(bars, i, entry, long)
            if mm is not None and sgn * (mm - entry) / risk < MIN_RUNG_R:
                mm = None
            tgt = ship if mm is None else (max(ship, mm) if long else min(ship, mm))
            a = t5.replay(bars, i, entry, stop, side, [scale, ship],
                          [0.5, 0.5], be_after_rung1=True)[0]
            b = t5.replay(bars, i, entry, stop, side, [scale, tgt],
                          [0.5, 0.5], be_after_rung1=True)[0]
            diffs.append((day, sym, b - a))

    d = [x[2] for x in diffs]
    n = len(d)
    mu = statistics.fmean(d)
    sd = statistics.stdev(d)
    out = {"n": n, "mu": mu,
           "iid_bar95": 1.96 * sd / math.sqrt(n),
           "iid_t": mu / (sd / math.sqrt(n))}

    def cluster_boot(keyfn, boot=20000, seed=11):
        groups = defaultdict(list)
        for row in diffs:
            groups[keyfn(row)].append(row[2])
        gk = list(groups)
        sums = {k: (sum(v), len(v)) for k, v in groups.items()}
        rng = random.Random(seed)
        G = len(gk)
        bs = []
        for _ in range(boot):
            s = c = 0.0
            for _ in range(G):
                a, b = sums[gk[rng.randrange(G)]]
                s += a
                c += b
            bs.append(s / c)
        bs.sort()
        return {"clusters": G, "lo": bs[int(0.025 * boot)],
                "hi": bs[int(0.975 * boot)],
                "excludes_zero": bs[int(0.025 * boot)] > 0}

    out["boot_by_session"] = cluster_boot(lambda r: r[0])
    out["boot_by_symbolday"] = cluster_boot(lambda r: (r[0], r[1]))
    out["boot_by_symbol"] = cluster_boot(lambda r: r[1])

    # leave-one-symbol-out
    loo = {}
    syms = sorted({r[1] for r in diffs})
    for s in syms:
        dd = [r[2] for r in diffs if r[1] != s]
        m = statistics.fmean(dd)
        bar = 1.96 * statistics.stdev(dd) / math.sqrt(len(dd))
        loo[s] = {"mu": m, "bar95": bar, "outside": abs(m) > bar}
    out["leave_one_symbol_out"] = loo
    out["loo_still_outside"] = sum(1 for v in loo.values() if v["outside"])
    out["loo_n"] = len(loo)
    # leave-one-YEAR-out
    yr = {}
    for y in ("2024", "2025", "2026"):
        dd = [r[2] for r in diffs if not r[0].startswith(y)]
        m = statistics.fmean(dd)
        bar = 1.96 * statistics.stdev(dd) / math.sqrt(len(dd))
        yr[y] = {"n": len(dd), "mu": m, "bar95": bar, "outside": abs(m) > bar}
    out["leave_one_year_out"] = yr
    json.dump(out, open(ROOT / "research/g71_advrefute_faraway_cluster.json", "w"),
              indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
