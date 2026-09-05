# g154 -- F5 stop-placement-routed

**What is different now:** recomputed the stop per Austin's structure taxonomy (OCR wick for one_candle_rule, broken level for break_and_retest) from data_archive, size-gated the result, and replayed exits against the one-trade-a-day book.

## baseline (shipped entry_bar stop)

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day: 1.0
S recall (100-card deck, 34 S): 5.9% (2/34)
S recall (all bar-backed S days): 5.2% (18/347)
precision (fired-day graded S / fired-day graded any): 30.5% (18/59)

## candidate (routed stop)

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| overall | 498 | $46.93 | 0.0469 | 35.1% | 12/25 | $-28793.94 |
| H1 | 249 | $145.44 | 0.1454 | 38.2% | 7/12 | $-14986.67 |
| H2 | 249 | $-51.58 | -0.0516 | 32.1% | 5/13 | $-28793.94 |

candidates/day: 16.52 -- fires/day: 1.0
S recall (100-card deck, 34 S): 5.9% (2/34)
S recall (all bar-backed S days): 5.2% (18/347)
precision (fired-day graded S / fired-day graded any): 30.5% (18/59)

## Routed-source counts (all candidates, not just first-of-day)

- broken_level: 7302
- unchanged: 312
- ocr_wick: 613

## stop_disagree = |routed - shipped_stop| / |entry - shipped_stop|

all candidates: n=8227 mean=0.0002 median=0.0
tight-risk only (original risk <= 2.0x min_risk_floor(entry)): n=5295 mean=0.0003 median=0.0

## Survivor verdict

H1 delta $/day: 9.73 -- H2 delta $/day: 16.27
**survivor = True**

survivor = True only if (H1 AND H2 both improve $/day, OR precision improves) AND S-recall-100 does not fall below baseline. `routed_source_counts` shows how many candidates actually got a routed stop vs fell back unchanged (no OCR block found / wrong side of close / reentry_84_rule setup) -- a rule can be real and still rarely trip on this book.
