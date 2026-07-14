# D2 — S-score-scaled sizing A/B (flat $1k vs S-scaled)

**Task:** 12mo A/B — per-trade risk scaled by selection score
(S=4 → 1.0x, S=5 → 1.25x, S≥6 → 1.5x, $1k base) vs flat $1k. Flag-gated, default OFF.
**Date:** 2026-07-13 · **Model:** Opus · **Baseline:** `research/c1_off_charts.json`
(C10's frozen 12mo tier-v2 baseline, 671 traded / 866 signals).

## Verdict (one line)

**S-score sizing lifts 12mo P&L +$16.4k (+20.9%) full-pop and +$19.3k (+23.8%) on
tier v2, for a proportional maxDD increase of −$1.6k / −$1.3k — return-to-drawdown
ratio improves on both (full-pop 3.63→4.09, tier 13.50→13.83). BUT the entire edge
is the S≥6 tranche (genuinely 44%/57.4%W, scaled 1.5x); the S=5 1.25x step levers the
*weakest* bucket (33%/40%W) for near-zero gain. It is real, accretive leverage — keep
the flag OFF pending D3 risk-of-ruin at the larger effective size (~$1.22k avg / $1.5k
peak per trade); a cleaner "S≥6-only 1.5x" ladder captures ~90% of the uplift.**

## Why this hits backtest P&L (unlike D1)

D1's SCARFACE_CONTRACT flag lives only in the live/paper card path — the 12mo P&L
engine (`backtest_12mo → backtest_week.simulate_day → SimTrade.pnl`) never reads it,
so it was bit-identical A==B. **D2's flag scales `SimTrade.pnl` directly**:

```
pnl = (stock_move / stock_risk) * (RISK_DOLLARS * sscore_mult(reason))
```

`sscore_mult` reads the " S<n>" score already in each trade's `reason`. Because P&L is
**exactly linear in risk dollars** and sizing changes no signal detection, no outcome,
and — for tier v2 (green-stop OFF, max-2 is a count) — no *selection*, both arms trade
the identical set and the scaled arm equals `flat_pnl × mult(S)` trade-for-trade. That
is bit-identical to what a real `OMEN_SSCORE_SIZING=1` 12mo rerun writes, so it is
computed over the frozen charts json — no network, no rate-limit risk (standing rule).
Flag verified live: S4 win $2,000 (unchanged), S5 win $2,500, S6 win $3,000, S5 loss
−$1,250; flag default OFF confirmed.

## Multiplier map & coverage

| S-score | multiplier | full-pop n | tier v2 n |
|---|---:|---:|---:|
| S≤3 / unscored | 1.0x | 375 | 0 (gated out) |
| S=4 | 1.0x | 99 | 64 |
| S=5 | 1.25x | 97 | 45 |
| S≥6 | 1.5x | 100 | 47 |

Scale-eligible (S≥5): full-pop 197/671 (29%), tier v2 92/156 (59%).

## TABLE 1 — Full population (671 traded)

| arm | n | W | L | win% | P&L | maxDD |
|---|---:|---:|---:|---:|---:|---:|
| **A — flat $1k (flag OFF)** | 671 | 251 | 419 | 37.5% | **$78,190** | **−$21,511** |
| **B — S-scaled (flag ON)** | 671 | 251 | 419 | 37.5% | **$94,563** | **−$23,139** |
| **Δ (B − A)** | 0 | 0 | 0 | 0.0pp | **+$16,372 (+20.9%)** | **−$1,628 (+7.6% deeper)** |

Return / \|maxDD\|: A 3.63 → B **4.09** (improves).

## TABLE 2 — Tier v2 (S≥4, skip-[chase], max 2/day, skip-news) — 156 traded

| arm | n | W | L | win% | P&L | maxDD |
|---|---:|---:|---:|---:|---:|---:|
| **A — flat $1k (flag OFF)** | 156 | 79 | 77 | 50.6% | **$81,000** | **−$6,000** |
| **B — S-scaled (flag ON)** | 156 | 79 | 77 | 50.6% | **$100,250** | **−$7,250** |
| **Δ (B − A)** | 0 | 0 | 0 | 0.0pp | **+$19,250 (+23.8%)** | **−$1,250 (+20.8% deeper)** |

Return / \|maxDD\|: A 13.50 → B **13.83** (improves slightly).
Arm A reproduces C10's published tier v2 exactly (156 tr, 50.6%W, $81k, −$6k maxDD) —
baseline sanity check passes. **Six figures ($100k) is reached on tier v2 in-sample
with S-scaling** (C10 flagged D-phase sizing as the path there).

## TABLE 3 — Per-S-bucket: where the uplift comes from (the real finding)

**Full population**

| bucket | mult | n | win% | flat P&L | scaled P&L | Δ |
|---|---:|---:|---:|---:|---:|---:|
| S≤3 / unscored | 1.0x | 375 | 36.0% | $23,702 | $23,702 | $0 |
| S=4 | 1.0x | 99 | 40.4% | $21,000 | $21,000 | $0 |
| S=5 | 1.25x | 97 | **33.3%** | $1,489 | $1,861 | +$372 |
| S≥6 | 1.5x | 100 | **44.0%** | $32,000 | $48,000 | **+$16,000** |

**Tier v2**

| bucket | mult | n | win% | flat P&L | scaled P&L | Δ |
|---|---:|---:|---:|---:|---:|---:|
| S=4 | 1.0x | 64 | 53.1% | $38,000 | $38,000 | $0 |
| S=5 | 1.25x | 45 | **40.0%** | $9,000 | $11,250 | +$2,250 |
| S≥6 | 1.5x | 47 | **57.4%** | $34,000 | $51,000 | **+$17,000** |

**S-score is not monotonic in win rate.** S=5 is the *worst* bucket on both
populations (33.3% full-pop / 40.0% tier) yet the spec scales it up 1.25x — that step
adds almost nothing (+$372 / +$2,250) and levers a below-average cohort. **~90% of the
uplift is the S≥6 1.5x step** (+$16k / +$17k), and S≥6 genuinely wins more (44% / 57.4%,
above each population's mean), so scaling it is accretive rather than pure leverage.
That is why the return-to-drawdown ratio *improves* despite maxDD deepening.

## Interpretation

- **It works, and it's the honest path to six figures.** C10 concluded 50%W + 1–2/day
  is not in this signal population and that sizing (D2/D3) is how $81k becomes $100k+.
  D2 confirms: tier v2 clears $100k in-sample at these multipliers.
- **It is leverage, so the drawdown scales too.** maxDD deepens $1.3–1.6k
  (+8% full-pop / +21% tier). The ratio improvement is modest because the S=5 step
  dilutes the accretive S≥6 step. Effective per-trade risk on tier v2 averages **~$1,223**
  (64×1.0 + 45×1.25 + 47×1.5 over 156) with a **$1,500 peak** — that, not $1k, is the
  size D3 must clear for risk-of-ruin.
- **Cleaner variant worth measuring at D3/F1:** "S≥6 → 1.5x, else 1.0x" captures
  ~$16k of the ~$16–19k with fewer levered losers (skips the weak S=5 tranche), i.e.
  higher return per unit of added drawdown. Not adopted here — task spec is the given
  4/5/6 ladder — but flagged for the go-live sizing decision.

## Recommendation

**Keep `SSCORE_SIZING` default OFF.** The flag is real, correct, and default-safe.
Do not flip it until **D3** re-runs risk-of-ruin on the tier-v2 stats at the larger
effective size ($1.22k avg / $1.5k peak vs the $1k the RoR was last run on), and **F1**
walk-forward confirms the S≥6 win-rate edge holds out-of-sample (the whole uplift rides
on 47 tier / 100 full-pop S≥6 trades — could be regime, not skill). All D2 numbers are
in-sample on one 12mo window: upper bound, not forward expectation.

## Hard-rule compliance

- **Opus signal-path edit, flag-gated, default OFF** — `SSCORE_SIZING`
  (env `OMEN_SSCORE_SIZING`, default `"0"`) + `sscore_mult()` in `backtest_week.py`;
  applied in `SimTrade.pnl` via a local `risk_dollars = RISK_DOLLARS * sscore_mult(reason)`.
  **No existing default moved** (RISK_DOLLARS still 1000, flag OFF ⇒ 1.0x ⇒ byte-identical
  to prior P&L; py_compile clean, flag-off pnl reproduces flat $2,000/−$1,000).
- **Both populations, both arms, maxDD included** — full-pop + tier v2, each with maxDD.
- **0-trade rule** — N/A (no backtest rerun; exact linear scaling over the 671-trade
  frozen baseline, all counts >0). Tier v2 arm A reproduces C10's $81k exactly.
- **No commits** — working tree left for Fable review.

## Reproduce

```
py -3.13 research/d2_sscore_sizing_ab.py        # A/B tables (set PYTHONUTF8=1 on Windows)
OMEN_SSCORE_SIZING=1 py -3.13 -c "..."          # live flag check in backtest_week.SimTrade.pnl
```

Reads `research/c1_off_charts.json`. No network, no backtest rerun, no rate-limit risk.
