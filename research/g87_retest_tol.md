# g87 -- the retest tolerance, stress tested

> Austin, 2026-08-30: *"it doesn't follow the 25 percent candle unit, its just if its close but didnt actually touch, within a few cents give or take, you stress test and find the best metric yourself."*

A resting buy limit sits `tol` **above** the level so a near-miss still fills. One pass over `bt2y_trades.json`, 9322 candidates, 500 sessions. Every exit is the shipped ladder; only the resting price moves. Bar: **$397/day**.

| arm | $/day | 95% band | % of bar | win | mean R | green | fill rate | bars early | unsizeable |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| BOOK | $64 | [$-43, $175] | 16.1% | 46.9% | +0.064 | 13/25 | 100.0% | None | 14.5% |
| **AT_LEVEL | $469 | [$272, $678] | 118.1% | 37.7% | +0.556 | 19/25 | 84.4% | 2 | 84.9% |
| cents_0.02 | $-162 | [$-231, $-90] | -40.8% | 18.0% | -0.471 | 4/25 | 34.4% | 2 | 97.6% |
| cents_0.05 | $-175 | [$-243, $-106] | -44.1% | 18.1% | -0.495 | 4/25 | 35.4% | 3 | 97.5% |
| cents_0.10 | $-324 | [$-431, $-210] | -81.6% | 15.2% | -0.466 | 4/25 | 69.6% | 3 | 92.6% |
| cents_0.20 | $-475 | [$-587, $-357] | -119.6% | 17.1% | -0.498 | 2/25 | 95.4% | 3 | 81.9% |
| bps_2 | $-167 | [$-236, $-94] | -42.1% | 17.8% | -0.479 | 4/25 | 34.8% | 2 | 97.3% |
| bps_5 | $-179 | [$-246, $-109] | -45.1% | 18.0% | -0.503 | 4/25 | 35.6% | 3 | 97.4% |
| bps_10 | $-188 | [$-253, $-120] | -47.4% | 18.1% | -0.516 | 3/25 | 36.4% | 3 | 97.4% |
| bps_20 | $-530 | [$-628, $-426] | -133.5% | 15.9% | -0.532 | 1/25 | 99.6% | 3 | 51.7% |
| prevrange_0.10 | $-180 | [$-248, $-110] | -45.3% | 17.0% | -0.513 | 3/25 | 35.2% | 3 | 97.4% |
| prevrange_0.25 | $-271 | [$-407, $-114] | -68.3% | 12.1% | -0.432 | 5/25 | 62.8% | 3 | 93.6% |
| prevrange_0.50 | $-518 | [$-616, $-413] | -130.5% | 16.6% | -0.543 | 1/25 | 95.4% | 3 | 74.8% |
| atr_0.05 | $-171 | [$-234, $-103] | -43.1% | 17.3% | -0.508 | 4/25 | 33.6% | 2 | 97.5% |
| atr_0.10 | $-193 | [$-258, $-125] | -48.6% | 16.3% | -0.542 | 2/25 | 35.6% | 3 | 97.4% |
| atr_0.25 | $-322 | [$-444, $-191] | -81.1% | 15.3% | -0.419 | 3/25 | 77.0% | 3 | 89.6% |
| AT_LEVEL|struct | $-151 | [$-214, $-84] | -38.0% | 17.5% | -0.490 | 4/25 | 30.8% | 5 | 77.0% |
| cents_0.02|struct | $-144 | [$-213, $-74] | -36.3% | 17.9% | -0.463 | 4/25 | 31.2% | 2 | 97.7% |
| cents_0.05|struct | $-159 | [$-225, $-91] | -40.1% | 17.9% | -0.491 | 3/25 | 32.4% | 3 | 97.7% |
| cents_0.10|struct | $-309 | [$-416, $-192] | -77.8% | 15.4% | -0.447 | 4/25 | 69.0% | 3 | 92.7% |
| cents_0.20|struct | $-475 | [$-587, $-357] | -119.6% | 17.1% | -0.498 | 2/25 | 95.4% | 3 | 82.0% |
| bps_2|struct | $-151 | [$-219, $-80] | -38.0% | 17.6% | -0.474 | 4/25 | 31.8% | 2 | 97.5% |
| bps_5|struct | $-163 | [$-229, $-94] | -41.1% | 17.8% | -0.500 | 3/25 | 32.6% | 3 | 97.6% |
| bps_10|struct | $-172 | [$-236, $-105] | -43.3% | 18.0% | -0.515 | 3/25 | 33.4% | 3 | 97.6% |
| bps_20|struct | $-530 | [$-628, $-426] | -133.5% | 15.9% | -0.532 | 1/25 | 99.6% | 3 | 51.4% |
| prevrange_0.10|struct | $-163 | [$-229, $-93] | -41.1% | 16.9% | -0.508 | 3/25 | 32.0% | 2 | 97.6% |
| prevrange_0.25|struct | $-271 | [$-407, $-114] | -68.3% | 11.4% | -0.442 | 5/25 | 61.4% | 3 | 93.8% |
| prevrange_0.50|struct | $-518 | [$-616, $-413] | -130.5% | 16.6% | -0.543 | 1/25 | 95.4% | 3 | 74.8% |
| atr_0.05|struct | $-152 | [$-214, $-85] | -38.3% | 17.6% | -0.496 | 4/25 | 30.6% | 2 | 97.6% |
| atr_0.10|struct | $-174 | [$-237, $-108] | -43.8% | 16.6% | -0.534 | 1/25 | 32.6% | 3 | 97.6% |
| atr_0.25|struct | $-318 | [$-440, $-188] | -80.1% | 15.4% | -0.416 | 3/25 | 76.6% | 3 | 89.7% |

`BOOK` is the shipped fill on this book (control). `AT_LEVEL` is a resting limit exactly at the level -- tolerance zero, the thing Austin says is wrong. Everything below it is his near-miss rule at a different size.

**Every arm is SIZE GATED** (`signal_runner.min_risk_floor`). 1R is a fixed $1,000, so a fill landing a cent from its stop is a 100,000-share position and an R-multiple with a one-cent denominator. Ungated, this sweep prints four-figure and five-figure days that are arithmetic, not money -- the `unsizeable` column is how much of each arm that would have been, and `ungated_oneaday_per_day` in the JSON is what it would have falsely claimed.

**Read the 95%% bands before picking a winner.** The standing error bar on this project is +/-1.5799R; arms whose bands overlap are a tie no matter how the point estimates sort.

