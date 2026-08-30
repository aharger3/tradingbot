# g88 -- is the resting-limit arm real, or a size-gate survivor?

**ORDER TYPE IS REAL -- resting the limit STRICTLY AFTER the signal bar, with nothing dropped for size, still earns $275/day against the shipped entry's $33/day. (Resting it from the arming bar earns $1622, but that uses the knowledge that the setup would fire.)**

One trade a day on `bt2y_trades.json`, 9322 candidates over 500 sessions, 1R = $1,000, bar = $397/day. Exits are the shipped ladder.

| arm | entry | stop when risk < floor | $/day | 95% band | % of bar | win | mean R | green | days traded | rows dropped | median risk |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `BOOK` | shipped | drop the trade | **$64** | $0..$0 | 16.1% | 46.9% | +0.064 | 13/25 | 500 | 14.5% | $0.52 |
| `BOOK_floor` | shipped | widen the stop | **$33** | $0..$0 | 8.3% | 45.8% | +0.033 | 11/25 | 500 | 0.0% | $0.54 |
| `LEVEL` | limit at level | drop the trade | **$469** | $0..$0 | 118.1% | 37.7% | +0.556 | 19/25 | 422 | 84.9% | $0.10 |
| `LEVEL_floor` | limit at level | widen the stop | **$1622** | $0..$0 | 408.6% | 63.7% | +1.622 | 25/25 | 500 | 0.0% | $0.30 |
| `POST_floor` | limit at level | widen the stop | **$275** | $0..$0 | 69.3% | 27.0% | +0.275 | 15/25 | 500 | 0.0% | $0.31 |

`intrabar` is the shipped pair: `signal_runner.intrabar_stop` moves the stop to the entry bar's completed extreme, and any row whose risk then falls under `signal_runner.min_risk_floor` is dropped as un-takeable. That drop is the thing under test -- it selects rows using the entry bar's own future.

`floor` holds the structural stop and pushes it out until the risk clears the same floor, reading `bars[fill_i - 1].close` so the constant is causal. No row is dropped for size, so nothing in those arms can be a survivor.

The limit fills a median of 2 bars before the book's own entry.


## What this does and does not say

**It kills g87's headline.** `AT_LEVEL` printed $469/day and `LEVEL_floor` printed
$1,622/day at 63.7% win and 25/25 green months. **89.6% of those fills land BEFORE
the signal bar.** The limit rests from `arm_index + 1`, and every row in this book is
here only because the setup went on to fire. Resting an order on that knowledge is
buying a retest you already know held. Both numbers are dead; do not quote either.

**What survives is smaller and honest.** Rest the same limit strictly after the
signal bar and it earns **$275/day against the shipped entry's $33** -- the largest
single-rule lift measured on the honest book, and its 95% band ($54..$504) clears
zero while the control's ($-66..$136) does not.

**It is not yet a change worth shipping.** $275/day is 69% of the $397 bar, the win
rate is 27%, only 15 of 25 months are green, and the two bands overlap between $54
and $136. Durability fails. What it establishes is a direction: on this book, waiting
for price to return to the level beats chasing the reclaim by roughly 8x, and the
median honest fill lands 4 bars AFTER the signal rather than 2 bars before it.

**The mechanism, stated plainly.** `signal_runner.intrabar_stop` puts the stop at the
entry bar's completed extreme. A limit at the level fills where that extreme usually
sits, so risk collapses and `min_risk_floor` drops the row -- and what survives is
selected by how far the rest of that bar ran. The `_floor` arms remove that selection
by widening the stop instead of skipping the trade, which is also what a trader does.
