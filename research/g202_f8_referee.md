# g202 -- independent leakage referee for F8 (`research/g157_ml_ceiling.py`)

**One sentence: F8 is clean where it was challenged -- not one feature reads a bar past the entry, no judged day crosses a CV fold, and a 22-feature stronger set still cannot beat a coin flip -- so the 'ML ceiling is at chance' finding is UPHELD; what the report got wrong is smaller: 5 of its 120 labels are days Austin graded twice and differently (2 of them flipping S), and the CV it calls 5-fold is 4-fold.**

## 0. Reproduction

- `python research/g157_ml_ceiling.py` re-run on this box: 120 rows, 28 S -- matches the published 120 rows / 28 S / AUC 0.492 / 0.426 exactly.
- this referee rebuilds the row set independently: identical (symbol,date) set = **True**, identical label vector = **True**.

## 1. Leakage -- is every feature computable at the entry bar?

Test, not inspection: recompute every feature from `bars[:i+1]` -- the bar list physically truncated at the entry bar -- and diff cell-by-cell against the value computed from the whole day. A feature that reads forward MUST differ.

| feature | rows differing under truncation |
|---|---:|
| `no_displacement` | 0 |
| `stale_retest` | 0 |
| `level_not_respected` | 0 |
| `exhausted` | 0 |
| `counter_trend_not_respected` | 0 |
| `break_then_rejection` | 0 |
| `no_retest` | 0 |
| `ocr_not_respected` | 0 |
| `confluence` | 0 |
| `n_tripped` | 0 |
| `net` | 0 |
| `bar` | 0 |
| `displacement` | 0 |
| `x_atr_pct` | 0 |
| `x_dist_level_atr` | 0 |
| `x_dist_level_pct` | 0 |
| `x_bar_rng_atr` | 0 |
| `x_body_frac` | 0 |
| `x_wick_with` | 0 |
| `x_wick_against` | 0 |
| `x_bars_since_break` | 0 |
| `x_break_seen` | 0 |
| `x_bars_since_retest` | 0 |
| `x_retest_seen` | 0 |
| `x_break_to_retest` | 0 |
| `x_ocr_age` | 0 |
| `x_ocr_seen` | 0 |
| `x_ocr_dist_atr` | 0 |
| `x_day_extension_atr` | 0 |
| `x_pos_in_day_range` | 0 |
| `x_day_range_atr` | 0 |
| `x_vol_ratio` | 0 |
| `x_break_body_atr` | 0 |
| `x_risk_atr` | 0 |
| `x_risk_pct` | 0 |

**0 of 35 features differ over 120 rows. No feature reads past the entry bar.**

The four categoricals (`stop_level_name`, `signal_type`, `grade`, `htf_bias`) are not in that table because they come out of the engine replay rather than out of `downgrade.py`. They are causal for a different reason: `research/t66_downgrade_measure.py::replay` sets `r.candles = candles[:i+1]` before every `detect_signals()` call, so the engine physically cannot see bar i+1; and `htf_bias` is close-vs-SMA20 over `names[max(0,i-40):i]` -- **strictly prior archived days, the slice ends before today**. That is the opposite of the `spy_trend` defect the O1 referee found last night, where today's close sat inside its own SMA.

One thing the report mis-describes but which is not a leak: `n_tripped` and `net` include the `chase` downgrade (`ENABLE_CHASE_DOWNGRADE` is ON), so the model sees a ninth variable that has no column of its own. `chase` reads `bars[i]` and the level only.

## 2. CV grouping -- can a card cross folds?

- duplicate (symbol,date) rows: **0**. One row per judged day, so no card can be in train and test at once.
- CV groups (calendar months): **4**. The code runs `n_splits = min(5, n_groups)`, so it is a **4-fold** CV. The report's headings say '5-fold GroupKFold'. Cosmetic, but wrong.

| month | rows | S rows |
|---|---:|---:|
| 2026-05 | 11 | 2 |
| 2026-06 | 25 | 7 |
| 2026-07 | 66 | 15 |
| 2026-08 | 18 | 4 |

| fold | test months | test rows | test S | train rows | train S |
|---:|---|---:|---:|---:|---:|
| 0 | 2026-07 | 66 | 15 | 54 | 13 |
| 1 | 2026-06 | 25 | 7 | 95 | 21 |
| 2 | 2026-08 | 18 | 4 | 102 | 24 |
| 3 | 2026-05 | 11 | 2 | 109 | 26 |

Every month lands in exactly one fold, so **no card leaks across folds**. The fragility is elsewhere: one fold is 2026-07 alone, 55% of the whole row set, and when it is held out the model trains on 54 rows. That is why the pooled out-of-fold AUC needs the null band in section 4 rather than a bare comparison to 0.500.

## 3. Labels -- do the 120 rows and the 28 S come from his marks?

- source of the 120: `research/t60_baseline.load_day_cards()` -> `research/exit_lab.MARKS_FILES` = `research/marks/deck_marks_tsla_2026-08-20.jsonl` + `research/marks/deck_marks_index_2026-08-19.jsonl`. Both are human deck exports (60 TSLA, 30 QQQ, 30 SPY); neither is engine output. Grades read 28 S / 27 A / 3 C / 61 none / 1 blank.
- cross-checked against the canonical cross-corpus view `research/marks_pool.py` (1263 symbol-days, nine grade spellings): **115 agree, 5 disagree, 0 missing**.

