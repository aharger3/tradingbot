# g154 F5 -- no-level-to-retest-against

No named level to break-and-retest against is tested here as a standalone REFUSAL, distinct from a level being present but chopped through (that is a separate row, `level-not-respected-refusal`). He does NOT refuse for lacking a level to TARGET -- verified below on `QQQ_2025-08-01`, graded S with exactly that complaint on record.

**QQQ_2025-08-01 falsifier check**: found=True, level='PML', level_name='PML', dropped_by_book_proxy=False. Graded **S** (`research/_extract_s_notes.jsonl:225`) with the comment "931 orderblock, looks like a textbook setup just no levels to target unless we know the longer timeframe bias" -- a TARGET complaint, and its book row carries a real named ENTRY level, so the predicate correctly keeps it.

Fired base rate (status=='fired', 10830 rows, NOT the one-a-day unit): no-level book_proxy 8035.

candidates/day (raw arrival stream, whole pool): **16.52**

## Baseline -- one trade a day, whole pool, size-gated

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

## Arm: book_proxy

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $14.44 | +0.015 | 46.3% | 10/25 | $22720 | 0.956 |
| H1 | $107.38 | +0.116 | 50.7% | 9/12 | $10575 | 0.924 |
| H2 | $-78.50 | -0.080 | 42.3% | 1/13 | $22720 | 0.988 |

delta $/day vs baseline: H1 -28.33, H2 -10.65.

| S recall set | n | baseline | book_proxy |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 14.7% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 18.3% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| book_proxy | 33.3% | 17 / 51 |

Arm survivor: **not a survivor**.

## Arm: bars_form

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $-29.12 | -0.029 | 44.5% | 11/25 | $36684 | 0.994 |
| H1 | $73.44 | +0.074 | 48.4% | 7/12 | $18988 | 0.992 |
| H2 | $-131.68 | -0.132 | 40.7% | 4/13 | $36684 | 0.996 |

delta $/day vs baseline: H1 -62.27, H2 -63.83.

| S recall set | n | baseline | bars_form |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 32.4% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 34.5% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| bars_form | 34.0% | 18 / 53 |

Arm survivor: **not a survivor**.

## Verdict

The specced predicate is `book_proxy`, verified to fire on **8035 of 10830** fired rows -- matching the row's own quoted count exactly. `bars_form` is a causal cross-check, not the survivor basis. **Overall survivor = False (basis: book_proxy arm (the row's specced predicate); bars_form is the causal cross-check, reported not averaged in).**
