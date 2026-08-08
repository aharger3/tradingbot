"""omen-3.7 T5 probe: WHICH part of detect_break_retest's geometry blocks the
27 S marks classified `no_break_retest` by research/miss_autopsy.md.

This does NOT recompute the autopsy. It reads miss_autopsy.jsonl, takes only the
rows with tier == S and miss_reason == "no_break_retest", and for each one
re-walks the SAME FSM detect_break_retest walks, instrumented, over the same
levels detect_signals would offer -- reporting the furthest state reached and
whether a candidate relaxation would have completed the sequence.

Purpose: pick ONE mechanism for DETECT_WIDE, and register a recall prediction.
"""
from __future__ import annotations
import json, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4
from omen_bot import OpeningRangeAnalyzer, detect_break_retest

TOL = 2


def levels_for(candles, pdh, pdl, pmh, pml):
    """level_pairs exactly as detect_signals builds them (HODLOD_PAIR off)."""
    or_high, or_low = OpeningRangeAnalyzer.get_opening_range(candles)
    pairs = [(or_high, or_low)]
    if pdh is not None and pdl is not None:
        pairs.append((pdh, pdl))
    if pmh is not None and pml is not None:
        pairs.append((pmh, pml))
    return pairs


def walk(candles, level, is_long, window=12, max_confirm_gap=3,
         need_leave=True, eps_mult=0.10, retest_mult=0.0):
    """Instrumented mirror of omen_bot.detect_break_retest. Returns
    (ok, furthest_state, confirm_gap_or_None, blocker)."""
    if len(candles) < 4:
        return False, "too_few", None, "too_few_candles"
    w = candles[-window:]
    cur = w[-1]
    if is_long and cur.close <= level:
        return False, "no_confirm_close", None, "cur_not_through_level"
    if not is_long and cur.close >= level:
        return False, "no_confirm_close", None, "cur_not_through_level"
    avg_rng = sum(c.high - c.low for c in w) / len(w)
    eps = eps_mult * avg_rng
    rtol = retest_mult * avg_rng
    adverse = cur.lower_wick if not is_long else cur.upper_wick
    if adverse > 1.5 * cur.body_size:
        return False, "adverse_wick", None, "adverse_wick"

    order = {"seek_break": 0, "seek_leave": 1, "seek_retest": 2, "hold": 3}
    state, retest_idx, furthest = "seek_break", None, "seek_break"
    for i in range(1, len(w)):
        c, p = w[i], w[i - 1]
        if state == "seek_break":
            crossed = (p.close <= level and c.close > level + eps) if is_long \
                else (p.close >= level and c.close < level - eps)
            if crossed:
                state = "seek_retest" if not need_leave else "seek_leave"
        elif state == "seek_leave":
            left = (c.low > level + eps) if is_long else (c.high < level - eps)
            failed = (c.close <= level + eps) if is_long else (c.close >= level - eps)
            if left:
                state = "seek_retest"
            elif failed:
                state = "seek_break"
        elif state == "seek_retest":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx, state = i, "hold"
        elif state == "hold":
            back = (c.low <= level + rtol) if is_long else (c.high >= level - rtol)
            if back:
                retest_idx = i
        if order[state] > order[furthest]:
            furthest = state

    if retest_idx is None:
        return False, furthest, None, f"stalled_at_{furthest}"
    gap = (len(w) - 1) - retest_idx
    if gap > max_confirm_gap:
        return False, "hold", gap, "confirm_gap_too_stale"
    return True, "hold", gap, None


VARIANTS = {
    "baseline":            dict(),
    "window20":            dict(window=20),
    "window30":            dict(window=30),
    "gap6":                dict(max_confirm_gap=6),
    "gap9":                dict(max_confirm_gap=9),
    "window20+gap6":       dict(window=20, max_confirm_gap=6),
    "window30+gap9":       dict(window=30, max_confirm_gap=9),
    "no_leave":            dict(need_leave=False),
    "eps0":                dict(eps_mult=0.0),
    "window20+no_leave":   dict(window=20, need_leave=False),
    "retest0.25":          dict(retest_mult=0.25),
    "retest0.50":          dict(retest_mult=0.50),
    "retest1.00":          dict(retest_mult=1.00),
    "retest1.50":          dict(retest_mult=1.50),
    "retest0.50+window20": dict(retest_mult=0.50, window=20),
    "retest1.00+window20": dict(retest_mult=1.00, window=20),
    "retest1.00+gap6":     dict(retest_mult=1.00, max_confirm_gap=6),
}
for _m in (0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9,1.0,1.1,1.2,1.3,1.4,1.5,1.75,2.0,2.5,3.0):
    VARIANTS["sweep_%.2f" % _m] = dict(retest_mult=_m)


def main():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "miss_autopsy.jsonl"))]
    targets = [r for r in rows
               if r.get("tier") == "S" and r.get("miss_reason") == "no_break_retest"]
    print(f"S x no_break_retest marks: {len(targets)}")

    hits = {k: 0 for k in VARIANTS}
    blockers = Counter()
    per_mark = []
    for r in targets:
        candles = t4.rth_candles(r["symbol"], r["day"])
        if not candles:
            print(f"  !! no bars {r['symbol']} {r['day']}")
            continue
        pdh, pdl, _o, _c = t4.prior_day_levels(r["symbol"], r["day"])
        pmh, pml = t4.premarket_extremes(r["symbol"], r["day"])
        e = r["entry_i"]
        bars = [b for b in range(e - TOL, e + TOL + 1) if 0 <= b < len(candles)]

        mark_hit = {k: False for k in VARIANTS}
        mark_block = set()
        for b in bars:
            cs = candles[: b + 1]
            close = cs[-1].close
            for hi, lo in levels_for(cs, pdh, pdl, pmh, pml):
                for level, is_long in ((hi, True), (lo, False)):
                    if level is None:
                        continue
                    # the classifier's own "reference level is near" gate
                    if abs(level - close) / close >= 0.005:
                        continue
                    for name, kw in VARIANTS.items():
                        ok, _st, _g, blk = walk(cs, level, is_long, **kw)
                        if ok:
                            mark_hit[name] = True
                        elif name == "baseline" and blk:
                            mark_block.add(blk)
        for k, v in mark_hit.items():
            hits[k] += 1 if v else 0
        if not mark_hit["baseline"] and mark_block:
            # rank blockers by how deep into the sequence they are: the
            # least-deep blocker present is what actually has to move first
            rank = ["cur_not_through_level", "adverse_wick", "stalled_at_seek_break",
                    "stalled_at_seek_leave", "stalled_at_seek_retest",
                    "stalled_at_hold", "confirm_gap_too_stale", "too_few_candles"]
            deepest = max(mark_block, key=lambda b: rank.index(b) if b in rank else -1)
            blockers[deepest] += 1
        per_mark.append({"symbol": r["symbol"], "day": r["day"],
                         "entry_i": e, **{k: mark_hit[k] for k in VARIANTS}})

    n = len(targets)
    print(f"\nmarks reached (within +/-{TOL} bars) per variant, of {n}:")
    for k in VARIANTS:
        print(f"  {k:20s} {hits[k]:3d}  ({hits[k]/n*100:.1f}%)")
    print("\ndominant baseline blocker per still-missed mark:")
    for k, v in blockers.most_common():
        print(f"  {k:28s} {v}")

    with open(os.path.join(HERE, "_t5_wide_probe.json"), "w") as f:
        json.dump({"n": n, "hits": hits, "blockers": dict(blockers),
                   "per_mark": per_mark}, f, indent=1)


if __name__ == "__main__":
    main()
