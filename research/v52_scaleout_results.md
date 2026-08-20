# OMEN 5.2 -- T5 scale-out results

Six policies replayed over two corpora. The five fixed policies live in `research/exit_lab.py`; the sixth (`adaptive`) picks `30_30_30_10` when `research/trend_gate.is_trending` is true and `50_20_20_10` otherwise. Per-trade R is dumped to `research/v52_scaleout_results.json`.

## Corpus A -- Austin's 64 marked entries (his entry bar, his stop, machine exits)

Counts N = trades with a realised R for that policy. Mean R annualised = mean_R * trades_per_year, where trades_per_year = N * 252 / distinct_trading_days_in_corpus (the corpus's own trade rate projected onto a 252-day year).

| policy | N | mean R | median R | win rate | worst trade | max consec losers | mean R annualised |
|---|---|---|---|---|---|---|---|
| flat_1r | 63 | 0.6825 | 1.0000 | 0.8413 | -1.0000 | 2 | 264.29 |
| flat_2r | 63 | 1.0317 | 2.0000 | 0.6825 | -1.0000 | 6 | 399.51 |
| hod_only | 63 | 0.9170 | 0.9064 | 0.7619 | -1.0000 | 3 | 355.09 |
| 30_30_30_10 | 63 | 1.1283 | 1.0606 | 0.8889 | -7.0394 | 2 | 436.92 |
| 50_20_20_10 | 63 | 1.0680 | 1.0881 | 0.8571 | -5.3139 | 3 | 413.54 |
| adaptive | 63 | 1.1415 | 1.0606 | 0.8889 | -7.0394 | 2 | 442.03 |


## Corpus B -- the engine's backtest trades (engine entries & stops, machine exits; carries the year)

Counts N = trades with a realised R for that policy. Mean R annualised = mean_R * trades_per_year, where trades_per_year = N * 252 / distinct_trading_days_in_corpus (the corpus's own trade rate projected onto a 252-day year).

| policy | N | mean R | median R | win rate | worst trade | max consec losers | mean R annualised |
|---|---|---|---|---|---|---|---|
| flat_1r | 911 | -0.0603 | -1.0000 | 0.4698 | -1.0000 | 9 | -59.37 |
| flat_2r | 911 | -0.0075 | -1.0000 | 0.3326 | -1.0000 | 13 | -7.43 |
| hod_only | 911 | -0.1302 | -1.0000 | 0.2437 | -2.4923 | 20 | -128.30 |
| 30_30_30_10 | 911 | 0.3850 | 0.3917 | 0.5818 | -12.4635 | 8 | 379.35 |
| 50_20_20_10 | 911 | 0.2378 | 0.0802 | 0.5170 | -9.1882 | 10 | 234.31 |
| adaptive | 911 | 0.2935 | 0.2117 | 0.5423 | -10.8875 | 10 | 289.15 |


```
best_policy: 30_30_30_10
best_policy_mean_r: 0.385015
adaptive_mean_r: 0.293471
baseline_flat_1r_mean_r: -0.060258
```

