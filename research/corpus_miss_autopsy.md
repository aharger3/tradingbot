# corpus_miss_autopsy (omen-3.7 T2.1)

The same autopsy as `research/miss_autopsy.md` (T2), run over the 10,379-instance `omen-corpus-1.0` Discord-alert corpus, using the SAME classifier and the SAME fixed reason vocabulary — so the counts are directly comparable to T2's mark autopsy.

## Structural difference from T2

Corpus instances are **alerts from Discord**, not Austin's own graded setups, so there is no S/A/X tier. Reasons are reported as a flat distribution, plus a split by `channel` (`scarface-alerts` 4,020, `jdub-alerts` 3,080, remainder per `research/corpus_instances.md`).

## Coverage / classification count

- Total corpus instances: **10379**
- Covered symbol-days (the denominator, per `research/corpus_bar_coverage.md`): **3,595**
- Distinct (symbol, day) pairs with bars replayed here: **3595**
- **Instances classified: 10263** (of 10379; those on the 3595 covered days whose `minute_i` resolves to a bar index).
- Excluded: {'bar_out_of_range': 42, 'no_archive_file': 74} (no archived bars for the day, or minute_i outside the day's RTH bar range — e.g. premarket/after-hours alerts).

`minute_i` is minutes since 09:30, the same frame as the marks' `entry_i`, so the +/-2 bar join and the per-bar classification are identical to T2.

## Reason counts over the whole corpus

| reason | count | % |
|---|---:|---:|
| detected | 0 | 0.0% |
| no_break_retest | 4186 | 40.8% |
| fired_wrong_bar | 3016 | 29.4% |
| no_reference_level | 2454 | 23.9% |
| consolidation_early_return | 495 | 4.8% |
| no_order_block | 109 | 1.1% |
| too_few_candles | 1 | 0.0% |
| vetoed_htf | 1 | 0.0% |
| vetoed_candle_colour | 1 | 0.0% |
| not_armed_84 | 0 | 0.0% |
| vetoed_stop_too_tight | 0 | 0.0% |
| vetoed_stop_too_wide | 0 | 0.0% |
| vetoed_pa_grade_D | 0 | 0.0% |
| **total** | **10263** | |

## Reason counts split by channel

| reason | scarface-alerts | jdub-alerts | trading-floor | trade-feedback | futures-alerts | swing-ideas | options-trade-reviews | pre-market-live | backtesting | futures-trade-reviews | scarface-tips | premarket-charts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| detected | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_break_retest | 1499 | 1414 | 1060 | 102 | 56 | 42 | 7 | 3 | 2 | 0 | 0 | 1 |
| fired_wrong_bar | 1306 | 816 | 761 | 67 | 25 | 30 | 3 | 4 | 3 | 0 | 1 | 0 |
| no_reference_level | 933 | 659 | 749 | 49 | 25 | 31 | 1 | 2 | 4 | 1 | 0 | 0 |
| consolidation_early_return | 218 | 153 | 110 | 10 | 0 | 1 | 2 | 1 | 0 | 0 | 0 | 0 |
| no_order_block | 40 | 31 | 31 | 5 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| too_few_candles | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_htf | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_candle_colour | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| not_armed_84 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_stop_too_tight | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_stop_too_wide | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_pa_grade_D | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **total** | 3996 | 3073 | 2713 | 234 | 106 | 105 | 13 | 11 | 9 | 1 | 1 | 1 |

## Side-by-side: corpus vs T2's S-mark reason distribution

Corpus (n=10263 classified instances) against the S column of `research/miss_autopsy.md` (n=77 S marks with bars). Same vocabulary, same classifier.

| reason | corpus count | corpus % | S-mark count | S-mark % |
|---|---:|---:|---:|---:|
| detected | 0 | 0.0% | 10 | 13.0% |
| no_break_retest | 4186 | 40.8% | 27 | 35.1% |
| fired_wrong_bar | 3016 | 29.4% | 10 | 13.0% |
| no_reference_level | 2454 | 23.9% | 7 | 9.1% |
| consolidation_early_return | 495 | 4.8% | 4 | 5.2% |
| no_order_block | 109 | 1.1% | 0 | 0.0% |
| too_few_candles | 1 | 0.0% | 0 | 0.0% |
| vetoed_htf | 1 | 0.0% | 10 | 13.0% |
| vetoed_candle_colour | 1 | 0.0% | 2 | 2.6% |
| not_armed_84 | 0 | 0.0% | 0 | 0.0% |
| vetoed_stop_too_tight | 0 | 0.0% | 7 | 9.1% |
| vetoed_stop_too_wide | 0 | 0.0% | 0 | 0.0% |
| vetoed_pa_grade_D | 0 | 0.0% | 0 | 0.0% |
| **total** | **10263** | | **77** | |

## Agreement

**The same reason tops both: `no_break_retest`** (corpus 4186/10263, S-marks 27/77). Austin's own graded setups and the Discord alerts fail the same way at n=3,595 and n≈77 — the strongest evidence this project has for what to change. T5 should target `no_break_retest`.

## Method

Same as `research/miss_autopsy.md`: the engine's own `detect_signals` replayed bar-by-bar via `research/t4_engine_recall.py`, with `CaptureRunner` recording every built signal's status (fired / skipped_d / skipped_tight) per bar. `detected` = fired entry within +/-2 bars; veto reasons re-run `grade_trade`; no-detection reasons call the engine's real `detect_break_retest` / `detect_order_block_setup` / `_is_consolidation`. The 84% rule is not armed in replay, so `not_armed_84` is structurally 0. Bars past the 11:00 entry cutoff are classified by detection state (the engine would not trade them regardless, but the vocabulary has no cutoff label). No engine or detection code changed — the classifier (`classify_bar` / `day_state` / the fixed `REASONS` vocabulary) is byte-identical to T2's; the only edits to `research/miss_autopsy.py` are (a) parallelizing the per-day replay across cores so the 3,595-day corpus finishes in minutes instead of the 25-min single-process timeout that voided the first attempt, and (b) escaping literal `%` in T2's prose paragraphs so `miss_autopsy.md` renders. Neither alters any bar's reason.
