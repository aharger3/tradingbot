# Rule Verdict Table — All 25 Candidates

**Spec**: Research/OMEN 9.0 spec.md, row F6 (write-up).

**Data source**: Measured arm performance on 498 sessions (2024-09-03 to 2026-09-02, split H1/H2 at 2025-09-01), one-trade-a-day unit, signal-bar CLOSE entry, stop_rule.stop_fill_price stops, size-gated on signal_runner.min_risk_floor, 1R = $1,000.

**Survivor verdict**: Marked TRUE if arm was claimed to survive F5 gate; marked FALSE otherwise. All 8 survivors carry independent refutation evidence (3–4 refuters per arm) shown below the table.

## Summary Table

| # | Rule | Base $/day | Arm $/day | Δ $/day | H1 Δ | H2 Δ | Prec% | Rec% | Survivor | Refuters |
|---|------|-----------|----------|--------|------|------|-------|------|----------|-----------|
| 1 | displacement-forgiven-unless-exempt | 33.93 | 22.86 | -11.07 | -11.03 | -11.10 | 30.0 | 44.1 | NO | — |
| 2 | entry-earlier-satisfiable-bar | 33.93 | -38.59 | -72.52 | -145.33 | 0.29 | 46.4 | 5.9 | YES | 3× |
| 3 | forming-candle-entry-not-extreme | 33.93 | 33.93 | 0.00 | 0.00 | 0.00 | 30.5 | 5.9 | NO | — |
| 4 | entry-time-of-day-early | 34.00 | 38.00 | 4.00 | 8.00 | 0.00 | 0.3 | 0.3 | NO | — |
| 5 | exhausted-overextended | 33.94 | 35.24 | 1.30 | -36.30 | 38.91 | 0.3 | 0.1 | YES | 3× |
| 6 | brocr-confluence-upgrade-at-fire | 33.94 | 30.83 | -3.11 | -44.65 | 38.43 | 0.3 | 0.1 | NO | — |
| 7 | level-not-respected-refusal | 33.93 | 58.89 | 24.96 | -8.62 | 58.53 | 35.5 | 42.0 | NO | — |
| 8 | stop-placement-routed | 33.93 | 46.93 | 13.00 | 9.73 | 16.27 | 30.5 | 5.9 | YES | 3× |
| 9 | or-break-without-retest | 33.93 | 47.44 | 13.51 | 8.56 | 18.46 | 30.5 | 48.7 | NO | — |
| 10 | ocr-strict-definition | 34.00 | -37.00 | -71.00 | -86.00 | -55.00 | 0.4 | 0.0 | NO | — |
| 11 | be-stop-after-enough-past-pt1 | 47.00 | 65.00 | 18.00 | 19.00 | 18.00 | 0.3 | 0.1 | YES | 3× |
| 12 | same-color-run-confluence | 33.93 | 39.13 | 5.20 | -109.27 | 119.57 | 35.6 | 0.0 | NO | — |
| 13 | per-symbol-s-cap | 33.93 | 33.93 | 0.00 | 0.00 | 0.00 | 30.5 | 44.1 | NO | — |
| 14 | ambiguous-stop-candidates | 33.93 | 29.94 | -3.99 | -4.36 | -3.62 | 31.7 | 5.9 | YES | 3× |
| 15 | displacement-graded-not-boolean | 33.93 | -36.03 | -69.96 | -91.47 | -47.78 | 38.3 | 14.7 | YES | 3× |
| 16 | no-level-to-retest-against | 33.93 | 14.44 | -19.49 | -28.33 | -10.65 | 0.0 | 0.0 | NO | — |
| 17 | round-number-targets | 33.93 | -32.15 | -66.08 | -90.18 | -41.98 | 30.5 | 49.0 | NO | — |
| 18 | scale-before-the-level | 50.00 | 93.00 | 43.00 | 9.40 | 76.50 | 0.3 | 0.1 | YES | 3× |
| 19 | hammer-wick-level-candle | 33.93 | -42.07 | -76.00 | -145.22 | -6.77 | 45.1 | 20.6 | NO | — |
| 20 | trail-stop-to-new-pivot | 143.00 | 98.00 | -45.00 | -68.00 | -24.00 | 30.5 | 5.9 | NO | — |
| 21 | cheap-stock-refusal | 33.93 | 36.95 | 3.02 | 10.60 | -4.57 | 0.0 | 0.0 | NO | — |
| 22 | index-etf-avoid-unless-clear-htf | 33.93 | 33.17 | -0.76 | -1.51 | 0.00 | 31.0 | 47.5 | NO | — |
| 23 | scratch-exit-direction-match | 33.93 | 35.09 | 1.16 | 1.89 | 0.42 | 30.0 | 5.9 | YES | 3× |
| 24 | standalone-ocr-no-br | 33.93 | -124.60 | -158.53 | -202.33 | -114.73 | 20.8 | 4.3 | NO | — |
| 25 | trend-conditional-scale-ladder | 89.00 | 69.00 | -20.00 | -27.00 | -13.00 | 0.3 | 0.1 | NO | — |

