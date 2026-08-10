# T3 Archive Coverage Report

**Date:** 2026-08-10
**Pool:** equity_pool (14) + index_pool (3) = 17 symbols
**Common start target:** 2024-01-02
**Most recent target:** 2026-08-10

## Symbol coverage

| Symbol | Pool | Old first | Old last | New first | New last | Symbol-days added |
|--------|------|-----------|----------|-----------|----------|------------------:|
| AAPL | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| AMD | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| AMZN | equity | 2024-02-20 | 2026-07-17 | 2024-01-02 | 2026-08-10 | 53 |
| GOOGL | equity | 2024-02-26 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 58 |
| INTC | equity | 2024-08-13 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 175 |
| META | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| MSFT | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| MSTR | equity | 2024-08-26 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 184 |
| MU | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| NVDA | equity | 2024-02-20 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 54 |
| PLTR | equity | 2024-07-10 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 151 |
| SPCX | equity | — | — | 2024-01-02 | 2026-08-10 | 527 |
| TSLA | equity | 2024-01-12 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 76 |
| QQQ | index | 2024-01-04 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 51 |
| SPY | index | 2024-02-22 | 2026-07-10 | 2024-01-02 | 2026-08-10 | 102 |
| IWM | index | 2024-02-28 | 2026-07-24 | 2024-01-02 | 2026-08-10 | 237 |

symbol_days_added: 1933

**Notes:**
- SPCX is new — 527 symbol-days from common start to most recent trading day (some early dates return zero bars from Polygon, which is expected for a symbol that may not have traded every day in 2024).
- All 16 existing symbols now start from 2024-01-02 and extend to 2026-08-10.
- Every symbol now covers 2024-01-02 through 2026-08-10 (653 potential trading days).
- Backward extension was the primary source of new data for older symbols (AAPL, AMD, etc. gained ~35 days going back to Jan 2024).
- Forward extension added ~20 trading days per symbol (2026-07-11 through 2026-08-10).

## SPCX shape validation

SPCX entries in `data_archive/SPCX/` are identical in format and naming to
existing equity_pool symbols: per-date CSV files with Datetime,Open,High,Low,
Close,Adj Close,Volume columns sourced from Polygon.io's 1-minute aggregate
bars.