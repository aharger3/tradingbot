"""g99_adv_recheck2.py -- round 2 of the adversarial recheck of g99 entry_timing.

Round 1 (research/g99_adv_recheck.py) reproduced the sweep's numbers exactly and
found three measurement defects (D1 target anchor, D2 lookahead stop, D3 mixed
stop ruler). Round 2 tests the two that decide whether variant 5 survives:

 D5 OFF-BY-ONE ON THE FILL BAR.  resim_from() walks from fill_i+1. For the
    SHIPPED variant that is correct -- the fill IS the bar close, the bar is
    over. Variants 4 and 5 fill INTRABAR, so the REST of the fill bar is live
    and can take the stop out. Skipping it can only help the trade. Under the
    sweep's own stop (the fill bar's own extreme) the defect is invisible
    because that stop cannot be hit on its own bar; the moment the stop is
    made causal (D2), the defect starts paying. Fix: on the fill bar, if the
    bar's own extreme is beyond the stop, take the stop (ties to the stop,
    per the within-bar-ordering rule).

 D6 SELECTION LOOKAHEAD -- the one that matters.  Variant 5 fills at the
    level "the instant entry_i's own bar range contains it", and calls that
    causal because the level pre-existed. But the POPULATION is every row the
    book recorded as a CONFIRMED retest, and confirmation is decided by the
    CLOSE of bar entry_i -- after the touch. A limit resting at that level in
    real time fills on the FIRST touch of the day, confirmed or not. The
    sweep counts only the touches that went on to confirm. Test: same level,
    same day, same direction, but fill at the FIRST bar of the session whose
    range contains level_px (limit truly resting from the open, cutoff
    11:00). If EV/R collapses, variant 5's edge is the selection, not the
    entry.

Usage:  python research/g99_adv_recheck2.py
Writes: research/g99_adv_recheck2.json
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
from research.g99_adv_recheck import bars_for, stop_asis, stop_causal, slim

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT = ROOT / "research" / "g99_adv_recheck2.json"


def resim2(row, bars, fill_i, entry_px, stop, target_mode, stop_mode, check_fill_bar):
    """Same control ladder as round 1, plus D5: the fill bar's own remainder."""
    long = row["dir"] == "call"
    if stop is None:
        return None, "no_causal_stop"
    risk = abs(entry_px - stop)
    if risk <= 0:
        return None, "zero_risk"
    target = (row["target"] if target_mode == "asis"
              else (entry_px + 2.0 * risk if long else entry_px - 2.0 * risk))
    n = len(bars)
    if fill_i + 1 >= n:
        return None, "no_management_bars"
    if check_fill_bar:
        fb = bars[fill_i]
        if (fb.low <= stop) if long else (fb.high >= stop):
            return -1.0, "stop_on_fill_bar"
    for j in range(fill_i + 1, n):
        c = bars[j]
        hit = ((c.close <= stop) if long else (c.close >= stop)) if stop_mode == "close" \
            else ((c.low <= stop) if long else (c.high >= stop))
        if hit:
            return -1.0, "stop"
        if (c.high >= target) if long else (c.low <= target):
            r = (target - entry_px) / risk if long else (entry_px - target) / risk
            return r, "target"
    last = bars[-1].close
    return ((last - entry_px) / risk if long else (entry_px - last) / risk), "eod"


def cutoff_idx(bars):
    for j, c in enumerate(bars):
        if c.timestamp >= "11:00:00":
            return j
    return len(bars)


def fill_v5(row, bars):
    i = row["entry_i"]
    if i >= len(bars):
        return None, None
    c, level = bars[i], row["level_px"]
    return (i, level) if c.low <= level <= c.high else (None, None)


def fill_v5_honest(row, bars):
    """D6: a limit truly resting at the level from the open -- FIRST touch."""
    level = row["level_px"]
    for j in range(0, min(cutoff_idx(bars), row["entry_i"] + 1)):
        c = bars[j]
        if c.low <= level <= c.high:
            return j, level
    return None, None


def fill_v4(row, bars):
    i, level = row["entry_i"], row["level_px"]
    long = row["dir"] == "call"
    for j in range(i + 1, cutoff_idx(bars)):
        c = bars[j]
        if long and c.low <= level:
            return j, min(level, c.open)
        if (not long) and c.high >= level:
            return j, max(level, c.open)
    return None, None


def run(rows, filler, stop_fn, target_mode, stop_mode, check_fill_bar):
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
        rr, why = resim2(r, bars, fi, px, st, target_mode, stop_mode, check_fill_bar)
        if rr is None:
            fails[why] += 1
            continue
        out.append({"r": rr, "day": r["day"], "entry": px, "stop": st, "why": why,
                    "lag": r["entry_i"] - fi})
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
    print("floor src=%s\n" % MIN_RISK_FLOOR_SOURCE)
    res = {"sessions": sessions, "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE, "arms": {}}

    ARMS = [
        # name,                  filler,         stop,        target, stopmode, fillbar
        ("v5|D2+D5", fill_v5, stop_causal, "asis", "close", True),
        ("v5|D2+D3+D5", fill_v5, stop_causal, "asis", "touch", True),
        ("v5|D1+D2+D3+D5_ALL", fill_v5, stop_causal, "2R", "touch", True),
        ("v5|D1+D2+D5", fill_v5, stop_causal, "2R", "close", True),
        ("v5|sweep_stop+D5", fill_v5, stop_asis, "asis", "close", True),
        ("v5HONEST|D1+D2+D3+D5", fill_v5_honest, stop_causal, "2R", "touch", True),
        ("v5HONEST|sweeplike", fill_v5_honest, stop_asis, "asis", "close", False),
        ("v4|D1+D2+D3+D5_ALL", fill_v4, stop_causal, "2R", "touch", True),
        ("v4|D2+D5", fill_v4, stop_causal, "asis", "close", True),
    ]
    for pop, rows in (("A_first", firsts), ("B_traded", traded)):
        for name, fl, sf, tm, sm, cfb in ARMS:
            rr, fails = run(rows, fl, sf, tm, sm, cfb)
            sb = ev_r_scoreboard(rr, sessions=sessions)
            key = "%s|%s" % (pop, name)
            lags = defaultdict(int)
            for x in rr:
                lags[x["lag"]] += 1
            res["arms"][key] = {"scoreboard": slim(sb), "drop_reasons": fails,
                                "prop": props(rr) if rr else None,
                                "years": yearsplit(rr, sessions) if rr else None,
                                "exit_reasons": dict(defaultdict(int, {
                                    w: sum(1 for x in rr if x["why"] == w)
                                    for w in {x["why"] for x in rr}})),
                                "bars_earlier_than_signal": dict(sorted(lags.items()))}
            print("%-34s ev_r=%-8s n=%-5s win=%-7s mg=%-6s pf=%s"
                  % (key, sb["ev_r"], sb["n"], sb["win_rate"], sb["months_green"],
                     sb["profit_factor"]))
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
