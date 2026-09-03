"""g76_minute_walk.py -- walk the bar Austin named and say what was missing.

g76_minute_measure.py finds the cards where he named an entry minute and the
engine had NO signal there at all. This script goes to that exact bar and asks
each detector, level by level and direction by direction, which clause it fell
over on. The reasons aggregate into a specification: the list of things the
engine cannot yet see at the moment he can see them.

Nothing is inferred. Every reason comes from the detector's own funnel:

  break-and-retest   omen_bot.BR_FUNNEL, read as a delta around one call, so the
                     terminal stage is the detector's own word, not a guess:
                       no_confirm_close  the bar did not close through the level
                       adverse_wick      wick against the trade > 1.5x the body
                       no_break          nothing closed through the level in the
                                         12-bar window
                       no_leave          it broke but never cleared the level
                       no_retest         it broke and left but never came back
                                         to TOUCH the level (exact touch)
                       stale_retest      the retest was > 3 bars before this one
  one-candle rule    omen_bot.detect_order_block_setup's own note string
  strong PA          the entry candle's body vs the average of the prior 10,
                     against signal_runner.STRONG_PA_MULT

READ-ONLY on the mark file, the book and every engine module. No engine constant
is changed; the detectors are called exactly as signal_runner.detect_signals
calls them, with the same levels, the same window and the same shipped
tolerances.

Writes ONE file: research/g76_minute_walk.json

    python research/g76_minute_walk.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import omen_bot as ob  # noqa: E402
import signal_runner as sr  # noqa: E402
from research.t4_engine_recall import (  # noqa: E402
    rth_candles, prior_day_levels, premarket_extremes)

MEASURE = os.path.join(HERE, "g76_minute_measure.json")
OUT = os.path.join(HERE, "g76_minute_walk.json")

BR_STAGES = ("too_short", "no_confirm_close", "adverse_wick", "no_break",
             "no_leave", "no_retest", "stale_retest", "passed")

PLAIN = {
    "no_confirm_close": "the bar he bought never closed back through the level",
    "adverse_wick":     "the bar had a wick against the trade bigger than 1.5x "
                        "its body, so the engine calls it a fight",
    "no_break":         "nothing closed through that level in the 12 bars before "
                        "his minute",
    "no_leave":         "price broke the level but never fully cleared it, so "
                        "the engine calls it chop on the level",
    "no_retest":        "price broke and left, but never came back to TOUCH the "
                        "level exactly -- a near miss is not a retest",
    "stale_retest":     "the retest happened more than 3 bars before his minute",
    "too_short":        "not enough bars yet",
    "passed":           "the geometry passed",
}


def mins(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def bar_min(ts):
    t = ts[11:16] if "T" in ts else ts[:5]
    return mins(t)


def br_probe(candles, level, is_long):
    """One detect_break_retest call, with the funnel read as a delta so the
    answer is this call's terminal stage and nothing else."""
    before = dict(ob.BR_FUNNEL)
    out = {}
    note = ob.detect_break_retest(candles, level, is_long=is_long, out=out,
                                  retest_tol_mult=sr._retest_tol())
    stage = None
    for k in BR_STAGES:
        if ob.BR_FUNNEL.get(k, 0) - before.get(k, 0) > 0:
            stage = k
            break
    if note:
        stage = "passed"
    return stage, note


def strong_pa(candles, is_long):
    cur = candles[-1]
    prior = candles[-11:-1]
    avg_body = (sum(c.body_size for c in prior) / len(prior)) if prior else 0.0
    ratio = (cur.body_size / avg_body) if avg_body > 0 else float("inf")
    dir_ok = cur.is_bullish if is_long else cur.is_bearish
    return {"dir_ok": bool(dir_ok), "body_ratio": round(ratio, 2),
            "needs": sr.STRONG_PA_MULT,
            "strong": bool(dir_ok and ratio >= sr.STRONG_PA_MULT)}


