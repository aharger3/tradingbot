# T8 -- is the tier inversion real, or is it n?

Bootstrap 95% CIs (20,000 resamples) and two-sided permutation tests (20,000 shuffles) on the two results Austin did not expect: S+ below S and A, and OTHER_POOL above MAJOR_15. Everything is R per trade at $1,000 risk. Seeded, so these numbers reproduce.

## Every bucket with its uncertainty

| bucket | trades | EV | 95% CI | width | win rate | 95% CI |
|---|---|---|---|---|---|---|
| **S+** | 63 | +0.786R | [+0.182, +1.497] | 1.316R | 47.6% | [35.8%, 59.7%] |
| **S** | 39 | +1.099R | [+0.425, +1.814] | 1.390R | 57.9% | [42.2%, 72.1%] |
| **A** | 15 | +1.579R | [+0.383, +2.832] | 2.450R | 60.0% | [35.7%, 80.2%] |
| **C** | 1313 | +0.798R | [+0.674, +0.925] | 0.252R | 51.2% | [48.4%, 53.9%] |
| **MAJOR_15** | 605 | +0.893R | [+0.720, +1.074] | 0.354R | 56.6% | [52.6%, 60.5%] |
| **INDEX_POOL** | 18 | +0.093R | [-0.382, +0.583] | 0.965R | 55.6% | [33.7%, 75.4%] |
| **OTHER_POOL** | 424 | +0.979R | [+0.749, +1.213] | 0.464R | 53.9% | [49.1%, 58.6%] |

A CI that straddles the other bucket's point estimate means the two are not separated by this data. Width is the honest measure of how little the small buckets say.

## The contrasts Austin asked about

| contrast | n | n | EV gap | p (permutation) | smallest gap detectable at this n |
|---|---|---|---|---|---|
| S+ vs S (the ranking rule itself) | 63 | 39 | -0.313R | 0.558 | 1.369R |
| S+ vs A | 63 | 15 | -0.792R | 0.304 | 1.985R |
| S+ vs C | 63 | 1313 | -0.012R | 0.970 | 0.963R |
| S vs C | 39 | 1313 | +0.301R | 0.418 | 1.006R |
| A vs C | 15 | 1313 | +0.781R | 0.194 | 1.755R |
| all S-family (S+/S/A) vs C | 117 | 1313 | +0.194R | 0.385 | 0.675R |
| MAJOR_15 vs OTHER_POOL | 605 | 424 | -0.086R | 0.561 | 0.419R |

## How much rides on single symbols

Leave-one-symbol-out: the pool's EV recomputed with that symbol removed. A pool whose edge is one name is not a pool result.

**MAJOR_15** (EV +0.893R) -- biggest movers when dropped:

| symbol | trades | pool EV without it | change |
|---|---|---|---|
| MU | 75 | +0.846R | -0.047R |
| PLTR | 84 | +0.856R | -0.037R |
| SPCX | 7 | +0.867R | -0.026R |
| AMZN | 34 | +0.924R | +0.031R |
| TSLA | 66 | +0.925R | +0.032R |
| AMD | 66 | +0.931R | +0.038R |

**OTHER_POOL** (EV +0.979R) -- biggest movers when dropped:

| symbol | trades | pool EV without it | change |
|---|---|---|---|
| HOOD | 74 | +0.853R | -0.126R |
| UBER | 29 | +0.910R | -0.068R |
| AVGO | 62 | +0.942R | -0.036R |
| BABA | 27 | +1.002R | +0.023R |
| IREN | 54 | +1.017R | +0.039R |
| COIN | 104 | +1.154R | +0.176R |

## Per-symbol EV (traded)

| symbol | pool | trades | EV | win rate |
|---|---|---|---|---|
| SPCX | MAJOR_15 | 7 | +3.143R | 71.4% |
| UBER | OTHER_POOL | 29 | +1.910R | 67.9% |
| HOOD | OTHER_POOL | 74 | +1.572R | 59.5% |
| ACHR | MAJOR_15 | 2 | +1.279R | 100.0% |
| INTC | MAJOR_15 | 20 | +1.249R | 60.0% |
| CRM | OTHER_POOL | 28 | +1.231R | 66.7% |
| MU | MAJOR_15 | 75 | +1.223R | 54.7% |
| META | MAJOR_15 | 46 | +1.211R | 71.1% |
| AVGO | OTHER_POOL | 62 | +1.192R | 54.8% |
| PLTR | MAJOR_15 | 84 | +1.122R | 54.8% |
| NFLX | MAJOR_15 | 31 | +1.060R | 58.1% |
| ORCL | MAJOR_15 | 48 | +0.967R | 56.2% |
| TSM | OTHER_POOL | 32 | +0.904R | 67.7% |
| NVDA | MAJOR_15 | 49 | +0.719R | 57.1% |
| IREN | OTHER_POOL | 54 | +0.713R | 40.7% |
| MSFT | MAJOR_15 | 32 | +0.660R | 62.5% |
| BABA | OTHER_POOL | 27 | +0.637R | 55.6% |
| TSLA | MAJOR_15 | 66 | +0.628R | 50.0% |
| SOFI | OTHER_POOL | 11 | +0.591R | 72.7% |
| AMD | MAJOR_15 | 66 | +0.582R | 51.5% |
| GOOGL | MAJOR_15 | 25 | +0.551R | 56.0% |
| COIN | OTHER_POOL | 104 | +0.438R | 43.3% |
| AMZN | MAJOR_15 | 34 | +0.381R | 55.9% |
| AAPL | MAJOR_15 | 20 | +0.342R | 55.0% |
| IWM | INDEX_POOL | 6 | +0.291R | 66.7% |
| QQQ | INDEX_POOL | 7 | +0.034R | 57.1% |
| SPY | INDEX_POOL | 5 | -0.061R | 40.0% |
| MARA | OTHER_POOL | 3 | -0.604R | 33.3% |

## Does the S+ rule pick worse trades, or just earlier ones?

S+ is the earliest 3 S of each day; S is what is left over. Same pool of candidates, split only by time of day -- so this is a clean read on the ranking rule with no grade confound.

- S+ (earliest 3/day): n=63, EV +0.786R, CI [+0.183, +1.494]
- S (the rest of the day): n=39, EV +1.099R, CI [+0.432, +1.802]
- permutation p = 0.552, smallest gap this n could detect = 1.369R
