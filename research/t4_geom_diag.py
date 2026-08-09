"""T4 geometry diagnostic across all 30 S x no_break_retest marks.

For each mark, for the nearest qualifying reference level (long if cur.close >
level else short), walk detect_break_retest's FSM instrumented and report:
  - furthest state reached (baseline, rtol=0)
  - break bar, leave bar (if any)
  - the candle after leave that approaches the level CLOSEST (max high for short /
    min low for long), its bar index, its distance to the level in $ and in
    avg-ranges, and whether the MARK bar (entry_i +/-2) is that closest-approach
    bar or a later failed retest
This isolates whether the retest is a near-miss (tolerance) vs a wrong-level vs a
late failed-retest the window/confirm-gap drops.
"""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer

WINDOW = 12
EPS_MULT = 0.10
TOL = 2


def levels_for(candles, pdh, pdl, pmh, pml):
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [("OR high", or_high), ("OR low", or_low)]
    if pdh is not None and pdl is not None:
        pairs += [("PDH", pdh), ("PDL", pdl)]
    if pmh is not None and pml is not None:
        pairs += [("PMH", pmh), ("PML", pml)]
    return [(n, v) for n, v in pairs if v is not None]


def walk(candles, level, is_long, window=12, eps_mult=0.10, rtol=0.0):
    if len(candles) < 4:
        return None
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return ("cur_not_through", None, None, None, None)
    if not is_long and cur.close >= level:
        return ("cur_not_through", None, None, None, None)
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = eps_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return ("adverse_wick", None, None, None, avg_rng)
    state, retest_idx, break_i, leave_i = "seek_break", None, None, None
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"; break_i = i
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"; leave_i = i
            elif failed:
                state = "seek_break"; break_i = None
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i
    if retest_idx is not None:
        final = "hold"
    else:
        final = state
    # closest approach after leave (or after break if no leave)
    start = leave_i if leave_i is not None else (break_i if break_i is not None else 0)
    closest_i, closest_val, closest_dist = None, None, None
    for i in range(start + 1, len(w)):
        v = w[i].low if is_long else w[i].high
        d = (level - v) if is_long else (v - level)   # + = short of level
        if closest_dist is None or d < closest_dist:
            closest_dist, closest_i, closest_val = d, i, v
    return (final, break_i, leave_i, retest_idx, avg_rng,
            closest_i, closest_val, closest_dist, eps)


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows
               if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    print(f"{'sym':6s} {'day':10s} {'ei':>3s} {'lvl':9s} {'dir':5s} {'final':>16s} {'brk':>3s} {'lv':>3s} {'rt':>3s} {'closest':>7s} {'bar':>4s} {'dist$':>7s} {'distR':>6s} {'markOff':>7s}")
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles:
            continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        # evaluate at the mark bar (and +/-2); pick the bar/level combo that
        # reaches the deepest state, to report the geometry the engine sees.
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]
        best = None
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for nm, level in levels_for(cs, pdh, pdl, pmh, pml):
                if abs(level - close) / close >= 0.005:
                    continue
                is_long = close > level
                res = walk(cs, level, is_long)
                if res is None:
                    continue
                final = res[0]
                depth = {"cur_not_through": 0, "adverse_wick": 1, "seek_break": 2,
                         "seek_leave": 3, "seek_retest": 4, "hold": 5}.get(final, 0)
                if best is None or depth > best[0]:
                    best = (depth, b, nm, level, is_long, res)
        if best is None:
            print(f"{r['symbol']:6s} {r['day']:10s} {e:3d}  (no near level)")
            continue
        depth, b, nm, level, is_long, res = best
        final, brk, lv, rt, avg, ci, cv, cd, eps = res
        dirn = "long" if is_long else "short"
        # closest-approach bar in window -> map to day-bar index
        w0 = b + 1 - WINDOW  # window covers day bars [w0 .. b]
        ci_day = (w0 + ci) if ci is not None else None
        distR = (cd / avg) if (cd is not None and avg) else None
        markoff = (ci_day - e) if ci_day is not None else None
        cvs = f"${cv:6.2f}" if cv is not None else f"{'-':>7s}"
        cds = f"{cd:7.3f}" if cd is not None else f"{'-':>7s}"
        drs = f"{distR:6.2f}" if distR is not None else f"{'-':>6s}"
        mos = f"{markoff if markoff is not None else '-':>7}"
        print(f"{r['symbol']:6s} {r['day']:10s} {e:3d} ${level:7.2f} {dirn:5s} {final:>16s} "
              f"{brk if brk is not None else '-':>3} {lv if lv is not None else '-':>3} "
              f"{rt if rt is not None else '-':>3} {cvs} {ci_day if ci_day is not None else '-':>4} "
              f"{cds} {drs} {mos}")


if __name__ == "__main__":
    main()
