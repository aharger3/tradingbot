# Rule 6 Comparison Report

Generated: 2026-07-12

## Summary

| Metric | Baseline (no BE) | Rule 6 (50% BE scale) | Delta |
|--------|-----------------|----------------------|-------|
| Trades | 5 | 5 | +0 |
| Win Rate | 0.0% | 0.0% | +0.0% |
| P&L | $-5000.00 | $-5000.00 | $+0.00 |

## Interpretation

Rule 6 had neutral P&L impact - no meaningful difference.

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
- Traded signals (A+/A/B, viable stop): **5** | 0W 5L 0 scratch | win rate 0.0% (of decided)
- Simulated P&L (traded all A+/A/B): **$-5000.0**
- C-grade alerts (alert-only per SPEC2): 2 | D filtered: 206 | tight-stop skips: 0

### By Grade
| Grade | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| A+ | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| B | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| C (alert only) | 2 | 0 | 2 | 0 | 0.0% | ($-2000.0 if traded) |
| D (filtered) | 206 | 32 | 174 | 0 | 15.5% | ($-110000.0 if traded) |

### By Setup
| Setup | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| break_and_retest | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| one_candle_rule | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### By Symbol
| Symbol | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| CRM | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| GOOGL | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| HOOD | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| META | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| TSM | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### By Entry Hour
| Hour | Signals | W | L | Scratch | Win rate | P&L |
|------|---------|---|---|---------|----------|-----|
| 09:30-10:00 | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| 10:30-11:00 | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### B&R: clean first break vs late (level broken earlier)
| Bucket | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| clean | 3 | 0 | 3 | 0 | 0.0% | $-3000.0 |
| late | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

## By Day
| Day | Signals | Wins | Losses | Scratch | P&L |
|-----|---------|------|--------|---------|-----|
| 2026-07-06 | 1 | 0 | 1 | 0 | $-1000.0 |
| 2026-07-07 | 1 | 0 | 1 | 0 | $-1000.0 |
| 2026-07-08 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-09 | 3 | 0 | 3 | 0 | $-3000.0 |
| 2026-07-10 | 0 | 0 | 0 | 0 | $0 |

## 84% Rule Analysis
- Total triggers (incl. filtered): 0
- Fired re-entry signals: 0
- Win rate on re-entry: 0.0% | P&L $0

