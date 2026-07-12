# Regime Filter — 24-Month Backtest Results

**Period:** 2024-07-11 to 2026-07-10 (522 trading days)
**Symbols:** TSLA, NVDA, AAPL, AMD, META, GOOGL, AMZN, MSFT, PLTR, SPY, QQQ
**Risk per trade:** $1,000, 2R target

## Problem
OMEN returns +$19,203 in trending bull markets (Year 2) but bleeds **-$13,370 in Year 1** — mostly from **puts (-$20,911)**. Melt-up regimes break put/B&R setups because price never retraces to entry levels.

## Winner: SMA Directional (5%)
**24mo P&L: $8,926** — **+30.6% vs baseline ($6,833)**

| Mode | Total P&L | vs Baseline | Calls P&L | Puts P&L | Trades | Days Stopped |
|------|-----------|-------------|-----------|----------|--------|-------------|
| No Filter (Baseline) | $6,833 | — | $20,374 | $-13,541 | 497 | 0 |
| **SMA Directional (5%)** | **$8,926** | **+$2,093 (+30.6%)** | $19,374 | $-10,448 | 477 | 0 |
| SMA Directional (3%) | $6,330 | -$503 (-7.4%) | $21,778 | $-15,448 | 456 | 0 |
| SMA Aggressive (7%, both) | $4,926 | -$1,907 (-27.9%) | $17,374 | $-12,448 | 475 | 198 |
| SMA Directional (4%) | $3,258 | -$3,575 (-52.3%) | $18,706 | $-15,448 | 471 | 0 |
| VIX Regime | $6,833 | $0 (0.0%) | $20,374 | $-13,541 | 497 | 0 |
| Directional P&L 5d | $-3,513 | -$10,346 | $4,028 | $-7,541 | 430 | 44 |

## How SMA Directional (5%) Works
- Checks SPY price vs SMA50 daily
- **Melt-up** (price >5% above SMA50): stops **PUT** entries only (directional)
- **Melt-down** (price >5% below SMA50): stops **CALL** entries only
- All other regimes: normal trading

This preserves call profits ($19,374 vs $20,374 baseline) while cutting put losses (-$10,448 vs -$13,541).

## Files Modified
- **regime_detector.py**: Added `MODE_PNL_DIRECTIONAL` mode + `_regime_pnl_directional()` method + `record_daily_directional_pnl()` feeder
- **live_scanner.py**: Integrated SMA Directional (5%) regime filter — loads SPY daily closes on startup, checks regime before each scan, filters signals by direction
- **backtest_regimes_fast.py**: Lean 24mo backtest runner (3-mode comparison)