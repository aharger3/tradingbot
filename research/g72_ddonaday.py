"""G7.2 / ddonaday -- the disaster stop, measured UNDER ONE TRADE A DAY.

THE GAP THIS CLOSES
-------------------
`research/g71_board.md` §2 item 2 and §6 both price the resting disaster order
across ALL 2,437 trades. But the policy Austin is actually going to run is one
position at a time, one-ish trade a day. A change that helps the average trade
does not have to help the FIRST trade of the day, and nobody had checked.

So: re-run the day policies on two already-simulated books that differ ONLY in
the resting disaster order, and read the answer off the same day calendar.

THE ARMS -- already on disk, nothing is re-simulated here
---------------------------------------------------------
    research/_g71s_S0_shipped.json   resting order at -1.00R  (what Austin
                                     ratified on the morning of 2026-08-29)
    research/_g71s_D_off.json        no resting order; the close-only rule,
                                     clamped at -1.25R by stop_rule
    research/_g71s_D_125.json        resting order pushed out to -1.25R
                                     (the middle option in board item #2)

All three were produced by `research/g71_stops.py run` within seven minutes of
each other (14:59-15:06 on 2026-08-29) from the SAME engine state, each a full
`backtest_2y.main` replay. They are a clean paired set. Every stop fill in them
came from `stop_rule.stop_fill_price()`; this script computes no fill, no exit
and no R -- it only SELECTS which of the already-scored rows a day policy would
have entered.

    !! `research/bt2y_trades.json` on disk is NO LONGER the board's book.
       The board describes 76,019 setups / 2,437 trades; the file was rebuilt
       at 17:06 by another track and now reads 134,012 / 4,508. That is why
       this script reads the g71_stops arms instead: S0_shipped (76,035 /
       2,436) IS the board's book to within one trade, and it is the only
       disaster-stop-ON book that has a disaster-stop-OFF twin.

THE POLICIES -- Austin's two candidates, plus context
-----------------------------------------------------
    P1  first trade of the day, then done                      (context)
    P2  first; a win ends the day; two losses end the day      (a)
    P4  keep going until the day is net green, 3-loss cap      (b)

(b) also carries the -$2,000 daily floor named in the board: the day stops as
soon as cumulative P&L is at or below -2.0R. Both a capped and an uncapped
reading of (b) are printed, because the floor and the 3-loss cap almost never
bind at the same time and it matters which one is doing the work.

CAUSALITY, CANDIDATE STREAM AND SCORING are `research/g71_firsts_policy.py`'s,
imported rather than copied: `walk`, `ekey`, `xkey`, `score`, `iso_week`. The
candidate stream is the R31-off counted stream (`fired & traded` plus
`halted`), because a day policy REPLACES the engine's two-loss halt.

FAIRNESS
--------
The three arms do not produce candidates on exactly the same days. Every
per-day and drawdown number here is computed over the UNION of candidate days
across the three arms, so the denominators match and a day one arm sits out is
a flat day rather than a missing one.

MEASURE ONLY. This script changes no engine file and no default. Austin has
not decided the disaster stop, and deleting it reverses what he ratified.

Usage:
    python research/g72_ddonaday.py                 # table + research/_g72_ddonaday.json
    python research/g72_ddonaday.py --report        # also writes the .md
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from g71_firsts_policy import ekey, xkey, iso_week, score, walk  # noqa: E402

RISK = 1000.0          # 1R = $1,000  (CLAUDE.md)
DAYS_PER_MONTH = 21    # the board's convention for $/month

ARMS = [
    ("keep it, resting at -$1,000 (ratified 29 Aug)", "S0_shipped"),
    ("delete the resting order (close-only, -$1,250 clamp)", "D_off"),
    ("push it out to -$1,250", "D_125"),
]

KEEP = ("entry_i", "bars", "et", "sym", "day", "out", "r", "status",
        "traded", "sgrade")


# ------------------------------------------------------------------ policies
# `walk`'s decide(state) sees (n_taken, wins, losses, scratches, cum_r).
P_FIRST = lambda s: s[0] >= 1                                   # noqa: E731
P_2LOSS = lambda s: s[1] >= 1 or s[2] >= 2                      # noqa: E731
P_GREEN3 = lambda s: s[4] > 0 or s[2] >= 3                      # noqa: E731
P_GREEN3F = lambda s: s[4] > 0 or s[2] >= 3 or s[4] <= -2.0     # noqa: E731

POLICIES = [
    ("P1  first trade only, then done", P_FIRST),
    ("(a) first; a win ends the day; 2 losses end the day", P_2LOSS),
    ("(b) until green, 3-loss cap", P_GREEN3),
    ("(b+) until green, 3-loss cap AND -$2,000 day floor", P_GREEN3F),
]


def load_arm(arm):
    path = os.path.join(HERE, "_g71s_%s.json" % arm)
    with open(path, encoding="utf-8") as fh:
        book = json.load(fh)
    meta = book["meta"]
    counted, shipped = [], []
    for r in book["trades"]:
        st, tr = r["status"], r["traded"]
        if (st == "fired" and tr) or st == "halted":
            counted.append({k: r[k] for k in KEEP})
        if tr:
            shipped.append({k: r[k] for k in KEEP})
    by_day = defaultdict(list)
    for r in counted:
        by_day[r["day"]].append(r)
    for d in by_day:
        by_day[d].sort(key=ekey)
    return meta, by_day, shipped


def group(rows):
    g = defaultdict(list)
    for r in rows:
        g[r["day"]].append(r)
    return g


def dayvec(taken_by_day):
    return {d: sum(x["r"] for x in rs) for d, rs in taken_by_day.items() if rs}


def enrich(row, taken_by_day, all_days):
    """Add the dollar reads and the worst-day the board asks for."""
    v = dayvec(taken_by_day)
    worst_day = min([v.get(d, 0.0) for d in all_days] or [0.0])
    row = dict(row)
    row["dollars_per_day"] = round(row["mean_r_day_all"] * RISK, 2)
    row["dollars_per_month"] = round(row["mean_r_day_all"] * RISK * DAYS_PER_MONTH, 2)
    row["dollars_total"] = round(row["total_r"] * RISK, 2)
    row["worst_drawdown_usd"] = round(row["max_dd_r"] * RISK, 2)
    row["worst_day_usd"] = round(worst_day * RISK, 2)
    row["green_days_pct"] = (round(row["green_days"] / row["days_traded"] * 100, 1)
                             if row["days_traded"] else 0.0)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_g72_ddonaday.json"))
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    arms = {}
    for label, key in ARMS:
        meta, by_day, shipped = load_arm(key)
        arms[key] = {"label": label, "meta": meta, "by_day": by_day,
                     "shipped": shipped}

    # one shared calendar so every $/day denominator is the same
    all_days = sorted(set().union(*[set(a_["by_day"]) for a_ in arms.values()]))
    all_months = sorted({d[:7] for d in all_days})
    all_weeks = sorted({iso_week(d) for d in all_days})

    rows, takes = [], {}
    for _label, key in ARMS:
        A = arms[key]
        # context: the whole book as that arm ships it, all signals concurrent
        r0 = score("P0  whole book, all signals at once", group(A["shipped"]),
                   all_days, all_months, all_weeks, A["label"])
        r0["arm"] = key
        r0["arm_label"] = A["label"]
        rows.append(enrich(r0, group(A["shipped"]), all_days))
        for pname, decide in POLICIES:
            taken = {d: walk(rs, decide) for d, rs in A["by_day"].items()}
            takes[(key, pname)] = taken
            r = score(pname, taken, all_days, all_months, all_weeks, A["label"])
            r["arm"] = key
            r["arm_label"] = A["label"]
            rows.append(enrich(r, taken, all_days))

    # ---- paired, per-day: does deleting the order beat its own error bar?
    paired = {}
    for pname, _ in POLICIES:
        base = dayvec(takes[("S0_shipped", pname)])
        for key in ("D_off", "D_125"):
            v = dayvec(takes[(key, pname)])
            diffs = [v.get(d, 0.0) - base.get(d, 0.0) for d in all_days]
            m = statistics.fmean(diffs)
            se = statistics.pstdev(diffs) / (len(diffs) ** 0.5)
            paired["%s | %s vs shipped" % (pname, key)] = {
                "mean_day_delta_r": round(m, 4),
                "mean_day_delta_usd": round(m * RISK, 2),
                "se_usd": round(se * RISK, 2),
                "t": round(m / se, 2) if se else 0.0,
                "beats_2se": bool(abs(m) > 2 * se),
            }

    # ---- per-TRADE delta, the number the board quoted across all trades
    per_trade = {}
    for pname, _ in POLICIES:
        for key in ("S0_shipped", "D_off", "D_125"):
            rs = [x for d in sorted(takes[(key, pname)])
                  for x in takes[(key, pname)][d]]
            per_trade.setdefault(pname, {})[key] = {
                "trades": len(rs),
                "usd_per_trade": round(statistics.fmean([x["r"] for x in rs]) * RISK, 2),
            }

    # ---- IS IT THE SAME TRADE? The three arms are three separate replays, so
    # a disaster stop can change the day's path and therefore which signals
    # exist at all. For the FIRST trade of the day it should not: nothing has
    # happened yet. If the first trade is the same signal on every day, then
    # P1's delta is a pure fill difference and not a different book.
    same = {}
    for key in ("D_off", "D_125"):
        base = {d: rs[0] for d, rs in takes[("S0_shipped", "P1  first trade only, then done")].items() if rs}
        other = {d: rs[0] for d, rs in takes[(key, "P1  first trade only, then done")].items() if rs}
        shared = sorted(set(base) & set(other))
        ident = sum(1 for d in shared
                    if (base[d]["sym"], base[d]["et"], base[d]["entry_i"])
                    == (other[d]["sym"], other[d]["et"], other[d]["entry_i"]))
        diff_r = [round(other[d]["r"] - base[d]["r"], 4) for d in shared
                  if (base[d]["sym"], base[d]["et"], base[d]["entry_i"])
                  == (other[d]["sym"], other[d]["et"], other[d]["entry_i"])
                  and abs(other[d]["r"] - base[d]["r"]) > 1e-9]
        flip = sum(1 for d in shared
                   if (base[d]["sym"], base[d]["et"], base[d]["entry_i"])
                   == (other[d]["sym"], other[d]["et"], other[d]["entry_i"])
                   and base[d]["out"] == "loss" and other[d]["out"] == "win")
        same[key] = {
            "days_both_arms_trade": len(shared),
            "same_first_signal": ident,
            "first_trade_R_changed": len(diff_r),
            "loss_becomes_win": flip,
            "mean_R_change_where_changed": (round(statistics.fmean(diff_r), 4)
                                            if diff_r else 0.0),
        }

    meta = {
        "what": "the resting disaster order, priced under one-trade-a-day",
        "first_trade_identity": same,
        "risk_dollars": RISK, "days_per_month": DAYS_PER_MONTH,
        "calendar_days": len(all_days), "months": len(all_months),
        "weeks": len(all_weeks),
        "arms": {k: {"label": v["label"],
                     "generated": v["meta"]["generated"],
                     "signals": v["meta"]["signals"],
                     "traded_as_shipped": v["meta"]["traded"],
                     "halted_by_R31": v["meta"]["halted"],
                     "counted_stream": sum(len(x) for x in v["by_day"].values()),
                     "candidate_days": len(v["by_day"])}
                 for k, v in arms.items()},
        "paired_vs_shipped": paired,
        "per_trade": per_trade,
        "source": "research/g71_stops.py arms S0_shipped / D_off / D_125; "
                  "policy walk imported from research/g71_firsts_policy.py",
        "caveat": "research/bt2y_trades.json was rebuilt at 17:06 by another "
                  "track (134,012 signals / 4,508 traded) and is no longer the "
                  "board's book; S0_shipped is.",
    }

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "rows": rows}, fh, indent=1)

    hdr = ("policy", "arm", "trades", "win%", "$/day", "$/mo", "mo", "wk",
           "green d", "worst DD", "worst day")
    print("%-52s %-12s %7s %7s %8s %9s %6s %7s %8s %10s %10s" % hdr)
    for r in rows:
        print("%-52s %-12s %7d %6.1f%% %8.0f %9.0f %2d/%-3d %3d/%-3d %7.1f%% %10.0f %10.0f"
              % (r["policy"], r["arm"], r["trades"], r["win_rate"],
                 r["dollars_per_day"], r["dollars_per_month"],
                 r["months_green"], r["months_total"], r["weeks_green"],
                 r["weeks_total"], r["green_days_pct"],
                 -r["worst_drawdown_usd"], r["worst_day_usd"]))
    print()
    print(json.dumps(meta, indent=1))
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