## Signal Log
| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |
|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|
| 2026-07-06 | 09:44:00 | GOOGL | one_candle_rule | call | D | skipped_d | 361.08 | 360.84 | win | - |
| 2026-07-06 | 09:45:00 | COIN | break_and_retest | put | D | skipped_d | 168.60 | 168.70 | win | - |
| 2026-07-06 | 09:45:00 | NFLX | break_and_retest | put | D | skipped_d | 77.59 | 77.70 | loss | - |
| 2026-07-06 | 09:50:00 | INTC | one_candle_rule | put | D | skipped_d | 123.92 | 124.18 | loss | - |
| 2026-07-06 | 09:52:00 | CRM | break_and_retest | call | B | fired | 166.80 | 166.30 | loss | $-1000 |
| 2026-07-06 | 09:53:00 | SMCI | break_and_retest | call | D | skipped_d | 27.81 | 27.77 | loss | - |
| 2026-07-06 | 09:54:00 | ORCL | one_candle_rule | call | D | skipped_d | 145.42 | 145.18 | loss | - |
| 2026-07-06 | 09:54:00 | HOOD | one_candle_rule | call | D | skipped_d | 113.98 | 113.83 | win | - |
| 2026-07-06 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 113.98 | 114.00 | loss | - |
| 2026-07-06 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 113.98 | 114.04 | loss | - |
| 2026-07-06 | 10:00:00 | AMD | break_and_retest | call | D | skipped_d | 532.51 | 530.99 | loss | - |
| 2026-07-06 | 10:03:00 | TSLA | break_and_retest | call | D | skipped_d | 399.82 | 399.77 | loss | - |
| 2026-07-06 | 10:03:00 | TSLA | break_and_retest | call | D | skipped_d | 399.82 | 399.75 | loss | - |
| 2026-07-06 | 10:03:00 | AMZN | break_and_retest | call | D | skipped_d | 246.22 | 245.95 | loss | - |
| 2026-07-06 | 10:03:00 | INTC | break_and_retest | call | D | skipped_d | 124.46 | 124.39 | loss | - |
| 2026-07-06 | 10:04:00 | CRM | break_and_retest | call | D | skipped_d | 166.40 | 166.39 | win | - |
| 2026-07-06 | 10:06:00 | PLTR | break_and_retest | call | D | skipped_d | 129.98 | 129.94 | loss | - |
| 2026-07-06 | 10:08:00 | COIN | break_and_retest | call | D | skipped_d | 169.00 | 168.93 | loss | - |
| 2026-07-06 | 10:09:00 | AVGO | break_and_retest | call | D | skipped_d | 367.40 | 367.25 | loss | - |
| 2026-07-06 | 10:10:00 | BABA | break_and_retest | put | D | skipped_d | 97.51 | 97.52 | loss | - |
| 2026-07-06 | 10:12:00 | AVGO | break_and_retest | call | D | skipped_d | 367.22 | 367.19 | loss | - |
| 2026-07-06 | 10:12:00 | MU | break_and_retest | put | D | skipped_d | 997.51 | 998.00 | loss | - |
| 2026-07-06 | 10:13:00 | HOOD | break_and_retest | call | D | skipped_d | 114.46 | 114.41 | loss | - |
| 2026-07-06 | 10:14:00 | NFLX | break_and_retest | call | D | skipped_d | 78.00 | 77.89 | loss | - |
| 2026-07-06 | 10:15:00 | AAPL | one_candle_rule | put | D | skipped_d | 305.60 | 305.80 | loss | - |
| 2026-07-06 | 10:25:00 | ORCL | break_and_retest | put | D | skipped_d | 145.05 | 145.10 | loss | - |
| 2026-07-06 | 10:32:00 | SPY | break_and_retest | call | D | skipped_d | 748.54 | 748.48 | win | - |
| 2026-07-06 | 10:37:00 | RIVN | one_candle_rule | call | D | skipped_d | 18.77 | 18.74 | loss | - |
| 2026-07-06 | 10:40:00 | TSM | break_and_retest | call | D | skipped_d | 445.95 | 445.76 | loss | - |
| 2026-07-06 | 10:42:00 | MARA | break_and_retest | call | D | skipped_d | 12.66 | 12.66 | loss | - |
| 2026-07-06 | 10:43:00 | IREN | break_and_retest | put | D | skipped_d | 41.18 | 41.25 | loss | - |
| 2026-07-06 | 10:51:00 | META | break_and_retest | put | D | skipped_d | 591.68 | 592.24 | loss | - |
| 2026-07-06 | 10:53:00 | HOOD | break_and_retest | put | D | skipped_d | 114.01 | 114.04 | loss | - |
| 2026-07-07 | 09:36:00 | AMD | break_and_retest | put | D | skipped_d | 527.80 | 528.60 | loss | - |
| 2026-07-07 | 09:38:00 | NVDA | break_and_retest | put | D | skipped_d | 193.75 | 193.80 | loss | - |
| 2026-07-07 | 09:40:00 | AVGO | break_and_retest | put | D | skipped_d | 365.86 | 366.50 | loss | - |
| 2026-07-07 | 09:41:00 | SMCI | break_and_retest | put | D | skipped_d | 26.70 | 26.71 | loss | - |
| 2026-07-07 | 09:42:00 | CRM | one_candle_rule | call | D | skipped_d | 168.70 | 168.33 | loss | - |
| 2026-07-07 | 09:43:00 | BABA | break_and_retest | call | D | skipped_d | 97.95 | 97.84 | loss | - |
| 2026-07-07 | 09:44:00 | GOOGL | break_and_retest | call | A+ | fired | 370.25 | 369.37 | loss | $-1000 |
| 2026-07-07 | 09:44:00 | GOOGL | break_and_retest | call | C | fired | 370.25 | 369.46 | loss | - |
| 2026-07-07 | 09:45:00 | TSLA | break_and_retest | call | D | skipped_d | 414.83 | 414.74 | loss | - |
| 2026-07-07 | 09:45:00 | TSLA | break_and_retest | call | D | skipped_d | 414.83 | 414.64 | loss | - |
| 2026-07-07 | 09:47:00 | CRM | break_and_retest | call | D | skipped_d | 168.75 | 168.63 | loss | - |
| 2026-07-07 | 09:47:00 | CRM | break_and_retest | call | D | skipped_d | 168.75 | 168.63 | loss | - |
| 2026-07-07 | 09:48:00 | SOFI | break_and_retest | call | D | skipped_d | 18.82 | 18.80 | loss | - |
| 2026-07-07 | 09:49:00 | INTC | break_and_retest | put | D | skipped_d | 116.30 | 116.33 | loss | - |
| 2026-07-07 | 09:51:00 | SPY | break_and_retest | call | D | skipped_d | 750.32 | 750.24 | win | - |
| 2026-07-07 | 09:55:00 | PLTR | break_and_retest | call | D | skipped_d | 134.55 | 134.49 | loss | - |
| 2026-07-07 | 09:56:00 | AVGO | break_and_retest | put | D | skipped_d | 364.59 | 365.50 | loss | - |
| 2026-07-07 | 09:56:00 | AVGO | break_and_retest | put | D | skipped_d | 364.59 | 365.62 | loss | - |
| 2026-07-07 | 09:57:00 | SOFI | break_and_retest | call | D | skipped_d | 18.83 | 18.82 | loss | - |
| 2026-07-07 | 09:58:00 | MSFT | break_and_retest | put | D | skipped_d | 392.65 | 392.83 | loss | - |
| 2026-07-07 | 10:01:00 | AMZN | one_candle_rule | put | D | skipped_d | 247.79 | 248.10 | win | - |
| 2026-07-07 | 10:02:00 | NVDA | break_and_retest | call | D | skipped_d | 194.05 | 194.02 | win | - |
| 2026-07-07 | 10:02:00 | AAPL | one_candle_rule | put | D | skipped_d | 314.52 | 314.77 | loss | - |
| 2026-07-07 | 10:04:00 | SMCI | break_and_retest | call | D | skipped_d | 26.79 | 26.78 | loss | - |
| 2026-07-07 | 10:05:00 | AMZN | one_candle_rule | put | D | skipped_d | 247.62 | 247.66 | loss | - |
| 2026-07-07 | 10:06:00 | TSLA | one_candle_rule | call | D | skipped_d | 415.99 | 415.52 | loss | - |
| 2026-07-07 | 10:08:00 | IREN | break_and_retest | call | D | skipped_d | 43.14 | 43.11 | loss | - |
| 2026-07-07 | 10:09:00 | INTC | break_and_retest | put | D | skipped_d | 116.68 | 116.80 | loss | - |
| 2026-07-07 | 10:10:00 | TSM | break_and_retest | call | D | skipped_d | 443.75 | 443.18 | win | - |
| 2026-07-07 | 10:11:00 | RIVN | one_candle_rule | call | D | skipped_d | 18.47 | 18.41 | loss | - |
| 2026-07-07 | 10:12:00 | AAPL | break_and_retest | call | D | skipped_d | 314.90 | 314.79 | loss | - |
| 2026-07-07 | 10:13:00 | UBER | break_and_retest | call | D | skipped_d | 72.99 | 72.91 | loss | - |
| 2026-07-07 | 10:16:00 | MSFT | one_candle_rule | put | D | skipped_d | 391.88 | 392.17 | loss | - |
| 2026-07-07 | 10:19:00 | ORCL | break_and_retest | call | D | skipped_d | 145.98 | 145.71 | loss | - |
| 2026-07-07 | 10:19:00 | BABA | break_and_retest | put | D | skipped_d | 97.14 | 97.30 | loss | - |
| 2026-07-07 | 10:21:00 | ORCL | break_and_retest | call | D | skipped_d | 145.87 | 145.79 | loss | - |
| 2026-07-07 | 10:22:00 | MARA | break_and_retest | call | D | skipped_d | 12.90 | 12.88 | loss | - |
| 2026-07-07 | 10:25:00 | SOFI | break_and_retest | put | D | skipped_d | 18.71 | 18.77 | loss | - |
| 2026-07-07 | 10:26:00 | SPY | break_and_retest | call | D | skipped_d | 750.43 | 750.24 | loss | - |
| 2026-07-07 | 10:27:00 | MSFT | one_candle_rule | put | D | skipped_d | 392.46 | 392.83 | loss | - |
| 2026-07-07 | 10:30:00 | GOOGL | break_and_retest | put | D | skipped_d | 368.22 | 368.57 | loss | - |
| 2026-07-07 | 10:31:00 | NFLX | break_and_retest | put | D | skipped_d | 76.70 | 76.78 | loss | - |
| 2026-07-07 | 10:32:00 | AMZN | break_and_retest | call | D | skipped_d | 247.64 | 247.52 | loss | - |
| 2026-07-07 | 10:34:00 | HOOD | break_and_retest | put | D | skipped_d | 116.50 | 116.63 | loss | - |
| 2026-07-07 | 10:38:00 | IREN | one_candle_rule | call | D | skipped_d | 43.13 | 43.05 | loss | - |
| 2026-07-07 | 10:44:00 | META | one_candle_rule | call | D | skipped_d | 605.06 | 604.95 | loss | - |
| 2026-07-07 | 10:44:00 | PLTR | break_and_retest | call | D | skipped_d | 134.49 | 134.49 | loss | - |
| 2026-07-07 | 10:44:00 | SPY | break_and_retest | put | D | skipped_d | 750.06 | 750.07 | loss | - |
| 2026-07-07 | 10:45:00 | RIVN | break_and_retest | put | D | skipped_d | 18.40 | 18.41 | loss | - |
| 2026-07-07 | 10:50:00 | AMD | break_and_retest | call | D | skipped_d | 529.51 | 529.47 | loss | - |
| 2026-07-07 | 10:50:00 | CRM | break_and_retest | put | D | skipped_d | 168.20 | 168.33 | loss | - |
| 2026-07-07 | 10:56:00 | IREN | one_candle_rule | put | D | skipped_d | 42.99 | 43.08 | loss | - |
| 2026-07-07 | 10:57:00 | MSTR | break_and_retest | call | D | skipped_d | 100.61 | 100.49 | loss | - |
| 2026-07-07 | 10:59:00 | PLTR | break_and_retest | put | D | skipped_d | 134.22 | 134.31 | loss | - |
| 2026-07-08 | 09:38:00 | IREN | break_and_retest | call | D | skipped_d | 38.76 | 38.75 | loss | - |
| 2026-07-08 | 09:38:00 | MU | break_and_retest | call | D | skipped_d | 886.50 | 885.50 | loss | - |
| 2026-07-08 | 09:41:00 | HOOD | one_candle_rule | call | D | skipped_d | 107.79 | 107.21 | loss | - |
| 2026-07-08 | 09:50:00 | AMZN | break_and_retest | call | D | skipped_d | 242.51 | 242.40 | loss | - |
| 2026-07-08 | 09:51:00 | AVGO | break_and_retest | call | D | skipped_d | 362.98 | 362.70 | loss | - |
| 2026-07-08 | 09:52:00 | NFLX | one_candle_rule | put | D | skipped_d | 76.67 | 76.75 | loss | - |
| 2026-07-08 | 09:55:00 | COIN | one_candle_rule | call | D | skipped_d | 158.07 | 157.80 | loss | - |
| 2026-07-08 | 10:00:00 | CRM | one_candle_rule | put | D | skipped_d | 165.61 | 166.03 | loss | - |
| 2026-07-08 | 10:01:00 | RIVN | break_and_retest | call | D | skipped_d | 15.76 | 15.75 | loss | - |
| 2026-07-08 | 10:04:00 | NFLX | break_and_retest | put | D | skipped_d | 76.45 | 76.55 | loss | - |
| 2026-07-08 | 10:08:00 | PLTR | one_candle_rule | put | D | skipped_d | 129.68 | 130.08 | loss | - |
| 2026-07-08 | 10:09:00 | SPY | break_and_retest | put | D | skipped_d | 739.77 | 739.84 | win | - |
| 2026-07-08 | 10:11:00 | TSLA | break_and_retest | put | D | skipped_d | 396.71 | 397.00 | loss | - |
| 2026-07-08 | 10:12:00 | TSM | one_candle_rule | call | D | skipped_d | 427.43 | 426.66 | win | - |
| 2026-07-08 | 10:22:00 | PLTR | one_candle_rule | call | D | skipped_d | 130.04 | 129.72 | win | - |
| 2026-07-08 | 10:22:00 | INTC | break_and_retest | call | D | skipped_d | 105.70 | 105.58 | loss | - |
| 2026-07-08 | 10:23:00 | SMCI | one_candle_rule | call | D | skipped_d | 25.77 | 25.75 | win | - |
| 2026-07-08 | 10:27:00 | AMD | break_and_retest | call | D | skipped_d | 506.93 | 505.00 | loss | - |
| 2026-07-08 | 10:27:00 | MSFT | break_and_retest | put | D | skipped_d | 382.15 | 382.40 | loss | - |
| 2026-07-08 | 10:31:00 | SPY | break_and_retest | call | D | skipped_d | 740.80 | 740.44 | win | - |
| 2026-07-08 | 10:31:00 | CRM | break_and_retest | call | D | skipped_d | 166.00 | 165.89 | loss | - |
| 2026-07-08 | 10:36:00 | TSLA | one_candle_rule | call | D | skipped_d | 398.11 | 397.81 | win | - |
| 2026-07-08 | 10:38:00 | GOOGL | break_and_retest | call | D | skipped_d | 362.66 | 362.45 | loss | - |
| 2026-07-08 | 10:39:00 | META | break_and_retest | call | D | skipped_d | 606.12 | 605.65 | loss | - |
| 2026-07-08 | 10:39:00 | PLTR | break_and_retest | call | D | skipped_d | 130.53 | 130.37 | loss | - |
| 2026-07-08 | 10:39:00 | HOOD | break_and_retest | call | D | skipped_d | 108.49 | 108.16 | loss | - |
| 2026-07-08 | 10:40:00 | AMZN | break_and_retest | call | D | skipped_d | 242.68 | 242.40 | loss | - |
| 2026-07-08 | 10:41:00 | RIVN | break_and_retest | call | D | skipped_d | 15.76 | 15.75 | win | - |
| 2026-07-08 | 10:42:00 | META | one_candle_rule | put | D | skipped_d | 606.08 | 607.00 | loss | - |
| 2026-07-08 | 10:45:00 | IREN | break_and_retest | put | D | skipped_d | 39.19 | 39.19 | loss | - |
| 2026-07-08 | 10:46:00 | AAPL | break_and_retest | put | D | skipped_d | 309.30 | 309.55 | loss | - |
| 2026-07-08 | 10:51:00 | MSTR | break_and_retest | call | D | skipped_d | 94.06 | 93.82 | loss | - |
| 2026-07-08 | 10:53:00 | SOFI | one_candle_rule | put | D | skipped_d | 17.33 | 17.35 | win | - |
| 2026-07-08 | 10:59:00 | COIN | break_and_retest | call | D | skipped_d | 158.63 | 158.45 | loss | - |
| 2026-07-09 | 09:37:00 | SMCI | break_and_retest | call | D | skipped_d | 28.65 | 28.63 | loss | - |
| 2026-07-09 | 09:38:00 | AMZN | break_and_retest | put | D | skipped_d | 242.91 | 242.98 | loss | - |
| 2026-07-09 | 09:40:00 | QQQ | break_and_retest | put | D | skipped_d | 715.78 | 715.80 | loss | - |
| 2026-07-09 | 09:40:00 | TSM | break_and_retest | put | B | fired | 440.33 | 441.02 | loss | $-1000 |
| 2026-07-09 | 09:42:00 | ORCL | break_and_retest | call | D | skipped_d | 142.90 | 142.80 | loss | - |
| 2026-07-09 | 09:42:00 | NFLX | break_and_retest | put | D | skipped_d | 75.15 | 75.25 | loss | - |
| 2026-07-09 | 09:44:00 | NVDA | one_candle_rule | put | D | skipped_d | 204.13 | 204.37 | loss | - |
| 2026-07-09 | 09:45:00 | AVGO | break_and_retest | put | D | skipped_d | 393.75 | 393.83 | loss | - |
| 2026-07-09 | 09:47:00 | GOOGL | break_and_retest | put | D | skipped_d | 360.05 | 360.14 | loss | - |
| 2026-07-09 | 09:48:00 | TSM | break_and_retest | call | D | skipped_d | 440.50 | 440.49 | loss | - |
| 2026-07-09 | 09:49:00 | GOOGL | break_and_retest | put | D | skipped_d | 360.21 | 360.27 | win | - |
| 2026-07-09 | 09:49:00 | SMCI | break_and_retest | put | D | skipped_d | 28.59 | 28.62 | loss | - |
| 2026-07-09 | 09:50:00 | BABA | break_and_retest | put | D | skipped_d | 108.78 | 108.80 | loss | - |
| 2026-07-09 | 09:53:00 | AAPL | break_and_retest | call | D | skipped_d | 312.47 | 312.39 | loss | - |
| 2026-07-09 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 114.19 | 114.22 | loss | - |
| 2026-07-09 | 09:56:00 | PLTR | break_and_retest | call | D | skipped_d | 130.96 | 130.90 | loss | - |
| 2026-07-09 | 09:57:00 | AMD | one_candle_rule | put | D | skipped_d | 527.52 | 529.02 | loss | - |
| 2026-07-09 | 09:58:00 | META | one_candle_rule | put | B | fired | 605.12 | 605.72 | loss | $-1000 |
| 2026-07-09 | 09:59:00 | SPY | one_candle_rule | call | D | skipped_d | 746.80 | 746.73 | loss | - |
| 2026-07-09 | 10:01:00 | UBER | break_and_retest | put | D | skipped_d | 73.47 | 73.50 | loss | - |
| 2026-07-09 | 10:04:00 | MU | break_and_retest | put | D | skipped_d | 980.61 | 982.04 | loss | - |
| 2026-07-09 | 10:05:00 | INTC | break_and_retest | put | D | skipped_d | 113.80 | 113.86 | loss | - |
| 2026-07-09 | 10:07:00 | MSFT | break_and_retest | call | D | skipped_d | 381.49 | 381.43 | loss | - |
| 2026-07-09 | 10:07:00 | CRM | one_candle_rule | call | D | skipped_d | 162.29 | 162.20 | loss | - |
| 2026-07-09 | 10:10:00 | SOFI | break_and_retest | put | D | skipped_d | 17.80 | 17.81 | loss | - |
| 2026-07-09 | 10:12:00 | QQQ | one_candle_rule | put | D | skipped_d | 715.99 | 716.13 | loss | - |
| 2026-07-09 | 10:14:00 | BABA | break_and_retest | call | D | skipped_d | 109.35 | 109.34 | loss | - |
| 2026-07-09 | 10:17:00 | META | break_and_retest | put | D | skipped_d | 606.40 | 606.81 | win | - |
| 2026-07-09 | 10:20:00 | TSLA | break_and_retest | put | D | skipped_d | 396.02 | 396.10 | loss | - |
| 2026-07-09 | 10:21:00 | COIN | break_and_retest | put | D | skipped_d | 160.27 | 160.50 | loss | - |
| 2026-07-09 | 10:22:00 | MSFT | break_and_retest | put | D | skipped_d | 380.10 | 380.60 | loss | - |
| 2026-07-09 | 10:22:00 | PLTR | break_and_retest | put | D | skipped_d | 130.12 | 130.26 | loss | - |
| 2026-07-09 | 10:22:00 | SPY | break_and_retest | call | D | skipped_d | 747.02 | 746.96 | loss | - |
| 2026-07-09 | 10:22:00 | HOOD | break_and_retest | call | D | skipped_d | 114.58 | 114.57 | loss | - |
| 2026-07-09 | 10:23:00 | QQQ | break_and_retest | call | D | skipped_d | 716.22 | 716.20 | loss | - |
| 2026-07-09 | 10:24:00 | INTC | break_and_retest | call | D | skipped_d | 114.11 | 114.10 | loss | - |
| 2026-07-09 | 10:30:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.77 | 360.14 | loss | - |
| 2026-07-09 | 10:30:00 | QQQ | break_and_retest | put | D | skipped_d | 715.73 | 715.80 | loss | - |
| 2026-07-09 | 10:32:00 | AMZN | break_and_retest | put | D | skipped_d | 242.76 | 242.98 | loss | - |
| 2026-07-09 | 10:33:00 | AVGO | break_and_retest | call | D | skipped_d | 395.46 | 394.84 | loss | - |
| 2026-07-09 | 10:34:00 | SPY | break_and_retest | put | D | skipped_d | 746.55 | 746.60 | loss | - |
| 2026-07-09 | 10:34:00 | SMCI | break_and_retest | call | D | skipped_d | 28.75 | 28.72 | loss | - |
| 2026-07-09 | 10:35:00 | IREN | break_and_retest | call | D | skipped_d | 44.26 | 44.22 | loss | - |
| 2026-07-09 | 10:46:00 | HOOD | break_and_retest | put | B | fired | 114.02 | 114.22 | loss | $-1000 |
| 2026-07-09 | 10:49:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.66 | 359.75 | win | - |
| 2026-07-09 | 10:53:00 | NFLX | break_and_retest | put | D | skipped_d | 75.03 | 75.14 | loss | - |
| 2026-07-09 | 10:58:00 | AMD | one_candle_rule | put | C | fired | 525.20 | 527.05 | loss | - |
| 2026-07-09 | 10:59:00 | SOFI | break_and_retest | put | D | skipped_d | 17.66 | 17.73 | loss | - |
| 2026-07-10 | 09:38:00 | TSLA | break_and_retest | call | D | skipped_d | 404.25 | 403.96 | win | - |
| 2026-07-10 | 09:40:00 | AMZN | break_and_retest | put | D | skipped_d | 247.65 | 247.79 | loss | - |
| 2026-07-10 | 09:41:00 | MU | break_and_retest | call | D | skipped_d | 973.45 | 973.00 | win | - |
| 2026-07-10 | 09:42:00 | PLTR | break_and_retest | put | D | skipped_d | 130.29 | 130.30 | loss | - |
| 2026-07-10 | 09:43:00 | BABA | break_and_retest | call | D | skipped_d | 113.40 | 113.40 | win | - |
| 2026-07-10 | 09:44:00 | MSTR | break_and_retest | call | D | skipped_d | 98.66 | 98.60 | loss | - |
| 2026-07-10 | 09:45:00 | MARA | break_and_retest | call | D | skipped_d | 13.53 | 13.53 | win | - |
| 2026-07-10 | 09:46:00 | COIN | break_and_retest | call | D | skipped_d | 162.96 | 162.92 | loss | - |
| 2026-07-10 | 09:46:00 | SMCI | break_and_retest | call | D | skipped_d | 28.30 | 28.26 | loss | - |
| 2026-07-10 | 09:47:00 | AMD | break_and_retest | call | D | skipped_d | 544.44 | 544.00 | loss | - |
| 2026-07-10 | 09:48:00 | SPY | break_and_retest | put | D | skipped_d | 750.90 | 750.95 | loss | - |
| 2026-07-10 | 09:51:00 | GOOGL | break_and_retest | put | D | skipped_d | 358.22 | 358.27 | loss | - |
| 2026-07-10 | 09:52:00 | INTC | break_and_retest | put | D | skipped_d | 108.87 | 109.08 | loss | - |
| 2026-07-10 | 09:54:00 | SMCI | break_and_retest | put | D | skipped_d | 28.16 | 28.18 | loss | - |
| 2026-07-10 | 09:57:00 | AAPL | break_and_retest | put | D | skipped_d | 315.01 | 315.23 | loss | - |
| 2026-07-10 | 09:59:00 | RIVN | break_and_retest | put | D | skipped_d | 18.11 | 18.15 | loss | - |
| 2026-07-10 | 10:01:00 | NFLX | break_and_retest | put | D | skipped_d | 76.04 | 76.10 | loss | - |
| 2026-07-10 | 10:01:00 | MARA | break_and_retest | put | D | skipped_d | 13.52 | 13.53 | loss | - |
| 2026-07-10 | 10:02:00 | AAPL | break_and_retest | call | D | skipped_d | 315.31 | 315.02 | loss | - |
| 2026-07-10 | 10:06:00 | ORCL | break_and_retest | call | D | skipped_d | 146.44 | 146.29 | loss | - |
| 2026-07-10 | 10:08:00 | TSM | break_and_retest | call | D | skipped_d | 439.19 | 438.81 | loss | - |
| 2026-07-10 | 10:10:00 | SOFI | break_and_retest | call | D | skipped_d | 18.69 | 18.68 | win | - |
| 2026-07-10 | 10:11:00 | PLTR | one_candle_rule | call | D | skipped_d | 130.06 | 129.85 | loss | - |
| 2026-07-10 | 10:11:00 | AVGO | break_and_retest | put | D | skipped_d | 397.23 | 397.57 | loss | - |
| 2026-07-10 | 10:12:00 | GOOGL | break_and_retest | call | D | skipped_d | 358.96 | 358.87 | loss | - |
| 2026-07-10 | 10:13:00 | AMZN | break_and_retest | call | D | skipped_d | 248.20 | 248.15 | loss | - |
| 2026-07-10 | 10:15:00 | MSTR | break_and_retest | call | D | skipped_d | 98.35 | 98.30 | loss | - |
| 2026-07-10 | 10:24:00 | UBER | break_and_retest | put | D | skipped_d | 74.62 | 74.63 | win | - |
| 2026-07-10 | 10:26:00 | QQQ | break_and_retest | call | D | skipped_d | 720.54 | 720.50 | win | - |
| 2026-07-10 | 10:26:00 | SOFI | break_and_retest | call | D | skipped_d | 18.72 | 18.70 | win | - |
| 2026-07-10 | 10:27:00 | SPY | one_candle_rule | put | D | skipped_d | 751.36 | 751.40 | loss | - |
| 2026-07-10 | 10:28:00 | MU | break_and_retest | call | D | skipped_d | 973.54 | 973.00 | win | - |
| 2026-07-10 | 10:29:00 | MSTR | break_and_retest | call | D | skipped_d | 98.90 | 98.60 | win | - |
| 2026-07-10 | 10:33:00 | PLTR | break_and_retest | put | D | skipped_d | 130.18 | 130.30 | loss | - |
| 2026-07-10 | 10:35:00 | QQQ | one_candle_rule | call | D | skipped_d | 721.15 | 720.99 | loss | - |
| 2026-07-10 | 10:39:00 | UBER | break_and_retest | call | D | skipped_d | 74.66 | 74.66 | loss | - |
| 2026-07-10 | 10:40:00 | MARA | break_and_retest | call | D | skipped_d | 13.54 | 13.53 | loss | - |
| 2026-07-10 | 10:42:00 | IREN | one_candle_rule | call | D | skipped_d | 42.40 | 42.38 | loss | - |
| 2026-07-10 | 10:43:00 | TSM | break_and_retest | call | D | skipped_d | 438.88 | 438.81 | loss | - |
| 2026-07-10 | 10:48:00 | SPY | break_and_retest | call | D | skipped_d | 751.72 | 751.71 | loss | - |
| 2026-07-10 | 10:48:00 | NFLX | break_and_retest | put | D | skipped_d | 76.00 | 76.10 | win | - |
| 2026-07-10 | 10:49:00 | IREN | one_candle_rule | put | D | skipped_d | 42.39 | 42.46 | loss | - |
| 2026-07-10 | 10:56:00 | MSFT | break_and_retest | put | D | skipped_d | 387.90 | 388.01 | win | - |
| 2026-07-10 | 10:59:00 | AVGO | break_and_retest | put | D | skipped_d | 397.55 | 397.57 | loss | - |

