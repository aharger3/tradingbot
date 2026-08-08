"""T4 diagnostic 3: for the 27 marks, find which are recovered by GEOMETRY knobs
(window, gap, leave, eps) vs only by RETEST-TOLERANCE (forbidden). Reports the
union of geometry-recoverable marks and the best single geometry knob."""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer

TOL = 2


def levels_for(candles, pdh, pdl, pmh, pml):
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [("ORhi", or_high), ("ORlo", or_low)]
    if pdh is not None and pdl is not None:
        pairs += [("PDH", pdh), ("PDL", pdl)]
    if pmh is not None and pml is not None:
        pairs += [("PMH", pmh), ("PML", pml)]
    return pairs


def walk(candles, level, is_long, window=12, max_confirm_gap=3, need_leave=True, eps_mult=0.10, retest_mult=0.0):
    if len(candles) < 4: return False
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return False
    if not is_long and cur.close >= level: return False
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = eps_mult * avg_rng
    rtol = retest_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size: return False
    state, retest_idx = "seek_break", None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed: state = "seek_retest" if not need_leave else "seek_leave"
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left: state = "seek_retest"
            elif failed: state = "seek_break"
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back: retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back: retest_idx = i
    if retest_idx is None: return False
    if (len(w) - 1) - retest_idx > max_confirm_gap: return False
    return True


GEO = {
    "window20":       dict(window=20),
    "window30":       dict(window=30),
    "gap6":           dict(max_confirm_gap=6),
    "gap9":           dict(max_confirm_gap=9),
    "w20g6":          dict(window=20, max_confirm_gap=6),
    "w30g9":          dict(window=30, max_confirm_gap=9),
    "no_leave":       dict(need_leave=False),
    "eps0":           dict(eps_mult=0.0),
    "w20noleave":     dict(window=20, need_leave=False),
    "w30g9_noleave":  dict(window=30, max_confirm_gap=9, need_leave=False),
    "w30g9_eps0":     dict(window=30, max_confirm_gap=9, eps_mult=0.0),
    "ALLGEO":         dict(window=30, max_confirm_gap=9, need_leave=False, eps_mult=0.0),
}
# tolerance variants (forbidden) for comparison
TOLV = {f"rt{m}": dict(retest_mult=m) for m in (0.5, 1.0, 1.5, 3.0)}
TOLV["rt1_w30g9"] = dict(retest_mult=1.0, window=30, max_confirm_gap=9)


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    geo_hits = {k: set() for k in GEO}
    tol_hits = {k: set() for k in TOLV}
    only_tol = set()
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles: continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]
        key = f"{r['symbol']}|{r['day']}|{e}"
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for name, level in levels_for(cs, pdh, pdl, pmh, pml):
                if level is None: continue
                if abs(level - close) / close >= 0.005: continue
                for lv, is_long in ((level, True), (level, False)):
                    for k, kw in GEO.items():
                        if walk(cs, lv, is_long, **kw): geo_hits[k].add(key)
                    for k, kw in TOLV.items():
                        if walk(cs, lv, is_long, **kw): tol_hits[k].add(key)
    union_geo = set()
    for k in GEO: union_geo |= geo_hits[k]
    print("per geometry knob (marks recovered of 27):")
    for k in GEO:
        print(f"  {k:16s} {len(geo_hits[k])}")
    print(f"  UNION of all geometry: {len(union_geo)}")
    print("\nper tolerance knob (forbidden):")
    for k in TOLV:
        print(f"  {k:16s} {len(tol_hits[k])}")
    best_tol = set()
    for k in TOLV: best_tol |= tol_hits[k]
    only_tol = best_tol - union_geo
    print(f"\nunion tolerance: {len(best_tol)}")
    print(f"recovered by tolerance but NOT by any geometry: {len(only_tol)}")
    for k in sorted(only_tol): print(f"   tol-only: {k}")
    print(f"\nrecovered by geometry (the wins):")
    for k in sorted(union_geo): print(f"   geo: {k}")
    # best single geometry knob
    best = max(GEO, key=lambda k: len(geo_hits[k]))
    print(f"\nbest single geometry knob: {best} -> {len(geo_hits[best])}")
    print(f"  marks: {sorted(geo_hits[best])}")


if __name__ == "__main__":
    main()
