"""G7.1 / track `rtarget` -- the money model, in DOLLARS, under one-trade-and-done.

Austin, 2026-08-29:
  "what +r for money should i be targeting? is that the ev or the mean 2r,
   less worried about that and need the financial numbers, but the financial
   numbers if we do the one trade and done strategy."
  "the purpose of this was to make money, thats the simple layer"
  "i want green weeks"
  "i dont have money just credit line so prop firm stocks is my way to a free
   financial life."
  "that i would fail a prop challenge 10 percent of the time"

WHAT THIS IS
------------
A dollar model on top of the ALREADY-SIMULATED two-year book. Nothing is
re-simulated and no engine file is touched. Every trade's R is a property of
that signal alone, so a day policy is pure SELECTION over existing rows --
the same argument `research/g71_firsts_policy.py` makes, and this script
imports that module's candidate stream and causal walk rather than
re-implementing either.

Book: `research/bt2y_trades.json` (backtest_2y.py, 2026-08-29T03:14:29),
500 sessions 2024-08-21 -> 2026-08-21, 76,019 signals, 2,437 traded.

THE TWO ENGINES IN HERE
-----------------------
1. EMPIRICAL BOOTSTRAP -- resample the 496 realised per-DAY R totals of a day
   policy. This is the honest one: it carries the true fat right tail (P1's
   best day is +10.07R) that a two-point +T/-1 model cannot express.
   Two flavours: iid days, and a moving-block bootstrap (block=5 days = one
   trading week) which preserves serial correlation, so P(green week) is not
   quietly assuming independence.
2. PARAMETRIC TWO-POINT -- win w.p. `w` for +T, else -1R, with
   T = (meanR + (1-w)) / w. This exists only so the two SPECIFIED points
   (today's headline 43.1%/+0.5481R and the money gate 55%/2.0R) can be
   priced, since neither is a realised day series. It is optimistic about the
   left tail (real losses average -0.984R, never worse than -1.00R in the
   one-trade stream) and pessimistic about the right (no 10R day exists in a
   two-point model).

DOLLARS
-------
1R = the risk unit in dollars, and it is a FREE VARIABLE here, not $1,000.
`CLAUDE.md` fixes 1R = $1,000 for reporting R-multiples; the whole point of
this track is that the prop floor, not the reporting convention, sets the
unit he can actually trade.

PROP MODEL (Apex $150K EOD, specs from `research/g4_prop_fit.md`)
----------------------------------------------------------------
  eval target +$9,000 | trailing drawdown $4,000, trailed on END-OF-DAY equity
  peaks only | floor locks at start+$100 once profit >= $4,100 | 100% split |
  20 accounts copyable | eval seat has a 30-day expiry.
Fail = EOD equity <= (EOD peak - $4,000). Pass = equity >= +$9,000.
Both a no-time-limit eval and the 30-day (21 trading day) eval are run.

Usage:
  python research/g71_rtarget_model.py                 # full report
  python research/g71_rtarget_model.py --trials 200000 # tighter MC
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "research"))

import g71_firsts_policy as F  # noqa: E402  (candidate stream + causal walk)

TRADING_DAYS_MONTH = 21
TRADING_DAYS_WEEK = 5
TRADING_DAYS_YEAR = 252

# ---- Apex $150K EOD, research/g4_prop_fit.md -------------------------------
PROP_TARGET = 9_000.0
PROP_DD = 4_000.0
PROP_LOCK = 4_100.0          # floor locks at start + $100 once profit >= this
PROP_EVAL_DAYS = 21          # 30 calendar days ~= 21 trading days
PROP_ACCOUNT = 150_000.0


# ---------------------------------------------------------------- day series

def day_series(book_path: Path):
    """Per-DAY R totals for each day policy, over the 496 candidate days.

    Reuses `g71_firsts_policy`'s counted stream (fired&traded, plus halted --
    the 857 rows R31 blocked, which keep every measured field) and its causal
    one-position-at-a-time walk. A day the policy sat out is a 0.0R day, not
    a missing one.
    """
    book = json.loads(book_path.read_text(encoding="utf-8"))
    trades = book["trades"]
    counted = [r for r in trades
               if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
    by_day = defaultdict(list)
    for r in counted:
        by_day[r["day"]].append(r)
    for d in by_day:
        by_day[d].sort(key=F.ekey)
    days = sorted(by_day)

    out = {}
    for name, decide in (("P1", F.P_FIRST), ("P2", F.P_2LOSS), ("P4", F.P_GREEN3)):
        dr, tr, outs, dr_cap = [], [], [], []
        for d in days:
            taken = F.walk(by_day[d], decide)
            dr.append(sum(x["r"] for x in taken))
            # LIVE-PATH CAP: options_sizer.py:25 DEFAULT_RR = 2.0, consumed at
            # :202/:223/:291, and paper_trader.py:132-143 closes the WHOLE
            # position on the 2R touch. There is no scale rung and no runner on
            # the path he would actually trade (research/g71_rrcap.md). Clipping
            # every winner at 2.0R is what that exit books.
            dr_cap.append(sum(min(x["r"], 2.0) for x in taken))
            tr.extend(x["r"] for x in taken)
            outs.extend(x["out"] for x in taken)
        out[name] = {"day_r": dr, "day_r_livecap": dr_cap, "trade_r": tr,
                     "out": outs, "days": days}
    return out, book["meta"]


# ---------------------------------------------------------------- scenarios

class Scenario:
    """A source of per-day R draws."""

    def __init__(self, key, label, kind, day_r=None, w=None, mean_r=None,
                 trades_per_day=1.0, note=""):
        self.key, self.label, self.kind, self.note = key, label, kind, note
        self.day_r = day_r
        self.w, self.mean_r, self.tpd = w, mean_r, trades_per_day
        if kind == "parametric":
            # mean R = w*T - (1-w)  =>  T = (mean R + (1-w)) / w
            self.T = (mean_r + (1.0 - w)) / w
            self.day_mean = mean_r * trades_per_day
            var_tr = w * (self.T - mean_r) ** 2 + (1 - w) * (-1.0 - mean_r) ** 2
            self.day_sd = math.sqrt(var_tr * trades_per_day)
        else:
            self.T = None
            self.day_mean = statistics.mean(day_r)
            self.day_sd = statistics.pstdev(day_r)

    def draw_day(self, rnd):
        if self.kind == "parametric":
            n = self.tpd
            whole, frac = int(n), n - int(n)
            k = whole + (1 if rnd.random() < frac else 0)
            return sum(self.T if rnd.random() < self.w else -1.0 for _ in range(k))
        return rnd.choice(self.day_r)

    def draw_block(self, rnd, length):
        """Moving-block bootstrap: contiguous runs preserve serial correlation."""
        if self.kind == "parametric":
            return [self.draw_day(rnd) for _ in range(length)]
        n = len(self.day_r)
        out = []
        while len(out) < length:
            i = rnd.randrange(n)
            out.extend(self.day_r[(i + j) % n] for j in range(min(5, length - len(out))))
        return out[:length]


# ---------------------------------------------------------------- MC engines

def horizon_stats(sc, ndays, trials, rnd, block=True):
    """Distribution of an ndays-long R total."""
    tot = []
    for _ in range(trials):
        if block:
            tot.append(sum(sc.draw_block(rnd, ndays)))
        else:
            tot.append(sum(sc.draw_day(rnd) for _ in range(ndays)))
    tot.sort()
    n = len(tot)
    return {
        "mean_r": statistics.mean(tot),
        "sd_r": statistics.pstdev(tot),
        "p_green": sum(1 for x in tot if x > 0) / n,
        "p05": tot[int(0.05 * n)],
        "p25": tot[int(0.25 * n)],
        "p50": tot[int(0.50 * n)],
        "p75": tot[int(0.75 * n)],
        "p95": tot[int(0.95 * n)],
    }


def drawdown_stats(sc, ndays, trials, rnd):
    """Max peak-to-trough R over an ndays path, on EOD equity."""
    dds = []
    for _ in range(trials):
        path = sc.draw_block(rnd, ndays)
        eq = peak = dd = 0.0
        for r in path:
            eq += r
            peak = max(peak, eq)
            dd = max(dd, peak - eq)
        dds.append(dd)
    dds.sort()
    n = len(dds)
    return {"p50": dds[n // 2], "p90": dds[int(0.90 * n)],
            "p95": dds[int(0.95 * n)], "p99": dds[int(0.99 * n)],
            "mean": statistics.mean(dds), "all": dds}


def funded_year(sc, risk, trials, rnd, months=12, dd=PROP_DD, lock=PROP_LOCK,
                split=1.0, min_payout=1_000.0, buffer_r=8.0):
    """One funded Apex-style account, 12 months, EOD trailing, monthly payout.

    Floor = EOD peak - dd until cumulative profit reaches `lock`, after which
    the floor is fixed at +$100 (Apex locks it at start+$100).

    `buffer_r` is the WORKING BUFFER, in R, that stays in the account above
    the floor. It is not optional: withdrawing down to the floor itself makes
    the next single losing day fatal with probability 1, so a model without a
    buffer reports a 0% survival rate that is an artefact of the withdrawal
    rule, not of the edge. 8R is the smallest buffer that survives P1's
    realised 11-trade losing run (`research/g71_drawdown.json`
    streaks.max_consec_losing_trades) with room to spare.

    Account dies on a floor breach and stays dead. Returns E[$ withdrawn in
    12 months], P(alive at 12 months), P(dead in month 1), the median.
    """
    keep = 100.0 + buffer_r * risk
    paid, alive, dead1 = [], 0, 0
    for _ in range(trials):
        eq = peak = 0.0
        locked = False
        got = 0.0
        dead_at = None
        for m in range(months):
            for _d in range(TRADING_DAYS_MONTH):
                eq += sc.draw_day(rnd) * risk
                peak = max(peak, eq)
                if not locked and eq >= lock:
                    locked = True
                floor = 100.0 if locked else peak - dd
                if eq <= floor:
                    dead_at = m
                    break
            if dead_at is not None:
                break
            if locked and eq - keep >= min_payout:
                got += (eq - keep) * split
                eq = keep
                peak = max(peak, eq)
        paid.append(got)
        if dead_at is None:
            alive += 1
        elif dead_at == 0:
            dead1 += 1
    paid.sort()
    return {"e_paid_12mo": statistics.mean(paid), "med_paid": paid[len(paid) // 2],
            "p_alive_12mo": alive / trials, "p_dead_month1": dead1 / trials,
            "p05_paid": paid[int(0.05 * trials)], "p95_paid": paid[int(0.95 * trials)]}


def prop_eval(sc, risk, trials, rnd, max_days=None, dd=PROP_DD,
              target=PROP_TARGET):
    """P(fail) on an Apex-style EOD-trailing eval at `risk` dollars per R.

    EOD trailing: the peak that sets the floor only advances at day close, so
    an intraday dip cannot kill the account. Fail when EOD equity <= floor.
    """
    fails = passes = expired = 0
    lens = []
    cap = max_days or 400
    for _ in range(trials):
        eq = peak = 0.0
        for d in range(1, cap + 1):
            eq += sc.draw_day(rnd) * risk
            peak = max(peak, eq)
            if eq <= peak - dd:
                fails += 1
                lens.append(d)
                break
            if eq >= target:
                passes += 1
                lens.append(d)
                break
        else:
            if max_days:
                expired += 1
            else:
                fails += 1
            lens.append(cap)
    n = trials
    return {"p_fail": (fails + expired) / n, "p_blow": fails / n,
            "p_expire": expired / n, "p_pass": passes / n,
            "med_days": sorted(lens)[n // 2]}


def solve_risk_for_fail(sc, tol, trials, rnd, max_days=None, lo=25, hi=3000):
    """Largest $25-grid risk unit whose P(fail) <= tol."""
    best = None
    for risk in range(lo, hi + 1, 25):
        r = prop_eval(sc, float(risk), trials, rnd, max_days=max_days)
        if r["p_fail"] <= tol:
            best = (risk, r)
        elif best is not None:
            break
    return best


# ---------------------------------------------------------------- report

def fmt_money(x):
    return ("-$%s" % f"{abs(x):,.0f}") if x < 0 else ("$%s" % f"{x:,.0f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--book", default="research/bt2y_trades.json")
    ap.add_argument("--trials", type=int, default=60_000)
    ap.add_argument("--seed", type=int, default=84)
    ap.add_argument("--json", default="research/g71_rtarget.json")
    a = ap.parse_args()

    rnd = random.Random(a.seed)
    series, meta = day_series(ROOT / a.book)

    p1, p2 = series["P1"]["day_r"], series["P2"]["day_r"]
    p4 = series["P4"]["day_r"]

    def emp_wr(k):
        o = series[k]["out"]
        w = sum(1 for x in o if x == "win")
        l = sum(1 for x in o if x == "loss")
        return w / (w + l) * 100

    scens = [
        Scenario("today_book", "today's headline book (all signals, ~4.91/day)",
                 "parametric", w=0.431, mean_r=0.5481, trades_per_day=4.91,
                 note="DIRECTION.md 2026-08-29 money row -- NOT one-trade-and-done"),
        Scenario("today_1", "today's headline rate, but ONE trade a day",
                 "parametric", w=0.431, mean_r=0.5481, trades_per_day=1.0,
                 note="apples-to-apples: 43.1%/+0.5481R at 1 trade/day"),
        Scenario("p1", "P1 one trade a day, first signal (MEASURED)",
                 "empirical", day_r=p1,
                 note="54.86% win / +0.6115R per trade, 496 days"),
        Scenario("p1_live", "P1 on the LIVE exit (every winner clipped at 2.0R)",
                 "empirical", day_r=series["P1"]["day_r_livecap"],
                 note="options_sizer DEFAULT_RR=2.0 + whole-position exit; "
                      "research/g71_rrcap.md"),
        Scenario("p2", "P2 first; win=done; 2 losses=done (MEASURED)",
                 "empirical", day_r=p2,
                 note="his sentence literally; 1.42 trades/active day"),
        Scenario("p4", "P4 until net green, 3-loss cap (MEASURED)",
                 "empirical", day_r=p4,
                 note="1.74 trades/active day"),
        Scenario("gate", "the money gate 55% / 2.0R, one trade a day",
                 "parametric", w=0.55, mean_r=2.0, trades_per_day=1.0,
                 note="requires a 5.455R average WINNER"),
        Scenario("mid", "realistic intermediate: 55% win, 1.20R mean, 1/day",
                 "parametric", w=0.55, mean_r=1.20, trades_per_day=1.0,
                 note="P1's win rate held, average winner 1.915R -> 3.0R"),
    ]

    print("=" * 78)
    print("G7.1 / rtarget -- the dollar model under one-trade-and-done")
    print("book:", a.book, meta["generated"], "|", meta["sessions"], "sessions",
          "|", meta["traded"], "traded | trials", f"{a.trials:,}")
    print("=" * 78)

    print("\n--- 0. the measured one-trade-a-day day series -------------------")
    for k, lbl in (("P1", "P1 first signal only"),
                   ("P2", "P2 win=done / 2 losses=done"),
                   ("P4", "P4 until net green, 3-loss cap")):
        tr = series[k]["trade_r"]
        dr = series[k]["day_r"]
        wins = [x for x in tr if x > 0]
        loss = [x for x in tr if x <= 0]
        print(f"  {lbl:34s} n_tr={len(tr):4d}  win%={emp_wr(k):5.2f}  "
              f"meanR/trade={statistics.mean(tr):+.4f}  meanR/day={statistics.mean(dr):+.4f}  "
              f"sd/day={statistics.pstdev(dr):.4f}")
        print(f"  {'':34s} avg winner {statistics.mean(wins):+.4f}R  "
              f"avg loser {statistics.mean(loss):+.4f}R  best day {max(dr):+.2f}R  "
              f"worst day {min(dr):+.2f}R")

    print("\n--- 0b. how much of P1's money is made PAST 2R -------------------")
    tr = series["P1"]["trade_r"]
    over = [x for x in tr if x > 2.0]
    print(f"  trades that ran past 2R: {len(over)} of {len(tr)} = "
          f"{len(over)/len(tr)*100:.2f}%")
    print(f"  R booked ABOVE the 2R line by those trades: "
          f"{sum(x-2.0 for x in over):+.2f}R of {sum(tr):+.2f}R total = "
          f"{sum(x-2.0 for x in over)/sum(tr)*100:.1f}% of all profit")
    capped = [min(x, 2.0) for x in tr]
    print(f"  P1 mean R with every winner clipped at 2.0R: "
          f"{statistics.mean(capped):+.4f}R  (total {sum(capped):+.2f}R)")
    print("  -> the live path (options_sizer.py:25 DEFAULT_RR=2.0, whole position")
    print("     at the 2R touch) books the SECOND number, not the first.")

    print("\n--- 1. DOLLARS per month at 1R = $1,000 --------------------------")
    print(f"  {'scenario':52s} {'E$/day':>9} {'E$/mo':>10} {'sd$/mo':>10} "
          f"{'P(grn mo)':>9} {'P(grn wk)':>9}")
    rows = {}
    for sc in scens:
        mo = horizon_stats(sc, TRADING_DAYS_MONTH, a.trials, rnd)
        wk = horizon_stats(sc, TRADING_DAYS_WEEK, a.trials, rnd)
        rows[sc.key] = {"sc": sc, "mo": mo, "wk": wk}
        print(f"  {sc.label[:52]:52s} {fmt_money(sc.day_mean*1000):>9} "
              f"{fmt_money(mo['mean_r']*1000):>10} {fmt_money(mo['sd_r']*1000):>10} "
              f"{mo['p_green']*100:8.1f}% {wk['p_green']*100:8.1f}%")

    print("\n--- 2. the monthly distribution at 1R = $1,000 (5/25/50/75/95) ---")
    for sc in scens:
        mo = rows[sc.key]["mo"]
        print(f"  {sc.label[:52]:52s} "
              f"{fmt_money(mo['p05']*1000):>9} {fmt_money(mo['p25']*1000):>9} "
              f"{fmt_money(mo['p50']*1000):>9} {fmt_money(mo['p75']*1000):>9} "
              f"{fmt_money(mo['p95']*1000):>9}")

    print("\n--- 3. realised calendar check (no model, the actual 2 years) ----")
    days = series["P1"]["days"]
    for k, fld in (("P1", "day_r"), ("P1-livecap", "day_r_livecap"),
                   ("P2", "day_r"), ("P4", "day_r")):
        dr = dict(zip(days, series[k.split("-")[0]][fld]))
        mon, wk = defaultdict(float), defaultdict(float)
        for d, v in dr.items():
            mon[d[:7]] += v
            wk[F.iso_week(d)] += v
        gm = sum(1 for v in mon.values() if v > 0)
        gw = sum(1 for v in wk.values() if v > 0)
        print(f"  {k}: months green {gm}/{len(mon)} = {gm/len(mon)*100:.1f}%   "
              f"weeks green {gw}/{len(wk)} = {gw/len(wk)*100:.1f}%   "
              f"total {sum(dr.values()):+.1f}R = {fmt_money(sum(dr.values())*1000)}")

    print("\n--- 4. drawdown over a 12-month path (R, then $ at 1R=$1,000) ----")
    print(f"  {'scenario':52s} {'med':>8} {'p90':>8} {'p95':>8} {'p99':>8}")
    dds = {}
    for sc in scens:
        d = drawdown_stats(sc, TRADING_DAYS_YEAR, min(a.trials, 40_000), rnd)
        dds[sc.key] = d
        print(f"  {sc.label[:52]:52s} {d['p50']:7.1f}R {d['p90']:7.1f}R "
              f"{d['p95']:7.1f}R {d['p99']:7.1f}R")
    print("  at 1R = $1,000 the p95 column is, in order: " +
          ", ".join(fmt_money(dds[s.key]['p95'] * 1000) for s in scens))

    print("\n--- 4b. P(12-month max drawdown > X% of a $150k account) ---------")
    print("  columns are the risk unit; rows are the % floor. MEASURED P1 stream.")
    sc = next(s for s in scens if s.key == "p1")
    allr = dds["p1"]["all"]
    n = len(allr)
    print(f"  {'floor':>8} " + " ".join(f"{('$%d/R' % r):>8}"
                                        for r in (250, 350, 500, 750, 1000)))
    for pct in (2, 3, 4, 5, 6, 10):
        usd = PROP_ACCOUNT * pct / 100.0
        cells = [f"{sum(1 for d in allr if d * r > usd)/n*100:6.1f}%"
                 for r in (250, 350, 500, 750, 1000)]
        print(f"  {('%d%% =' % pct):>5}{fmt_money(usd):>4} " +
              " ".join(f"{c:>8}" for c in cells))

    print("\n--- 5. THE PROP QUESTION: 10% failure tolerance ------------------")
    print(f"  Apex $150K EOD: target +{fmt_money(PROP_TARGET)}, "
          f"trailing DD {fmt_money(PROP_DD)} on EOD peaks, lock at "
          f"+{fmt_money(PROP_LOCK)}.")
    print(f"  {'scenario':44s} {'limit':>11} {'risk/trade':>11} {'P(fail)':>8} "
          f"{'P(pass)':>8} {'med days':>9}")
    prop = {}
    for sc in scens:
        for lbl, md in (("no time cap", None), ("30-day eval", PROP_EVAL_DAYS)):
            got = solve_risk_for_fail(sc, 0.10, min(a.trials, 20_000), rnd,
                                      max_days=md)
            if got is None:
                print(f"  {sc.label[:44]:44s} {lbl:>11} {'NONE':>11} "
                      f"{'--':>8} {'--':>8} {'--':>9}   <- no unit >= $25 clears 10%")
                prop[(sc.key, lbl)] = None
                continue
            risk, r = got
            prop[(sc.key, lbl)] = {"risk": risk, **{k: v for k, v in r.items()}}
            print(f"  {sc.label[:44]:44s} {lbl:>11} {'$%d' % risk:>11} "
                  f"{r['p_fail']*100:7.1f}% {r['p_pass']*100:7.1f}% {r['med_days']:>9}")

    print("\n--- 6. P(fail) vs risk unit, the measured P1 stream, no time cap -")
    sc = next(s for s in scens if s.key == "p1")
    print(f"  {'risk/trade':>11} {'P(fail)':>9} {'P(pass)':>9} {'med days':>9} "
          f"{'E$/mo':>10}")
    for risk in (100, 150, 200, 250, 300, 350, 400, 500, 750, 1000, 1500):
        r = prop_eval(sc, float(risk), min(a.trials, 20_000), rnd)
        print(f"  {'$%d' % risk:>11} {r['p_fail']*100:8.1f}% {r['p_pass']*100:8.1f}% "
              f"{r['med_days']:>9} "
              f"{fmt_money(sc.day_mean*risk*TRADING_DAYS_MONTH):>10}")

    print("\n--- 7. ONE FUNDED ACCOUNT, 12 months, money actually withdrawn ---")
    print("  Floor trails on EOD peaks until profit hits +$4,100, then locks at")
    print("  +$100. Month end: everything above a WORKING BUFFER of 8R is")
    print("  withdrawn if it clears $1,000. Dies on a floor breach, stays dead.")
    print(f"  {'scenario':44s} {'$/R':>7} {'E paid 12mo':>12} {'median':>10} "
          f"{'alive@12mo':>11} {'dead in mo1':>12}")
    funded = {}
    for sc in scens:
        for risk in (250, 500):
            fy = funded_year(sc, float(risk), min(a.trials, 20_000), rnd)
            funded[(sc.key, risk)] = fy
            print(f"  {sc.label[:44]:44s} {('$%d' % risk):>7} "
                  f"{fmt_money(fy['e_paid_12mo']):>12} {fmt_money(fy['med_paid']):>10} "
                  f"{fy['p_alive_12mo']*100:10.1f}% {fy['p_dead_month1']*100:11.1f}%")
    print("  NOTE: this is ONE account, gross of the $397 eval and $99 activation,")
    print("  and it ignores Apex's 6-payout ladder ($2,500 -> $5,000) and the 50%")
    print("  consistency rule, both of which slow the first year's withdrawals.")
    print("  For the x20 copy-stack figure use research/g4_prop_fit.md's lifecycle")
    print("  model ($17.4k-$31.8k/mo at 43.0-45.5% win), not this number x20.")

    print("\n--- 7c. the OTHER 10%: losing the FUNDED account inside 12 months -")
    print("  Passing the eval is not the goal; keeping the seat is. Same 10%")
    print("  tolerance applied to P(account dead within 12 months).")
    print(f"  {'scenario':44s} {'$/R':>7} {'P(dead 12mo)':>13} {'E paid 12mo':>12}")
    for sc in scens:
        if sc.key not in ("p1", "p1_live", "p2", "mid"):
            continue
        for risk in (200, 250, 300, 350, 400, 500):
            fy = funded_year(sc, float(risk), min(a.trials, 12_000), rnd)
            mark = "  <- 10% line" if 0.08 <= 1 - fy["p_alive_12mo"] <= 0.12 else ""
            print(f"  {sc.label[:44]:44s} {('$%d' % risk):>7} "
                  f"{(1-fy['p_alive_12mo'])*100:12.1f}% "
                  f"{fmt_money(fy['e_paid_12mo']):>12}{mark}")

    print("\n--- 7b. months to a threshold at 1 trade/day (gross, no ruin) ----")
    print("  E[months] = threshold / E[$ per month]. Ruin is NOT netted here.")
    for sc in scens:
        pr = prop.get((sc.key, "no time cap"))
        if not pr:
            continue
        risk = pr["risk"]
        em = sc.day_mean * risk * TRADING_DAYS_MONTH
        cells = " ".join(f"{thr/em:5.1f}mo" for thr in (2_500, 5_000, 25_000))
        print(f"  {sc.label[:44]:44s} @{('$%d/R' % risk):>8} "
              f"E{fmt_money(em):>9}/mo -> $2.5k/$5k/$25k: {cells}")

    print("\n--- 8. what mean R would 1 trade/day need, per dollar goal -------")
    print(f"  {'goal $/mo':>10} " + " ".join(f"{('$%d/R' % r):>9}"
                                             for r in (250, 350, 500, 1000)))
    for goal in (2_000, 5_000, 10_000, 20_000):
        cells = [f"{goal/(TRADING_DAYS_MONTH*risk):.2f}R" for risk in (250, 350, 500, 1000)]
        print(f"  {fmt_money(goal):>10} " + " ".join(f"{c:>9}" for c in cells))

    out = {
        "book": a.book, "generated": meta["generated"], "trials": a.trials,
        "seed": a.seed,
        "measured": {k: {"n_trades": len(series[k]["trade_r"]),
                         "win_pct": round(emp_wr(k), 2),
                         "mean_r_trade": round(statistics.mean(series[k]["trade_r"]), 4),
                         "mean_r_day": round(statistics.mean(series[k]["day_r"]), 4),
                         "sd_r_day": round(statistics.pstdev(series[k]["day_r"]), 4)}
                     for k in ("P1", "P2", "P4")},
        "scenarios": {sc.key: {
            "label": sc.label, "kind": sc.kind, "note": sc.note,
            "day_mean_r": round(sc.day_mean, 4), "day_sd_r": round(sc.day_sd, 4),
            "avg_winner_needed_R": round(sc.T, 4) if sc.T else None,
            "usd_day_at_1k": round(sc.day_mean * 1000, 0),
            "usd_month_at_1k": round(rows[sc.key]["mo"]["mean_r"] * 1000, 0),
            "usd_month_sd_at_1k": round(rows[sc.key]["mo"]["sd_r"] * 1000, 0),
            "p_green_month": round(rows[sc.key]["mo"]["p_green"], 4),
            "p_green_week": round(rows[sc.key]["wk"]["p_green"], 4),
            "dd12mo_p95_r": round(dds[sc.key]["p95"], 2),
        } for sc in scens},
        "prop_10pct": {f"{k[0]}|{k[1]}": v for k, v in prop.items()},
        "funded_12mo": {f"{k[0]}|{k[1]}": {kk: round(vv, 4)
                                           for kk, vv in v.items()}
                        for k, v in funded.items()},
    }
    (ROOT / a.json).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\nwrote", a.json)


if __name__ == "__main__":
    main()
