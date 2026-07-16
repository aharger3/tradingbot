"""G4 — prop-firm fit: D3 fable_ror model adapted to 2026 futures-prop specs.

Reuses the d3_risk_of_ruin.py trade model verbatim (+2R win / -1R loss,
seed 84, 20k trials) but swaps the account envelope per firm:

  - Apex Trader Funding 4.0 (post 2026-03-01), $150K + $100K EOD plans
  - Topstep $150K / $100K Trading Combine -> Express Funded Account (XFA)
  - MyFundedFutures Pro $150K (3% EOD trail)

Key structural differences vs the old Vanquish $150k/$7.5k envelope:
  - much smaller trailing DD ($3-4.5k, EOD-type trailing)
  - much smaller lock buffer (DD+~$100 safety net, not +$8,625)
  - eval risk unit and funded risk unit are allowed to differ
    (pass aggressively, trade funded conservatively)
  - Apex 4.0 evals expire in 30 calendar days (~13 trades at 0.7/day)
    -> failed-or-expired attempt = re-buy

Phases modeled per firm/size/win-rate:
  1. EVAL   : sweep R_eval, expected $ cost per funded account
  2. FUNDED : sweep R_funded, pre-lock ruin (reach safety-net buffer before
              trailing-DD blow) -> pick max R with ruin < 5%
  3. LIFECYCLE: full account life at chosen R_funded — pre-lock, then floor
              locks, monthly withdrawals down to buffer (payout caps/splits
              applied), death when equity hits the locked floor. Yields
              expected total withdrawn + lifespan -> churn-adjusted $/mo.

EOD-vs-intraday note: the +-R closed-trade model matches EOD trailing well
(threshold ratchets on settled equity). Intraday-trailing plans (Apex
Intraday, MFF Rapid) ratchet on open-trade highs, which this model does NOT
capture -> their true ruin is strictly worse. Only EOD plans are modeled.
"""
import random

TRIALS = 20_000
LIFE_TRIALS = 8_000
TRADES_PER_MO = 13          # 156/yr (C10 tier v2), ~0.7/day
WIN_RATES = [0.430, 0.455, 0.506]   # F1 pooled OOS / pure-forward / in-sample

FIRMS = {
    # name: dict of envelope + economics
    "Apex $150K EOD": dict(
        dd=4_000, target=9_000, buffer=4_100,        # safety net = DD+$100
        eval_fee=397, eval_trade_cap=13,             # 30-day expiry -> re-buy
        activation=99, split=1.00, split_after=None,
        caps=[2_500, 3_000, 3_000, 3_000, 4_000, 5_000],  # 6-payout ladder
        cap_after=None,                              # uncapped after ladder
        max_n=20,
    ),
    "Apex $100K EOD": dict(
        dd=3_000, target=6_000, buffer=3_100,
        eval_fee=297, eval_trade_cap=13,
        activation=99, split=1.00, split_after=None,
        caps=[2_000, 2_500, 2_500, 3_000, 4_000, 4_000],
        cap_after=None,
        max_n=20,
    ),
    "Topstep $150K XFA": dict(
        dd=4_500, target=9_000, buffer=4_500,        # MLL locks at $0
        eval_fee=149, eval_trade_cap=None,           # monthly, no time limit
        activation=149, split=1.00, split_after=(10_000, 0.90),
        caps=None, cap_flat=5_000, cap_pct=0.50,     # 50% of balance <= $5k
        cap_after=None,
        max_n=5,
    ),
    "Topstep $100K XFA": dict(
        dd=3_000, target=6_000, buffer=3_000,
        eval_fee=99, eval_trade_cap=None,
        activation=149, split=1.00, split_after=(10_000, 0.90),
        caps=None, cap_flat=3_000, cap_pct=0.50,
        cap_after=None,
        max_n=5,
    ),
    "MFF Pro $150K": dict(
        dd=4_500, target=9_000, buffer=4_600,        # 3% EOD, locks start+$100
        eval_fee=477, eval_trade_cap=None,           # monthly, no time limit
        activation=0, split=0.80, split_after=None,
        caps=None, cap_flat=None, cap_pct=None,      # uncapped, biweekly
        cap_after=None,
        max_n=3,                                     # 100k/150k sim-funded cap
    ),
}


def sim_eval(p, risk, dd, target, trade_cap):
    """One eval attempt. Returns (outcome, n_trades)."""
    eq = peak = 0.0
    cap = trade_cap or 2_000
    for t in range(1, cap + 1):
        eq += 2 * risk if random.random() < p else -risk
        peak = max(peak, eq)
        if eq <= peak - dd:
            return "blow", t
        if eq >= target:
            return "pass", t
    return "timeout", cap


def eval_cost(p, risk, spec):
    """Expected $ eval spend per funded account at this eval risk."""
    res = [sim_eval(p, risk, spec["dd"], spec["target"],
                    spec["eval_trade_cap"]) for _ in range(TRIALS)]
    n_pass = sum(1 for r, _ in res if r == "pass")
    if n_pass == 0:
        return None, 0.0
    pass_rate = n_pass / TRIALS
    if spec["eval_trade_cap"]:                      # Apex: $fee per attempt
        cost = spec["eval_fee"] / pass_rate
    else:                                           # monthly subscription
        # total months paid across attempts until one pass
        mean_tr = sum(t for _, t in res) / TRIALS   # trades per attempt
        months_per_attempt = max(1.0, mean_tr / TRADES_PER_MO)
        cost = spec["eval_fee"] * months_per_attempt / pass_rate
    return cost + spec["activation"], pass_rate


