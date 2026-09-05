# g154 F5 -- per-symbol-s-cap

**One sentence: capping how many times one symbol can fire per day (k=2 or k=3) is near-inert on the one-trade-a-day unit -- it trims 1.51/0.56 candidates per day of redundant re-fires but never changes the day's actual pick, because the day's first pick is always rank 1 for its symbol and a cap of k>=2 never removes rank 1.**

Predicate (refusal-indicator): within each (sym, day) group of the fired&traded/halted candidate stream, ordered by et, keep only the first k fired rows; the one-a-day pick skips any row past rank k and falls through to the next surviving candidate that day, across every symbol.

`live_scanner.GOVERNOR_S_CAP` already exists in the live scanner but defaults to `None` and has no `backtest_week` analog -- the committed 2-year book (`bt2y_trades_retest_on.json`) was built with no per-symbol cap in effect at all.

Uncapped candidates/day (fired&traded or halted stream, whole pool): **16.52**.

## k = 2

Candidates/day: uncapped **16.52** -> capped **15.01** (trims **1.51**/day). One-a-day arm picks identical to baseline: **True**. Redundancy: of the 754 rows trimmed, **196** shared level_px with an already-kept row for that symbol-day (26.0%).

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| candidate | k=2 (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| candidate | k=2 H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| candidate | k=2 H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

H1/H2 split at **2025-09-01**. delta $/day: H1 +0.00, H2 +0.00.

| set | n | baseline recall | candidate recall |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 49.0% |

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 30.5% | 18 / 59 |

k=2 survivor: **False**.

## k = 3

Candidates/day: uncapped **16.52** -> capped **15.96** (trims **0.56**/day). One-a-day arm picks identical to baseline: **True**. Redundancy: of the 281 rows trimmed, **93** shared level_px with an already-kept row for that symbol-day (33.1%).

| arm | split | $/day | mean R | win | months green | max DD | fires/day |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| baseline | H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| baseline | H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |
| candidate | k=3 (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| candidate | k=3 H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| candidate | k=3 H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

H1/H2 split at **2025-09-01**. delta $/day: H1 +0.00, H2 +0.00.

| set | n | baseline recall | candidate recall |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 49.0% |

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 30.5% | 18 / 59 |

k=3 survivor: **False**.

## Verdict

Survivor rule: H1 AND H2 both improve $/day or precision, and recall on both S-day panels does not fall below baseline -- required at both k=2 and k=3 for `overall_survivor`. **Result: NOT a survivor.** As predicted going in: this cap is a candidate/day and live-noise reducer, not a money or precision lever on the one-trade-a-day unit -- the unit already only ever asks for the day's rank-1 candidate, which a k>=2 cap can never remove.
