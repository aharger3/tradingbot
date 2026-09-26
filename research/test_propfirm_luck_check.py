"""Plain asserts for propfirm_luck_check.py -- synthetic P&L only, no market
data, no book file required. Runs on the Mac with nothing but the standard
library.

    python research/test_propfirm_luck_check.py

Checks:
 1. a real-edge series (positive per-day mean in BOTH halves, real order is
    nothing special) earns eval_ready -- real and shuffled pass rates both
    clear the floor, and shuffled clearly beats the zero-edge (de-meaned)
    baseline.
 2. a ZERO-mean series (values sum to ~0 in each half) whose specific
    historical order happens to be a lucky one -- found here by literally
    searching random reorderings of the same values for the one with the
    highest start-date pass rate, then using THAT as "real" -- does NOT
    earn eval_ready: the real rate is inflated by the lucky order, but the
    mean pass rate over fresh reshuffles of the same values (shuffled_pass_
    pct) reveals the true, near-zero rate and stays under the floor.
 3. a rule dict missing keys evaluate_prop_challenge requires raises
    INSIDE the check (a KeyError building the simulator kwargs) and
    firm_luck_check() catches it -- eval_ready False, the repr in "error",
    nothing propagates.

n_shuffles is turned down from the module's own default (500, sized for the
nightly gate's real book) to keep this file fast; the arithmetic exercised
is identical either way.
"""
import datetime
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import propfirm_luck_check as luck  # noqa: E402

# A rule with a $3,000 target, generous consistency/min-days (so ONLY the
# profit-target and trailing-DD/daily-loss dynamics matter), used across
# every check in this file so the numbers below are all against one ruler.
RULE = dict(account_size=50_000.0, profit_target_pct=0.06, trailing_dd_pct=0.06,
           daily_loss_limit_pct=0.04, min_trading_days=0, consistency_pct=1.0,
           dd_mode="eod", dd_lock_at_breakeven=False)


def _dates(n, start="2024-01-01"):
    d0 = datetime.date.fromisoformat(start)
    return [str(d0 + datetime.timedelta(days=i)) for i in range(n)]


def _zero_mean_vals(n, rng):
    """n values summing to exactly 0 -- half a handful of positive sizes,
    the rest scaled negative weights so the two halves cancel exactly."""
    pos = [rng.choice([150, 200, 250, 300]) for _ in range(n // 2)]
    neg_weights = [rng.choice([1, 2, 3]) for _ in range(n - len(pos))]
    scale = -sum(pos) / sum(neg_weights)
    vals = pos + [w * scale for w in neg_weights]
    rng.shuffle(vals)
    return vals


def _luckiest_order(vals, dates, trials, rng):
    """The highest-`_score_windows`-pass_pct reordering of `vals` found over
    `trials` random tries -- i.e. deliberately the lucky tail of the same
    distribution `shuffled_pass_pct` (many MORE reshuffles, averaged) would
    reveal the truth about."""
    best = None
    for _ in range(trials):
        order = vals[:]
        rng.shuffle(order)
        pct, _ = luck._score_windows(list(zip(dates, order)), RULE, luck.HORIZON)
        if pct is not None and (best is None or pct > best[0]):
            best = (pct, order[:])
    return best[1]


def main():
    # 1. real edge: positive-mean daily P&L in both halves, ordinary order.
    half_n = 260
    dates = _dates(2 * half_n)
    gen = random.Random(1)
    choices = [200, -80, 250, -60, 220, -100, 180, -40, 210, -70]  # mean +71/day
    daily_edge = [(d, gen.choice(choices)) for d in dates]
    split_day = dates[half_n]
    res = luck.firm_luck_check(daily_edge, RULE, n_shuffles=80, seed=42,
                               split_day=split_day)
    assert res["error"] is None, "real-edge check raised: %r" % res["error"]
    assert res["eval_ready"], "a real, positive-mean series should be eval_ready: %r" % res
    for h in ("h1", "h2"):
        r, s, z = (res[h]["real_pass_pct"], res[h]["shuffled_pass_pct"],
                  res[h]["zero_edge_pass_pct"])
        assert r >= luck.PASS_FLOOR_PCT and s >= luck.PASS_FLOOR_PCT, \
            "%s: real/shuffled should both clear the floor: %r" % (h, res[h])
        assert s - z >= luck.EVAL_READY_MARGIN_PTS, \
            "%s: shuffled should clear the zero-edge baseline by the margin: %r" % (h, res[h])
    print("ok   a real, positive-mean series (both halves) earns eval_ready")

    # 2. zero-edge, lucky order: same idea per half -- generate a ZERO-mean
    # multiset, then search reorderings of it for the luckiest one and use
    # THAT as the "historical" order. shuffled_pass_pct (many more, fresh
    # reshuffles) must reveal the true near-zero rate and block eval_ready.
    dates_h1, dates_h2 = dates[:half_n], dates[half_n:]
    gen2 = random.Random(11)
    vals_h1 = _zero_mean_vals(half_n, gen2)
    vals_h2 = _zero_mean_vals(half_n, gen2)
    lucky_h1 = _luckiest_order(vals_h1, dates_h1, 500, random.Random(22))
    lucky_h2 = _luckiest_order(vals_h2, dates_h2, 500, random.Random(33))
    daily_lucky = list(zip(dates_h1, lucky_h1)) + list(zip(dates_h2, lucky_h2))
    res2 = luck.firm_luck_check(daily_lucky, RULE, n_shuffles=150, seed=999,
                                split_day=split_day)
    assert res2["error"] is None, "lucky-order check raised: %r" % res2["error"]
    assert not res2["eval_ready"], \
        "a zero-edge series with a lucky historical order must NOT be eval_ready: %r" % res2
    for h in ("h1", "h2"):
        assert res2[h]["real_pass_pct"] >= luck.PASS_FLOOR_PCT, \
            "the search should have found a real order that clears the floor: %r" % res2[h]
        assert res2[h]["shuffled_pass_pct"] < luck.PASS_FLOOR_PCT, \
            "fresh reshuffles of the same zero-edge values should stay under the floor: %r" % res2[h]
    print("ok   a zero-edge series with a lucky order (real %.1f%%/%.1f%%, "
          "shuffled %.1f%%/%.1f%%) does NOT earn eval_ready"
          % (res2["h1"]["real_pass_pct"], res2["h2"]["real_pass_pct"],
             res2["h1"]["shuffled_pass_pct"], res2["h2"]["shuffled_pass_pct"]))

    # 3. a broken rule (missing keys evaluate_prop_challenge requires) must
    # not raise out of firm_luck_check -- caught, reported, eval_ready False.
    broken_rule = dict(account_size=50_000.0, profit_target_pct=0.06)  # incomplete
    res3 = luck.firm_luck_check([("d1", 100.0), ("d2", -50.0)], broken_rule,
                                n_shuffles=5, seed=1)
    assert res3["eval_ready"] is False and res3["error"], \
        "a broken rule should be caught, not raised: %r" % res3
    print("ok   a broken rule dict is caught inside firm_luck_check (%s), "
          "never raised" % res3["error"])

    print("\nPASS: all propfirm_luck_check checks held.")


if __name__ == "__main__":
    main()
