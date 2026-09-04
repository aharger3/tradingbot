"""g120 -- THREE FUNDING ARMS, same one-trade-a-day book, real firm rules.

Austin's ruling (Projects/AUGUR.md, 2026-09-03, grilling): "All angles go in
the backtest: options prop (Vanquish), stock-share prop (Trade The Pool and
peers), futures prop (...), and a personal ~$10k account. Each is an arm with
the firm's instrument and rules." This file is the options-prop / shares-prop
/ personal-capital half of that ruling (futures already has its own path
elsewhere in OMEN).

Same candidate stream for all three arms: `build_arm(rows, keep=lambda r:
True)` from g116 -- the shipped A_base arm, first size-gated candidate of the
day, RETEST_REQUIRED=1 book (`research/bt2y_trades_retest_on.json`).

  Arm 1 -- Vanquish Advanced Options $50k. Fixed-dollar risk (the book's own
           R x $ convention), swept 0.25%-3% of account, headline case is the
           book's native $1,000/trade (== 2.0% of $50k, already a RISK_PCTS
           grid point). Rules from research/prop_vanquish_terms.md and the
           "What the eval simulator must assume" section of Projects/AUGUR.md
           (vault): 10% target, 5% EOD-anchored trail, no daily loss limit
           (passed as 1.0 = disabled), min 4 days, no day over 30% of profit.
           $499/mo while in eval, $249 reset on a fail.
           CONDITIONAL: Vanquish's Advanced Options underlyings (index-only
           SPX/XSP/VIX vs single-name) are UNVERIFIED per AUGUR.md's open
           question -- this arm's universe is the CURRENT 28-symbol
           single-name book, and this result only holds if that verification
           lands single-names in scope.

  Arm 2 -- Trade The Pool, shares. The ONE arm that must be repriced off the
           book's own entry/stop PRICE fields, not r x a flat risk constant:
           per research/prop_firms_stocks.md's own "Simplified backtest
           model" -- "Set daily loss limit at 3% of initial capital, max
           position size at 1,000 shares or min(account balance / 4, 1,000
           shares), whichever binds first. This covers Funder Trading's
           strictest constraints..." -- shares = min(1000, floor(account_size
           * 4 / entry_price)), risk_dollars = shares * |entry - stop|,
           dollar pnl = r * risk_dollars (R-multiple stays invariant to
           position size, same convention g116's prop_row() uses, just fed a
           per-trade risk that now varies by symbol/price). account_size
           =$25,000 is a MODELING PICK (mid of Trade The Pool's stated
           $5k-$200k range, not a fact from their site). trailing_dd_pct=5%
           is a MODELING PICK (middle of their stated 3-7% range; their exact
           drawdown TYPE -- trailing vs static -- is not confirmed by the
           research file). consistency_pct=1.0 effectively disables the
           check (the fetched research states no consistency rule for this
           firm). $97 one-time eval fee, no monthly cost.

  Arm 3 -- Personal ~$10k account. No prop rules at all -- solvency, not
           PASS/FAIL: can this book be traded on $10k of real money without
           blowing up. Two sizings: the book's native $1,000/trade (10% of
           account per trade at max loss -- flagged explicitly as
           aggressive, more than most professional risk budgets) and a
           conservative $100/trade (1% of account). No cost line.

    python research/g120_prop_arms.py
    python research/test_g120_prop_arms.py
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from omen_metrics import evaluate_prop_challenge
from g116_sizing_kelly_options import (load_rows, build_arm, prop_row,
                                       pass_day, months_between, RISK_PCTS)

# ADVERSARIAL FIX (2026-09-03 night, opus REFUTE pass on this file's first
# cut): g116's own RISK_PCTS grid (0.25%, 0.50%, 0.75%, ..., 3.00% of
# account) straddles Vanquish's actual passing band without ever landing in
# it -- the reviewer found a PASS at every risk level from $131.00-$178.50
# per trade (0.262%-0.357% of $50k) using this file's own
# evaluate_prop_challenge, bracketed by the grid's $125 (FAIL) and $250
# (FAIL) points. Sources' own worked example ($150 risk -- both
# `Projects/AUGUR.md` and `research/prop_vanquish_terms.md` use "one 2R win
# at $150 risk is $300") sits dead centre of that band and was never tested.
# This finer grid adds explicit points through and around it so the sweep
# cannot straddle a real PASS band again without landing inside it.
VANQUISH_FINE_PCTS = sorted(set(RISK_PCTS) | {r / 50000.0 for r in
    (100, 110, 120, 125, 130, 140, 150, 160, 170, 175, 178.5, 180, 190, 200, 220, 240)})

OUT_JSON = os.path.join(HERE, "g120_prop_arms.json")
OUT_MD = os.path.join(HERE, "g120_prop_arms.md")

# ==========================================================================
# Arm 1 -- Vanquish Advanced Options $50k
# ==========================================================================
VANQUISH_ACCOUNT = 50000.0
VANQUISH_KW = dict(
    profit_target_pct=0.10,
    trailing_dd_pct=0.05,
    dd_mode="eod",
    daily_loss_limit_pct=1.0,   # Vanquish states NO daily loss limit; 1.0
                                 # (100% of account) disables the check --
                                 # no single day on this book ever loses the
                                 # whole account, so the rule can never trip.
    min_trading_days=4,
    consistency_pct=0.30,
)
VANQUISH_MONTHLY_FEE = 499.0
VANQUISH_RESET_FEE = 249.0
VANQUISH_HEADLINE_RISK = 1000.0   # the book's own native unit; == 2.0% of $50k


def vanquish_sweep(arm):
    """Fine sweep (VANQUISH_FINE_PCTS -- g116's own 9-point grid PLUS extra
    points through the actual passing band, see the comment above that
    constant) against Vanquish's real rules. Every row also carries
    months-to-pass, subscription cost through the pass day (or through the
    whole book if it never passes), and net dollars after that cost.

    ADVERSARIAL FIX: on a FAIL row this used to credit the full book's
    un-gated cumulative equity as if the eval kept trading for two years
    after it had already blown up -- a real eval STOPS the day it breaches
    the trail. A FAIL row now reports cost-only (subscription through the
    breach day, plus one reset) against $0 earned, not the fictional
    full-book total. `total_net_dollars_full_book` is still reported
    separately, clearly labeled as "if this book had kept trading
    ungated" -- informative, but never summed into net_dollars_after_cost
    for a FAIL."""
    d0 = arm[0]["day"]
    d_last = arm[-1]["day"]
    total_months_book = months_between(d0, d_last)
    rows = []
    for rp in VANQUISH_FINE_PCTS:
        risk = rp * VANQUISH_ACCOUNT
        res = prop_row(arm, risk, account=VANQUISH_ACCOUNT, **VANQUISH_KW)
        pnls = [r["r"] * risk for r in arm]
        cum = []
        s = 0.0
        for p in pnls:
            s += p
            cum.append(s)
        total_net_full_book = cum[-1]

        if res["passed"]:
            pd_, pi = pass_day(arm, risk, account=VANQUISH_ACCOUNT, **VANQUISH_KW)
            months = months_between(d0, pd_) if pd_ else None
            equity_at_event = cum[pi - 1] if pi else None
            sub_months = max(1, math.ceil(months)) if months is not None else None
            sub_cost = sub_months * VANQUISH_MONTHLY_FEE if sub_months else None
            reset_cost = 0.0
            net_after_cost = (equity_at_event - sub_cost) if (equity_at_event is not None and sub_cost is not None) else None
        else:
            pd_, pi = None, None
            fail_day = res["fail_day"]
            months = months_between(d0, fail_day) if fail_day else total_months_book
            equity_at_event = 0.0   # the eval breached -- nothing is realized/withdrawable
            sub_months = max(1, math.ceil(months))
            sub_cost = sub_months * VANQUISH_MONTHLY_FEE
            reset_cost = VANQUISH_RESET_FEE  # one reset charged; does not model repeated cycles
            net_after_cost = -(sub_cost + reset_cost)

        rows.append(dict(
            risk_pct=rp, risk_dollars=risk, is_headline_1000=(abs(risk - VANQUISH_HEADLINE_RISK) < 1e-6),
            is_worked_example_150=(abs(risk - 150.0) < 1e-6),
            passed=bool(res["passed"]), fail_reason=res["fail_reason"],
            first_fail_day=res["fail_day"], pass_day=pd_, pass_day_index=pi,
            months_to_event=round(months, 3) if months is not None else None,
            subscription_months_charged=sub_months,
            subscription_cost=sub_cost, reset_cost=reset_cost,
            total_net_dollars_full_book_if_ungated=round(total_net_full_book, 2),
            equity_at_pass_or_book_end=round(equity_at_event, 2) if equity_at_event is not None else None,
            net_dollars_after_cost=round(net_after_cost, 2) if net_after_cost is not None else None,
            final_equity_pct=res["final_equity_pct"],
            max_drawdown_seen_pct=res["max_drawdown_seen_pct"],
        ))
    return rows


# ==========================================================================
# Arm 2 -- Trade The Pool, shares (repriced off entry/stop, not flat $1,000)
# ==========================================================================
POOL_ACCOUNT = 25000.0
POOL_SHARE_CAP = 1000
POOL_BP_MULT = 4.0   # 4:1 intraday buying power
POOL_KW = dict(
    profit_target_pct=0.06,
    daily_loss_limit_pct=0.03,   # prop_firms_stocks.md's own recommended 3%
    trailing_dd_pct=0.05,        # middle of the file's stated 3-7% range
    dd_mode="eod",
    min_trading_days=0,
    consistency_pct=1.0,         # no consistency rule found for this firm -- disabled
)
POOL_EVAL_FEE = 97.0


def shares_for(entry_price, stop_price=None, account=POOL_ACCOUNT, cap=POOL_SHARE_CAP,
               mult=POOL_BP_MULT, daily_loss_limit_pct=None):
    """prop_firms_stocks.md, 'Simplified backtest model': "Set daily loss
    limit at 3% of initial capital, max position size at 1,000 shares or
    min(account balance / 4, 1,000 shares), whichever binds first."

    ADVERSARIAL NOTE (2026-09-03 night): that quoted sentence's own literal
    text is "account balance / 4", but this function computes
    `account * mult / entry_price` (i.e. account TIMES 4, divided by price)
    -- the RECIPROCAL of a literal reading. This is deliberate, not a typo
    surviving unnoticed: the file's own paragraph immediately above the
    quote explains the number in unambiguous dollar terms -- "Typical 4:1
    intraday buying power on equities. A $10k account can hold ~$40k
    notional" -- and `$40k notional / entry_price = shares`, i.e.
    `account_size * 4 / entry_price`, exactly what this function computes.
    The quoted sentence's "/ 4" phrasing describes the SAME buying-power
    idea loosely (buying power is often quoted as "4x", and dividing by 4
    reads naturally as "how much of your OWN capital backs one share" from
    the opposite direction), but taken completely literally it would mean a
    $25k account can buy $6,250 of notional -- a few shares of a $400 stock
    -- which contradicts the file's own worked $10k/$40k example by roughly
    16x. This function follows the file's own worked dollar example, not
    the ambiguous shorthand sentence next to it; if that reading is later
    judged wrong, the fix is a one-line change here (`mult=0.25`), not a
    rewrite of this model.

    ADVERSARIAL FIX #2: the quote's OWN daily loss limit (3% of capital) is
    now also enforced as a share-count cap, not just checked after the fact
    by `evaluate_prop_challenge`. Before this fix 27 of 495 trades carried a
    max-loss risk above the 3%-of-$25k ($750) daily loss limit the same
    quote states -- a real Trade The Pool account could not have taken
    those position sizes in the first place. `daily_loss_limit_pct`, when
    given, caps shares so `shares * |entry - stop| <= daily_loss_limit_pct
    * account` whenever entry/stop are both known."""
    if entry_price <= 0:
        return 0
    shares = min(cap, math.floor(account * mult / entry_price))
    if daily_loss_limit_pct and stop_price is not None:
        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share > 0:
            limit_shares = math.floor(daily_loss_limit_pct * account / risk_per_share)
            shares = min(shares, limit_shares)
    return max(0, shares)


def pool_series(arm):
    """Per-trade risk repriced off the book's own entry/stop PRICE fields --
    the one arm that is not r * a flat risk constant. Shares are capped by
    BOTH the buying-power/share-count rule and the firm's own daily loss
    limit (see shares_for()'s docstring, ADVERSARIAL FIX #2)."""
    out = []
    for r in arm:
        shares = shares_for(r["entry"], r["stop"],
                            daily_loss_limit_pct=POOL_KW["daily_loss_limit_pct"])
        risk_dollars = shares * abs(r["entry"] - r["stop"])
        pnl = r["r"] * risk_dollars
        out.append(dict(day=r["day"], sym=r["sym"], entry=r["entry"], stop=r["stop"],
                        shares=shares, risk_dollars=risk_dollars, pnl=pnl, r=r["r"]))
    return out


def pass_day_series(series, **kw):
    """Same replay-prefixes idea as g116's pass_day(), generalized to a
    precomputed (day, pnl) series with per-trade risk that already varies --
    g116's pass_day() assumes one constant risk_dollars and cannot be reused
    verbatim here."""
    for i in range(1, len(series) + 1):
        pnl = [(row["day"], row["pnl"]) for row in series[:i]]
        res = evaluate_prop_challenge(pnl, **kw)
        if res["passed"]:
            return series[i - 1]["day"], i, res
    pnl_all = [(row["day"], row["pnl"]) for row in series]
    return None, None, evaluate_prop_challenge(pnl_all, **kw)


def pool_arm_result(arm):
    series = pool_series(arm)
    pnl_all = [(row["day"], row["pnl"]) for row in series]
    res_full = evaluate_prop_challenge(pnl_all, account_size=POOL_ACCOUNT, **POOL_KW)
    d0, d_last = series[0]["day"], series[-1]["day"]

    cum = []
    s = 0.0
    for row in series:
        s += row["pnl"]
        cum.append(s)
    total_net_full_book = cum[-1]

    pd_, pi, res_at_pass = pass_day_series(series, account_size=POOL_ACCOUNT, **POOL_KW)
    passed = bool(res_at_pass["passed"])
    first_fail_day = res_full["fail_day"]
    if passed:
        months = months_between(d0, pd_)
        equity_at_event = cum[pi - 1]
        net_after_cost = equity_at_event - POOL_EVAL_FEE
    else:
        # ADVERSARIAL FIX (same one applied to Arm 1): a FAILed eval stops
        # trading the day it breaches, so nothing past that day is real --
        # report cost-only against $0 earned, not the un-gated full-book
        # total. total_net_full_book is still reported separately, clearly
        # labeled "if ungated".
        months = months_between(d0, first_fail_day) if first_fail_day else months_between(d0, d_last)
        equity_at_event = 0.0
        net_after_cost = -POOL_EVAL_FEE

    risk_dollars_all = [row["risk_dollars"] for row in series]
    return dict(
        n_trades=len(series),
        account_size=POOL_ACCOUNT,
        params=POOL_KW,
        share_cap=POOL_SHARE_CAP, bp_mult=POOL_BP_MULT,
        risk_dollars_min=round(min(risk_dollars_all), 2),
        risk_dollars_max=round(max(risk_dollars_all), 2),
        risk_dollars_mean=round(sum(risk_dollars_all) / len(risk_dollars_all), 2),
        passed=passed, fail_reason=res_at_pass["fail_reason"],
        first_fail_day=first_fail_day, pass_day=pd_, pass_day_index=pi,
        months_to_event=round(months, 3),
        eval_fee=POOL_EVAL_FEE,
        total_net_dollars_full_book_if_ungated=round(total_net_full_book, 2),
        equity_at_pass_or_book_end=round(equity_at_event, 2),
        net_dollars_after_cost=round(net_after_cost, 2),
        final_equity_pct=res_full["final_equity_pct"],
        max_drawdown_seen_pct=res_full["max_drawdown_seen_pct"],
        per_trade_sample=series[:5],   # a few rows -- proof risk varies, kept small
    )


# ==========================================================================
# Arm 3 -- personal ~$10k account (solvency, not PASS/FAIL)
# ==========================================================================
PERSONAL_ACCOUNT = 10000.0
PERSONAL_SIZINGS = [
    ("book_native_1000", 1000.0, "10% of $10k per trade at max loss -- the book's own "
     "native $1,000 unit, AGGRESSIVE: more than most professional risk budgets (typical "
     "professional risk is 0.5-2% of account per trade)."),
    ("conservative_1pct", 100.0, "1% of $10k per trade at max loss -- a conservative "
     "sizing for comparison."),
]


def personal_arm_result(arm):
    """ADVERSARIAL NOTE (2026-09-03 night): 'never wipes the account' is
    ORDER-DEPENDENT, not a safety property of this sizing -- the reviewer's
    own trace at $1,000/trade found equity climbs to a peak of ~$25.4k
    before the drawdown drags it back down to a trough of ~$3.8k; it only
    stays positive because the early trades in this particular book
    happened to be profitable BEFORE the losing stretch. `min_equity_ever`
    and `min_equity_pct_of_account` are reported alongside the peak-relative
    drawdown so this is visible, not implied by a bare 'never wiped'."""
    out = {}
    for key, risk, note in PERSONAL_SIZINGS:
        equity = PERSONAL_ACCOUNT
        peak = PERSONAL_ACCOUNT
        min_equity = PERSONAL_ACCOUNT
        min_equity_day = None
        max_dd_dollars = 0.0
        wiped = False
        wipe_day = None
        for r in arm:
            equity += r["r"] * risk
            peak = max(peak, equity)
            dd = peak - equity
            if dd > max_dd_dollars:
                max_dd_dollars = dd
            if equity < min_equity:
                min_equity = equity
                min_equity_day = r["day"]
            if equity <= 0 and not wiped:
                wiped = True
                wipe_day = r["day"]
        total_dollars = equity - PERSONAL_ACCOUNT
        out[key] = dict(
            risk_per_trade=risk, note=note,
            account_size=PERSONAL_ACCOUNT,
            n_trades=len(arm),
            total_dollars=round(total_dollars, 2),
            final_equity=round(equity, 2),
            max_drawdown_dollars=round(max_dd_dollars, 2),
            max_drawdown_pct_of_account=round(max_dd_dollars / PERSONAL_ACCOUNT * 100, 3),
            min_equity_ever=round(min_equity, 2), min_equity_day=min_equity_day,
            min_equity_pct_of_account=round(min_equity / PERSONAL_ACCOUNT * 100, 2),
            wiped=wiped, wipe_day=wipe_day,
            order_dependent_caveat=("never wiped in THIS book's own trade order -- "
                                    "profitable early trades built a cushion before "
                                    "the drawdown; a different ordering of the same "
                                    "trades could wipe the account even though the "
                                    "total P&L is identical"),
        )
    return out


# ==========================================================================
# ranking
# ==========================================================================
def rank_arms(vanquish_best_pass, pool_result):
    """Fundable FIRST = reaches a clean PASS soonest and cheapest, using each
    arm's BEST passing case (Vanquish: the lowest-months passing row from
    the sweep, not necessarily the book's native $1,000 unit -- see the
    module's ADVERSARIAL FIX note: a coarse sweep straddling the real
    passing band is exactly the bug that made 'no arm fundable' wrong on
    this file's first cut; Trade The Pool: its own repriced-shares series --
    there is only one sizing tested for that arm). Personal $10k has no
    PASS concept and is excluded from the funding race; it is reported
    separately as solvency."""
    candidates = []
    if vanquish_best_pass:
        candidates.append(("Vanquish Advanced Options $50k (at $%.0f/trade)" % vanquish_best_pass["risk_dollars"],
                           vanquish_best_pass["months_to_event"],
                           vanquish_best_pass["subscription_cost"] + vanquish_best_pass["reset_cost"]))
    if pool_result["passed"]:
        candidates.append(("Trade The Pool (shares)", pool_result["months_to_event"], pool_result["eval_fee"]))
    if not candidates:
        return dict(winner=None, reason="neither arm with a PASS/FAIL gate clears its target "
                    "anywhere in the book -- no arm is fundable on this candidate stream as "
                    "currently sized", candidates=[])
    candidates.sort(key=lambda c: (c[1], c[2]))
    winner = candidates[0][0]
    coinflip = False
    if len(candidates) == 2:
        (n0, m0, c0), (n1, m1, c1) = candidates
        # a coin flip if months-to-pass are within ~1 week of each other
        coinflip = abs(m0 - m1) < (7 / 30.4375)
    return dict(winner=winner, candidates=[dict(name=n, months=m, cost=c) for n, m, c in candidates],
                coinflip=coinflip,
                reason=None)


def main():
    rows = load_rows()
    arm = build_arm(rows, keep=lambda r: True)
    print("A_base arm (shipped unit, first size-gated candidate of the day): n=%d, %s .. %s"
          % (len(arm), arm[0]["day"], arm[-1]["day"]))

    out = {"meta": dict(book="bt2y_trades_retest_on.json", n_sessions=len(arm),
                        first_day=arm[0]["day"], last_day=arm[-1]["day"])}

    # ---------------- Arm 1: Vanquish ------------------------------------
    print("\n=== ARM 1 -- Vanquish Advanced Options $50k ===")
    print("CONDITIONAL: universe is the CURRENT 28-symbol single-name book; Vanquish's "
          "Advanced Options underlyings (index-only SPX/XSP/VIX vs single-name) are still "
          "UNVERIFIED per Projects/AUGUR.md's open question. This result only holds if that "
          "verification lands single-names in scope.")
    print("rules: 10% target / 5% EOD trail / no daily loss limit (passed as 100%, "
          "disabled) / 4 min days / no day >30% of profit | $499/mo, $249 reset on fail")
    v_rows = vanquish_sweep(arm)
    print("   %6s %8s %7s %26s %12s %7s %10s %10s %14s"
          % ("risk%", "$/trade", "verdict", "reason", "1st-fail/pass-day", "months", "sub$", "netFull$*", "netAfterCost$"))
    for row in v_rows:
        star = " *1000*" if row["is_headline_1000"] else (" *150*" if row["is_worked_example_150"] else "")
        print("   %5.2f%% %8.0f %7s %26s %12s %7s %10.0f %10.0f %14.0f%s"
              % (row["risk_pct"] * 100, row["risk_dollars"],
                 "PASS" if row["passed"] else "FAIL",
                 str(row["fail_reason"] or "-"), str(row["pass_day"] or row["first_fail_day"] or "-"),
                 ("%.1f" % row["months_to_event"]) if row["months_to_event"] is not None else "-",
                 row["subscription_cost"] or 0.0, row["total_net_dollars_full_book_if_ungated"],
                 row["net_dollars_after_cost"], star))
    print("   (*netFull$ = if this book had kept trading ungated for the whole 2 years; "
          "FAIL rows' netAfterCost$ is cost-only against $0 earned -- a real eval stops "
          "trading the day it breaches, see the module docstring)")

    passing = [r for r in v_rows if r["passed"]]
    if passing:
        lo = min(passing, key=lambda r: r["risk_dollars"])
        hi = max(passing, key=lambda r: r["risk_dollars"])
        print("   PASSING BAND (of the risk levels actually tested): $%.2f-$%.2f/trade "
              "(%d of %d tested levels pass)" % (lo["risk_dollars"], hi["risk_dollars"],
                                                 len(passing), len(v_rows)))
    elif len(set(r["fail_reason"] for r in v_rows)) == 1:
        print("   NOTE: every TESTED risk level FAILS the same way (%s) -- this is a "
              "statement about the levels tested, not a proof that no risk level "
              "anywhere would pass; see VANQUISH_FINE_PCTS's own docstring for why a "
              "coarse sweep can straddle a real passing band." % v_rows[0]["fail_reason"])

    v_headline = next(r for r in v_rows if r["is_headline_1000"])
    v_worked_example = next((r for r in v_rows if r["is_worked_example_150"]), None)
    # "best" = the passing row needing the fewest months, cheapest as tiebreak --
    # what actually decides the funding race, not necessarily the book's native unit.
    v_best_pass = min(passing, key=lambda r: (r["months_to_event"], r["risk_dollars"])) if passing else None

    print("\n   headline ($1,000/trade, the book's own native unit): %s"
          % ("PASS on %s (%.1f mo), net after cost $%.0f"
             % (v_headline["pass_day"], v_headline["months_to_event"], v_headline["net_dollars_after_cost"])
             if v_headline["passed"] else
             "FAIL (%s), cost-only through breach $%.0f"
             % (v_headline["fail_reason"], v_headline["net_dollars_after_cost"])))
    if v_worked_example:
        print("   worked example ($150/trade, from AUGUR.md / prop_vanquish_terms.md's own "
              "text): %s"
              % ("PASS on %s (%.1f mo), net after cost $%.0f"
                 % (v_worked_example["pass_day"], v_worked_example["months_to_event"],
                    v_worked_example["net_dollars_after_cost"])
                 if v_worked_example["passed"] else
                 "FAIL (%s), cost-only through breach $%.0f"
                 % (v_worked_example["fail_reason"], v_worked_example["net_dollars_after_cost"])))
    if v_best_pass:
        print("   BEST passing row in the sweep: $%.2f/trade, PASS on %s (%.1f mo), "
              "net after cost $%.0f"
              % (v_best_pass["risk_dollars"], v_best_pass["pass_day"],
                 v_best_pass["months_to_event"], v_best_pass["net_dollars_after_cost"]))

    out["arm1_vanquish"] = dict(
        name="Vanquish Advanced Options $50k",
        conditional_note="Universe is the CURRENT 28-symbol single-name book. Vanquish's "
                         "Advanced Options underlyings (index-only vs single-name) are "
                         "UNVERIFIED per Projects/AUGUR.md's open question -- this result is "
                         "CONDITIONAL on verification landing single-names in scope.",
        account_size=VANQUISH_ACCOUNT, params=VANQUISH_KW,
        monthly_fee=VANQUISH_MONTHLY_FEE, reset_fee=VANQUISH_RESET_FEE,
        headline_risk_dollars=VANQUISH_HEADLINE_RISK,
        sweep=v_rows, headline=v_headline, worked_example_150=v_worked_example,
        best_pass=v_best_pass,
        passing_band=(dict(low_dollars=lo["risk_dollars"], high_dollars=hi["risk_dollars"],
                           n_passing=len(passing), n_tested=len(v_rows))
                      if passing else None),
    )

    # ---------------- Arm 2: Trade The Pool -------------------------------
    print("\n=== ARM 2 -- Trade The Pool, shares (repriced off entry/stop) ===")
    print("prop_firms_stocks.md 'Simplified backtest model': \"Set daily loss limit at 3% "
          "of initial capital, max position size at 1,000 shares or min(account balance / 4, "
          "1,000 shares), whichever binds first.\"")
    print("modeling picks (stated, not from the site): account_size=$25,000 (mid of their "
          "$5k-$200k range); trailing_dd_pct=5% (middle of their stated 3-7% range, exact "
          "drawdown TYPE unconfirmed); consistency disabled (no rule found)")
    p_res = pool_arm_result(arm)
    print("   n=%d  risk$/trade min/mean/max = %.0f / %.0f / %.0f  (proof: NOT flat $1,000)"
          % (p_res["n_trades"], p_res["risk_dollars_min"], p_res["risk_dollars_mean"], p_res["risk_dollars_max"]))
    if p_res["passed"]:
        print("   PASS on %s (%.1f mo, trade #%d of %d), net after $97 fee = $%.0f"
              % (p_res["pass_day"], p_res["months_to_event"], p_res["pass_day_index"],
                 p_res["n_trades"], p_res["net_dollars_after_cost"]))
    else:
        print("   FAIL (%s, first breach %s) through the whole book, net after $97 fee = $%.0f"
              % (p_res["fail_reason"], p_res["first_fail_day"], p_res["net_dollars_after_cost"]))
    out["arm2_pool_shares"] = p_res

    # ---------------- Arm 3: personal $10k --------------------------------
    print("\n=== ARM 3 -- personal ~$10k account (solvency, no PASS/FAIL gate) ===")
    pers = personal_arm_result(arm)
    print("   %20s %10s %12s %12s %10s %8s"
          % ("sizing", "risk$/tr", "total$", "maxDD$", "maxDD%acct", "wiped?"))
    for key, d in pers.items():
        print("   %20s %10.0f %12.0f %12.0f %9.2f%% %8s"
              % (key, d["risk_per_trade"], d["total_dollars"], d["max_drawdown_dollars"],
                 d["max_drawdown_pct_of_account"], "YES" if d["wiped"] else "no"))
    out["arm3_personal"] = pers

    # ---------------- ranking ----------------------------------------------
    ranking = rank_arms(v_best_pass, p_res)
    print("\n=== RANKING -- fundable FIRST (soonest + cheapest clean PASS) ===")
    if ranking["winner"]:
        print("   %s (%s)" % (ranking["winner"],
              "coin flip -- within ~1 week of each other" if ranking["coinflip"] else "clear"))
        for c in ranking["candidates"]:
            print("     %-32s %6.1f months  $%.0f cost-to-pass" % (c["name"], c["months"], c["cost"]))
    else:
        print("   NO WINNER: %s" % ranking["reason"])
    out["ranking"] = ranking

    json.dump(out, open(OUT_JSON, "w"), indent=1)
    print("\nwrote", OUT_JSON)
    write_md(out)
    print("wrote", OUT_MD)
    return out


def _fmt_money(x):
    return "-" if x is None else ("$%s%.0f" % ("-" if x < 0 else "", abs(x)))


def write_md(out):
    a1 = out["arm1_vanquish"]
    a2 = out["arm2_pool_shares"]
    a3 = out["arm3_personal"]
    rk = out["ranking"]
    v_hl = a1["headline"]
    v_best = a1["best_pass"]
    v_band = a1["passing_band"]

    lines = []
    lines.append("# g120 -- three funding arms, same book, real firm rules\n")
    lines.append("Same one-trade-a-day candidate stream for all three arms: `build_arm(rows, "
                 "keep=lambda r: True)` from `research/g116_sizing_kelly_options.py` -- the "
                 "shipped A_base arm, first size-gated candidate of the day, "
                 "`research/bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, current shipped "
                 "default), n=%d sessions, %s .. %s.\n"
                 % (out["meta"]["n_sessions"], out["meta"]["first_day"], out["meta"]["last_day"]))
    lines.append("**Adversarial pass, 2026-09-03 night: this file's first cut was REFUTED.** "
                 "All mechanics, arithmetic and the shares conversion reproduced exactly under "
                 "independent re-derivation, but the headline \"no arm is fundable\" call was "
                 "wrong -- the 9-point risk-percent grid this file swept (0.25%, 0.50%, ..., "
                 "3.00% of account) straddled Vanquish's real passing band without ever landing "
                 "in it, and the sources' own worked example ($150/trade, from both "
                 "`Projects/AUGUR.md` and `research/prop_vanquish_terms.md`) sits dead centre of "
                 "that band. This version sweeps a finer grid through the actual band, reports "
                 "the passing band explicitly, and fixes a related bug where a FAILed eval's "
                 "\"net after cost\" credited two more years of un-gated trading past the day it "
                 "actually blew up.\n")

    lines.append("## Findings\n")
    if v_band:
        we = a1["worked_example_150"]
        we_line = ("PASS on %s (%.1f mo), net %s" % (we["pass_day"], we["months_to_event"],
                                                       _fmt_money(we["net_dollars_after_cost"]))
                  if we and we["passed"] else "not separately tested at exactly $150")
        lines.append("- **Arm 1, Vanquish Advanced Options $50k, PASSES in a narrow band: "
                     "$%.2f-$%.2f/trade (%.3f%%-%.3f%% of the $50k account, %d of %d tested "
                     "levels).** Best case in the sweep: $%.0f/trade, PASS on %s (%.1f months "
                     "in), net after subscription %s. At the sources' own worked example "
                     "($150/trade): %s. **The book's native $1,000/trade unit does NOT pass** "
                     "(FAILs %s, %.1f months to breach) -- the eval is passable, just not at "
                     "anything like the size this repo's numbers are usually quoted at. "
                     "CONDITIONAL: this arm's universe is the CURRENT 28-symbol single-name "
                     "book; Vanquish's Advanced Options underlyings (index-only SPX/XSP/VIX vs "
                     "single-name) are still UNVERIFIED per `Projects/AUGUR.md`'s open question, "
                     "so this result only holds if that verification lands single-names in "
                     "scope. Also CAVEAT: `dd_mode=\"eod\"` only checks the trail at each day's "
                     "close; a real intraday floor check (which this book cannot test -- no "
                     "intraday equity path is recorded) could shrink or eliminate this band."
                     % (v_band["low_dollars"], v_band["high_dollars"],
                        v_band["low_dollars"] / VANQUISH_ACCOUNT * 100, v_band["high_dollars"] / VANQUISH_ACCOUNT * 100,
                        v_band["n_passing"], v_band["n_tested"],
                        v_best["risk_dollars"], v_best["pass_day"], v_best["months_to_event"],
                        _fmt_money(v_best["net_dollars_after_cost"]),
                        we_line, v_hl["fail_reason"], v_hl["months_to_event"]))
    else:
        lines.append("- **Arm 1, Vanquish Advanced Options $50k:** never PASSES at any of the "
                     "%d risk levels tested (all FAIL %s). CONDITIONAL -- this arm's universe "
                     "is the CURRENT 28-symbol single-name book; Vanquish's Advanced Options "
                     "underlyings (index-only vs single-name) are still UNVERIFIED per "
                     "`Projects/AUGUR.md`'s open question."
                     % (len(a1["sweep"]), v_hl["fail_reason"]))

    p_line = ("**PASSES on %s (%.1f months in, trade #%d of %d), net of the $97 eval fee %s.**"
              % (a2["pass_day"], a2["months_to_event"], a2["pass_day_index"], a2["n_trades"],
                 _fmt_money(a2["net_dollars_after_cost"]))
              if a2["passed"] else
              "**never PASSES over the whole book** (fails %s at first breach %s; cost-only "
              "through breach, net %s)." % (a2["fail_reason"], a2["first_fail_day"], _fmt_money(a2["net_dollars_after_cost"])))
    lines.append("- **Arm 2, Trade The Pool (shares, repriced off entry/stop):** %s Per-trade "
                 "risk actually varies with each symbol's own price ($%.0f-$%.0f, mean $%.0f) "
                 "-- proof this is not the book's flat $1,000 convention. Shares are capped by "
                 "BOTH the buying-power rule AND the firm's own 3%% daily loss limit (see "
                 "`shares_for()`'s docstring for the fix and why the buying-power reading is "
                 "`account*4/entry`, not a literal `account/4`)." % (
                     p_line, a2["risk_dollars_min"], a2["risk_dollars_max"], a2["risk_dollars_mean"]))

    for key, note_key in (("book_native_1000", "aggressive"), ("conservative_1pct", "conservative")):
        d = a3[key]
        wipe = ("**would have WIPED the account** on %s" % d["wipe_day"]) if d["wiped"] else "never wipes the account IN THIS BOOK'S OWN TRADE ORDER"
        lines.append("- **Arm 3, personal ~$10k, %s ($%.0f/trade):** total %s over the book, "
                     "max drawdown %s (%.2f%% of the $10k account), trough equity %s (%.1f%% "
                     "of the account), %s -- order-dependent, not a safety property: early "
                     "profitable trades built the cushion before the drawdown; see "
                     "`personal_arm_result()`'s docstring."
                     % (note_key, d["risk_per_trade"], _fmt_money(d["total_dollars"]),
                        _fmt_money(d["max_drawdown_dollars"]), d["max_drawdown_pct_of_account"],
                        _fmt_money(d["min_equity_ever"]), d["min_equity_pct_of_account"], wipe))

    lines.append("")
    if rk["winner"]:
        lines.append("**Ranking: %s is fundable FIRST** -- %s." % (
            rk["winner"], "a coin flip against the other PASSing arm (within about a week of "
                          "each other)" if rk["coinflip"] else "clearly soonest and cheapest of the two"))
        for c in rk["candidates"]:
            lines.append("  - %s: %.1f months to a clean PASS, $%.0f cost to get there." % (c["name"], c["months"], c["cost"]))
    else:
        lines.append("**Ranking: no arm is fundable at any tested risk level.** %s" % rk["reason"])

    lines.append("\nModeling choices stated explicitly (none silently baked in):\n")
    lines.append("- Vanquish: no daily loss limit is modeled as `daily_loss_limit_pct=1.0` "
                 "(100% of account) so the rule can structurally never trip -- Vanquish's own "
                 "page states there is no such limit, this is how the generic simulator "
                 "encodes 'disabled'.")
    lines.append("- Trade The Pool: account_size=$25,000 is a MID-OF-RANGE PICK ($5k-$200k "
                 "stated range, not a number from their site). trailing_dd_pct=5% is a "
                 "MIDDLE-OF-RANGE PICK (3-7% stated range); the exact drawdown TYPE (trailing "
                 "vs static) is NOT confirmed by `research/prop_firms_stocks.md`. "
                 "consistency_pct=1.0 disables the consistency check because the fetched "
                 "research states no such rule for this firm. min_trading_days=0 because none "
                 "is stated.")
    lines.append("- Personal $10k: an arbitrary account size Austin named "
                 "(\"a personal ~$10k account\") in the AUGUR grilling session, not a specific "
                 "committed number -- both a book-native ($1,000/trade, aggressive) and a "
                 "conservative (1%, $100/trade) sizing are reported since neither is obviously "
                 "the right one to commit to alone.")

    lines.append("\n## Arm 1 -- Vanquish Advanced Options $50k, risk sweep\n")
    lines.append("Rules: 10% profit target / 5% EOD-anchored trailing drawdown / no daily "
                 "loss limit / min 4 trading days / no single day over 30% of accumulated "
                 "profit, per `research/prop_vanquish_terms.md` and the \"What the eval "
                 "simulator must assume\" section of `Projects/AUGUR.md`. Cost: $499/month "
                 "while in eval; $249 reset assumed once if the eval never passes over the "
                 "whole book.\n")
    lines.append("| risk% | $/trade | verdict | fail reason | 1st-fail/pass day | months | "
                 "sub$ charged | net $ if ungated (full book) | net $ after cost |")
    lines.append("|---:|---:|---|---|---|---:|---:|---:|---:|")
    for row in a1["sweep"]:
        tag = (" **(=$1,000, shipped unit)**" if row["is_headline_1000"]
              else " **(=$150, sources' worked example)**" if row["is_worked_example_150"] else "")
        day = row["pass_day"] or row["first_fail_day"] or "-"
        lines.append("| %.2f%%%s | %.2f | %s | %s | %s | %s | %s | %s | %s |" % (
            row["risk_pct"] * 100, tag, row["risk_dollars"],
            "PASS" if row["passed"] else "FAIL", row["fail_reason"] or "-",
            day,
            ("%.1f" % row["months_to_event"]) if row["months_to_event"] is not None else "-",
            _fmt_money(row["subscription_cost"]),
            _fmt_money(row["total_net_dollars_full_book_if_ungated"]),
            _fmt_money(row["net_dollars_after_cost"])))
    lines.append("\n(FAIL rows' \"net $ after cost\" is cost-only against $0 earned -- a real "
                 "eval stops trading the day it breaches the trail, so the un-gated full-book "
                 "total is not money that could ever be realized inside that eval. \"net $ if "
                 "ungated\" is reported for context only.)")
    if v_band:
        lines.append("\n**Passing band: $%.2f-$%.2f/trade** (%d of %d tested levels). Every "
                     "risk level ABOVE the band's top and every level BELOW it FAILs "
                     "`trailing_drawdown` (rows below the band reach it via a different R-path "
                     "timing, not a different mechanism) -- the FAILing levels are not one "
                     "monolithic phenomenon, they bracket a real window that a coarse sweep can "
                     "miss entirely, which is exactly what this file's first cut did."
                     % (v_band["low_dollars"], v_band["high_dollars"], v_band["n_passing"], v_band["n_tested"]))
    elif len(set(r["fail_reason"] for r in a1["sweep"])) == 1:
        lines.append("\n**Note:** every TESTED risk level FAILs the same way "
                     "(`%s`) -- a statement about the levels actually tested, not a proof no "
                     "risk level anywhere passes." % a1["sweep"][0]["fail_reason"])

    lines.append("\n## Arm 2 -- Trade The Pool, shares\n")
    lines.append("Repricing per `research/prop_firms_stocks.md`'s \"Simplified backtest "
                 "model\": *\"Set daily loss limit at 3% of initial capital, max position "
                 "size at 1,000 shares or min(account balance / 4, 1,000 shares), whichever "
                 "binds first. This covers Funder Trading's strictest constraints and "
                 "resembles a real intraday account.\"* `shares = min(1000, floor(account_size "
                 "* 4 / entry_price))`, `risk_dollars = shares * |entry - stop|`, `pnl = r * "
                 "risk_dollars`.\n")
    lines.append("| metric | value |\n|---|---:|")
    lines.append("| account size (modeling pick) | $%.0f |" % a2["account_size"])
    lines.append("| profit target | %.0f%% |" % (a2["params"]["profit_target_pct"] * 100))
    lines.append("| daily loss limit | %.0f%% |" % (a2["params"]["daily_loss_limit_pct"] * 100))
    lines.append("| trailing drawdown (modeling pick) | %.0f%% |" % (a2["params"]["trailing_dd_pct"] * 100))
    lines.append("| min trading days | %d |" % a2["params"]["min_trading_days"])
    lines.append("| consistency | disabled (%.1f) |" % a2["params"]["consistency_pct"])
    lines.append("| risk $/trade min / mean / max | $%.0f / $%.0f / $%.0f |" % (
        a2["risk_dollars_min"], a2["risk_dollars_mean"], a2["risk_dollars_max"]))
    lines.append("| verdict | %s |" % ("PASS on %s" % a2["pass_day"]
                 if a2["passed"] else "FAIL (%s, first breach %s)" % (a2["fail_reason"], a2["first_fail_day"])))
    lines.append("| months to event | %.1f |" % a2["months_to_event"])
    lines.append("| total net $ if ungated (full book) | %s |" % _fmt_money(a2["total_net_dollars_full_book_if_ungated"]))
    lines.append("| eval fee | $%.0f |" % a2["eval_fee"])
    lines.append("| net $ after cost | %s |" % _fmt_money(a2["net_dollars_after_cost"]))

    lines.append("\n## Arm 3 -- personal ~$10k account (solvency)\n")
    lines.append("No prop-firm rules. Same $1,000-fixed-risk unit as the shipped book (10% of "
                 "the $10k account per trade at max loss -- AGGRESSIVE, more than most "
                 "professional risk budgets) and a conservative 1%-of-account sizing ($100/trade).\n")
    lines.append("| sizing | risk $/trade | total $ | max DD $ | max DD % of account | "
                 "trough equity $ | trough % of account | wiped? |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|:---:|")
    for key, label in (("book_native_1000", "book-native $1,000 (10%, aggressive)"),
                       ("conservative_1pct", "conservative $100 (1%)")):
        d = a3[key]
        lines.append("| %s | $%.0f | %s | %s | %.2f%% | %s | %.1f%% | %s |" % (
            label, d["risk_per_trade"], _fmt_money(d["total_dollars"]),
            _fmt_money(d["max_drawdown_dollars"]), d["max_drawdown_pct_of_account"],
            _fmt_money(d["min_equity_ever"]), d["min_equity_pct_of_account"],
            ("YES on %s" % d["wipe_day"]) if d["wiped"] else "no"))
    lines.append("\n\"Never wiped\" is order-dependent, not a safety property: it holds only "
                 "because this book's own early trades happened to be profitable before the "
                 "drawdown built the cushion the trough later ate into. See "
                 "`personal_arm_result()`'s docstring.")

    lines.append("\n## Ranking\n")
    if rk["winner"]:
        lines.append("**%s is fundable FIRST** -- %s.\n" % (
            rk["winner"], "this is a coin flip against the other PASSing arm (within about a "
                          "week of each other, not a clean call)" if rk["coinflip"] else
                          "clearly soonest and cheapest of the arms that PASS"))
        lines.append("| arm | months to clean PASS | cost to get there |\n|---|---:|---:|")
        for c in rk["candidates"]:
            lines.append("| %s | %.1f | $%.0f |" % (c["name"], c["months"], c["cost"]))
    else:
        lines.append("**No arm is fundable.** %s\n" % rk["reason"])

    lines.append("")
    open(OUT_MD, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
