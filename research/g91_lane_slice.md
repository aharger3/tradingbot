# g91 -- the lane, measured

Honest book (`research/bt2y_trades.json`), one trade a day = the first fired-and-traded candidate of the session, exactly as `g86_honest_ceiling.candidates` defines it. 1R = $1,000.

Daily loss limit: **$2000**. Funded trailing max drawdown: **$2500**.

## Money

| lane | syms | cand/day | first $/day | win | months green | best-of-day $/day |
|---|---:|---:|---:|---:|---:|---:|
| full pool (shipped) | 28 | 18.6 | $28 | 45.5% | 11/25 | $2948 |
| index only: QQQ/SPY/IWM | 3 | 2.3 | $51 | 49.4% | 13/25 | $437 |
| QQQ + SPY only | 2 | 2.0 | $43 | 50.9% | 14/25 | $323 |
| QQQ only | 1 | 1.5 | $-66 | 50.6% | 9/25 | $93 |
| ten tickers (his rule_11) | 10 | 7.8 | $-8 | 46.3% | 10/25 | $1752 |
| equities only | 15 | 10.9 | $7 | 44.8% | 11/25 | $2317 |
| core tier only | 10 | 8.1 | $-20 | 45.7% | 11/25 | $1851 |

## Survival -- what a funded account is judged on

| lane | max DD (at 1R=$1,000) | green days | best day % of profit | max 1R inside $2500 trailing DD | what it really pays |
|---|---:|---:|---:|---:|---:|
| full pool (shipped) | $25570 | 45.4% | 68.4% | $98 | $2.72/day |
| index only: QQQ/SPY/IWM | $19406 | 49.0% | 47.4% | $129 | $6.59/day |
| QQQ + SPY only | $17832 | 50.6% | 68.9% | $140 | $6.02/day |
| QQQ only | $27091 | 50.6% | n/a (book loses) | $92 | $-6.09/day |
| ten tickers (his rule_11) | $28080 | 46.3% | n/a (book loses) | $89 | $-0.70/day |
| equities only | $32603 | 44.6% | 266.3% | $77 | $0.50/day |
| core tier only | $34752 | 45.6% | n/a (book loses) | $72 | $-1.46/day |

## What each lane is

- **full pool (shipped)** -- every symbol in the book -- the baseline every published figure uses
- **index only: QQQ/SPY/IWM** -- the prop-firm lane at one remove: cash proxies for NQ/ES/RTY
- **QQQ + SPY only** -- the tightest futures proxy -- NQ and ES, the two most-funded contracts
- **QQQ only** -- one instrument, the way a funded futures trader actually trades
- **ten tickers (his rule_11)** -- his ballot: "10 tickers is a good sample size, and still tracking the main pool for data for edge refinement"
- **equities only** -- single names -- the options lane
- **core tier only** -- universe.CORE_SYMBOLS
