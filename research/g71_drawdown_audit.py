"""G7.1 / drawdown — the true max drawdown of the current 2-year book.

Austin: "you say max drawdown is not an issue but i still see it in the graph."

Everything here is measured off research/bt2y_trades.json (the book
research/build_bt2y_report.py renders as research/omen-2y-backtest.html).
Trades only (traded == True), chronological by (day, et) — the same ordering
build_bt2y_report.py's `order` array and research/t0_rebaseline.py:43 use, so
this is a like-for-like read of the number the page prints, plus everything the
page does NOT print: when the drawdown happened, how long it lasted, how long
recovery took, and what it does to a prop-firm trailing floor.

Two granularities, because prop firms differ:
  TRADE level  — cumulative R after each closed trade. This is the intraday
                 high-water mark an INTRADAY-trailing account ratchets on.
  DAY level    — cumulative R after each session's total. This is what an
                 EOD-trailing account (Apex 4.0, Topstep MLL, MFF Pro) sees.

No engine file is touched. Read-only.

Usage: python research/g71_drawdown_audit.py [--book research/bt2y_trades.json]
"""
from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RISK = 1000.0            # 1R = $1,000 (CLAUDE.md)


def usd(x):
    """Python's %% formatting has no thousands flag; this is the one money fmt."""
    return ("-$" if x < 0 else "$") + format(abs(x), ",.0f")


# ---------------------------------------------------------------- load

def load(path):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    meta = d["meta"]
    tr = [t for t in d["trades"] if t.get("traded")]
    tr.sort(key=lambda t: (t["day"], t["et"]))
    return meta, tr


# ---------------------------------------------------------------- drawdown

def curve(rs):
    """Cumulative sum, starting at 0.0 before the first element."""
    eq, out = 0.0, []
    for r in rs:
        eq += r
        out.append(eq)
    return out


def drawdowns(eq, labels):
    """Every peak-to-trough episode on an equity curve, deepest first.

    An episode opens when the curve leaves a running high-water mark and closes
    when it makes a new one (or at the end of the series, still under water).
    Returns dicts with peak/trough/recovery indices so callers can date them.
    """
    eps = []
    peak_v, peak_i = 0.0, -1          # equity starts flat at 0 before trade 0
    trough_v, trough_i = 0.0, -1
    open_ep = False
    for i, v in enumerate(eq):
        if v >= peak_v:
            if open_ep:
                eps.append({"peak_i": peak_i, "trough_i": trough_i,
                            "rec_i": i, "depth": peak_v - trough_v,
                            "peak_v": peak_v, "trough_v": trough_v})
                open_ep = False
            peak_v, peak_i = v, i
            trough_v, trough_i = v, i
        else:
            if not open_ep or v < trough_v:
                trough_v, trough_i = v, i
            open_ep = True
    if open_ep:
        eps.append({"peak_i": peak_i, "trough_i": trough_i, "rec_i": None,
                    "depth": peak_v - trough_v,
                    "peak_v": peak_v, "trough_v": trough_v})
    for e in eps:
        e["peak_lab"] = labels[e["peak_i"]] if e["peak_i"] >= 0 else "<start>"
        e["trough_lab"] = labels[e["trough_i"]]
        e["rec_lab"] = labels[e["rec_i"]] if e["rec_i"] is not None else None
    eps.sort(key=lambda e: -e["depth"])
    return eps


def sessions_between(sessions, a, b):
    """Trading sessions from day a to day b inclusive, off the book's own
    session calendar (not calendar days — the book only knows days it traded,
    so this is 'sessions the engine was live', which is the honest unit)."""
    ia, ib = sessions.index(a), sessions.index(b)
    return ib - ia + 1


