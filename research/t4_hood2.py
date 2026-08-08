"""Trace HOOD OR-low short fire at bar 17, window 12 vs 20 (no proximity gate)."""
from __future__ import annotations
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer


def trace(candles, level, is_long, window, gap=3):
    if len(candles) < 4: return (None, "too_few", [])
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return (None, "no_confirm_close", [])
    if not is_long and cur.close >= level: return (None, "no_confirm_close", [])
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size: return (None, "adverse_wick", [])
    state, retest_idx = "seek_break", None
    seq = []
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
            if back: retest_idx = i; seq.append(("retest2", i, round(c.low if is_long else c.high, 2)))
    if retest_idx is None: return (None, state, seq)
    g = (len(w) - 1) - retest_idx
    if g > gap: return (None, "stale(gap=%d retest@%d last=%d)" % (g, retest_idx, len(w)-1), seq)
    return ("FIRE gap=%d" % g, "hold", seq)


candles = t4.rth_candles("HOOD", "2025-02-24")
lv = 51.95
for b in (16, 17, 18):
    cs = candles[:b+1]
    for win in (12, 20, 30):
        note, st, seq = trace(cs, lv, False, win)
        print(f"bar={b} close={cs[-1].close:.2f} ORlo short w={win:2d} -> {str(note):18s} state={st}")
        if win == 12 or win == 20:
            print(f"     seq={seq}")