| symbol-day | F8 label | marks_pool canonical | all his opinions | corpora |
|---|---|---|---|---:|
| QQQ_2026-07-02 | `none` | `A` | ['A', 'none'] | 2 |
| QQQ_2026-07-21 | `none` | `C` | ['C', 'none'] | 2 |
| QQQ_2026-07-31 | `none` | `S` | ['S', 'none'] | 2 |
| SPY_2026-08-03 | `(blank)` | `none` | ['none'] | 1 |
| TSLA_2026-07-09 | `A` | `S` | ['A', 'S'] | 3 |

**5 of 120 rows are days Austin graded more than once and graded DIFFERENTLY**, in a different session. 2 of them flip the S bit: F8 scores them 0, cross-corpus resolution scores them 1. So the honest positive count on these 120 days is **28 under the two deck files, 30 under `marks_pool`** -- a 7% swing in the positive class.

This is label noise, not a label error: neither reading is wrong, he just answered twice. F8 did not disclose it. It also puts a hard floor under any achievable AUC -- 2 of the ~29 positives are contested by the labeller himself.

## 4. A stronger feature set the F8 agent did not try

22 continuous predicates on top of F8's set, every one verified truncation-identical in section 1: level distance in ATR and in %, bars since the break, bars since the retest, the break->retest gap, OCR age and OCR-edge distance in ATR, entry-bar range / body / with-wick / against-wick geometry, position in the day's range so far, day extension in ATR, volume against the prior 20 bars, break-candle body in ATR, and risk (|entry - level|) in ATR and in %. These are the continuous forms of the g154 rule predicates -- displacement size, staleness, chase distance, exhaustion -- which F8 only saw as the eight booleans.

The null is a label permutation **within month groups**, 200 draws, same pipeline. On 120 rows with 28 positives and 4 folds, chance is not 0.500 with a tight band around it.

| feature set | model | out-of-fold ROC AUC | permutation null mean | null 5th-95th | p |
|---|---|---:|---:|---|---:|
| F8 as shipped | logistic | **0.496** | 0.493 | 0.356 - 0.620 | 0.49 |
| F8 as shipped | grad boost | **0.430** | 0.492 | 0.377 - 0.627 | 0.79 |
| F8 + 22 engineered | logistic | **0.428** | 0.496 | 0.369 - 0.626 | 0.80 |
| F8 + 22 engineered | grad boost | **0.534** | 0.492 | 0.387 - 0.608 | 0.24 |
| engineered only | logistic | **0.355** | 0.492 | 0.377 - 0.609 | 0.97 |
| engineered only | grad boost | **0.526** | 0.498 | 0.389 - 0.614 | 0.34 |

**Best arm anywhere: F8 + 22 engineered / grad boost, AUC 0.534, p = 0.24.** Not one arm clears its own permutation null. Adding 22 engineered predicates moved the logistic arm from 0.496 to 0.428 and the boosted arm from 0.430 to 0.534 -- inside the noise either way, and the engineered set alone is worse than a coin flip.

The 'F8 as shipped' row here reads 0.496 / 0.430 against the published 0.492 / 0.426 because of a third small defect: `g157.build_rows()` computes a `displacement` column -- a feature the spec row explicitly named -- and `g157.make_xy()` then leaves it out of `X`. This referee puts it back. It is worth +0.004 AUC. Mentioned for the record, not because it matters.

### The same, with the two contested days relabelled S (30 positives)

| feature set | model | out-of-fold ROC AUC |
|---|---|---:|
| F8 as shipped | logistic | 0.501 |
| F8 as shipped | grad boost | 0.463 |
| F8 + 22 engineered | logistic | 0.440 |
| F8 + 22 engineered | grad boost | 0.587 |

The label question does not rescue it either.

## Verdict

| check | result |
|---|---|
| every feature computable at the entry bar | **PASS** -- 35 numeric features x 120 rows, 0 differ under truncation; the 4 categoricals are causal by the replay's `candles[:i+1]` slice and a prior-days-only HTF bias |
| CV grouped by month, no card across folds | **PASS** -- 0 duplicate days, 4 disjoint month groups |
| the 120-card set and 28 S labels match his marks | **PARTIAL** -- 115/120 agree with `marks_pool`; 5 are days he graded twice and differently, 2 of which flip S (28 vs 30) |
| a stronger feature set moves AUC | **NO** -- best 0.534, p = 0.24 |

**F8's headline stands and is NOT refuted: on these features, over these 120 judged days, there is no learnable S signal.** It survives 22 extra engineered predicates and survives relabelling the contested days. Three corrections belong in the record and none changes the answer -- the CV is 4-fold, not 5-fold (`min(5, n_groups)` with 4 month groups); 5 of the 120 labels are days he graded twice and differently, 2 of them flipping S; and `displacement`, a feature the spec row named, is computed and then dropped before `X` is built.

**What none of this establishes.** 120 rows, 28 positives, 4 month groups, one of them 55% of the data. The permutation null itself spans 0.36-0.62, so this rig could not detect a modest real edge if one existed. 'These features do not contain the answer' is well supported. 'No features could' is not tested by anything here, and the morning report should not be read as saying it.
