# OMEN 5.2 -- T5 scale-out results

Six policies replayed over two corpora. The five fixed policies live in `research/exit_lab.py`; the sixth (`adaptive`) picks `30_30_30_10` when `research/trend_gate.is_trending` is true and `50_20_20_10` otherwise. Per-trade R is dumped to `research/v52_scaleout_results.json`.

## Corpus A -- Austin's 64 marked entries (his entry bar, his stop, machine exits)

Counts N = trades with a realised R for that policy. Mean R annualised = mean_R * trades_per_year, where trades_per_year = N * 252 / distinct_trading_days_in_corpus (the corpus's own trade rate projected onto a 252-day year).

| policy | N | mean R | median R | win rate | worst trade | max consec losers | mean R annualised |
|---|---|---|---|---|---|---|---|
| flat_1r | 63 | 0.6825 | 1.0000 | 0.8413 | -1.0000 | 2 | 264.29 |
| flat_2r | 63 | 1.0317 | 2.0000 | 0.6825 | -1.0000 | 6 | 399.51 |
| hod_only | 63 | 0.9170 | 0.9064 | 0.7619 | -1.0000 | 3 | 355.09 |
| 30_30_30_10 | 63 | 1.3238 | 1.0507 | 0.8413 | -0.3000 | 2 | 512.60 |
| 50_20_20_10 | 63 | 1.2065 | 1.0881 | 0.8095 | -0.5000 | 2 | 467.18 |
| adaptive | 63 | 1.3087 | 1.0507 | 0.8413 | -0.3000 | 2 | 506.77 |


## Corpus B -- the engine's backtest trades (engine entries & stops, machine exits; carries the year)

Counts N = trades with a realised R for that policy. Mean R annualised = mean_R * trades_per_year, where trades_per_year = N * 252 / distinct_trading_days_in_corpus (the corpus's own trade rate projected onto a 252-day year).

| policy | N | mean R | median R | win rate | worst trade | max consec losers | mean R annualised |
|---|---|---|---|---|---|---|---|
| flat_1r | 911 | -0.0805 | -1.0000 | 0.4599 | -1.0000 | 9 | -79.32 |
| flat_2r | 911 | -0.0248 | -1.0000 | 0.3260 | -1.0000 | 13 | -24.41 |
| hod_only | 911 | -0.1636 | -1.0000 | 0.2327 | -2.4923 | 20 | -161.17 |
| 30_30_30_10 | 911 | 1.5148 | 0.6644 | 0.6476 | -0.3000 | 6 | 1492.52 |
| 50_20_20_10 | 911 | 1.0361 | 0.2708 | 0.5862 | -0.5000 | 6 | 1020.85 |
| adaptive | 911 | 1.1644 | 0.4910 | 0.6235 | -0.5000 | 6 | 1147.31 |


```
best_policy: 30_30_30_10
best_policy_mean_r: 1.514805
adaptive_mean_r: 1.164444
baseline_flat_1r_mean_r: -0.080504
```

