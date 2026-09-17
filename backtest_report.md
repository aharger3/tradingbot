# Backtest Report: Week of 2026-09-14 to 2026-09-15

## Assumptions
- Data: yfinance 1-min RTH bars; walk-forward replay through SignalRunner.detect_signals
- $1000 risk per trade, 2R target -> win +$2000, loss -$1000, scratch = R x $1000 at EOD close
- Stop+target same bar counted as loss (conservative)
- Repeat fires of same setup deduped by level (2 bars)

## Summary
- Traded signals (A+/A/B, viable stop): **25** | 10W 15L 0 scratch | win rate 40.0% (of decided)
- Simulated P&L (traded all A+/A/B): **$-5528.11**
- C-grade alerts (alert-only per SPEC2): 12 | D filtered: 462 | tight-stop skips: 20

### By Grade
| Grade | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| B | 25 | 10 | 15 | 0 | 40.0% | $-5528.11 |
| C (alert only) | 12 | 2 | 8 | 2 | 20.0% | ($-2175.41 if traded) |
| D (filtered) | 462 | 72 | 385 | 5 | 15.8% | ($9181286.54 if traded) |

### By Setup
| Setup | Signals | W | L | Scratch | Win rate | P&L |
|-------|---------|---|---|---------|----------|-----|
| break_and_retest | 22 | 9 | 13 | 0 | 40.9% | $-4826.35 |
| one_candle_rule | 1 | 1 | 0 | 0 | 100.0% | $1298.24 |
| reentry_84_rule | 2 | 0 | 2 | 0 | 0.0% | $-2000.0 |

### By Symbol
| Symbol | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| AMD _(low n)_ | 1 | 1 | 0 | 0 | 100.0% | $889.11 |
| AMZN _(low n)_ | 1 | 1 | 0 | 0 | 100.0% | $847.56 |
| AVGO _(low n)_ | 3 | 3 | 0 | 0 | 100.0% | $2359.21 |
| BABA _(low n)_ | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| COIN _(low n)_ | 1 | 1 | 0 | 0 | 100.0% | $309.22 |
| GOOGL _(low n)_ | 2 | 1 | 1 | 0 | 50.0% | $254.92 |
| INTC _(low n)_ | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| IREN _(low n)_ | 1 | 0 | 1 | 0 | 0.0% | $-1000.0 |
| META _(low n)_ | 3 | 1 | 2 | 0 | 33.3% | $-1151.97 |
| MSFT _(low n)_ | 1 | 0 | 1 | 0 | 0.0% | $-22.15 |
| NVDA _(low n)_ | 3 | 1 | 2 | 0 | 33.3% | $-1312.25 |
| PLTR _(low n)_ | 2 | 0 | 2 | 0 | 0.0% | $-2000.0 |
| TSLA _(low n)_ | 3 | 1 | 2 | 0 | 33.3% | $-701.76 |
| TSM _(low n)_ | 2 | 0 | 2 | 0 | 0.0% | $-2000.0 |
_(low n): under 20 trades -- too few for this row to mean much (research/p12_sample_floor.md). Still counted in every total above._

### By Entry Hour
| Hour | Signals | W | L | Scratch | Win rate | P&L |
|------|---------|---|---|---------|----------|-----|
| 09:30-10:00 | 12 | 3 | 9 | 0 | 25.0% | $-4679.1 |
| 10:00-10:30 | 4 | 2 | 2 | 0 | 50.0% | $-365.0 |
| 10:30-11:00 | 9 | 5 | 4 | 0 | 55.6% | $-484.01 |

### B&R: clean first break vs late (level broken earlier)
| Bucket | Signals | W | L | Scratch | Win rate | P&L |
|--------|---------|---|---|---------|----------|-----|
| clean | 15 | 9 | 6 | 0 | 60.0% | $1255.49 |
| late | 7 | 0 | 7 | 0 | 0.0% | $-6081.84 |

## By Day
| Day | Signals | Wins | Losses | Scratch | P&L |
|-----|---------|------|--------|---------|-----|
| 2026-09-14 | 12 | 3 | 9 | 0 | $-4179.91 |
| 2026-09-15 | 13 | 7 | 6 | 0 | $-1348.2 |

## 84% Rule Analysis
- Total triggers (incl. filtered): 3
- Fired re-entry signals: 2
- Win rate on re-entry: 0.0% | P&L $-2000.0