---

## Refutation Evidence for the 8 Survivors

Each survivor rule has been independently evaluated by multiple refuters on the grounds of lookahead/leakage, multiplicity, sampling error, and gate validity. All 8 have been marked refuted. The refutation record is below.

### 1. entry-earlier-satisfiable-bar

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): OR-precision loophole; H1 -$145.33, neither half's money improved.

**Refuter #2**: REFUTED (Refuter #2): Multiplicity failure; P(delta>0)=0.073, 100 arm-tests, FWER uncorrected.

**Refuter #3**: REFUTED (Refuter #3): Same verdict; verified clean on lookahead, but H1 delta -145.34 destroys the profitable half, recall rests on 2 cards.

### 2. exhausted-overextended

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Arm 1 (the shipped rule) is a verified no-op, 0/498 days changed; survivor comes from swept-threshold replacement.

**Refuter #2**: REFUTED (Refuter #2): Multiplicity and paired bootstrap P(delta<=0)=0.486; arm converts noise baseline to noise negative.

**Refuter #3**: REFUTED (Refuter #3): H1 delta -$36.30 is a 27% destruction; precision move is one net day; mechanism loses -$19.21/day, gains only from days that drop fires.

### 3. stop-placement-routed

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Routed stop never moves (7,302 of 7,302 break-and-retest have level_px == stop); the $13/day is an exit-model swap.

**Refuter #2**: REFUTED (Refuter #2): Null control routing to ITSELF produces identical $46.93/day; 331 of 498 picks had PnL change on an IDENTICAL stop.

**Refuter #3**: REFUTED (Refuter #3): Precision unchanged (30.5→30.5); recall unchanged (5.9→5.9); identical picked rows both arms prove the stop never moved.

### 4. be-stop-after-enough-past-pt1

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Asymmetric intrabar exemption; armed trades granted TOUCH immunity unarmed trades denied; re-run with BE as resting TOUCH flips H2 negative.

**Refuter #2**: REFUTED (Refuter #2): Multiplicity; P(both halves positive under null)=0.252; fine-grid sweep shows jagged non-monotone surface (k-ladder cliff), not threshold.

**Refuter #3**: REFUTED (Refuter #3): Effect size t=+1.11 on H1, bootstrap 95% CI [-$14, +$49], effect inside error bar; only 46 of 498 picks change.

### 5. ambiguous-stop-candidates

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): The one-card verdict; arm swaps NFLX +$37 for COIN -$1,000 to claim precision gain; placebo test passes gate 64.8%, observed at 50.5th percentile null.

**Refuter #2**: REFUTED (Refuter #2): Sampling error; paired bootstrap $/day CI [-$14.10, +$7.38], positive in 65% of resamples; money NEGATIVE both halves.

**Refuter #3**: REFUTED (Refuter #3): Multiplicity; random 9.19% drop rate produces survivors 47.9% of time; only 6/498 day-picks change, losses WORSE than placebo median.

### 6. displacement-graded-not-boolean

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Survivor test vacuous on money (OR-precision loophole); H1 -$91.47, H2 -$47.78, both halves fail money test.

**Refuter #2**: REFUTED (Refuter #2): Precision gain is numerator-only (18/59→18/47, same S count, 78% day churn); Fisher p=0.42; null baseline clears 49.7% of time.

**Refuter #3**: REFUTED (Refuter #3): Multiplicity and selection bias; T=2.0 is argmax of both criteria post-hoc, 25 rule families tried, expected survivors 12/25 by chance.

### 7. scale-before-the-level

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Seven penny-exact touches, 90.2% of total delta; intrabar-limit framing is the least reliable fill class; H1 +$9.4 is indistinguishable from zero (t=0.37).

**Refuter #2**: REFUTED (Refuter #2): Does not test the rule it is named after; script shifts 2R target, not the level; construct-validity failure.

**Refuter #3**: REFUTED (Refuter #3): Multiplicity; centered-null passes gate 35.4% of time ANY of 3 arms; H1 CI straddles zero; $/day is non-monotone signal of noise.

### 8. scratch-exit-direction-match

**Refuted**: YES — 3 independent refuters

**Refuter #1**: REFUTED (Refuter #1): Only 5 of 498 days change; 81.3% of delta is one swap (MSFT→INTC); remove that single trade and H1 falls to +$0.01/day.

**Refuter #2**: REFUTED (Refuter #2): Paired bootstrap CI [-$1.20, +$3.92]; placebo random drop 61% pass rate; H2 delta below null median.

**Refuter #3**: REFUTED (Refuter #3): Two-day verdict (one is a 09:41 tiebreak); multiplicity null passes 61% of time; precision fell; green months fell 13→12.
