# G7.1/labels -- the setup name and the level name, on every trade row

> *"so in homework also tell me what setup you think it is"*
> *"remember BR and OCR is also a setup when both of them are together."*
> -- Austin, 2026-08-29

**What changed.** Both fields already existed on every signal inside the engine and were thrown away one line later, when the signal was turned into a trade row (`research/g71_labeller.md`). Nothing new is computed. `backtest_week.SimTrade` now carries `setup_type` and `stop_level_name` through instead of dropping them, and `backtest_2y.py` writes them onto every row as `setup_label` and `level_name` (plus `level_tf`, `entry_tf`, `bias_tf`, `level_px`). No fill, no grade and no P&L moved -- this is a relabelling of the same 4508 trades.

**Correction to the earlier diagnosis:** `research/g71_labeller.md` still guessed the opening range belonged in Austin's six levels. Asked directly later the same day, his answer is **PDH, PDL, PMH, PML, HOD, LOD** -- the opening range is not one of them (`Projects/omen-rulebook.md`, "The six levels, named at last"). This report uses the corrected six.

Book: `C:\Users\aharg\Desktop\Projects\tradingbot\research\bt2y_trades.json`, generated 2026-08-29T17:06:27, 500 sessions 2024-08-21..2026-08-21, 4508 traded rows.

## Setup, across the 2-year book

| setup | trades | share |
|---|---:|---:|
| BR+OCR | 2993 | 66.4% |
| break-and-retest | 1168 | 25.9% |
| other (84% re-entry) | 206 | 4.6% |
| one-candle-rule | 141 | 3.1% |
| **all** | **4508** | |

## Level, against his six

| level | trades | share |
|---|---:|---:|
| not-his: pivot high | 714 | 15.8% |
| not-his: pivot low | 687 | 15.2% |
| not-his: OR high | 603 | 13.4% |
| not-his: OR low | 572 | 12.7% |
| not-his: order block | 482 | 10.7% |
| PMH | 423 | 9.4% |
| PML | 385 | 8.5% |
| PDH | 229 | 5.1% |
| PDL | 207 | 4.6% |
| not-his: prior entry (84%) | 206 | 4.6% |

**His six coverage: 1244 / 4508 = 27.6%.**

## 20-row sample

Round-robin across setup classes, oldest first, so no class is crowded out by BR+OCR's 60% share. `eng` = legacy A+/A/B/C/X ladder, `aus` = Austin's S/A/C ladder -- both, never mixed.

| sym | day | et | side | setup | level | level px | entry TF | level TF | eng | aus | R | out |
|---|---|---|---|---|---|---:|---|---|---|---|---:|---|
| AMD | 2024-08-21 | 09:44 | L | break-and-retest | not-his: OR high | 156.64 | 1m | 5m opening range | B | C | -1.000 | loss |
| NVDA | 2024-08-21 | 09:46 | L | BR+OCR | not-his: OR high | 127.87 | 1m | 5m opening range | B | C | +0.452 | win |
| COIN | 2024-08-21 | 09:49 | S | BR+OCR | not-his: pivot low @09:38 | 196.42 | 1m | 1m intraday swing | B | C | -1.000 | loss |
| BABA | 2024-08-21 | 09:58 | L | BR+OCR | not-his: pivot high @09:49 | 82.34 | 1m | 1m intraday swing | B | S | +1.875 | win |
| SPY | 2024-08-21 | 10:03 | L | BR+OCR | not-his: order block | 560.36 | 1m | 1m single candle | A | C | -1.000 | loss |
| COIN | 2024-08-21 | 10:04 | L | break-and-retest | not-his: pivot high @09:36 | 197.95 | 1m | 1m intraday swing | B | C | +2.052 | win |
| AMD | 2024-08-21 | 10:10 | L | one-candle-rule | not-his: order block | 156.99 | 1m | 1m single candle | B | C | -1.000 | loss |
| AAPL | 2024-08-21 | 10:11 | L | BR+OCR | not-his: order block | 227.36 | 1m | 1m single candle | A | S | -1.000 | loss |
| AVGO | 2024-08-21 | 10:24 | S | break-and-retest | not-his: OR low | 164.75 | 1m | 5m opening range | B | C | -1.000 | loss |
| AMD | 2024-08-21 | 10:30 | L | other (84% re-entry) | not-his: prior entry (84%) | 156.99 | 1m | 1m failed entry | B | C | -1.000 | loss |
| TSLA | 2024-08-22 | 09:38 | S | break-and-retest | PML | 222.60 | 1m | 1m premarket | B | A | -1.000 | loss |
| NVDA | 2024-08-23 | 09:59 | L | break-and-retest | not-his: pivot high @09:40 | 127.22 | 1m | 1m intraday swing | B | C | +2.115 | win |
| AMD | 2024-08-28 | 09:52 | S | other (84% re-entry) | not-his: prior entry (84%) | 148.58 | 1m | 1m failed entry | B | C | +0.531 | win |
| QQQ | 2024-08-28 | 10:03 | S | one-candle-rule | not-his: order block | 474.55 | 1m | 1m single candle | B | C | +0.580 | win |
| META | 2024-08-30 | 10:21 | S | other (84% re-entry) | not-his: prior entry (84%) | 519.70 | 1m | 1m failed entry | B | A | -1.000 | loss |
| MSFT | 2024-09-03 | 10:08 | L | one-candle-rule | not-his: order block | 416.74 | 1m | 1m single candle | B | C | -1.000 | loss |
| NFLX | 2024-09-05 | 10:11 | S | one-candle-rule | not-his: order block | 68.14 | 1m | 1m single candle | B | C | -1.000 | loss |
| AVGO | 2024-09-09 | 10:24 | S | other (84% re-entry) | not-his: prior entry (84%) | 137.70 | 1m | 1m failed entry | B | S | +2.529 | win |
| AAPL | 2024-09-10 | 10:34 | L | one-candle-rule | not-his: order block | 219.37 | 1m | 1m single candle | B | C | -1.000 | loss |
| AMD | 2024-09-10 | 10:49 | L | other (84% re-entry) | not-his: prior entry (84%) | 138.60 | 1m | 1m failed entry | B | A | -1.000 | loss |

Reproduce with `python research/g72_labels_report.py`.
