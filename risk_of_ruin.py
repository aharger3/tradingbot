"""Vanquish $150k options account risk-of-ruin Monte Carlo (2026-07-10).

Facts (support.vanquishtrader.com, verified 2026-07-10):
- $150k account, max drawdown $7,500 TRAILING from equity peak.
  Basic plan trails intraday on unrealized peaks ($750/mo, $375 reset);
  Advanced trails end-of-day only ($1,499/mo, $749 reset).
- Eval: +$15,000 profit target (10%), min 10 trades, no time limit, no daily loss limit.
- Funded: floor locks once equity >= start + 5.75% ($8,625 buffer); 100% split.
- Consistency: no single trade (Basic) / day (Advanced) > 30% of total profit.

Model: each trade wins +2R with prob p, loses -R otherwise (scratches ignored —
they don't move the floor much and our sim counts them ~0). Trailing floor =
max(equity peak) - 7500. Ruin when equity <= floor + nothing left... i.e.
equity - (peak - 7500) <= 0. Eval passes at +15000 cumulative.
"""
import random

TRIALS = 20_000
DD = 7_500
TARGET = 15_000


def run_eval(p: float, risk: float, max_trades: int = 2_000):
    """Return ('pass'|'blow', n_trades)."""
    eq = peak = 0.0
    for n in range(1, max_trades + 1):
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return "blow", n
        if eq >= TARGET:
            return "pass", n
    return "blow", max_trades  # never converged = treat as dead money


def funded_survival(p: float, risk: float):
    """P(reach the +$8,625 buffer lock before ruin) once funded."""
    eq = peak = 0.0
    while True:
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - DD:
            return False
        if eq >= 8_625:
            return True


def streak_odds(p: float, risk: float):
    """Consecutive full-risk losses from a fresh peak needed to blow: DD/risk."""
    k = int(DD // risk)
    return k, (1 - p) ** k


def main():
    random.seed(84)  # reproducible
    print(f"{'p':>4} {'risk':>6} | eval pass% | med trades | blows/pass | "
          f"$cost/funded acct | funded->buffer%")
    for p in (0.35, 0.40, 0.45, 0.50, 0.55):
        for risk in (1_000, 1_500):
            res = [run_eval(p, risk) for _ in range(TRIALS)]
            passes = [n for r, n in res if r == "pass"]
            pass_rate = len(passes) / TRIALS
            med = sorted(passes)[len(passes) // 2] if passes else 0
            # expected resets before a pass (geometric): (1-q)/q
            blows_per_pass = (1 - pass_rate) / pass_rate if pass_rate else float("inf")
            cost = 750 + blows_per_pass * 375  # first month + resets (Basic)
            fund = sum(funded_survival(p, risk) for _ in range(4_000)) / 4_000
            k, pk = streak_odds(p, risk)
            print(f"{p:.2f} {risk:>6} |   {pass_rate*100:5.1f}%   | {med:>6}     | "
                  f"{blows_per_pass:7.2f}    |   ${cost:8,.0f}      | {fund*100:5.1f}%"
                  f"   (streak: {k} straight losses = {pk*100:.2f}%/seq)")


if __name__ == "__main__":
    main()
