"""g91 -- the lane, measured instead of argued.

Austin, 2026-09-01: "we really need to pick our lane, 'cause I don't have a lot
of money. So, we really need to do prop firms. And if we're doing prop firms, we
need to really focus on those stocks. But we can do all options, lots of options."

There is a real inconsistency in that sentence, and it is worth naming before any
number: **the mainstream prop firms are futures desks** (Topstep, Apex,
MyFundedFutures, TakeProfit -- ES/NQ/RTY/CL/GC). They do not fund equity-options
traders. So "prop firms" and "those stocks, lots of options" are two different
lanes, not one.

The good news is that the choice is measurable **today, on the book we already
have**, because QQQ/SPY/IWM are already in the universe and they are the cash
proxies for NQ/ES/RTY. Slicing the honest book to the index names IS the prop
lane, at one remove.

WHAT THIS ADDS THAT NOTHING ELSE MEASURES. Every OMEN number to date optimises
$/day and months-green. A funded account does not care about either one first --
it cares whether you survive:

  * a **daily loss limit** (one bad day ends the account, not the month),
  * a **trailing max drawdown** (the PATH of the equity curve, not its endpoint),
  * a **consistency rule** (most firms void a payout if one day is more than
    20-30%% of total profit).

That last one matters more than it looks: the oracle "best setup of the day" arm
that CLAUDE.md holds up as the ceiling would **fail** a standard consistency rule
outright. A prop lane is a different objective function, not the same one with a
smaller account.

R IS THE RESULT, DOLLARS ARE A SIZING SKIN. 1R = $1,000 is an options-account
skin. On a $50k funded account with a $2,000 daily loss limit, one -1.25R stop at
that size is 62%% of the day's limit. So every lane is also reported at
`max_r_for_dd` -- the largest 1R whose worst peak-to-trough drawdown still fits
inside a funded account's trailing limit -- and at `funded_per_day`, what the lane
then actually pays. Those two, not $/day at a notional $1,000 R, decide whether a
lane is fundable. The daily loss cap turns out never to bind on a one-trade-a-day
book: one trade can only lose 1R.

    python research/g91_lane_slice.py
    python research/g91_lane_slice.py --limit 2500

Writes research/g91_lane_slice.json and .md. Applies nothing, ships nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, HERE)

import g86_honest_ceiling as g86              # noqa: E402  reuse, do not re-derive

HONEST = os.path.join(HERE, "bt2y_trades.json")
OUT_JSON = os.path.join(HERE, "g91_lane_slice.json")
OUT_MD = os.path.join(HERE, "g91_lane_slice.md")

# The lanes. Each is a predicate over a book row.
INDEX = {"QQQ", "SPY", "IWM"}
TEN = {"QQQ", "SPY", "NVDA", "TSLA", "AAPL", "AMD", "META", "MSFT", "AMZN", "GOOGL"}

LANES = [
    ("full pool (shipped)", lambda r: True,
     "every symbol in the book -- the baseline every published figure uses"),
    ("index only: QQQ/SPY/IWM", lambda r: r["sym"] in INDEX,
     "the prop-firm lane at one remove: cash proxies for NQ/ES/RTY"),
    ("QQQ + SPY only", lambda r: r["sym"] in {"QQQ", "SPY"},
     "the tightest futures proxy -- NQ and ES, the two most-funded contracts"),
    ("QQQ only", lambda r: r["sym"] == "QQQ",
     "one instrument, the way a funded futures trader actually trades"),
    ("ten tickers (his rule_11)", lambda r: r["sym"] in TEN,
     'his ballot: "10 tickers is a good sample size, and still tracking the '
     'main pool for data for edge refinement"'),
    ("equities only", lambda r: r.get("pool") == "equity",
     "single names -- the options lane"),
    ("core tier only", lambda r: r.get("tier") == "core",
     "universe.CORE_SYMBOLS"),
]


def daily_pnl(firsts):
    """{day: pnl} for a one-trade-a-day arm."""
    d = defaultdict(float)
    for r in firsts:
        d[r["day"]] += r["pnl"]
    return d


def path_risk(by_day: dict, limit: float, dd_budget: float) -> dict:
    """The metrics a funded account is actually judged on.

    `dd_budget` is the funded account's trailing max drawdown.

    `max_dd` is peak-to-trough on the cumulative daily curve. `worst_day` is the
    single worst session. `breaches` counts sessions that would have tripped a
    `limit`-dollar daily loss cap -- ONE of those ends a funded account, so the
    count matters far more than the mean.
    """
    days = sorted(by_day)
    if not days:
        return {}
    cum = peak = 0.0
    max_dd = 0.0
    for d in days:
        cum += by_day[d]
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
    vals = [by_day[d] for d in days]
    total = sum(vals)
    wins = [v for v in vals if v > 0]
    worst = min(vals)
    best = max(vals)
    return {
        "days": len(days),
        "total": round(total, 2),
        "per_day": round(total / len(days), 2),
        "worst_day": round(worst, 2),
        "best_day": round(best, 2),
        "max_dd": round(max_dd, 2),
        "green_days_pct": round(len(wins) / len(days) * 100, 1),
        "breaches": sum(1 for v in vals if v < -limit),
        "breach_pct": round(sum(1 for v in vals if v < -limit) / len(days) * 100, 2),
        # Consistency: most firms void a payout when one day is >20-30% of total
        # profit. Meaningless (and reported as None) when the book loses money.
        "best_day_pct_of_total": (round(best / total * 100, 1)
                                  if total > 0 else None),
        # The largest 1R that keeps the book's own worst day inside the limit.
        # Everything scales linearly in R, so this is exact, not an estimate.
        # For a one-trade-a-day book this is nearly always slack: one trade can
        # only lose 1R, so the DAILY cap is never what binds.
        "max_r_for_limit": (round(limit / abs(worst) * g86.RISK)
                            if worst < 0 else None),
        # THE ONE THAT ACTUALLY BINDS. A funded account dies on its TRAILING
        # drawdown, not on a single session, and a 50k account carries roughly
        # $2,000-2,500 of it. Everything scales linearly in R, so the largest
        # survivable 1R is exact -- and `funded_per_day` is what this lane would
        # really pay at that size. That number, not $/day at a notional $1,000
        # R, is the honest prop-firm figure.
        "max_r_for_dd": (round(dd_budget / max_dd * g86.RISK)
                         if max_dd > 0 else None),
        "funded_per_day": (round(total / len(days) * (dd_budget / max_dd), 2)
                           if max_dd > 0 else None),
    }


def months_green(by_day: dict) -> tuple:
    m = defaultdict(float)
    for d, v in by_day.items():
        m[d[:7]] += v
    return sum(1 for v in m.values() if v > 0), len(m)


def run_lane(rows, label, pred, why, limit, dd_budget):
    sub = [r for r in rows if pred(r)]
    if not sub:
        return None
    byday = g86.candidates(sub)
    firsts, bests = [], []
    for day in sorted(byday):
        v = byday[day]
        if not v:
            continue
        firsts.append(v[0])
        bests.append(max(v, key=lambda r: r["pnl"]))

    f_daily, b_daily = daily_pnl(firsts), daily_pnl(bests)
    fg, fm = months_green(f_daily)
    bg, bm = months_green(b_daily)
    n_days = len(f_daily)

    return {
        "lane": label, "why": why,
        "symbols": len({r["sym"] for r in sub}),
        "book_rows": len(sub),
        "candidates": sum(len(v) for v in byday.values()),
        "cands_per_day": round(sum(len(v) for v in byday.values()) / n_days, 1)
                          if n_days else 0,
        "first": g86.stats(firsts, n_days),
        "best": g86.stats(bests, n_days),
        "first_path": path_risk(f_daily, limit, dd_budget),
        "best_path": path_risk(b_daily, limit, dd_budget),
        "months_green_first": "%d/%d" % (fg, fm),
        "months_green_best": "%d/%d" % (bg, bm),
    }


def demo():
    """Self-check: the full-pool lane must reproduce g86's published first-of-day.

    If this drifts, the slicer is not measuring the same book as the table in
    CLAUDE.md and every lane comparison below it is meaningless.
    """
    book = json.load(open(HONEST, encoding="utf-8"))
    rows = book["trades"] if isinstance(book, dict) else book
    mine = run_lane(rows, "full", lambda r: True, "", 2000.0, 2500.0)
    ref = g86.arm(HONEST, "honest")
    for k in ("per_day", "win_pct"):
        a, b = mine["first"][k], ref["first"][k]
        assert abs(a - b) < 0.01, "full-pool %s: slicer=%s g86=%s" % (k, a, b)
    assert mine["first"]["per_day"] == ref["first"]["per_day"]
    print("demo OK -- full pool reproduces g86 exactly: first-of-day $%.0f/day, "
          "%.1f%% win" % (mine["first"]["per_day"], mine["first"]["win_pct"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=float, default=2000.0,
                    help="daily loss limit in dollars (typical 50k funded account)")
    ap.add_argument("--dd", type=float, default=2500.0,
                    help="funded account trailing max drawdown (50k acct ~= $2,500)")
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()

    if a.demo:
        demo()
        return

    book = json.load(open(HONEST, encoding="utf-8"))
    rows = book["trades"] if isinstance(book, dict) else book
    print("honest book: %d rows, %d symbols, %d days"
          % (len(rows), len({r["sym"] for r in rows}),
             len({r["day"] for r in rows})))
    print("daily loss limit for the survival columns: $%.0f\n" % a.limit)

    out = []
    for label, pred, why in LANES:
        r = run_lane(rows, label, pred, why, a.limit, a.dd)
        if r:
            out.append(r)
            fp, f = r["first_path"], r["first"]
            print("%-28s %2d sym  %4.1f cand/day  $%6.0f/day  %4.1f%% win  "
                  "maxDD $%-7.0f  -> funded 1R $%-5s = $%s/day"
                  % (label, r["symbols"], r["cands_per_day"], f["per_day"],
                     f["win_pct"], fp["max_dd"],
                     fp["max_r_for_dd"] or "-", fp["funded_per_day"] or "-"))

    json.dump({"limit": a.limit, "lanes": out}, open(OUT_JSON, "w", encoding="utf-8"),
              indent=1)

    md = ["# g91 -- the lane, measured", "",
          "Honest book (`research/bt2y_trades.json`), one trade a day = the "
          "first fired-and-traded candidate of the session, exactly as "
          "`g86_honest_ceiling.candidates` defines it. 1R = $1,000.",
          "", "Daily loss limit: **$%.0f**. Funded trailing max drawdown: **$%.0f**." % (a.limit, a.dd), "",
          "## Money", "",
          "| lane | syms | cand/day | first $/day | win | months green | best-of-day $/day |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for r in out:
        md.append("| %s | %d | %.1f | $%.0f | %.1f%% | %s | $%.0f |"
                  % (r["lane"], r["symbols"], r["cands_per_day"],
                     r["first"]["per_day"], r["first"]["win_pct"],
                     r["months_green_first"], r["best"]["per_day"]))
    dd = a.dd
    md += ["", "## Survival -- what a funded account is judged on", "",
           "| lane | max DD (at 1R=$1,000) | green days | best day %% of profit | "
           "max 1R inside $%.0f trailing DD | what it really pays |" % dd,
           "|---|---:|---:|---:|---:|---:|"]
    for r in out:
        p = r["first_path"]
        md.append("| %s | $%.0f | %.1f%% | %s | %s | %s |"
                  % (r["lane"], p["max_dd"], p["green_days_pct"],
                     ("%.1f%%" % p["best_day_pct_of_total"])
                     if p["best_day_pct_of_total"] is not None else "n/a (book loses)",
                     ("$%.0f" % p["max_r_for_dd"]) if p["max_r_for_dd"] else "-",
                     ("$%.2f/day" % p["funded_per_day"])
                     if p["funded_per_day"] is not None else "-"))
    md += ["", "## What each lane is", ""]
    for r in out:
        md.append("- **%s** -- %s" % (r["lane"], r["why"]))
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(md) + "\n")
    print("\n  -> %s\n  -> %s" % (OUT_JSON, OUT_MD))
    demo()


if __name__ == "__main__":
    main()
