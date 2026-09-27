# R36 walk-forward audit -- g88 POST_floor break-and-retest baseline

Book: `research\tape\g88_post_floor_trades.json.gz` -- 498 trades, 2024-09-03 to 2026-09-02, one per session.

Grid: 5 params, 360 combos (min 60 train trades to qualify).

## Split
- Train (fit window): first 298 trades, 2024-09-03 to 2025-11-07
- Test (unseen, never touched by the fit): last 200 trades, 2025-11-10 to 2026-09-02

## Baseline (no filter, this book)
- Full sample: n=498, win 27.5%, avg R 0.256, $256/day-equiv
- Train slice: n=298, win 24.8%, avg R 0.082, $82/day-equiv
- Test slice:  n=200, win 31.5%, avg R 0.515, $515/day-equiv

## Fitted filter (chosen on TRAIN ONLY, maximizing train avg R)
- Params (5): sgrade_min=ANY, score_min=4, exclude_fri=True, vol_regime=normal_or_wild, aligned=not_against
- Train (in-sample) result: n=68, win 27.9%, avg R 0.546, $546/day-equiv

## Applied unchanged to the unseen test period
- n=58, win 29.3%, avg R 0.521, $521/day-equiv

## Verdict
- Delta vs unfiltered test (same period, same baseline strategy): +0.006R/trade (+6$/day-equiv)
- Delta vs the train fit itself (in-sample -> out-of-sample decay): -0.025R/trade
- HOLDS (weak claim): filter beats no-filter on unseen data with limited in-sample decay -- still n<200 in most cells, not a green light.

## Context vs the ledger's headline number
`07-money/omen/u03-backtest-ledger.md`: g88 POST_floor, full 498-trade sample, $256/day gross / $161/day net of slippage, 27.5% win rate, p=0.074 (not significant), stocks not futures. Nothing here changes that verdict or the paper-trade gate.
