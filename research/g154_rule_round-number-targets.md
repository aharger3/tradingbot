# g154 F5 -- round-number-targets

**One sentence: the round-number-target substitution touches 81.06% of the book's 8227 candidate rows (6669 of them), and is not a survivor** on the honest, retest-on book, one-trade-a-day unit, size-gated -- H1 -90/day, H2 -42/day.

Predicate: round_grid = whole dollars, or half dollars when entry < $20. cand = the round_grid price strictly between entry and target, nearest to ENTRY (the first round number price reaches walking from entry toward the original target), in the trade direction. Where cand exists, the target is replaced with cand and the exit is replayed off data_archive bars strictly after the signal bar: disaster stop (touch, -1.0R), level stop (close, stop_rule.stop_fill_price, floored at 1.0R), new target (touch). Rows with no cand, or that cannot be replayed (no data_archive bars / no entry_i), are left untouched.

## Substitution rate (reported before any R figure, per the row spec)

| candidates (fired&traded or halted) | touched | fraction |
|---:|---:|---:|
| 8227 | 6669 | 81.06% |

candidates/day (raw arrival stream, whole pool): **16.52**

## Money -- one trade a day, whole pool, size-gated

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | all | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| candidate | all | $-32.15 | -0.032 | 57.6% | 12/25 | $32802 | 1.000 |
| candidate | H1 | $45.53 | +0.045 | 59.4% | 6/12 | $9607 | 1.000 |
| candidate | H2 | $-109.83 | -0.110 | 55.8% | 6/13 | $32802 | 1.000 |

H1/H2 split at **2025-09-01**. delta $/day (candidate vs baseline): H1 -90.18, H2 -41.98.

## S recall

| set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 49.0% |

## Precision (fired days graded S / fired days graded at all)

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 30.5% | 18 / 59 |

Survivor rule: H1 AND H2 both improve $/day or precision, and recall on both S-day panels does not fall below baseline. **Result: not a survivor.**
