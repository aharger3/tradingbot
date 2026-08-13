# T8 -- two-year backtest of the omen-5.0 engine, by pool and by tier

`backtest_week.simulate_day` at the committed omen-5.0 defaults (`STOP_ON_CLOSE=1`, `LADDER_MODE=B`, the 09:30-11:00 gate inside `detect_signals`, pivot levels on, T11's S clauses on), replayed over **2024-08-12 to 2026-08-11** (500 trading days) across **29 symbols** in the three tracked pools. $1,000 risk per trade. Win rate counts decided trades only (scratches excluded from the denominator, kept in P&L).

## Whole run

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| all fired | 1388 | 699 | 678 | 11 | 50.8% | $1,080,479 | $778 |
| traded (engine A+/A/B) | 1017 | 558 | 457 | 2 | 55.0% | $887,892 | $873 |
| C alerts (not traded) | 371 | 141 | 221 | 9 | 39.0% | $192,586 | $519 |

## By pool

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| **MAJOR_15** | 603 | 340 | 262 | 1 | 56.5% | $525,356 | $871 |
| **INDEX_POOL** | 18 | 10 | 8 | 0 | 55.6% | $1,676 | $93 |
| **OTHER_POOL** | 396 | 208 | 187 | 1 | 52.7% | $360,860 | $911 |

## By tier (Austin's scale)

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| **S+** | 63 | 30 | 33 | 0 | 47.6% | $49,533 | $786 |
| **S** | 39 | 22 | 16 | 1 | 57.9% | $42,855 | $1,099 |
| **A** | 13 | 7 | 6 | 0 | 53.8% | $16,225 | $1,248 |
| **C** | 1273 | 640 | 623 | 10 | 50.7% | $971,866 | $763 |

## Pool x tier

| pool | tier | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|---|
| MAJOR_15 | S+ | 42 | 20 | 22 | 0 | 47.6% | $16,054 | $382 |
| MAJOR_15 | S | 22 | 14 | 8 | 0 | 63.6% | $33,331 | $1,515 |
| MAJOR_15 | A | 4 | 1 | 3 | 0 | 25.0% | $-330 | $-82 |
| MAJOR_15 | C | 767 | 392 | 371 | 4 | 51.4% | $562,128 | $733 |
| INDEX_POOL | S | 1 | 0 | 1 | 0 | 0.0% | $-1,000 | $-1,000 |
| INDEX_POOL | C | 33 | 15 | 18 | 0 | 45.5% | $7,975 | $242 |
| OTHER_POOL | S+ | 21 | 10 | 11 | 0 | 47.6% | $33,479 | $1,594 |
| OTHER_POOL | S | 16 | 8 | 7 | 1 | 53.3% | $10,524 | $658 |
| OTHER_POOL | A | 9 | 6 | 3 | 0 | 66.7% | $16,555 | $1,839 |
| OTHER_POOL | C | 473 | 233 | 234 | 6 | 49.9% | $401,763 | $849 |

## By setup

| | trades | W | L | scratch | win rate | P&L | avg/trade |
|---|---|---|---|---|---|---|---|
| break_and_retest | 1234 | 640 | 585 | 9 | 52.2% | $1,022,603 | $829 |
| one_candle_rule | 153 | 58 | 93 | 2 | 38.4% | $53,814 | $352 |
| reentry_84_rule | 1 | 1 | 0 | 0 | 100.0% | $4,062 | $4,062 |

## Rates

- **S+**: 63 over 500 trading days = **0.13/day** universe-wide
- **S**: 39 over 500 trading days = **0.08/day** universe-wide
- **A**: 13 over 500 trading days = **0.03/day** universe-wide
- **C**: 1273 over 500 trading days = **2.55/day** universe-wide
