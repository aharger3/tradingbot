"""T4 diagnostic: WHY does the retest never register on the 27/30 S x no_break_retest marks?

For each mark, for each near reference level, walk detect_break_retest's FSM
instrumented over the SAME window the engine uses, and print the per-bar OHLC
relative to the level + the state reached. Goal: find the geometry bug, not
re-arm a tolerance.
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer

TOL = 2
WINDOW = 12
EPS_MULT = 0.10


def levels_for(candles, pdh, pdl, pmh, pml):
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [("OR high", "OR low", or_high, or_low)]
    if pdh is not None and pdl is not None:
        pairs.append(("PDH", "PDL", pdh, pdl))
    if pmh is not None and pml is not None:
        pairs.append(("PMH", "PML", pmh, pml))
    return pairs


def walk_print(candles, level, is_long, window=12, eps_mult=0.10, rtol=0.0):
    if len(candles) < 4:
        return "too_few"
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return "cur_not_through_level(long)"
    if not is_long and cur.close >= level:
        return "cur_not_through_level(short)"
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = eps_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return "adverse_wick"
    rows = []
    state, retest_idx = "seek_break", None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        tag = ""
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"; tag = "BREAK"
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"; tag = "LEAVE"
            elif failed:
                state = "seek_break"; tag = "BREAK-FAIL"
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx, state = i, "hold"; tag = "RETEST"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i; tag = "RETEST-update"
        rel = ("c.low-level" if is_long else "level-c.high")
        rows.append((i, c.timestamp, c.open, c.high, c.low, c.close, state, tag))
    final = "hold" if retest_idx is not None else state
    return final, retest_idx, rows, avg_rng, eps


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows
               if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    only = sys.argv[1:]  # optional 'SYM DAY' filters
    for r in targets:
        if only and (r["symbol"], r["day"]) not in zip(only[::2], only[1::2]) and r["symbol"] not in only and r["day"] not in only:
            # crude filter: skip if none of args match symbol or day
            if not any(a == r["symbol"] or a == r["day"] for a in only):
                continue
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles:
            continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        print(f"\n=== {r['symbol']} {r['day']} entry_i={e}  (mark side: {r.get('side','?')}) ===")
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]
        # try each bar as the "current" bar
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for hi_name, lo_name, hi, lo in levels_for(cs, pdh, pdl, pmh, pml):
                for level, is_long, nm in ((hi, True, hi_name), (lo, False, lo_name)):
                    if level is None:
                        continue
                    if abs(level - close) / close >= 0.005:
                        continue
                    res = walk_print(cs, level, is_long)
                    if isinstance(res, str):
                        st = res
                    else:
                        st, ri, rr, avg, eps = res
                    dirn = "long" if is_long else "short"
                    print(f"  bar={b} {dirn:5s} lvl={nm} ${level:.2f} -> {st}")
        # detailed dump for the bar closest to entry against the nearest level
        b = min(bars, key=lambda x: abs(x - e)) if bars else e
        cs = candles[: b + 1]
        close = cs[-1].close
        best = None
        for hi_name, lo_name, hi, lo in levels_for(cs, pdh, pdl, pmh, pml):
            for level, is_long, nm in ((hi, True, hi_name), (lo, False, lo_name)):
                if level is None:
                    continue
                if abs(level - close) / close >= 0.005:
                    continue
                best = (level, is_long, nm)
        if best:
            level, is_long, nm = best
            res = walk_print(cs, level, is_long)
            print(f"  --- detail at bar={b} lvl={nm} ${level:.2f} ({'long' if is_long else 'short'}) ---")
            if not isinstance(res, str):
                st, ri, rr, avg, eps = res
                print(f"  final_state={st} retest_idx={ri} avg_rng={avg:.3f} eps={eps:.3f} (rtol=0 -> exact touch)")
                print(f"  {'i':>3} {'time':>7} {'open':>9} {'high':>9} {'low':>9} {'close':>9} {'low-lvl':>9} {'state':>14} tag")
                for (i, ts, o, h, l, c, s, tag) in rr:
                    d = (l - level) if is_long else (level - h)
                    print(f"  {i:>3} {ts:>7} {o:>9.2f} {h:>9.2f} {l:>9.2f} {c:>9.2f} {d:>9.3f} {s:>14} {tag}")


if __name__ == "__main__":
    main()
