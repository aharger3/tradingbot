| figure | before | after | move |
|---|---:|---:|---:|
| signals detected | 45193 | 75953 | +30760 |
| **traded_count** | 1017 | 2595 | +1578 |
| **mean_r** | 0.8341 | 0.5481 | -0.2860 |
| **win_rate** (%) | 53.0632 | 43.0566 | -10.0 |
| total R | 848.3250 | 1422.3330 | +574.0 |
| profit factor | 2.4977 | 1.9732 | -0.52 |
| **months_green** (of 25) | 23 | 25 | +2 |
| max drawdown (R) | 14.9360 | 32.4300 | +17.5 |
| wins | 537 | 1110 | +573 |
| losses | 475 | 1468 | +993 |
| scratches | 5 | 17 | +12 |
| worst trade (R) | -1.2500 | -1.0000 | +0.250 |
| best trade (R) | 14.2640 | 24.3480 | +10.084 |
| losses booked at exactly -1.000R | 14 | 1460 | +1446 |
| losses booked worse than -1R | 460 | 0 | -460 |
| losses clamped at the -1.25R bound | 303 | 0 | -303 |
| index (ETF) trades | 18 | 137 | +119 |
| premarket-level trades | 203 | 357 | +154 |
| counter-day-trend traded rows (only recorded after R21) | 0 | 249 | +249 |
| symbols with at least one trade | 27 | 28 | +1 |
| traded, setup = break_and_retest | 947 | 1704 | +757 |
| traded, setup = one_candle_rule | 67 | 572 | +505 |
| traded, setup = reentry_84_rule | 3 | 319 | +316 |
| traded, level = other | 70 | 891 | +821 |
| traded, level = pivot low | 174 | 338 | +164 |
| traded, level = pivot high | 169 | 307 | +138 |
| traded, level = OR high | 156 | 267 | +111 |
| traded, level = OR low | 152 | 255 | +103 |
| traded, level = PMH | 98 | 184 | +86 |
| traded, level = PML | 105 | 173 | +68 |
| traded, level = PDH | 50 | 96 | +46 |
| traded, level = PDL | 43 | 84 | +41 |
| traded, engine grade = B | 1000 | 2447 | +1447 |
| traded, engine grade = A | 15 | 141 | +126 |
| traded, engine grade = A+ | 2 | 7 | +5 |
| traded, his S/A/C = C | 638 | 1677 | +1039 |
| traded, his S/A/C = A | 251 | 570 | +319 |
| traded, his S/A/C = S | 128 | 348 | +220 |

## Error bar

mean R moved **-0.2860 R**; the 95% bar on that move is **+/-0.1725 R** (sd 2.395 -> 2.337, n 1017 -> 2595).

Inside its own bar: **no - the move is real**.

## Reachability (method rule 3: under 1% or over 85% means the finding is the gate)

| condition | before | after |
|---|---:|---:|
| chase trips as a downgrade, all signals | not recorded | 7.5% |
| counter-day-trend, all signals (before = the CAP actually firing) | 0.0% | 25.5% |
| a level sits in the 2R path (before = the CAP actually firing) | 0.1% | 14.7% |
| scores S on his ladder, all signals | 16.5% | 13.1% |

The two `before` cells above are the rate at which those gates ACTUALLY CAPPED something: 9 of 45193 signals for counter-trend (0.0%) and 37 of 45193 for the level block (0.1%). Both are far under the 1% reachability floor. The 89.5% figure on his card was the rate at which the CONDITION was true, not the rate at which the gate changed a grade -- the cap only ran on signals already graded above C, and `_grade_pa` grades 95% of signals X. R21 and R25 removed two gates that were already almost dead; the book did not move because of them.

## What the new rows are worth (after book only)

| slice | trades | mean R | win rate |
|---|---:|---:|---:|
| whole book | 2595 | +0.5481 | 43.1% |
| break_and_retest | 1704 | +0.6024 | 47.4% |
| one_candle_rule (R3/R4) | 572 | +0.5913 | 37.7% |
| 84% re-entry (R6) | 319 | +0.1804 | 29.3% |
| premarket level (R23) | 357 | +0.4849 | 42.0% |
| counter day trend (R21) | 249 | +0.3512 | 15.1% |
| with day trend | 2346 | +0.5690 | 45.9% |
| index (ETF) | 137 | +0.9266 | 56.6% |
| his S | 348 | +0.2671 | 42.7% |
| his A | 570 | +0.6507 | 45.3% |
| his C | 1677 | +0.5716 | 42.4% |
| 2nd+ trade on its symbol-day (R16/R17) | 433 | +0.3744 | 31.9% |
| first trade on its symbol-day | 2162 | +0.5829 | 45.3% |

## Month by month (R)

| month | before | after |
|---|---:|---:|
| 2024-08 | +11.28 | +18.25 |
| 2024-09 | +3.32 | +11.04 |
| 2024-10 | +22.59 | +61.40 |
| 2024-11 | +26.54 | +57.41 |
| 2024-12 | +7.97 | +14.37 |
| 2025-01 | +25.48 | +51.23 |
| 2025-02 | +12.37 | +23.89 |
| 2025-03 | +39.21 | +49.38 |
| 2025-04 | +75.51 | +119.10 |
| 2025-05 | +17.11 | +14.27 |
| 2025-06 | -9.47 | +21.40 |
| 2025-07 | +36.11 | +51.86 |
| 2025-08 | +35.70 | +28.47 |
| 2025-09 | -6.07 | +6.01 |
| 2025-10 | +8.97 | +38.91 |
| 2025-11 | +59.88 | +65.71 |
| 2025-12 | +38.01 | +78.39 |
| 2026-01 | +39.38 | +99.77 |
| 2026-02 | +44.26 | +53.72 |
| 2026-03 | +31.45 | +71.44 |
| 2026-04 | +43.05 | +59.05 |
| 2026-05 | +73.54 | +82.44 |
| 2026-06 | +53.33 | +125.07 |
| 2026-07 | +98.13 | +152.17 |
| 2026-08 | +60.66 | +67.57 |

## Symbol spread (traded count, after)

| symbol | before | after |
|---|---:|---:|
| COIN | 104 | 215 |
| PLTR | 77 | 172 |
| MU | 82 | 166 |
| AMD | 69 | 160 |
| HOOD | 75 | 155 |
| TSLA | 75 | 148 |
| ORCL | 52 | 135 |
| AVGO | 55 | 135 |
| NVDA | 48 | 126 |
| IREN | 52 | 105 |
| NFLX | 30 | 99 |
| META | 42 | 97 |
| AAPL | 19 | 96 |
| AMZN | 33 | 89 |
| MSFT | 29 | 84 |
| BABA | 16 | 77 |
| INTC | 30 | 74 |
| GOOGL | 21 | 72 |
| TSM | 27 | 69 |
| IWM | 5 | 60 |
| UBER | 26 | 60 |
| CRM | 18 | 55 |
| SPY | 4 | 41 |
| QQQ | 9 | 36 |
| SPCX | 15 | 23 |
| SOFI | 2 | 21 |
| ACHR | 2 | 13 |
| MARA | 0 | 12 |
