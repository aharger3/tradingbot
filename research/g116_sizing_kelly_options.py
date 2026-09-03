"""g116 -- POSITION SIZING, DERIVED. Risk-per-trade vs prop-eval, Kelly, and the
options floor on a $1,000 account.

Austin, 2026-09-03: the bar is PASS ONE PROP EVALUATION within 12 months, the
headline is EV per trade in R, and position sizing is to be DERIVED.

EV/R does not move with sizing. PASS/FAIL does. This file answers four things
for the arms that survived tonight's adversarial rechecks:

  1. risk/trade 0.25%..3% of account -> PASS/FAIL and WHICH RULE breaks first
  2. full Kelly and quarter Kelly from each arm's own R distribution, against
     what the drawdown constraint actually allows
  3. the options floor: ONE contract, priced off the only real option tape in
     this repo (research/t7_alpaca_cache.json, real Alpaca 0DTE 1-min bars)
  4. the honest verdict on $1,000

Every arm is built on MASTER_SPEC's unit: the FIRST SIZE-GATED candidate of the
session (gate inside selection, substitute the next candidate), 498 sessions.
Nothing is imported from the mid-edit engine files except signal_runner's floor,
via research/omen_metrics.py.
"""
from __future__ import annotations
import json
import math
import os
import statistics
import sys
from collections import defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import (ev_r_scoreboard, evaluate_prop_challenge,
                          min_risk_floor, MIN_RISK_FLOOR_SOURCE)

BOOK = os.path.join(HERE, "bt2y_trades_retest_on.json")
TAPE = os.path.join(HERE, "t7_alpaca_cache.json")
DELTA = 0.5           # options_sizer.DEFAULT_DELTA -- ATM
MULT = 100            # contract multiplier


def load_rows():
    b = json.load(open(BOOK))
    rows = [r for r in b["trades"] if r.get("traded") and r.get("r") is not None]
    rows.sort(key=lambda r: (r["day"], r["et"], r["sym"]))
    return rows


def sizeable(r):
    return abs(r["entry"] - r["stop"]) >= min_risk_floor(r["entry"])


def is_1d(r):
    return r.get("level") in ("PDH", "PDL") or str(r.get("level_tf", "")).strip() == "1D"


ARMS = {
    "A_base": ("first size-gated candidate of the day (SHIPPED unit)",
               lambda r: True),
    "B_no1D": ("A, veto prior-day levels (PDH/PDL)",
               lambda r: not is_1d(r)),
    "C_no1D_noThu": ("B, and skip Thursdays",
                     lambda r: (not is_1d(r)) and r["dow"] != "Thu"),
    "D_nochase": ("A, veto chase (stop wider than 0.5% of price)",
                  lambda r: "chase" not in r.get("downgrades", [])),
}


def build_arm(rows, keep):
    byday = defaultdict(list)
    for r in rows:
        byday[r["day"]].append(r)
    out = []
    for day in sorted(byday):
        for r in byday[day]:
            if sizeable(r) and keep(r):
                out.append(r)
                break
    return out


def months_between(d0, d1):
    a = date(*map(int, d0.split("-")))
    b = date(*map(int, d1.split("-")))
    return (b - a).days / 30.4375


def prop_row(arm, risk_dollars, account=50000.0, **kw):
    pnl = [(r["day"], r["r"] * risk_dollars) for r in arm]
    res = evaluate_prop_challenge(pnl, account_size=account, **kw)
    res["risk_dollars"] = risk_dollars
    return res


def pass_day(arm, risk_dollars, account=50000.0, **kw):
    """The day a PASSing curve first clears -- replay prefixes."""
    for i in range(1, len(arm) + 1):
        r = prop_row(arm[:i], risk_dollars, account, **kw)
        if r["passed"]:
            return arm[i - 1]["day"], i
    return None, None


def kelly_from_sample(Rs, hi=2.0, iters=300):
    """Growth-optimal fraction of account risked per trade (per 1R of risk),
    maximising E[log(1 + f*R)] on the arm's OWN empirical R distribution."""
    worst = min(Rs)
    cap = hi if worst >= 0 else min(hi, 0.999 / abs(worst))

    def g(f):
        s = 0.0
        for r in Rs:
            v = 1 + f * r
            if v <= 0:
                return -1e18
            s += math.log(v)
        return s / len(Rs)

    a, b = 0.0, cap
    for _ in range(iters):
        m1 = a + (b - a) / 3
        m2 = b - (b - a) / 3
        if g(m1) < g(m2):
            a = m1
        else:
            b = m2
    f = (a + b) / 2
    return f if g(f) > 0 else 0.0


def kelly_two_outcome(win, avg_w, avg_l):
    if avg_l <= 0:
        return float("inf")
    b = avg_w / avg_l
    f_units = (win * b - (1 - win)) / b
    return f_units / avg_l


