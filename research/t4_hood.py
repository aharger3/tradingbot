"""Why does widening the window regress HOOD|2025-02-24|16? Trace
detect_break_retest's FSM over the levels signal_runner offers, at window=12 vs
window=20, for the bars around the mark (entry_i=16)."""
from __future__ import annotations
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer, detect_break_retest


def trace(candles, level, is_long, window):
    """Return (note-or-None, furthest_state, retest_idx, seq)."""
    if len(candles) < 4: return (None, "too_few", None, [])
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return (None, "no_confirm_close", None, [])
    if not is_long and cur.close >= level: return (None, "no_confirm_close", None, [])
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size: return (None, "adverse_wick", None, [])
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
    if retest_idx is None: return (None, state, None, seq)
    gap = (len(w) - 1) - retest_idx
    if gap > 3: return (None, "stale(gap=%d)" % gap, retest_idx, seq)
    return ("FIRE gap=%d" % gap, "hold", retest_idx, seq)


candles = t4.rth_candles("HOOD", "2025-02-24")
pdh, pdl, _o, _c = t4.prior_day_levels("HOOD", "2025-02-24")
pmh, pml = t4.premarket_extremes("HOOD", "2025-02-24")
print(f"HOOD 2025-02-24 pdh={pdh} pdl={pdl} pmh={pmh} pml={pml}")
for b in range(14, 19):
    cs = candles[:b+1]
    orh, orl = OpeningRangeAnalyzer.get_opening_range(cs)
    close = cs[-1].close
    pairs = [("ORhi", orh, True), ("ORlo", orl, False), ("PDH", pdh, True), ("PDL", pdl, False), ("PMH", pmh, True), ("PML", pml, False)]
    print(f"\n=== bar={b} close={close:.2f} ===")
    for name, lv, is_long in pairs:
        if lv is None: continue
        if abs(lv - close) / close >= 0.005: continue
        for win in (12, 20):
            note, st, ri, seq = trace(cs, lv, is_long, win)
            print(f"   {name:4s} {'L' if is_long else 'S'} w={win:2d} lvl={lv:.2f} -> {str(note):14s} state={st} seq={seq}")
