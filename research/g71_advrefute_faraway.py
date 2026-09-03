"""ADVERSARIAL re-run of g71_faraway's `or_mmove` recommendation.

Independent of research/g71_faraway.py except for the two shared, previously
ratified primitives it is not allowed to re-implement:
  * research/t5_structural_target.replay  (exit semantics, stop_rule fill)
  * polygon_feed                          (bars)

Everything else -- the shipped runner, the measured move, the pairing, the
error bar, the month/week greens -- is written fresh here.

Outputs research/g71_advrefute_faraway.json.
"""
from __future__ import annotations
import json
import math
import os
import random
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
MMOVE_LOOKBACK = 30
LIMIT = int(os.getenv("ADV_LIMIT", "0")) or None


def swing_low(b, j):
    return 0 < j < len(b) - 1 and b[j]["l"] < b[j - 1]["l"] and b[j]["l"] < b[j + 1]["l"]


def swing_high(b, j):
    return 0 < j < len(b) - 1 and b[j]["h"] > b[j - 1]["h"] and b[j]["h"] > b[j + 1]["h"]


def mmove(bars, i, entry, long, last_confirm_bar):
    """Measured move. `last_confirm_bar` is the newest bar allowed to CONFIRM a
    swing: i  = g71's convention (bar i is complete at entry),
           i-1 = strictly-prior tape (bar i's own print not used to confirm)."""
    lo = max(1, i - MMOVE_LOOKBACK)
    origin = None
    jmax = min(i - 1, last_confirm_bar - 1)
    for j in range(jmax, lo - 1, -1):
        if (swing_low(bars, j) if long else swing_high(bars, j)):
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

    recs = []
    missed = 0
    t0 = time.time()
    for n, (sym, day) in enumerate(sorted(by_day)):
        try:
            full = pf.fetch_day(sym, day)
            rth = pf.rth(full)
        except Exception:
            missed += len(by_day[(sym, day)])
            continue
        if not rth:
            missed += len(by_day[(sym, day)])
            continue
        bars = [{"o": c.open, "h": c.high, "l": c.low, "c": c.close} for c in rth]
        pmh, pml = pf.premarket_hi_lo(full)
        pdh, pdl = p21._pdh_pdl(sym, day)
        for t in by_day[(sym, day)]:
            i = t.get("entry_i")
            if i is None or i >= len(bars) - 1:
                missed += 1
                continue
            entry, stop, side = t["entry"], t["stop"], t["side"]
            risk = abs(entry - stop)
            if risk <= 0:
                missed += 1
                continue
            long = side == "L"
            seg = bars[:i + 1]
            if long:
                scale = max(b["h"] for b in seg)
                named = [x for x in (pdh, pmh) if x is not None and x > scale]
                psych = math.floor(scale) + 1.0
                ship = min(named + [psych])
            else:
                scale = min(b["l"] for b in seg)
                named = [x for x in (pdl, pml) if x is not None and x < scale]
                psych = math.ceil(scale) - 1.0
                ship = max(named + [psych])
            sgn = 1.0 if long else -1.0

            def rr(px, _e=entry, _r=risk, _s=sgn):
                return _s * (px - _e) / _r

            out = {"sym": sym, "day": day, "ym": t["ym"], "side": side,
                   "book_r": t.get("r")}
            out["ship"] = t5.replay(bars, i, entry, stop, side, [scale, ship],
                                    [0.5, 0.5], be_after_rung1=True)[0]
            out["ship_src"] = "psych" if abs(ship - psych) <= 1e-9 else "named"
            for tag, lcb in (("i", i), ("im1", i - 1)):
                mm = mmove(bars, i, entry, long, lcb)
                if mm is not None and rr(mm) < MIN_RUNG_R:
                    mm = None
                tgt = ship if mm is None else (max(ship, mm) if long else min(ship, mm))
                out["mm_" + tag] = mm
                out["moved_" + tag] = abs(tgt - ship) > 1e-9
                out["extraR_" + tag] = rr(tgt) - rr(ship)
                out["or_" + tag] = t5.replay(bars, i, entry, stop, side,
                                             [scale, tgt], [0.5, 0.5],
                                             be_after_rung1=True)[0]
            recs.append(out)
        if n % 300 == 0:
            print("  %d/%d  %.0fs" % (n, len(by_day), time.time() - t0), flush=True)

    print("replayed %d of %d traded rows, %d missed" % (len(recs), len(rows), missed))

    def agg(key):
        v = [r[key] for r in recs]
        return (len(v), 100.0 * sum(1 for x in v if x > 0) / len(v),
                statistics.fmean(v), sum(v))

    def greens(key, mode):
        import datetime as dt
        m = defaultdict(float)
        for r in recs:
            k = r["ym"] if mode == "m" else dt.date.fromisoformat(r["day"]).isocalendar()[:2]
            m[k] += r[key]
        return sum(1 for v in m.values() if v > 0), len(m)

    def paired(a, b, boot=20000):
        d = [x[a] - x[b] for x in recs]
        mu = statistics.fmean(d)
        sd = statistics.stdev(d)
        norm = 1.96 * sd / math.sqrt(len(d))
        rng = random.Random(7)
        nz = len(d)
        bs = []
        for _ in range(boot):
            s = 0.0
            for _ in range(nz):
                s += d[rng.randrange(nz)]
            bs.append(s / nz)
        bs.sort()
        lo, hi = bs[int(0.025 * boot)], bs[int(0.975 * boot)]
        pos = sum(1 for x in d if x > 1e-12)
        neg = sum(1 for x in d if x < -1e-12)
        return {"mu": mu, "sd": sd, "norm95": norm, "boot_lo": lo, "boot_hi": hi,
                "n": len(d), "pos": pos, "neg": neg,
                "t": mu / (sd / math.sqrt(len(d)))}

    res = {"n_rows": len(recs), "missed": missed, "book_meta": raw["meta"]}
    for k in ("ship", "or_i", "or_im1"):
        n, w, mr, tot = agg(k)
        gm, tm = greens(k, "m")
        gw, tw = greens(k, "w")
        res[k] = {"n": n, "win": w, "meanR": mr, "totR": tot,
                  "months": "%d/%d" % (gm, tm), "weeks": "%d/%d" % (gw, tw)}
    res["moved_i"] = sum(1 for r in recs if r["moved_i"])
    res["moved_im1"] = sum(1 for r in recs if r["moved_im1"])
    mv = [r["extraR_i"] for r in recs if r["moved_i"]]
    res["extraR_i_mean"] = statistics.fmean(mv) if mv else 0.0
    res["paired_or_i"] = paired("or_i", "ship")
    res["paired_or_im1"] = paired("or_im1", "ship")

    d = sorted(((r["or_i"] - r["ship"]), r["sym"], r["day"]) for r in recs)
    tot = sum(x[0] for x in d)
    res["gain_totR"] = tot
    for k in (1, 5, 10, 25, 50):
        res["top%d_share" % k] = (sum(x[0] for x in d[-k:]) / tot) if tot else 0.0
    res["worst5"] = d[:5]
    res["best5"] = d[-5:]
    days = sorted({r["day"] for r in recs})
    mid = days[len(days) // 2]
    for tag, sel in (("h1", lambda r: r["day"] < mid),
                     ("h2", lambda r: r["day"] >= mid)):
        sub = [r for r in recs if sel(r)]
        dd = [r["or_i"] - r["ship"] for r in sub]
        res[tag] = {"n": len(dd), "mu": statistics.fmean(dd),
                    "norm95": 1.96 * statistics.stdev(dd) / math.sqrt(len(dd))}
    json.dump(res, open(ROOT / "research/g71_advrefute_faraway.json", "w"),
              indent=1, default=str)
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
