# g88 -- is the resting-limit arm real, or a size-gate survivor?

**ORDER TYPE IS REAL -- resting the limit STRICTLY AFTER the signal bar, with nothing dropped for size, still earns $256/day against the shipped entry's $31/day. (Resting it from the arming bar earns $1699, but that uses the knowledge that the setup would fire.)**

One trade a day on `bt2y_trades_retest_on.json`, 8227 candidates over 498 sessions, 1R = $1,000, bar = $397/day. Exits are the shipped ladder.

| arm | entry | stop when risk < floor | $/day | 95% band | % of bar | win | mean R | green | days traded | rows dropped | median risk |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BOOK` | shipped | drop the trade | **$37** | $0..$0 | 9.3% | 46.4% | +0.037 | 12/25 | 498 | 16.3% | $0.54 |
| `BOOK_floor` | shipped | widen the stop | **$31** | $0..$0 | 7.8% | 46.3% | +0.031 | 14/25 | 498 | 0.0% | $0.57 |
| `LEVEL` | limit at level | drop the trade | **$574** | $0..$0 | 144.6% | 42.3% | +0.756 | 20/25 | 378 | 86.8% | $0.10 |
| `LEVEL_floor` | limit at level | widen the stop | **$1699** | $0..$0 | 428.0% | 65.6% | +1.699 | 25/25 | 498 | 0.0% | $0.31 |
| `POST_floor` | limit at level | widen the stop | **$256** | $0..$0 | 64.5% | 27.5% | +0.256 | 16/25 | 498 | 0.0% | $0.32 |

`intrabar` is the shipped pair: `signal_runner.intrabar_stop` moves the stop to the entry bar's completed extreme, and any row whose risk then falls under `signal_runner.min_risk_floor` is dropped as un-takeable. That drop is the thing under test -- it selects rows using the entry bar's own future.

`floor` holds the structural stop and pushes it out until the risk clears the same floor, reading `bars[fill_i - 1].close` so the constant is causal. No row is dropped for size, so nothing in those arms can be a survivor.

The limit fills a median of 2 bars before the book's own entry.