def walk_one(symbol, day, his_min, claimed_level):
    candles = rth_candles(symbol, day)
    if not candles:
        return {"error": "no archived bars"}
    idx = None
    for i, c in enumerate(candles):
        if bar_min(c.timestamp) == his_min:
            idx = i
            break
    if idx is None:
        return {"error": "his minute is not an archived bar (%s)" % his_min}

    win = candles[: idx + 1]
    cur = win[-1]
    pdh, pdl, _pdo, _pdc = prior_day_levels(symbol, day)
    pmh, pml = premarket_extremes(symbol, day)
    orh, orl = sr.OpeningRangeAnalyzer.get_opening_range(win)

    named = {"PDH": pdh, "PDL": pdl, "PMH": pmh, "PML": pml,
             "ORH": orh, "ORL": orl}
    named = {k: v for k, v in named.items() if v is not None}

    # pivots, exactly as detect_signals builds them
    active = [v for v in named.values()]
    pivots = {}
    if sr.PIVOT_LEVELS:
        for p in sr.pivot_levels(win, as_of=len(win) - 1,
                                 lookback=sr.PIVOT_LOOKBACK):
            if any(abs(p["price"] - l) <= sr.PIVOT_DEDUPE_FRAC * abs(l)
                   for l in active if l):
                continue
            pivots[p["name"]] = p["price"]

    rows = []
    for name, lv in list(named.items()) + list(pivots.items()):
        for is_long in (True, False):
            stage, note = br_probe(win, lv, is_long)
            rows.append({
                "level": name, "price": round(lv, 4),
                "dir": "call" if is_long else "put",
                "is_named_level": name in named,
                "dist_pct": round(100.0 * (cur.close - lv) / lv, 3),
                "br_stage": stage,
                "br_plain": PLAIN.get(stage, stage),
                "fired": stage == "passed",
            })

    ocr = {}
    for d, is_long in (("bullish", True), ("bearish", False)):
        o = {}
        block, retest, note = ob.detect_order_block_setup(win, direction=d, out=o)
        rec = {"note": note, "retest_type": retest, "found": block is not None}
        if block is not None and o:
            q = ob.ocr_quality(win, block, o["block_idx"], o["break_idx"], d)
            rec["quality"] = {k: v for k, v in q.items()}
            rec["his_clauses_all_true"] = ob.ocr_is_his(
                win, block, o["block_idx"], o["break_idx"], d)
        ocr["call" if is_long else "put"] = rec

    passing = [r for r in rows if r["fired"]]
    # the closest thing to a signal: the stage each level died at, ranked by how
    # deep into the sequence it got
    depth = {"too_short": 0, "no_confirm_close": 1, "adverse_wick": 1,
             "no_break": 2, "no_leave": 3, "no_retest": 4, "stale_retest": 5,
             "passed": 6}
    deepest = max(rows, key=lambda r: depth.get(r["br_stage"], 0)) if rows else None

    return {
        "symbol": symbol, "day": day, "his_minute": his_min, "bar_index": idx,
        "bar": {"o": cur.open, "h": cur.high, "l": cur.low, "c": cur.close,
                "body": round(cur.body_size, 4),
                "upper_wick": round(cur.upper_wick, 4),
                "lower_wick": round(cur.lower_wick, 4)},
        "claimed_level": claimed_level,
        "claimed_level_price": named.get(claimed_level),
        "claimed_level_dist_pct": (
            round(100.0 * (cur.close - named[claimed_level]) / named[claimed_level], 3)
            if claimed_level in named else None),
        "levels_named": {k: round(v, 4) for k, v in named.items()},
        "n_pivot_levels": len(pivots),
        "strong_pa_call": strong_pa(win, True),
        "strong_pa_put": strong_pa(win, False),
        "br": rows,
        "br_any_passed": bool(passing),
        "br_deepest_stage": deepest["br_stage"] if deepest else None,
        "br_deepest_level": deepest["level"] if deepest else None,
        "br_deepest_plain": PLAIN.get(deepest["br_stage"]) if deepest else None,
        "br_stage_counts": dict(Counter(r["br_stage"] for r in rows)),
        "br_stage_counts_named_levels_only": dict(Counter(
            r["br_stage"] for r in rows if r["is_named_level"])),
        "ocr": ocr,
    }


