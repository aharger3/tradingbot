# Per-pool recall (omen-3.9 T7)

Pool definitions from `config.yaml` — index (3), equity (14), everything else is "other".

| Pool | Marks | Fired recall | Any-signal recall | Raw-signal recall | Precision (engine→mark) |
|------|-------|-------------|-------------------|-------------------|------------------------|
| index | 71 | 7/71 = 9.9% | 30/71 = 42.3% | 32/71 = 45.1% | 8/19 = 42.1% |
| equity | 36 | 4/36 = 11.1% | 14/36 = 38.9% | 16/36 = 44.4% | 4/18 = 22.2% |
| other | 52 | 11/52 = 21.2% | 20/52 = 38.5% | 23/52 = 44.2% | 13/29 = 44.8% |

**Notes:**
- Index pool (QQQ, SPY, IWM) : 71 of 159 marks (44.7% of all S/A/X marks). Fired S recall on index marks is the dominant driver of overall S recall.
- Equity pool (14 high-options-volume US equities): 36 marks. Lower precision (22%) than index or other pools — the engine fires on more equity-pool bars that Austin doesn't mark.
- Other pool (remaining symbols not in either pool): 52 marks, highest fired recall (21.2%).

## Equity pool data-archive coverage

Of the 14 equity pool symbols, **12 have data_archive coverage** and 2 do not:

| Has archive | Symbols |
|---|---|
| ✅ 12/14 | NVDA, TSLA, PLTR, AAPL, MU, MSTR, AMZN, MSFT, INTC, AMD, GOOGL, META |
| ❌ 2/14 | SPCX, HTZ |

SPCX and HTZ have no data_archive directory at all — no historical bars exist to replay detection on. MSTR *does* have archive coverage (469 csv files as of 2026-08-09), contrary to the original `priority_pool.json` note which listed it as uncovered. No equity-pool mark exists for AAPL or MSTR in the marks file; all 36 equity-pool marks come from the other 10 symbols.

pools_configured: index=3 equity=14
equity_pool_measurable: 12/14