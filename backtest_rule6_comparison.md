# Rule 6 Comparison Report

Generated: 2026-07-11

## Summary

| Metric | Baseline (no BE) | Rule 6 (50% BE scale) | Delta |
|--------|-----------------|----------------------|-------|
| Trades | 12 | 12 | +0 |
| Win Rate | 0.0% | 0.0% | +0.0% |
| P&L | $2639.24 | $1000.00 | $-1639.24 |

## Interpretation

Rule 6 reduced P&L by $1639.24 - breakeven scaling may cost too many runners that would have hit 2R anyway.

Rule 6 mechanics:
- Scale 50% of position at breakeven (entry + 1R for calls, entry - 1R for puts)
- Move runner stop to entry (breakeven)
- Runner continues to original 2R target
- P&L on BE-scale trades: 0.5 x 1R + 0.5 x outcome (2R = 1.5R, stop = 0.5R)

The key trade-off: locking partial profit reduces max win ($2000 -> $1500)
but eliminates the full loss on trades that did touch breakeven first. Whether
this helps depends on how often price reaches 1R without ever touching 2R.

## Baseline Report

# Backtest Report: Week of 2026-07-06 to 2026-07-10

## Assumptions
- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals
- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close
- Stop+target same bar counted as loss (conservative)
- Repeat fires of same setup within 30 min deduped

## Summary
- Traded signals (A+/A/B, viable stop): **12** | 5W 7L 0 scratch | win rate 41.7% (of decided)
- Simulated P&L (traded all A+/A/B): **+$2639.24**
- C-grade alerts (alert-only per SPEC2): 3 | D filtered: 125 | tight-stop skips: 1

### By Grade
| Grade | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| A | 4 | 2 | 2 | 0 | 50.0% | $1639.24 |
| B | 8 | 3 | 5 | 0 | 37.5% | $1000.0 |
| C (alert only) | 3 | 1 | 2 | 0 | 33.3% | ($0.0 if traded) |
| D (filtered) | 125 | 42 | 83 | 0 | 33.6% | ($1000.0 if traded) |

### By Setup
| Setup | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| break_and_retest | 10 | 4 | 6 | 0 | 40.0% | $2000.0 |
| reentry_84_rule | 2 | 1 | 1 | 0 | 50.0% | $639.24 |

### By Symbol
| Symbol | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| AAPL | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| AMD | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| AMZN | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| INTC | 1 | 1 | 0 | 0 | 100.0% | $2000.0 |
| MSFT | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| NVDA | 4 | 2 | 2 | 0 | 50.0% | $2000.0 |
| ORCL | 1 | 1 | 0 | 0 | 100.0% | $2000.0 |
| TSLA | 2 | 1 | 1 | 0 | 50.0% | $639.24 |

### B&R: clean first break vs late (level broken earlier)
| Bucket | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| clean | 4 | 2 | 2 | 0 | 50.0% | $2000.0 |
| late | 6 | 2 | 4 | 0 | 33.3% | $0.0 |

## By Day
| Day | Signals | Wins | Losses | Scratch | P&L |
|-----|---------|------|--------|---------|-----|
| 2026-07-06 | 2 | 1 | 1 | 0 | $1000.0 |
| 2026-07-07 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-08 | 7 | 3 | 4 | 0 | $1639.24 |
| 2026-07-09 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-10 | 3 | 1 | 2 | 0 | $0.0 |

## 84% Rule Analysis
- Total triggers (incl. filtered): 3
- Fired re-entry signals: 2
- Win rate on re-entry: 50.0% | P&L $639.24

