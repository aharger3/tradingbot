"""G7.2 / buffer_math -- what $10,000 and a 0% APR credit line actually buy.

Everything here is in DOLLARS and MONTHS. Inputs, all measured elsewhere:

  research/bt2y_trades.json   the 2-year book (meta.risk_dollars = 1000,
                              500 sessions 2024-08-21 -> 2026-08-21, 2,437
                              traded + 857 halted = 3,294 counted rows).
  research/g71_firsts.md      the day policies P1..P4. Austin's rule is P3/P4:
                              "trade the first one; if it wins we're done; keep
                              trading until the day is green."
  research/g71_instrument.md  friction per trade in R, by instrument.
  research/g71_propfirm.md    the firm table.

THE ONE IDEA THIS SCRIPT ADDS: risk-per-trade is not a free parameter. It is
  risk_$ = notional * stop_pct
and notional is capped by the account's buying power. A Trade The Pool "$50,000"
account IS $50,000 of buying power (tradethepool.com/the-program/, 2026-08-29),
so on the book's median stop of 0.223% the most that account can ever risk on one
trade is $111.50. Dollars per month are therefore a property of the ACCOUNT SIZE,
not of a risk setting. Every path below is priced that way, per trade, using each
row's own stop_pct -- no fixed-$-per-trade fiction.

Run: python research/g72_buffer_math.py [--trials 20000]
"""
from __future__ import annotations

import argparse, json, math, statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
BOOK = ROOT / "research" / "bt2y_trades.json"

TRADING_DAYS_PER_MONTH = 21.0

# ---------------------------------------------------------------- policies
# copied deliberately from research/g71_firsts_policy.py so this script is
# reproducible on its own (CLAUDE.md: "if you publish a number, commit the
# script that made it"). Same keys, same causality rule.


def ekey(r):
    return (r["entry_i"], r["et"], r["sym"])


def xkey(r):
    return (r["entry_i"] + r["bars"], r["et"], r["sym"])


def walk(cands, decide):
    taken, free = [], None
    wins = losses = scr = 0
    cum = 0.0
    for c in cands:
        if decide((len(taken), wins, losses, scr, cum)):
            break
        if free is not None and ekey(c) < free:
            continue
        taken.append(c)
        free = xkey(c)
        o = c["out"]
        if o == "win":
            wins += 1
        elif o == "loss":
            losses += 1
        else:
            scr += 1
        cum += c["r"]
    return taken


P_FIRST = lambda s: s[0] >= 1
P_2LOSS = lambda s: s[1] >= 1 or s[2] >= 2
P_GREEN = lambda s: s[4] > 0
P_GREEN3 = lambda s: s[4] > 0 or s[2] >= 3


def load_days():
    book = json.loads(BOOK.read_text(encoding="utf-8"))
    counted = [r for r in book["trades"]
               if (r["status"] == "fired" and r["traded"]) or r["status"] == "halted"]
    by_day = defaultdict(list)
    for r in counted:
        by_day[r["day"]].append(r)
    for d in by_day:
        by_day[d].sort(key=ekey)
    return book["meta"], by_day


def policy_days(by_day, decide):
    """-> list of days; each day is a list of (r, stop_pct, entry_px, outcome)."""
    out = []
    for d in sorted(by_day):
        rows = walk(by_day[d], decide)
        out.append([(x["r"], x["stop_pct"] / 100.0, x["entry"], x["out"]) for x in rows])
    return out


# ---------------------------------------------------------------- $ per day

