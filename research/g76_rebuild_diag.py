"""G76 — the mechanics behind the rebuilt numbers.

Answers, off the books `research/g76_rebuild_book.py` wrote:

  1. WHY the win rate collapses when the fill becomes obtainable — the risk
     geometry of each model (how far the stop is, how far the 2R target is).
  2. The resting limit in detail — how often it never fills, how long it waits,
     and whether a gap through the order can leave the fill on the wrong side
     of the stop.
  3. What time of day the one-trade-a-day trades happen under each model.
  4. How much of the published book survives into each model, trade for trade.

Usage:  python research/g76_rebuild_diag.py
Writes: research/g76_rebuild_diag.json
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research"))

from g72_suppress_price import load, shipped_rows, oneaday_rows  # noqa: E402

MODELS = ["head", "close", "next_open", "limit", "late1", "late2", "late5"]


def med(xs):
    return round(statistics.median(xs), 4) if xs else None


def main():
    out = {}
    books = {}
    for m in MODELS:
        p = ROOT / "research" / ("g76_book_%s.json" % m)
        if not p.exists():
            continue
        books[m] = load(p)

    # ---- 1. risk geometry --------------------------------------------------
    geom = {}
    for m, (meta, rows) in books.items():
        tr = shipped_rows(rows)
        risk = [abs(r["entry"] - r["stop"]) for r in tr]
        pct = [abs(r["entry"] - r["stop"]) / r["entry"] * 100 for r in tr if r["entry"]]
        tgt = [abs(r["target"] - r["entry"]) / r["entry"] * 100 for r in tr if r["entry"]]
        outs = Counter(r["out"] for r in tr)
        geom[m] = {
            "trades": len(tr),
            "median_risk_dollars": med(risk),
            "median_risk_pct_of_price": med(pct),
            "median_target_distance_pct": med(tgt),
            "pct_risk_under_10c": round(sum(1 for x in risk if x < 0.10) / len(risk) * 100, 1),
            "outcomes": dict(outs),
            "win_pct_of_all": round(outs.get("win", 0) / len(tr) * 100, 1),
        }
    out["geometry"] = geom

    # ---- 2. the resting limit ---------------------------------------------
    meta, rows = books["limit"]
    ordered = [r for r in rows if r.get("sig_status") == "fired" and r.get("grade") != "C"]
    filled = [r for r in ordered if r["status"] != "unfilled"]
    unf = [r for r in ordered if r["status"] == "unfilled"]
    lags = [r["lag"] for r in filled]
    inverted = [r for r in filled
                if (r["dir"] == "call" and r["entry"] <= r["stop"])
                or (r["dir"] == "put" and r["entry"] >= r["stop"])]
    same_bar = sum(1 for x in lags if x == 1)
    out["limit"] = {
        "orders_placed": len(ordered),
        "never_filled": len(unf),
        "never_filled_pct": round(len(unf) / len(ordered) * 100, 1),
        "lag_minutes": {
            "median": med(lags),
            "mean": round(statistics.fmean(lags), 2) if lags else None,
            "p90": round(statistics.quantiles(lags, n=10)[-1], 1) if len(lags) > 10 else None,
            "filled_next_minute_pct": round(same_bar / len(lags) * 100, 1) if lags else 0.0,
        },
        "gap_through_leaves_fill_past_stop": len(inverted),
        "unfilled_by_setup": dict(Counter(r["setup"] for r in unf)),
        "filled_by_setup": dict(Counter(r["setup"] for r in filled)),
    }
    # days on which the day's FIRST order never filled
    byday = {}
    for r in ordered:
        byday.setdefault(r["day"], []).append(r)
    firsts = [sorted(v, key=lambda r: (r["sig_et"], r["sym"]))[0] for v in byday.values()]
    out["limit"]["days_with_an_order"] = len(firsts)
    out["limit"]["days_first_order_never_filled"] = sum(
        1 for r in firsts if r["status"] == "unfilled")

    # ---- 3. time of day, one trade a day ----------------------------------
    tod = {}
    for m, (meta, rows) in books.items():
        rr = oneaday_rows(rows)
        before10 = sum(1 for r in rr if r["et"] < "10:00")
        tod[m] = {"n": len(rr), "before_10am": before10,
                  "before_10am_pct": round(before10 / len(rr) * 100, 1) if rr else 0.0,
                  "median_et": sorted(r["et"] for r in rr)[len(rr) // 2] if rr else None}
    out["time_of_day_one_a_day"] = tod

    # ---- 3b. how much of the trade was already won before it existed ------
    # The head book fills BELOW the close on a long. Its risk denominator is
    # the distance from that fill to the entry bar's own low. So at the very
    # instant the signal comes into existence -- the close of the signal bar --
    # the trade is already showing a profit, measured in R, that nobody paying
    # a visible price can have. This is the edge, in one number.
    import polygon_feed as pf
    cache = {}

    def bars(sym, day):
        k = (sym, day)
        if k not in cache:
            if len(cache) > 60:
                cache.clear()
            cache[k] = pf.rth(pf.fetch_day(sym, day))
        return cache[k]

    head_free = {}
    for m in ("head", "close", "limit"):
        if m not in books:
            continue
        tr = sorted(shipped_rows(books[m][1]), key=lambda r: (r["sym"], r["day"]))
        free = []
        for r in tr:
            b = bars(r["sym"], r["day"])
            i = r["sig_i"]
            if i >= len(b):
                continue
            risk = abs(r["entry"] - r["stop"])
            if risk <= 0:
                continue
            c = b[i].close
            free.append(((c - r["entry"]) if r["dir"] == "call" else (r["entry"] - c)) / risk)
        head_free[m] = {
            "n": len(free),
            "median_R_already_won_at_signal": med(free),
            "mean_R_already_won_at_signal": round(statistics.fmean(free), 3) if free else None,
            "pct_already_up_half_R": round(sum(1 for x in free if x >= 0.5) / len(free) * 100, 1)
            if free else 0.0,
            "pct_already_up_1R": round(sum(1 for x in free if x >= 1.0) / len(free) * 100, 1)
            if free else 0.0,
        }
    out["free_R_at_signal"] = head_free

    # ---- 4. survival of the published book --------------------------------
    def ident(r):
        return (r["sym"], r["day"], r["sig_et"], r["dir"], r["setup"])

    head_ids = {ident(r) for r in shipped_rows(books["head"][1])}
    surv = {}
    for m, (meta, rows) in books.items():
        if m == "head":
            continue
        ids = {ident(r) for r in shipped_rows(rows)}
        surv[m] = {"trades": len(ids), "shared_with_head": len(ids & head_ids),
                   "new": len(ids - head_ids), "lost_from_head": len(head_ids - ids),
                   "shared_pct_of_head": round(len(ids & head_ids) / len(head_ids) * 100, 1)}
    out["survival_vs_head"] = surv

    (ROOT / "research" / "g76_rebuild_diag.json").write_text(
        json.dumps(out, indent=2), encoding="utf-8")

    print("== risk geometry of the trades each model takes ==")
    print("  %-10s %6s %10s %9s %10s %8s %7s"
          % ("model", "n", "risk($)", "risk(%px)", "target(%px)", "<10c", "win%"))
    for m, g in geom.items():
        print("  %-10s %6d %10.3f %9.3f %10.3f %7.1f%% %6.1f%%"
              % (m, g["trades"], g["median_risk_dollars"], g["median_risk_pct_of_price"],
                 g["median_target_distance_pct"], g["pct_risk_under_10c"], g["win_pct_of_all"]))
    print()
    print("== the resting limit ==")
    L = out["limit"]
    print("  orders placed              %d" % L["orders_placed"])
    print("  never filled               %d  (%.1f%%)" % (L["never_filled"], L["never_filled_pct"]))
    print("  filled on the very next minute  %.1f%%" % L["lag_minutes"]["filled_next_minute_pct"])
    print("  median wait                %s min   mean %s   p90 %s"
          % (L["lag_minutes"]["median"], L["lag_minutes"]["mean"], L["lag_minutes"]["p90"]))
    print("  fill left past its own stop     %d" % L["gap_through_leaves_fill_past_stop"])
    print("  days with an order         %d, of which the first order never filled %d"
          % (L["days_with_an_order"], L["days_first_order_never_filled"]))
    print()
    print("== R already won at the moment the signal exists ==")
    for m, f in head_free.items():
        print("  %-10s n=%4d  median %+.3fR  mean %+.3fR   already up 0.5R %.1f%%   1R %.1f%%"
              % (m, f["n"], f["median_R_already_won_at_signal"],
                 f["mean_R_already_won_at_signal"], f["pct_already_up_half_R"],
                 f["pct_already_up_1R"]))
    print()
    print("== one trade a day, when does it happen ==")
    for m, t in tod.items():
        print("  %-10s n=%3d  before 10:00 %3d (%.0f%%)  median %s"
              % (m, t["n"], t["before_10am"], t["before_10am_pct"], t["median_et"]))
    print()
    print("== how much of the published book survives ==")
    for m, s in surv.items():
        print("  %-10s %5d trades  %5d shared with head (%.0f%% of head's)  %5d new  %5d lost"
              % (m, s["trades"], s["shared_with_head"], s["shared_pct_of_head"],
                 s["new"], s["lost_from_head"]))
    print("\nwrote research/g76_rebuild_diag.json")


if __name__ == "__main__":
    main()
