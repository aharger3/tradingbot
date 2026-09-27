"""Payout planning calculator (PAPER/SIM only - no orders, no live data).

Given a firm's funded-account payout rules and daily equity paths, report:
first-payout session distribution, request size, 30% tax set-aside, net to the
lessons fund, and cumulative payouts over 120 funded sessions at 1 vs 5 copied
accounts.

Equity paths come from either
  * the g/sizing-mc rig (same R shape, 12/10/6 MNQ ladder, $2K EOD trail) -
    mc_all.csv holds only per-ladder summaries, so paths are regenerated here
    from the inputs documented in 07-money/omen/g/sizing-mc.md; or
  * the paper journal (research/paper_journal/*.jsonl, `usd` summed per date).

Usage:
  python research/payout_plan.py [--paths 4000] [--journal FILE] [--md OUT.md]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

START = 50_000.0
TRAIL = 2_000.0      # EOD trailing drawdown (sizing-mc: Lucid $2K trail)
LOCK = 100.0         # trail locks at start + $100
H_FUND = 120         # funded sessions modeled
TAX = 0.30           # gig-taxes.md: set aside 25-30% of every 1099 payout
COPIES = 5           # u06 / pass-plan-by-firm: up to 5 accounts on the copier


@dataclass(frozen=True)
class FirmRules:
    name: str
    days_per_request: int      # qualifying days needed before each request
    min_day_profit: float      # a day qualifies if its P&L >= this
    max_frac: float            # request <= max_frac * profit above start
    cap: float                 # per-request dollar cap
    split: float               # trader share of the request
    max_payouts: int | None    # after this many payouts the account moves to live


# Lucid: every 5 profitable days, <=50% of profit, <=$2K/request, 90/10, 5 payouts -> live.
# min_day_profit $150 matches the g/sizing-mc funded rig ("5 days >= $150").
LUCID = FirmRules("LucidFlex 50K", 5, 150.0, 0.50, 2_000.0, 0.90, 5)
# Topstep XFA: 5 days >= $150, <=50% of balance (XFA balance = profit above start), $5K cap, 90/10.
TOPSTEP = FirmRules("Topstep 50K XFA", 5, 150.0, 0.50, 5_000.0, 0.90, None)


def simulate_payouts(daily_pnl, rules: FirmRules, start: float = START,
                     trail: float = TRAIL, lock: float = LOCK):
    """Walk one daily P&L path through the payout rules.

    Returns a list of dicts {session (1-based), gross, trader, tax, net}.
    Stops on an EOD trail breach or when max_payouts is reached (moved to live).
    """
    bal, hi, floor = start, start, start - trail
    days = 0
    out = []
    for i, pnl in enumerate(daily_pnl, start=1):
        bal += float(pnl)
        if bal <= floor:
            break                                   # account lost
        hi = max(hi, bal)
        floor = max(floor, min(hi - trail, start + lock))
        if pnl >= rules.min_day_profit:
            days += 1
        profit = bal - start
        if days >= rules.days_per_request and profit > 0:
            gross = min(rules.max_frac * profit, rules.cap)
            trader = gross * rules.split
            tax = trader * TAX
            out.append({"session": i, "gross": gross, "trader": trader,
                        "tax": tax, "net": trader - tax})
            bal -= gross
            days = 0
            if rules.max_payouts and len(out) >= rules.max_payouts:
                break                               # moves to live; out of model
    return out


# ---- equity paths from the g/sizing-mc rig (inputs cited in sizing-mc.md) ----
WIN_R, LOSS_R, THRU_R = 1.95, -1.14, -2.3       # target / stop / stop-through
SH_FLAT, SH_THRU = 0.06, 0.014
LADDER = (12, 10, 6)                            # MNQ cts at profit <1K / 1-2K / >=2K
PT, COMM, STOP_MED = 2.0, 1.24, 21.0            # $/pt MNQ, RT comm, median stop pts


def p_win(mu):
    """Win share of all trades that gives mean R = mu (flat ~0R)."""
    rest = 1 - SH_FLAT - SH_THRU
    return (mu - SH_THRU * THRU_R - rest * LOSS_R) / (WIN_R - LOSS_R)


def rig_paths(n_paths: int, mu: float, se: float = 0.127, freq: float = 0.25,
              sessions: int = H_FUND, seed: int = 7):
    """(n_paths, sessions) daily P&L; <=1 trade/session, sized by profit tier."""
    rng = np.random.default_rng(seed)
    pw = np.clip(p_win(mu + rng.normal(0, se, n_paths)), 0.02, 1 - SH_FLAT - SH_THRU - 0.02)
    trade = rng.random((n_paths, sessions)) < freq
    u = rng.random((n_paths, sessions))
    r = np.where(u < SH_FLAT, 0.0,
        np.where(u < SH_FLAT + SH_THRU, THRU_R,
        np.where(u < SH_FLAT + SH_THRU + pw[:, None], WIN_R, LOSS_R)))
    stop = np.clip(np.exp(rng.normal(np.log(STOP_MED), 0.45, (n_paths, sessions))), 6, 70)
    pnl = np.zeros((n_paths, sessions))
    prof = np.zeros(n_paths)          # profit since last payout proxy for tier choice
    for s in range(sessions):
        n = np.where(prof < 1000, LADDER[0], np.where(prof < 2000, LADDER[1], LADDER[2]))
        day = np.where(trade[:, s], n * (r[:, s] * stop[:, s] * PT - COMM), 0.0)
        pnl[:, s] = day
        prof += day
    return pnl


def journal_path(jsonl_file):
    """Daily P&L (one entry per journal date, sorted) from confirmed trades."""
    by_day = defaultdict(float)
    with open(jsonl_file, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                row = json.loads(line)
                if row.get("confirmed", True):
                    by_day[row["date"]] += float(row.get("usd", 0.0))
    return [by_day[d] for d in sorted(by_day)]


def summarize(paths, rules: FirmRules):
    runs = [simulate_payouts(p, rules) for p in paths]
    first = np.array([r[0]["session"] for r in runs if r])
    req = np.array([r[0]["gross"] for r in runs if r])
    cum = np.array([sum(x["net"] for x in r) for r in runs])
    pct = (lambda a, q: float(np.percentile(a, q)) if len(a) else float("nan"))
    return {
        "firm": rules.name, "n": len(runs), "paid": len(first) / max(len(runs), 1),
        "first_p25": pct(first, 25), "first_p50": pct(first, 50), "first_p75": pct(first, 75),
        "req_p50": pct(req, 50), "trader_p50": pct(req, 50) * rules.split,
        "tax_p50": pct(req, 50) * rules.split * TAX, "net_p50": pct(req, 50) * rules.split * (1 - TAX),
        "cum1_mean": float(cum.mean()) if len(cum) else 0.0,
        "cum1_p50": pct(cum, 50),
        "cum5_mean": float(cum.mean()) * COPIES if len(cum) else 0.0,
        "n_pay_mean": float(np.mean([len(r) for r in runs])) if runs else 0.0,
    }


def render_md(rows, scen_label, n_paths, journal_note):
    f = lambda v: "-" if v != v else f"{v:,.0f}"
    L = ["---", "date: 2026-09-27", "type: research", "status: done",
         "script: tradingbot `research/payout_plan.py` (branch research/q-payout-plan-calc)", "---",
         "# PAPER/SIM - payout plan (no live data, no orders)",
         f"Paths: {n_paths:,} funded paths x {H_FUND} sessions from the g/sizing-mc rig [sizing-mc.md: "
         "R shape 45%@+1.95R / 47%@-1.14R, 12/10/6 MNQ, 0.25 trades/session, $2K EOD trail]. "
         f"Tax {TAX:.0%} [gig-taxes.md 25-30%]. Copies x{COPIES} [pass-plan-by-firm.md scaling].",
         "", "| firm | edge | paid% | 1st payout p25/50/75 (sess) | request | trader 90% | tax 30% | net to lessons | cum net 120s x1 | x5 |",
         "|---|---|--:|---|--:|--:|--:|--:|--:|--:|"]
    for sc, r in rows:
        L.append(f"| {r['firm']} | {sc} | {r['paid']:.0%} | {f(r['first_p25'])}/{f(r['first_p50'])}/{f(r['first_p75'])} "
                 f"| ${f(r['req_p50'])} | ${f(r['trader_p50'])} | ${f(r['tax_p50'])} | ${f(r['net_p50'])} "
                 f"| ${f(r['cum1_mean'])} | ${f(r['cum5_mean'])} |")
    L += ["", f"Edges [sizing-mc.md]: {scen_label}. Request/net = median first payout; cum = mean net after tax.",
          "Rules [task/u06, aggregator-sourced, not live-checked]: Lucid 5 days>=$150, <=50% profit, $2K cap, 90/10, "
          "5 payouts->live; Topstep 5 days>=$150, <=50% XFA balance, $5K cap, 90/10.",
          "x5 = identical copied fills (one bet, busts together), so x5 is 5x mean, not diversified.",
          journal_note,
          "Flags: funded-only (eval pass not included - see pass-plan-by-firm.md); R shape is hindsight S grades (upper bound)."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paths", type=int, default=4000)
    ap.add_argument("--journal", default="research/paper_journal/acks_replay.jsonl")
    ap.add_argument("--md", default=None)
    a = ap.parse_args(argv)
    scen = {"B +0.38R": 0.38, "C +0.19R": 0.19, "D 0R": 0.0}
    rows = []
    for sc, mu in scen.items():
        paths = rig_paths(a.paths, mu)
        for rules in (LUCID, TOPSTEP):
            rows.append((sc, summarize(paths, rules)))
    try:
        jp = journal_path(a.journal)
        js = [(r, simulate_payouts(jp, r)) for r in (LUCID, TOPSTEP)]
        jnote = (f"Paper journal [{a.journal}]: {len(jp)} day(s), ${sum(jp):,.0f} total -> "
                 + ", ".join(f"{r.name}: {len(p)} payout(s)" for r, p in js) + ".")
    except FileNotFoundError:
        jnote = f"Paper journal [{a.journal}]: not found."
    md = render_md(rows, ", ".join(scen), a.paths, jnote)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write(md)
    print(md)


if __name__ == "__main__":
    main()
