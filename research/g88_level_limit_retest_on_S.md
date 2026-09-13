# g88 -- is the resting-limit arm real, or a size-gate survivor?

**ORDER TYPE IS REAL -- resting the limit STRICTLY AFTER the signal bar, with nothing dropped for size, still earns $74/day against the shipped entry's $-49/day. (Resting it from the arming bar earns $1608, but that uses the knowledge that the setup would fire.)**

One trade a day on `bt2y_trades_retest_on.json`, 1407 candidates over 498 sessions, 1R = $1,000, bar = $397/day. Exits are the shipped ladder.

| arm | entry | stop when risk < floor | $/day | 95% band | % of bar | win | mean R | green | days traded | rows dropped | median risk |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BOOK` | shipped | drop the trade | **$-52** | $0..$0 | -13.1% | 43.9% | -0.058 | 9/25 | 446 | 15.0% | $0.57 |
| `BOOK_floor` | shipped | widen the stop | **$-49** | $0..$0 | -12.3% | 44.5% | -0.053 | 10/25 | 459 | 0.0% | $0.60 |
| `LEVEL` | limit at level | drop the trade | **$110** | $0..$0 | 27.7% | 49.4% | +0.647 | 18/25 | 85 | 91.7% | $0.09 |
| `LEVEL_floor` | limit at level | widen the stop | **$1608** | $0..$0 | 405.0% | 74.5% | +1.745 | 25/25 | 459 | 0.0% | $0.35 |
| `POST_floor` | limit at level | widen the stop | **$74** | $0..$0 | 18.6% | 26.9% | +0.086 | 12/25 | 431 | 0.0% | $0.35 |

`intrabar` is the shipped pair: `signal_runner.intrabar_stop` moves the stop to the entry bar's completed extreme, and any row whose risk then falls under `signal_runner.min_risk_floor` is dropped as un-takeable. That drop is the thing under test -- it selects rows using the entry bar's own future.

`floor` holds the structural stop and pushes it out until the risk clears the same floor, reading `bars[fill_i - 1].close` so the constant is causal. No row is dropped for size, so nothing in those arms can be a survivor.

The limit fills a median of 1 bars before the book's own entry.

