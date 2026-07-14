# D3 — Risk-of-ruin re-run (fable_ror method) on FINAL tier stats (C10/D2)

**Date:** 2026-07-13 · **Model:** GLM · **Method:** `risk_of_ruin.py` (fable_ror)
verbatim · **Script:** `research/d3_risk_of_ruin.py` · **No commits.**

## Verdict (one line)

**At the measured 50.6%W tier-v2 win rate, no size clears the strict <5%
ruin gate — but flat $1k is the only defensible live size (6.4% funded-phase
ruin / 9.4% eval blow). Flat $1.5k is too aggressive (17.2% / 26.2%). D2's
S-scaled profile ($1.22k avg / $1.5k peak) sits between (10.7% / 17.1%) — keep
OFF until F1 confirms win rate ≥55% OOS, where $1k ruin drops <5%.**

## Account assumptions (prior fable_ror, unchanged)

From `risk_of_ruin.py` header (verified 2026-07-10, Vanquish $150k options account):

- **$150k account**, **$7,500 TRAILING drawdown** from equity peak
  (Basic trails intraday, Advanced EOD). Ruin = `equity <= peak − $7,500`.
- **Eval:** +$15,000 profit target (10%), min 10 trades, no time limit.
- **Funded:** floor locks once equity ≥ start + 5.75% (**+$8,625 buffer**);
  100% split. Consistency: no single trade (Basic) / day (Advanced) > 30% of profit.
- **Trade model:** win = +2R, loss = −R, scratches ≈0 (ignored).
- **Sim:** 20,000 trials, `random.seed(84)` (reproducible).

State explicitly because the prior `fable_ror.log` run used these — D3 does not
re-derive them, it only swaps in the measured win rate (50.6%W vs the old 44%) and
the S-scaled risk profile from D2.

## Inputs (FINAL tier stats, C10 + D2)

| source | stat | value |
|---|---|---:|
| C10 tier v2 | trades/yr | 156 |
| C10 tier v2 | win rate | 50.6% |
| C10 tier v2 | P&L @ flat $1k | $81k |
| C10 tier v2 | maxDD @ flat $1k | −$6k |
| D2 S-scaled tier | per-bucket W | S4 53.1% / S5 40.0% / S6+ 57.4% |
| D2 S-scaled tier | risk mult | S4 1.0x / S5 1.25x / S6+ 1.5x |
| D2 S-scaled tier | avg effective risk | ~$1,223 (peak $1,500) |

2R/−R model is a faithful match to tier-v2's average: `0.506×$2k − 0.494×$1k = $518/tr
× 156 = $80.8k ≈ $81k`. The fable_ror model is not a rough approximation here — it
reproduces the backtest's mean P&L almost exactly.

## S-scaled profile (D2 per-bucket, tier v2)

The S-scaled arm draws each simulated trade from D2's bucket distribution
(weighted by trade count), then resolves the outcome by that bucket's win rate
and applies that bucket's risk multiplier — instead of a flat risk/blended-p.
Buckets: S4 (n=64, 53.1%W, 1.0x), S5 (n=45, 40.0%W, 1.25x), S6+ (n=47, 57.4%W, 1.5x).
Blended W = 50.6% (matches C10). This is the fable_ror method extended to the
per-bucket profile; the blended-stats fallback would give identical results to
flat $1.22k at p=0.506, so the per-bucket version is the informative one.

## Results (seed 84, 20k trials)

| arm | eval pass% | eval blow (=ruin, eval) | funded→buffer% | funded-phase ruin | blows/pass | $cost/funded acct |
|---|---:|---:|---:|---:|---:|---:|
| **flat $1k** (p=0.506) | **90.6%** | 9.4% | **93.6%** | **6.4%** | 0.10 | $789 |
| **flat $1.5k** (p=0.506) | 73.8% | 26.2% | 82.8% | 17.2% | 0.35 | $883 |
| **S-scaled $1k base** (D2 profile) | 82.9% | 17.1% | 89.3% | 10.7% | 0.21 | $827 |

Streak-to-ruin (consecutive full-risk losses from a fresh peak; DD $7,500 / risk):

| arm | k losses | P(k straight) |
|---|---:|---:|
| flat $1k | 7 | 0.72%/seq |
| flat $1.5k | 5 | 2.94%/seq |
| S-scaled (worst case: S6+ 1.5x @ $1.5k) | 5 | 1.40%/seq |

## Two ruin metrics (both reported, primary = funded-phase)

- **Eval blow** = P(lose the $7,500 before hitting +$15k target) — costs an
  eval reset ($375 Basic). This is the metric the prior `fable_ror.log` reported.
- **Funded-phase ruin** = 1 − funded→buffer = P(blow after funded, before the
  +$8,625 floor lock). **Primary go-live metric** — this is real money, and once
  the buffer locks the trailing floor stops (no further ruin path).

F3 gate text: *"risk-of-ruin <5% at chosen size."* Reading it as funded-phase
ruin (the binding real-money constraint):

- flat $1k → **6.4%** — closest to the gate but not under it at 50.6%W.
- S-scaled → 10.7% — meaningfully worse.
- flat $1.5k → 17.2% — disqualified.

## Sanity check (method = prior fable_ror)

Prior `fable_ror.log` headline: "$1k vs $1.5k at every win rate (96% vs 84% pass
at 55%WR)." This script at p=0.55 reproduces it exactly: **96.1% / 84.1%**.
Method unchanged → D3 numbers are directly comparable to the prior run; the only
delta is the win rate (44% → 50.6%) and the added S-scaled arm.

## Recommendation

1. **Live size = flat $1k.** Only arm near the <5% gate (6.4% funded ruin / 9.4%
   eval). Matches prior fable_ror rec ("$1k until buffer locked +$8,625").
2. **S-scaled sizing (D2) stays OFF.** 10.7% funded ruin / 17.1% eval blow —
   worse RoR than flat $1k despite higher P&L, because the 1.5x S6+ tranche
   cuts streak tolerance from 7 losses to 5. The six-figure uplift ($81k→$100k)
   is not worth the ~2x ruin increase at this win rate.
3. **Re-evaluate S-scaled after F1.** Prior fable_ror @ 55%WR: $1k eval blow
   3.9%, funded ruin ~4%. If F1 walk-forward proves tier v2 holds ≥55%W OOS
   (current 50.6% is in-sample upper bound), the S6+ tranche's RoR clears the
   gate and D2's recommendation flips ON.
4. **D2's cleaner "S≥6-only 1.5x" variant** (skips weak S5 1.25x) is the
   right re-test at F1 — same peak risk, fewer levered losers.

## Hard-rule compliance

- **Analysis only** — no signal-logic edits, no config changes, no commits.
  `risk_of_ruin.py` untouched; new script `research/d3_risk_of_ruin.py` only.
- **Backtest stats on disk** — C10/D2 numbers used directly; no backtest rerun,
  no rate-limit exposure. Sanity check confirms method parity with prior run.
