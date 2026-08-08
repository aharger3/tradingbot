"""Diagnose the 3 S-fired marks the fb_w20_g6 fix recovers: show why the 12-bar
window misses (break too early / retest too late) and how the 20-bar window
completes the sequence."""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer

GAINED = ["IWM|2026-05-28|46", "PLTR|2025-09-18|14", "QQQ|2025-12-05|35"]


def levels_for(candles, pdh, pdl, pmh, pml):
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [("ORhi", or_high, True), ("ORlo", or_low, False)]
    if pdh is not None and pdl is not None:
        pairs += [("PDH", pdh, True), ("PDL", pdl, False)]
    if pmh is not None and pml is not None:
        pairs += [("PMH", pmh, True), ("PML", pml, False)]
    return pairs


def trace(candles, level, is_long, window, gap):
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return "cur_not_through"
    if not is_long and cur.close >= level: return "cur_not_through"
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    state, retest_idx, seq = "seek_break", None, []
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long else (p.close >= level and c.close < level - eps)
            if crossed: state = "seek_leave"; seq.append(("break", i, round(c.close, 2)))
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left: state = "seek_retest"; seq.append(("leave", i, round(c.low if is_long else c.high, 2)))
            elif failed: state = "seek_break"; seq.append(("fail", i, round(c.close, 2)))
        elif state == "seek_retest":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back: retest_idx, state = i, "hold"; seq.append(("retest", i, round(c.low if is_long else c.high, 2)))
        elif state == "hold":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back: retest_idx = i
    if retest_idx is None:
        return f"stall_at_{state}  seq={seq}"
    cg = (len(w) - 1) - retest_idx
    if cg > gap:
        return f"retest_too_stale(gap={cg}>{gap})  seq={seq}"
    return f"OK retest@{retest_idx} gap={cg}  seq={seq}"


for key in GAINED:
    sym, day, e = key.split("|"); e = int(e)
    candles = t4.rth_candles(sym, day)
    pdh, pdl, _o, _c = t4.prior_day_levels(sym, day)
    pmh, pml = t4.premarket_extremes(sym, day)
    print(f"\n=== {key}  (mark bar={e}) ===")
    for b in range(e - 2, e + 3):
        if not (0 <= b < len(candles)): continue
        cs = candles[:b + 1]
        close = cs[-1].close
        for nm, lvl, is_long in levels_for(cs, pdh, pdl, pmh, pml):
            if lvl is None: continue
            if abs(lvl - close) / close >= 0.005: continue
            r12 = trace(cs, lvl, is_long, 12, 3)
            r20 = trace(cs, lvl, is_long, 20, 6)
            if "OK" in r20 or "OK" in r12:
                print(f"  bar={b} {nm}={lvl} {'long' if is_long else 'short'}")
                print(f"    win12/g3 : {r12}")
                print(f"    win20/g6 : {r20}")
