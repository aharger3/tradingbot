# g154 -- exhausted-overextended (F5)

One sentence: dropping fired candidates flagged 'exhausted' (as shipped, EXHAUSTED_ATR=10.0) does NOT clearly improve the one-trade-a-day arm, and sweeping the drop threshold over (1.5, 2.0, 2.5, 3.0) ATR on a data_archive-recomputed extension does find a better cutoff either -- so this candidate IS a survivor.

## Arm 1 -- flag-drop, as shipped

| arm | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (first-of-day) | $33.94 | 0.0339 | 0.4639 | 13/25 | -21404.68 | 1.0 | 0.3051 | 0.0588 |
| arm1: drop if exhausted-flagged | $33.94 | 0.0339 | 0.4639 | 13/25 | -21404.68 | 1.0 | 0.3051 | 0.0588 |

H1/H2 delta vs baseline (arm1): $0.0 / $0.0

**Arm 1 is a verified no-op**: the shipped flag (EXHAUSTED_ATR=10.0) never coincides with the day's chosen one-trade-a-day candidate -- 0 of 498 days changed pick. Extension >=10 ATR from the open essentially never happens on a day's FIRST fired candidate (that much displacement takes hours to build), so at the shipped threshold this variable cannot touch first-of-day selection at all, whatever it does downstream in `signal_runner._grade_pa`.

## Arm 2 -- continuous, recomputed extension, threshold sweep

| threshold (ATR) | $/day | mean R | win | green months | max DD | fires/day | precision | recall_100 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.5 | $18.87 | 0.0225 | 0.4197 | 15/25 | -30465.86 | 0.8373 | 0.2642 | 0.0294 |
| 2.0 | $35.24 | 0.0383 | 0.4498 | 13/25 | -22473.17 | 0.9197 | 0.322 | 0.0588 |
| 2.5 | $-11.14 | -0.0114 | 0.4303 | 11/25 | -27943.83 | 0.9799 | 0.386 | 0.0882 |
| 3.0 | $22.8 | 0.0231 | 0.446 | 13/25 | -21994.25 | 0.9859 | 0.4219 | 0.1176 |

best sweep threshold by $/day: **2.0 ATR** -- H1/H2 delta vs baseline: $-36.3 / $38.91

**Caveat on precision**: precision is computed over only 53-64 judged days per arm (14-27 graded S) -- a handful of days moving between arms swings precision several points. The 2.0-3.0 ATR sweep's precision lift over baseline (0.305 -> up to 0.422) is directional, not a diagnosis: it says a lower cutoff than the shipped 10.0 changes which candidate fires some days and those changes skew toward days he graded S, not that any single threshold is settled.

candidates/day flagged exhausted (pre-selection, shipped flag): 2.1406

extension missing bars/ATR (never dropped by threshold): 0 of the candidate stream

survivor = True (arm1 OR best sweep threshold: H1 and H2 both improve $/day or precision, recall_100 not below baseline)