## Findings & Recommendations
- A+/A win rate 0% vs B/C 0% -> KEEP grading
- D-grade filter: filtered signals would have won 16% -> filter justified (<50%)
- 84% live wiring: armed per-symbol off paper stop-outs in live_scanner (2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.
- Best setup: one_candle_rule (0%) | worst: break_and_retest (0%)
- C-grade alerts (2, alert-only per SPEC2) would have won 0% - similar to traded grades; alert-only demotion costs little.


## Rule 6 Report

# Backtest Report: Week of 2026-07-06 to 2026-07-10

## Assumptions
- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals
- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close
- Stop+target same bar counted as loss (conservative)
- Repeat fires of same setup within 30 min deduped

## Summary
- Traded signals (A+/A/B, viable stop): **5** | 0W 5L 0 scratch | win rate 0.0% (of decided)
- Simulated P&L (traded all A+/A/B): **$-5000.0**
- C-grade alerts (alert-only per SPEC2): 2 | D filtered: 206 | tight-stop skips: 0

### By Grade
| Grade | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| A+ | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| B | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| C (alert only) | 2 | 0 | 2 | 0 | 0.0% | ($-2000.0 if traded) |
| D (filtered) | 206 | 19 | 187 | 0 | 9.2% | ($-62500.0 if traded) |

### By Setup
| Setup | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| break_and_retest | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| one_candle_rule | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### By Symbol
| Symbol | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| CRM | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| GOOGL | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| HOOD | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| META | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| TSM | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### By Entry Hour
| Hour | Signals | W | L | Scratch | Win rate | P&L |
|------|---------|---|---|---------|----------|-----|
| 09:30-10:00 | 4 | 0 | 4 | 0 | 0.0% | $-4000.0 |
| 10:30-11:00 | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

### B&R: clean first break vs late (level broken earlier)
| Bucket | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| clean | 3 | 0 | 3 | 0 | 0.0% | $-3000.0 |
| late | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |

## By Day
| Day | Signals | Wins | Losses | Scratch | P&L |
|-----|---------|------|--------|---------|-----|
| 2026-07-06 | 1 | 0 | 1 | 0 | $-1000.0 |
| 2026-07-07 | 1 | 0 | 1 | 0 | $-1000.0 |
| 2026-07-08 | 0 | 0 | 0 | 0 | $0 |
| 2026-07-09 | 3 | 0 | 3 | 0 | $-3000.0 |
| 2026-07-10 | 0 | 0 | 0 | 0 | $0 |

## 84% Rule Analysis
- Total triggers (incl. filtered): 0
- Fired re-entry signals: 0
- Win rate on re-entry: 0.0% | P&L $0

## Signal Log
| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |
|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|
| 2026-07-06 | 09:44:00 | GOOGL | one_candle_rule | call | D | skipped_d | 361.08 | 360.84 | loss | - |
| 2026-07-06 | 09:45:00 | COIN | break_and_retest | put | D | skipped_d | 168.60 | 168.70 | win | - |
| 2026-07-06 | 09:45:00 | NFLX | break_and_retest | put | D | skipped_d | 77.59 | 77.70 | loss | - |
| 2026-07-06 | 09:50:00 | INTC | one_candle_rule | put | D | skipped_d | 123.92 | 124.18 | loss | - |
| 2026-07-06 | 09:52:00 | CRM | break_and_retest | call | B | fired | 166.80 | 166.30 | loss | $-1000 |
| 2026-07-06 | 09:53:00 | SMCI | break_and_retest | call | D | skipped_d | 27.81 | 27.77 | loss | - |
| 2026-07-06 | 09:54:00 | ORCL | one_candle_rule | call | D | skipped_d | 145.42 | 145.18 | loss | - |
| 2026-07-06 | 09:54:00 | HOOD | one_candle_rule | call | D | skipped_d | 113.98 | 113.83 | win | - |
| 2026-07-06 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 113.98 | 114.00 | loss | - |
| 2026-07-06 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 113.98 | 114.04 | loss | - |
| 2026-07-06 | 10:00:00 | AMD | break_and_retest | call | D | skipped_d | 532.51 | 530.99 | loss | - |
| 2026-07-06 | 10:03:00 | TSLA | break_and_retest | call | D | skipped_d | 399.82 | 399.77 | loss | - |
| 2026-07-06 | 10:03:00 | TSLA | break_and_retest | call | D | skipped_d | 399.82 | 399.75 | loss | - |
| 2026-07-06 | 10:03:00 | AMZN | break_and_retest | call | D | skipped_d | 246.22 | 245.95 | loss | - |
| 2026-07-06 | 10:03:00 | INTC | break_and_retest | call | D | skipped_d | 124.46 | 124.39 | loss | - |
| 2026-07-06 | 10:04:00 | CRM | break_and_retest | call | D | skipped_d | 166.40 | 166.39 | win | - |
| 2026-07-06 | 10:06:00 | PLTR | break_and_retest | call | D | skipped_d | 129.98 | 129.94 | loss | - |
| 2026-07-06 | 10:08:00 | COIN | break_and_retest | call | D | skipped_d | 169.00 | 168.93 | loss | - |
| 2026-07-06 | 10:09:00 | AVGO | break_and_retest | call | D | skipped_d | 367.40 | 367.25 | loss | - |
| 2026-07-06 | 10:10:00 | BABA | break_and_retest | put | D | skipped_d | 97.51 | 97.52 | loss | - |
| 2026-07-06 | 10:12:00 | AVGO | break_and_retest | call | D | skipped_d | 367.22 | 367.19 | loss | - |
| 2026-07-06 | 10:12:00 | MU | break_and_retest | put | D | skipped_d | 997.51 | 998.00 | loss | - |
| 2026-07-06 | 10:13:00 | HOOD | break_and_retest | call | D | skipped_d | 114.46 | 114.41 | loss | - |
| 2026-07-06 | 10:14:00 | NFLX | break_and_retest | call | D | skipped_d | 78.00 | 77.89 | loss | - |
| 2026-07-06 | 10:15:00 | AAPL | one_candle_rule | put | D | skipped_d | 305.60 | 305.80 | loss | - |
| 2026-07-06 | 10:25:00 | ORCL | break_and_retest | put | D | skipped_d | 145.05 | 145.10 | loss | - |
| 2026-07-06 | 10:32:00 | SPY | break_and_retest | call | D | skipped_d | 748.54 | 748.48 | win | - |
| 2026-07-06 | 10:37:00 | RIVN | one_candle_rule | call | D | skipped_d | 18.77 | 18.74 | loss | - |
| 2026-07-06 | 10:40:00 | TSM | break_and_retest | call | D | skipped_d | 445.95 | 445.76 | loss | - |
| 2026-07-06 | 10:42:00 | MARA | break_and_retest | call | D | skipped_d | 12.66 | 12.66 | loss | - |
| 2026-07-06 | 10:43:00 | IREN | break_and_retest | put | D | skipped_d | 41.18 | 41.25 | loss | - |
| 2026-07-06 | 10:51:00 | META | break_and_retest | put | D | skipped_d | 591.68 | 592.24 | loss | - |
| 2026-07-06 | 10:53:00 | HOOD | break_and_retest | put | D | skipped_d | 114.01 | 114.04 | loss | - |
| 2026-07-07 | 09:36:00 | AMD | break_and_retest | put | D | skipped_d | 527.80 | 528.60 | loss | - |
| 2026-07-07 | 09:38:00 | NVDA | break_and_retest | put | D | skipped_d | 193.75 | 193.80 | loss | - |
| 2026-07-07 | 09:40:00 | AVGO | break_and_retest | put | D | skipped_d | 365.86 | 366.50 | loss | - |
| 2026-07-07 | 09:41:00 | SMCI | break_and_retest | put | D | skipped_d | 26.70 | 26.71 | loss | - |
| 2026-07-07 | 09:42:00 | CRM | one_candle_rule | call | D | skipped_d | 168.70 | 168.33 | loss | - |
| 2026-07-07 | 09:43:00 | BABA | break_and_retest | call | D | skipped_d | 97.95 | 97.84 | loss | - |
| 2026-07-07 | 09:44:00 | GOOGL | break_and_retest | call | A+ | fired | 370.25 | 369.37 | loss | $-1000 |
| 2026-07-07 | 09:44:00 | GOOGL | break_and_retest | call | C | fired | 370.25 | 369.46 | loss | - |
| 2026-07-07 | 09:45:00 | TSLA | break_and_retest | call | D | skipped_d | 414.83 | 414.74 | loss | - |
| 2026-07-07 | 09:45:00 | TSLA | break_and_retest | call | D | skipped_d | 414.83 | 414.64 | loss | - |
| 2026-07-07 | 09:47:00 | CRM | break_and_retest | call | D | skipped_d | 168.75 | 168.63 | loss | - |
| 2026-07-07 | 09:47:00 | CRM | break_and_retest | call | D | skipped_d | 168.75 | 168.63 | loss | - |
| 2026-07-07 | 09:48:00 | SOFI | break_and_retest | call | D | skipped_d | 18.82 | 18.80 | loss | - |
| 2026-07-07 | 09:49:00 | INTC | break_and_retest | put | D | skipped_d | 116.30 | 116.33 | loss | - |
| 2026-07-07 | 09:51:00 | SPY | break_and_retest | call | D | skipped_d | 750.32 | 750.24 | loss | - |
| 2026-07-07 | 09:55:00 | PLTR | break_and_retest | call | D | skipped_d | 134.55 | 134.49 | loss | - |
| 2026-07-07 | 09:56:00 | AVGO | break_and_retest | put | D | skipped_d | 364.59 | 365.50 | loss | - |
| 2026-07-07 | 09:56:00 | AVGO | break_and_retest | put | D | skipped_d | 364.59 | 365.62 | loss | - |
| 2026-07-07 | 09:57:00 | SOFI | break_and_retest | call | D | skipped_d | 18.83 | 18.82 | loss | - |
| 2026-07-07 | 09:58:00 | MSFT | break_and_retest | put | D | skipped_d | 392.65 | 392.83 | loss | - |
| 2026-07-07 | 10:01:00 | AMZN | one_candle_rule | put | D | skipped_d | 247.79 | 248.10 | win | - |
| 2026-07-07 | 10:02:00 | NVDA | break_and_retest | call | D | skipped_d | 194.05 | 194.02 | loss | - |
| 2026-07-07 | 10:02:00 | AAPL | one_candle_rule | put | D | skipped_d | 314.52 | 314.77 | loss | - |
| 2026-07-07 | 10:04:00 | SMCI | break_and_retest | call | D | skipped_d | 26.79 | 26.78 | loss | - |
| 2026-07-07 | 10:05:00 | AMZN | one_candle_rule | put | D | skipped_d | 247.62 | 247.66 | loss | - |
| 2026-07-07 | 10:06:00 | TSLA | one_candle_rule | call | D | skipped_d | 415.99 | 415.52 | loss | - |
| 2026-07-07 | 10:08:00 | IREN | break_and_retest | call | D | skipped_d | 43.14 | 43.11 | loss | - |
| 2026-07-07 | 10:09:00 | INTC | break_and_retest | put | D | skipped_d | 116.68 | 116.80 | loss | - |
| 2026-07-07 | 10:10:00 | TSM | break_and_retest | call | D | skipped_d | 443.75 | 443.18 | loss | - |
| 2026-07-07 | 10:11:00 | RIVN | one_candle_rule | call | D | skipped_d | 18.47 | 18.41 | loss | - |
| 2026-07-07 | 10:12:00 | AAPL | break_and_retest | call | D | skipped_d | 314.90 | 314.79 | loss | - |
| 2026-07-07 | 10:13:00 | UBER | break_and_retest | call | D | skipped_d | 72.99 | 72.91 | loss | - |
| 2026-07-07 | 10:16:00 | MSFT | one_candle_rule | put | D | skipped_d | 391.88 | 392.17 | loss | - |
| 2026-07-07 | 10:19:00 | ORCL | break_and_retest | call | D | skipped_d | 145.98 | 145.71 | loss | - |
| 2026-07-07 | 10:19:00 | BABA | break_and_retest | put | D | skipped_d | 97.14 | 97.30 | loss | - |
| 2026-07-07 | 10:21:00 | ORCL | break_and_retest | call | D | skipped_d | 145.87 | 145.79 | loss | - |
| 2026-07-07 | 10:22:00 | MARA | break_and_retest | call | D | skipped_d | 12.90 | 12.88 | loss | - |
| 2026-07-07 | 10:25:00 | SOFI | break_and_retest | put | D | skipped_d | 18.71 | 18.77 | loss | - |
| 2026-07-07 | 10:26:00 | SPY | break_and_retest | call | D | skipped_d | 750.43 | 750.24 | loss | - |
| 2026-07-07 | 10:27:00 | MSFT | one_candle_rule | put | D | skipped_d | 392.46 | 392.83 | loss | - |
| 2026-07-07 | 10:30:00 | GOOGL | break_and_retest | put | D | skipped_d | 368.22 | 368.57 | loss | - |
| 2026-07-07 | 10:31:00 | NFLX | break_and_retest | put | D | skipped_d | 76.70 | 76.78 | loss | - |
| 2026-07-07 | 10:32:00 | AMZN | break_and_retest | call | D | skipped_d | 247.64 | 247.52 | loss | - |
| 2026-07-07 | 10:34:00 | HOOD | break_and_retest | put | D | skipped_d | 116.50 | 116.63 | loss | - |
| 2026-07-07 | 10:38:00 | IREN | one_candle_rule | call | D | skipped_d | 43.13 | 43.05 | loss | - |
| 2026-07-07 | 10:44:00 | META | one_candle_rule | call | D | skipped_d | 605.06 | 604.95 | loss | - |
| 2026-07-07 | 10:44:00 | PLTR | break_and_retest | call | D | skipped_d | 134.49 | 134.49 | loss | - |
| 2026-07-07 | 10:44:00 | SPY | break_and_retest | put | D | skipped_d | 750.06 | 750.07 | loss | - |
| 2026-07-07 | 10:45:00 | RIVN | break_and_retest | put | D | skipped_d | 18.40 | 18.41 | loss | - |
| 2026-07-07 | 10:50:00 | AMD | break_and_retest | call | D | skipped_d | 529.51 | 529.47 | loss | - |
| 2026-07-07 | 10:50:00 | CRM | break_and_retest | put | D | skipped_d | 168.20 | 168.33 | loss | - |
| 2026-07-07 | 10:56:00 | IREN | one_candle_rule | put | D | skipped_d | 42.99 | 43.08 | loss | - |
| 2026-07-07 | 10:57:00 | MSTR | break_and_retest | call | D | skipped_d | 100.61 | 100.49 | loss | - |
| 2026-07-07 | 10:59:00 | PLTR | break_and_retest | put | D | skipped_d | 134.22 | 134.31 | loss | - |
| 2026-07-08 | 09:38:00 | IREN | break_and_retest | call | D | skipped_d | 38.76 | 38.75 | loss | - |
| 2026-07-08 | 09:38:00 | MU | break_and_retest | call | D | skipped_d | 886.50 | 885.50 | loss | - |
| 2026-07-08 | 09:41:00 | HOOD | one_candle_rule | call | D | skipped_d | 107.79 | 107.21 | loss | - |
| 2026-07-08 | 09:50:00 | AMZN | break_and_retest | call | D | skipped_d | 242.51 | 242.40 | loss | - |
| 2026-07-08 | 09:51:00 | AVGO | break_and_retest | call | D | skipped_d | 362.98 | 362.70 | loss | - |
| 2026-07-08 | 09:52:00 | NFLX | one_candle_rule | put | D | skipped_d | 76.67 | 76.75 | loss | - |
| 2026-07-08 | 09:55:00 | COIN | one_candle_rule | call | D | skipped_d | 158.07 | 157.80 | loss | - |
| 2026-07-08 | 10:00:00 | CRM | one_candle_rule | put | D | skipped_d | 165.61 | 166.03 | loss | - |
| 2026-07-08 | 10:01:00 | RIVN | break_and_retest | call | D | skipped_d | 15.76 | 15.75 | loss | - |
| 2026-07-08 | 10:04:00 | NFLX | break_and_retest | put | D | skipped_d | 76.45 | 76.55 | loss | - |
| 2026-07-08 | 10:08:00 | PLTR | one_candle_rule | put | D | skipped_d | 129.68 | 130.08 | loss | - |
| 2026-07-08 | 10:09:00 | SPY | break_and_retest | put | D | skipped_d | 739.77 | 739.84 | win | - |
| 2026-07-08 | 10:11:00 | TSLA | break_and_retest | put | D | skipped_d | 396.71 | 397.00 | loss | - |
| 2026-07-08 | 10:12:00 | TSM | one_candle_rule | call | D | skipped_d | 427.43 | 426.66 | win | - |
| 2026-07-08 | 10:22:00 | PLTR | one_candle_rule | call | D | skipped_d | 130.04 | 129.72 | win | - |
| 2026-07-08 | 10:22:00 | INTC | break_and_retest | call | D | skipped_d | 105.70 | 105.58 | loss | - |
| 2026-07-08 | 10:23:00 | SMCI | one_candle_rule | call | D | skipped_d | 25.77 | 25.75 | loss | - |
| 2026-07-08 | 10:27:00 | AMD | break_and_retest | call | D | skipped_d | 506.93 | 505.00 | loss | - |
| 2026-07-08 | 10:27:00 | MSFT | break_and_retest | put | D | skipped_d | 382.15 | 382.40 | loss | - |
| 2026-07-08 | 10:31:00 | SPY | break_and_retest | call | D | skipped_d | 740.80 | 740.44 | loss | - |
| 2026-07-08 | 10:31:00 | CRM | break_and_retest | call | D | skipped_d | 166.00 | 165.89 | loss | - |
| 2026-07-08 | 10:36:00 | TSLA | one_candle_rule | call | D | skipped_d | 398.11 | 397.81 | loss | - |
| 2026-07-08 | 10:38:00 | GOOGL | break_and_retest | call | D | skipped_d | 362.66 | 362.45 | loss | - |
| 2026-07-08 | 10:39:00 | META | break_and_retest | call | D | skipped_d | 606.12 | 605.65 | loss | - |
| 2026-07-08 | 10:39:00 | PLTR | break_and_retest | call | D | skipped_d | 130.53 | 130.37 | loss | - |
| 2026-07-08 | 10:39:00 | HOOD | break_and_retest | call | D | skipped_d | 108.49 | 108.16 | loss | - |
| 2026-07-08 | 10:40:00 | AMZN | break_and_retest | call | D | skipped_d | 242.68 | 242.40 | loss | - |
| 2026-07-08 | 10:41:00 | RIVN | break_and_retest | call | D | skipped_d | 15.76 | 15.75 | win | - |
| 2026-07-08 | 10:42:00 | META | one_candle_rule | put | D | skipped_d | 606.08 | 607.00 | loss | - |
| 2026-07-08 | 10:45:00 | IREN | break_and_retest | put | D | skipped_d | 39.19 | 39.19 | loss | - |
| 2026-07-08 | 10:46:00 | AAPL | break_and_retest | put | D | skipped_d | 309.30 | 309.55 | loss | - |
| 2026-07-08 | 10:51:00 | MSTR | break_and_retest | call | D | skipped_d | 94.06 | 93.82 | loss | - |
| 2026-07-08 | 10:53:00 | SOFI | one_candle_rule | put | D | skipped_d | 17.33 | 17.35 | win | - |
| 2026-07-08 | 10:59:00 | COIN | break_and_retest | call | D | skipped_d | 158.63 | 158.45 | loss | - |
| 2026-07-09 | 09:37:00 | SMCI | break_and_retest | call | D | skipped_d | 28.65 | 28.63 | loss | - |
| 2026-07-09 | 09:38:00 | AMZN | break_and_retest | put | D | skipped_d | 242.91 | 242.98 | loss | - |
| 2026-07-09 | 09:40:00 | QQQ | break_and_retest | put | D | skipped_d | 715.78 | 715.80 | loss | - |
| 2026-07-09 | 09:40:00 | TSM | break_and_retest | put | B | fired | 440.33 | 441.02 | loss | $-1000 |
| 2026-07-09 | 09:42:00 | ORCL | break_and_retest | call | D | skipped_d | 142.90 | 142.80 | loss | - |
| 2026-07-09 | 09:42:00 | NFLX | break_and_retest | put | D | skipped_d | 75.15 | 75.25 | loss | - |
| 2026-07-09 | 09:44:00 | NVDA | one_candle_rule | put | D | skipped_d | 204.13 | 204.37 | loss | - |
| 2026-07-09 | 09:45:00 | AVGO | break_and_retest | put | D | skipped_d | 393.75 | 393.83 | loss | - |
| 2026-07-09 | 09:47:00 | GOOGL | break_and_retest | put | D | skipped_d | 360.05 | 360.14 | loss | - |
| 2026-07-09 | 09:48:00 | TSM | break_and_retest | call | D | skipped_d | 440.50 | 440.49 | loss | - |
| 2026-07-09 | 09:49:00 | GOOGL | break_and_retest | put | D | skipped_d | 360.21 | 360.27 | loss | - |
| 2026-07-09 | 09:49:00 | SMCI | break_and_retest | put | D | skipped_d | 28.59 | 28.62 | loss | - |
| 2026-07-09 | 09:50:00 | BABA | break_and_retest | put | D | skipped_d | 108.78 | 108.80 | loss | - |
| 2026-07-09 | 09:53:00 | AAPL | break_and_retest | call | D | skipped_d | 312.47 | 312.39 | loss | - |
| 2026-07-09 | 09:54:00 | HOOD | break_and_retest | put | D | skipped_d | 114.19 | 114.22 | loss | - |
| 2026-07-09 | 09:56:00 | PLTR | break_and_retest | call | D | skipped_d | 130.96 | 130.90 | loss | - |
| 2026-07-09 | 09:57:00 | AMD | one_candle_rule | put | D | skipped_d | 527.52 | 529.02 | loss | - |
| 2026-07-09 | 09:58:00 | META | one_candle_rule | put | B | fired | 605.12 | 605.72 | loss | $-1000 |
| 2026-07-09 | 09:59:00 | SPY | one_candle_rule | call | D | skipped_d | 746.80 | 746.73 | loss | - |
| 2026-07-09 | 10:01:00 | UBER | break_and_retest | put | D | skipped_d | 73.47 | 73.50 | loss | - |
| 2026-07-09 | 10:04:00 | MU | break_and_retest | put | D | skipped_d | 980.61 | 982.04 | loss | - |
| 2026-07-09 | 10:05:00 | INTC | break_and_retest | put | D | skipped_d | 113.80 | 113.86 | loss | - |
| 2026-07-09 | 10:07:00 | MSFT | break_and_retest | call | D | skipped_d | 381.49 | 381.43 | loss | - |
| 2026-07-09 | 10:07:00 | CRM | one_candle_rule | call | D | skipped_d | 162.29 | 162.20 | loss | - |
| 2026-07-09 | 10:10:00 | SOFI | break_and_retest | put | D | skipped_d | 17.80 | 17.81 | loss | - |
| 2026-07-09 | 10:12:00 | QQQ | one_candle_rule | put | D | skipped_d | 715.99 | 716.13 | loss | - |
| 2026-07-09 | 10:14:00 | BABA | break_and_retest | call | D | skipped_d | 109.35 | 109.34 | loss | - |
| 2026-07-09 | 10:17:00 | META | break_and_retest | put | D | skipped_d | 606.40 | 606.81 | win | - |
| 2026-07-09 | 10:20:00 | TSLA | break_and_retest | put | D | skipped_d | 396.02 | 396.10 | loss | - |
| 2026-07-09 | 10:21:00 | COIN | break_and_retest | put | D | skipped_d | 160.27 | 160.50 | loss | - |
| 2026-07-09 | 10:22:00 | MSFT | break_and_retest | put | D | skipped_d | 380.10 | 380.60 | loss | - |
| 2026-07-09 | 10:22:00 | PLTR | break_and_retest | put | D | skipped_d | 130.12 | 130.26 | loss | - |
| 2026-07-09 | 10:22:00 | SPY | break_and_retest | call | D | skipped_d | 747.02 | 746.96 | loss | - |
| 2026-07-09 | 10:22:00 | HOOD | break_and_retest | call | D | skipped_d | 114.58 | 114.57 | loss | - |
| 2026-07-09 | 10:23:00 | QQQ | break_and_retest | call | D | skipped_d | 716.22 | 716.20 | loss | - |
| 2026-07-09 | 10:24:00 | INTC | break_and_retest | call | D | skipped_d | 114.11 | 114.10 | loss | - |
| 2026-07-09 | 10:30:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.77 | 360.14 | loss | - |
| 2026-07-09 | 10:30:00 | QQQ | break_and_retest | put | D | skipped_d | 715.73 | 715.80 | loss | - |
| 2026-07-09 | 10:32:00 | AMZN | break_and_retest | put | D | skipped_d | 242.76 | 242.98 | loss | - |
| 2026-07-09 | 10:33:00 | AVGO | break_and_retest | call | D | skipped_d | 395.46 | 394.84 | loss | - |
| 2026-07-09 | 10:34:00 | SPY | break_and_retest | put | D | skipped_d | 746.55 | 746.60 | loss | - |
| 2026-07-09 | 10:34:00 | SMCI | break_and_retest | call | D | skipped_d | 28.75 | 28.72 | loss | - |
| 2026-07-09 | 10:35:00 | IREN | break_and_retest | call | D | skipped_d | 44.26 | 44.22 | loss | - |
| 2026-07-09 | 10:46:00 | HOOD | break_and_retest | put | B | fired | 114.02 | 114.22 | loss | $-1000 |
| 2026-07-09 | 10:49:00 | GOOGL | break_and_retest | put | D | skipped_d | 359.66 | 359.75 | win | - |
| 2026-07-09 | 10:53:00 | NFLX | break_and_retest | put | D | skipped_d | 75.03 | 75.14 | loss | - |
| 2026-07-09 | 10:58:00 | AMD | one_candle_rule | put | C | fired | 525.20 | 527.05 | loss | - |
| 2026-07-09 | 10:59:00 | SOFI | break_and_retest | put | D | skipped_d | 17.66 | 17.73 | loss | - |
| 2026-07-10 | 09:38:00 | TSLA | break_and_retest | call | D | skipped_d | 404.25 | 403.96 | loss | - |
| 2026-07-10 | 09:40:00 | AMZN | break_and_retest | put | D | skipped_d | 247.65 | 247.79 | loss | - |
| 2026-07-10 | 09:41:00 | MU | break_and_retest | call | D | skipped_d | 973.45 | 973.00 | loss | - |
| 2026-07-10 | 09:42:00 | PLTR | break_and_retest | put | D | skipped_d | 130.29 | 130.30 | loss | - |
| 2026-07-10 | 09:43:00 | BABA | break_and_retest | call | D | skipped_d | 113.40 | 113.40 | win | - |
| 2026-07-10 | 09:44:00 | MSTR | break_and_retest | call | D | skipped_d | 98.66 | 98.60 | loss | - |
| 2026-07-10 | 09:45:00 | MARA | break_and_retest | call | D | skipped_d | 13.53 | 13.53 | win | - |
| 2026-07-10 | 09:46:00 | COIN | break_and_retest | call | D | skipped_d | 162.96 | 162.92 | loss | - |
| 2026-07-10 | 09:46:00 | SMCI | break_and_retest | call | D | skipped_d | 28.30 | 28.26 | loss | - |
| 2026-07-10 | 09:47:00 | AMD | break_and_retest | call | D | skipped_d | 544.44 | 544.00 | loss | - |
| 2026-07-10 | 09:48:00 | SPY | break_and_retest | put | D | skipped_d | 750.90 | 750.95 | loss | - |
| 2026-07-10 | 09:51:00 | GOOGL | break_and_retest | put | D | skipped_d | 358.22 | 358.27 | loss | - |
| 2026-07-10 | 09:52:00 | INTC | break_and_retest | put | D | skipped_d | 108.87 | 109.08 | loss | - |
| 2026-07-10 | 09:54:00 | SMCI | break_and_retest | put | D | skipped_d | 28.16 | 28.18 | loss | - |
| 2026-07-10 | 09:57:00 | AAPL | break_and_retest | put | D | skipped_d | 315.01 | 315.23 | loss | - |
| 2026-07-10 | 09:59:00 | RIVN | break_and_retest | put | D | skipped_d | 18.11 | 18.15 | loss | - |
| 2026-07-10 | 10:01:00 | NFLX | break_and_retest | put | D | skipped_d | 76.04 | 76.10 | loss | - |
| 2026-07-10 | 10:01:00 | MARA | break_and_retest | put | D | skipped_d | 13.52 | 13.53 | loss | - |
| 2026-07-10 | 10:02:00 | AAPL | break_and_retest | call | D | skipped_d | 315.31 | 315.02 | loss | - |
| 2026-07-10 | 10:06:00 | ORCL | break_and_retest | call | D | skipped_d | 146.44 | 146.29 | loss | - |
| 2026-07-10 | 10:08:00 | TSM | break_and_retest | call | D | skipped_d | 439.19 | 438.81 | loss | - |
| 2026-07-10 | 10:10:00 | SOFI | break_and_retest | call | D | skipped_d | 18.69 | 18.68 | loss | - |
| 2026-07-10 | 10:11:00 | PLTR | one_candle_rule | call | D | skipped_d | 130.06 | 129.85 | loss | - |
| 2026-07-10 | 10:11:00 | AVGO | break_and_retest | put | D | skipped_d | 397.23 | 397.57 | loss | - |
| 2026-07-10 | 10:12:00 | GOOGL | break_and_retest | call | D | skipped_d | 358.96 | 358.87 | loss | - |
| 2026-07-10 | 10:13:00 | AMZN | break_and_retest | call | D | skipped_d | 248.20 | 248.15 | loss | - |
| 2026-07-10 | 10:15:00 | MSTR | break_and_retest | call | D | skipped_d | 98.35 | 98.30 | loss | - |
| 2026-07-10 | 10:24:00 | UBER | break_and_retest | put | D | skipped_d | 74.62 | 74.63 | win | - |
| 2026-07-10 | 10:26:00 | QQQ | break_and_retest | call | D | skipped_d | 720.54 | 720.50 | win | - |
| 2026-07-10 | 10:26:00 | SOFI | break_and_retest | call | D | skipped_d | 18.72 | 18.70 | win | - |
| 2026-07-10 | 10:27:00 | SPY | one_candle_rule | put | D | skipped_d | 751.36 | 751.40 | loss | - |
| 2026-07-10 | 10:28:00 | MU | break_and_retest | call | D | skipped_d | 973.54 | 973.00 | loss | - |
| 2026-07-10 | 10:29:00 | MSTR | break_and_retest | call | D | skipped_d | 98.90 | 98.60 | win | - |
| 2026-07-10 | 10:33:00 | PLTR | break_and_retest | put | D | skipped_d | 130.18 | 130.30 | loss | - |
| 2026-07-10 | 10:35:00 | QQQ | one_candle_rule | call | D | skipped_d | 721.15 | 720.99 | loss | - |
| 2026-07-10 | 10:39:00 | UBER | break_and_retest | call | D | skipped_d | 74.66 | 74.66 | loss | - |
| 2026-07-10 | 10:40:00 | MARA | break_and_retest | call | D | skipped_d | 13.54 | 13.53 | loss | - |
| 2026-07-10 | 10:42:00 | IREN | one_candle_rule | call | D | skipped_d | 42.40 | 42.38 | loss | - |
| 2026-07-10 | 10:43:00 | TSM | break_and_retest | call | D | skipped_d | 438.88 | 438.81 | loss | - |
| 2026-07-10 | 10:48:00 | SPY | break_and_retest | call | D | skipped_d | 751.72 | 751.71 | loss | - |
| 2026-07-10 | 10:48:00 | NFLX | break_and_retest | put | D | skipped_d | 76.00 | 76.10 | loss | - |
| 2026-07-10 | 10:49:00 | IREN | one_candle_rule | put | D | skipped_d | 42.39 | 42.46 | loss | - |
| 2026-07-10 | 10:56:00 | MSFT | break_and_retest | put | D | skipped_d | 387.90 | 388.01 | win | - |
| 2026-07-10 | 10:59:00 | AVGO | break_and_retest | put | D | skipped_d | 397.55 | 397.57 | loss | - |

## Findings & Recommendations
- A+/A win rate 0% vs B/C 0% -> KEEP grading
- D-grade filter: filtered signals would have won 9% -> filter justified (<50%)
- 84% live wiring: armed per-symbol off paper stop-outs in live_scanner (2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.
- Best setup: one_candle_rule (0%) | worst: break_and_retest (0%)
- C-grade alerts (2, alert-only per SPEC2) would have won 0% - similar to traded grades; alert-only demotion costs little.
