"""scaling_ladder.py -- prop-firm account-scaling simulator (build ticket 2).

Answers OMEN-SHIP-PLAN.md section 2's question with a number instead of a
plan: replaying the chosen setup's actual trade list (NQ break-and-retest,
`research/nq_br_trades.json`, generated from `t02-break-retest/bt.py`'s own
PRE/LVL/3R grid row, NQ only -- 150 trades, +0.369R, 40% win) day by day
through the funding ladder u06-prop-firms.md recommends: 1 LucidFlex 50K,
scale to 5 Lucid funded accounts (same signal copied), then up to 5 Topstep
50K XFA, tracking every eval purchase, funding date, payout and blown
account along the way.

REUSED, NOT REIMPLEMENTED. Every PASS/FAIL/breach judgment is
`propfirm_gate.evaluate_firm` -> `omen_metrics.evaluate_prop_challenge`,
called fresh each day on an expanding window `daily[start_idx:d+1]` for
each live account. No drawdown, profit-target or consistency arithmetic is
reimplemented here -- this file only tracks WHICH accounts exist, WHEN they
were bought, and books payouts. Calling the same pure function on a
1-longer window each day is O(days) per account per day, i.e. O(n^2) per
account lifetime; for a ~500-session book and a handful of concurrent
accounts this is a few hundred thousand calls, trivial in practice.

Funded-stage tracking uses the SAME firm rule as the eval (same trailing
drawdown / daily loss limit), with profit_target_pct pushed out of reach
and min_trading_days=0, so `evaluate_prop_challenge` never fires a
spurious "pass" once already funded -- it can only ever report "still
alive" or a genuine drawdown/daily-loss breach ("funded_blown").

APPROXIMATIONS (read before trusting a payout number):
  1. Payout timing follows u06's own summary of each firm's payout cadence
     (Lucid: every 5 profitable days, <=50% of profit-since-last-payout,
     <=$2,000/request; same shape applied to Topstep since XFA payout
     mechanics were not separately modeled). This is not the firm's exact
     payout contract, only its shape.
  2. A payout is money OUT of the account in real life; this simulator does
     NOT reduce the account's internal equity/peak/floor when a payout is
     booked (evaluate_prop_challenge has no withdrawal parameter). This
     means the modeled trailing floor is a hair more forgiving after a
     payout than a real account's would be -- a real account's floor would
     sit `payout` dollars lower. Flagged, not fixed, per Austin's
     honest-backtest rule (state the approximation, don't silently patch
     over it with unreviewed logic in a gate file).
  3. Topstep's recurring $49/mo subscription while in eval/funded is not
     accrued day-by-day, only the $49 (+$149 activation) initial eval cost.
     `cost_dollars` on each event is the one-time cost only.
  4. Every account trades the IDENTICAL daily P&L series (a signal copied
     across accounts, per u06's "copied accounts are one bet"). Real fills
     would differ slightly account to account; this is the same
     simplification the ship plan's own sizing formula already makes.

Run: python research/scaling_ladder.py [--book PATH] [--out PATH]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import propfirm_gate as PG  # noqa: E402

DEFAULT_BOOK = os.path.join(HERE, "nq_br_trades.json")
DEFAULT_OUT = os.path.join(ROOT, "logs", "scaling_ladder_latest.json")

# ==========================================================================
# 1. the ladder -- u06-prop-firms.md section "Scale path: more 50Ks, not
#    bigger accounts": 1 LucidFlex -> 5 Lucid funded, then up to 5 Topstep
#    XFA. LucidFlex is not in propfirm_gate.FIRM_RULES yet (u06 flagged it
#    "(missing)"); this ticket adds it there (see propfirm_gate.py diff),
#    so this module imports the rule rather than redefining it.
# ==========================================================================

DEFAULT_LADDER = [
    dict(firm="LucidFlex 50K", max_funded=5, eval_cost=146.0,
         payout_every_n_winning_days=5, payout_pct_of_profit=0.50,
         payout_cap_dollars=2000.0),
    dict(firm="Topstep 50K Combine", max_funded=5, eval_cost=49.0 + 149.0,
         payout_every_n_winning_days=5, payout_pct_of_profit=0.50,
         payout_cap_dollars=2500.0),
]


# ==========================================================================
# 2. one account-day step, entirely through propfirm_gate.evaluate_firm
# ==========================================================================

# evaluate_prop_challenge always returns a definitive verdict for whatever
# finite window it is handed -- it has no "still pending" return value. Fed
# a window that just hasn't run long enough yet, a live, unresolved account
# comes back FAIL/profit_target_not_reached (or min_trading_days, or
# consistency): true statements about the window-so-far, but NOT permanent
# breaches -- more days could still flip them to a pass. Only
# daily_loss_limit and trailing_drawdown are events a later day can never
# undo. Treating every non-None fail_reason as a real failure (the first
# version of this function did) rebuys a new eval every single day and
# never lets one run long enough to pass -- caught by this module's own
# tests (test_never_resolves_within_one_day_is_alive_not_failed).
_PERMANENT_FAIL_REASONS = frozenset({"daily_loss_limit", "trailing_drawdown"})


def _account_status(daily, start_idx, end_idx, rule):
    """PASS/FAIL/ALIVE for one account trading daily[start_idx:end_idx+1]
    under `rule`, via propfirm_gate.evaluate_firm (omen_metrics.evaluate_
    prop_challenge underneath) -- the existing gate code, called fresh
    each day. Returns (status, result_dict) where status is one of
    "alive", "passed", "failed" ("failed" only for the two permanent
    breach reasons; a provisional not-yet-reached verdict is "alive")."""
    seg = daily[start_idx:end_idx + 1]
    if not seg:
        return "alive", None
    res = PG.evaluate_firm(seg, rule)
    if res["passed"]:
        return "passed", res
    if res["fail_reason"] in _PERMANENT_FAIL_REASONS:
        return "failed", res
    return "alive", res


def _funded_rule(rule: dict) -> dict:
    """The same firm rule, with the profit-target/consistency/min-days
    machinery neutralized so evaluate_prop_challenge can only ever report
    "still alive" or a genuine drawdown/daily-loss breach once an account
    is already funded (a funded account isn't re-evaluated against a
    profit target; it just has to not blow up)."""
    r = dict(rule)
    r["profit_target_pct"] = 1000.0   # unreachable
    r["min_trading_days"] = 0
    r["consistency_pct"] = 1.0        # never the binding constraint
    return r


# ==========================================================================
# 3. the ladder walk
# ==========================================================================

def simulate_ladder(daily, ladder=None, firm_rules=None) -> dict:
    """`daily`: chronological [(day_label, usd), ...] -- the chosen setup's
    trade list (one entry per trading day, honest fill). Walks it day by
    day, buying evals, funding accounts, booking approximate payouts and
    retiring blown accounts, entirely off propfirm_gate's PASS/FAIL/
    breach judgments. Returns a report dict; see module docstring for the
    documented approximations."""
    ladder = ladder if ladder is not None else DEFAULT_LADDER
    firm_rules = firm_rules if firm_rules is not None else PG.FIRM_RULES
    n = len(daily)

    events = []
    tier_i = 0
    funded = []       # [{firm, tier, start_idx, since, payout_days, payout_profit, blown}]
    eval_acct = None  # {firm, tier, start_idx}
    total_eval_cost = 0.0
    total_payouts = 0.0

    for d in range(n):
        day_label, day_usd = daily[d][0], daily[d][1]

        # (a) open a new eval if the ladder has room and none is pending
        while eval_acct is None and tier_i < len(ladder):
            tier = ladder[tier_i]
            n_funded_here = sum(1 for a in funded if a["tier"] == tier_i and not a["blown"])
            if n_funded_here >= tier["max_funded"]:
                tier_i += 1
                continue
            eval_acct = dict(firm=tier["firm"], tier=tier_i, start_idx=d)
            total_eval_cost += tier["eval_cost"]
            events.append(dict(day=day_label, kind="buy_eval", firm=tier["firm"],
                                tier=tier_i, cost=tier["eval_cost"]))
            break

        # (b) step the pending eval by one day
        if eval_acct is not None:
            rule = firm_rules[eval_acct["firm"]]
            status, res = _account_status(daily, eval_acct["start_idx"], d, rule)
            if status == "passed":
                funded.append(dict(firm=eval_acct["firm"], tier=eval_acct["tier"],
                                    start_idx=d, since=day_label,
                                    payout_days=0, payout_profit=0.0, blown=False))
                events.append(dict(day=day_label, kind="funded",
                                    firm=eval_acct["firm"], tier=eval_acct["tier"]))
                eval_acct = None
            elif status == "failed":
                events.append(dict(day=day_label, kind="eval_failed",
                                    firm=eval_acct["firm"], tier=eval_acct["tier"],
                                    reason=res["fail_reason"]))
                eval_acct = None  # a fresh eval is bought on the NEXT iteration

        # (c) step every funded account by one day: survival + payout
        for a in funded:
            if a["blown"]:
                continue
            tier = ladder[a["tier"]]
            rule = _funded_rule(firm_rules[a["firm"]])
            status, res = _account_status(daily, a["start_idx"], d, rule)
            if status == "failed":
                a["blown"] = True
                events.append(dict(day=day_label, kind="funded_blown", firm=a["firm"],
                                    tier=a["tier"], reason=res["fail_reason"]))
                continue
            if day_usd > 0:
                a["payout_days"] += 1
                a["payout_profit"] += day_usd
            if a["payout_days"] >= tier["payout_every_n_winning_days"] and a["payout_profit"] > 0:
                payout = min(tier["payout_pct_of_profit"] * a["payout_profit"],
                             tier["payout_cap_dollars"])
                payout = round(payout, 2)
                total_payouts += payout
                events.append(dict(day=day_label, kind="payout", firm=a["firm"],
                                    tier=a["tier"], amount=payout))
                a["payout_days"] = 0
                a["payout_profit"] = 0.0

    # whatever remains at the end of the book is neither a pass nor a
    # permanent fail -- it just ran out of history. Report it as such
    # rather than silently dropping it.
    open_eval_at_end = dict(firm=eval_acct["firm"], tier=eval_acct["tier"],
                             days_in=n - eval_acct["start_idx"]) if eval_acct else None

    n_funded_alive = sum(1 for a in funded if not a["blown"])
    n_funded_ever = len(funded)
    n_blown = sum(1 for a in funded if a["blown"])
    n_eval_fails = sum(1 for e in events if e["kind"] == "eval_failed")
    span_days = (daily[-1][0], daily[0][0]) if daily else (None, None)

    # crude $/trading-day at the FINAL scale (funded accounts alive at the
    # end, replaying the book's own +0.369R average), for a same-units
    # comparison against the ship plan's ~$18/day single-account estimate.
    mean_usd_per_day = (sum(u for _, u in daily) / n) if n else 0.0
    projected_per_day_at_scale = mean_usd_per_day * n_funded_alive

    report = dict(
        book=os.path.basename(DEFAULT_BOOK),
        n_days=n, span=span_days, ladder=[t["firm"] for t in ladder],
        total_eval_cost=round(total_eval_cost, 2),
        total_payouts=round(total_payouts, 2),
        net=round(total_payouts - total_eval_cost, 2),
        n_eval_purchases=sum(1 for e in events if e["kind"] == "buy_eval"),
        n_eval_fails=n_eval_fails,
        n_funded_ever=n_funded_ever,
        n_funded_alive_at_end=n_funded_alive,
        n_funded_blown=n_blown,
        open_eval_at_end=open_eval_at_end,
        mean_usd_per_trading_day_single_account=round(mean_usd_per_day, 2),
        projected_usd_per_day_at_final_scale=round(projected_per_day_at_scale, 2),
        events=events,
    )
    return report


# ==========================================================================
# 4. loading + CLI
# ==========================================================================

def load_book(path=None):
    path = path or DEFAULT_BOOK
    blob = json.load(open(path, encoding="utf-8"))
    trades = blob["trades"]
    daily = [(t["day"], t["usd"]) for t in trades]
    return daily, blob.get("meta", {})


def write_report(book_path=None, out_path=None, ladder=None, firm_rules=None) -> dict:
    daily, meta = load_book(book_path)
    report = simulate_ladder(daily, ladder, firm_rules)
    report["book_meta"] = meta
    out_path = Path(out_path or DEFAULT_OUT)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["out_path"] = str(out_path)
    return report


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--book", default=DEFAULT_BOOK)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()
    report = write_report(args.book, args.out)
    print("book: %s (%d days, %s -> %s)" % (report["book"], report["n_days"], *report["span"][::-1]))
    print("evals bought: %d  eval fails: %d  funded (ever/alive/blown): %d/%d/%d"
          % (report["n_eval_purchases"], report["n_eval_fails"], report["n_funded_ever"],
             report["n_funded_alive_at_end"], report["n_funded_blown"]))
    print("total eval cost: $%.2f  total payouts: $%.2f  net: $%.2f"
          % (report["total_eval_cost"], report["total_payouts"], report["net"]))
    print("mean $/trading-day (1 account): $%.2f   projected $/day at final scale (%d funded): $%.2f"
          % (report["mean_usd_per_trading_day_single_account"], report["n_funded_alive_at_end"],
             report["projected_usd_per_day_at_final_scale"]))
    print("wrote", report["out_path"])


if __name__ == "__main__":
    main()
