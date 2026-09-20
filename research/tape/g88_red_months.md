# g88 POST_floor red months
`bt2y_trades_retest_on.json` POST_floor arm, re-derived per-trade (`research/tape/g88_post_floor_trades.json.gz`). Matches vault verdict: $256/day, 27.5% win, 16/25 green.

| month | $ | trades | win% |
|---|--:|--:|--:|
| 2024-09 | -1735 | 20 | 20.0 RED |
| 2024-10 | 18951 | 23 | 34.8 |
| 2024-11 | -10221 | 20 | 10.0 RED |
| 2024-12 | 261 | 21 | 28.6 |
| 2025-01 | 11210 | 20 | 20.0 |
| 2025-02 | 9348 | 19 | 21.1 |
| 2025-03 | -1848 | 21 | 33.3 RED |
| 2025-04 | -7915 | 21 | 19.0 RED |
| 2025-05 | 11307 | 21 | 42.9 |
| 2025-06 | -4830 | 20 | 20.0 RED |
| 2025-07 | 3208 | 22 | 22.7 |
| 2025-08 | 12505 | 21 | 38.1 |
| 2025-09 | -1142 | 21 | 23.8 RED |
| 2025-10 | -14443 | 23 | 13.0 RED |
| 2025-11 | 1546 | 19 | 31.6 |
| 2025-12 | 1557 | 22 | 18.2 |
| 2026-01 | -10872 | 20 | 15.0 RED |
| 2026-02 | 6160 | 19 | 31.6 |
| 2026-03 | 15734 | 22 | 45.5 |
| 2026-04 | 15103 | 21 | 47.6 |
| 2026-05 | 7354 | 20 | 25.0 |
| 2026-06 | 23781 | 21 | 33.3 |
| 2026-07 | 30396 | 22 | 36.4 |
| 2026-08 | 14116 | 17 | 29.4 |
| 2026-09 | -2000 | 2 | 0.0 RED |

**9 red**: 2024-09, 2024-11, 2025-03, 2025-04, 2025-06, 2025-09, 2025-10, 2026-01, 2026-09.

**(a) 1-3 symbols dominate?** No. Worst-3 syms carry 35-58% (avg ~43%) of each red month's loss but differ month to month; only AVGO recurs (top-3 in 3/9). Flag test: none of the three — no symbol-scoped gate exists; `OCR_STRICT` cuts volume broadly, not a real test.

**(b) more counter-trend?** No, opposite: red months avg **31.4%** counter-trend (via `aligned` field) vs **40.1%** in green (overall 38.4%). Flag test: `COUNTER_TREND_CAP` + `HTF_BIAS_GATE` cap counter-trend/bias setups — since red months already run leaner here, capping would trim green months more and likely hurt.

**(c) weekday/week-of-month clustering?** Yes, some. "Mid" week-of-month (days 8-21) carries **70.7%** of red-month losses (-$38.9k/-$55.0k) vs ~56% share of overall profit. Thursday worst weekday (-$17.5k, 31.9% of red loss) vs ~20% of trading days. Flag test: none of the three — no calendar-gated flag exists (`day_policy` is hardcoded); needs a new flag.

**Bottom line**: only (c) has signal and no candidate flag tests it; (b) is falsified (its flags would hurt); (a) is diffuse (`OCR_STRICT` is the only loose lever, not targeted).
