# g93 -- RETEST_REQUIRED, priced

Honest book (`research/bt2y_trades.json`), one trade a day = the first fired-and-traded candidate of the session (`g86_honest_ceiling.candidates`). 1R = $1,000. Selection arm over the book's recorded causal `downgrade.score()` fields -- detection is NOT re-run.

## full -- full pool, 28 symbols

`no_retest` trips on **2228 of 9322** pickable rows (23.9%) and on **99 of 500** of the days' first picks (19.8%).

| arm | cand/day | $/day | win | green | max DD | funded $/day |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 18.6 | $28 | 45.5% | 11/25 | $25570 | $2.72 |
| retest | 14.2 | $36 | 46.9% | 15/25 | $19655 | $4.59 |
| retest+chase | 11.1 | $73 | 48.3% | 14/25 | $16672 | $10.91 |

## index -- QQQ/SPY/IWM

`no_retest` trips on **181 of 919** pickable rows (19.7%) and on **78 of 402** of the days' first picks (19.4%).

| arm | cand/day | $/day | win | green | max DD | funded $/day |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 2.3 | $51 | 49.4% | 13/25 | $19406 | $6.59 |
| retest | 2.0 | $82 | 49.7% | 16/25 | $13353 | $15.27 |
| retest+chase | 2.0 | $82 | 49.7% | 16/25 | $13353 | $15.27 |