def streaks(vals):
    """(longest run of negatives, its start index, its end index)."""
    best, best_s, best_e = 0, -1, -1
    run, start = 0, 0
    for i, v in enumerate(vals):
        if v < 0:
            if run == 0:
                start = i
            run += 1
            if run > best:
                best, best_s, best_e = run, start, i
        else:
            run = 0
    return best, best_s, best_e


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="research/bt2y_trades.json")
    a = ap.parse_args()

    meta, tr = load(ROOT / a.book)
    rs = [t["r"] for t in tr]
    tlabs = ["%s %s %s" % (t["day"], t["et"], t["sym"]) for t in tr]
    eqt = curve(rs)

    # day level
    byday = OrderedDict()
    for t in tr:
        byday[t["day"]] = byday.get(t["day"], 0.0) + t["r"]
    days = list(byday)
    dvals = [byday[d] for d in days]
    eqd = curve(dvals)

    print("=" * 74)
    print("BOOK  %s" % a.book)
    print("  generated %s | %s .. %s | %d sessions in universe"
          % (meta["generated"], meta["first"], meta["last"], meta["sessions"]))
    print("  signals %d | traded %d | loss_halt %s (%d blocked)"
          % (meta["signals"], meta["traded"], meta.get("loss_halt"),
             meta.get("halted", 0)))
    print("  traded rows read here: %d | trading days with a trade: %d"
          % (len(tr), len(days)))
    print("  total %+.2fR (%s) | mean %+.4fR | win%% %.1f"
          % (sum(rs), "$%s" % format(sum(rs)*RISK, ",.0f"), sum(rs) / len(rs),
             100.0 * sum(1 for r in rs if r > 0)
             / max(1, sum(1 for r in rs if r != 0))))

    # ---- trade-level drawdown
    et = drawdowns(eqt, tlabs)
    print()
    print("== TRADE-LEVEL DRAWDOWN (intraday high-water, cumulative R) ==")
    print("  worst 6 episodes:")
    print("  %-6s %-26s %-26s %8s %10s %7s %7s"
          % ("depth", "peak (day time sym)", "trough (day time sym)",
             "dollars", "peak eq", "trades", "sess"))
    for e in et[:6]:
        pday = e["peak_lab"].split()[0] if e["peak_i"] >= 0 else days[0]
        tday = e["trough_lab"].split()[0]
        sess = sessions_between(days, pday, tday)
        print("  %-6.2f %-26s %-26s %8s %10.2f %7d %7d"
              % (e["depth"], e["peak_lab"], e["trough_lab"],
                 usd(e["depth"] * RISK), e["peak_v"],
                 e["trough_i"] - e["peak_i"], sess))
    w = et[0]
    wpday = w["peak_lab"].split()[0] if w["peak_i"] >= 0 else days[0]
    wtday = w["trough_lab"].split()[0]
    print()
    print("  WORST: -%.2fR = -%s at $%d/R"
          % (w["depth"], usd(w["depth"] * RISK), RISK))
    print("         peak  %s  (equity %+.2fR)" % (w["peak_lab"], w["peak_v"]))
    print("         trough %s  (equity %+.2fR)" % (w["trough_lab"], w["trough_v"]))
    print("         duration %d trades / %d trading sessions (%s -> %s)"
          % (w["trough_i"] - w["peak_i"],
             sessions_between(days, wpday, wtday), wpday, wtday))
    if w["rec_lab"]:
        rday = w["rec_lab"].split()[0]
        print("         recovered %s — %d sessions under water from the peak"
              % (rday, sessions_between(days, wpday, rday)))
    else:
        print("         NEVER RECOVERED — the book ends inside this drawdown")
    print("         %.1f%% of the book's total %+.1fR"
          % (100.0 * w["depth"] / sum(rs), sum(rs)))

    # ---- day-level drawdown
    ed = drawdowns(eqd, days)
    print()
    print("== DAY-LEVEL DRAWDOWN (EOD equity, what an EOD-trailing account sees) ==")
    print("  %-6s %-12s %-12s %10s %7s" % ("depth", "peak day", "trough day",
                                           "dollars", "sess"))
    for e in ed[:6]:
        pday = e["peak_lab"] if e["peak_i"] >= 0 else days[0]
        print("  %-6.2f %-12s %-12s %10s %7d"
              % (e["depth"], pday, e["trough_lab"], usd(e["depth"] * RISK),
                 sessions_between(days, pday, e["trough_lab"])))
    wd = ed[0]
    wdp = wd["peak_lab"] if wd["peak_i"] >= 0 else days[0]

    # ---- streaks
    n_l, s_l, e_l = streaks(rs)
    n_d, s_d, e_d = streaks(dvals)
    print()
    print("== STREAKS ==")
    print("  max consecutive LOSING TRADES : %d  (%s -> %s)"
          % (n_l, tlabs[s_l], tlabs[e_l]))
    print("      that run alone is %+.2fR ($%s)"
          % (sum(rs[s_l:e_l + 1]), format(sum(rs[s_l:e_l + 1]) * RISK, ",.0f")))
    print("  max consecutive LOSING DAYS   : %d  (%s -> %s)"
          % (n_d, days[s_d], days[e_d]))
    print("      that run alone is %+.2fR ($%s)"
          % (sum(dvals[s_d:e_d + 1]), format(sum(dvals[s_d:e_d + 1]) * RISK, ",.0f")))
    worst_day = min(days, key=lambda d: byday[d])
    print("  worst single day              : %s  %+.2fR ($%s), %d trades"
          % (worst_day, byday[worst_day], format(byday[worst_day] * RISK, ",.0f"),
             sum(1 for t in tr if t["day"] == worst_day)))
    dcount = {}
    for t in tr:
        dcount[t["day"]] = dcount.get(t["day"], 0) + 1
    busiest = max(dcount, key=dcount.get)
    print("  most trades in one day        : %d on %s (open risk if concurrent)"
          % (dcount[busiest], busiest))
    print("  trades/day mean %.2f, median %d, p95 %d"
          % (len(tr) / len(days), sorted(dcount.values())[len(days) // 2],
             sorted(dcount.values())[int(len(days) * 0.95)]))

    # ---- prop-firm survival
    print()
    print("== PROP-FIRM TRAILING DRAWDOWN ==")
    print("  The book's drawdown is scale-free in R. What busts an account is")
    print("  maxDD_R * risk_per_trade vs the firm's trailing floor.")
    print()
    acct = 150_000.0
    dd_trade, dd_day = w["depth"], wd["depth"]
    rows = [
        ("4% of $150k (Austin's low end)", 0.04 * acct),
        ("5% of $150k", 0.05 * acct),
        ("6% of $150k (Austin's high end)", 0.06 * acct),
        ("Apex $150K EOD 4.0 (g4_prop_fit.md)", 4_000.0),
        ("Topstep $150K MLL / MFF Pro", 4_500.0),
        ("Vanquish $150k (risk_of_ruin.py)", 7_500.0),
    ]
    print("  %-38s %9s %12s %12s" % ("floor", "floor $", "max $/trade",
                                     "at $1000/R"))
    print("  %-38s %9s %12s %12s" % ("", "", "(EOD dd %.2fR)" % dd_day,
                                     "verdict"))
    for lab, floor in rows:
        per = floor / dd_day
        busts_1k = dd_day * RISK >= floor
        print("  %-38s %9s %12s %12s"
              % (lab, usd(floor), usd(per),
                 "BUSTS" if busts_1k else "survives"))
    print()
    print("  intraday-trailing variant (ratchets on the trade-level high-water,")
    print("  maxDD %.2fR):" % dd_trade)
    for lab, floor in rows:
        print("    %-38s max %s/trade" % (lab, usd(floor / dd_trade)))
    print()
    print("  g4_prop_fit.md sized the funded risk unit at $250-$525 from")
    print("  risk-of-ruin, independent of this curve. Cross-check:")
    for unit in (250, 350, 525, 1000):
        print("    $%-5d/R -> EOD dd %s, intraday dd %s  | Apex $4,000: %s"
              % (unit, usd(dd_day * unit), usd(dd_trade * unit),
                 "BUST" if dd_trade * unit >= 4000 else "ok"))

    print()
    print("  the same thing as a %% of a $150k account (Austin's 4-6%% question):")
    print("    %-10s %10s %10s %10s %10s"
          % ("risk/trade", "EOD dd $", "EOD dd %", "intra dd $", "intra dd %"))
    for unit in (250, 350, 400, 500, 650, 1000):
        print("    $%-9d %10s %9.2f%% %10s %9.2f%%"
              % (unit, usd(dd_day * unit), 100 * dd_day * unit / acct,
                 usd(dd_trade * unit), 100 * dd_trade * unit / acct))
    print("    largest risk unit holding 4%% ($6,000): $%.0f EOD / $%.0f intraday"
          % (0.04 * acct / dd_day, 0.04 * acct / dd_trade))
    print("    largest risk unit holding 6%% ($9,000): $%.0f EOD / $%.0f intraday"
          % (0.06 * acct / dd_day, 0.06 * acct / dd_trade))
    print("    (in-sample worst case, zero margin — a live worst case is")
    print("     conventionally taken at 1.5-2x the backtested one)")

    # ---- what the page prints
    print()
    print("== WHAT THE HTML PAGE PRINTS ==")
    print("  build_bt2y_report.py:385 computes dd over `live` (filtered,")
    print("  chronological) and :479 prints it as 'Max drawdown'.")
    print("  On the default 'traded' book that KPI = -%.1fR = -%s."
          % (dd_trade, usd(dd_trade * RISK)))
    print("  The equity curve at :506 plots the SAME series, so the dip Austin")
    print("  sees on the chart and this number are the same object.")

    out = {
        "book": a.book, "generated": meta["generated"],
        "traded": len(tr), "days": len(days), "total_r": round(sum(rs), 2),
        "trade_level": {
            "max_dd_r": round(dd_trade, 2),
            "max_dd_usd": round(dd_trade * RISK, 0),
            "peak": w["peak_lab"], "trough": w["trough_lab"],
            "recovered": w["rec_lab"],
            "trades_in_dd": w["trough_i"] - w["peak_i"],
            "sessions_in_dd": sessions_between(days, wpday, wtday),
            "top6": [{"depth": round(e["depth"], 2), "peak": e["peak_lab"],
                      "trough": e["trough_lab"], "recovered": e["rec_lab"]}
                     for e in et[:6]],
        },
        "day_level": {
            "max_dd_r": round(dd_day, 2),
            "max_dd_usd": round(dd_day * RISK, 0),
            "peak": wdp, "trough": wd["trough_lab"], "recovered": wd["rec_lab"],
            "sessions_in_dd": sessions_between(days, wdp, wd["trough_lab"]),
            "top6": [{"depth": round(e["depth"], 2),
                      "peak": (e["peak_lab"] if e["peak_i"] >= 0 else days[0]),
                      "trough": e["trough_lab"], "recovered": e["rec_lab"]}
                     for e in ed[:6]],
        },
        "streaks": {
            "max_consec_losing_trades": n_l,
            "run_from": tlabs[s_l], "run_to": tlabs[e_l],
            "max_consec_losing_days": n_d,
            "day_run_from": days[s_d], "day_run_to": days[e_d],
            "worst_day": worst_day, "worst_day_r": round(byday[worst_day], 2),
            "max_trades_one_day": dcount[busiest], "busiest_day": busiest,
        },
    }
    p = ROOT / "research" / "g71_drawdown.json"
    p.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("\nwrote %s" % p)


if __name__ == "__main__":
    main()
