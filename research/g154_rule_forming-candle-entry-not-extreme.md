# g154 -- F5 forming-candle-entry-not-extreme

**What is different now:** built the candidate arm for Austin's rule that a fill sitting at the bar's adverse extreme (a close at the low/high of day) kills R:R, swept at 3 thresholds against the one-trade-a-day book.

## Baseline (no filter)

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0
S recall (100-card deck, 34 S): 5.9% (2/34)
S recall (all bar-backed S days): 5.2% (18/347)
precision (fired-day graded S / fired-day graded any): 30.5% (18/59)

## Arm: DROP extreme_frac <= 0.15

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0 -- candidates dropped: 0.38%
S recall (100-card): 5.9% (2/34) -- baseline 5.9%
S recall (all bar-backed): 5.2% (18/347) -- baseline 5.2%
precision: 30.5% (18/59) -- baseline 30.5%

## Arm: DROP extreme_frac <= 0.25

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0 -- candidates dropped: 0.67%
S recall (100-card): 5.9% (2/34) -- baseline 5.9%
S recall (all bar-backed): 5.2% (18/347) -- baseline 5.2%
precision: 30.5% (18/59) -- baseline 30.5%

## Arm: DROP extreme_frac <= 0.35

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0 -- candidates dropped: 1.28%
S recall (100-card): 5.9% (2/34) -- baseline 5.9%
S recall (all bar-backed): 5.2% (18/347) -- baseline 5.2%
precision: 30.5% (18/59) -- baseline 30.5%

## Survivor verdict (primary arm = 0.25)

H1 delta $/day: 0.0 -- H2 delta $/day: 0.0
**survivor = False**

survivor = True only if H1 AND H2 both improve $/day (or precision) and S-recall-100 does not fall below baseline. Precision is compared overall (not split H1/H2 -- the row asked for $/day split, precision/recall are asked for once). MEASURED, NOT A BUG: at every swept threshold (0.15/0.25/0.35) the extreme_frac filter drops well under 1.3% of all book candidates (median extreme_frac across 8,227 candidates is 0.875 -- most fills already sit near the FAVORABLE extreme, not the adverse one), and it never touches the FIRST candidate of any of the 498 days, so the one-trade-a-day arm is byte-identical to baseline at all three thresholds. The rule is real but the shipped book almost never trips it.