## Signal Log
| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |
|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|
| 2026-07-06 | 09:35:00 | QQQ | one_candle_rule | call | D | skipped_d | 721.43 | 720.16 | loss | - |
| 2026-07-06 | 09:36:00 | SOFI | break_and_retest | call | D | skipped_d | 18.52 | 18.46 | win | - |
| 2026-07-06 | 09:38:00 | AMD | break_and_retest | call | D | skipped_d | 542.94 | 540.00 | win | - |
| 2026-07-06 | 09:41:00 | ORCL | break_and_retest | put | B | fired | 142.71 | 143.08 | win | $2000 |
| 2026-07-06 | 09:41:00 | COIN | break_and_retest | put | D | skipped_d | 162.99 | 163.22 | win | - |
| 2026-07-06 | 09:42:00 | AAPL | break_and_retest | call | D | skipped_d | 308.74 | 308.63 | loss | - |
| 2026-07-06 | 09:42:00 | SPY | break_and_retest | put | D | skipped_d | 748.00 | 748.12 | loss | - |
| 2026-07-06 | 09:42:00 | ORCL | break_and_retest | put | C | skipped_tight_stop | 142.08 | 142.61 | loss | - |
| 2026-07-06 | 09:43:00 | IREN | break_and_retest | call | D | skipped_d | 43.62 | 43.42 | loss | - |
| 2026-07-06 | 09:46:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.60 | 360.44 | win | - |
| 2026-07-06 | 09:48:00 | NVDA | break_and_retest | call | D | skipped_d | 194.98 | 194.88 | win | - |
| 2026-07-06 | 09:48:00 | INTC | break_and_retest | call | D | skipped_d | 125.32 | 125.08 | win | - |
| 2026-07-06 | 09:48:00 | INTC | break_and_retest | call | D | skipped_d | 125.32 | 125.01 | win | - |
| 2026-07-06 | 09:53:00 | SPY | break_and_retest | call | D | skipped_d | 748.90 | 748.88 | loss | - |
| 2026-07-06 | 09:53:00 | QQQ | break_and_retest | call | D | skipped_d | 723.14 | 722.27 | loss | - |
| 2026-07-06 | 09:53:00 | QQQ | break_and_retest | call | D | skipped_d | 723.14 | 722.38 | loss | - |
| 2026-07-06 | 09:54:00 | TSLA | break_and_retest | call | D | skipped_d | 401.36 | 400.66 | win | - |
| 2026-07-06 | 09:54:00 | SPY | one_candle_rule | put | C | fired | 748.88 | 749.54 | loss | - |
| 2026-07-06 | 10:00:00 | HOOD | one_candle_rule | call | D | skipped_d | 114.44 | 113.77 | win | - |
| 2026-07-06 | 10:06:00 | SMCI | break_and_retest | put | D | skipped_d | 27.24 | 27.26 | win | - |
| 2026-07-06 | 10:12:00 | AAPL | break_and_retest | call | D | skipped_d | 309.46 | 309.42 | loss | - |
| 2026-07-06 | 10:12:00 | AAPL | one_candle_rule | put | D | skipped_d | 309.46 | 309.73 | loss | - |
| 2026-07-06 | 10:19:00 | ORCL | one_candle_rule | call | D | skipped_d | 142.39 | 141.51 | loss | - |
| 2026-07-06 | 10:23:00 | NVDA | one_candle_rule | put | D | skipped_d | 196.23 | 196.39 | loss | - |
| 2026-07-06 | 10:24:00 | COIN | break_and_retest | put | D | skipped_d | 163.01 | 163.22 | loss | - |
| 2026-07-06 | 10:26:00 | ORCL | break_and_retest | put | D | skipped_d | 142.46 | 142.61 | loss | - |
| 2026-07-06 | 10:38:00 | MSFT | break_and_retest | put | D | skipped_d | 383.17 | 383.70 | loss | - |
| 2026-07-06 | 10:50:00 | AMZN | break_and_retest | put | B | fired | 242.82 | 243.20 | loss | $-1000 |
| 2026-07-06 | 10:50:00 | AMZN | break_and_retest | put | D | skipped_d | 242.82 | 243.01 | loss | - |
| 2026-07-06 | 10:52:00 | PLTR | break_and_retest | call | D | skipped_d | 130.54 | 130.48 | loss | - |
| 2026-07-06 | 10:55:00 | SOFI | one_candle_rule | call | D | skipped_d | 18.57 | 18.51 | win | - |
| 2026-07-06 | 10:59:00 | INTC | one_candle_rule | put | D | skipped_d | 126.20 | 126.52 | loss | - |
| 2026-07-07 | 09:38:00 | AMD | break_and_retest | put | D | skipped_d | 511.02 | 515.80 | loss | - |
| 2026-07-07 | 09:39:00 | SMCI | break_and_retest | put | D | skipped_d | 26.54 | 26.55 | loss | - |
| 2026-07-07 | 09:44:00 | SOFI | break_and_retest | put | D | skipped_d | 18.43 | 18.45 | loss | - |
| 2026-07-07 | 09:47:00 | PLTR | break_and_retest | call | D | skipped_d | 134.07 | 134.07 | loss | - |
| 2026-07-07 | 09:48:00 | QQQ | break_and_retest | put | D | skipped_d | 712.89 | 713.46 | win | - |
| 2026-07-07 | 09:59:00 | HOOD | break_and_retest | put | D | skipped_d | 115.07 | 115.10 | loss | - |
| 2026-07-07 | 10:03:00 | SOFI | one_candle_rule | put | D | skipped_d | 18.12 | 18.21 | win | - |
| 2026-07-07 | 10:05:00 | AMZN | one_candle_rule | put | D | skipped_d | 246.74 | 247.95 | win | - |
| 2026-07-07 | 10:06:00 | TSLA | break_and_retest | put | D | skipped_d | 414.48 | 414.54 | loss | - |
| 2026-07-07 | 10:06:00 | INTC | break_and_retest | put | D | skipped_d | 111.95 | 112.02 | win | - |
| 2026-07-07 | 10:06:00 | SMCI | one_candle_rule | put | D | skipped_d | 26.14 | 26.21 | win | - |
| 2026-07-07 | 10:12:00 | MSFT | one_candle_rule | call | D | skipped_d | 392.55 | 391.52 | win | - |
| 2026-07-07 | 10:15:00 | AMZN | one_candle_rule | call | D | skipped_d | 247.02 | 246.53 | loss | - |
| 2026-07-07 | 10:17:00 | AMZN | break_and_retest | call | D | skipped_d | 246.18 | 246.04 | win | - |
| 2026-07-07 | 10:21:00 | META | break_and_retest | call | D | skipped_d | 612.34 | 612.18 | loss | - |
| 2026-07-07 | 10:21:00 | HOOD | break_and_retest | put | D | skipped_d | 113.91 | 114.11 | loss | - |
| 2026-07-07 | 10:22:00 | HOOD | one_candle_rule | put | D | skipped_d | 113.96 | 114.57 | loss | - |
| 2026-07-07 | 10:30:00 | GOOGL | break_and_retest | call | D | skipped_d | 370.73 | 370.50 | loss | - |
| 2026-07-07 | 10:31:00 | PLTR | one_candle_rule | put | D | skipped_d | 133.38 | 134.20 | loss | - |
| 2026-07-07 | 10:35:00 | SMCI | one_candle_rule | call | D | skipped_d | 25.52 | 25.45 | loss | - |
| 2026-07-07 | 10:57:00 | AAPL | break_and_retest | put | D | skipped_d | 312.70 | 312.80 | loss | - |
| 2026-07-08 | 09:40:00 | PLTR | break_and_retest | put | D | skipped_d | 128.47 | 128.53 | loss | - |
| 2026-07-08 | 09:42:00 | ORCL | break_and_retest | call | D | skipped_d | 140.56 | 140.50 | win | - |
| 2026-07-08 | 09:42:00 | ORCL | one_candle_rule | call | D | skipped_d | 140.56 | 139.20 | loss | - |
| 2026-07-08 | 09:43:00 | NVDA | break_and_retest | call | B | fired | 198.04 | 197.45 | win | $2000 |
| 2026-07-08 | 09:43:00 | SOFI | break_and_retest | call | D | skipped_d | 17.53 | 17.50 | loss | - |
| 2026-07-08 | 09:44:00 | SPY | break_and_retest | call | D | skipped_d | 744.34 | 744.09 | win | - |
| 2026-07-08 | 09:45:00 | HOOD | break_and_retest | call | D | skipped_d | 112.61 | 111.81 | loss | - |
| 2026-07-08 | 09:47:00 | NVDA | break_and_retest | call | D | skipped_d | 198.41 | 198.41 | win | - |
| 2026-07-08 | 09:49:00 | AAPL | break_and_retest | put | D | skipped_d | 308.52 | 308.68 | loss | - |
| 2026-07-08 | 09:50:00 | META | break_and_retest | put | D | skipped_d | 603.40 | 603.66 | loss | - |
| 2026-07-08 | 09:50:00 | QQQ | break_and_retest | call | D | skipped_d | 707.96 | 707.92 | loss | - |
| 2026-07-08 | 09:51:00 | AMD | one_candle_rule | put | D | skipped_d | 517.61 | 521.98 | win | - |
| 2026-07-08 | 09:51:00 | SPY | one_candle_rule | put | C | fired | 743.81 | 744.92 | win | - |
| 2026-07-08 | 09:51:00 | QQQ | one_candle_rule | put | D | skipped_d | 708.22 | 709.71 | win | - |
| 2026-07-08 | 09:59:00 | TSLA | break_and_retest | put | D | skipped_d | 395.88 | 395.99 | win | - |
| 2026-07-08 | 10:00:00 | TSLA | break_and_retest | put | B | fired | 394.96 | 395.66 | loss | $-1000 |
| 2026-07-08 | 10:03:00 | PLTR | one_candle_rule | call | D | skipped_d | 128.02 | 127.45 | win | - |
| 2026-07-08 | 10:11:00 | IREN | one_candle_rule | call | D | skipped_d | 42.04 | 41.85 | loss | - |
| 2026-07-08 | 10:17:00 | META | break_and_retest | put | D | skipped_d | 604.39 | 604.40 | loss | - |
| 2026-07-08 | 10:18:00 | AMZN | break_and_retest | put | D | skipped_d | 242.69 | 242.70 | loss | - |
| 2026-07-08 | 10:25:00 | QQQ | break_and_retest | call | D | skipped_d | 708.39 | 707.92 | loss | - |
| 2026-07-08 | 10:25:00 | IREN | break_and_retest | call | D | skipped_d | 42.27 | 42.12 | loss | - |
| 2026-07-08 | 10:27:00 | AMD | one_candle_rule | call | D | skipped_d | 516.31 | 513.62 | loss | - |
| 2026-07-08 | 10:27:00 | PLTR | break_and_retest | put | D | skipped_d | 128.35 | 128.53 | loss | - |
| 2026-07-08 | 10:28:00 | AAPL | break_and_retest | put | B | fired | 309.08 | 310.15 | loss | $-1000 |
| 2026-07-08 | 10:32:00 | TSLA | reentry_84_rule | put | A | fired | 394.87 | 395.66 | win | $1639 |
| 2026-07-08 | 10:38:00 | INTC | break_and_retest | put | B | fired | 107.57 | 108.00 | win | $2000 |
| 2026-07-08 | 10:42:00 | SPY | break_and_retest | put | D | skipped_d | 742.29 | 742.64 | win | - |
| 2026-07-08 | 10:51:00 | SPY | one_candle_rule | put | D | skipped_d | 741.58 | 741.93 | loss | - |
| 2026-07-08 | 10:51:00 | QQQ | break_and_retest | put | D | skipped_d | 704.87 | 704.94 | loss | - |
| 2026-07-08 | 10:51:00 | QQQ | break_and_retest | put | D | skipped_d | 704.87 | 704.90 | loss | - |
| 2026-07-08 | 10:51:00 | SOFI | one_candle_rule | put | D | skipped_d | 17.21 | 17.26 | loss | - |
| 2026-07-08 | 10:52:00 | SMCI | break_and_retest | call | D | skipped_d | 26.87 | 26.83 | loss | - |
| 2026-07-08 | 10:53:00 | COIN | break_and_retest | put | D | skipped_d | 158.10 | 158.15 | loss | - |
| 2026-07-08 | 10:56:00 | AMZN | one_candle_rule | put | D | skipped_d | 241.82 | 242.20 | win | - |
| 2026-07-08 | 10:57:00 | NVDA | break_and_retest | call | A | fired | 198.75 | 197.93 | loss | $-1000 |
| 2026-07-08 | 10:59:00 | NVDA | reentry_84_rule | call | A | fired | 198.78 | 197.93 | loss | $-1000 |
| 2026-07-08 | 10:59:00 | AAPL | reentry_84_rule | put | C | fired | 308.88 | 310.15 | loss | - |
| 2026-07-09 | 09:38:00 | GOOGL | break_and_retest | call | D | skipped_d | 358.22 | 358.10 | loss | - |
| 2026-07-09 | 09:40:00 | MSFT | break_and_retest | call | D | skipped_d | 376.46 | 375.95 | win | - |
| 2026-07-09 | 09:40:00 | SPY | break_and_retest | call | D | skipped_d | 747.54 | 747.50 | win | - |
| 2026-07-09 | 09:43:00 | AAPL | break_and_retest | call | D | skipped_d | 311.10 | 311.00 | loss | - |
| 2026-07-09 | 09:43:00 | IREN | break_and_retest | put | D | skipped_d | 43.92 | 44.02 | loss | - |
| 2026-07-09 | 09:44:00 | MSFT | one_candle_rule | call | D | skipped_d | 378.33 | 377.01 | loss | - |
| 2026-07-09 | 09:47:00 | AAPL | one_candle_rule | put | D | skipped_d | 311.30 | 311.92 | loss | - |
| 2026-07-09 | 09:51:00 | AMD | break_and_retest | call | D | skipped_d | 551.78 | 548.95 | win | - |
| 2026-07-09 | 09:51:00 | SPY | break_and_retest | call | D | skipped_d | 748.57 | 748.43 | win | - |
| 2026-07-09 | 09:53:00 | SOFI | one_candle_rule | call | D | skipped_d | 18.15 | 18.06 | loss | - |
| 2026-07-09 | 10:00:00 | AMD | one_candle_rule | call | D | skipped_d | 556.56 | 554.71 | loss | - |
| 2026-07-09 | 10:09:00 | IREN | one_candle_rule | put | D | skipped_d | 43.20 | 43.63 | win | - |
| 2026-07-09 | 10:14:00 | ORCL | one_candle_rule | put | D | skipped_d | 146.36 | 147.28 | win | - |
| 2026-07-09 | 10:17:00 | AMD | one_candle_rule | put | D | skipped_d | 552.29 | 557.65 | loss | - |
| 2026-07-09 | 10:27:00 | HOOD | one_candle_rule | put | D | skipped_d | 115.78 | 116.35 | win | - |
| 2026-07-09 | 10:27:00 | INTC | break_and_retest | put | D | skipped_d | 113.25 | 113.42 | loss | - |
| 2026-07-09 | 10:28:00 | IREN | one_candle_rule | call | D | skipped_d | 42.89 | 42.55 | loss | - |
| 2026-07-09 | 10:30:00 | PLTR | break_and_retest | put | D | skipped_d | 125.53 | 125.69 | loss | - |
| 2026-07-09 | 10:30:00 | COIN | break_and_retest | call | D | skipped_d | 157.62 | 157.51 | loss | - |
| 2026-07-09 | 10:32:00 | SPY | break_and_retest | call | D | skipped_d | 747.57 | 747.50 | loss | - |
| 2026-07-09 | 10:32:00 | HOOD | break_and_retest | call | D | skipped_d | 115.36 | 115.00 | win | - |
| 2026-07-09 | 10:35:00 | NVDA | one_candle_rule | put | D | skipped_d | 199.89 | 200.27 | loss | - |
| 2026-07-09 | 10:37:00 | COIN | one_candle_rule | call | D | skipped_d | 157.09 | 156.67 | win | - |
| 2026-07-09 | 10:50:00 | QQQ | break_and_retest | call | D | skipped_d | 719.35 | 719.17 | loss | - |
| 2026-07-09 | 10:50:00 | QQQ | break_and_retest | call | D | skipped_d | 719.35 | 719.24 | loss | - |
| 2026-07-09 | 10:51:00 | GOOGL | break_and_retest | put | D | skipped_d | 353.02 | 353.16 | win | - |
| 2026-07-10 | 09:40:00 | SOFI | break_and_retest | call | D | skipped_d | 19.50 | 19.48 | loss | - |
| 2026-07-10 | 09:40:00 | ORCL | break_and_retest | put | D | skipped_d | 143.31 | 144.20 | win | - |
| 2026-07-10 | 09:41:00 | TSLA | break_and_retest | put | D | skipped_d | 406.72 | 407.05 | loss | - |
| 2026-07-10 | 09:41:00 | META | break_and_retest | call | D | skipped_d | 665.21 | 664.79 | loss | - |
| 2026-07-10 | 09:46:00 | NVDA | break_and_retest | call | A | fired | 205.47 | 204.40 | win | $2000 |
| 2026-07-10 | 09:53:00 | QQQ | one_candle_rule | call | D | skipped_d | 723.60 | 722.62 | loss | - |
| 2026-07-10 | 09:54:00 | MSFT | break_and_retest | put | B | fired | 385.72 | 386.36 | loss | $-1000 |
| 2026-07-10 | 09:55:00 | QQQ | break_and_retest | call | D | skipped_d | 722.85 | 722.80 | loss | - |
| 2026-07-10 | 09:56:00 | SPY | break_and_retest | call | D | skipped_d | 752.97 | 752.86 | loss | - |
| 2026-07-10 | 10:07:00 | HOOD | break_and_retest | put | D | skipped_d | 111.08 | 111.63 | loss | - |
| 2026-07-10 | 10:08:00 | GOOGL | break_and_retest | put | D | skipped_d | 355.15 | 355.22 | loss | - |
| 2026-07-10 | 10:12:00 | AMD | break_and_retest | call | B | fired | 552.15 | 550.98 | loss | $-1000 |
| 2026-07-10 | 10:18:00 | NVDA | one_candle_rule | put | D | skipped_d | 207.29 | 208.14 | loss | - |
| 2026-07-10 | 10:18:00 | ORCL | break_and_retest | put | D | skipped_d | 141.69 | 141.83 | win | - |
| 2026-07-10 | 10:18:00 | INTC | one_candle_rule | call | D | skipped_d | 109.21 | 108.88 | loss | - |
| 2026-07-10 | 10:21:00 | NVDA | one_candle_rule | call | D | skipped_d | 206.40 | 205.90 | win | - |
| 2026-07-10 | 10:21:00 | AMZN | one_candle_rule | call | D | skipped_d | 246.37 | 246.13 | loss | - |
| 2026-07-10 | 10:23:00 | ORCL | one_candle_rule | put | D | skipped_d | 141.10 | 141.30 | win | - |
| 2026-07-10 | 10:26:00 | SPY | break_and_retest | call | D | skipped_d | 752.61 | 752.33 | loss | - |
| 2026-07-10 | 10:29:00 | AAPL | break_and_retest | put | D | skipped_d | 313.13 | 313.21 | win | - |
| 2026-07-10 | 10:29:00 | ORCL | break_and_retest | put | D | skipped_d | 140.93 | 140.94 | loss | - |
| 2026-07-10 | 10:34:00 | META | one_candle_rule | call | D | skipped_d | 666.60 | 662.12 | loss | - |
| 2026-07-10 | 10:35:00 | TSLA | break_and_retest | put | D | skipped_d | 406.83 | 407.05 | loss | - |
| 2026-07-10 | 10:39:00 | SPY | break_and_retest | put | D | skipped_d | 751.69 | 752.01 | loss | - |

