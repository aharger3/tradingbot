# miss_autopsy (omen-3.7 T2)

Why the engine fired NO entry at every marked bar. One classifier, fixed vocabulary (see footer). Detection is the engine's own `SignalRunner.detect_signals` replayed bar-by-bar via `research/t4_engine_recall.py` (a mirror of `backtest_week.simulate_day`).

Classified **159** marks that have bars (of 159; 0 symbol-day pair(s) had no archive). **77** of those are S marks.

## Reason x tier (sorted by S column, descending)

| reason | S | A | X | total |
|---|---:|---:|---:|---:|
| detected | 10 | 6 | 6 | 22 |
| no_setup_any | 29 | 22 | 4 | 55 |
| vetoed_htf | 10 | 12 | 5 | 27 |
| vetoed_stop_too_tight | 8 | 8 | 3 | 19 |
| no_reference_level | 7 | 5 | 2 | 14 |
| fired_wrong_bar | 6 | 4 | 1 | 11 |
| timing_miss | 4 | 2 | 0 | 6 |
| vetoed_candle_colour | 2 | 0 | 1 | 3 |
| no_break_retest | 1 | 1 | 0 | 2 |
| too_few_candles | 0 | 0 | 0 | 0 |
| consolidation_early_return | 0 | 0 | 0 | 0 |
| no_order_block | 0 | 0 | 0 | 0 |
| not_armed_84 | 0 | 0 | 0 | 0 |
| vetoed_stop_too_wide | 0 | 0 | 0 | 0 |
| vetoed_pa_grade_D | 0 | 0 | 0 | 0 |
| **total** | **77** | **60** | **22** | **159** |

`detected` is not a miss (the engine fired within +/-2 bars) but is shown so the vocabulary table is complete.

## Top three S-blindness causes — what would have to change

### no_setup_any (29 S marks)

Neither `detect_break_retest` nor `detect_order_block_setup` found anything on this bar — no reference level completed its geometry AND no order block exists on either side. The fix is new detection vocabulary (swing-pivot / flag-low / FVG reference levels, or a wider order-block search), not a tolerance tweak on either existing test. Would reach ~29 S marks the engine currently sees nothing tradeable on at all.

### vetoed_htf (10 S marks)

`PriceActionAnalyzer.grade_trade` returned D because `htf_bias` opposed the direction (`omen_bot.py:141-144`). The fix is the HTF bias construction or its gating strength. Would recover ~10 S marks vetoed on trend.

### vetoed_stop_too_tight (8 S marks)

A signal was built but the stop was too tight: the B&R path's `stock_risk < max(0.10, 0.0015*close)` (`signal_runner.py:592`), the order block path's `stock_risk < 0.50`, or `_route` dropping a C via `_min_viable_stop` (`signal_runner.py:302`). The fix is the tight-stop thresholds or the stop-placement mode (`BNR_STOP_MODE`). Would recover ~8 S marks the engine saw and then threw away for stop width.

## Method / vocabulary

Reasons (order = order the checks occur inside `detect_signals`):
- `detected`
- `too_few_candles`
- `consolidation_early_return`
- `no_reference_level`
- `no_break_retest`
- `no_order_block`
- `no_setup_any`
- `not_armed_84`
- `vetoed_htf`
- `vetoed_candle_colour`
- `vetoed_stop_too_tight`
- `vetoed_stop_too_wide`
- `vetoed_pa_grade_D`
- `timing_miss`
- `fired_wrong_bar`

Detection vs veto is read from `CaptureRunner`'s per-bar capture (fired / skipped_d / skipped_tight). No-detection sub-reasons call the engine's real helpers (`detect_break_retest`, `detect_order_block_setup`). Veto sub-reasons re-run `PriceActionAnalyzer.grade_trade` with the same levels/lookback `detect_signals` uses. The 84% re-entry rule is not armed in this replay (no stopped prior trade), so `not_armed_84` is structurally 0 — a replay limitation, recorded not pretended away.

No code was changed in this row.
