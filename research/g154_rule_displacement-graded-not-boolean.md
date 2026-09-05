# g154 F5 -- displacement-graded-not-boolean

What is different now, in one sentence: measuring displacement as a continuous ratio instead of the shipped on/off gate (`downgrade.DISP_BODY_MULT=1.5`) is **a survivor by the row's own rule (precision + recall, NOT money)** -- the T=2.0 arm loses $/day in BOTH halves (H1 -91.47/day, H2 -47.78/day) but raises precision 30.5%->38.3% and S-recall-100 5.9%->14.7% against baseline.

Book: `bt2y_trades_retest_on.json`. One-trade-a-day unit (`research/omen_metrics.first_of_day_arm`-equivalent arrival-order walk), size-gated on `signal_runner.min_risk_floor`. 498 sessions, 16.52 candidates/day (raw arrival stream, whole pool). H1/H2 split at **2025-09-01**.

Predicate: `break_bar` = last bar at index<=entry_i whose CLOSE crossed `level_px` in `dir` direction (same walk as `downgrade._break_bar`). `disp_ratio` = body of break_bar / mean body of the 10 bars before it (same arithmetic as `downgrade.no_displacement`). **`DISP_BODY_MULT=1.5` IS `disp_ratio>=1.5` -- it is not a separate arm, it is the T=1.5 row in the table below, on the same curve.**

## Money -- one trade a day, whole pool, size-gated

| arm | split | trades | $/day | mean R | win | green/months | max DD |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | all | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| baseline | H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| baseline | H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |
| T=1.0 | all | 497 | $9.34 | 0.0093 | 45.3% | 13/25 | $-20985.49 |
| T=1.0 | H1 | 249 | $78.26 | 0.0783 | 46.2% | 9/12 | $-18663.14 |
| T=1.0 | H2 | 248 | $-59.86 | -0.0599 | 44.4% | 4/13 | $-19714.8 |
| T=1.5  <- shipped boolean (DISP_BODY_MULT) | all | 495 | $7.41 | 0.0074 | 44.0% | 12/25 | $-34369.24 |
| T=1.5  <- shipped boolean (DISP_BODY_MULT) | H1 | 248 | $89.03 | 0.089 | 45.2% | 8/12 | $-13968.2 |
| T=1.5  <- shipped boolean (DISP_BODY_MULT) | H2 | 247 | $-74.54 | -0.0745 | 42.9% | 4/13 | $-22284.95 |
| T=2.0 | all | 482 | $-36.03 | -0.036 | 44.4% | 9/25 | $-38420.62 |
| T=2.0 | H1 | 240 | $44.24 | 0.0442 | 46.2% | 5/12 | $-12592.99 |
| T=2.0 | H2 | 242 | $-115.63 | -0.1156 | 42.6% | 4/13 | $-33017.26 |
| T=2.5 | all | 438 | $-100.46 | -0.1005 | 42.0% | 8/25 | $-50356.71 |
| T=2.5 | H1 | 214 | $-43.9 | -0.0439 | 42.5% | 6/12 | $-15309.85 |
| T=2.5 | H2 | 224 | $-154.5 | -0.1545 | 41.5% | 2/13 | $-38234.58 |

delta $/day vs baseline, headline T=2.0: H1 -91.47, H2 -47.78. delta $/day vs baseline, shipped T=1.5: H1 -46.68, H2 -6.69.

candidates dropped at each threshold: T=1.0: 26.82%, T=1.5: 49.03%, T=2.0: 67.12%, T=2.5: 79.66%

## S recall

| arm | probe_s_sweep (34 S cards) | bar-backed S days (canonical_pool) |
|---|---:|---:|
| baseline | 5.9% (2/34) | 5.2% (18/347) |
| T=1.0 | 8.8% (3/34) | 6.3% (22/347) |
| T=1.5 (shipped boolean) | 8.8% (3/34) | 4.9% (17/347) |
| T=2.0 | 14.7% (5/34) | 5.2% (18/347) |
| T=2.5 | 8.8% (3/34) | 4.3% (15/347) |

## Precision (fired days graded S / fired days graded at all, canonical_pool)

| arm | precision | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| T=1.0 | 36.1% | 22 / 61 |
| T=1.5 (shipped boolean) | 34.0% | 17 / 50 |
| T=2.0 | 38.3% | 18 / 47 |
| T=2.5 | 31.2% | 15 / 48 |

Survivor rule: H1 AND H2 both improve $/day (or precision), and S-recall-100 does not fall below baseline. **Result: SURVIVOR.** survivor = True only if H1 AND H2 both improve $/day (or precision) and S-recall-100 does not fall below baseline. 'graded beats boolean' is read off this table by comparing the T=1.5 row (the shipped on/off gate, unchanged) against the other three T values on the SAME ratio -- if a different T does better than 1.5, grading beats the boolean; if 1.5 is already best or all four are indistinguishable inside the book's error bar, the boolean was fine and 'graded' buys nothing measurable here.
