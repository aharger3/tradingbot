# T5 Universe — Three-Pool Split (omen-5.0)

**Date:** 2026-08-11

## Summary

Created `universe.py` as the single source of truth for all three tracked
symbol pools. Removed MSTR from every pool. Added ACHR, NFLX, ORCL to MAJOR_15.

## Pools

| Pool | Count | Symbols |
|------|-------|---------|
| MAJOR_15 | 15 | NVDA, TSLA, AAPL, SPCX, MSFT, MU, INTC, PLTR, AMZN, META, AMD, GOOGL, ACHR, NFLX, ORCL |
| INDEX_POOL | 3 | QQQ, SPY, IWM |
| OTHER_POOL | 11 | GOOG, SOFI, COIN, HOOD, IREN, AVGO, UBER, BABA, CRM, TSM, MARA |

## Data archive coverage for new MAJOR_15 members

Checked `data_archive/` as of 2026-08-11:

| Symbol | Days |
|--------|-----:|
| ACHR | **0** |
| NFLX | 507 |
| ORCL | 274 |

ACHR has zero days in the archive — it cannot be backtested until T6 (data
ingestion for new symbols) lands. NFLX and ORCL have existing coverage from
the old archive_1m SYMBOLS list; widen commands will fill gaps automatically.

## Consumers rewired

| File | Before | After |
|------|--------|-------|
| `_t3_stage.py` | Own `EQUITY_POOL` (13 syms) | `from universe import ALL_SYMS` |
| `archive_1m.py` | Own `SYMBOLS` (29 syms) | `from universe import ALL_SYMS` |
| `build_corpus_instances.py` | Own `SYMBOLS` (28 syms + ARM/QCOM/IWM) | `from universe import ALL_SYMS` (+ ARM/QCOM extras) |
| `live_scanner.py` | Own `DEFAULT_SYMBOLS` (27 syms) | `from universe import MAJOR_15, INDEX_POOL, OTHER_POOL` |

MSTR removed from all consumers. `live_scanner.py` now tags every signal with
a `pool` field for per-pool tracking.