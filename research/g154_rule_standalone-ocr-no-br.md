# g154 F5 -- standalone-ocr-no-br

**One sentence: not a survivor -- H1 -202/day, H2 -115/day** on the honest, retest-on book, one-trade-a-day unit, size-gated.

Claim: a one-candle-rule (OCR) level with no break-and-retest event on the same symbol-day can still be a full, clean S setup on its own. S-indicator arm: KEEP only OCR candidates (per day, first arrival-order sizeable OCR row). Refusal-indicator arm: SKIP OCR candidates, take the first surviving non-OCR row. n=1 card note: any single-card read below is a sizing exercise, not a rule.

Raw row counts (all 127152 rows, NOT one-a-day): one_candle_rule **6803**, break_and_retest **119806**.

candidates/day (mixed arrival stream, whole pool): **16.52**

## Money -- one trade a day, whole pool, size-gated

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline (mixed) | (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline (mixed) | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline (mixed) | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| S-indicator (OCR-only) | (OCR-only) | $-124.60 | -0.234 | 28.3% | 7/25 | $62404 | 0.532 |
| S-indicator (OCR-only) | H1 | $-66.62 | -0.130 | 32.0% | 5/12 | $24418 | 0.514 |
| S-indicator (OCR-only) | H2 | $-182.58 | -0.332 | 24.8% | 2/13 | $45816 | 0.550 |
| refusal-indicator (skip OCR) | (skip OCR) | $33.19 | +0.033 | 46.3% | 11/25 | $21405 | 1.000 |
| refusal-indicator (skip OCR) | H1 | $134.23 | +0.134 | 49.2% | 7/12 | $12861 | 1.000 |
| refusal-indicator (skip OCR) | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| BR-only stream | stream | $33.19 | +0.033 | 46.3% | 11/25 | $21405 | 1.000 |
| BR-only stream | H1 | $134.23 | +0.134 | 49.2% | 7/12 | $12861 | 1.000 |
| BR-only stream | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

H1/H2 split at **2025-09-01**. delta $/day (S-indicator OCR-only arm vs baseline): H1 -202.33, H2 -114.73.

## OCR stream vs BR stream (the row's own comparison)

| stream | $/day | mean R | win | precision (S rate) |
|---|---:|---:|---:|---:|
| OCR-only (S-indicator) | $-124.60 | -0.234 | 28.3% | 20.8% (11/53) |
| break_and_retest-only | $33.19 | +0.033 | 46.3% | 32.8% (19/58) |

## Is a standalone-OCR detector worth building?

Scan over status=='fired' rows (regardless of traded): **368** symbol-days fired an OCR level; of those, **199** (**54.1%**) fired NO break_and_retest level that same symbol-day. 5225 symbol-days fired a break_and_retest level. A non-trivial share of OCR fires arrive with no accompanying break -- BreakAndRetestDetector and RuleOf84Detector both arm only off a level-break event today, so a standalone-OCR detector is worth scoping.

## S recall

| set | n | baseline | S-indicator (OCR-only) | refusal-indicator (skip OCR) |
|---|---:|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 2.9% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 4.3% | 47.2% |

## Precision (fired days graded S / fired days graded at all)

| arm | precision | S / graded |
|---|---:|---:|
| baseline (mixed) | 30.5% | 18 / 59 |
| S-indicator (OCR-only) | 20.8% | 11 / 53 |
| refusal-indicator (skip OCR) | 32.8% | 19 / 58 |
| BR-only stream | 32.8% | 19 / 58 |

Survivor rule: H1 AND H2 both improve $/day or precision (S-indicator OCR-only arm vs baseline), and recall on both S-day panels does not fall below baseline. **Result: NOT a survivor.**
