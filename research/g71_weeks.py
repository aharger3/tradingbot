"""G7.1 / track `weeks` -- WEEKLY durability as a first-class gate.

Austin, 2026-08-29: "besides green months i want green weeks."

The repo scores durability monthly only (`DIRECTION.md` gate 3, and
`build_bt2y_report.py::stats` -> `greenPct`, which is months-only). A month is
21 sessions; a week is 5. Nothing in the repo had ever reported the weekly
number, so this script computes it, for the shipped book and for every day
policy the `firsts` track defined, and then asks the question behind the
sentence: can "every week green" be bought, and what does it cost.

WHAT IS COMPUTED
----------------
Per policy, over the 105 ISO weeks the two-year book touches:
  * weeks green / total  (green = week R > 0; a week the policy sat out is a
    FLAT week and is not green -- silence is not a win)
  * worst week in R and in dollars (1R = meta.risk_dollars = $1,000)
  * longest run of consecutive red weeks, and of non-green weeks
  * full weekly-R distribution: min/p5/p10/q1/median/q3/p90/p95/max, mean, sd
  * trades per week, expected dollars per week
  * modelled P(green week) from the weekly mean/sd (normal approx) beside the
    observed share, and a Wilson 95% interval on the observed share

TRADE-OFF CURVE
---------------
Two families, both pure SELECTION over rows `backtest_2y.py` already wrote --
nothing is re-simulated, every row's R is fixed at detection:
  * CAP-N: take at most the first N counted signals of each day, one position
    at a time (causal, same entry/exit keys `loss_halt.py` uses). N = 1..24.
    This sweeps trades-per-week without changing WHICH KIND of trade is taken,
    so it isolates count from quality.
  * the `firsts` day policies P0/P0u/P0seq/P1..P5, re-scored weekly.

THE ARITHMETIC THE CURVE IS TESTING
-----------------------------------
If weekly R is a sum of n roughly-independent trades with per-trade mean mu
and sd sigma, then weekly mean = n*mu and weekly sd = sqrt(n)*sigma, so
    P(green week) = Phi(sqrt(n) * mu/sigma).
That RISES with n. Trading less cannot buy green weeks unless the trades you
drop have negative edge. The script measures the realised weekly sd against
this iid prediction to size the intra-week correlation drag, and inverts the
relation to report how many trades a week "every week green" would need.

Usage: python research/g71_weeks.py [--book research/bt2y_trades.json]
Outputs: research/_g71_weeks.json  (+ a printed table)
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Reuse the firsts track's causality keys and policy walker verbatim so the two
# reports cannot drift. g71_firsts_policy defines ekey/xkey/walk/iso_week/P_*
# exactly as loss_halt.py orders the book.
sys.path.insert(0, str(ROOT / "research"))
from g71_firsts_policy import (ekey, xkey, walk, iso_week,  # noqa: E402
                               P_FIRST, P_2LOSS, P_GREEN, P_GREEN3)


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def inv_phi(p):
    lo, hi = -10.0, 10.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def pct(v, q):
    if not v:
        return 0.0
    s = sorted(v)
    i = (len(s) - 1) * q
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (i - lo)


def week_stats(name, taken_by_day, all_weeks, all_months, risk, note=""):
    """Score one policy on the WEEK, with the month kept beside it."""
    rows = [r for d in taken_by_day for r in taken_by_day[d]]
    n = len(rows)
    wins = sum(1 for r in rows if r["out"] == "win")
    losses = sum(1 for r in rows if r["out"] == "loss")
    dec = wins + losses
    total = sum(r["r"] for r in rows)

    day_r = {d: sum(r["r"] for r in taken_by_day[d])
             for d in taken_by_day if taken_by_day[d]}
    wk_r = defaultdict(float)
    wk_n = defaultdict(int)
    mo_r = defaultdict(float)
    for d, v in day_r.items():
        wk_r[iso_week(d)] += v
        mo_r[d[:7]] += v
    for d, rs in taken_by_day.items():
        wk_n[iso_week(d)] += len(rs)

    # A week with no trades is a FLAT week, present in the series at 0.0.
    series = [wk_r.get(w, 0.0) for w in all_weeks]
    counts = [wk_n.get(w, 0) for w in all_weeks]
    green = sum(1 for v in series if v > 0)
    red = sum(1 for v in series if v < 0)
    flat = sum(1 for v in series if v == 0)

    # longest run of consecutive RED weeks, and (stricter, the read that
    # matches "every week green") of consecutive NON-GREEN weeks.
    run = best = 0
    for v in series:
        if v < 0:
            run += 1
            best = max(best, run)
        else:
            run = 0
    run = bestng = 0
    for v in series:
        if v <= 0:
            run += 1
            bestng = max(bestng, run)
        else:
            run = 0

    worst_i = min(range(len(series)), key=lambda i: series[i])
    best_i = max(range(len(series)), key=lambda i: series[i])
    mean_w = statistics.fmean(series)
    sd_w = statistics.pstdev(series) if len(series) > 1 else 0.0

    lo, hi = wilson(green, len(all_weeks))
    per_trade = [r["r"] for r in rows]
    mu = statistics.fmean(per_trade) if per_trade else 0.0
    sg = statistics.pstdev(per_trade) if len(per_trade) > 1 else 0.0
    tpw = n / len(all_weeks)
    sd_iid = sg * math.sqrt(tpw) if sg else 0.0   # iid prediction

    return {
        "policy": name, "note": note,
        "trades": n, "win_rate": round(wins / dec * 100, 2) if dec else 0.0,
        "mean_r_trade": round(mu, 4), "sd_r_trade": round(sg, 4),
        "total_r": round(total, 2),
        "trades_per_week": round(tpw, 2),
        "weeks_total": len(all_weeks),
        "weeks_green": green, "weeks_red": red, "weeks_flat": flat,
        "green_week_pct": round(green / len(all_weeks) * 100, 2),
        "green_week_ci95": [round(lo * 100, 2), round(hi * 100, 2)],
        "worst_week": all_weeks[worst_i],
        "worst_week_r": round(series[worst_i], 2),
        "worst_week_usd": round(series[worst_i] * risk),
        "best_week": all_weeks[best_i],
        "best_week_r": round(series[best_i], 2),
        "max_red_week_streak": best,
        "max_nongreen_week_streak": bestng,
        "mean_week_r": round(mean_w, 4),
        "sd_week_r": round(sd_w, 4),
        "sd_week_iid_pred": round(sd_iid, 4),
        "corr_drag": round(sd_w / sd_iid, 3) if sd_iid else 0.0,
        "week_sharpe": round(mean_w / sd_w, 4) if sd_w else 0.0,
        "p_green_model": round(phi(mean_w / sd_w) * 100, 2) if sd_w else 0.0,
        "usd_per_week": round(mean_w * risk),
        "p_all_weeks_green": (green / len(all_weeks)) ** len(all_weeks),
        "dist_week_r": {
            "min": round(min(series), 2), "p05": round(pct(series, .05), 2),
            "p10": round(pct(series, .10), 2), "q1": round(pct(series, .25), 2),
            "med": round(pct(series, .50), 2), "q3": round(pct(series, .75), 2),
            "p90": round(pct(series, .90), 2), "p95": round(pct(series, .95), 2),
            "max": round(max(series), 2)},
        # How many median weeks it takes to earn the worst week back. A policy
        # that buys its green-week share with a fat left tail (many small
        # greens, rare huge reds) shows up here and nowhere else.
        "median_weeks_to_recover_worst": round(
            abs(min(series)) / pct(series, .50), 2) if pct(series, .50) > 0 else None,
        "green_week_r_total": round(sum(v for v in series if v > 0), 2),
        "red_week_r_total": round(sum(v for v in series if v < 0), 2),
        "months_green": sum(1 for m in all_months if mo_r.get(m, 0.0) > 0),
        "months_total": len(all_months),
        "mean_trades_per_active_week": round(
            statistics.fmean([c for c in counts if c]), 2) if any(counts) else 0.0,
        "weekly_series": [[w, round(v, 3), c]
                          for w, v, c in zip(all_weeks, series, counts)],
    }


def walk_week(days_rows, decide):
    """Walk a WHOLE WEEK one position at a time, day by day.

    `days_rows` is [(day, [rows sorted by entry key]), ...] in date order.
    `decide(state)` -> True to stop for the rest of the WEEK; state is
    (n_taken, wins, losses, scratches, cum_r_week, cum_r_today).

    The one-position-at-a-time key resets each day: `entry_i` is a within-day
    bar index, so comparing it across sessions would be meaningless, and no
    position in this book is held overnight (the window is 09:30-11:00).
    """
    taken = defaultdict(list)
    wins = losses = scr = 0
    cum = 0.0
    for day, rows in days_rows:
        free = None
        today = 0.0
        for c in rows:
            if decide((sum(len(v) for v in taken.values()), wins, losses, scr,
                       cum, today)):
                return taken
            if free is not None and ekey(c) < free:
                continue
            taken[day].append(c)
            free = xkey(c)
            o = c["out"]
            if o == "win":
                wins += 1
            elif o == "loss":
                losses += 1
            else:
                scr += 1
            cum += c["r"]
            today += c["r"]
    return taken


def hist(series, edges):
    out = []
    for i, e in enumerate(edges):
        lo = edges[i - 1] if i else float("-inf")
        out.append(["%s..%s" % ("-inf" if i == 0 else lo, e),
                    sum(1 for v in series if lo <= v < e)])
    out.append(["%s..inf" % edges[-1], sum(1 for v in series if v >= edges[-1])])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="research/bt2y_trades.json")
    ap.add_argument("--out", default="research/_g71_weeks.json")
    a = ap.parse_args()

    book = json.loads((ROOT / a.book).read_text(encoding="utf-8"))
    meta, trades = book["meta"], book["trades"]
    risk = meta.get("risk_dollars", 1000.0)

    counted = [r for r in trades if (r["status"] == "fired" and r["traded"])
               or r["status"] == "halted"]
    shipped = [r for r in trades if r["traded"]]
    fired_any = [r for r in trades if r["status"] in ("fired", "halted")]

    by_day = defaultdict(list)
    for r in counted:
        by_day[r["day"]].append(r)
    for d in by_day:
        by_day[d].sort(key=ekey)

    s_by_day = defaultdict(list)
    for d, rs in by_day.items():
        ss = [r for r in rs if r["sgrade"] == "S"]
        if ss:
            s_by_day[d] = ss
    s_all_by_day = defaultdict(list)
    for r in fired_any:
        if r["sgrade"] == "S":
            s_all_by_day[r["day"]].append(r)
    for d in s_all_by_day:
        s_all_by_day[d].sort(key=ekey)

    all_days = sorted(by_day)
    all_weeks = sorted({iso_week(d) for d in all_days})
    all_months = sorted({d[:7] for d in all_days})

    def group(rows):
        g = defaultdict(list)
        for r in rows:
            g[r["day"]].append(r)
        return g

    def run(stream, decide):
        return {d: walk(rs, decide) for d, rs in stream.items()}

    def W(name, t, note=""):
        return week_stats(name, t, all_weeks, all_months, risk, note)

    pol = []
    pol.append(W("P0 shipped (R31 on, concurrent)", group(shipped),
                 "the book as it ships today"))
    pol.append(W("P0u all counted (R31 off, concurrent)", by_day,
                 "take everything"))
    pol.append(W("P0seq all counted, 1 at a time", run(by_day, lambda s: False),
                 "control: concurrency removed"))
    pol.append(W("P1 first signal only", run(by_day, P_FIRST), ""))
    pol.append(W("P2 first; win=done; 2 losses=done", run(by_day, P_2LOSS),
                 "his sentence"))
    pol.append(W("P3 until day net green (no cap)", run(by_day, P_GREEN), ""))
    pol.append(W("P4 until net green, 3-loss cap", run(by_day, P_GREEN3), ""))
    pol.append(W("P5 P2 on S only (counted)", run(s_by_day, P_2LOSS),
                 "S proxy = downgrade.py sgrade"))
    pol.append(W("P5b P2 on S only (incl legacy-C)", run(s_all_by_day, P_2LOSS), ""))
    orc = {d: [max(rs, key=lambda r: r["r"])] for d, rs in by_day.items()}
    pol.append(W("ORACLE best single trade/day", orc, "look-ahead ceiling"))

    # ---- CAP-N trade-off curve: first N of the day, one position at a time.
    curve = []
    for N in (1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 24):
        t = run(by_day, (lambda n: (lambda s: s[0] >= n))(N))
        curve.append(W("CAP-%d first %d/day, seq" % (N, N), t,
                       "count sweep, quality held fixed"))

    # ---- W-policies: his day rule lifted to the WEEK.
    # "keep trading until you've hit profit" applied to the week: trade
    # sequentially from Monday and stand down for the rest of the week the
    # moment the week is net green. Plus weekly loss caps.
    wk_days = defaultdict(list)
    for d in all_days:
        wk_days[iso_week(d)].append((d, by_day[d]))
    for w in wk_days:
        wk_days[w].sort(key=lambda x: x[0])

    def runw(decide):
        t = defaultdict(list)
        for w, dr in wk_days.items():
            for d, rs in walk_week(dr, decide).items():
                t[d].extend(rs)
        return t

    wpol = []
    W_GREEN = lambda s: s[4] > 0                      # stop the week when green
    wpol.append(W("W1 stop the WEEK when net green", runw(W_GREEN),
                  "his day rule lifted to the week"))
    for cap in (3.0, 5.0, 8.0):
        wpol.append(W("W2-%.0f stop when green or -%.0fR week" % (cap, cap),
                      runw((lambda c: (lambda s: s[4] > 0 or s[4] <= -c))(cap)),
                      "weekly stop-loss"))
    # W3: day rule (P3) AND week rule together
    wpol.append(W("W3 P3 daily + stop week when green",
                  runw(lambda s: s[4] > 0 or s[5] > 0),
                  "stop the day when the day is green, stop the week when green"))

    # ---- what would "every week green" require?
    base = pol[0]
    mu, sg = base["mean_r_trade"], base["sd_r_trade"]
    drag = base["corr_drag"] or 1.0
    req = {}
    for want in (0.50, 0.80, 0.95):
        p_week = want ** (1.0 / len(all_weeks))
        z = inv_phi(p_week)
        # week_sharpe = n*mu / (drag*sigma*sqrt(n)) = sqrt(n)*mu/(drag*sigma)
        n_need = (z * drag * sg / mu) ** 2 if mu > 0 else float("inf")
        req["P(all %d green)>=%.0f%%" % (len(all_weeks), want * 100)] = {
            "p_per_week_needed": round(p_week * 100, 4),
            "week_sharpe_needed": round(z, 3),
            "trades_per_week_needed_at_current_edge": round(n_need, 1),
            "x_current_volume": round(n_need / base["trades_per_week"], 1),
            "mu_over_sigma_needed_at_current_volume": round(
                z * drag / math.sqrt(base["trades_per_week"]), 4),
        }
    req["current_mu_over_sigma"] = round(mu / sg, 4) if sg else 0.0
    req["current_week_sharpe"] = base["week_sharpe"]
    req["corr_drag_used"] = drag

    # ---- paired weekly tests. Green/not-green is a binary outcome on the SAME
    # 105 weeks, so the honest comparison is McNemar's exact test on the
    # discordant weeks, not two independent Wilson intervals.
    def greenvec(r):
        return [1 if v > 0 else 0 for _w, v, _c in r["weekly_series"]]

    def mcnemar(a, b):
        ga, gb = greenvec(a), greenvec(b)
        b01 = sum(1 for x, y in zip(ga, gb) if x == 0 and y == 1)   # b better
        b10 = sum(1 for x, y in zip(ga, gb) if x == 1 and y == 0)   # a better
        n = b01 + b10
        if n == 0:
            return {"a_only": 0, "b_only": 0, "p_exact": 1.0}
        k = min(b01, b10)
        p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        return {"a_only": b10, "b_only": b01, "p_exact": round(min(1.0, p), 5)}

    named = {r["policy"].split()[0]: r for r in pol + wpol + curve}
    pairs = {}
    for other in ("P1", "P2", "P3", "P4", "P5", "P0seq", "P0u", "W1",
                  "W2-5", "W2-8", "CAP-3"):
        if other in named:
            pairs["P0 vs " + other] = mcnemar(base, named[other])
    pairs["CAP-3 vs CAP-8"] = mcnemar(named["CAP-3"], named["CAP-8"])
    pairs["W1 vs W2-8"] = mcnemar(named["W1"], named["W2-8"])

    series0 = [x[1] for x in base["weekly_series"]]
    out = {
        "meta": {
            "book": a.book,
            "generated_book": meta["generated"],
            "first": meta["first"], "last": meta["last"],
            "risk_dollars": risk,
            "weeks": len(all_weeks), "months": len(all_months),
            "candidate_days": len(all_days),
            "counted_stream": len(counted), "shipped_traded": len(shipped),
            "week_def": ("ISO week of the session date; a week with no trade is "
                         "flat (0R) and NOT green"),
            "policies_source": "research/g71_firsts_policy.py (walk/ekey/xkey/P_*)",
        },
        "policies": pol,
        "week_policies": wpol,
        "capn_curve": curve,
        "every_week_green_requirement": req,
        "paired_weekly_mcnemar": pairs,
        "shipped_week_hist": hist(series0, [-20, -10, -5, -2, 0, 2, 5, 10, 20, 40]),
        "shipped_nongreen_weeks": sorted(
            [[w, round(v, 2), round(v * risk), c]
             for w, v, c in base["weekly_series"] if v <= 0],
            key=lambda x: x[1]),
    }
    (ROOT / a.out).write_text(json.dumps(out, indent=1), encoding="utf-8")

    hdr = ("policy", "trades", "t/wk", "wk green", "%grn", "worstR",
           "worst $", "redrun", "medR", "sdR", "Shrp", "$/wk", "mo")
    print("%-38s %6s %6s %8s %6s %8s %9s %6s %7s %7s %6s %8s %6s" % hdr)
    for r in pol + wpol + curve:
        print("%-38s %6d %6.2f %4d/%-3d %5.1f%% %8.2f %9.0f %6d %7.2f %7.2f %6.2f %8.0f %3d/%-2d"
              % (r["policy"], r["trades"], r["trades_per_week"],
                 r["weeks_green"], r["weeks_total"], r["green_week_pct"],
                 r["worst_week_r"], r["worst_week_usd"],
                 r["max_red_week_streak"], r["dist_week_r"]["med"],
                 r["sd_week_r"], r["week_sharpe"], r["usd_per_week"],
                 r["months_green"], r["months_total"]))
    print()
    print(json.dumps(req, indent=1))
    print()
    print("paired McNemar (green weeks): " + json.dumps(pairs))
    print("shipped weekly-R histogram: " + json.dumps(out["shipped_week_hist"]))
    print("shipped non-green weeks: " + json.dumps(out["shipped_nongreen_weeks"]))
    print("wrote %s" % (ROOT / a.out))


if __name__ == "__main__":
    main()
