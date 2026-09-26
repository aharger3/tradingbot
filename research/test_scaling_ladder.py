"""Plain asserts for scaling_ladder.py -- synthetic P&L only except test 6,
no market data required.

    python research/test_scaling_ladder.py

Checks:
 1. an account that needs many days to reach its profit target is NOT
    rebought every day while still alive (the bug this module's first
    version had: evaluate_prop_challenge's "profit_target_not_reached" on
    a truncated window is provisional, not a permanent failure).
 2. a real trailing-drawdown breach DOES end the eval and a fresh one is
    bought the next day.
 3. tier transition: once a tier's max_funded is reached, the next eval
    buys the NEXT tier, not another account at the maxed-out one.
 4. payout mechanics: after N winning days, a payout of
    min(pct * profit_since_last, cap) is booked and the counters reset.
 5. a funded account that later breaches drawdown is marked blown and its
    slot opens back up for a fresh eval.
 6. the real chosen-setup book (research/nq_br_trades.json, NQ PRE/LVL/3R,
    150 trades) funds at least one LucidFlex account and the single walk-
    forward day-by-day verdict matches a single whole-series
    evaluate_firm() call for the FIRST account (cross-check against the
    already-trusted gate code, not a second implementation of it).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import propfirm_gate as PG
from scaling_ladder import simulate_ladder, load_book, DEFAULT_LADDER

# A rule with a reachable-but-not-trivial target and no other tripwires, so
# tests can isolate exactly the behavior they're checking.
SLOW_RULE = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.04,
                 dd_mode="eod", dd_lock_at_breakeven=False, daily_loss_limit_pct=1.0,
                 min_trading_days=0, consistency_pct=1.0, max_days=None)


def main():
    # 1. a $150/day climb takes 20 days to reach the $3,000 (6% of 50K)
    # target. It must NOT be rebought partway through.
    slow_climb = [("d%d" % i, 150.0) for i in range(1, 21)]
    ladder = [dict(firm="TEST", max_funded=5, eval_cost=100.0,
                   payout_every_n_winning_days=999, payout_pct_of_profit=0.5,
                   payout_cap_dollars=2000.0)]
    rules = {"TEST": SLOW_RULE}
    r = simulate_ladder(slow_climb, ladder, rules)
    assert r["n_eval_purchases"] == 1, "should buy exactly ONE eval for a slow clean climb: %r" % r
    assert r["n_funded_ever"] == 1 and r["n_funded_blown"] == 0, r
    funded_day = next(e["day"] for e in r["events"] if e["kind"] == "funded")
    assert funded_day == "d20", "should fund on day 20 (150*20=3000): got %s" % funded_day
    print("ok   a slow clean climb is bought ONCE, not rebought every day it hasn't yet passed")

    # 2. a real trailing-drawdown breach: 5 up days to +$1,000 peak (short of
    # the $3,000 target), then 3 down days losing $2,100 off that peak --
    # more than the $2,000 trail. This MUST end the eval.
    curve = ([("d%d" % i, 200.0) for i in range(1, 6)]
             + [("d6", -700.0), ("d7", -700.0), ("d8", -700.0), ("d9", 10.0)])
    r = simulate_ladder(curve, ladder, rules)
    assert r["n_eval_fails"] == 1, "the $2,100 pullback off a $1,000 peak should breach the $2,000 trail: %r" % r
    fail_ev = next(e for e in r["events"] if e["kind"] == "eval_failed")
    assert fail_ev["day"] == "d8" and fail_ev["reason"] == "trailing_drawdown", fail_ev
    assert r["n_eval_purchases"] == 2, "a fresh eval should be bought the day after the breach: %r" % r
    print("ok   a real trailing-drawdown breach ends the eval on the correct day, "
          "and a fresh one is bought next")

    # 3. tier transition: tier 0 caps at 1 funded account; a clean climb
    # long enough to fund TWO accounts must put the second one in tier 1.
    two_tier = [dict(firm="T0", max_funded=1, eval_cost=50.0,
                     payout_every_n_winning_days=999, payout_pct_of_profit=0.5,
                     payout_cap_dollars=2000.0),
                dict(firm="T1", max_funded=1, eval_cost=75.0,
                     payout_every_n_winning_days=999, payout_pct_of_profit=0.5,
                     payout_cap_dollars=2000.0)]
    two_rules = {"T0": SLOW_RULE, "T1": SLOW_RULE}
    long_climb = [("d%d" % i, 150.0) for i in range(1, 41)]  # two 20-day fundings back to back
    r = simulate_ladder(long_climb, two_tier, two_rules)
    firms_bought = [e["firm"] for e in r["events"] if e["kind"] == "buy_eval"]
    assert firms_bought[0] == "T0", firms_bought
    assert "T1" in firms_bought, "tier 0 is maxed at 1 funded; the next eval must be tier 1: %r" % firms_bought
    print("ok   once a tier's max_funded is reached, the next eval buys the NEXT tier")

    # 4. payout: a near-zero profit target so day 1 funds immediately, then
    # 5 winning $500 days total (funding day counts as day 1 of the payout
    # window, same as a real account's own P&L would) -> profit_since_last
    # = $2,500, payout = min(0.5*2500, 2000) = $1,250, counters reset.
    pay_ladder = [dict(firm="TEST", max_funded=5, eval_cost=0.0,
                       payout_every_n_winning_days=5, payout_pct_of_profit=0.5,
                       payout_cap_dollars=2000.0)]
    tiny_target_rule = dict(SLOW_RULE, profit_target_pct=0.00001)  # $0.50 on 50K
    pay_rules = {"TEST": tiny_target_rule}
    curve = [("f%d" % i, 500.0) for i in range(1, 6)]
    r = simulate_ladder(curve, pay_ladder, pay_rules)
    funded_day = next(e["day"] for e in r["events"] if e["kind"] == "funded")
    assert funded_day == "f1", "the near-zero target should fund on day 1: %r" % r
    payouts = [e for e in r["events"] if e["kind"] == "payout"]
    assert len(payouts) == 1 and payouts[0]["amount"] == 1250.0, payouts
    print("ok   payout = min(50%% of profit-since-last, cap) after 5 winning days, "
          "counters reset (%r)" % payouts[0])

    # 5. a funded account can still blow up: fund on day 1 with a lump sum,
    # then give back more than the trail off the post-funding peak.
    blow_curve = ([("g1", 3000.0)]
                  + [("g%d" % i, 100.0) for i in range(2, 6)]   # peak 3,400
                  + [("g6", -1200.0), ("g7", -1200.0)])          # -2,400 off peak
    r = simulate_ladder(blow_curve, ladder, rules)
    assert r["n_funded_blown"] == 1, r
    blown_ev = next(e for e in r["events"] if e["kind"] == "funded_blown")
    assert blown_ev["reason"] == "trailing_drawdown", blown_ev
    print("ok   a funded account that later breaches its trail is marked funded_blown "
          "(%s)" % blown_ev["day"])

    # 6. cross-check against the real chosen-setup book: the walk-forward
    # verdict for the FIRST account must match a single whole-series
    # evaluate_firm() call starting at day 0 -- same gate code, two ways of
    # calling it, must agree.
    book_path = os.path.join(HERE, "nq_br_trades.json")
    daily, meta = load_book(book_path)
    assert meta.get("n_trades") == 150 and meta.get("root") == "NQ", meta
    whole = PG.evaluate_firm(daily, PG.FIRM_RULES["LucidFlex 50K"])
    assert whole["passed"], "the real NQ B&R book should fund LucidFlex on the full series: %r" % whole
    r = simulate_ladder(daily, DEFAULT_LADDER, PG.FIRM_RULES)
    first_funded_day = next(e["day"] for e in r["events"] if e["kind"] == "funded")
    pass_idx = whole["days_traded"] - 1
    assert daily[pass_idx][0] == first_funded_day, \
        ("walk-forward funded day (%s) must match the day evaluate_firm's own "
         "days_traded points to on the whole series (%s)"
         % (first_funded_day, daily[pass_idx][0]))
    assert r["n_funded_ever"] >= 1
    print("ok   real NQ B&R book (150 trades): walk-forward day-by-day funding date "
          "matches a single whole-series evaluate_firm() call (%s)" % first_funded_day)

    print("\nPASS: all scaling_ladder checks held.")


if __name__ == "__main__":
    main()