def load_tape():
    d = json.load(open(TAPE))
    out = []
    for k, v in d.items():
        if not v:
            continue
        sym, day, et, direction, px = k.split("|")
        out.append(dict(sym=sym, day=day, et=et, dir=direction, px=float(px),
                        strike=v["strike"], prem=v["entry_premium"]))
    return out


RISK_PCTS = [0.0025, 0.005, 0.0075, 0.01, 0.0125, 0.015, 0.02, 0.025, 0.03]


def main():
    rows = load_rows()
    tape = load_tape()
    out = {"meta": {"book": os.path.basename(BOOK), "rows_traded": len(rows),
                    "min_risk_floor_source": MIN_RISK_FLOOR_SOURCE,
                    "tape_real_prints": len(tape)}}
    print("min_risk_floor from:", MIN_RISK_FLOOR_SOURCE)
    print("book traded rows:", len(rows), "| real 0DTE option prints:", len(tape))

    arms = {}
    print("\n=== ARMS (spec unit: first SIZE-GATED candidate of the session) ===")
    hdr = ("%-14s %4s %8s %6s %6s %6s %5s %8s %8s %7s"
           % ("arm", "n", "EV/R", "win%", "avgW", "avgL", "PF", "totR", "maxDD_R", "green"))
    print(hdr)
    for key, (desc, keep) in ARMS.items():
        a = build_arm(rows, keep)
        sb = ev_r_scoreboard(a, size_gate=False)
        arms[key] = dict(rows=a, sb=sb, desc=desc)
        print("%-14s %4d %+8.4f %6.2f %6.3f %6.3f %5.2f %+8.2f %8.2f %7s"
              % (key, sb["n"], sb["ev_r"], sb["win_rate"] * 100, sb["avg_win_R"],
                 sb["avg_loss_R"], sb["profit_factor"], sb["total_R"],
                 sb["max_drawdown_R"], sb["months_green"]))
        out.setdefault("arms", {})[key] = dict(
            desc=desc, n=sb["n"], ev_r=sb["ev_r"], win_rate=sb["win_rate"],
            avg_win_R=sb["avg_win_R"], avg_loss_R=sb["avg_loss_R"],
            profit_factor=sb["profit_factor"], total_R=sb["total_R"],
            max_drawdown_R=sb["max_drawdown_R"], months_green=sb["months_green"],
            r_stability=sb["r_stability"])

    # ---------------- 1. risk sweep -------------------------------------
    print("\n=== 1. RISK PER TRADE vs PROP EVAL ===")
    print("$50k account, 8% target / 4% trailing DD / 2% daily loss / 5 min days"
          " / 30% consistency, dd_mode=eod")
    out["risk_sweep"] = {}
    for key in ARMS:
        a = arms[key]["rows"]
        d0 = a[0]["day"]
        print("\n-- %s: %s   (n=%d)" % (key, arms[key]["desc"], len(a)))
        print("   %6s %8s %7s %26s %12s %6s %9s %8s"
              % ("risk%", "$/trade", "verdict", "first rule broken", "on day",
                 "months", "finalEq%", "maxDD%"))
        rowsout = []
        for rp in RISK_PCTS:
            risk = rp * 50000.0
            res = prop_row(a, risk)
            if res["passed"]:
                pd_, pi = pass_day(a, risk)
                mo = months_between(d0, pd_) if pd_ else None
                verdict, when, why = "PASS", pd_, "-"
            else:
                mo = months_between(d0, res["fail_day"]) if res["fail_day"] else None
                verdict, when, why = "FAIL", res["fail_day"], res["fail_reason"]
            print("   %5.2f%% %8.0f %7s %26s %12s %6s %8.2f%% %7.2f%%"
                  % (rp * 100, risk, verdict, str(why or "-"), str(when or "-"),
                     ("%.1f" % mo) if mo else "-",
                     res["final_equity_pct"], res["max_drawdown_seen_pct"]))
            rowsout.append(dict(risk_pct=rp, risk_dollars=risk, passed=res["passed"],
                                rule=why, day=when, months=mo,
                                final_equity_pct=res["final_equity_pct"],
                                max_dd_pct=res["max_drawdown_seen_pct"]))
        out["risk_sweep"][key] = rowsout

    # ---------------- 2. Kelly ------------------------------------------
    print("\n=== 2. KELLY vs THE DRAWDOWN CONSTRAINT ===")
    print("f = fraction of account risked per trade (per 1R). Kelly from the arm's"
          " own empirical R sample, E[log(1+fR)] maximised.")
    print("   %-14s %10s %10s %10s %12s %10s" %
          ("arm", "fullKelly", "1/4 Kelly", "2-outcome", "eval allows", "K/eval"))
    out["kelly"] = {}
    for key in ARMS:
        a = arms[key]["rows"]
        Rs = [r["r"] for r in a]
        sb = arms[key]["sb"]
        fk = kelly_from_sample(Rs)
        qk = fk / 4
        k2 = kelly_two_outcome(sb["win_rate"], sb["avg_win_R"], sb["avg_loss_R"])
        # what the eval allows: largest risk% in a fine grid that still PASSES
        allowed = None
        for rp in [x / 10000.0 for x in range(5, 401, 5)]:
            if prop_row(a, rp * 50000.0)["passed"]:
                allowed = rp
        ratio = (fk / allowed) if allowed else None
        print("   %-14s %9.2f%% %9.2f%% %9.2f%% %11s %10s"
              % (key, fk * 100, qk * 100, k2 * 100,
                 ("%.2f%%" % (allowed * 100)) if allowed else "NONE",
                 ("%.1fx" % ratio) if ratio else "-"))
        out["kelly"][key] = dict(full_kelly=fk, quarter_kelly=qk,
                                 two_outcome_kelly=k2, eval_max_risk_pct=allowed,
                                 kelly_over_eval=ratio)

    # ---------------- 3. the options floor ------------------------------
    print("\n=== 3. THE OPTIONS FLOOR -- ONE CONTRACT ===")
    prem_pct = [t["prem"] / t["px"] for t in tape]
    prem_pct.sort()
    med_pct = statistics.median(prem_pct)
    print("real 0DTE ATM prints: n=%d  premium as %% of spot: p10 %.3f%%  median %.3f%%"
          "  p90 %.3f%%  (median premium $%.2f on median spot $%.2f)"
          % (len(tape), prem_pct[int(.1 * len(prem_pct))] * 100, med_pct * 100,
             prem_pct[int(.9 * len(prem_pct))] * 100,
             statistics.median(t["prem"] for t in tape),
             statistics.median(t["px"] for t in tape)))
    out["tape"] = dict(n=len(tape), median_prem_pct_of_spot=med_pct,
                       p10=prem_pct[int(.1 * len(prem_pct))],
                       p90=prem_pct[int(.9 * len(prem_pct))],
                       median_prem=statistics.median(t["prem"] for t in tape),
                       median_spot=statistics.median(t["px"] for t in tape))

    print("\n   ONE contract on each arm's own trades. premium_risk = stock_risk x"
          " delta 0.5 (options_sizer). cost = premium x 100.")
    print("   %-14s %10s %10s %10s %12s %12s %12s"
          % ("arm", "med $risk", "min $risk", "max $risk", "med $cost", "cost>$1000",
             "risk%of$1k"))
    out["options_floor"] = {}
    for key in ARMS:
        a = arms[key]["rows"]
        risks = sorted(abs(r["entry"] - r["stop"]) * DELTA * MULT for r in a)
        costs = sorted(r["entry"] * med_pct * MULT for r in a)
        over = sum(1 for c in costs if c > 1000)
        med_risk = statistics.median(risks)
        print("   %-14s %10.2f %10.2f %10.2f %12.2f %11d%% %11.1f%%"
              % (key, med_risk, risks[0], risks[-1], statistics.median(costs),
                 round(100 * over / len(costs)), med_risk / 1000 * 100))
        out["options_floor"][key] = dict(
            med_risk_1ct=med_risk, min_risk_1ct=risks[0], max_risk_1ct=risks[-1],
            med_cost_1ct=statistics.median(costs),
            pct_cost_over_1000=100 * over / len(costs),
            med_risk_pct_of_1k=med_risk / 1000 * 100)

    # ---------------- 4. the $1,000 account -----------------------------
    print("\n=== 4. THE HONEST VERDICT ON $1,000 ===")
    print("   at ONE contract, risk/trade = the arm's own median premium risk."
          " Worst drawdown in R x that dollar risk, against the account.")
    print("   %-14s %10s %10s %12s %12s %10s"
          % ("arm", "risk$/tr", "risk%acct", "maxDD_R", "worstDD$", "survives"))
    out["thousand"] = {}
    for key in ARMS:
        a = arms[key]["rows"]
        sb = arms[key]["sb"]
        med_risk = out["options_floor"][key]["med_risk_1ct"]
        dd = abs(sb["max_drawdown_R"]) * med_risk
        surv = dd < 1000
        print("   %-14s %10.2f %9.1f%% %12.2f %12.0f %10s"
              % (key, med_risk, med_risk / 1000 * 100, sb["max_drawdown_R"], dd,
                 "YES" if surv else "NO"))
        out["thousand"][key] = dict(risk_per_trade=med_risk,
                                    risk_pct_of_1k=med_risk / 1000 * 100,
                                    max_dd_R=sb["max_drawdown_R"], worst_dd_dollars=dd,
                                    survives_1k=surv)

    json.dump(out, open(os.path.join(HERE, "g116_sizing_kelly_options.json"), "w"),
              indent=1)
    print("\nwrote research/g116_sizing_kelly_options.json")
    return arms, rows, tape, out


if __name__ == "__main__":
    main()