def main():
    m = json.load(open(MEASURE, encoding="utf-8"))
    todo = [r for r in m["sample_A_rows"] if r.get("verdict") == "SILENT"]
    todo_b = [r for r in m["sample_B_rows"] if r.get("verdict") == "SILENT"]

    res = {"what": "what the engine was missing at the minute Austin named",
           "shipped_constants": {
               "retest_tol_mult": sr._retest_tol(),
               "BAR_EXTREME_FRAC": sr.BAR_EXTREME_FRAC,
               "STRONG_PA_MULT": sr.STRONG_PA_MULT,
               "PIVOT_LEVELS": sr.PIVOT_LEVELS,
               "HODLOD_PAIR": sr.HODLOD_PAIR,
           }}

    for label, rows in (("sample_A", todo), ("sample_B", todo_b)):
        walked = []
        for r in rows:
            his = mins(r["his_times"][0]) if r.get("his_times") else None
            if his is None:
                # sample B rows carry the raw minute only
                his = r.get("his_minute")
            w = walk_one(r["symbol"], r["date"], his, r.get("claimed_level"))
            w["card_id"] = r["card_id"]
            w["is_s"] = r["is_s"]
            w["bucket"] = r.get("bucket")
            w["note"] = r.get("note")
            walked.append(w)
            print("%-18s %-5s  deepest=%-16s (%s)  ocr call=%s | put=%s"
                  % (r["card_id"], r.get("his_times", [None])[0] or his,
                     w.get("br_deepest_stage"), w.get("br_deepest_level"),
                     (w.get("ocr", {}).get("call", {}).get("note") or "")[:34],
                     (w.get("ocr", {}).get("put", {}).get("note") or "")[:34]),
                  flush=True)
        res[label] = walked

        agg = Counter()
        agg_named = Counter()
        for w in walked:
            if "error" in w:
                agg["no_bars_or_no_such_bar"] += 1
                continue
            agg[w["br_deepest_stage"]] += 1
            named = w["br_stage_counts_named_levels_only"]
            best = max(named, key=lambda k: {"too_short": 0, "no_confirm_close": 1,
                                             "adverse_wick": 1, "no_break": 2,
                                             "no_leave": 3, "no_retest": 4,
                                             "stale_retest": 5,
                                             "passed": 6}.get(k, 0)) if named else None
            agg_named[best] += 1
        res[label + "_reasons_any_level"] = dict(agg)
        res[label + "_reasons_his_six_levels_only"] = dict(agg_named)

        ocr_notes = Counter()
        for w in walked:
            for side in ("call", "put"):
                n = (w.get("ocr", {}).get(side) or {}).get("note")
                if n:
                    ocr_notes[n] += 1
        res[label + "_ocr_notes"] = dict(ocr_notes)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)

    print("\n" + "=" * 72)
    for label in ("sample_A", "sample_B"):
        print("\n%s -- how far the break-and-retest sequence got, deepest of all "
              "levels" % label)
        for k, v in sorted(res[label + "_reasons_any_level"].items(),
                           key=lambda kv: -kv[1]):
            print("  %-18s %2d   %s" % (k, v, PLAIN.get(k, "")))
        print("  ...restricted to HIS six levels only:")
        for k, v in sorted(res[label + "_reasons_his_six_levels_only"].items(),
                           key=lambda kv: -kv[1]):
            print("  %-18s %2d" % (k, v))
        print("  one-candle rule, why no order block:")
        for k, v in sorted(res[label + "_ocr_notes"].items(), key=lambda kv: -kv[1]):
            print("  %2d  %s" % (v, k))
    print("\nwrote %s" % OUT)


if __name__ == "__main__":
    main()
