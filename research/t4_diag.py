"""T4 diagnostic: dump the candle-by-candle FSM trace for the 27 S x no_break_retest
marks, so the geometry flaw can be seen, not guessed.

For each mark, for each bar in +/-2 of entry_i, for each reference level/direction
within 0.5% of close, run an instrumented walk that prints every candle in the
12-bar window with OHLC, the level, eps/rtol, and the state transition. Report the
furthest state, the break/leave/retest candle indexes, and (for seek_retest stalls)
the closest the retest-side wick got to the level AFTER the leave, in $ and x avg
range.
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer


def levels_for(candles, pdh, pdl, pmh, pml):
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [("ORhigh", or_high), ("ORlow", or_low)]
    if pdh is not None and pdl is not None:
        pairs.append(("PDH", pdh)); pairs.append(("PDL", pdl))
    if pmh is not None and pml is not None:
        pairs.append(("PMH", pmh)); pairs.append(("PML", pml))
    return pairs


def trace(cs, level, is_long, window=12, eps_mult=0.10, rtol_mult=0.0):
    """Instrumented walk returning rich info."""
    w = cs[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return {"ok": False, "block": "cur_not_through_level", "furthest": "no_confirm_close"}
    if not is_long and cur.close >= level:
        return {"ok": False, "block": "cur_not_through_level", "furthest": "no_confirm_close"}
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = eps_mult * avg_rng
    rtol = rtol_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return {"ok": False, "block": "adverse_wick", "furthest": "adverse_wick",
                "avg_rng": avg_rng, "eps": eps}
    state = "seek_break"
    retest_idx = None
    break_idx = leave_idx = None
    furthest = "seek_break"
    order = {"seek_break": 0, "seek_leave": 1, "seek_retest": 2, "hold": 3}
    # track closest approach of the retest-side wick after a leave
    closest_after_leave = None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"; break_idx = i
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"; leave_idx = i
            elif failed:
                state = "seek_break"; break_idx = None
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            dist = (c.low - level) if is_long else (level - c.high)
            if closest_after_leave is None or dist < closest_after_leave:
                closest_after_leave = dist
            if back:
                retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i
        if order[state] > order[furthest]:
            furthest = state
    out = {"ok": False, "furthest": furthest, "avg_rng": avg_rng, "eps": eps,
           "break_idx": break_idx, "leave_idx": leave_idx, "retest_idx": retest_idx,
           "closest_after_leave": closest_after_leave,
           "window_len": len(w)}
    if retest_idx is None:
        out["block"] = f"stalled_at_{furthest}"
        return out
    gap = (len(w) - 1) - retest_idx
    if gap > 3:
        out["block"] = "confirm_gap_too_stale"; out["gap"] = gap
        return out
    out["ok"] = True; out["block"] = None; out["gap"] = gap
    return out


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    print(f"=== {len(targets)} S x no_break_retest marks ===\n")
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles:
            print(f"## {r['symbol']} {r['day']} ei={r['entry_i']}  NO BARS\n")
            continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        bars = [b for b in range(e - 2, e + 3) if 0 <= b < len(candles)]
        print(f"## {r['symbol']} {r['day']} ei={e}  (test bars {bars})")
        best = None
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for nm, lv in levels_for(cs, pdh, pdl, pmh, pml):
                if lv is None:
                    continue
                if abs(lv - close) / close >= 0.005:
                    continue
                for is_long in (True, False):
                    res = trace(cs, lv, is_long)
                    res.update({"bar": b, "level_name": nm, "level": lv,
                                "is_long": is_long, "close": close})
                    key = (res["furthest"], res["block"], nm, is_long)
                    depth = {"no_confirm_close": 0, "adverse_wick": 0,
                            "seek_break": 1, "seek_leave": 2,
                            "seek_retest": 3, "hold": 4}
                    sc = (depth.get(res["furthest"], 0) + (1 if res["ok"] else 0))
                    if best is None or sc > best[0]:
                        best = (sc, res)
        if best is None:
            print("  (no near level)\n"); continue
        _, R = best
        lv = R["level"]; ar = R.get("avg_rng", 0)
        print(f"  BEST furthest={R['furthest']} block={R['block']} "
              f"lvl={R['level_name']}=${lv:.2f} long={R['is_long']} bar={R['bar']} close=${R['close']:.2f}")
        print(f"  avg_rng=${ar:.3f} eps=${R.get('eps',0):.3f} "
              f"break_idx={R.get('break_idx')} leave_idx={R.get('leave_idx')} "
              f"retest_idx={R.get('retest_idx')}")
        if R.get("closest_after_leave") is not None and not R["ok"]:
            d = R["closest_after_leave"]
            print(f"  closest retest-side wick got to level: ${d:.3f} = {d/ar:.2f}x avg_rng "
                  f"(rtol mult needed: {d/ar:.2f})")
        # dump the window candles of the best bar
        cs = candles[: R["bar"] + 1]
        w = cs[-12:]
        is_long = R["is_long"]
        print(f"  window (is_long={is_long}, level=${lv:.2f}):")
        for i, c in enumerate(w):
            rel = ""
            if is_long:
                rel += "B" if c.close > lv + R.get("eps",0) else ("b" if c.close > lv else ".")
            else:
                rel += "B" if c.close < lv - R.get("eps",0) else ("b" if c.close < lv else ".")
            print(f"    [{i:2d}] {c.timestamp} O={c.open:.2f} H={c.high:.2f} "
                  f"L={c.low:.2f} C={c.close:.2f} {rel}")
        print()


if __name__ == "__main__":
    main()