def funded_prelock_ruin(p, risk, dd, buffer):
    """P(blow trailing DD before reaching lock buffer). D3 method."""
    ruins = 0
    for _ in range(TRIALS):
        eq = peak = 0.0
        while True:
            eq += 2 * risk if random.random() < p else -risk
            peak = max(peak, eq)
            if eq <= peak - dd:
                ruins += 1
                break
            if eq >= buffer:
                break
    return ruins / TRIALS


def payout_cap(spec, k, eq):
    """Max withdrawal for payout #k (1-based) at equity eq."""
    if spec.get("caps"):
        ladder = spec["caps"]
        return ladder[k - 1] if k <= len(ladder) else float("inf")
    c = float("inf")
    if spec.get("cap_flat"):
        c = spec["cap_flat"]
    if spec.get("cap_pct"):
        c = min(c, spec["cap_pct"] * eq)
    return c


def lifecycle(p, risk, spec, max_months=60):
    """Full account life. Returns (total_withdrawn_net, months, made_lock).

    Pre-lock: trailing DD. Post-lock: floor at start ($0), withdraw at each
    month-end down to buffer (capped). Death = eq <= floor (or trailing blow
    pre-lock). Split applied (Topstep: 100% of first $10k then 90%).
    """
    dd, buf = spec["dd"], spec["buffer"]
    eq = peak = 0.0
    locked = False
    withdrawn_gross = 0.0
    k = 0
    for month in range(1, max_months + 1):
        for _ in range(TRADES_PER_MO):
            eq += 2 * risk if random.random() < p else -risk
            if not locked:
                peak = max(peak, eq)
                if eq <= peak - dd:
                    return _net(withdrawn_gross, spec), month, False
                if eq >= buf:
                    locked = True
            else:
                if eq <= 0:
                    return _net(withdrawn_gross, spec), month, True
        if locked and eq > buf:
            k += 1
            w = min(eq - buf, payout_cap(spec, k, eq))
            if w > 0:
                withdrawn_gross += w
                eq -= w
    return _net(withdrawn_gross, spec), max_months, locked


def _net(gross, spec):
    sa = spec.get("split_after")
    if sa:
        thresh, later = sa
        if gross <= thresh:
            return gross * spec["split"]
        return thresh * spec["split"] + (gross - thresh) * later
    return gross * spec["split"]


def main():
    random.seed(84)
    print("G4 prop-firm fit — fable_ror model on 2026 firm envelopes")
    print(f"{TRIALS:,} trials/point, {TRADES_PER_MO} trades/mo, +2R/-1R\n")

    for name, spec in FIRMS.items():
        print("=" * 78)
        print(f"{name}: DD ${spec['dd']:,} EOD-trail | target ${spec['target']:,}"
              f" | lock buffer ${spec['buffer']:,} | eval ${spec['eval_fee']}"
              f"{'/attempt(30d)' if spec['eval_trade_cap'] else '/mo'}"
              f" | max {spec['max_n']} accts")
        for p in WIN_RATES:
            # 1. best eval risk (min cost per funded account)
            best = (None, float("inf"), 0.0)
            for r_ev in range(500, 4_001, 250):
                c, pr = eval_cost(p, r_ev, spec)
                if c is not None and c < best[1]:
                    best = (r_ev, c, pr)
            r_ev, ev_cost, ev_pass = best

            # 2. max funded risk with pre-lock ruin < 5%
            r_star, ruin_star = None, None
            for r_f in range(650, 99, -25):
                ruin = funded_prelock_ruin(p, r_f, spec["dd"], spec["buffer"])
                if ruin < 0.05:
                    r_star, ruin_star = r_f, ruin
                    break
            line = f"  p={p:.3f}: eval R*=${r_ev} (pass {ev_pass*100:.0f}%," \
                   f" ${ev_cost:,.0f}/funded)"
            if r_star is None:
                print(line + "  |  funded: NO risk unit >= $100 clears <5%")
                continue

            # 3. lifecycle at r_star
            res = [lifecycle(p, r_star, spec) for _ in range(LIFE_TRIALS)]
            tot = sum(w for w, _, _ in res) / LIFE_TRIALS
            mos = sum(m for _, m, _ in res) / LIFE_TRIALS
            lock = sum(1 for _, _, l in res if l) / LIFE_TRIALS
            alive60 = sum(1 for _, m, _ in res if m >= 60) / LIFE_TRIALS
            net_life = tot - ev_cost
            per_mo = net_life / mos if mos else 0
            n = spec["max_n"]
            print(line)
            print(f"      funded R*=${r_star} (pre-lock ruin {ruin_star*100:.1f}%)"
                  f" | lock {lock*100:.0f}% | E[withdrawn] ${tot:,.0f}"
                  f" over {mos:.1f} mo (alive@60mo {alive60*100:.0f}%)")
            print(f"      per-acct net (incl eval/act cost) ${net_life:,.0f}"
                  f" (${per_mo:,.0f}/mo) | x{n} copy-stack:"
                  f" ${n*net_life:,.0f} lifetime, ${n*per_mo:,.0f}/mo")
        print()


if __name__ == "__main__":
    main()
