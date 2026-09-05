# g154 F5 -- cheap-stock-refusal

**One card cannot establish a price floor.** The claim that cheap, low-priced stocks are harder to trade and get refused independent of setup quality rests on exactly one outright symbol-day refusal -- `IREN_2025-08-22`, graded X, "just are hard one to trade, cheap stock 20 dollars and a lot of weird things happened here" -- plus two thinner quotes that are NOT symbol-day refusals: a downgrade note on a card still graded A (`t1_ACHR_2026-03-30`), and a general rule-ballot comment. What follows is an effect-size measurement over the book, not a rule to ship.

Predicate, refusal-indicator, two arms: DROP r if r['entry'] < P, for P in {$10, $20}. Measured on the honest retest-on book, one-trade-a-day, size-gated, same construction as `research/g154_rule_level-not-respected-refusal.py`.

Fired base rates (status=='fired', 10830 rows, NOT the one-a-day unit): entry < $10: 217, entry < $20: 539.

candidates/day (raw arrival stream, whole pool): **16.52**

## Baseline -- one trade a day, whole pool, size-gated

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

## Arm: under_$10

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $36.19 | +0.036 | 46.9% | 13/25 | $22634 | 1.000 |
| H1 | $143.74 | +0.144 | 50.0% | 9/12 | $13186 | 1.000 |
| H2 | $-71.36 | -0.071 | 43.8% | 4/13 | $22634 | 1.000 |

delta $/day vs baseline: H1 +8.03, H2 -3.51.

| S recall set | n | baseline | under_$10 |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 49.0% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| under_$10 | 30.5% | 18 / 59 |

Arm survivor: **not a survivor**.

## Arm: under_$20

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $36.95 | +0.037 | 47.5% | 13/25 | $21929 | 1.000 |
| H1 | $146.31 | +0.146 | 49.6% | 9/12 | $12340 | 1.000 |
| H2 | $-72.42 | -0.072 | 45.4% | 4/13 | $21929 | 1.000 |

delta $/day vs baseline: H1 +10.60, H2 -4.57.

| S recall set | n | baseline | under_$20 |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 48.4% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| under_$20 | 30.4% | 17 / 56 |

Arm survivor: **not a survivor**.

## Verdict

One symbol-day refusal cannot establish a price floor. **Overall survivor = False** (both price arms must independently pass H1/H2 $/day-or-precision and recall-not-below-baseline).