## Findings & Recommendations
- A+/A win rate 50% vs B/C 38% -> KEEP grading
- D-grade filter: filtered signals would have won 34% -> filter justified (<50%)
- 84% rule (Lesson 6 canonical 2026-07-06: solid B&R stop-out arms one re-entry on the reclaim close, ORIGINAL stop + target): 3 triggers, fired win rate 50%.
- 84% live wiring: armed per-symbol off paper stop-outs in live_scanner (2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.
- Best setup: reentry_84_rule (50%) | worst: break_and_retest (40%)
- C-grade alerts (3, alert-only per SPEC2) would have won 33% - similar to traded grades; alert-only demotion costs little.


## Rule 6 Report

# Backtest Report: Week of 2026-07-06 to 2026-07-10

## Assumptions
- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals
- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close
- Stop+target same bar counted as loss (conservative)
- Repeat fires of same setup within 30 min deduped

## Summary
- Traded signals (A+/A/B, viable stop): **12** | 4W 8L 0 scratch | win rate 33.3% (of decided)
- Simulated P&L (traded all A+/A/B): **+$1000.0**
- C-grade alerts (alert-only per SPEC2): 3 | D filtered: 125 | tight-stop skips: 2

### By Grade
| Grade | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| A | 4 | 2 | 2 | 0 | 50.0% | $1000.0 |
| B | 8 | 2 | 6 | 0 | 25.0% | $0.0 |
| C (alert only) | 3 | 0 | 3 | 0 | 0.0% | ($0.0 if traded) |
| D (filtered) | 125 | 13 | 112 | 0 | 10.4% | ($18500.0 if traded) |

### By Setup
| Setup | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| break_and_retest | 10 | 3 | 7 | 0 | 30.0% | $500.0 |
| reentry_84_rule | 2 | 1 | 1 | 0 | 50.0% | $500.0 |

### By Symbol
| Symbol | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| AAPL | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| AMD | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| AMZN | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| INTC | 1 | 1 | 0 | 0 | 100.0% | $1500.0 |
| MSFT | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| NVDA | 4 | 2 | 2 | 0 | 50.0% | $1000.0 |
| ORCL | 1 | 0 | 1 | 0 | 0.0% | $500.0 |
| TSLA | 2 | 1 | 1 | 0 | 50.0% | $2000.0 |

### B&R: clean first break vs late (level broken earlier)
| Bucket | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| clean | 4 | 1 | 3 | 0 | 25.0% | $0.0 |
| late | 6 | 2 | 4 | 0 | 33.3% | $500.0 |

### Rule 6: Breakeven Scale Analysis
| Metric | Value |
|--------|-------|
| Trades that hit BE scale | 6/12 (50%) |
| BE scaled -> win | 4 |
| BE scaled -> loss (stopped at breakeven) | 2 |
| BE scaled -> scratch | 0 |
| P&L from BE-scaled trades | $7000.0 |
| Win rate (BE scaled) | 66.7% |
| Win rate (no BE scale) | 0.0% |
| Scaling improved returns | YES |

## By Day
| Day | Signals | Wins | Losses | Scratch | P&L |
|-----|---------|------|--------|---------|-----|
| 2026-07-06 | 2 | 0 | 2 | 0 | $-500.0 |
| 2026-07-07 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-08 | 7 | 3 | 4 | 0 | $2000.0 |
| 2026-07-09 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-10 | 3 | 1 | 2 | 0 | $-500.0 |

## 84% Rule Analysis
- Total triggers (incl. filtered): 4
- Fired re-entry signals: 2
- Win rate on re-entry: 50.0% | P&L $500.0

## Signal Log
| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |
|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|
| 2026-07-06 | 09:35:00 | QQQ | one_candle_rule | call | D | skipped_d | 721.43 | 720.16 | loss | - |
| 2026-07-06 | 09:36:00 | SOFI | break_and_retest | call | D | skipped_d | 18.52 | 18.46 | loss | - |
| 2026-07-06 | 09:38:00 | AMD | break_and_retest | call | D | skipped_d | 542.94 | 540.00 | loss | - |
| 2026-07-06 | 09:41:00 | ORCL | break_and_retest | put | B | fired | 142.71 | 143.08 | loss | $500 |
| 2026-07-06 | 09:41:00 | COIN | break_and_retest | put | D | skipped_d | 162.99 | 163.22 | loss | - |
| 2026-07-06 | 09:42:00 | AAPL | break_and_retest | call | D | skipped_d | 308.74 | 308.63 | loss | - |
| 2026-07-06 | 09:42:00 | SPY | break_and_retest | put | D | skipped_d | 748.00 | 748.12 | loss | - |
| 2026-07-06 | 09:42:00 | ORCL | break_and_retest | put | C | skipped_tight_stop | 142.08 | 142.61 | loss | - |
| 2026-07-06 | 09:43:00 | IREN | break_and_retest | call | D | skipped_d | 43.62 | 43.42 | loss | - |
| 2026-07-06 | 09:46:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.60 | 360.44 | win | - |
| 2026-07-06 | 09:46:00 | ORCL | reentry_84_rule | put | C | skipped_tight_stop | 142.67 | 143.08 | loss | - |
| 2026-07-06 | 09:48:00 | NVDA | break_and_retest | call | D | skipped_d | 194.98 | 194.88 | loss | - |
| 2026-07-06 | 09:48:00 | INTC | break_and_retest | call | D | skipped_d | 125.32 | 125.08 | loss | - |
| 2026-07-06 | 09:48:00 | INTC | break_and_retest | call | D | skipped_d | 125.32 | 125.01 | loss | - |
| 2026-07-06 | 09:53:00 | SPY | break_and_retest | call | D | skipped_d | 748.90 | 748.88 | loss | - |
| 2026-07-06 | 09:53:00 | QQQ | break_and_retest | call | D | skipped_d | 723.14 | 722.27 | loss | - |
| 2026-07-06 | 09:53:00 | QQQ | break_and_retest | call | D | skipped_d | 723.14 | 722.38 | loss | - |
| 2026-07-06 | 09:54:00 | TSLA | break_and_retest | call | D | skipped_d | 401.36 | 400.66 | loss | - |
| 2026-07-06 | 09:54:00 | SPY | one_candle_rule | put | C | fired | 748.88 | 749.54 | loss | - |
| 2026-07-06 | 10:00:00 | HOOD | one_candle_rule | call | D | skipped_d | 114.44 | 113.77 | loss | - |
| 2026-07-06 | 10:06:00 | SMCI | break_and_retest | put | D | skipped_d | 27.24 | 27.26 | loss | - |
| 2026-07-06 | 10:12:00 | AAPL | break_and_retest | call | D | skipped_d | 309.46 | 309.42 | loss | - |
| 2026-07-06 | 10:12:00 | AAPL | one_candle_rule | put | D | skipped_d | 309.46 | 309.73 | loss | - |
| 2026-07-06 | 10:19:00 | ORCL | one_candle_rule | call | D | skipped_d | 142.39 | 141.51 | loss | - |
| 2026-07-06 | 10:23:00 | NVDA | one_candle_rule | put | D | skipped_d | 196.23 | 196.39 | loss | - |
| 2026-07-06 | 10:24:00 | COIN | break_and_retest | put | D | skipped_d | 163.01 | 163.22 | loss | - |
| 2026-07-06 | 10:26:00 | ORCL | break_and_retest | put | D | skipped_d | 142.46 | 142.61 | loss | - |
| 2026-07-06 | 10:38:00 | MSFT | break_and_retest | put | D | skipped_d | 383.17 | 383.70 | loss | - |
| 2026-07-06 | 10:50:00 | AMZN | break_and_retest | put | B | fired | 242.82 | 243.20 | loss | $-1000 |
| 2026-07-06 | 10:50:00 | AMZN | break_and_retest | put | D | skipped_d | 242.82 | 243.01 | loss | - |
| 2026-07-06 | 10:52:00 | PLTR | break_and_retest | call | D | skipped_d | 130.54 | 130.48 | loss | - |
| 2026-07-06 | 10:55:00 | SOFI | one_candle_rule | call | D | skipped_d | 18.57 | 18.51 | win | - |
| 2026-07-06 | 10:59:00 | INTC | one_candle_rule | put | D | skipped_d | 126.20 | 126.52 | loss | - |
| 2026-07-07 | 09:38:00 | AMD | break_and_retest | put | D | skipped_d | 511.02 | 515.80 | loss | - |
| 2026-07-07 | 09:39:00 | SMCI | break_and_retest | put | D | skipped_d | 26.54 | 26.55 | loss | - |
| 2026-07-07 | 09:44:00 | SOFI | break_and_retest | put | D | skipped_d | 18.43 | 18.45 | loss | - |
| 2026-07-07 | 09:47:00 | PLTR | break_and_retest | call | D | skipped_d | 134.07 | 134.07 | loss | - |
| 2026-07-07 | 09:48:00 | QQQ | break_and_retest | put | D | skipped_d | 712.89 | 713.46 | loss | - |
| 2026-07-07 | 09:59:00 | HOOD | break_and_retest | put | D | skipped_d | 115.07 | 115.10 | loss | - |
| 2026-07-07 | 10:03:00 | SOFI | one_candle_rule | put | D | skipped_d | 18.12 | 18.21 | win | - |
| 2026-07-07 | 10:05:00 | AMZN | one_candle_rule | put | D | skipped_d | 246.74 | 247.95 | win | - |
| 2026-07-07 | 10:06:00 | TSLA | break_and_retest | put | D | skipped_d | 414.48 | 414.54 | loss | - |
| 2026-07-07 | 10:06:00 | INTC | break_and_retest | put | D | skipped_d | 111.95 | 112.02 | loss | - |
| 2026-07-07 | 10:06:00 | SMCI | one_candle_rule | put | D | skipped_d | 26.14 | 26.21 | loss | - |
| 2026-07-07 | 10:12:00 | MSFT | one_candle_rule | call | D | skipped_d | 392.55 | 391.52 | win | - |
| 2026-07-07 | 10:15:00 | AMZN | one_candle_rule | call | D | skipped_d | 247.02 | 246.53 | loss | - |
| 2026-07-07 | 10:17:00 | AMZN | break_and_retest | call | D | skipped_d | 246.18 | 246.04 | loss | - |
| 2026-07-07 | 10:21:00 | META | break_and_retest | call | D | skipped_d | 612.34 | 612.18 | loss | - |
| 2026-07-07 | 10:21:00 | HOOD | break_and_retest | put | D | skipped_d | 113.91 | 114.11 | loss | - |
| 2026-07-07 | 10:22:00 | HOOD | one_candle_rule | put | D | skipped_d | 113.96 | 114.57 | loss | - |
| 2026-07-07 | 10:30:00 | GOOGL | break_and_retest | call | D | skipped_d | 370.73 | 370.50 | loss | - |
| 2026-07-07 | 10:31:00 | PLTR | one_candle_rule | put | D | skipped_d | 133.38 | 134.20 | loss | - |
| 2026-07-07 | 10:35:00 | SMCI | one_candle_rule | call | D | skipped_d | 25.52 | 25.45 | loss | - |
| 2026-07-07 | 10:57:00 | AAPL | break_and_retest | put | D | skipped_d | 312.70 | 312.80 | loss | - |
| 2026-07-08 | 09:40:00 | PLTR | break_and_retest | put | D | skipped_d | 128.47 | 128.53 | loss | - |
| 2026-07-08 | 09:42:00 | ORCL | break_and_retest | call | D | skipped_d | 140.56 | 140.50 | win | - |
| 2026-07-08 | 09:42:00 | ORCL | one_candle_rule | call | D | skipped_d | 140.56 | 139.20 | loss | - |
| 2026-07-08 | 09:43:00 | NVDA | break_and_retest | call | B | fired | 198.04 | 197.45 | win | $1500 |
| 2026-07-08 | 09:43:00 | SOFI | break_and_retest | call | D | skipped_d | 17.53 | 17.50 | loss | - |
| 2026-07-08 | 09:44:00 | SPY | break_and_retest | call | D | skipped_d | 744.34 | 744.09 | loss | - |
| 2026-07-08 | 09:45:00 | HOOD | break_and_retest | call | D | skipped_d | 112.61 | 111.81 | loss | - |
| 2026-07-08 | 09:47:00 | NVDA | break_and_retest | call | D | skipped_d | 198.41 | 198.41 | loss | - |
| 2026-07-08 | 09:49:00 | AAPL | break_and_retest | put | D | skipped_d | 308.52 | 308.68 | loss | - |
| 2026-07-08 | 09:50:00 | META | break_and_retest | put | D | skipped_d | 603.40 | 603.66 | loss | - |
| 2026-07-08 | 09:50:00 | QQQ | break_and_retest | call | D | skipped_d | 707.96 | 707.92 | loss | - |
| 2026-07-08 | 09:51:00 | AMD | one_candle_rule | put | D | skipped_d | 517.61 | 521.98 | loss | - |
| 2026-07-08 | 09:51:00 | SPY | one_candle_rule | put | C | fired | 743.81 | 744.92 | loss | - |
| 2026-07-08 | 09:51:00 | QQQ | one_candle_rule | put | D | skipped_d | 708.22 | 709.71 | loss | - |
| 2026-07-08 | 09:59:00 | TSLA | break_and_retest | put | D | skipped_d | 395.88 | 395.99 | loss | - |
| 2026-07-08 | 10:00:00 | TSLA | break_and_retest | put | B | fired | 394.96 | 395.66 | loss | $500 |
| 2026-07-08 | 10:03:00 | PLTR | one_candle_rule | call | D | skipped_d | 128.02 | 127.45 | loss | - |
| 2026-07-08 | 10:11:00 | IREN | one_candle_rule | call | D | skipped_d | 42.04 | 41.85 | loss | - |
| 2026-07-08 | 10:17:00 | META | break_and_retest | put | D | skipped_d | 604.39 | 604.40 | loss | - |
| 2026-07-08 | 10:18:00 | AMZN | break_and_retest | put | D | skipped_d | 242.69 | 242.70 | loss | - |
| 2026-07-08 | 10:25:00 | QQQ | break_and_retest | call | D | skipped_d | 708.39 | 707.92 | loss | - |
| 2026-07-08 | 10:25:00 | IREN | break_and_retest | call | D | skipped_d | 42.27 | 42.12 | loss | - |
| 2026-07-08 | 10:27:00 | AMD | one_candle_rule | call | D | skipped_d | 516.31 | 513.62 | loss | - |
| 2026-07-08 | 10:27:00 | PLTR | break_and_retest | put | D | skipped_d | 128.35 | 128.53 | loss | - |
| 2026-07-08 | 10:28:00 | AAPL | break_and_retest | put | B | fired | 309.08 | 310.15 | loss | $-1000 |
| 2026-07-08 | 10:32:00 | TSLA | reentry_84_rule | put | A | fired | 394.87 | 395.66 | win | $1500 |
| 2026-07-08 | 10:38:00 | INTC | break_and_retest | put | B | fired | 107.57 | 108.00 | win | $1500 |
| 2026-07-08 | 10:42:00 | SPY | break_and_retest | put | D | skipped_d | 742.29 | 742.64 | loss | - |
| 2026-07-08 | 10:51:00 | SPY | one_candle_rule | put | D | skipped_d | 741.58 | 741.93 | loss | - |
| 2026-07-08 | 10:51:00 | QQQ | break_and_retest | put | D | skipped_d | 704.87 | 704.94 | loss | - |
| 2026-07-08 | 10:51:00 | QQQ | break_and_retest | put | D | skipped_d | 704.87 | 704.90 | loss | - |
| 2026-07-08 | 10:51:00 | SOFI | one_candle_rule | put | D | skipped_d | 17.21 | 17.26 | loss | - |
| 2026-07-08 | 10:52:00 | SMCI | break_and_retest | call | D | skipped_d | 26.87 | 26.83 | loss | - |
| 2026-07-08 | 10:53:00 | COIN | break_and_retest | put | D | skipped_d | 158.10 | 158.15 | loss | - |
| 2026-07-08 | 10:56:00 | AMZN | one_candle_rule | put | D | skipped_d | 241.82 | 242.20 | win | - |
| 2026-07-08 | 10:57:00 | NVDA | break_and_retest | call | A | fired | 198.75 | 197.93 | loss | $-1000 |
| 2026-07-08 | 10:59:00 | NVDA | reentry_84_rule | call | A | fired | 198.78 | 197.93 | loss | $-1000 |
| 2026-07-08 | 10:59:00 | AAPL | reentry_84_rule | put | C | fired | 308.88 | 310.15 | loss | - |
| 2026-07-09 | 09:38:00 | GOOGL | break_and_retest | call | D | skipped_d | 358.22 | 358.10 | loss | - |
| 2026-07-09 | 09:40:00 | MSFT | break_and_retest | call | D | skipped_d | 376.46 | 375.95 | loss | - |
| 2026-07-09 | 09:40:00 | SPY | break_and_retest | call | D | skipped_d | 747.54 | 747.50 | loss | - |
| 2026-07-09 | 09:43:00 | AAPL | break_and_retest | call | D | skipped_d | 311.10 | 311.00 | loss | - |
| 2026-07-09 | 09:43:00 | IREN | break_and_retest | put | D | skipped_d | 43.92 | 44.02 | loss | - |
| 2026-07-09 | 09:44:00 | MSFT | one_candle_rule | call | D | skipped_d | 378.33 | 377.01 | loss | - |
| 2026-07-09 | 09:47:00 | AAPL | one_candle_rule | put | D | skipped_d | 311.30 | 311.92 | loss | - |
| 2026-07-09 | 09:51:00 | AMD | break_and_retest | call | D | skipped_d | 551.78 | 548.95 | win | - |
| 2026-07-09 | 09:51:00 | SPY | break_and_retest | call | D | skipped_d | 748.57 | 748.43 | loss | - |
| 2026-07-09 | 09:53:00 | SOFI | one_candle_rule | call | D | skipped_d | 18.15 | 18.06 | loss | - |
| 2026-07-09 | 10:00:00 | AMD | one_candle_rule | call | D | skipped_d | 556.56 | 554.71 | loss | - |
| 2026-07-09 | 10:09:00 | IREN | one_candle_rule | put | D | skipped_d | 43.20 | 43.63 | win | - |
| 2026-07-09 | 10:14:00 | ORCL | one_candle_rule | put | D | skipped_d | 146.36 | 147.28 | win | - |
| 2026-07-09 | 10:17:00 | AMD | one_candle_rule | put | D | skipped_d | 552.29 | 557.65 | loss | - |
| 2026-07-09 | 10:27:00 | HOOD | one_candle_rule | put | D | skipped_d | 115.78 | 116.35 | loss | - |
| 2026-07-09 | 10:27:00 | INTC | break_and_retest | put | D | skipped_d | 113.25 | 113.42 | loss | - |
| 2026-07-09 | 10:28:00 | IREN | one_candle_rule | call | D | skipped_d | 42.89 | 42.55 | loss | - |
| 2026-07-09 | 10:30:00 | PLTR | break_and_retest | put | D | skipped_d | 125.53 | 125.69 | loss | - |
| 2026-07-09 | 10:30:00 | COIN | break_and_retest | call | D | skipped_d | 157.62 | 157.51 | loss | - |
| 2026-07-09 | 10:32:00 | SPY | break_and_retest | call | D | skipped_d | 747.57 | 747.50 | loss | - |
| 2026-07-09 | 10:32:00 | HOOD | break_and_retest | call | D | skipped_d | 115.36 | 115.00 | loss | - |
| 2026-07-09 | 10:35:00 | NVDA | one_candle_rule | put | D | skipped_d | 199.89 | 200.27 | loss | - |
| 2026-07-09 | 10:37:00 | COIN | one_candle_rule | call | D | skipped_d | 157.09 | 156.67 | win | - |
| 2026-07-09 | 10:50:00 | QQQ | break_and_retest | call | D | skipped_d | 719.35 | 719.17 | loss | - |
| 2026-07-09 | 10:50:00 | QQQ | break_and_retest | call | D | skipped_d | 719.35 | 719.24 | loss | - |
| 2026-07-09 | 10:51:00 | GOOGL | break_and_retest | put | D | skipped_d | 353.02 | 353.16 | loss | - |
| 2026-07-10 | 09:40:00 | SOFI | break_and_retest | call | D | skipped_d | 19.50 | 19.48 | loss | - |
| 2026-07-10 | 09:40:00 | ORCL | break_and_retest | put | D | skipped_d | 143.31 | 144.20 | loss | - |
| 2026-07-10 | 09:41:00 | TSLA | break_and_retest | put | D | skipped_d | 406.72 | 407.05 | loss | - |
| 2026-07-10 | 09:41:00 | META | break_and_retest | call | D | skipped_d | 665.21 | 664.79 | loss | - |
| 2026-07-10 | 09:46:00 | NVDA | break_and_retest | call | A | fired | 205.47 | 204.40 | win | $1500 |
| 2026-07-10 | 09:53:00 | QQQ | one_candle_rule | call | D | skipped_d | 723.60 | 722.62 | loss | - |
| 2026-07-10 | 09:54:00 | MSFT | break_and_retest | put | B | fired | 385.72 | 386.36 | loss | $-1000 |
| 2026-07-10 | 09:55:00 | QQQ | break_and_retest | call | D | skipped_d | 722.85 | 722.80 | loss | - |
| 2026-07-10 | 09:56:00 | SPY | break_and_retest | call | D | skipped_d | 752.97 | 752.86 | loss | - |
| 2026-07-10 | 10:07:00 | HOOD | break_and_retest | put | D | skipped_d | 111.08 | 111.63 | loss | - |
| 2026-07-10 | 10:08:00 | GOOGL | break_and_retest | put | D | skipped_d | 355.15 | 355.22 | loss | - |
| 2026-07-10 | 10:12:00 | AMD | break_and_retest | call | B | fired | 552.15 | 550.98 | loss | $-1000 |
| 2026-07-10 | 10:18:00 | NVDA | one_candle_rule | put | D | skipped_d | 207.29 | 208.14 | loss | - |
| 2026-07-10 | 10:18:00 | ORCL | break_and_retest | put | D | skipped_d | 141.69 | 141.83 | loss | - |
| 2026-07-10 | 10:18:00 | INTC | one_candle_rule | call | D | skipped_d | 109.21 | 108.88 | loss | - |
| 2026-07-10 | 10:21:00 | NVDA | one_candle_rule | call | D | skipped_d | 206.40 | 205.90 | win | - |
| 2026-07-10 | 10:21:00 | AMZN | one_candle_rule | call | D | skipped_d | 246.37 | 246.13 | loss | - |
| 2026-07-10 | 10:23:00 | ORCL | one_candle_rule | put | D | skipped_d | 141.10 | 141.30 | win | - |
| 2026-07-10 | 10:26:00 | SPY | break_and_retest | call | D | skipped_d | 752.61 | 752.33 | loss | - |
| 2026-07-10 | 10:29:00 | AAPL | break_and_retest | put | D | skipped_d | 313.13 | 313.21 | loss | - |
| 2026-07-10 | 10:29:00 | ORCL | break_and_retest | put | D | skipped_d | 140.93 | 140.94 | loss | - |
| 2026-07-10 | 10:34:00 | META | one_candle_rule | call | D | skipped_d | 666.60 | 662.12 | loss | - |
| 2026-07-10 | 10:35:00 | TSLA | break_and_retest | put | D | skipped_d | 406.83 | 407.05 | loss | - |
| 2026-07-10 | 10:39:00 | SPY | break_and_retest | put | D | skipped_d | 751.69 | 752.01 | loss | - |

## Findings & Recommendations
- A+/A win rate 50% vs B/C 25% -> KEEP grading
- D-grade filter: filtered signals would have won 10% -> filter justified (<50%)
- 84% rule (Lesson 6 canonical 2026-07-06: solid B&R stop-out arms one re-entry on the reclaim close, ORIGINAL stop + target): 4 triggers, fired win rate 50%.
- 84% live wiring: armed per-symbol off paper stop-outs in live_scanner (2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.
- Best setup: reentry_84_rule (50%) | worst: break_and_retest (30%)
- C-grade alerts (3, alert-only per SPEC2) would have won 0% - similar to traded grades; alert-only demotion costs little.
