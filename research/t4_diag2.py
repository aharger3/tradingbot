"""T4 diagnostic 2: classify the 14 seek_retest stalls. After the LEAVE bar,
measure the CLOSEST approach to the level in the remaining window, and whether
the closest approach is the LAST bar (retest outside window) vs an interior bar
(came close but didn't touch = tolerance-recoverable)."""
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


def walk(candles, level, is_long, window=12, max_confirm_gap=3):
    if len(candles) < 4:
        return None
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level: return None
    if not is_long and cur.close >= level: return None
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size: return None
    state, retest_idx = "seek_break", None
    leave_idx = None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed: state = "seek_leave"
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"; leave_idx = i
            elif failed:
                state = "seek_break"
        elif state == "seek_retest":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back: retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back: retest_idx = i
    if retest_idx is not None:
        return ("ok", leave_idx, retest_idx, None)
    if state != "seek_retest":
        return (state, leave_idx, None, None)
    # stalled at seek_retest: closest approach after leave
    best_i, best_d = None, None
    for i in range(leave_idx, len(w)):
        c = w[i]
        # distance of the retest field from the level, signed toward level
        if is_long:
            d = c.low - level          # >0 means low still above level (didn't touch)
        else:
            d = level - c.high          # >0 means high still below level
        if best_d is None or d < best_d:
            best_d, best_i = d, i
    return ("seek_retest", leave_idx, None, (best_i, best_d, avg_rng))


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    cats = {"no_return": [], "return_at_last": [], "near_miss": [], "other": []}
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles: continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]
        res = None
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for name, level in levels_for(cs, pdh, pdl, pmh, pml):
                if level is None: continue
                if abs(level - close) / close >= 0.005: continue
                for lv, is_long in ((level, True), (level, False)):
                    out = walk(cs, lv, is_long)
                    if out and out[0] == "seek_retest":
                        res = (r, name, lv, is_long, b, out)
                        break
                if res: break
            if res: break
        if not res:
            continue
        r, name, lv, is_long, b, out = res
        st, leave_idx, _, (best_i, best_d, ar) = out
        d_r = best_d / ar if ar else 0
        row = (r["symbol"], r["day"], e, name, "L" if is_long else "S", b,
               leave_idx, best_i, round(d_r, 2), round(best_d, 3))
        if best_d > 0.5 * ar:           # never got within half a range -> no real return
            cats["no_return"].append(row)
        elif best_i == 11:              # closest approach IS the last bar -> return outside window
            cats["return_at_last"].append(row)
        else:                           # came close inside window but didn't touch
            cats["near_miss"].append(row)
    for cat, rows2 in cats.items():
        print(f"=== {cat} ({len(rows2)}) ===")
        for x in rows2:
            print(f"  {x[0]:6s} {x[1]} i={x[2]:3d} lvl={x[3]} {x[4]} bar={x[5]} leave@{x[6]} closest@{x[7]} dist={x[8]}r (${x[9]})")
        print()


if __name__ == "__main__":
    main()
