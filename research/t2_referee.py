"""t2_referee.py -- referee for row T2 (research/g213_instruments.py).

Builder commit: ccd7fa0683ef7ebf10a539228d8a4a5b8a571d64
(the T2 files actually landed across 07c35df8 + ccd7fa06, both
 "wip: auto-commit" messages, not a T2-named commit).

Everything here is re-derived from research/tape/instruments_2026-09-05.json.gz
and research/tape/baseline_2026-09-05.json.gz with this file's own arithmetic --
no import of g72_suppress_price.stats, no import of g213_instruments' pricing.

Sections
  A  independent recompute of the three published instrument tables
  B  matched comparison: shares vs futures on the SAME 99 futures-eligible rows
  C  contract rounding: the realised-R distribution vs 1.0 (futures + options)
  D  futures basis sensitivity: perturb the ETF->index ratio and re-price
  E  options: instrument_source census, spread-cost asymmetry real vs model
  F  options: does the "real" row price the same trade the shares row booked?

Run: python research/t2_referee.py            (offline, no network)
     python research/t2_referee.py --polygon  (adds the 10-row live re-pull)
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

BOOK = ROOT / "research" / "tape" / "instruments_2026-09-05.json.gz"
BASE = ROOT / "research" / "tape" / "baseline_2026-09-05.json.gz"
BOUNDARY = "2025-09-01"
RISK = 1000.0


def load(p):
    b = json.loads(gzip.open(p, "rt", encoding="utf-8").read())
    return b["meta"], b["trades"]


def iso_week(day):
    import datetime as dt
    y, w, _ = dt.date(int(day[:4]), int(day[5:7]), int(day[8:10])).isocalendar()
    return "%04d-W%02d" % (y, w)


def stats(rows, n_days):
    """rows: [{day, pnl}]. Independent of g72_suppress_price."""
    if not rows or not n_days:
        return None
    pnls = [r["pnl"] for r in rows]
    total = sum(pnls)
    w = sum(1 for p in pnls if p > 0)
    l = sum(1 for p in pnls if p < 0)
    by_m, by_w = {}, {}
    for r in rows:
        by_m[r["day"][:7]] = by_m.get(r["day"][:7], 0.0) + r["pnl"]
        by_w[iso_week(r["day"])] = by_w.get(iso_week(r["day"]), 0.0) + r["pnl"]
    return {
        "trades": len(rows),
        "total": round(total, 0),
        "per_day": round(total / n_days, 0),
        "mean_r": round(total / len(rows) / RISK, 4),
        "win_pct": round(w / (w + l) * 100, 1) if (w + l) else 0.0,
        "months_green": sum(1 for v in by_m.values() if v > 0),
        "months": len(by_m),
        "weeks_green": sum(1 for v in by_w.values() if v > 0),
        "weeks": len(by_w),
    }


def fmt(s, label):
    if s is None:
        return "%-34s no rows" % label
    flag = "" if (s["trades"] >= 30 and s["months"] >= 12) else \
        "   NOT ENOUGH (%d trades, %d months)" % (s["trades"], s["months"])
    return ("%-34s $%s/day  meanR %+.3f  win %4.1f%%  %2d/%-2d green  n=%d%s"
            % (label, ("%d" % s["per_day"]).rjust(5), s["mean_r"], s["win_pct"],
               s["months_green"], s["months"], s["trades"], flag))


# --------------------------------------------------------- futures re-pricing
FUT_MAP = {"SPY": "MES", "QQQ": "MNQ", "IWM": "M2K"}
FUT_TICK = {"MES": 0.25, "MNQ": 0.25, "M2K": 0.10}
FUT_MULT = {"MES": 5.0, "MNQ": 2.0, "M2K": 5.0}
COMM = 0.62


def round_tick(px, tick):
    return round(round(px / tick) * tick, 4)


def price_fut(entry, stop, r, sym, ratio):
    fut = FUT_MAP[sym]
    tick, mult = FUT_TICK[fut], FUT_MULT[fut]
    ie, isx = round_tick(entry * ratio, tick), round_tick(stop * ratio, tick)
    pts = abs(ie - isx) or tick
    rpc = pts * mult
    n = max(1, round(RISK / rpc))
    actual = n * rpc
    return r * actual - 2 * COMM * n, actual, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--polygon", action="store_true")
    args = ap.parse_args()

    meta, T = load(BOOK)
    bmeta, brows = load(BASE)
    bx = {}
    for r in brows:
        k = (r["sym"], r["day"], r["et"], round(r["entry"], 2), round(r["stop"], 2),
             r["dir"], r["setup"])
        bx["|".join(str(x) for x in k)] = r

    out = []
    P = out.append
    P("T2 REFEREE -- independent recompute")
    P("book   : research/tape/instruments_2026-09-05.json.gz")
    P("stamp  : commit %s  dirty_py_count=%s  dirty_engine_py=%s  built %s"
      % (meta["git"]["commit"][:8], meta["git"]["dirty_py_count"],
         meta["git"]["dirty_engine_py"], meta["built_at"]))
    P("rows   : %d" % len(T))
    P("")

    days_all = sorted({t["day"] for t in T})
    nd_all = len(days_all)
    nd_h1 = len({d for d in days_all if d < BOUNDARY})
    nd_h2 = len({d for d in days_all if d >= BOUNDARY})
    P("A. INDEPENDENT RECOMPUTE (denominator = every day in the unit book: "
      "all %d, H1 %d, H2 %d)" % (nd_all, nd_h1, nd_h2))
    for key in ("shares", "futures", "options"):
        rows = [{"day": t["day"], "pnl": t[key]["pnl"]} for t in T if "pnl" in t[key]]
        h1 = [r for r in rows if r["day"] < BOUNDARY]
        h2 = [r for r in rows if r["day"] >= BOUNDARY]
        P("  " + fmt(stats(rows, nd_all), key + " whole"))
        P("  " + fmt(stats(h1, nd_h1), key + " H1 <2025-09-01"))
        P("  " + fmt(stats(h2, nd_h2), key + " H2 >=2025-09-01"))
    P("")

    # --------------------------------------------------------------- B matched
    fut_rows = [t for t in T if "pnl" in t["futures"]]
    fut_days = sorted({t["day"] for t in fut_rows})
    P("B. MATCHED SUBSET -- the %d futures-eligible rows (SPY/QQQ only), "
      "on %d distinct days" % (len(fut_rows), len(fut_days)))
    P("   the published table compares 99 futures rows against 769 shares rows.")
    P("   same-rows comparison, both denominators shown:")
    for key in ("shares", "futures", "options"):
        rows = [{"day": t["day"], "pnl": t[key]["pnl"]} for t in fut_rows]
        h1 = [r for r in rows if r["day"] < BOUNDARY]
        h2 = [r for r in rows if r["day"] >= BOUNDARY]
        P("  " + fmt(stats(rows, nd_all), key + " on the 99 /all-days"))
        P("  " + fmt(stats(rows, len(fut_days)), key + " on the 99 /its-own-days"))
        P("  " + fmt(stats(h1, nd_h1), key + " on the 99, H1"))
        P("  " + fmt(stats(h2, nd_h2), key + " on the 99, H2"))
    P("")

    # -------------------------------------------------------------- C rounding
    P("C. CONTRACT ROUNDING -- realised 1R in dollars vs the nominal $1,000")
    for key in ("futures", "options"):
        a = [t[key]["actual_r_dollars"] for t in T if "actual_r_dollars" in t[key]]
        if not a:
            continue
        ratio = [x / RISK for x in a]
        P("  %-8s n=%d  min %.3f  p05 %.3f  median %.3f  p95 %.3f  max %.3f  "
          "mean %.4f  sd %.4f" % (key, len(a), min(ratio),
                                  statistics.quantiles(ratio, n=20)[0],
                                  statistics.median(ratio),
                                  statistics.quantiles(ratio, n=20)[18],
                                  max(ratio), statistics.mean(ratio),
                                  statistics.pstdev(ratio)))
        P("           |realised R - 1.0| > 5%%: %d rows (%.1f%%);  > 20%%: %d rows"
          % (sum(1 for x in ratio if abs(x - 1) > .05),
             100 * sum(1 for x in ratio if abs(x - 1) > .05) / len(ratio),
             sum(1 for x in ratio if abs(x - 1) > .20)))
    nc = [t["futures"]["contracts"] for t in T if "contracts" in t["futures"]]
    if nc:
        P("  futures contract counts: min %d median %d max %d; rows sized to 1 "
          "contract (rounding floor bites hardest): %d"
          % (min(nc), int(statistics.median(nc)), max(nc), sum(1 for x in nc if x == 1)))
    P("")

    # ------------------------------------------------------- D basis sensitivity
    P("D. FUTURES BASIS SENSITIVITY -- re-price the 99 rows at perturbed ratios")
    P("   (basis + carry - dividends on a 2y ETF/index ratio is order 1-2%%; "
      "5%% and 10%% are stress rows)")
    base_ratio = {"SPY": 10.0, "QQQ": 41.35}
    P("   %-8s %-9s %-9s %-8s %-7s %-6s" % ("shock", "$/day", "total", "meanR", "win%", "green"))
    for pct in (0.0, -0.005, 0.005, -0.01, 0.01, -0.02, 0.02, -0.05, 0.05, -0.10, 0.10):
        rows = []
        for t in fut_rows:
            b = bx[t["id"]]
            ratio = base_ratio[t["sym"]] * (1 + pct)
            pnl, _, _ = price_fut(b["entry"], b["stop"], b["r"], t["sym"], ratio)
            rows.append({"day": t["day"], "pnl": pnl})
        s = stats(rows, nd_all)
        P("   %-8s %-9s %-9s %-8.4f %-7.1f %d/%d"
          % ("%+.1f%%" % (pct * 100), "$%d" % s["per_day"], "$%d" % s["total"],
             s["mean_r"], s["win_pct"], s["months_green"], s["months"]))
    # how far does the ratio have to move to flip the sign of futures $/day?
    P("   sign of futures $/day across the whole shock range above: "
      + ("UNCHANGED" if len({1 if stats([{"day": t["day"], "pnl":
            price_fut(bx[t["id"]]["entry"], bx[t["id"]]["stop"], bx[t["id"]]["r"],
                      t["sym"], base_ratio[t["sym"]] * (1 + p))[0]}
            for t in fut_rows], nd_all)["per_day"] > 0 else 0
            for p in (-.10, -.05, -.02, 0, .02, .05, .10)}) == 1 else "FLIPS"))
    P("")

    # ------------------------------------------------------------- E options
    P("E. OPTIONS -- instrument_source census, read off the book, not assumed")
    src = {}
    for t in T:
        src[t["options"]["instrument_source"]] = src.get(t["options"]["instrument_source"], 0) + 1
    P("   %s   -> real share %.2f%% of %d" % (src, 100 * src.get("real", 0) / len(T), len(T)))
    P("   every row carries instrument_source: %s"
      % all("instrument_source" in t["options"] for t in T))
    real = [t for t in T if t["options"]["instrument_source"] == "real"]
    model = [t for t in T if t["options"]["instrument_source"] == "model"]
    P("   spread cost charged: real rows with a spread_cost field = %d of %d; "
      "model rows = %d of %d" % (sum(1 for t in real if "spread_cost" in t["options"]),
                                  len(real),
                                  sum(1 for t in model if "spread_cost" in t["options"]),
                                  len(model)))
    sc = [t["options"]["spread_cost"] for t in model]
    P("   model spread cost per trade: median $%d, mean $%d, total $%d over %d rows"
      % (statistics.median(sc), statistics.mean(sc), sum(sc), len(sc)))
    P("   model total pnl $%d, of which spread is $%d (%.0f%% of the loss)"
      % (sum(t["options"]["pnl"] for t in model), -sum(sc),
         100 * sum(sc) / abs(sum(t["options"]["pnl"] for t in model))))
    # what the model column looks like with the SAME zero-spread treatment
    # the real rows got
    nos = [{"day": t["day"], "pnl": t["options"]["pnl"] + t["options"].get("spread_cost", 0.0)}
           for t in T]
    P("   " + fmt(stats(nos, nd_all), "options, spread removed"))
    half = [{"day": t["day"], "pnl": t["options"]["pnl"] + t["options"].get("spread_cost", 0.0) / 2}
            for t in T]
    P("   " + fmt(stats(half, nd_all), "options, half the spread"))
    P("   the script charges 2 x $0.05 x 100 x contracts = $10/contract round")
    P("   trip, i.e. the FULL quoted width twice. Crossing a $0.05 wide market")
    P("   from mid costs $0.025 each way = $5/contract round trip. The 'half")
    P("   the spread' row is that convention.")
    P("   -> the real rows are priced with NO spread (a 1-min aggregate close is")
    P("      a traded print) and the model rows with two full widths; the two")
    P("      sources are not on one ruler.")
    P("")

    # ------------------------------------------------------------- F same trade
    P("F. DOES A 'real' OPTION ROW PRICE THE SAME TRADE THE SHARES ROW BOOKED?")
    dis = 0
    lad = 0
    for t in real:
        b = bx[t["id"]]
        if b.get("scaled"):
            lad += 1
        if (t["shares"]["pnl"] > 0) != (t["options"]["pnl"] > 0):
            dis += 1
    P("   real rows: %d;  of those the shares book scaled out of: %d" % (len(real), lad))
    P("   real rows where the option P&L sign DISAGREES with the shares P&L sign: "
      "%d of %d (%.0f%%)" % (dis, len(real), 100 * dis / len(real)))
    P("   the option leg is priced entry-close -> (entry+bars)-close on ONE")
    P("   contract; the shares row is a 30/30/30/10 ladder with up to four")
    P("   exits. `bars` is backtest_2y.py:244 `exit_idx - entry_idx`, i.e. the")
    P("   LAST leg. Examples:")
    for t in real[:6]:
        b = bx[t["id"]]
        P("     %-6s %s %s  shares r %+.3f pnl $%-8.0f  scaled=%-5s  "
          "opt %.2f->%.2f x%d pnl $%.0f"
          % (t["sym"], t["day"], t["et"], b["r"], t["shares"]["pnl"],
             bool(b.get("scaled")), t["options"]["entry_opt"], t["options"]["exit_opt"],
             t["options"]["contracts"], t["options"]["pnl"]))
    P("")

    # ------------------------------------------------------------ G cache truth
    P("G. WHY THE REAL SHARE IS 2.6%% -- what is actually on disk")
    cat = sorted((ROOT / "data_archive" / "options" / "catalog").glob("*.json"))
    agg = sorted((ROOT / "data_archive" / "options" / "aggs").glob("*.json"))
    n403 = sum(1 for f in agg if json.loads(f.read_text()).get("_status") == 403)
    P("   catalog files cached: %d ; aggregate files cached: %d (of which 403: %d)"
      % (len(cat), len(agg), n403))
    P("   distinct unit rows ever ATTEMPTED for a real fetch: <= %d of %d (%.1f%%)"
      % (len(agg), len(T), 100 * len(agg) / len(T)))
    prog = ROOT / "data_archive" / "options" / "g213_progress.json"
    P("   checkpoint file g213_progress.json exists: %s" % prog.exists())
    P("   403 contracts on disk: %s"
      % [f.name for f in agg if json.loads(f.read_text()).get("_status") == 403])
    P("")

    if args.polygon:
        P("H. LIVE POLYGON RE-PULL (referee's own fetch, 10 rows)")
        from research.g73_polygon_fetch import _get
        import datetime as dt
        from zoneinfo import ZoneInfo
        ET = ZoneInfo("America/New_York")
        rnd = random.Random(777)
        pick = rnd.sample(real, min(10, len(real)))
        npass = nfail = 0
        for t in pick:
            tk = t["options"]["contract"]
            j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (tk, t["day"], t["day"]),
                     adjusted="true", sort="asc", limit=50000)
            if "_status" in j:
                P("   %-6s %s %-24s FETCH %s" % (t["sym"], t["day"], tk, j["_status"]))
                nfail += 1
                continue
            bars = {}
            for b in (j.get("results") or []):
                ts = dt.datetime.fromtimestamp(b["t"] / 1000, tz=dt.timezone.utc).astimezone(ET)
                bars[ts.strftime("%H:%M")] = b["c"]

            def near(hhmm):
                if hhmm in bars:
                    return bars[hhmm], 0
                tot = int(hhmm[:2]) * 60 + int(hhmm[3:])
                best, bd = None, 6
                for k, v in bars.items():
                    d = abs(int(k[:2]) * 60 + int(k[3:]) - tot)
                    if d < bd:
                        bd, best = d, v
                return best, bd

            ex = "%02d:%02d" % divmod(int(t["et"][:2]) * 60 + int(t["et"][3:]) + t["bars"], 60)
            e, de = near(t["et"])
            x, dx = near(ex)
            ok = (e == t["options"]["entry_opt"]) and (x == t["options"]["exit_opt"])
            npass += ok
            nfail += (not ok)
            P("   %-6s %s %-24s stored %.2f->%.2f | fresh %s->%s (offset %dm/%dm) %s"
              % (t["sym"], t["day"], tk, t["options"]["entry_opt"],
                 t["options"]["exit_opt"], e, x, de, dx, "PASS" if ok else "FAIL"))
        P("   %d pass / %d fail of %d re-pulled" % (npass, nfail, len(pick)))
        P("")
        P("I. IS THE 403 A LOOKBACK BOUNDARY? (the fetch loop breaks on the first")
        P("   403 -- g213_instruments.py:341-343 -- so one boundary day ends the pass)")
        for tk, day in (("O:SPY240904C00552000", "2024-09-04"),
                        ("O:MSFT240906C00407500", "2024-09-04"),
                        ("O:TSLA240906C00230000", "2024-09-05"),
                        ("O:SPY250130C00605000", "2025-01-30")):
            j = _get("/v2/aggs/ticker/%s/range/1/minute/%s/%s" % (tk, day, day),
                     adjusted="true", sort="asc", limit=50000)
            P("   %-24s %s -> %s" % (tk, day,
                                      j.get("_status", "200, %d bars" % len(j.get("results") or []))))
        P("")

    txt = "\n".join(out)
    print(txt)
    (ROOT / "research" / "t2_referee_out.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    main()
