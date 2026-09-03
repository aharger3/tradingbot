"""G7.2 / share_props -- how hard does a prop firm's CONSISTENCY RULE bite a
one-trade-a-day robot?

A consistency rule caps the share of total profit that any single position (or
day) may contribute. With ONE trade per session, position == day, so the rule
reduces to: best winning day <= K x total *valid* profit.

Input   research/g71_propfirm_daily.json -- the first traded signal of each of
        496 sessions from the 2-year book (meta.risk_dollars = 1000).
Method  i.i.d. bootstrap of the daily-R series. Each path walks day by day at a
        fixed risk-per-trade until it reaches the target (pass) or breaches the
        static max drawdown (fail) or runs out of days. On a PASSING path we
        then evaluate the consistency ratio the firm would actually measure.

Two readings of "total valid profit", because firms differ and the wording is
ambiguous:
  gross  = sum of winning days only   (strictest; TTP's "total valid profit"
           is widely read this way in their own examples)
  net    = sum of all days (= the account's net gain)   (kindest)
Both are reported. The truth is one of the two; the answer does not change.

Run: python research/g72_consistency_sim.py
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SER = json.load(open(os.path.join(HERE, "g71_propfirm_daily.json")))
R = np.array([d["r"] for d in SER], dtype=float)
RNG = np.random.default_rng(20260829)

# name, start, target$, daily_loss_limit, max_dd$, max_days, consistency K
FIRMS = [
    ("TTP 50K MAX  (30% rule, 60d)",  3000,  500, 1500,  60, 0.30),
    ("TTP 50K FLEX (50% rule, none)", 3000, 1000, 2000, 120, 0.50),
    ("TTP 100K FLEX(50% rule, none)", 6000, 2000, 4000, 120, 0.50),
    ("TTP 25K FLEX (50% rule, none)", 1500,  500, 1000, 120, 0.50),
    ("TTP 200K FLEX(50% rule, none)",12000, 4000, 8000, 120, 0.50),
]
RISKS = [100, 150, 200, 250, 300, 400, 446, 500, 750, 1000]
TRIALS = 20000


def run(target, dll, maxdd, maxdays, risk, trials=TRIALS):
    """Return arrays (passed, best_day$, gross$, net$) over `trials` paths."""
    idx = RNG.integers(0, len(R), size=(trials, maxdays))
    day_r = R[idx]
    pnl = day_r * risk
    if dll is not None:
        pnl = np.maximum(pnl, -float(dll))     # daily limit clips, does not fail
    cum = np.cumsum(pnl, axis=1)
    hit_t = cum >= target
    hit_d = cum <= -maxdd                       # static floor from start
    first_t = np.where(hit_t.any(1), hit_t.argmax(1), maxdays)
    first_d = np.where(hit_d.any(1), hit_d.argmax(1), maxdays)
    passed = first_t < first_d
    n = np.where(passed, first_t + 1, 0)        # days used on a pass
    mask = np.arange(maxdays)[None, :] < n[:, None]
    p = np.where(mask, pnl, 0.0)
    best = p.max(axis=1)
    gross = np.where(p > 0, p, 0.0).sum(axis=1)
    net = p.sum(axis=1)
    return passed, best, gross, net, n


print(f"daily-R series: {len(R)} sessions, mean {R.mean():+.4f}R, "
      f"{(R>0).mean()*100:.1f}% win, best {R.max():.3f}R, worst {R.min():.3f}R")
print()
print(f"{'firm':32s} {'risk':>6s} {'pass%':>7s} {'days':>5s} "
      f"{'bestday/GROSS':>14s} {'>K%':>7s} {'bestday/NET':>12s} {'>K%':>7s}")
print("-" * 100)
for name, target, dll, maxdd, maxdays, K in FIRMS:
    for risk in RISKS:
        ok, best, gross, net, n = run(target, dll, maxdd, maxdays, risk)
        if ok.sum() < 50:
            continue
        b, g, nt, nd = best[ok], gross[ok], net[ok], n[ok]
        rg = b / np.maximum(g, 1e-9)
        rn = b / np.maximum(nt, 1e-9)
        print(f"{name:32s} {risk:6d} {ok.mean()*100:6.1f}% {np.median(nd):5.0f} "
              f"{np.median(rg)*100:13.1f}% {(rg>K).mean()*100:6.1f}% "
              f"{np.median(rn)*100:11.1f}% {(rn>K).mean()*100:6.1f}%")
    print()
