# T8 -- what it would take to answer the tier question

Over 501 trading days. n is per group for 80% power at a=.05 against the gap actually observed; years assumes the bucket keeps firing at its current rate and 252 trading days a year.

| contrast | observed gap | n needed per side | have | slower side fires | years to reach it |
|---|---|---|---|---|---|
| S+ vs S | -0.313R | 969 | 63 / 39 | S at 0.08/day | **49** |
| S+ vs A | -0.792R | 163 | 63 / 15 | A at 0.03/day | **22** |
| S vs C | +0.301R | 892 | 39 / 1313 | S at 0.08/day | **45** |
| A vs C | +0.781R | 145 | 15 / 1313 | A at 0.03/day | **19** |
| MAJOR_15 vs OTHER_POOL | -0.086R | 11,764 | 605 / 424 | OTHER_POOL at 0.85/day | **55** |

Reading it: the S-tier contrasts are not close to answerable on P&L. The variance of a ladder-B R distribution is large enough that separating two buckets whose true gap is a few tenths of an R takes thousands of trades per side, and the S tiers fire well under one a day between them. **Tier quality has to be judged on agreement with Austin's own grades (T9's eye-match), not on backtest P&L** -- P&L will not resolve it this decade.

The pool contrast is the one that is merely slow rather than hopeless: both pools fire often, so it is a matter of more history rather than a different kind of measurement.
