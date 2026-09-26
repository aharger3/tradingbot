"""Plain asserts for propfirm_gate.py -- synthetic P&L only, no market data,
no book file required. Runs on the Mac with nothing but the standard library.

    python research/test_propfirm_gate.py

Checks:
 1. a clean curve passes a real firm rule (Topstep 50K Combine).
 2. a curve that breaches the trailing drawdown intraday but NOT end-of-day
    -- proves dd_mode is correctly plumbed from a rule dict through to
    omen_metrics.evaluate_prop_challenge.
 3. a single brutal day breaches the daily loss limit before anything else.
 4. a target hit almost entirely on one day breaches the consistency rule
    (Vanquish's real 30% cap) and is never diluted before the series ends.
 5. all_starts_pass_rate()'s sweep arithmetic on a hand-checked series.
 6. every FIRM_RULES entry actually runs through evaluate_prop_challenge
    (catches a typo'd kwarg key before it ever reaches the nightly loop).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from propfirm_gate import (FIRM_RULES, evaluate_firm, gate_series,
                           all_starts_pass_rate)

TOPSTEP = FIRM_RULES["Topstep 50K Combine"]
VANQUISH = FIRM_RULES["Vanquish Trader Advanced Options 50K"]

# A rule built for test #2 only -- isolates the dd_mode plumbing from every
# other rule (unreachable target, no daily loss limit, no consistency cap)
# so the ONLY thing that can fail is the trailing drawdown check itself.
INTRADAY_PROBE = dict(
    account_size=50_000.0, profit_target_pct=1.0, trailing_dd_pct=0.04,
    dd_mode="intraday", dd_lock_at_breakeven=False,
    daily_loss_limit_pct=1.0, min_trading_days=0, consistency_pct=1.0,
    max_days=None,
)


def main():
    # 1. clean pass: Topstep's own $3,000 target on 50K, 5 days of $600,
    # never a pullback, no consistency rule at the eval stage.
    clean = [("d%d" % i, 600) for i in range(1, 6)]
    r = evaluate_firm(clean, TOPSTEP)
    assert r["passed"] and r["fail_reason"] is None, \
        "clean curve should pass Topstep 50K Combine: %r" % r
    print("ok   clean curve passes a real firm rule (Topstep 50K Combine)")

    # 2. intraday trailing DD catches a mid-day breach an EOD-only day misses.
    # peak $2,500 after 5 up days, given back to $1,100 over two down days
    # (each individually smaller than the disabled daily loss limit), then a
    # day that closes FLAT but dips $700 intraday.
    curve = ([{"day": "d%d" % i, "pnl": 500} for i in range(1, 6)]
             + [{"day": "d6", "pnl": -700}, {"day": "d7", "pnl": -700}])
    curve.append({"day": "d8", "pnl": 0, "intraday_min": -700})
    intraday_rule = dict(INTRADAY_PROBE, dd_mode="intraday")
    eod_rule = dict(INTRADAY_PROBE, dd_mode="eod")
    r_intra = evaluate_firm(curve, intraday_rule)
    r_eod = evaluate_firm(curve, eod_rule)
    assert r_intra["fail_reason"] == "trailing_drawdown" and r_intra["fail_day"] == "d8", \
        "intraday mode should breach on d8: %r" % r_intra
    assert r_eod["fail_reason"] != "trailing_drawdown", \
        "EOD mode should NOT see the intraday-only dip: %r" % r_eod
    print("ok   intraday trailing DD breaches on d8; EOD mode on the same "
          "curve does not (dd_mode is correctly plumbed through)")

    # 3. daily loss limit: one brutal day, well inside every other rule.
    curve = [("d1", 300), ("d2", -1200), ("d3", 100)]
    r = evaluate_firm(curve, TOPSTEP)
    assert not r["passed"] and r["fail_reason"] == "daily_loss_limit" and r["fail_day"] == "d2", \
        "d2's -1200 should breach Topstep's $1,000 daily loss limit: %r" % r
    print("ok   a single -$1,200 day breaches the $1,000 daily loss limit on d2")

    # 4. consistency: Vanquish's $5,000 target (10% of 50K) hit almost
    # entirely on day 1, never diluted below its 30% cap across the
    # 4 minimum trading days.
    curve = [("d1", 5000)] + [("d%d" % i, 10) for i in range(2, 6)]
    r = evaluate_firm(curve, VANQUISH)
    assert not r["passed"] and r["fail_reason"] == "consistency", \
        "day 1's $5,000 should dominate and breach Vanquish's 30%% consistency cap: %r" % r
    print("ok   a target hit almost entirely on day 1 breaches Vanquish's "
          "30%% consistency rule")

    # 5. all_starts_pass_rate(): 20 days of Topstep's own clean $600/day.
    # Reaching the $3,000 target takes exactly 5 days, so a start needs >=5
    # days left in the series -- true for starts 0..15 (16 of 20), false for
    # the last 4 (4, 3, 2, 1 days left, $2,400/$1,800/$1,200/$600 max).
    series20 = [("d%d" % i, 600) for i in range(1, 21)]
    pct, n = all_starts_pass_rate(series20, TOPSTEP)
    assert n == 20 and pct == 80.0, \
        "expected 16/20 = 80.0%% of start dates to pass, got %s/%s" % (pct, n)
    print("ok   all_starts_pass_rate: 16/20 = 80.0%% of start dates pass "
          "(hand-checked)")

    # 6. every FIRM_RULES entry actually runs -- a typo'd kwarg key or a
    # value evaluate_prop_challenge rejects would otherwise only surface the
    # night the nightly loop tries to use it for real.
    results = gate_series(clean, FIRM_RULES)
    assert set(results) == set(FIRM_RULES), "gate_series dropped or added a firm"
    for name, res in results.items():
        assert "passed" in res and "all_starts_pass_pct" in res, \
            "malformed result for %s: %r" % (name, res)
    print("ok   gate_series() runs cleanly across all %d FIRM_RULES entries"
          % len(FIRM_RULES))

    print("\nPASS: all propfirm_gate checks held.")


if __name__ == "__main__":
    main()
