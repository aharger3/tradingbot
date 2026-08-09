# miss_autopsy (omen-3.7 T2)

Why the engine fired NO entry at every marked bar. One classifier, fixed vocabulary (see footer). Detection is the engine's own `SignalRunner.detect_signals` replayed bar-by-bar via `research/t4_engine_recall.py` (a mirror of `backtest_week.simulate_day`).

Classified **159** marks that have bars (of 159; 0 symbol-day pair(s) had no archive). **77** of those are S marks.

## Reason x tier (sorted by S column, descending)

| reason | S | A | X | total |
|---|---:|---:|---:|---:|
| detected | 10 | 6 | 6 | 22 |
| no_break_retest | 30 | 23 | 4 | 57 |
| vetoed_htf | 10 | 12 | 5 | 27 |
| fired_wrong_bar | 10 | 6 | 1 | 17 |
| vetoed_stop_too_tight | 8 | 8 | 3 | 19 |
| no_reference_level | 7 | 5 | 2 | 14 |
| vetoed_candle_colour | 2 | 0 | 1 | 3 |
| too_few_candles | 0 | 0 | 0 | 0 |
| consolidation_early_return | 0 | 0 | 0 | 0 |
| no_order_block | 0 | 0 | 0 | 0 |
| not_armed_84 | 0 | 0 | 0 | 0 |
| vetoed_stop_too_wide | 0 | 0 | 0 | 0 |
| vetoed_pa_grade_D | 0 | 0 | 0 | 0 |
| **total** | **77** | **60** | **22** | **159** |

`detected` is not a miss (the engine fired within +/-2 bars) but is shown so the vocabulary table is complete.

## Top three S-blindness causes — what would have to change

### no_break_retest (30 S marks)

`detect_break_retest` (`omen_bot.py:403`) returned falsy for every level — its ordered break/leave/retest/confirm geometry did not complete. The fix is that geometry: its 12-bar window, its `max_confirm_gap`, or its requirement that the break close beyond the level by body. Relaxing the window or the confirm gap would reach ~30 S marks where a break happened but the retest/confirm did not line up inside the window.

### vetoed_htf (10 S marks)

`PriceActionAnalyzer.grade_trade` returned D because `htf_bias` opposed the direction (`omen_bot.py:141-144`). The fix is the HTF bias construction or its gating strength. Would recover ~10 S marks vetoed on trend.

### fired_wrong_bar (10 S marks)

The engine DID fire on this symbol-day, but more than 2 bars from the mark — a timing/geometry mismatch, not a blind spot. Reaching these needs the B&R window or confirm-gap widened so the fire lands on the marked bar. Would move ~10 S marks from wrong-bar to detected.

## Method / vocabulary

Reasons (order = order the checks occur inside `detect_signals`):
- `detected`
- `too_few_candles`
- `consolidation_early_return`
- `no_reference_level`
- `no_break_retest`
- `no_order_block`
- `not_armed_84`
- `vetoed_htf`
- `vetoed_candle_colour`
- `vetoed_stop_too_tight`
- `vetoed_stop_too_wide`
- `vetoed_pa_grade_D`
- `fired_wrong_bar`

Detection vs veto is read from `CaptureRunner`'s per-bar capture (fired / skipped_d / skipped_tight). No-detection sub-reasons call the engine's real helpers (`detect_break_retest`, `detect_order_block_setup`). Veto sub-reasons re-run `PriceActionAnalyzer.grade_trade` with the same levels/lookback `detect_signals` uses. The 84% re-entry rule is not armed in this replay (no stopped prior trade), so `not_armed_84` is structurally 0 — a replay limitation, recorded not pretended away.

No code was changed in this row.
