"""D3 — risk-of-ruin re-run (fable_ror method) on C10/D2 FINAL tier stats.

Reuses the risk_of_ruin.py model verbatim (Vanquish $150k, $7,500 trailing
maxDD, +$15k eval target, +$8,625 funded buffer lock, +2R/-R per trade, seed 84,
20k trials). Only difference: p is tier v2's 50.6%W (not the old 44% the prior
fable_ror.log run used), and an S-scaled arm draws each trade from D2's
per-bucket win-rate/risk-multiplier profile.

Account assumptions (from risk_of_ruin.py header, the prior fable_ror run):
  - $150k Vanquish options account
  - $7,500 TRAILING drawdown from equity peak  (ruin when eq <= peak - 7500)
  - Eval: +$15,000 profit target, min 10 trades, no time limit
  - Funded: floor locks at +$8,625 (start + 5.75%); 100% split
  - +2R win / -R loss, scratches ignored (~0 in sim)
These are unchanged; D3 only swaps in the measured tier-v2 win rate + S-scaled risk.
"""
import random

TRIALS = 20_000
DD = 7_500
TARGET = 15_000
BUFFER = 8_625

# C10 tier v2 (frozen 12mo, S>=4 + skip-[chase] + max2/day): 156 tr, 50.6%W.
TIER_P = 0.506

# D2 per-bucket tier-v2 profile (S=4/5/6+ risk multipliers, measured win rates).
# (n, win_rate, risk_mult). Counts sum 156; blended W = 50.6%.
S_BUCKETS = [
    (64, 0.531, 1.00),
    (45, 0.400, 1.25),
    (47, 0.574, 1.50),
]
# weighted pick of bucket by trade count
_TOTAL = sum(b[0] for b in S_BUCKETS)
_cum = []
_acc = 0
for n, p, m in S_BUCKETS:
    _acc += n / _TOTAL
    _cum.append((_acc, p, m))


def _pick_bucket():
    r = random.random()
    for cum, p, m in _cum:
        if r < cum:
            return p, m
    return _cum[-1][1], _cum[-1][2]  # safety


def run_eval_flat(p, risk, max_trades=2_000):
    eq = peak = 0.0
    for _ in range(1, max_trades + 1):
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return "blow"
        if eq >= TARGET:
            return "pass"
    return "blow"  # never converged = dead money


def run_eval_scaled(base_risk, max_trades=2_000):
    """Per-trade risk = base_risk * bucket mult; outcome by bucket win rate."""
    eq = peak = 0.0
    for _ in range(1, max_trades + 1):
        p, m = _pick_bucket()
        risk = base_risk * m
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return "blow"
        if eq >= TARGET:
            return "pass"
    return "blow"


def funded_survival_flat(p, risk):
    eq = peak = 0.0
    while True:
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return False
        if eq >= BUFFER:
            return True


def funded_survival_scaled(base_risk):
    eq = peak = 0.0
    while True:
        p, m = _pick_bucket()
        risk = base_risk * m
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return False
        if eq >= BUFFER:
            return True


def streak_odds(p, risk):
    """Consecutive full-risk losses from a fresh peak needed to blow: DD/risk."""
    k = int(DD // risk)
    return k, (1 - p) ** k


def arm(label, pass_rate, fund):
    blows = (1 - pass_rate) / pass_rate if pass_rate else float("inf")
    cost = 750 + blows * 375  # first month + resets (Basic)
    print(f"  eval pass {pass_rate*100:5.1f}%  |  blows/pass {blows:6.2f}  "
          f"|  $cost/funded acct ${cost:8,.0f}  |  funded->buffer {fund*100:5.1f}%")


def main():
    random.seed(84)
    print("D3 risk-of-ruin (fable_ror model) — tier v2 stats")
    print(f"  account $150k | trailing DD ${DD:,} | eval +${TARGET:,} | "
          f"funded buffer +${BUFFER:,}")
    print(f"  tier v2: 156 tr/yr, 50.6%W (C10). S-scaled profile = D2 buckets "
          f"(S4 1.0x/53.1%, S5 1.25x/40.0%, S6+ 1.5x/57.4%; avg eff risk ~$1.22k, "
          f"peak $1.5k @ $1k base).")
    print()

    arms = [
        ("flat $1k  (p=0.506)",     "flat",  TIER_P, 1_000),
        ("flat $1.5k (p=0.506)",    "flat",  TIER_P, 1_500),
        ("S-scaled $1k base",       "scaled", None,  1_000),
    ]

    for label, kind, p, risk in arms:
        if kind == "flat":
            res = [run_eval_flat(p, risk) for _ in range(TRIALS)]
            pr = sum(1 for r in res if r == "pass") / TRIALS
            fu = sum(funded_survival_flat(p, risk) for _ in range(4_000)) / 4_000
            k, pk = streak_odds(p, risk)
            print(f"{label}")
            arm(label, pr, fu)
            print(f"    streak: {k} straight losses = {pk*100:.2f}%/seq "
                  f"(peak mult {'1.0x' if risk==1000 else '1.5x'})")
        else:
            res = [run_eval_scaled(risk) for _ in range(TRIALS)]
            pr = sum(1 for r in res if r == "pass") / TRIALS
            fu = sum(funded_survival_scaled(risk) for _ in range(4_000)) / 4_000
            # streak worst-case: 5 straight S6+ losses at $1.5k = $7.5k = DD
            k_peak, pk_peak = streak_odds(0.574, 1_500)
            print(f"{label}")
            arm(label, pr, fu)
            print(f"    streak (worst: S6+ 1.5x): {k_peak} straight = "
                  f"{pk_peak*100:.2f}%/seq; avg eff risk ~$1.22k")
        print()

    # sanity: reproduce prior fable_ror.log headline (p=0.55, $1k vs $1.5k)
    print("SANITY (reproduce prior fable_ror @ p=0.55):")
    for risk in (1_000, 1_500):
        res = [run_eval_flat(0.55, risk) for _ in range(TRIALS)]
        pr = sum(1 for r in res if r == "pass") / TRIALS
        print(f"  p=0.55 ${risk}: {pr*100:.1f}% pass")


if __name__ == "__main__":
    main()
