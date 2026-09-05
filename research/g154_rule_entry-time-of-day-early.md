# g154/F5 -- entry-time-of-day-early

**What is different now:** tested Austin's "earlier in the day is better, no new entries past ~11:00" claim as a selection ceiling (keep only candidates at or before T) over the honest book, and it is **not** the money-losing floor removal the claim's original 09:40 TRADE_FLOOR citation implied -- that flag is deleted (`live_scanner.py:759`, `backtest_week` never had one) and only 487 of 10,830 fired rows precede 09:40 anyway.

Book `bt2y_trades_retest_on.json`, 498 sessions (H1 249 / H2 249), size-gated on `signal_runner.min_risk_floor`. 1R = $1000. H1/H2 split at 2025-09-01.

## Baseline -- first sized candidate of the day, any time

| $/day | mean R | win | months green | max DD | cand/day | fires/day | recall_100 | recall_all | precision |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| $34 | +0.034 | 46.5% | 13/25 | $-21405 | 16.5 | 1.000 | 15/34 | 169/341 | 18/59 |

## S-indicator arm (keep candidates at or before T)

| T | $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD | cand/day | fires/day | recall_100 | recall_all | precision | survivor |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 09:45 | $14 | $99 | $-72 | +0.015 | 45.7% | 13/25 | $-21583 | 3.4 | 0.920 | 5/34 | 63/341 | 17/55 | False |
| 10:00 | $38 | $144 | $-68 | +0.038 | 46.7% | 13/25 | $-21405 | 7.8 | 0.996 | 10/34 | 117/341 | 18/59 | False |
| 10:30 | $34 | $136 | $-68 | +0.034 | 46.5% | 13/25 | $-21405 | 13.5 | 1.000 | 14/34 | 154/341 | 18/59 | False |
| 11:00 (control) | $34 | $136 | $-68 | +0.034 | 46.5% | 13/25 | $-21405 | 16.5 | 1.000 | 15/34 | 169/341 | 18/59 | False |

## Refusal-indicator mirror (skip early, take first after T)

Not the direction his claim asks for -- reported so a T that only helps because late trades are bad on their own isn't credited to "early is good".

| T | $/day | mean R | win |
|---|---:|---:|---:|
| 09:45 | $-65 | -0.065 | 46.1% |
| 10:00 | $-80 | -0.081 | 37.1% |
| 10:30 | $-68 | -0.082 | 34.9% |
| 11:00 | n/a (0 trades) | -- | -- |

## Verdict

Best-performing non-control threshold: **T=10:00**. Survivor (H1 and H2 both improve $/day or precision, recall_100 not below baseline): **False**.

g110_time_of_day.py already scanned this same book for the best arrival threshold and found the OPPOSITE sign: "first at/after 10:40" beat "first regardless" ($68/day vs $34/day). That is evidence late candidates carry more edge, not that early ones do -- this table is the direct check of Austin's own claim on the same book, not a re-litigation of g110.