def day_dollar_series(days, bp, risk_cap_frac, comm=None, friction_r=0.0,
                      loss_tail=None, rng=None):
    """Dollar P&L per day for one pass over the 496 real days.

    bp             account buying power (max notional on one position)
    risk_cap_frac  never risk more than this fraction of bp on one trade
    comm           callable(shares, notional) -> $ round-trip, or None
    friction_r     spread cost in R per trade (subtracted from every trade)
    loss_tail      (prob, lo, hi): with prob, a losing trade's R is multiplied
                   into U(lo, hi) instead of resting at its booked value --
                   the "the stop did not hold" stress. Applied on |R| basis.
    """
    risk_cap = bp * risk_cap_frac
    out = []
    n_capped = n_trades = 0
    for day in days:
        tot = 0.0
        for (r, sp, px, o) in day:
            notional = min(bp, risk_cap / sp) if sp > 0 else bp
            if notional >= bp - 1e-9:
                n_capped += 1
            n_trades += 1
            risk_d = notional * sp
            eff_r = r - friction_r
            if loss_tail and eff_r < 0 and rng is not None:
                p, lo, hi = loss_tail
                if rng.random() < p:
                    eff_r = -abs(rng.uniform(lo, hi))
            pnl = eff_r * risk_d
            if comm is not None:
                pnl -= comm(notional / px if px else 0.0, notional)
            tot += pnl
        out.append(tot)
    return np.array(out), (n_capped / n_trades if n_trades else 0.0), n_trades


def ttp_commission(shares, notional):
    """1/2 cent per share, min $0.75 per filled order (tradethepool.com program
    terms, 2026-08-29). The book scales out, so count 1 entry + 2 exits."""
    per_order = max(0.75, 0.005 * shares / 3.0)
    return 3.0 * per_order


def retail_share_commission(shares, notional):
    """tastytrade: $0 commission on stock. SEC fee 0.0000278 of sale proceeds +
    TAF $0.000166/share sold, capped $8.30 (tastytrade fee schedule 2026-07-30)."""
    return notional * 0.0000278 + min(8.30, shares * 0.000166)


# ---------------------------------------------------------------- prop sim

def sim_prop(day_pnl, spec, months, trials, rng, fee, buffer0=10000.0):
    """Walk an eval -> funded -> payout loop day by day, in dollars.

    spec: dict with target, daily_loss_limit, max_loss (static from start),
          min_days, payout_min, payout_gap_days, split.
    Returns dict of outcomes.
    """
    n_days = int(months * TRADING_DAYS_PER_MONTH)
    target = spec["target"]; dll = spec["dll"]; mloss = spec["max_loss"]
    min_days = spec["min_days"]; pmin = spec["payout_min"]
    pgap = spec["payout_gap_days"]; split = spec["split"]

    paid = np.zeros(trials); spent = np.zeros(trials)
    first_payout_day = np.full(trials, -1)
    passed_day = np.full(trials, -1)
    n_evals = np.zeros(trials)
    busted_funded = np.zeros(trials)

    idx = rng.integers(0, len(day_pnl), size=(trials, n_days))
    draws = day_pnl[idx]
    if dll is not None:
        draws = np.maximum(draws, -dll)

    for t in range(trials):
        phase = "eval"; bal = 0.0; days_in = 0; since_payout = 0
        spent[t] += fee; n_evals[t] += 1
        for d in range(n_days):
            x = draws[t, d]
            bal += x
            days_in += 1
            if phase == "funded":
                since_payout += 1
            if bal <= -mloss:                      # blown
                if phase == "funded":
                    busted_funded[t] += 1
                spent[t] += fee; n_evals[t] += 1
                phase = "eval"; bal = 0.0; days_in = 0; since_payout = 0
                if spent[t] > buffer0:
                    break
                continue
            if phase == "eval" and bal >= target and days_in >= min_days:
                phase = "funded"; bal = 0.0; days_in = 0; since_payout = 0
                if passed_day[t] < 0:
                    passed_day[t] = d
                continue
            if phase == "funded" and bal >= pmin and since_payout >= pgap:
                paid[t] += bal * split
                if first_payout_day[t] < 0:
                    first_payout_day[t] = d
                bal = 0.0; since_payout = 0
    return dict(paid=paid, spent=spent, first_payout_day=first_payout_day,
                passed_day=passed_day, n_evals=n_evals,
                busted_funded=busted_funded)


# ---------------------------------------------------------------- self sim

