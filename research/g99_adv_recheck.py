"""g99_adv_recheck.py -- ADVERSARIAL recheck of the entry_timing sweep (g99).

Refutation target: research/g99_entry_timing_sweep.py's claim that variants
4 (resting limit after the signal bar) and 5 (retest-touch on the signal bar)
are causal, shippable arms worth ev_r 0.60 / 2.15 on POP A.

Four defects are tested one at a time, then together:

 D1 TARGET IS NOT A LEVEL.  The sweep docstring says row['target'] is
    "PT1 = HOD/LOD, unchanged". It is not. Measured on the book: 2,724 of
    4,022 traded rows have |target-entry|/|entry-stop| == 2.00 exactly and
    the whole distribution sits on 2.0 +/- 0.03. `target` is 2R FROM THE
    ORIGINAL ENTRY. Moving the entry to a better price therefore inflates
    the R numerator mechanically, because the target price does not move
    with it. Correction: re-anchor the target to 2R from the NEW entry,
    which is the book's own target rule.

 D2 THE STOP IS LOOKAHEAD FOR AN INTRABAR FILL.  effective_stop() puts the
    stop on the FILL BAR's own low/high. In the shipped engine that is
    legal -- the shipped fill is the bar CLOSE, so the bar is complete and
    its extreme is printed. Variants 4 and 5 fill INTRABAR, mid-bar, so the
    bar's eventual extreme is not knowable at fill time, and a stop placed
    there can never be hit on the fill bar by construction. Correction:
    place the stop on the PREVIOUS bar's extreme (printed, placeable), and
    drop the row when that is not beyond the entry.

 D3 THE STOP UNIT DIFFERS FROM VARIANT 1's.  Variant 1 is the book's own
    row['r'], and the book's stops fill on a WICK at the level at exactly
    -1.000R (backtest_week.DISASTER_STOP=True, DISASTER_R=1.0 -- see
    research/MASTER_SPEC.md section 1). The control ladder used for 4/5
    triggers the stop on the CLOSE, which is strictly more forgiving.
    Comparing 4/5 against 1 is comparing two rulers. Correction: stop on
    intrabar touch, the book's own ruler.

 D4 OVERFIT / DURABILITY.  Year-1 (2024-09..2025-08) vs year-2 splits.

Usage:  python research/g99_adv_recheck.py
Writes: research/g99_adv_recheck.json
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import polygon_feed as pf
from research.omen_metrics import (ev_r_scoreboard, evaluate_prop_challenge,
                                   MIN_RISK_FLOOR_SOURCE, first_of_day_arm)

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT = ROOT / "research" / "g99_adv_recheck.json"
_bc = {}


def bars_for(sym, day):
    k = (sym, day)
    if k not in _bc:
        if len(_bc) > 900:
            _bc.clear()
        try:
            _bc[k] = pf.rth(pf.fetch_day(sym, day))
        except Exception:
            _bc[k] = []
    return _bc[k]


def stop_asis(row, bars, fill_i, entry_px):
    """the sweep effective_stop(), verbatim -- fill bar own extreme"""
    long = row["dir"] == "call"
    stop = row["stop"]
    if abs(stop - row["level_px"]) < 0.005 and abs(entry_px - stop) < 0.005:
        fb = bars[fill_i]
        return fb.low if long else fb.high
    return stop


def stop_causal(row, bars, fill_i, entry_px):
    """D2 fix: the PREVIOUS bar extreme -- printed before the fill."""
    long = row["dir"] == "call"
    stop = row["stop"]
    if abs(stop - row["level_px"]) < 0.005 and abs(entry_px - stop) < 0.005:
        if fill_i - 1 < 0:
            return None
        pb = bars[fill_i - 1]
        cand = pb.low if long else pb.high
        if (cand < entry_px) if long else (cand > entry_px):
            return cand
        return None
    return stop


def resim(row, bars, fill_i, entry_px, stop, target_mode, stop_mode):
    long = row["dir"] == "call"
    if stop is None:
        return None, "no_causal_stop"
    risk = abs(entry_px - stop)
    if risk <= 0:
        return None, "zero_risk"
    if target_mode == "asis":
        target = row["target"]
    else:  # D1 fix: 2R from the NEW entry, the book own target rule
        target = entry_px + 2.0 * risk if long else entry_px - 2.0 * risk
    n = len(bars)
    if fill_i + 1 >= n:
        return None, "no_management_bars"
    for j in range(fill_i + 1, n):
        c = bars[j]
        if stop_mode == "close":
            hit = (c.close <= stop) if long else (c.close >= stop)
        else:  # D3: intrabar touch, the book own ruler
            hit = (c.low <= stop) if long else (c.high >= stop)
        if hit:
            return -1.0, "stop"
        tgt = (c.high >= target) if long else (c.low <= target)
        if tgt:
            r = (target - entry_px) / risk if long else (entry_px - target) / risk
            return r, "target"
    last = bars[-1].close
    r = (last - entry_px) / risk if long else (entry_px - last) / risk
    return r, "eod"


def fill_v4(row, bars):
    i, level = row["entry_i"], row["level_px"]
    long = row["dir"] == "call"
    cut = len(bars)
    for j, c in enumerate(bars):
        if c.timestamp >= "11:00:00":
            cut = j
            break
    for j in range(i + 1, cut):
        c = bars[j]
        if long and c.low <= level:
            return j, min(level, c.open)
        if (not long) and c.high >= level:
            return j, max(level, c.open)
    return None, None


def fill_v5(row, bars):
    i = row["entry_i"]
    if i >= len(bars):
        return None, None
    c, level = bars[i], row["level_px"]
    if not (c.low <= level <= c.high):
        return None, None
    return i, level


def run(rows, filler, stop_fn, target_mode, stop_mode):
    out, fails = [], defaultdict(int)
    for r in rows:
        bars = bars_for(r["sym"], r["day"])
        if not bars:
            fails["no_bars"] += 1
            continue
        fi, px = filler(r, bars)
        if fi is None:
            fails["no_fill"] += 1
            continue
        st = stop_fn(r, bars, fi, px)
        rr, why = resim(r, bars, fi, px, st, target_mode, stop_mode)
        if rr is None:
            fails[why] += 1
            continue
        out.append({"r": rr, "day": r["day"], "entry": px, "stop": st, "why": why})
    return out, dict(fails)


def props(rows_r):
    by = defaultdict(float)
    for r in rows_r:
        by[r["day"]] += r["r"] * 1000.0
    daily = [(d, by[d]) for d in sorted(by)]
    o = {}
    for risk in (100, 250, 500, 1000):
        sc = [(d, v * risk / 1000.0) for d, v in daily]
        res = evaluate_prop_challenge(sc, account_size=50000.0)
        o[str(risk)] = {"passed": res["passed"], "fail_reason": res["fail_reason"]}
    return o


def slim(sb):
    return {k: sb[k] for k in ("ev_r", "n", "n_input", "n_dropped_size_gate", "win_rate",
                               "avg_win_R", "avg_loss_R", "profit_factor", "total_R",
                               "months_green", "expectancy_per_day", "yearly_R")}


def yearsplit(rows_r, sessions):
    y1 = [r for r in rows_r if r["day"] < "2025-09-01"]
    y2 = [r for r in rows_r if r["day"] >= "2025-09-01"]
    return {"y1": slim(ev_r_scoreboard(y1, sessions=sessions // 2)),
            "y2": slim(ev_r_scoreboard(y2, sessions=sessions // 2))}


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, allr = blob["meta"], blob["trades"]
    sessions = meta["sessions"]
    traded = [r for r in allr if r["status"] == "fired" and r.get("traded")]
    firsts = first_of_day_arm(allr)
    print("book %d sessions, %d traded, %d firsts; floor src=%s"
          % (sessions, len(traded), len(firsts), MIN_RISK_FLOOR_SOURCE))

    res = {"sessions": sessions, "n_traded": len(traded), "n_firsts": len(firsts),
           "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE, "arms": {}}

    for pop, rows in (("A_first", firsts), ("B_traded", traded)):
        v1 = [{"r": r["r"], "day": r["day"], "entry": r["entry"], "stop": r["stop"]}
              for r in rows]
        sb = ev_r_scoreboard(v1, sessions=sessions)
        res["arms"]["%s|v1_shipped" % pop] = {"scoreboard": slim(sb), "prop": props(v1),
                                              "years": yearsplit(v1, sessions)}
        print("%s v1_shipped ev_r=%.4f n=%d" % (pop, sb["ev_r"], sb["n"]))

    GRID = [
        ("asis_asis_close", stop_asis, "asis", "close"),      # the sweep, verbatim
        ("D1_target2R", stop_asis, "2R", "close"),            # D1 only
        ("D2_causalstop", stop_causal, "asis", "close"),      # D2 only
        ("D3_stoptouch", stop_asis, "asis", "touch"),         # D3 only
        ("D123_all", stop_causal, "2R", "touch"),             # all three
    ]
    for pop, rows in (("A_first", firsts), ("B_traded", traded)):
        for vname, filler in (("v4_resting", fill_v4), ("v5_retest", fill_v5)):
            for gname, sfn, tm, sm in GRID:
                rr, fails = run(rows, filler, sfn, tm, sm)
                sb = ev_r_scoreboard(rr, sessions=sessions)
                key = "%s|%s|%s" % (pop, vname, gname)
                res["arms"][key] = {"scoreboard": slim(sb), "drop_reasons": fails,
                                    "prop": props(rr) if rr else None,
                                    "years": yearsplit(rr, sessions) if rr else None}
                print("%-40s ev_r=%s n=%s win=%s mg=%s" %
                      (key, sb["ev_r"], sb["n"], sb["win_rate"], sb["months_green"]))

    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
