"""Where does or_mmove's +55.6R actually come from?

t5.replay returns (R, exit_bar). Compare the exit bar and the exit KIND of the
shipped runner against or_mmove. If the gain is a hold-to-session-close effect
it belongs to T5's `hold_eod` family, which T5 already rejected on durability.

Outputs research/g71_advrefute_faraway_mech.json.
"""
from __future__ import annotations
import json
import math
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


def swing_low(b, j):
    return 0 < j < len(b) - 1 and b[j]["l"] < b[j - 1]["l"] and b[j]["l"] < b[j + 1]["l"]


def swing_high(b, j):
    return 0 < j < len(b) - 1 and b[j]["h"] > b[j - 1]["h"] and b[j]["h"] > b[j + 1]["h"]


def mmove(bars, i, entry, long):
    lo = max(1, i - LOOKBACK)
    origin = None
    for j in range(i - 1, lo - 1, -1):
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
    by_day = defaultdict(list)
    for t in rows:
        by_day[(t["sym"], t["day"])].append(t)

    recs = []
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
        n = len(bars)
        for t in by_day[(sym, day)]:
            i = t.get("entry_i")
            if i is None or i >= n - 1:
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
            rs, xs = t5.replay(bars, i, entry, stop, side, [scale, ship],
                               [0.5, 0.5], be_after_rung1=True)
            ro, xo = t5.replay(bars, i, entry, stop, side, [scale, tgt],
                               [0.5, 0.5], be_after_rung1=True)
            recs.append({"sym": sym, "day": day, "ym": t["ym"],
                         "rs": rs, "ro": ro, "xs": xs, "xo": xo,
                         "last": n - 1, "moved": abs(tgt - ship) > 1e-9,
                         "ship_at_close": xs == n - 1, "or_at_close": xo == n - 1,
                         "tgtR_ship": sgn * (ship - entry) / risk,
                         "tgtR_or": sgn * (tgt - entry) / risk})

    d = [r["ro"] - r["rs"] for r in recs]
    out = {"n": len(recs)}
    out["ship_exits_at_session_close"] = sum(1 for r in recs if r["ship_at_close"])
    out["or_exits_at_session_close"] = sum(1 for r in recs if r["or_at_close"])
    flipped = [r for r in recs if r["or_at_close"] and not r["ship_at_close"]]
    out["flipped_to_close"] = len(flipped)
    out["gain_from_flipped"] = sum(r["ro"] - r["rs"] for r in flipped)
    out["gain_total"] = sum(d)
    nonflip = [r for r in recs if not (r["or_at_close"] and not r["ship_at_close"])]
    dn = [r["ro"] - r["rs"] for r in nonflip]
    out["gain_from_nonflipped"] = sum(dn)
    out["nonflipped_mu"] = statistics.fmean(dn)
    out["nonflipped_bar95"] = 1.96 * statistics.stdev(dn) / math.sqrt(len(dn))
    out["nonflipped_outside_bar"] = abs(out["nonflipped_mu"]) > out["nonflipped_bar95"]
    # per-symbol decomposition
    bysym = defaultdict(float)
    for r in recs:
        bysym[r["sym"]] += r["ro"] - r["rs"]
    out["by_symbol"] = dict(sorted(bysym.items(), key=lambda kv: -kv[1]))
    # drop the two biggest contributors, re-test
    top2 = list(out["by_symbol"])[:2]
    sub = [r for r in recs if r["sym"] not in top2]
    ds = [r["ro"] - r["rs"] for r in sub]
    out["drop_top2_syms"] = {
        "dropped": top2, "n": len(ds), "mu": statistics.fmean(ds),
        "bar95": 1.96 * statistics.stdev(ds) / math.sqrt(len(ds)),
        "outside": abs(statistics.fmean(ds)) >
                   1.96 * statistics.stdev(ds) / math.sqrt(len(ds))}
    # per-month gain: is it broad or one month?
    bym = defaultdict(float)
    for r in recs:
        bym[r["ym"]] += r["ro"] - r["rs"]
    out["by_month_gain"] = dict(sorted(bym.items()))
    out["months_gain_positive"] = sum(1 for v in bym.values() if v > 0)
    out["months_total"] = len(bym)
    json.dump(out, open(ROOT / "research/g71_advrefute_faraway_mech.json", "w"),
              indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
