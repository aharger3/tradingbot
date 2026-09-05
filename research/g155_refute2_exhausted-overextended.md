# g155 refuter #2 -- exhausted-overextended (multiplicity + sampling error)

One sentence: the F5 survivor verdict for 'exhausted-overextended' is a selection artefact -- the shipped rule is a literal no-op (0/498 picks changed), the 'survivor' is a different, newly-invented continuous variable picked as the best of 4 swept thresholds, its $/day gain is $1.30/day inside a paired-bootstrap 95% CI that straddles zero by two orders of magnitude, and the survivor gate that passed it did so on a precision move worth exactly ONE judged day out of 59.

Fill: signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on `omen_metrics._row_is_sizeable`, 1R = $1,000, unit `omen_metrics.first_of_day_arm`, book `bt2y_trades_retest_on.json` (498 sessions). Every arm below is rebuilt from the claim's own module.

## 1. Reproduction

| arm | $/day | H1 $/day | H2 $/day | precision | recall_100 | judged days | S days |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | $33.94 | $135.71 | $-67.84 | 0.3051 | 0.0588 | 59 | 18 |
| arm1_flag_drop | $33.94 | $135.71 | $-67.84 | 0.3051 | 0.0588 | 59 | 18 |
| sweep_1.5 | $18.87 | $87.59 | $-49.86 | 0.2642 | 0.0294 | 53 | 14 |
| sweep_2.0 | $35.24 | $99.41 | $-28.93 | 0.322 | 0.0588 | 59 | 19 |
| sweep_2.5 | $-11.14 | $48.87 | $-71.15 | 0.386 | 0.0882 | 57 | 22 |
| sweep_3.0 | $22.8 | $98.97 | $-53.37 | 0.4219 | 0.1176 | 64 | 27 |

## 2. Paired bootstrap on sessions (20000 resamples, seed 20260905)

Resamples the 498 sessions with replacement; each resample's statistic is the mean paired per-session dollar delta (arm minus baseline), i.e. the $/day delta.

| arm | $/day delta | 95% CI | P(delta <= 0) | paired permutation p |
|---|---:|---:|---:|---:|
| arm1_flag_drop | +0.00 | [+0.00, +0.00] | 1.000 | 1.000 |
| sweep_1.5 | -15.06 | [-129.59, +99.83] | 0.600 | 0.796 |
| sweep_2.0 | +1.31 | [-101.91, +105.41] | 0.489 | 0.979 |
| sweep_2.5 | -45.07 | [-122.23, +31.15] | 0.877 | 0.244 |
| sweep_3.0 | -11.14 | [-79.01, +57.68] | 0.625 | 0.755 |

The headline arm (2.0 ATR) moves **+1.31 $/day** with a 95% CI of **[-101.91, +105.41]** -- the CI is ~158x wider than the point estimate and P(delta <= 0) = **0.489**. That is a coin flip, not an effect.

## 3. Multiplicity

Four thresholds were swept and the winner picked by overall $/day (`best_sweep_label = max(..., key=usd_day)`). The F5 family tried **25 rule candidates** in total. The reported delta is therefore an order statistic, not a sample mean.

Max-over-4-thresholds sign-flip null (session signs shared across arms, so the arms stay as correlated as they really are): observed best = +1.31 $/day, **p_max = 0.761**. Picking the best of 4 is indistinguishable from noise.

Family-wise: 25 candidates at alpha 0.05 expects ~1.2 spurious survivors by chance alone; the Sidak-corrected per-test alpha is 0.0020. The headline arm's UNCORRECTED paired p is 0.979, so it fails even before any correction.

## 4. The survivor gate is self-satisfying

`is_survivor` reads:

```python
h1_ok = (h1d is not None and h1d > 0) or better(arm['precision'], base['precision'])
h2_ok = (h2d is not None and h2d > 0) or better(arm['precision'], base['precision'])
```

Both halves share the SAME disjunct. Any precision improvement, however small, satisfies H1 and H2 at once regardless of money -- so the spec's "H1 and H2 both improve" collapses into a single global test. Proof from this very sweep: **sweep_2.5 loses money in BOTH halves (H1 -86.84, H2 -3.31 $/day vs baseline) and is still scored survivor = True.**

On the headline arm the money test fails outright in H1 (**-36.30 $/day**); the verdict is carried entirely by precision.

## 5. That precision move is one day

baseline: 18/59 judged days graded S (precision 0.3051). sweep_2.0: 19/59 (precision 0.322). The whole survivor verdict is **one judged day** in a 59-day denominator.

Bootstrap of the precision delta over the judged-day universe: **+0.0169 [-0.1066, +0.1426]**, P(delta <= 0) = **0.395**.

recall_100 is 0.0588 for both arms = **2 of 34** S cards in the 100-card sweep. A recall statistic with a numerator of 2 cannot license "no loss of S recall".

## 6. What is actually true

- Arm 1 -- the rule as it exists in the engine (`downgrade.exhausted`, EXHAUSTED_ATR=10.0) -- changed **0 of 498** day picks and is survivor=False. The claim's headline is not about the rule under test.

- Arm 2's variable is clean on lookahead: extension reads `bars[entry_i].close`, `bars[0].open` and ATR14 over `bars[:entry_i+1]` only, nothing past the entry bar. Leakage is NOT the defect here.

- The defect is selection: best-of-4 thresholds inside a 25-candidate family, scored by a gate whose H1/H2 conjunction is satisfiable by one shared precision disjunct, on a $1.31/day move whose 95% CI spans [-102, +105].


## Verdict: REFUTED

Numbers reproduce exactly (re-running the claim script leaves its .md and .json byte-identical). The arithmetic is right; the inference is not.
