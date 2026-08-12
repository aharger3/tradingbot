# T8 -- two-year backtest of the omen-5.0 engine, by pool and by tier

`backtest_week.simulate_day` at the committed omen-5.0 defaults (`STOP_ON_CLOSE=1`, `LADDER_MODE=B`, the 09:30-11:00 gate inside `detect_signals`, pivot levels on, T11's S clauses on), replayed over **2024-08-12 to 2026-08-11** (501 trading days) across **29 symbols** in the three tracked pools. $1,000 risk per trade. Win rate counts decided trades only (scratches excluded from the denominator, kept in P&L).

## Whole run

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| all fired | 1430 | 725 | 689 | 16 | 51.3% | $1,163,500 | $814 |
| traded (engine A+/A/B) | 1047 | 579 | 464 | 4 | 55.5% | $956,883 | $914 |
| C alerts (not traded) | 383 | 146 | 225 | 12 | 39.4% | $206,617 | $539 |

## By pool

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| **MAJOR_15** | 605 | 342 | 262 | 1 | 56.6% | $540,292 | $893 |
| **INDEX_POOL** | 18 | 10 | 8 | 0 | 55.6% | $1,676 | $93 |
| **OTHER_POOL** | 424 | 227 | 194 | 3 | 53.9% | $414,915 | $979 |

## By tier (Austin's scale)

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| **S+** | 63 | 30 | 33 | 0 | 47.6% | $49,533 | $786 |
| **S** | 39 | 22 | 16 | 1 | 57.9% | $42,855 | $1,099 |
| **A** | 15 | 9 | 6 | 0 | 60.0% | $23,681 | $1,579 |
| **C** | 1313 | 664 | 634 | 15 | 51.2% | $1,047,432 | $798 |

## Pool x tier

| pool | tier | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|---|
| MAJOR_15 | S+ | 42 | 20 | 22 | 0 | 47.6% | $16,054 | $382 |
| MAJOR_15 | S | 22 | 14 | 8 | 0 | 63.6% | $33,331 | $1,515 |
| MAJOR_15 | A | 4 | 1 | 3 | 0 | 25.0% | $-330 | $-82 |
| MAJOR_15 | C | 771 | 394 | 371 | 6 | 51.5% | $580,942 | $753 |
| INDEX_POOL | S | 1 | 0 | 1 | 0 | 0.0% | $-1,000 | $-1,000 |
| INDEX_POOL | C | 33 | 15 | 18 | 0 | 45.5% | $7,975 | $242 |
| OTHER_POOL | S+ | 21 | 10 | 11 | 0 | 47.6% | $33,479 | $1,594 |
| OTHER_POOL | S | 16 | 8 | 7 | 1 | 53.3% | $10,524 | $658 |
| OTHER_POOL | A | 11 | 8 | 3 | 0 | 72.7% | $24,011 | $2,183 |
| OTHER_POOL | C | 509 | 255 | 245 | 9 | 51.0% | $458,515 | $901 |

## By setup

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| break_and_retest | 1272 | 664 | 596 | 12 | 52.7% | $1,098,993 | $864 |
| one_candle_rule | 157 | 60 | 93 | 4 | 39.2% | $60,445 | $385 |
| reentry_84_rule | 1 | 1 | 0 | 0 | 100.0% | $4,062 | $4,062 |

## Rates

- **S+**: 63 over 501 trading days = **0.13/day** universe-wide
- **S**: 39 over 501 trading days = **0.08/day** universe-wide
- **A**: 15 over 501 trading days = **0.03/day** universe-wide
- **C**: 1313 over 501 trading days = **2.62/day** universe-wide
