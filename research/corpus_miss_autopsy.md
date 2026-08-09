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
| no_setup_any | 4423 | 43.1% |
| fired_wrong_bar | 3045 | 29.7% |
| no_reference_level | 2485 | 24.2% |
| no_break_retest | 182 | 1.8% |
| no_order_block | 122 | 1.2% |
| timing_miss | 3 | 0.0% |
| too_few_candles | 1 | 0.0% |
| vetoed_htf | 1 | 0.0% |
| vetoed_candle_colour | 1 | 0.0% |
| consolidation_early_return | 0 | 0.0% |
| not_armed_84 | 0 | 0.0% |
| vetoed_stop_too_tight | 0 | 0.0% |
| vetoed_stop_too_wide | 0 | 0.0% |
| vetoed_pa_grade_D | 0 | 0.0% |
| **total** | **10263** | |

## Reason counts split by channel

| reason | scarface-alerts | jdub-alerts | trading-floor | trade-feedback | futures-alerts | swing-ideas | options-trade-reviews | pre-market-live | backtesting | futures-trade-reviews | scarface-tips | premarket-charts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| detected | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_setup_any | 1606 | 1495 | 1107 | 104 | 54 | 42 | 9 | 3 | 2 | 0 | 0 | 1 |
| fired_wrong_bar | 1329 | 823 | 761 | 66 | 25 | 30 | 3 | 4 | 3 | 0 | 1 | 0 |
| no_reference_level | 950 | 664 | 757 | 50 | 25 | 31 | 1 | 2 | 4 | 1 | 0 | 0 |
| no_break_retest | 65 | 56 | 50 | 7 | 2 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| no_order_block | 46 | 35 | 34 | 5 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| timing_miss | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| too_few_candles | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_htf | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| vetoed_candle_colour | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| consolidation_early_return | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
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
| no_setup_any | 4423 | 43.1% | 29 | 37.7% |
| fired_wrong_bar | 3045 | 29.7% | 6 | 7.8% |
| no_reference_level | 2485 | 24.2% | 7 | 9.1% |
| no_break_retest | 182 | 1.8% | 1 | 1.3% |
| no_order_block | 122 | 1.2% | 0 | 0.0% |
| timing_miss | 3 | 0.0% | 4 | 5.2% |
| too_few_candles | 1 | 0.0% | 0 | 0.0% |
| vetoed_htf | 1 | 0.0% | 10 | 13.0% |
| vetoed_candle_colour | 1 | 0.0% | 2 | 2.6% |
| consolidation_early_return | 0 | 0.0% | 0 | 0.0% |
| not_armed_84 | 0 | 0.0% | 0 | 0.0% |
| vetoed_stop_too_tight | 0 | 0.0% | 8 | 10.4% |
| vetoed_stop_too_wide | 0 | 0.0% | 0 | 0.0% |
| vetoed_pa_grade_D | 0 | 0.0% | 0 | 0.0% |
| **total** | **10263** | | **77** | |

## Agreement

**The same reason tops both: `no_setup_any`** (corpus 4423/10263, S-marks 29/77). Austin's own graded setups and the Discord alerts fail the same way at n=3,595 and n≈77 — the strongest evidence this project has for what to change. T5 should target `no_setup_any`.

## Method

Same as `research/miss_autopsy.md`: the engine's own `detect_signals` replayed bar-by-bar via `research/t4_engine_recall.py`, with `CaptureRunner` recording every built signal's status (fired / skipped_d / skipped_tight) per bar. `detected` = fired entry within +/-2 bars; veto reasons re-run `grade_trade`; no-detection reasons call the engine's real `detect_break_retest` / `detect_order_block_setup`. The 84% rule is not armed in replay, so `not_armed_84` is structurally 0. Bars past the 11:00 entry cutoff are classified by detection state (the engine would not trade them regardless, but the vocabulary has no cutoff label). No code changed.