## Signal Log
| Day | Time | Sym | Setup | Dir | Grade | Status | Entry | Stop | Outcome | P&L |
|-----|------|-----|-------|-----|-------|--------|-------|------|---------|-----|
| 2026-09-14 | 09:36:00 | AMD | break_and_retest | put | X | skipped_d | 483.12 | 484.71 | loss | - |
| 2026-09-14 | 09:37:00 | AMD | break_and_retest | put | X | skipped_d | 483.18 | 484.71 | loss | - |
| 2026-09-14 | 09:37:00 | HOOD | break_and_retest | call | X | skipped_d | 114.40 | 114.01 | loss | - |
| 2026-09-14 | 09:38:00 | AMD | break_and_retest | put | X | skipped_d | 483.78 | 484.71 | loss | - |
| 2026-09-14 | 09:39:00 | AMD | break_and_retest | put | X | skipped_d | 483.22 | 484.71 | loss | - |
| 2026-09-14 | 09:40:00 | AMD | break_and_retest | put | X | skipped_d | 483.72 | 484.71 | loss | - |
| 2026-09-14 | 09:40:00 | ORCL | break_and_retest | put | C | skipped_tight_stop | 142.10 | 142.39 | loss | - |
| 2026-09-14 | 09:40:00 | HOOD | break_and_retest | call | X | skipped_d | 114.49 | 114.01 | loss | - |
| 2026-09-14 | 09:41:00 | META | break_and_retest | call | B | fired | 663.36 | 659.75 | loss | $-263 |
| 2026-09-14 | 09:44:00 | META | break_and_retest | call | B | fired | 662.35 | 659.75 | loss | $-1000 |
| 2026-09-14 | 09:46:00 | BABA | break_and_retest | put | X | skipped_d | 108.00 | 108.06 | loss | - |
| 2026-09-14 | 09:47:00 | META | break_and_retest | call | X | skipped_d | 661.53 | 659.75 | win | - |
| 2026-09-14 | 09:48:00 | TSLA | break_and_retest | put | C | skipped_tight_stop | 360.34 | 360.93 | loss | - |
| 2026-09-14 | 09:48:00 | META | break_and_retest | call | X | skipped_d | 660.71 | 659.75 | win | - |
| 2026-09-14 | 09:48:00 | GOOGL | break_and_retest | call | X | skipped_d | 345.55 | 344.48 | win | - |
| 2026-09-14 | 09:49:00 | TSLA | break_and_retest | put | X | skipped_d | 360.69 | 360.93 | loss | - |
| 2026-09-14 | 09:49:00 | META | break_and_retest | call | B | fired | 662.79 | 659.75 | win | $111 |
| 2026-09-14 | 09:49:00 | GOOGL | break_and_retest | call | B | fired | 346.03 | 344.48 | loss | $-82 |
| 2026-09-14 | 09:50:00 | MSFT | break_and_retest | call | X | skipped_d | 499.32 | 498.97 | win | - |
| 2026-09-14 | 09:50:00 | MU | break_and_retest | call | X | skipped_d | 914.80 | 914.55 | loss | - |
| 2026-09-14 | 09:51:00 | GOOGL | break_and_retest | call | X | skipped_d | 345.53 | 345.29 | loss | - |
| 2026-09-14 | 09:51:00 | GOOGL | one_candle_rule | call | X | skipped_d | 345.53 | 344.59 | win | - |
| 2026-09-14 | 09:51:00 | AMZN | break_and_retest | put | X | skipped_d | 253.90 | 254.04 | loss | - |
| 2026-09-14 | 09:51:00 | HOOD | break_and_retest | call | X | skipped_d | 114.31 | 114.01 | loss | - |
| 2026-09-14 | 09:52:00 | GOOGL | break_and_retest | call | C | skipped_tight_stop | 345.88 | 345.29 | win | - |
| 2026-09-14 | 09:52:00 | AMZN | break_and_retest | put | X | skipped_d | 253.30 | 254.04 | loss | - |
| 2026-09-14 | 09:52:00 | MSFT | break_and_retest | call | B | fired | 500.89 | 498.97 | loss | $-22 |
| 2026-09-14 | 09:52:00 | HOOD | break_and_retest | call | X | skipped_d | 114.77 | 114.01 | loss | - |
| 2026-09-14 | 09:53:00 | GOOGL | break_and_retest | call | C | fired | 346.71 | 345.29 | loss | - |
| 2026-09-14 | 09:53:00 | AMZN | break_and_retest | put | X | skipped_d | 253.65 | 254.04 | loss | - |
| 2026-09-14 | 09:53:00 | HOOD | break_and_retest | call | X | skipped_d | 114.52 | 114.01 | loss | - |
| 2026-09-14 | 09:53:00 | TSM | break_and_retest | call | B | fired | 419.95 | 419.27 | loss | $-1000 |
| 2026-09-14 | 09:54:00 | NVDA | break_and_retest | put | B | fired | 210.68 | 211.00 | loss | $-1000 |
| 2026-09-14 | 09:54:00 | AMZN | break_and_retest | put | X | skipped_d | 253.48 | 254.04 | loss | - |
| 2026-09-14 | 09:54:00 | HOOD | break_and_retest | call | X | skipped_d | 114.66 | 114.01 | loss | - |
| 2026-09-14 | 09:55:00 | TSLA | break_and_retest | put | X | skipped_d | 361.10 | 361.60 | loss | - |
| 2026-09-14 | 09:55:00 | AMZN | break_and_retest | put | X | skipped_d | 253.05 | 254.04 | loss | - |
| 2026-09-14 | 09:55:00 | ORCL | break_and_retest | call | X | skipped_d | 144.31 | 144.25 | loss | - |
| 2026-09-14 | 09:56:00 | NVDA | break_and_retest | put | X | skipped_d | 210.76 | 211.00 | loss | - |
| 2026-09-14 | 09:56:00 | META | break_and_retest | call | X | skipped_d | 661.65 | 659.75 | loss | - |
| 2026-09-14 | 09:56:00 | TSM | break_and_retest | call | X | skipped_d | 419.59 | 419.27 | loss | - |
| 2026-09-14 | 09:57:00 | NVDA | break_and_retest | put | C | skipped_tight_stop | 210.66 | 211.00 | loss | - |
| 2026-09-14 | 09:57:00 | PLTR | break_and_retest | call | X | skipped_d | 168.72 | 168.16 | loss | - |
| 2026-09-14 | 09:58:00 | PLTR | break_and_retest | call | X | skipped_d | 168.46 | 168.16 | loss | - |
| 2026-09-14 | 09:58:00 | ORCL | break_and_retest | call | X | skipped_d | 144.48 | 144.25 | loss | - |
| 2026-09-14 | 09:58:00 | AVGO | break_and_retest | put | X | skipped_d | 347.48 | 347.65 | loss | - |
| 2026-09-14 | 09:58:00 | AVGO | break_and_retest | put | X | skipped_d | 347.48 | 347.53 | loss | - |
| 2026-09-14 | 09:59:00 | MARA | break_and_retest | put | X | skipped_d | 11.51 | 11.54 | loss | - |
| 2026-09-14 | 10:00:00 | PLTR | break_and_retest | call | X | skipped_d | 168.03 | 167.97 | loss | - |
| 2026-09-14 | 10:00:00 | ORCL | break_and_retest | call | X | skipped_d | 144.31 | 144.25 | loss | - |
| 2026-09-14 | 10:01:00 | NVDA | break_and_retest | put | X | skipped_d | 210.97 | 211.00 | loss | - |
| 2026-09-14 | 10:01:00 | AAPL | break_and_retest | call | X | skipped_d | 334.23 | 334.20 | loss | - |
| 2026-09-14 | 10:01:00 | ORCL | break_and_retest | call | X | skipped_d | 144.68 | 144.25 | loss | - |
| 2026-09-14 | 10:02:00 | ORCL | break_and_retest | call | X | skipped_d | 144.28 | 144.25 | loss | - |
| 2026-09-14 | 10:02:00 | AVGO | break_and_retest | put | X | skipped_d | 347.13 | 347.65 | loss | - |
| 2026-09-14 | 10:02:00 | AVGO | break_and_retest | put | X | skipped_d | 347.13 | 347.53 | loss | - |
| 2026-09-14 | 10:03:00 | AMZN | break_and_retest | put | X | skipped_d | 253.00 | 253.14 | loss | - |
| 2026-09-14 | 10:03:00 | AVGO | break_and_retest | put | X | skipped_d | 347.26 | 347.65 | loss | - |
| 2026-09-14 | 10:03:00 | AVGO | break_and_retest | put | X | skipped_d | 347.26 | 347.53 | loss | - |
| 2026-09-14 | 10:04:00 | AMZN | break_and_retest | put | X | skipped_d | 252.90 | 253.14 | loss | - |
| 2026-09-14 | 10:04:00 | ORCL | break_and_retest | call | X | skipped_d | 144.46 | 144.25 | loss | - |
| 2026-09-14 | 10:05:00 | AMZN | break_and_retest | put | X | skipped_d | 252.81 | 253.14 | loss | - |
| 2026-09-14 | 10:06:00 | AMZN | break_and_retest | put | X | skipped_d | 252.89 | 253.14 | loss | - |
| 2026-09-14 | 10:06:00 | MSFT | break_and_retest | call | X | skipped_d | 502.10 | 501.67 | loss | - |
| 2026-09-14 | 10:06:00 | ORCL | break_and_retest | call | X | skipped_d | 144.49 | 144.25 | loss | - |
| 2026-09-14 | 10:06:00 | COIN | break_and_retest | call | X | skipped_d | 188.00 | 187.86 | loss | - |
| 2026-09-14 | 10:06:00 | MARA | break_and_retest | call | X | skipped_d | 11.59 | 11.56 | win | - |
| 2026-09-14 | 10:07:00 | SOFI | break_and_retest | put | X | skipped_d | 17.29 | 17.29 | loss | - |
| 2026-09-14 | 10:08:00 | MARA | break_and_retest | call | X | skipped_d | 11.64 | 11.56 | win | - |
| 2026-09-14 | 10:09:00 | SOFI | break_and_retest | put | X | skipped_d | 17.28 | 17.29 | loss | - |
| 2026-09-14 | 10:10:00 | COIN | break_and_retest | call | X | skipped_d | 188.13 | 187.86 | loss | - |
| 2026-09-14 | 10:10:00 | BABA | break_and_retest | call | X | skipped_d | 108.29 | 108.26 | loss | - |
| 2026-09-14 | 10:11:00 | COIN | break_and_retest | call | X | skipped_d | 188.73 | 187.86 | loss | - |
| 2026-09-14 | 10:12:00 | TSLA | one_candle_rule | put | B | fired | 360.60 | 361.80 | win | $1298 |
| 2026-09-14 | 10:13:00 | TSLA | break_and_retest | call | X | skipped_d | 360.96 | 360.53 | loss | - |
| 2026-09-14 | 10:13:00 | AMZN | break_and_retest | put | X | skipped_d | 252.70 | 252.70 | loss | - |
| 2026-09-14 | 10:13:00 | SPY | break_and_retest | call | X | skipped_d | 760.64 | 760.59 | loss | - |
| 2026-09-14 | 10:13:00 | SPY | break_and_retest | call | X | skipped_d | 760.64 | 760.59 | loss | - |
| 2026-09-14 | 10:13:00 | MU | break_and_retest | call | X | skipped_d | 919.64 | 918.66 | loss | - |
| 2026-09-14 | 10:13:00 | BABA | break_and_retest | call | X | skipped_d | 108.34 | 108.26 | loss | - |
| 2026-09-14 | 10:13:00 | BABA | break_and_retest | call | X | skipped_d | 108.34 | 108.32 | loss | - |
| 2026-09-14 | 10:15:00 | AMZN | break_and_retest | put | X | skipped_d | 252.49 | 252.70 | loss | - |
| 2026-09-14 | 10:16:00 | AMZN | break_and_retest | put | X | skipped_d | 252.58 | 252.70 | loss | - |
| 2026-09-14 | 10:17:00 | AMZN | break_and_retest | put | X | skipped_d | 252.35 | 252.70 | loss | - |
| 2026-09-14 | 10:17:00 | PLTR | break_and_retest | put | X | skipped_d | 167.75 | 167.76 | loss | - |
| 2026-09-14 | 10:17:00 | UBER | break_and_retest | put | X | skipped_d | 71.39 | 71.43 | win | - |
| 2026-09-14 | 10:18:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.90 | 344.88 | loss | - |
| 2026-09-14 | 10:18:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.90 | 345.54 | loss | - |
| 2026-09-14 | 10:18:00 | AMZN | break_and_retest | put | X | skipped_d | 251.96 | 252.70 | loss | - |
| 2026-09-14 | 10:18:00 | PLTR | break_and_retest | put | X | skipped_d | 167.70 | 167.76 | loss | - |
| 2026-09-14 | 10:18:00 | COIN | break_and_retest | call | X | skipped_d | 188.01 | 187.86 | loss | - |
| 2026-09-14 | 10:19:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.40 | 345.54 | loss | - |
| 2026-09-14 | 10:19:00 | PLTR | break_and_retest | put | X | skipped_d | 167.55 | 167.76 | loss | - |
| 2026-09-14 | 10:19:00 | INTC | break_and_retest | call | X | skipped_d | 97.56 | 97.51 | loss | - |
| 2026-09-14 | 10:19:00 | BABA | break_and_retest | call | X | skipped_d | 108.30 | 108.26 | loss | - |
| 2026-09-14 | 10:20:00 | PLTR | break_and_retest | put | X | skipped_d | 167.64 | 167.76 | loss | - |
| 2026-09-14 | 10:21:00 | PLTR | break_and_retest | put | X | skipped_d | 167.56 | 167.76 | loss | - |
| 2026-09-14 | 10:21:00 | IREN | break_and_retest | call | X | skipped_d | 43.86 | 43.85 | loss | - |
| 2026-09-14 | 10:22:00 | PLTR | break_and_retest | put | B | fired | 167.48 | 167.76 | loss | $-1000 |
| 2026-09-14 | 10:23:00 | AAPL | one_candle_rule | put | X | skipped_d | 333.33 | 333.82 | loss | - |
| 2026-09-14 | 10:24:00 | CRM | one_candle_rule | call | X | skipped_d | 252.86 | 252.14 | win | - |
| 2026-09-14 | 10:24:00 | TSM | break_and_retest | put | X | skipped_d | 422.64 | 422.65 | loss | - |
| 2026-09-14 | 10:24:00 | TSM | break_and_retest | put | X | skipped_d | 422.64 | 422.84 | loss | - |
| 2026-09-14 | 10:25:00 | ORCL | break_and_retest | put | C | fired | 142.41 | 142.90 | loss | - |
| 2026-09-14 | 10:26:00 | TSM | break_and_retest | put | X | skipped_d | 422.15 | 422.65 | loss | - |
| 2026-09-14 | 10:26:00 | TSM | break_and_retest | put | X | skipped_d | 422.15 | 422.84 | loss | - |
| 2026-09-14 | 10:27:00 | TSM | break_and_retest | put | X | skipped_d | 422.52 | 422.65 | loss | - |
| 2026-09-14 | 10:27:00 | TSM | break_and_retest | put | X | skipped_d | 422.52 | 422.84 | loss | - |
| 2026-09-14 | 10:28:00 | PLTR | break_and_retest | put | X | skipped_d | 167.25 | 167.30 | loss | - |
| 2026-09-14 | 10:28:00 | QQQ | break_and_retest | put | X | skipped_d | 705.67 | 705.76 | loss | - |
| 2026-09-14 | 10:28:00 | ORCL | break_and_retest | put | X | skipped_d | 142.59 | 142.90 | loss | - |
| 2026-09-14 | 10:28:00 | TSM | break_and_retest | put | X | skipped_d | 421.73 | 422.65 | loss | - |
| 2026-09-14 | 10:28:00 | TSM | break_and_retest | put | X | skipped_d | 421.73 | 422.84 | loss | - |
| 2026-09-14 | 10:30:00 | MSFT | break_and_retest | call | X | skipped_d | 499.26 | 498.97 | loss | - |
| 2026-09-14 | 10:30:00 | QQQ | break_and_retest | put | X | skipped_d | 705.52 | 705.76 | loss | - |
| 2026-09-14 | 10:31:00 | MSFT | break_and_retest | call | X | skipped_d | 499.47 | 498.97 | loss | - |
| 2026-09-14 | 10:31:00 | QQQ | break_and_retest | put | X | skipped_d | 705.73 | 705.76 | loss | - |
| 2026-09-14 | 10:32:00 | MSFT | break_and_retest | call | C | fired | 500.21 | 498.97 | loss | - |
| 2026-09-14 | 10:32:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 96.86 | 97.10 | loss | - |
| 2026-09-14 | 10:32:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 96.86 | 97.08 | loss | - |
| 2026-09-14 | 10:32:00 | NFLX | break_and_retest | call | X | skipped_d | 79.93 | 79.92 | loss | - |
| 2026-09-14 | 10:33:00 | AAPL | one_candle_rule | put | X | skipped_d | 333.20 | 333.82 | loss | - |
| 2026-09-14 | 10:33:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 96.71 | 97.10 | loss | - |
| 2026-09-14 | 10:33:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 96.71 | 97.08 | loss | - |
| 2026-09-14 | 10:35:00 | NVDA | reentry_84_rule | put | B | fired | 210.65 | 211.00 | loss | $-1000 |
| 2026-09-14 | 10:35:00 | QQQ | break_and_retest | put | X | skipped_d | 705.27 | 705.76 | loss | - |
| 2026-09-14 | 10:37:00 | MSFT | break_and_retest | call | X | skipped_d | 499.00 | 498.97 | loss | - |
| 2026-09-14 | 10:37:00 | PLTR | break_and_retest | call | X | skipped_d | 168.15 | 168.14 | loss | - |
| 2026-09-14 | 10:37:00 | ORCL | break_and_retest | call | X | skipped_d | 143.28 | 142.90 | scratch | - |
| 2026-09-14 | 10:37:00 | TSM | reentry_84_rule | call | B | fired | 420.02 | 419.27 | loss | $-1000 |
| 2026-09-14 | 10:38:00 | MSFT | break_and_retest | call | X | skipped_d | 499.14 | 498.97 | loss | - |
| 2026-09-14 | 10:38:00 | ORCL | break_and_retest | call | X | skipped_d | 143.18 | 142.90 | scratch | - |
| 2026-09-14 | 10:39:00 | AMZN | one_candle_rule | put | X | skipped_d | 251.87 | 252.10 | loss | - |
| 2026-09-14 | 10:39:00 | MSFT | break_and_retest | call | X | skipped_d | 499.38 | 499.30 | loss | - |
| 2026-09-14 | 10:39:00 | PLTR | break_and_retest | call | X | skipped_d | 168.16 | 168.14 | loss | - |
| 2026-09-14 | 10:39:00 | ORCL | break_and_retest | call | X | skipped_d | 143.63 | 142.90 | scratch | - |
| 2026-09-14 | 10:40:00 | MSFT | break_and_retest | call | X | skipped_d | 499.32 | 499.30 | loss | - |
| 2026-09-14 | 10:40:00 | CRM | one_candle_rule | call | X | skipped_d | 253.90 | 253.53 | win | - |
| 2026-09-14 | 10:41:00 | MSFT | break_and_retest | call | X | skipped_d | 499.60 | 499.30 | loss | - |
| 2026-09-14 | 10:41:00 | AVGO | break_and_retest | put | X | skipped_d | 344.77 | 345.10 | loss | - |
| 2026-09-14 | 10:41:00 | MARA | break_and_retest | put | X | skipped_d | 11.52 | 11.54 | loss | - |
| 2026-09-14 | 10:42:00 | AMZN | break_and_retest | call | X | skipped_d | 252.10 | 251.93 | scratch | - |
| 2026-09-14 | 10:42:00 | QQQ | break_and_retest | put | X | skipped_d | 705.07 | 705.11 | loss | - |
| 2026-09-14 | 10:42:00 | AVGO | break_and_retest | put | X | skipped_d | 345.06 | 345.10 | loss | - |
| 2026-09-14 | 10:43:00 | QQQ | break_and_retest | put | X | skipped_d | 704.79 | 705.11 | loss | - |
| 2026-09-14 | 10:43:00 | ORCL | break_and_retest | call | X | skipped_d | 143.75 | 143.50 | loss | - |
| 2026-09-14 | 10:43:00 | UBER | break_and_retest | call | X | skipped_d | 71.46 | 71.43 | loss | - |
| 2026-09-14 | 10:43:00 | MARA | break_and_retest | put | X | skipped_d | 11.48 | 11.54 | loss | - |
| 2026-09-14 | 10:44:00 | TSLA | break_and_retest | call | X | skipped_d | 358.76 | 358.69 | loss | - |
| 2026-09-14 | 10:44:00 | ORCL | break_and_retest | call | X | skipped_d | 143.62 | 143.50 | loss | - |
| 2026-09-14 | 10:44:00 | AVGO | break_and_retest | put | X | skipped_d | 344.98 | 345.10 | loss | - |
| 2026-09-14 | 10:44:00 | MARA | break_and_retest | put | X | skipped_d | 11.49 | 11.54 | loss | - |
| 2026-09-14 | 10:45:00 | ORCL | break_and_retest | call | X | skipped_d | 144.31 | 143.50 | loss | - |
| 2026-09-14 | 10:45:00 | IREN | break_and_retest | put | X | skipped_d | 43.33 | 43.35 | loss | - |
| 2026-09-14 | 10:45:00 | INTC | break_and_retest | put | X | skipped_d | 96.76 | 96.79 | loss | - |
| 2026-09-14 | 10:46:00 | AMD | break_and_retest | put | X | skipped_d | 484.44 | 484.71 | loss | - |
| 2026-09-14 | 10:46:00 | ORCL | break_and_retest | call | X | skipped_d | 144.05 | 143.50 | loss | - |
| 2026-09-14 | 10:46:00 | NFLX | break_and_retest | call | X | skipped_d | 80.14 | 80.13 | loss | - |
| 2026-09-14 | 10:46:00 | AVGO | break_and_retest | put | X | skipped_d | 344.94 | 345.10 | win | - |
| 2026-09-14 | 10:47:00 | TSLA | break_and_retest | call | X | skipped_d | 358.80 | 358.69 | loss | - |
| 2026-09-14 | 10:47:00 | TSLA | break_and_retest | call | X | skipped_d | 358.80 | 358.60 | loss | - |
| 2026-09-14 | 10:47:00 | NFLX | break_and_retest | call | X | skipped_d | 80.21 | 80.13 | loss | - |
| 2026-09-14 | 10:47:00 | AVGO | break_and_retest | put | B | fired | 344.61 | 345.10 | win | $778 |
| 2026-09-14 | 10:48:00 | TSLA | break_and_retest | call | X | skipped_d | 359.06 | 358.69 | loss | - |
| 2026-09-14 | 10:48:00 | TSLA | break_and_retest | call | X | skipped_d | 359.06 | 358.60 | loss | - |
| 2026-09-14 | 10:48:00 | MU | break_and_retest | call | X | skipped_d | 914.64 | 914.55 | loss | - |
| 2026-09-14 | 10:49:00 | TSLA | break_and_retest | call | X | skipped_d | 359.22 | 358.69 | loss | - |
| 2026-09-14 | 10:49:00 | TSLA | break_and_retest | call | X | skipped_d | 359.22 | 358.60 | loss | - |
| 2026-09-14 | 10:49:00 | META | break_and_retest | call | X | skipped_d | 654.88 | 654.70 | loss | - |
| 2026-09-14 | 10:49:00 | SOFI | break_and_retest | call | X | skipped_d | 17.33 | 17.32 | loss | - |
| 2026-09-14 | 10:49:00 | MARA | break_and_retest | put | X | skipped_d | 11.45 | 11.47 | loss | - |
| 2026-09-14 | 10:50:00 | TSLA | break_and_retest | call | X | skipped_d | 358.66 | 358.60 | loss | - |
| 2026-09-14 | 10:50:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.32 | 344.31 | loss | - |
| 2026-09-14 | 10:50:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.32 | 344.29 | loss | - |
| 2026-09-14 | 10:50:00 | SOFI | break_and_retest | call | X | skipped_d | 17.33 | 17.32 | loss | - |
| 2026-09-14 | 10:50:00 | SOFI | break_and_retest | call | X | skipped_d | 17.33 | 17.33 | loss | - |
| 2026-09-14 | 10:50:00 | MARA | break_and_retest | put | X | skipped_d | 11.43 | 11.47 | loss | - |
| 2026-09-14 | 10:51:00 | TSLA | break_and_retest | call | X | skipped_d | 359.19 | 358.69 | loss | - |
| 2026-09-14 | 10:51:00 | NVDA | break_and_retest | call | X | skipped_d | 210.66 | 210.62 | loss | - |
| 2026-09-14 | 10:51:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.57 | 344.31 | loss | - |
| 2026-09-14 | 10:51:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.57 | 344.29 | loss | - |
| 2026-09-14 | 10:51:00 | MU | break_and_retest | call | X | skipped_d | 915.41 | 914.55 | loss | - |
| 2026-09-14 | 10:51:00 | MARA | break_and_retest | put | X | skipped_d | 11.41 | 11.47 | loss | - |
| 2026-09-14 | 10:52:00 | TSLA | break_and_retest | call | X | skipped_d | 358.87 | 358.69 | loss | - |
| 2026-09-14 | 10:52:00 | AMD | break_and_retest | put | X | skipped_d | 483.47 | 484.71 | loss | - |
| 2026-09-14 | 10:52:00 | META | break_and_retest | call | X | skipped_d | 653.46 | 653.28 | loss | - |
| 2026-09-14 | 10:52:00 | META | break_and_retest | call | X | skipped_d | 653.46 | 652.91 | loss | - |
| 2026-09-14 | 10:52:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.32 | 344.31 | loss | - |
| 2026-09-14 | 10:52:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.32 | 344.29 | loss | - |
| 2026-09-14 | 10:52:00 | MSFT | break_and_retest | call | X | skipped_d | 499.81 | 499.80 | loss | - |
| 2026-09-14 | 10:52:00 | MARA | break_and_retest | put | X | skipped_d | 11.38 | 11.47 | loss | - |
| 2026-09-14 | 10:53:00 | NVDA | one_candle_rule | put | C | skipped_tight_stop | 210.48 | 210.83 | loss | - |
| 2026-09-14 | 10:53:00 | AMD | break_and_retest | put | X | skipped_d | 483.21 | 484.71 | loss | - |
| 2026-09-14 | 10:53:00 | AMZN | break_and_retest | call | X | skipped_d | 252.32 | 252.24 | loss | - |
| 2026-09-14 | 10:54:00 | NVDA | break_and_retest | call | X | skipped_d | 210.63 | 210.62 | loss | - |
| 2026-09-14 | 10:54:00 | AMD | break_and_retest | put | X | skipped_d | 483.71 | 484.71 | loss | - |
| 2026-09-14 | 10:54:00 | META | break_and_retest | call | X | skipped_d | 653.33 | 653.28 | loss | - |
| 2026-09-14 | 10:54:00 | META | break_and_retest | call | X | skipped_d | 653.33 | 652.91 | loss | - |
| 2026-09-14 | 10:54:00 | MSFT | break_and_retest | call | X | skipped_d | 500.39 | 499.80 | win | - |
| 2026-09-14 | 10:54:00 | NFLX | break_and_retest | call | X | skipped_d | 80.22 | 80.13 | loss | - |
| 2026-09-14 | 10:54:00 | CRM | break_and_retest | call | X | skipped_d | 254.98 | 254.91 | loss | - |
| 2026-09-14 | 10:55:00 | NVDA | one_candle_rule | put | C | skipped_tight_stop | 210.48 | 210.83 | loss | - |
| 2026-09-14 | 10:55:00 | AMD | break_and_retest | put | X | skipped_d | 484.05 | 484.71 | loss | - |
| 2026-09-14 | 10:55:00 | META | break_and_retest | call | X | skipped_d | 652.96 | 652.91 | loss | - |
| 2026-09-14 | 10:55:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.47 | 344.31 | loss | - |
| 2026-09-14 | 10:55:00 | GOOGL | break_and_retest | call | X | skipped_d | 344.47 | 344.29 | loss | - |
| 2026-09-14 | 10:55:00 | MSFT | break_and_retest | call | X | skipped_d | 500.13 | 499.80 | win | - |
| 2026-09-14 | 10:55:00 | NFLX | break_and_retest | call | X | skipped_d | 80.14 | 80.13 | loss | - |
| 2026-09-14 | 10:56:00 | MSFT | break_and_retest | call | X | skipped_d | 500.46 | 499.80 | win | - |
| 2026-09-14 | 10:57:00 | INTC | break_and_retest | put | X | skipped_d | 96.39 | 96.43 | loss | - |
| 2026-09-14 | 10:57:00 | NFLX | break_and_retest | call | X | skipped_d | 80.18 | 80.13 | loss | - |
| 2026-09-14 | 10:57:00 | BABA | break_and_retest | put | X | skipped_d | 108.93 | 109.00 | loss | - |
| 2026-09-14 | 10:58:00 | ORCL | break_and_retest | call | X | skipped_d | 144.10 | 144.08 | loss | - |
| 2026-09-14 | 10:58:00 | INTC | break_and_retest | put | X | skipped_d | 96.32 | 96.43 | loss | - |
| 2026-09-14 | 10:58:00 | NFLX | break_and_retest | call | X | skipped_d | 80.19 | 80.13 | loss | - |
| 2026-09-14 | 10:58:00 | BABA | break_and_retest | put | X | skipped_d | 108.97 | 109.00 | loss | - |
| 2026-09-14 | 10:59:00 | SOFI | break_and_retest | put | X | skipped_d | 17.29 | 17.30 | loss | - |
| 2026-09-14 | 10:59:00 | SOFI | break_and_retest | put | X | skipped_d | 17.29 | 17.31 | loss | - |
| 2026-09-14 | 10:59:00 | INTC | break_and_retest | put | X | skipped_d | 96.42 | 96.43 | loss | - |
| 2026-09-15 | 09:38:00 | AMD | break_and_retest | call | X | skipped_d | 503.95 | 501.99 | win | - |
| 2026-09-15 | 09:39:00 | NVDA | break_and_retest | call | X | skipped_d | 213.09 | 212.77 | win | - |
| 2026-09-15 | 09:39:00 | UBER | break_and_retest | put | X | skipped_d | 71.93 | 71.95 | loss | - |
| 2026-09-15 | 09:40:00 | NVDA | break_and_retest | call | B | fired | 213.24 | 212.77 | win | $688 |
| 2026-09-15 | 09:40:00 | AMD | break_and_retest | call | B | fired | 505.00 | 501.99 | win | $889 |
| 2026-09-15 | 09:41:00 | INTC | break_and_retest | call | X | skipped_d | 99.62 | 99.60 | loss | - |
| 2026-09-15 | 09:44:00 | TSLA | break_and_retest | call | X | skipped_d | 361.05 | 360.69 | loss | - |
| 2026-09-15 | 09:46:00 | BABA | break_and_retest | call | X | skipped_d | 110.60 | 110.43 | loss | - |
| 2026-09-15 | 09:47:00 | TSLA | break_and_retest | call | X | skipped_d | 360.86 | 360.69 | loss | - |
| 2026-09-15 | 09:48:00 | BABA | break_and_retest | call | X | skipped_d | 110.32 | 110.31 | loss | - |
| 2026-09-15 | 09:49:00 | TSLA | break_and_retest | call | B | fired | 361.48 | 360.69 | loss | $-1000 |
| 2026-09-15 | 09:49:00 | BABA | break_and_retest | call | X | skipped_d | 110.48 | 110.39 | loss | - |
| 2026-09-15 | 09:49:00 | BABA | break_and_retest | call | X | skipped_d | 110.48 | 110.43 | loss | - |
| 2026-09-15 | 09:49:00 | BABA | break_and_retest | call | B | fired | 110.48 | 110.31 | loss | $-1000 |
| 2026-09-15 | 09:50:00 | PLTR | break_and_retest | call | X | skipped_d | 172.32 | 172.13 | loss | - |
| 2026-09-15 | 09:51:00 | INTC | break_and_retest | put | X | skipped_d | 99.42 | 99.45 | loss | - |
| 2026-09-15 | 09:52:00 | PLTR | break_and_retest | call | X | skipped_d | 172.34 | 172.13 | loss | - |
| 2026-09-15 | 09:52:00 | QQQ | break_and_retest | call | X | skipped_d | 708.86 | 708.81 | loss | - |
| 2026-09-15 | 09:53:00 | PLTR | break_and_retest | call | B | fired | 172.57 | 172.13 | loss | $-1000 |
| 2026-09-15 | 09:53:00 | QQQ | break_and_retest | call | X | skipped_d | 709.11 | 708.81 | loss | - |
| 2026-09-15 | 09:54:00 | QQQ | break_and_retest | call | X | skipped_d | 708.98 | 708.81 | loss | - |
| 2026-09-15 | 09:57:00 | BABA | break_and_retest | call | X | skipped_d | 110.50 | 110.39 | loss | - |
| 2026-09-15 | 09:57:00 | BABA | break_and_retest | call | X | skipped_d | 110.50 | 110.43 | loss | - |
| 2026-09-15 | 09:57:00 | BABA | reentry_84_rule | call | C | skipped_tight_stop | 110.50 | 110.31 | loss | - |
| 2026-09-15 | 09:58:00 | GOOGL | break_and_retest | put | X | skipped_d | 345.72 | 345.87 | win | - |
| 2026-09-15 | 09:58:00 | BABA | break_and_retest | call | X | skipped_d | 110.41 | 110.39 | loss | - |
| 2026-09-15 | 09:59:00 | GOOGL | break_and_retest | put | X | skipped_d | 345.86 | 345.87 | win | - |
| 2026-09-15 | 09:59:00 | QQQ | break_and_retest | call | X | skipped_d | 708.95 | 708.81 | loss | - |
| 2026-09-15 | 09:59:00 | BABA | break_and_retest | call | X | skipped_d | 110.44 | 110.39 | loss | - |
| 2026-09-15 | 09:59:00 | BABA | break_and_retest | call | X | skipped_d | 110.44 | 110.43 | loss | - |
| 2026-09-15 | 10:00:00 | TSLA | one_candle_rule | put | X | skipped_d | 359.68 | 360.89 | loss | - |
| 2026-09-15 | 10:00:00 | GOOGL | break_and_retest | put | X | skipped_d | 345.00 | 345.87 | win | - |
| 2026-09-15 | 10:00:00 | QQQ | break_and_retest | call | X | skipped_d | 708.84 | 708.81 | loss | - |
| 2026-09-15 | 10:00:00 | INTC | break_and_retest | call | X | skipped_d | 99.99 | 99.60 | loss | - |
| 2026-09-15 | 10:00:00 | NFLX | break_and_retest | put | X | skipped_d | 78.11 | 78.17 | win | - |
| 2026-09-15 | 10:00:00 | BABA | break_and_retest | call | X | skipped_d | 110.40 | 110.39 | loss | - |
| 2026-09-15 | 10:01:00 | INTC | break_and_retest | call | X | skipped_d | 99.63 | 99.60 | loss | - |
| 2026-09-15 | 10:01:00 | NFLX | break_and_retest | put | X | skipped_d | 78.07 | 78.17 | win | - |
| 2026-09-15 | 10:01:00 | MU | one_candle_rule | call | X | skipped_d | 938.86 | 936.20 | loss | - |
| 2026-09-15 | 10:02:00 | TSLA | one_candle_rule | put | X | skipped_d | 359.60 | 360.89 | loss | - |
| 2026-09-15 | 10:02:00 | HOOD | break_and_retest | call | X | skipped_d | 110.02 | 109.94 | loss | - |
| 2026-09-15 | 10:02:00 | NFLX | break_and_retest | put | X | skipped_d | 77.94 | 78.17 | win | - |
| 2026-09-15 | 10:02:00 | MU | one_candle_rule | call | X | skipped_d | 939.58 | 936.20 | loss | - |
| 2026-09-15 | 10:02:00 | TSM | break_and_retest | put | X | skipped_d | 416.87 | 417.13 | win | - |
| 2026-09-15 | 10:03:00 | NVDA | break_and_retest | put | X | skipped_d | 212.78 | 213.02 | loss | - |
| 2026-09-15 | 10:03:00 | NFLX | break_and_retest | put | X | skipped_d | 77.90 | 78.17 | win | - |
| 2026-09-15 | 10:03:00 | UBER | one_candle_rule | put | X | skipped_d | 72.03 | 72.13 | win | - |
| 2026-09-15 | 10:03:00 | TSM | break_and_retest | put | C | fired | 416.50 | 417.13 | win | - |
| 2026-09-15 | 10:05:00 | NVDA | break_and_retest | put | X | skipped_d | 212.98 | 213.02 | loss | - |
| 2026-09-15 | 10:05:00 | HOOD | break_and_retest | call | X | skipped_d | 109.94 | 109.84 | loss | - |
| 2026-09-15 | 10:05:00 | TSM | break_and_retest | put | X | skipped_d | 416.54 | 417.13 | win | - |
| 2026-09-15 | 10:06:00 | NVDA | break_and_retest | put | X | skipped_d | 213.21 | 213.21 | win | - |
| 2026-09-15 | 10:06:00 | GOOGL | break_and_retest | put | X | skipped_d | 345.00 | 345.37 | win | - |
| 2026-09-15 | 10:07:00 | NVDA | break_and_retest | put | X | skipped_d | 213.10 | 213.21 | win | - |
| 2026-09-15 | 10:07:00 | NVDA | break_and_retest | put | X | skipped_d | 213.10 | 213.18 | win | - |
| 2026-09-15 | 10:07:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.88 | 345.37 | win | - |
| 2026-09-15 | 10:08:00 | NVDA | break_and_retest | put | X | skipped_d | 212.93 | 213.21 | win | - |
| 2026-09-15 | 10:08:00 | NVDA | break_and_retest | put | X | skipped_d | 212.93 | 213.18 | win | - |
| 2026-09-15 | 10:08:00 | NVDA | break_and_retest | put | X | skipped_d | 212.93 | 213.02 | loss | - |
| 2026-09-15 | 10:09:00 | NVDA | break_and_retest | put | X | skipped_d | 213.12 | 213.21 | win | - |
| 2026-09-15 | 10:09:00 | NVDA | break_and_retest | put | X | skipped_d | 213.12 | 213.18 | win | - |
| 2026-09-15 | 10:09:00 | AMD | break_and_retest | put | X | skipped_d | 509.89 | 510.21 | loss | - |
| 2026-09-15 | 10:09:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.78 | 345.37 | win | - |
| 2026-09-15 | 10:10:00 | NVDA | break_and_retest | put | X | skipped_d | 212.96 | 213.18 | win | - |
| 2026-09-15 | 10:10:00 | NVDA | break_and_retest | put | X | skipped_d | 212.96 | 213.02 | win | - |
| 2026-09-15 | 10:10:00 | AAPL | break_and_retest | put | X | skipped_d | 329.65 | 330.10 | loss | - |
| 2026-09-15 | 10:10:00 | AMD | break_and_retest | put | X | skipped_d | 509.47 | 510.21 | loss | - |
| 2026-09-15 | 10:10:00 | COIN | break_and_retest | put | X | skipped_d | 178.84 | 179.15 | loss | - |
| 2026-09-15 | 10:10:00 | COIN | break_and_retest | put | X | skipped_d | 178.84 | 179.04 | loss | - |
| 2026-09-15 | 10:10:00 | IREN | break_and_retest | put | X | skipped_d | 41.94 | 41.99 | loss | - |
| 2026-09-15 | 10:11:00 | AMD | break_and_retest | put | C | fired | 508.81 | 510.21 | loss | - |
| 2026-09-15 | 10:11:00 | COIN | break_and_retest | put | X | skipped_d | 179.05 | 179.15 | loss | - |
| 2026-09-15 | 10:11:00 | IREN | break_and_retest | put | B | fired | 41.87 | 41.99 | loss | $-1000 |
| 2026-09-15 | 10:11:00 | MARA | break_and_retest | put | X | skipped_d | 11.19 | 11.22 | loss | - |
| 2026-09-15 | 10:11:00 | MARA | break_and_retest | put | X | skipped_d | 11.19 | 11.20 | loss | - |
| 2026-09-15 | 10:12:00 | AAPL | break_and_retest | put | X | skipped_d | 329.58 | 330.20 | loss | - |
| 2026-09-15 | 10:12:00 | AAPL | break_and_retest | put | X | skipped_d | 329.58 | 330.10 | loss | - |
| 2026-09-15 | 10:12:00 | PLTR | break_and_retest | put | X | skipped_d | 171.73 | 171.86 | loss | - |
| 2026-09-15 | 10:12:00 | PLTR | break_and_retest | put | X | skipped_d | 171.73 | 171.88 | loss | - |
| 2026-09-15 | 10:12:00 | ORCL | break_and_retest | call | X | skipped_d | 141.24 | 141.16 | loss | - |
| 2026-09-15 | 10:13:00 | AMD | break_and_retest | put | X | skipped_d | 509.61 | 510.21 | loss | - |
| 2026-09-15 | 10:13:00 | PLTR | break_and_retest | put | X | skipped_d | 171.28 | 171.86 | loss | - |
| 2026-09-15 | 10:13:00 | PLTR | break_and_retest | put | X | skipped_d | 171.28 | 171.88 | loss | - |
| 2026-09-15 | 10:13:00 | ORCL | break_and_retest | call | X | skipped_d | 141.20 | 141.16 | loss | - |
| 2026-09-15 | 10:13:00 | MARA | break_and_retest | put | X | skipped_d | 11.21 | 11.22 | loss | - |
| 2026-09-15 | 10:14:00 | AAPL | break_and_retest | put | X | skipped_d | 329.76 | 330.20 | loss | - |
| 2026-09-15 | 10:14:00 | AAPL | break_and_retest | put | X | skipped_d | 329.76 | 330.10 | loss | - |
| 2026-09-15 | 10:14:00 | AMD | break_and_retest | put | C | fired | 508.91 | 510.21 | loss | - |
| 2026-09-15 | 10:14:00 | META | break_and_retest | put | X | skipped_d | 669.81 | 669.94 | loss | - |
| 2026-09-15 | 10:14:00 | PLTR | break_and_retest | put | X | skipped_d | 171.10 | 171.86 | loss | - |
| 2026-09-15 | 10:14:00 | PLTR | break_and_retest | put | X | skipped_d | 171.10 | 171.88 | loss | - |
| 2026-09-15 | 10:15:00 | AAPL | break_and_retest | put | X | skipped_d | 329.56 | 330.20 | loss | - |
| 2026-09-15 | 10:15:00 | AAPL | break_and_retest | put | X | skipped_d | 329.56 | 330.10 | loss | - |
| 2026-09-15 | 10:15:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.64 | 344.71 | loss | - |
| 2026-09-15 | 10:15:00 | MSFT | break_and_retest | put | X | skipped_d | 498.78 | 499.10 | loss | - |
| 2026-09-15 | 10:15:00 | INTC | break_and_retest | put | X | skipped_d | 99.24 | 99.32 | loss | - |
| 2026-09-15 | 10:15:00 | MARA | break_and_retest | put | X | skipped_d | 11.21 | 11.22 | loss | - |
| 2026-09-15 | 10:16:00 | AMD | break_and_retest | put | C | fired | 509.03 | 510.21 | loss | - |
| 2026-09-15 | 10:16:00 | MSFT | break_and_retest | put | X | skipped_d | 499.00 | 499.10 | loss | - |
| 2026-09-15 | 10:16:00 | ORCL | break_and_retest | call | X | skipped_d | 141.30 | 141.16 | loss | - |
| 2026-09-15 | 10:16:00 | COIN | break_and_retest | put | X | skipped_d | 178.96 | 179.04 | loss | - |
| 2026-09-15 | 10:16:00 | MARA | break_and_retest | put | X | skipped_d | 11.19 | 11.22 | loss | - |
| 2026-09-15 | 10:16:00 | MARA | break_and_retest | put | X | skipped_d | 11.19 | 11.20 | loss | - |
| 2026-09-15 | 10:17:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.55 | 344.71 | win | - |
| 2026-09-15 | 10:17:00 | ORCL | break_and_retest | call | X | skipped_d | 141.97 | 141.16 | loss | - |
| 2026-09-15 | 10:18:00 | AAPL | break_and_retest | put | X | skipped_d | 329.64 | 329.76 | loss | - |
| 2026-09-15 | 10:18:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.32 | 344.71 | win | - |
| 2026-09-15 | 10:18:00 | ORCL | break_and_retest | call | X | skipped_d | 141.57 | 141.16 | loss | - |
| 2026-09-15 | 10:18:00 | COIN | break_and_retest | put | X | skipped_d | 178.80 | 179.04 | win | - |
| 2026-09-15 | 10:18:00 | HOOD | break_and_retest | put | X | skipped_d | 110.46 | 110.50 | loss | - |
| 2026-09-15 | 10:18:00 | UBER | break_and_retest | put | X | skipped_d | 71.67 | 71.69 | loss | - |
| 2026-09-15 | 10:19:00 | GOOGL | break_and_retest | put | B | fired | 344.22 | 344.71 | win | $337 |
| 2026-09-15 | 10:19:00 | MSFT | break_and_retest | put | X | skipped_d | 498.81 | 499.10 | win | - |
| 2026-09-15 | 10:19:00 | ORCL | break_and_retest | call | X | skipped_d | 142.05 | 141.16 | loss | - |
| 2026-09-15 | 10:19:00 | UBER | break_and_retest | put | X | skipped_d | 71.64 | 71.69 | win | - |
| 2026-09-15 | 10:20:00 | AMD | break_and_retest | put | C | fired | 508.41 | 510.21 | scratch | - |
| 2026-09-15 | 10:20:00 | MSFT | break_and_retest | put | X | skipped_d | 499.02 | 499.10 | win | - |
| 2026-09-15 | 10:20:00 | COIN | break_and_retest | put | X | skipped_d | 178.44 | 179.04 | win | - |
| 2026-09-15 | 10:20:00 | HOOD | break_and_retest | put | X | skipped_d | 110.47 | 110.50 | loss | - |
| 2026-09-15 | 10:20:00 | UBER | break_and_retest | put | X | skipped_d | 71.55 | 71.69 | win | - |
| 2026-09-15 | 10:20:00 | TSM | break_and_retest | put | X | skipped_d | 415.79 | 416.01 | win | - |
| 2026-09-15 | 10:21:00 | AAPL | break_and_retest | put | X | skipped_d | 329.96 | 330.10 | loss | - |
| 2026-09-15 | 10:21:00 | META | one_candle_rule | put | X | skipped_d | 666.66 | 672.31 | loss | - |
| 2026-09-15 | 10:21:00 | HOOD | break_and_retest | put | X | skipped_d | 110.15 | 110.50 | loss | - |
| 2026-09-15 | 10:21:00 | UBER | break_and_retest | put | X | skipped_d | 71.38 | 71.69 | loss | - |
| 2026-09-15 | 10:22:00 | AMD | break_and_retest | put | C | fired | 507.38 | 510.21 | scratch | - |
| 2026-09-15 | 10:22:00 | HOOD | break_and_retest | put | X | skipped_d | 110.10 | 110.50 | loss | - |
| 2026-09-15 | 10:23:00 | HOOD | break_and_retest | put | X | skipped_d | 110.21 | 110.50 | loss | - |
| 2026-09-15 | 10:23:00 | MARA | break_and_retest | call | X | skipped_d | 11.25 | 11.24 | loss | - |
| 2026-09-15 | 10:24:00 | HOOD | break_and_retest | put | X | skipped_d | 110.38 | 110.50 | loss | - |
| 2026-09-15 | 10:24:00 | IREN | break_and_retest | put | X | skipped_d | 42.13 | 42.18 | loss | - |
| 2026-09-15 | 10:24:00 | IREN | one_candle_rule | put | X | skipped_d | 42.13 | 42.27 | win | - |
| 2026-09-15 | 10:24:00 | INTC | break_and_retest | put | X | skipped_d | 98.98 | 99.07 | loss | - |
| 2026-09-15 | 10:24:00 | MU | break_and_retest | call | X | skipped_d | 939.89 | 938.65 | loss | - |
| 2026-09-15 | 10:25:00 | AAPL | break_and_retest | put | X | skipped_d | 329.66 | 329.76 | loss | - |
| 2026-09-15 | 10:25:00 | AMD | break_and_retest | put | C | fired | 507.74 | 508.66 | loss | - |
| 2026-09-15 | 10:25:00 | AMD | break_and_retest | put | X | skipped_d | 507.74 | 508.12 | loss | - |
| 2026-09-15 | 10:25:00 | AMD | break_and_retest | put | C | skipped_tight_stop | 507.74 | 508.65 | loss | - |
| 2026-09-15 | 10:25:00 | HOOD | break_and_retest | put | X | skipped_d | 110.36 | 110.50 | loss | - |
| 2026-09-15 | 10:25:00 | IREN | break_and_retest | put | C | skipped_tight_stop | 41.99 | 42.18 | loss | - |
| 2026-09-15 | 10:25:00 | INTC | break_and_retest | put | X | skipped_d | 99.02 | 99.07 | loss | - |
| 2026-09-15 | 10:25:00 | AVGO | break_and_retest | put | X | skipped_d | 342.42 | 342.68 | loss | - |
| 2026-09-15 | 10:26:00 | NVDA | break_and_retest | put | X | skipped_d | 212.46 | 212.56 | loss | - |
| 2026-09-15 | 10:26:00 | AAPL | break_and_retest | put | X | skipped_d | 329.53 | 329.76 | loss | - |
| 2026-09-15 | 10:26:00 | HOOD | break_and_retest | put | X | skipped_d | 110.45 | 110.50 | loss | - |
| 2026-09-15 | 10:26:00 | IREN | break_and_retest | put | X | skipped_d | 42.08 | 42.18 | loss | - |
| 2026-09-15 | 10:26:00 | AVGO | break_and_retest | put | X | skipped_d | 342.37 | 342.68 | loss | - |
| 2026-09-15 | 10:26:00 | MARA | break_and_retest | call | X | skipped_d | 11.27 | 11.24 | loss | - |
| 2026-09-15 | 10:27:00 | NVDA | break_and_retest | put | X | skipped_d | 212.52 | 212.56 | loss | - |
| 2026-09-15 | 10:27:00 | AAPL | break_and_retest | put | X | skipped_d | 329.45 | 329.76 | loss | - |
| 2026-09-15 | 10:27:00 | AMD | break_and_retest | put | X | skipped_d | 507.63 | 508.66 | loss | - |
| 2026-09-15 | 10:27:00 | AMD | break_and_retest | put | X | skipped_d | 507.63 | 508.12 | loss | - |
| 2026-09-15 | 10:27:00 | AMD | break_and_retest | put | X | skipped_d | 507.63 | 508.65 | loss | - |
| 2026-09-15 | 10:27:00 | AMZN | break_and_retest | put | X | skipped_d | 249.73 | 249.82 | win | - |
| 2026-09-15 | 10:27:00 | INTC | break_and_retest | put | X | skipped_d | 99.14 | 99.20 | loss | - |
| 2026-09-15 | 10:27:00 | AVGO | break_and_retest | put | X | skipped_d | 342.53 | 342.68 | loss | - |
| 2026-09-15 | 10:27:00 | MARA | break_and_retest | call | X | skipped_d | 11.28 | 11.24 | loss | - |
| 2026-09-15 | 10:28:00 | AMD | break_and_retest | call | X | skipped_d | 508.27 | 507.36 | loss | - |
| 2026-09-15 | 10:28:00 | AMD | break_and_retest | put | X | skipped_d | 508.27 | 508.66 | loss | - |
| 2026-09-15 | 10:28:00 | AMD | break_and_retest | put | X | skipped_d | 508.27 | 508.65 | loss | - |
| 2026-09-15 | 10:28:00 | CRM | break_and_retest | put | X | skipped_d | 255.98 | 256.53 | loss | - |
| 2026-09-15 | 10:29:00 | AMD | break_and_retest | call | X | skipped_d | 508.68 | 507.36 | loss | - |
| 2026-09-15 | 10:29:00 | AMZN | break_and_retest | put | X | skipped_d | 249.60 | 249.82 | win | - |
| 2026-09-15 | 10:29:00 | COIN | break_and_retest | put | X | skipped_d | 178.40 | 178.43 | loss | - |
| 2026-09-15 | 10:29:00 | CRM | break_and_retest | put | X | skipped_d | 256.26 | 256.53 | loss | - |
| 2026-09-15 | 10:29:00 | MARA | break_and_retest | call | X | skipped_d | 11.25 | 11.24 | loss | - |
| 2026-09-15 | 10:30:00 | AMD | break_and_retest | put | C | skipped_tight_stop | 507.85 | 508.66 | loss | - |
| 2026-09-15 | 10:30:00 | AMD | break_and_retest | put | X | skipped_d | 507.85 | 508.12 | loss | - |
| 2026-09-15 | 10:30:00 | AMD | break_and_retest | put | C | skipped_tight_stop | 507.85 | 508.65 | loss | - |
| 2026-09-15 | 10:30:00 | AMZN | break_and_retest | put | B | fired | 249.41 | 249.82 | win | $848 |
| 2026-09-15 | 10:30:00 | PLTR | break_and_retest | put | X | skipped_d | 170.65 | 170.83 | loss | - |
| 2026-09-15 | 10:30:00 | COIN | break_and_retest | put | X | skipped_d | 178.13 | 178.43 | win | - |
| 2026-09-15 | 10:30:00 | NFLX | break_and_retest | put | X | skipped_d | 77.65 | 77.71 | loss | - |
| 2026-09-15 | 10:30:00 | NFLX | break_and_retest | put | X | skipped_d | 77.65 | 77.76 | loss | - |
| 2026-09-15 | 10:30:00 | CRM | break_and_retest | put | X | skipped_d | 256.30 | 256.53 | loss | - |
| 2026-09-15 | 10:31:00 | PLTR | break_and_retest | put | X | skipped_d | 170.69 | 170.83 | loss | - |
| 2026-09-15 | 10:31:00 | COIN | break_and_retest | put | X | skipped_d | 178.18 | 178.43 | win | - |
| 2026-09-15 | 10:31:00 | NFLX | break_and_retest | put | X | skipped_d | 77.64 | 77.71 | loss | - |
| 2026-09-15 | 10:31:00 | NFLX | break_and_retest | put | X | skipped_d | 77.64 | 77.76 | loss | - |
| 2026-09-15 | 10:31:00 | CRM | break_and_retest | put | X | skipped_d | 256.11 | 256.53 | loss | - |
| 2026-09-15 | 10:32:00 | AMD | break_and_retest | put | X | skipped_d | 508.60 | 508.66 | loss | - |
| 2026-09-15 | 10:32:00 | AMD | break_and_retest | put | X | skipped_d | 508.60 | 508.65 | loss | - |
| 2026-09-15 | 10:32:00 | PLTR | break_and_retest | put | X | skipped_d | 170.70 | 170.83 | loss | - |
| 2026-09-15 | 10:32:00 | COIN | break_and_retest | put | X | skipped_d | 177.88 | 178.43 | win | - |
| 2026-09-15 | 10:33:00 | AMD | break_and_retest | put | X | skipped_d | 508.10 | 508.66 | loss | - |
| 2026-09-15 | 10:33:00 | AMD | break_and_retest | put | X | skipped_d | 508.10 | 508.12 | loss | - |
| 2026-09-15 | 10:33:00 | AMD | break_and_retest | put | X | skipped_d | 508.10 | 508.65 | loss | - |
| 2026-09-15 | 10:33:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.68 | 344.71 | loss | - |
| 2026-09-15 | 10:33:00 | MSFT | break_and_retest | put | X | skipped_d | 498.85 | 499.10 | loss | - |
| 2026-09-15 | 10:33:00 | CRM | break_and_retest | put | X | skipped_d | 256.22 | 256.53 | loss | - |
| 2026-09-15 | 10:34:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.57 | 344.71 | loss | - |
| 2026-09-15 | 10:34:00 | CRM | break_and_retest | put | X | skipped_d | 256.20 | 256.53 | loss | - |
| 2026-09-15 | 10:35:00 | TSLA | break_and_retest | put | X | skipped_d | 358.71 | 358.80 | loss | - |
| 2026-09-15 | 10:35:00 | AAPL | break_and_retest | put | X | skipped_d | 329.40 | 329.41 | loss | - |
| 2026-09-15 | 10:35:00 | AAPL | break_and_retest | put | X | skipped_d | 329.40 | 329.42 | loss | - |
| 2026-09-15 | 10:35:00 | AMD | break_and_retest | put | X | skipped_d | 507.96 | 508.66 | loss | - |
| 2026-09-15 | 10:35:00 | AMD | break_and_retest | put | X | skipped_d | 507.96 | 508.12 | loss | - |
| 2026-09-15 | 10:35:00 | AMD | break_and_retest | put | X | skipped_d | 507.96 | 508.65 | loss | - |
| 2026-09-15 | 10:35:00 | MSFT | break_and_retest | put | X | skipped_d | 498.77 | 499.10 | loss | - |
| 2026-09-15 | 10:35:00 | PLTR | break_and_retest | put | X | skipped_d | 170.78 | 170.83 | loss | - |
| 2026-09-15 | 10:35:00 | HOOD | break_and_retest | put | X | skipped_d | 110.45 | 110.50 | loss | - |
| 2026-09-15 | 10:35:00 | AVGO | break_and_retest | put | X | skipped_d | 342.39 | 342.68 | win | - |
| 2026-09-15 | 10:35:00 | MU | break_and_retest | call | X | skipped_d | 938.70 | 938.65 | loss | - |
| 2026-09-15 | 10:36:00 | MSFT | break_and_retest | put | X | skipped_d | 498.90 | 499.10 | loss | - |
| 2026-09-15 | 10:36:00 | MU | break_and_retest | call | X | skipped_d | 940.85 | 938.65 | loss | - |
| 2026-09-15 | 10:36:00 | UBER | break_and_retest | put | X | skipped_d | 71.68 | 71.69 | loss | - |
| 2026-09-15 | 10:36:00 | CRM | break_and_retest | put | X | skipped_d | 256.43 | 256.53 | loss | - |
| 2026-09-15 | 10:37:00 | AAPL | break_and_retest | put | X | skipped_d | 329.24 | 329.41 | loss | - |
| 2026-09-15 | 10:37:00 | AAPL | break_and_retest | put | X | skipped_d | 329.24 | 329.42 | loss | - |
| 2026-09-15 | 10:37:00 | AAPL | break_and_retest | put | X | skipped_d | 329.24 | 329.29 | loss | - |
| 2026-09-15 | 10:37:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.56 | 344.71 | loss | - |
| 2026-09-15 | 10:37:00 | HOOD | break_and_retest | put | X | skipped_d | 110.13 | 110.50 | loss | - |
| 2026-09-15 | 10:37:00 | MU | break_and_retest | call | X | skipped_d | 939.36 | 938.65 | loss | - |
| 2026-09-15 | 10:37:00 | UBER | break_and_retest | put | X | skipped_d | 71.65 | 71.69 | loss | - |
| 2026-09-15 | 10:38:00 | NVDA | break_and_retest | call | X | skipped_d | 212.79 | 212.77 | loss | - |
| 2026-09-15 | 10:38:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.66 | 344.71 | loss | - |
| 2026-09-15 | 10:38:00 | HOOD | break_and_retest | put | X | skipped_d | 109.96 | 110.50 | loss | - |
| 2026-09-15 | 10:38:00 | CRM | break_and_retest | put | X | skipped_d | 256.24 | 256.53 | loss | - |
| 2026-09-15 | 10:39:00 | AAPL | break_and_retest | put | X | skipped_d | 329.36 | 329.41 | loss | - |
| 2026-09-15 | 10:39:00 | AAPL | break_and_retest | put | X | skipped_d | 329.36 | 329.42 | loss | - |
| 2026-09-15 | 10:39:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.36 | 344.71 | loss | - |
| 2026-09-15 | 10:40:00 | MSFT | break_and_retest | put | X | skipped_d | 499.06 | 499.10 | loss | - |
| 2026-09-15 | 10:41:00 | NVDA | break_and_retest | call | X | skipped_d | 212.78 | 212.77 | loss | - |
| 2026-09-15 | 10:42:00 | PLTR | break_and_retest | call | X | skipped_d | 171.05 | 170.92 | loss | - |
| 2026-09-15 | 10:42:00 | INTC | break_and_retest | put | X | skipped_d | 98.65 | 98.70 | loss | - |
| 2026-09-15 | 10:42:00 | AVGO | break_and_retest | put | X | skipped_d | 342.09 | 342.10 | loss | - |
| 2026-09-15 | 10:42:00 | AVGO | break_and_retest | put | X | skipped_d | 342.09 | 342.16 | loss | - |
| 2026-09-15 | 10:43:00 | AMD | break_and_retest | put | X | skipped_d | 505.95 | 506.64 | loss | - |
| 2026-09-15 | 10:43:00 | AMZN | break_and_retest | put | X | skipped_d | 248.80 | 249.02 | loss | - |
| 2026-09-15 | 10:43:00 | COIN | break_and_retest | put | X | skipped_d | 177.61 | 177.71 | loss | - |
| 2026-09-15 | 10:43:00 | INTC | break_and_retest | put | B | fired | 98.50 | 98.70 | loss | $-1000 |
| 2026-09-15 | 10:43:00 | AVGO | break_and_retest | put | X | skipped_d | 341.95 | 342.06 | loss | - |
| 2026-09-15 | 10:43:00 | AVGO | break_and_retest | put | X | skipped_d | 341.95 | 342.10 | loss | - |
| 2026-09-15 | 10:43:00 | AVGO | break_and_retest | put | X | skipped_d | 341.95 | 342.16 | loss | - |
| 2026-09-15 | 10:43:00 | TSM | break_and_retest | put | C | fired | 414.71 | 415.36 | loss | - |
| 2026-09-15 | 10:44:00 | AMZN | break_and_retest | put | X | skipped_d | 248.88 | 249.02 | win | - |
| 2026-09-15 | 10:44:00 | PLTR | one_candle_rule | call | X | skipped_d | 170.85 | 170.56 | loss | - |
| 2026-09-15 | 10:44:00 | COIN | break_and_retest | put | X | skipped_d | 177.38 | 177.71 | win | - |
| 2026-09-15 | 10:44:00 | AVGO | break_and_retest | put | X | skipped_d | 342.01 | 342.06 | loss | - |
| 2026-09-15 | 10:44:00 | AVGO | break_and_retest | put | X | skipped_d | 342.01 | 342.10 | loss | - |
| 2026-09-15 | 10:44:00 | AVGO | break_and_retest | put | X | skipped_d | 342.01 | 342.16 | loss | - |
| 2026-09-15 | 10:44:00 | MARA | break_and_retest | put | X | skipped_d | 11.15 | 11.16 | loss | - |
| 2026-09-15 | 10:45:00 | TSLA | break_and_retest | put | X | skipped_d | 358.00 | 358.11 | loss | - |
| 2026-09-15 | 10:45:00 | NVDA | break_and_retest | call | X | skipped_d | 212.79 | 212.77 | loss | - |
| 2026-09-15 | 10:45:00 | COIN | break_and_retest | put | B | fired | 177.06 | 177.71 | win | $309 |
| 2026-09-15 | 10:45:00 | HOOD | break_and_retest | put | X | skipped_d | 110.12 | 110.50 | loss | - |
| 2026-09-15 | 10:45:00 | TSM | break_and_retest | put | X | skipped_d | 415.00 | 415.36 | loss | - |
| 2026-09-15 | 10:45:00 | MARA | break_and_retest | put | X | skipped_d | 11.14 | 11.16 | win | - |
| 2026-09-15 | 10:45:00 | MARA | break_and_retest | put | X | skipped_d | 11.14 | 11.15 | loss | - |
| 2026-09-15 | 10:46:00 | TSLA | break_and_retest | put | X | skipped_d | 357.59 | 358.11 | loss | - |
| 2026-09-15 | 10:46:00 | AAPL | break_and_retest | put | X | skipped_d | 329.67 | 329.76 | loss | - |
| 2026-09-15 | 10:46:00 | PLTR | one_candle_rule | call | X | skipped_d | 170.80 | 170.56 | loss | - |
| 2026-09-15 | 10:46:00 | HOOD | break_and_retest | put | X | skipped_d | 109.89 | 110.12 | loss | - |
| 2026-09-15 | 10:46:00 | HOOD | break_and_retest | put | X | skipped_d | 109.89 | 110.00 | loss | - |
| 2026-09-15 | 10:46:00 | MARA | break_and_retest | put | X | skipped_d | 11.13 | 11.16 | win | - |
| 2026-09-15 | 10:46:00 | MARA | break_and_retest | put | X | skipped_d | 11.13 | 11.15 | loss | - |
| 2026-09-15 | 10:47:00 | TSLA | break_and_retest | put | B | fired | 357.52 | 358.11 | loss | $-1000 |
| 2026-09-15 | 10:47:00 | GOOGL | break_and_retest | put | X | skipped_d | 344.62 | 344.71 | win | - |
| 2026-09-15 | 10:47:00 | HOOD | break_and_retest | put | X | skipped_d | 109.97 | 110.00 | loss | - |
| 2026-09-15 | 10:47:00 | INTC | break_and_retest | put | X | skipped_d | 98.64 | 98.70 | loss | - |
| 2026-09-15 | 10:47:00 | MARA | break_and_retest | put | X | skipped_d | 11.13 | 11.15 | win | - |
| 2026-09-15 | 10:48:00 | AAPL | break_and_retest | put | X | skipped_d | 329.47 | 329.76 | loss | - |
| 2026-09-15 | 10:48:00 | HOOD | break_and_retest | put | X | skipped_d | 109.84 | 110.00 | loss | - |
| 2026-09-15 | 10:48:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 98.55 | 98.70 | loss | - |
| 2026-09-15 | 10:48:00 | AVGO | break_and_retest | put | X | skipped_d | 341.89 | 342.06 | win | - |
| 2026-09-15 | 10:48:00 | AVGO | break_and_retest | put | X | skipped_d | 341.89 | 342.29 | win | - |
| 2026-09-15 | 10:48:00 | AVGO | break_and_retest | put | X | skipped_d | 341.89 | 342.10 | win | - |
| 2026-09-15 | 10:48:00 | AVGO | break_and_retest | put | X | skipped_d | 341.89 | 342.16 | win | - |
| 2026-09-15 | 10:48:00 | TSM | break_and_retest | put | X | skipped_d | 415.23 | 415.49 | win | - |
| 2026-09-15 | 10:49:00 | AAPL | break_and_retest | put | X | skipped_d | 329.61 | 329.76 | loss | - |
| 2026-09-15 | 10:49:00 | AVGO | break_and_retest | put | B | fired | 341.64 | 342.06 | win | $827 |
| 2026-09-15 | 10:49:00 | AVGO | break_and_retest | put | B | fired | 341.64 | 342.10 | win | $754 |
| 2026-09-15 | 10:49:00 | AVGO | break_and_retest | put | C | fired | 341.64 | 342.16 | win | - |
| 2026-09-15 | 10:50:00 | AAPL | break_and_retest | put | X | skipped_d | 329.71 | 329.76 | loss | - |
| 2026-09-15 | 10:50:00 | AMD | break_and_retest | put | X | skipped_d | 506.18 | 506.64 | scratch | - |
| 2026-09-15 | 10:50:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 98.41 | 98.70 | loss | - |
| 2026-09-15 | 10:53:00 | AAPL | break_and_retest | put | X | skipped_d | 329.54 | 329.76 | loss | - |
| 2026-09-15 | 10:54:00 | AAPL | break_and_retest | put | X | skipped_d | 329.68 | 329.76 | loss | - |
| 2026-09-15 | 10:54:00 | CRM | break_and_retest | call | X | skipped_d | 256.85 | 256.79 | loss | - |
| 2026-09-15 | 10:55:00 | TSLA | break_and_retest | put | X | skipped_d | 356.59 | 356.66 | loss | - |
| 2026-09-15 | 10:55:00 | PLTR | break_and_retest | put | X | skipped_d | 170.63 | 170.67 | loss | - |
| 2026-09-15 | 10:55:00 | NFLX | break_and_retest | call | X | skipped_d | 77.92 | 77.92 | loss | - |
| 2026-09-15 | 10:55:00 | CRM | break_and_retest | call | X | skipped_d | 256.92 | 256.79 | loss | - |
| 2026-09-15 | 10:55:00 | CRM | break_and_retest | call | X | skipped_d | 256.92 | 256.65 | win | - |
| 2026-09-15 | 10:56:00 | NFLX | break_and_retest | call | X | skipped_d | 77.94 | 77.92 | loss | - |
| 2026-09-15 | 10:56:00 | CRM | break_and_retest | call | X | skipped_d | 256.90 | 256.79 | win | - |
| 2026-09-15 | 10:56:00 | CRM | break_and_retest | call | X | skipped_d | 256.90 | 256.65 | win | - |
| 2026-09-15 | 10:57:00 | GOOGL | one_candle_rule | put | X | skipped_d | 344.43 | 344.75 | loss | - |
| 2026-09-15 | 10:57:00 | NFLX | break_and_retest | call | X | skipped_d | 78.00 | 77.92 | loss | - |
| 2026-09-15 | 10:57:00 | CRM | break_and_retest | call | X | skipped_d | 256.92 | 256.79 | win | - |
| 2026-09-15 | 10:57:00 | CRM | break_and_retest | call | X | skipped_d | 256.92 | 256.65 | win | - |
| 2026-09-15 | 10:58:00 | INTC | break_and_retest | put | X | skipped_d | 98.42 | 98.50 | loss | - |
| 2026-09-15 | 10:58:00 | INTC | break_and_retest | put | X | skipped_d | 98.42 | 98.50 | loss | - |
| 2026-09-15 | 10:58:00 | NFLX | break_and_retest | call | C | skipped_tight_stop | 78.07 | 77.92 | loss | - |
| 2026-09-15 | 10:58:00 | CRM | break_and_retest | call | X | skipped_d | 257.02 | 256.79 | win | - |
| 2026-09-15 | 10:58:00 | CRM | break_and_retest | call | X | skipped_d | 257.02 | 256.65 | win | - |
| 2026-09-15 | 10:59:00 | GOOGL | break_and_retest | put | X | skipped_d | 343.90 | 344.24 | loss | - |
| 2026-09-15 | 10:59:00 | IREN | break_and_retest | put | X | skipped_d | 41.51 | 41.53 | loss | - |
| 2026-09-15 | 10:59:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 98.25 | 98.50 | loss | - |
| 2026-09-15 | 10:59:00 | INTC | break_and_retest | put | C | skipped_tight_stop | 98.25 | 98.50 | loss | - |

## Findings & Recommendations
- D-grade filter: filtered signals would have won 16% -> filter justified (<50%)
- 84% rule (Lesson 6 canonical 2026-07-06: solid B&R stop-out arms one re-entry on the reclaim close, ORIGINAL stop + target): 3 triggers, fired win rate 0%.
- 84% live wiring: armed per-symbol off paper stop-outs in live_scanner (2026-07-05). Requires --paper mode; signal-only runs have no stop-out feedback.
- Best setup: one_candle_rule (100%) | worst: reentry_84_rule (0%)
- C-grade alerts (12, alert-only per SPEC2) would have won 20% - similar to traded grades; alert-only demotion costs little.
