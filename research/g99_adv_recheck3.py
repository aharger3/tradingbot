"""g99_adv_recheck3.py -- round 3: the decisive test on g99's variant 5.

Round 2 showed variant 5's edge survives the target/stop/ruler corrections
but evaporates when the limit is allowed to rest from the open. Round 3
isolates WHY, with a lookback-window decay curve, and hand-checks three
individual trades against the raw bars.

THE DECAY TEST.  Variant 5 fills at the level on bar entry_i -- the bar whose
CLOSE confirms the retest. A limit order does not know that. Let the same
limit rest for K bars before entry_i and take the FIRST touch in
[entry_i-K, entry_i]. K=0 IS the sweep's variant 5. If the edge is in the
ENTRY (a good price at a real level), EV/R should be roughly flat in K --
the same level, the same price, a slightly earlier clock. If the edge is in
the SELECTION (only counting the touches that went on to confirm on bar
entry_i), EV/R must fall as K grows, because larger K admits the touches
that did not confirm.

Ladder held identical across every K: causal stop (previous bar's extreme),
target 2R from the fill, stop on intrabar touch, fill bar's own remainder
checked (D1+D2+D3+D5 from rounds 1-2). Size-gated on
signal_runner.min_risk_floor throughout.

Usage:  python research/g99_adv_recheck3.py
Writes: research/g99_adv_recheck3.json
"""
from __future__ import annotations
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from research.omen_metrics import (ev_r_scoreboard, evaluate_prop_challenge,
                                   MIN_RISK_FLOOR_SOURCE, first_of_day_arm)
from research.g99_adv_recheck import bars_for, stop_causal, slim
from research.g99_adv_recheck2 import resim2

BOOK = ROOT / "research" / "bt2y_trades_retest_on.json"
OUT = ROOT / "research" / "g99_adv_recheck3.json"


def fill_within_k(row, bars, k):
    """First bar in [entry_i-k, entry_i] whose range contains the level."""
    i, level = row["entry_i"], row["level_px"]
    if i >= len(bars):
        return None, None
    for j in range(max(0, i - k), i + 1):
        c = bars[j]
        if c.low <= level <= c.high:
            return j, level
    return None, None


def run_k(rows, k, sessions):
    out, fails = [], defaultdict(int)
    for r in rows:
        bars = bars_for(r["sym"], r["day"])
        if not bars:
            fails["no_bars"] += 1
            continue
        fi, px = fill_within_k(r, bars, k)
        if fi is None:
            fails["no_fill"] += 1
            continue
        st = stop_causal(r, bars, fi, px)
        rr, why = resim2(r, bars, fi, px, st, "2R", "touch", True)
        if rr is None:
            fails[why] += 1
            continue
        out.append({"r": rr, "day": r["day"], "entry": px, "stop": st,
                    "why": why, "lag": r["entry_i"] - fi})
    sb = ev_r_scoreboard(out, sessions=sessions)
    by = defaultdict(float)
    for x in out:
        by[x["day"]] += x["r"] * 1000.0
    daily = [(d, by[d]) for d in sorted(by)]
    prop = {}
    for risk in (100, 250, 500, 1000):
        res = evaluate_prop_challenge([(d, v * risk / 1000.0) for d, v in daily],
                                      account_size=50000.0)
        prop[str(risk)] = {"passed": res["passed"], "fail_reason": res["fail_reason"],
                           "final_equity_pct": res["final_equity_pct"]}
    y1 = [x for x in out if x["day"] < "2025-09-01"]
    y2 = [x for x in out if x["day"] >= "2025-09-01"]
    lags = defaultdict(int)
    for x in out:
        lags[x["lag"]] += 1
    return {"k": k, "scoreboard": slim(sb), "drop_reasons": dict(fails), "prop": prop,
            "y1_ev_r": ev_r_scoreboard(y1, sessions=sessions // 2)["ev_r"], "y1_n": len(y1),
            "y2_ev_r": ev_r_scoreboard(y2, sessions=sessions // 2)["ev_r"], "y2_n": len(y2),
            "lag_hist": dict(sorted(lags.items()))}


def handcheck(rows, n=3):
    """Print the raw bars behind the first n variant-5 fills, so the numbers
    can be recomputed by eye rather than trusted."""
    shown = []
    for r in rows:
        if len(shown) >= n:
            break
        bars = bars_for(r["sym"], r["day"])
        if not bars:
            continue
        i, level = r["entry_i"], r["level_px"]
        if i >= len(bars):
            continue
        c = bars[i]
        if not (c.low <= level <= c.high):
            continue
        long = r["dir"] == "call"
        sweep_stop = c.low if long else c.high
        causal_stop = bars[i - 1].low if long else bars[i - 1].high
        d = {
            "sym": r["sym"], "day": r["day"], "dir": r["dir"], "entry_i": i,
            "bar_prev": [bars[i-1].timestamp, bars[i-1].open, bars[i-1].high,
                         bars[i-1].low, bars[i-1].close],
            "bar_entry": [c.timestamp, c.open, c.high, c.low, c.close],
            "bar_next": [bars[i+1].timestamp, bars[i+1].open, bars[i+1].high,
                         bars[i+1].low, bars[i+1].close],
            "book_entry": r["entry"], "book_stop": r["stop"], "book_target": r["target"],
            "book_r": r["r"], "level_px": level,
            "book_risk": round(abs(r["entry"] - r["stop"]), 4),
            "book_target_R_from_book_entry":
                round(abs(r["target"] - r["entry"]) / abs(r["entry"] - r["stop"]), 3),
            "v5_entry": level,
            "v5_sweep_stop_fill_bar_extreme": sweep_stop,
            "v5_sweep_risk": round(abs(level - sweep_stop), 4),
            "v5_sweep_R_if_target_hit":
                (round(abs(r["target"] - level) / abs(level - sweep_stop), 3)
                 if abs(level - sweep_stop) > 1e-9 else None),
            "v5_causal_stop_prev_bar_extreme": causal_stop,
            "v5_causal_risk": round(abs(level - causal_stop), 4),
            "min_risk_floor_at_this_price": round(max(0.10, 0.0015 * level), 4),
            "sweep_stop_is_the_fill_bar_low_so_a_touch_rule_hits_it_immediately": True,
        }
        shown.append(d)
    return shown


def main():
    blob = json.load(open(BOOK, encoding="utf-8"))
    meta, allr = blob["meta"], blob["trades"]
    sessions = meta["sessions"]
    traded = [r for r in allr if r["status"] == "fired" and r.get("traded")]
    firsts = first_of_day_arm(allr)
    print("floor src=%s" % MIN_RISK_FLOOR_SOURCE)
    res = {"sessions": sessions, "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
           "decay": {}, "handcheck": handcheck(firsts, 3)}
    for pop, rows in (("A_first", firsts), ("B_traded", traded)):
        print("\n--- %s : lookback-K decay (identical ladder) ---" % pop)
        for k in (0, 1, 2, 3, 5, 10, 20, 60):
            d = run_k(rows, k, sessions)
            res["decay"]["%s|k=%d" % (pop, k)] = d
            sb = d["scoreboard"]
            print("k=%-3d ev_r=%-8s n=%-5s win=%-7s mg=%-6s pf=%-7s y1=%s y2=%s"
                  % (k, sb["ev_r"], sb["n"], sb["win_rate"], sb["months_green"],
                     sb["profit_factor"], d["y1_ev_r"], d["y2_ev_r"]))
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1)
    print("\nwrote", OUT)


if __name__ == "__main__":
    main()
