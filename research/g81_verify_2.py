"""g81_verify_2.py -- independent adversarial recompute of research/g81_mentor_timing.md.

Rebuilds, from scratch and without importing g81_mentor_timing.py, the three
largest published numbers:

  A. join yield          2,597 of 3,547 (73.2%)
  B. same-side fire rate  594 of 1,962 (30.3%)   [and in-window 295 of 849]
  C. opposite-only rate   313 of 907  (34.5%)
  D. signed timing        n=295, median 0

and additionally re-expresses B and C on DISTINCT SYMBOL-DAYS, because the
pool holds 3,547 rows over only 2,915 distinct symbol-days -- the published
headline calls the q5 denominators "symbol-days" but the script counts rows.

    python research/g81_verify_2.py [--limit N] [--out research/g81_verify_2.json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import statistics
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)

import t4_engine_recall as t4            # noqa: E402
import backtest_week as bw               # noqa: E402
import levels                            # noqa: E402
from universe import ALL_SYMS            # noqa: E402

POOL = os.path.join(HERE, "corpus_sf", "pooled_trades.jsonl")
LO, HI = 570, 660


def mins(hhmm):
    return int(hhmm[:2]) * 60 + int(hhmm[3:5])


def weekday(d):
    y, m, dd = (int(x) for x in d.split("-"))
    return datetime.date(y, m, dd).weekday() < 5


def summarize(v):
    if not v:
        return None
    s = sorted(v)
    return {"n": len(s), "median": statistics.median(s),
            "mean": round(statistics.mean(s), 2), "min": s[0], "max": s[-1],
            "neg": sum(1 for x in s if x < 0), "zero": sum(1 for x in s if x == 0),
            "pos": sum(1 for x in s if x > 0),
            "within10": sum(1 for x in s if abs(x) <= 10)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "g81_verify_2.json"))
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(POOL, encoding="utf-8") if l.strip()]
    n_total = len(rows)

    wk = [r for r in rows if weekday(r["trade_date"])]
    uni = [r for r in wk if r["symbol"] in ALL_SYMS]
    pairs_uni = sorted({(r["symbol"], r["trade_date"]) for r in uni})
    with_bars = {p for p in pairs_uni
                 if os.path.exists(os.path.join(levels.ARCHIVE, p[0], "%s.csv" % p[1]))}
    joined = [r for r in uni if (r["symbol"], r["trade_date"]) in with_bars]

    funnel = {
        "pool_rows": n_total,
        "weekend_dropped": n_total - len(wk),
        "after_weekday": len(wk),
        "after_universe": len(uni),
        "distinct_symdays_after_universe": len(pairs_uni),
        "distinct_symdays_with_bars": len(with_bars),
        "joined_rows": len(joined),
        "join_yield_pct": round(len(joined) / n_total * 100, 1),
        "joined_rows_posted_in_window": sum(
            1 for r in joined if r["et_minute"] is not None and LO <= r["et_minute"] <= HI),
    }
    print(json.dumps(funnel, indent=2))

    pairs = sorted({(r["symbol"], r["trade_date"]) for r in joined})
    if a.limit:
        pairs = pairs[:a.limit]
        keep = set(pairs)
        joined = [r for r in joined if (r["symbol"], r["trade_date"]) in keep]

    t0 = time.time()
    eng = {}
    for i, (sym, day) in enumerate(pairs, 1):
        candles = t4.rth_candles(sym, day)
        if not candles:
            eng[(sym, day)] = {"fired": {}, "booked": {}}
            continue
        entries, _all, _raw = t4.run_day(sym, day)
        pdh, pdl, pdo, pdc = t4.prior_day_levels(sym, day)
        pmh, pml = t4.premarket_extremes(sym, day)
        bias = t4.htf_bias(sym, day)
        trades = bw.simulate_day(sym, day, candles, pdh, pdl, bias, pmh, pml,
                                 pdo, pdc, qqq=None)
        f = defaultdict(list)
        for e in (entries or []):
            f[e["direction"]].append(mins(e["timestamp"]))
        b = defaultdict(list)
        for t in trades:
            if t.counted:
                b[t.direction].append(mins(t.entry_time))
        eng[(sym, day)] = {"fired": dict(f), "booked": dict(b)}
        if i % 250 == 0:
            print("  %d/%d  %.0fs" % (i, len(pairs), time.time() - t0))

    D = {"long": "call", "short": "put"}

    with_dir = [r for r in joined if r.get("direction") in D]
    same_fired = same_booked = 0
    iw_n = iw_same = iw_booked = 0
    cases = {"same_only": 0, "opp_only": 0, "both": 0, "silent": 0}
    deltas_fire, deltas_book = [], []
    # symbol-day level views
    sd_dirs = defaultdict(set)
    for r in with_dir:
        sd_dirs[(r["symbol"], r["trade_date"])].add(D[r["direction"]])

    for r in with_dir:
        e = eng[(r["symbol"], r["trade_date"])]
        d = D[r["direction"]]
        opp = "put" if d == "call" else "call"
        sm = e["fired"].get(d, [])
        om = e["fired"].get(opp, [])
        bm = e["booked"].get(d, [])
        if sm:
            same_fired += 1
        if bm:
            same_booked += 1
        if sm and om:
            cases["both"] += 1
        elif sm:
            cases["same_only"] += 1
        elif om:
            cases["opp_only"] += 1
        else:
            cases["silent"] += 1
        et = r["et_minute"]
        inw = et is not None and LO <= et <= HI
        if inw:
            iw_n += 1
            if sm:
                iw_same += 1
                deltas_fire.append(min(sm) - et)
            if bm:
                iw_booked += 1
                deltas_book.append(min(bm) - et)

    any_sig = cases["same_only"] + cases["opp_only"] + cases["both"]

    # --- same thing, deduplicated to distinct symbol-days ---
    sd_cases = {"same_only": 0, "opp_only": 0, "both": 0, "silent": 0}
    for (sym, day), dirs in sd_dirs.items():
        e = eng[(sym, day)]
        fired = {k for k, v in e["fired"].items() if v}
        same = bool(fired & dirs)
        opp = bool(fired - dirs)
        if same and opp:
            sd_cases["both"] += 1
        elif same:
            sd_cases["same_only"] += 1
        elif opp:
            sd_cases["opp_only"] += 1
        else:
            sd_cases["silent"] += 1
    sd_any = sd_cases["same_only"] + sd_cases["opp_only"] + sd_cases["both"]

    out = {
        "funnel": funnel,
        "n_with_stated_direction": len(with_dir),
        "B_same_side_fired": same_fired,
        "B_same_side_pct": round(same_fired / len(with_dir) * 100, 1),
        "B_same_side_booked": same_booked,
        "B_in_window_n": iw_n,
        "B_in_window_same_fired": iw_same,
        "B_in_window_pct": round(iw_same / max(1, iw_n) * 100, 1),
        "B_in_window_same_booked": iw_booked,
        "C_row_cases": cases,
        "C_row_any_signal": any_sig,
        "C_opp_only_pct_rows": round(cases["opp_only"] / max(1, any_sig) * 100, 1),
        "C_symbolday_cases": sd_cases,
        "C_symbolday_any_signal": sd_any,
        "C_opp_only_pct_symboldays": round(sd_cases["opp_only"] / max(1, sd_any) * 100, 1),
        "C_distinct_symdays_with_stated_dir": len(sd_dirs),
        "D_first_fire_minus_post": summarize(deltas_fire),
        "D_first_booked_minus_post": summarize(deltas_book),
    }
    print(json.dumps(out, indent=2, default=str))
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, default=str)
    print("wrote %s" % a.out)


if __name__ == "__main__":
    main()
