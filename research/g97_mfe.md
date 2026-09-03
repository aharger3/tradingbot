# g97 -- maximum favourable excursion, bar-ordered

full lane, 444 first-of-day trades (54 dropped below `min_risk_floor`), 1R = |entry - stop|, window to 11:00. A bar that touches both target and stop is given to the stop.

| measure | mean | median |
|---|---:|---:|
| realised R (book) | +0.038 | -0.045 |
| **MFE while alive** | **+2.141** | **+1.015** |

Reached >=1R before any stop: **50.2%**. >=2R: **33.1%**. Stopped before 11:00: 73.9%.

| flat target | mean R | $/trade |
|---|---:|---:|
| 1.0R | +0.0059 | $+6 |
| 1.5R | +0.0484 | $+48 |
| 2.0R | +0.0396 | $+40 |
| 2.5R | +0.0982 | $+98 |
| 3.0R | +0.0840 | $+84 |
| 4.0R | +0.1533 | $+153 |

Best flat target **4.0R** at +0.1533R/trade against the book's own +0.0377R.
