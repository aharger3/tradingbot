# T8 -- expectancy per trade, and what carries it

Every number is R at $1,000 risk (`pnl / 1000`). Win rate counts decided trades only; EV counts every trade including scratches.

## Against the previous backtest

| run | window | symbols | trades | win rate | EV/trade |
|---|---|---|---|---|---|
| `backtest_metrics_full.json` (blind 2R, wick stops, pre-pivot, T11 gates inert) | 2024-07-31..2026-07-31 | 24 | 1289 | 38.0% | **+0.144R** |
| **omen-5.0 T8** (close stops, ladder B, pivots, T11 live) | 2024-08-12..2026-08-11 | 29 | 1047 | 55.5% | **+0.914R** |

Delta: **+0.770R per trade**, win rate **+17.5 points**, on -242 trades over near-identical windows.

## Expectancy by bucket

| | trades | win rate | EV/trade | median R | best | worst |
|---|---|---|---|---|---|---|
| all fired | 1430 | 51.3% | **+0.814R** | +0.20R | +15.1R | -1.0R |
| **traded (A+/A/B)** | 1047 | 55.5% | **+0.914R** | +0.46R | +14.7R | -1.0R |
| C alerts (not traded) | 383 | 39.4% | **+0.539R** | -1.00R | +15.1R | -1.0R |
| | | | | | | |
| pool: MAJOR_15 | 605 | 56.6% | **+0.893R** | +0.53R | +14.7R | -1.0R |
| pool: INDEX_POOL | 18 | 55.6% | **+0.093R** | +0.37R | +1.8R | -1.0R |
| pool: OTHER_POOL | 424 | 53.9% | **+0.979R** | +0.29R | +13.9R | -1.0R |
| | | | | | | |
| tier: S+ | 63 | 47.6% | **+0.786R** | -1.00R | +13.9R | -1.0R |
| tier: S | 39 | 57.9% | **+1.099R** | +0.83R | +7.7R | -1.0R |
| tier: A | 15 | 60.0% | **+1.579R** | +2.10R | +6.4R | -1.0R |
| tier: C | 1313 | 51.2% | **+0.798R** | +0.20R | +15.1R | -1.0R |
| | | | | | | |
| setup: break_and_retest | 1272 | 52.7% | **+0.864R** | +0.25R | +15.1R | -1.0R |
| setup: one_candle_rule | 157 | 39.2% | **+0.385R** | -1.00R | +10.4R | -1.0R |
| setup: reentry_84_rule | 1 | 100.0% | **+4.062R** | +4.06R | +4.1R | +4.1R |

## Is it an edge or a tail?

The ladder-B runner has no fixed R ceiling -- it exits at the first key level beyond the scale point, so a trade with a few-cent stop can return tens of R. That makes the mean sensitive to a handful of trades. Three ways of asking whether the expectancy survives without them:

| view | traded EV | MAJOR_15 EV |
|---|---|---|
| as measured | +0.914R | +0.893R |
| R capped at +2 | +0.375R | +0.394R |
| R capped at +5 | +0.797R | +0.789R |
| R capped at +10 | +0.905R | +0.884R |
| top 1% of trades dropped (10 / 6 trades) | +0.821R | +0.801R |
| top 5% of trades dropped (52 / 30 trades) | +0.579R | +0.569R |

- Top **1%** of traded (10 trades) carry **11%** of total R.
- Top **5%** of traded (52 trades) carry **40%** of total R.
- Top **10%** of traded (104 trades) carry **65%** of total R.
- Median traded trade: **+0.46R**. Best: **+14.7R**. Trades over +10R: **5**.

## Biggest winners (traded)

| symbol | day | setup | tier | R |
|---|---|---|---|---|
| PLTR | 2025-12-16 | break_and_retest | C | +14.7R |
| IREN | 2026-05-27 | break_and_retest | S+ | +13.9R |
| HOOD | 2025-11-17 | break_and_retest | C | +10.5R |
| META | 2026-02-05 | one_candle_rule | C | +10.4R |
| HOOD | 2025-07-02 | break_and_retest | C | +10.1R |
| AVGO | 2024-12-23 | break_and_retest | C | +9.8R |
| HOOD | 2024-11-18 | break_and_retest | C | +9.5R |
| SPCX | 2026-08-05 | break_and_retest | C | +9.5R |
| MU | 2025-04-04 | break_and_retest | C | +8.7R |
| PLTR | 2026-08-11 | break_and_retest | C | +8.6R |
