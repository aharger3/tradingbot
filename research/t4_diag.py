"""T4 diagnostic: for the 27 S x no_break_retest marks, walk the FSM at baseline
and dump, for the FIRST (level, bar) that reaches seek_retest but stalls there,
the window candles relative to the level — so we can see why the retest step
does not register. Prints a compact per-mark trace."""
from __future__ import annotations
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
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
        return False, "too_few", None, None
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return False, "no_confirm_close", None, None
    if not is_long and cur.close >= level:
        return False, "no_confirm_close", None, None
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = 0.10 * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return False, "adverse_wick", None, None
    state, retest_idx, furthest = "seek_break", None, "seek_break"
    seq = []
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_leave"
                seq.append(("break", i, round(c.close, 2)))
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"
                seq.append(("leave", i, round(c.low if is_long else c.high, 2)))
            elif failed:
                state = "seek_break"
                seq.append(("fail", i, round(c.close, 2)))
        elif state == "seek_retest":
            back = (c.low <= level) if is_long else (c.high >= level)
            if back:
                retest_idx, state = i, "hold"
                seq.append(("retest", i, round(c.low if is_long else c.high, 2)))
        if state not in ("hold",) and i == len(w) - 1 and retest_idx is None:
            furthest = state
    if retest_idx is None:
        return False, furthest, None, seq
    gap = (len(w) - 1) - retest_idx
    if gap > max_confirm_gap:
        return False, "stale", gap, seq
    return True, "hold", gap, seq


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows
               if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    print(f"marks: {len(targets)}\n")
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles:
            continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]
        best = None
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for name, level in levels_for(cs, pdh, pdl, pmh, pml):
                if level is None:
                    continue
                if abs(level - close) / close >= 0.005:
                    continue
                for level_val, is_long in ((level, True), (level, False)):
                    ok, st, gap, seq = walk(cs, level_val, is_long)
                    depth = {"seek_break": 1, "seek_leave": 2, "seek_retest": 3,
                             "hold": 4, "stale": 4, "no_confirm_close": 0,
                             "adverse_wick": 0, "too_few": 0}.get(st, 0)
                    if best is None or depth > best[0]:
                        best = (depth, st, name, level_val, is_long, b, seq, cs[-12:])
        if best is None:
            print(f"{r['symbol']} {r['day']} i={e}: nothing in range")
            continue
        depth, st, name, level, is_long, b, seq, w = best
        mark = f"{r['symbol']} {r['day']} i={e} (bar={b}) lvl={name}={'long' if is_long else 'short'} {level:.2f} -> {st}"
        print(mark)
        # print window candles relative to level
        for j, c in enumerate(w):
            rel = "break" if False else ""
            tag = ""
            for s in seq:
                if s[1] == j + (len(candles[:b+1]) - len(w)):
                    pass
            # show offset of each field from level in units of avg range
            ar = sum(cc.high - cc.low for cc in w) / len(w)
            def u(x):
                return f"{(x-level)/ar:+.2f}r" if ar else "?"
            print(f"   j={j:2d} O{u(c.open)} H{u(c.high)} L{u(c.low)} C{u(c.close)} body={c.body_size:.2f}")
        print(f"   seq: {seq}")
        print()


if __name__ == "__main__":
    main()