def sim_self(days, months, trials, rng, start_equity, leverage, risk_cap_frac,
             comm, friction_r, loss_tail, min_equity_frac=0.10):
    """Compounding self-funded account. Notional cap = equity * leverage.

    Sizing is recomputed off live equity each day, so the account shrinks its
    own size on the way down -- the friendliest possible ruin assumption.
    """
    n_days = int(months * TRADING_DAYS_PER_MONTH)
    eq = np.full(trials, float(start_equity))
    lo = np.full(trials, float(start_equity))
    dead = np.zeros(trials, dtype=bool)
    m1 = np.zeros(trials)
    day_idx = rng.integers(0, len(days), size=(trials, n_days))
    for t in range(trials):
        for d in range(n_days):
            if dead[t]:
                break
            day = days[day_idx[t, d]]
            bp = eq[t] * leverage
            risk_cap = eq[t] * risk_cap_frac
            tot = 0.0
            for (r, sp, px, o) in day:
                notional = min(bp, risk_cap / sp) if sp > 0 else bp
                risk_d = notional * sp
                eff_r = r - friction_r
                if loss_tail and eff_r < 0:
                    p, plo, phi = loss_tail
                    if rng.random() < p:
                        eff_r = -abs(rng.uniform(plo, phi))
                tot += eff_r * risk_d
                if comm is not None:
                    tot -= comm(notional / px if px else 0.0, notional)
            eq[t] += tot
            lo[t] = min(lo[t], eq[t])
            if d == int(TRADING_DAYS_PER_MONTH) - 1:
                m1[t] = eq[t] - start_equity
            if eq[t] <= start_equity * min_equity_frac:
                dead[t] = True
                eq[t] = max(eq[t], 0.0)
    return dict(equity=eq, low=lo, dead=dead, month1=m1)


