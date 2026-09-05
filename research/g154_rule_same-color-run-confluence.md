# g154 -- F5 same-color-run-confluence

**What is different now:** measured Austin's rule that a run of 2-3 same-coloured candles into the entry reads as strength -- against the one-trade-a-day book, in three SEPARATE buckets (no summed score), because one of his own cards (NVDA_2026-06-25) says the opposite for two green candles at the open.

## Bucket profile -- every candidate in the book, no filtering

| bucket | n | share | mean R | S rate | graded S/any |
|---|---:|---:|---:|---:|---:|
| isolated (run_len 0-1) | 4709 | 57.2% | -0.032 | 30.9% | 171/553 |
| short_run (run_len 2-3) | 3063 | 37.2% | -0.0209 | 29.1% | 104/357 |
| long_run (run_len >=4) | 455 | 5.5% | -0.001 | 32.3% | 20/62 |

unreadable run_len (entry_i missing/bar unavailable): 0 of 8227 total candidates

## Baseline (no filter, one-trade-a-day arm)

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0
S recall (100-card deck, 34 S): 5.9% (2/34)
S recall (all bar-backed S days): 5.2% (18/347)
precision (fired-day graded S / fired-day graded any): 30.5% (18/59)

## Candidate arm: keep only short_run (run_len in {2,3})

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 486 | $39.13 | 0.0391 | 47.6% | 14/25 | $-17592.74 |
| H1 | 242 | $26.44 | 0.0264 | 46.9% | 5/12 | $-16512.78 |
| H2 | 244 | $51.72 | 0.0517 | 48.4% | 9/13 | $-17592.74 |

candidates/day: 16.52 -- fires/day: 0.976 -- candidates dropped: 62.77%
S recall (100-card): 0.0% (0/34) -- baseline 5.9%
S recall (all bar-backed): 6.1% (21/347) -- baseline 5.2%
precision: 35.6% (21/59) -- baseline 30.5%

## Survivor verdict

H1 delta $/day: -109.27 -- H2 delta $/day: 119.57
**survivor = False**

Three buckets reported separately (isolated / short_run / long_run), never summed into a score -- see 'buckets' above for S rate and mean R per bucket. The candidate arm tests only the spec's stated default reading: keep the day's first candidate only if it falls in short_run (run_len 2-3), i.e. the 'additive to displacement' hypothesis, else fall through to the next candidate that day (same pick-then-gate logic as omen_metrics.first_of_day_arm). survivor = True only if H1 AND H2 both improve $/day (or precision improves) and S-recall-100 does not fall below baseline. The isolated-candle counter-reading from NVDA_2026-06-25 is NOT separately armed here -- one card is a hint, not a rule, per the no-oversell instruction -- but the bucket table lets that counter-reading be checked against the whole book's S rate and realized R.