def pct(a, p):
    return float(np.percentile(a, p))


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=8000)
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--out", default="research/_g72_buffer_math.json")
    a = ap.parse_args()
    rng = np.random.default_rng(72)
    meta, by_day = load_days()

    pol = {
        "P1 first only": policy_days(by_day, P_FIRST),
        "P2 win=done, 2 losses=done": policy_days(by_day, P_2LOSS),
        "P3 until green": policy_days(by_day, P_GREEN),
        "P4 until green, 3-loss cap": policy_days(by_day, P_GREEN3),
    }
    report = {"meta": meta, "policies": {}}

    print("=== 0. THE R-TO-DOLLAR BRIDGE ===")
    sps = sorted(r["stop_pct"] / 100.0 for d in by_day.values() for r in d)
    for q in (10, 25, 50, 75, 90, 99):
        v = np.percentile(sps, q)
        print("  stop_pct p%-2d %.4f%%   -> notional for $1,000 of risk $%9s"
              % (q, v * 100, "{:,.0f}".format(1000 / v)))
    report["stop_pct_pctiles"] = {str(q): float(np.percentile(sps, q))
                                  for q in (10, 25, 50, 75, 90, 99)}
    print("  MEDIAN 0.223%% -> a $50,000-buying-power account can risk at most"
          " $%.2f on the median setup." % (50000 * np.median(sps)))

    for name, days in pol.items():
        n = sum(len(d) for d in days)
        rs = [r for d in days for (r, s, p, o) in d]
        print("  %-28s %4d trades over %d days (%.2f/day), mean %+.4fR"
              % (name, n, len(days), n / len(days), statistics.mean(rs)))
        report["policies"][name] = dict(trades=n, days=len(days),
                                        per_day=round(n / len(days), 3),
                                        mean_r=round(statistics.mean(rs), 4))

    P4 = pol["P4 until green, 3-loss cap"]
    P1 = pol["P1 first only"]

    # ---------------------------------------------------------- section 1
    print("\n=== 1. WHAT EACH ACCOUNT SIZE PAYS, PER MONTH, GROSS AND NET ===")
    print("  Trade The Pool FLEX day. Headline number = BUYING POWER. Sizing:")
    print("  full BP, never more than 0.5%% of BP of risk on one trade.")
    print("  Commission 1/2c per share, $0.75 min per order, 3 orders/trade.\n")
    print("  %-10s %10s %12s %12s %12s %12s" %
          ("BP", "risk/trade", "gross $/mo", "net 70%/mo", "DLL", "maxloss"))
    rows_acct = []
    for bp, price in ((5000, 59), (25000, 120), (50000, 285),
                      (100000, 545), (200000, 1475)):
        s, capfrac, ntr = day_dollar_series(P4, bp, 0.005, comm=ttp_commission)
        gross = s.mean() * TRADING_DAYS_PER_MONTH
        med_risk = bp * min(0.005, np.median(sps))
        rows_acct.append(dict(bp=bp, price=price, risk=round(med_risk, 2),
                              gross_mo=round(gross, 2), net_mo=round(gross * 0.7, 2),
                              day_mean=round(float(s.mean()), 2),
                              day_sd=round(float(s.std()), 2),
                              bp_capped_frac=round(capfrac, 3)))
        print("  $%-9s %10s %12s %12s %12s %12s" %
              ("{:,}".format(bp), "${:,.0f}".format(med_risk),
               "${:,.0f}".format(gross), "${:,.0f}".format(gross * 0.7),
               "${:,.0f}".format(bp * 0.02), "${:,.0f}".format(bp * 0.04)))
    report["ttp_accounts"] = rows_acct
    need = 5000 / (rows_acct[2]["net_mo"] / 50000)
    print("\n  -> $5,000/month NET needs about $%s of buying power." %
          "{:,.0f}".format(need))
    report["bp_for_5k_net"] = round(need, 0)

    # ---------------------------------------------------------- section 2
    print("\n=== 2. PATH A -- ONE PROP CHALLENGE, $10k STAYS IN THE BANK ===")
    specs = {
        "TTP 50k FLEX ($285)": dict(bp=50000, fee=285, target=3000, dll=1000,
                                    max_loss=2000, min_days=10, payout_min=300,
                                    payout_gap_days=10, split=0.70),
        "TTP 100k FLEX ($545)": dict(bp=100000, fee=545, target=6000, dll=2000,
                                     max_loss=4000, min_days=10, payout_min=300,
                                     payout_gap_days=10, split=0.70),
        "TTP 200k FLEX ($1,475)": dict(bp=200000, fee=1475, target=12000,
                                       dll=4000, max_loss=8000, min_days=10,
                                       payout_min=300, payout_gap_days=10,
                                       split=0.70),
        "TTP 25k FLEX ($120)": dict(bp=25000, fee=120, target=1500, dll=500,
                                    max_loss=1000, min_days=10, payout_min=300,
                                    payout_gap_days=10, split=0.70),
    }
    report["paths"] = {}
    print("  %-24s %10s %10s %10s %10s %10s %8s" %
          ("account", "pass d(med)", "1st pay", "12mo paid", "p10 paid",
           "fees", "P(ruin)"))
    for nm, sp in specs.items():
        s, _, _ = day_dollar_series(P4, sp["bp"], 0.005, comm=ttp_commission)
        o = sim_prop(s, sp, a.months, a.trials, rng, sp["fee"])
        pd_ = o["passed_day"]; fp = o["first_payout_day"]
        pass_med = np.median(pd_[pd_ >= 0]) if (pd_ >= 0).any() else float("nan")
        fp_med = np.median(fp[fp >= 0]) if (fp >= 0).any() else float("nan")
        ruin = float((o["spent"] > 10000).mean())
        print("  %-24s %10s %10s %10s %10s %10s %8.2f%%" %
              (nm,
               "%.0f" % pass_med if pass_med == pass_med else "never",
               "%.0f" % fp_med if fp_med == fp_med else "never",
               "${:,.0f}".format(o["paid"].mean()),
               "${:,.0f}".format(pct(o["paid"], 10)),
               "${:,.0f}".format(o["spent"].mean()), 100 * ruin))
        report["paths"]["A " + nm] = dict(
            pass_day_median=None if pass_med != pass_med else float(pass_med),
            first_payout_day_median=None if fp_med != fp_med else float(fp_med),
            paid_12mo_mean=round(float(o["paid"].mean()), 2),
            paid_12mo_p10=round(pct(o["paid"], 10), 2),
            paid_12mo_p50=round(pct(o["paid"], 50), 2),
            paid_12mo_p90=round(pct(o["paid"], 90), 2),
            fees_mean=round(float(o["spent"].mean()), 2),
            evals_mean=round(float(o["n_evals"].mean()), 2),
            funded_busts_mean=round(float(o["busted_funded"].mean()), 3),
            p_buffer_gone=ruin)

    print("\n  Same, but the stop does NOT hold: 5%% of losing trades slip to")
    print("  between -1.25R and -3.0R (CLAUDE.md's floor, then past it).")
    for nm in ("TTP 50k FLEX ($285)", "TTP 200k FLEX ($1,475)"):
        sp = specs[nm]
        s, _, _ = day_dollar_series(P4, sp["bp"], 0.005, comm=ttp_commission,
                                    loss_tail=(0.05, 1.25, 3.0), rng=rng)
        o = sim_prop(s, sp, a.months, a.trials, rng, sp["fee"])
        pd_ = o["passed_day"]
        pm = np.median(pd_[pd_ >= 0]) if (pd_ >= 0).any() else float("nan")
        print("    %-22s pass day med %5s   12mo paid $%-9s  fees $%-7s"
              % (nm, "%.0f" % pm if pm == pm else "never",
                 "{:,.0f}".format(o["paid"].mean()),
                 "{:,.0f}".format(o["spent"].mean())))
        report["paths"]["A-stress " + nm] = dict(
            paid_12mo_mean=round(float(o["paid"].mean()), 2),
            fees_mean=round(float(o["spent"].mean()), 2),
            evals_mean=round(float(o["n_evals"].mean()), 2))

    # ---------------------------------------------------------- section 3
    print("\n=== 3. PATH B -- N CHALLENGES IN PARALLEL ===")
    print("  The accounts trade the SAME signal on the SAME days, so their")
    print("  outcomes are the same draw. Correlation is 1, not 0.")
    sp = specs["TTP 50k FLEX ($285)"]
    s50, _, _ = day_dollar_series(P4, 50000, 0.005, comm=ttp_commission)
    o1 = sim_prop(s50, sp, a.months, a.trials, rng, sp["fee"])
    base_pass = float((o1["passed_day"] >= 0).mean())
    print("  P(one $50k FLEX reaches funded inside %d months) = %.3f"
          % (a.months, base_pass))
    print("  independent-attempts fiction: 1-(1-p)^N")
    print("  correlated reality:           p, for every N")
    for N in (1, 2, 3, 5):
        print("    N=%d   fiction %.4f   reality %.4f   fee outlay $%s"
              % (N, 1 - (1 - base_pass) ** N, base_pass,
                 "{:,}".format(285 * N)))
    report["paths"]["B"] = dict(p_pass_single=base_pass,
                                fiction={str(N): 1 - (1 - base_pass) ** N
                                         for N in (1, 2, 3, 5)},
                                reality=base_pass)

    # ---------------------------------------------------------- section 4
    print("\n=== 4. PATHS C & D -- SELF-FUNDED $10,000 ===")
    print("  PDT is gone (FINRA RN 26-10, effective 2026-06-04; tastytrade")
    print("  day-one). So a $10k account may day-trade. Leverage below is")
    print("  broker day-trading buying power, which is now intraday-margin set.")
    print("\n  %-34s %10s %10s %10s %10s %8s" %
          ("path", "mo1 mean", "12mo med", "12mo p10", "12mo p90", "P(ruin)"))
    self_rows = []
    for label, lev, capf, comm, fric, tail in (
        ("C shares, cash 1:1, $0.01 spread", 1.0, 0.02, retail_share_commission,
         0.0342, (0.02, 1.25, 3.0)),
        ("C shares, 2:1", 2.0, 0.02, retail_share_commission, 0.0342,
         (0.02, 1.25, 3.0)),
        ("C shares, 4:1", 4.0, 0.02, retail_share_commission, 0.0342,
         (0.02, 1.25, 3.0)),
        ("C shares, 4:1, $0.02 spread", 4.0, 0.02, retail_share_commission,
         0.0683, (0.02, 1.25, 3.0)),
        ("D 0DTE, 2% risk, $0.01 spread", 4.0, 0.02, None, 0.1412,
         (0.043, 1.25, 7.9)),
        ("D 0DTE, 2% risk, $0.02 spread", 4.0, 0.02, None, 0.2041,
         (0.043, 1.25, 7.9)),
        ("D 0DTE, 2% risk, $0.05 spread", 4.0, 0.02, None, 0.3929,
         (0.043, 1.25, 7.9)),
        ("D 0DTE, 5% risk, $0.02 spread", 4.0, 0.05, None, 0.2041,
         (0.043, 1.25, 7.9)),
    ):
        o = sim_self(P4, a.months, min(a.trials, 4000), rng, 10000.0, lev,
                     capf, comm, fric, tail)
        eq = o["equity"]
        print("  %-34s %10s %10s %10s %10s %7.1f%%" %
              (label, "${:,.0f}".format(o["month1"].mean()),
               "${:,.0f}".format(np.median(eq)),
               "${:,.0f}".format(pct(eq, 10)),
               "${:,.0f}".format(pct(eq, 90)), 100 * o["dead"].mean()))
        self_rows.append(dict(path=label, month1_mean=round(float(o["month1"].mean()), 2),
                              eq12_med=round(float(np.median(eq)), 2),
                              eq12_p10=round(pct(eq, 10), 2),
                              eq12_p90=round(pct(eq, 90), 2),
                              p_ruin=round(float(o["dead"].mean()), 4),
                              p_half=round(float((eq < 5000).mean()), 4)))
    report["paths"]["CD"] = self_rows

    print("\n  NOTE ON PATH D SIZING: a 2%-of-equity risk on a 0DTE ATM needs a")
    print("  cash debit about 8.1x the risk (research/g71_instrument.md: median")
    print("  $8,068 of debit to risk $1,000). On $10,000 of equity, 2% = $200 of")
    print("  risk = $1,613 of debit -- affordable. 5%% risk = $500 = $4,034 of")
    print("  debit, 40%% of the account in one 0DTE position.")

    # ---------------------------------------------------------- section 5
    print("\n=== 5. PATH E -- PROP + A SMALL SELF-FUNDED OPTIONS ACCOUNT ===")
    sp = specs["TTP 50k FLEX ($285)"]
    s, _, _ = day_dollar_series(P4, 50000, 0.005, comm=ttp_commission)
    oA = sim_prop(s, sp, a.months, a.trials, rng, sp["fee"])
    oD = sim_self(P4, a.months, min(a.trials, 4000), rng, 3000.0, 4.0, 0.02,
                  None, 0.2041, (0.043, 1.25, 7.9))
    tot = oA["paid"].mean() - oA["spent"].mean() + (oD["equity"].mean() - 3000)
    print("  TTP 50k FLEX ($285 fee, $9,715 stays liquid) + $3,000 0DTE sleeve")
    print("    prop 12mo paid  $%s   fees $%s" %
          ("{:,.0f}".format(oA["paid"].mean()), "{:,.0f}".format(oA["spent"].mean())))
    print("    sleeve 12mo P&L $%s   P(sleeve zeroed) %.1f%%   worst-case loss $3,000"
          % ("{:,.0f}".format(oD["equity"].mean() - 3000), 100 * oD["dead"].mean()))
    print("    combined mean   $%s     buffer still intact $%s"
          % ("{:,.0f}".format(tot), "{:,.0f}".format(10000 - 285 - 3000)))
    report["paths"]["E"] = dict(
        prop_paid=round(float(oA["paid"].mean()), 2),
        prop_fees=round(float(oA["spent"].mean()), 2),
        sleeve_pl=round(float(oD["equity"].mean() - 3000), 2),
        sleeve_ruin=round(float(oD["dead"].mean()), 4),
        combined=round(float(tot), 2))

    # ---------------------------------------------------------- section 6
    print("\n=== 6. MONTHS TO $5,000/MONTH ===")
    net_per_bp = rows_acct[2]["net_mo"] / 50000.0
    print("  measured: net $%.4f per $1 of buying power per month (P4, 0.5%%"
          % net_per_bp)
    print("  risk cap, 1/2c commission). Income is LINEAR in BP and the eval")
    print("  fee is a rounding error, so the buffer's job is to buy the")
    print("  BIGGEST account he can pass, not the cheapest.\n")
    print("  %-24s %8s %10s %12s %14s" %
          ("ladder", "fee", "net $/mo", "months to 5k", "buffer left"))
    for lab, bp_, fee_ in (("start $50k FLEX", 50000, 285),
                           ("start $100k FLEX", 100000, 545),
                           ("start $200k FLEX", 200000, 1475)):
        net = bp_ * net_per_bp
        print("  %-24s %8s %10s %12s %14s" %
              (lab, "${:,}".format(fee_), "${:,.0f}".format(net),
               "never (cap)" if net < 5000 else "~2 (pass+payout)",
               "${:,.0f}".format(10000 - fee_)))
    print("\n  TTP hard ceilings on running ONE signal across MANY accounts:")
    print("   * total base buying power across all evals <= $450,000")
    print("   * copy trading (same position within 30 min in another account)")
    print("     is allowed between 2 accounts ONLY, and only among $5k/$25k/$50k")
    print("     -- and a $50k may not pair with another $50k.")
    print("   -> a robot firing the same signal into two accounts IS copy")
    print("      trading by their definition. Legal maxima on one signal:")
    print("      ONE $200k FLEX ($7,077/mo net), or a $50k+$25k pair")
    print("      ($%s/mo net). The single $200k wins."
          % "{:,.0f}".format(75000 * net_per_bp))
    report["net_per_bp_per_month"] = round(net_per_bp, 6)
    report["legal_max_bp_one_signal"] = 200000

    # ---------------------------------------------------------- section 7
    print("\n=== 7. THE REAL RUIN DRIVER: THE BACKTEST BEING WRONG ===")
    print("  Every zero above comes from a book that never books worse than")
    print("  -1.000R, fills at the mid, and never misses a fill. Sections 2-5")
    print("  are the arithmetic IF that holds. This is the arithmetic if it")
    print("  does not: subtract a flat haircut h from every trade's R.")
    print("  P4 books +0.5166R/trade, so h=0.52 is a dead strategy.\n")
    print("  %6s %9s | %-30s | %-30s" %
          ("h", "mean R", "PROP $200k FLEX (12mo)", "SELF $10k shares 4:1 (12mo)"))
    print("  %6s %9s | %10s %9s %8s | %10s %9s %8s" %
          ("", "", "paid", "fees", "P(pass)", "median eq", "p10", "P(<$5k)"))
    deg = []
    sp200 = specs["TTP 200k FLEX ($1,475)"]
    for h in (0.0, 0.15, 0.30, 0.45, 0.5166, 0.65, 0.80):
        s, _, _ = day_dollar_series(P4, 200000, 0.005, comm=ttp_commission,
                                    friction_r=h)
        o = sim_prop(s, sp200, a.months, a.trials, rng, 1475)
        pp = float((o["passed_day"] >= 0).mean())
        os_ = sim_self(P4, a.months, min(a.trials, 2500), rng, 10000.0, 4.0,
                       0.02, retail_share_commission, 0.0342 + h,
                       (0.02, 1.25, 3.0))
        eq = os_["equity"]
        print("  %6.2f %9.4f | %10s %9s %7.1f%% | %10s %9s %7.1f%%" %
              (h, 0.5166 - h, "${:,.0f}".format(o["paid"].mean()),
               "${:,.0f}".format(o["spent"].mean()), 100 * pp,
               "${:,.0f}".format(np.median(eq)), "${:,.0f}".format(pct(eq, 10)),
               100 * float((eq < 5000).mean())))
        deg.append(dict(h=h, mean_r=round(0.5166 - h, 4),
                        prop_paid=round(float(o["paid"].mean()), 2),
                        prop_fees=round(float(o["spent"].mean()), 2),
                        prop_p_pass=round(pp, 4),
                        prop_p_buffer_gone=round(float((o["spent"] > 10000).mean()), 4),
                        self_eq_med=round(float(np.median(eq)), 2),
                        self_eq_p10=round(pct(eq, 10), 2),
                        self_p_ruin=round(float(os_["dead"].mean()), 4),
                        self_p_half=round(float((eq < 5000).mean()), 4)))
    report["degradation"] = deg
    print("\n  The asymmetry is the whole answer: on the prop path a dead")
    print("  strategy costs FEES. On the self-funded path it costs the BUFFER.")

    (ROOT / a.out).write_text(json.dumps(report, indent=1, default=float),
                              encoding="utf-8")
    print("\nwrote %s" % a.out)


if __name__ == "__main__":
    main()
