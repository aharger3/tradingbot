# g86 -- does the selection prize survive an honest fill?

**SELECTION -- the ceiling survives the honest fill, so the setup has edge and the engine is picking the wrong one**

| book | first of day | best of day | prize | coin flip | months green (best) |
|---|---:|---:|---:|---:|---:|
| honest (close fill, current default) | $28/day, 45.5% win | $2948/day, 99.6% win | **$2920/day** | $-25/day | 25/25 |
| published (old fill, unobtainable) | $721/day, 66.7% win | $4179/day, 99.0% win | **$3458/day** | $522/day | 25/25 |

Bar: **$397/day** (six figures a year). One trade a day, 1R = $1000.

## honest (close fill, current default)

`bt2y_trades.json` -- 500 sessions, 9322 candidates over 500 days, median 18/day.

| arm | $/day | %% of bar | mean R | win | months green | worst DD |
|---|---:|---:|---:|---:|---:|---:|
| first | $28 | 7.0% | +0.028 | 45.5% | 11/25 | $-25570 |
| best | $2948 | 742.4% | +2.948 | 99.6% | 25/25 | $-469 |
| worst | $-993 | -250.1% | -0.993 | 0.4% | 0/25 | $-496380 |

Arrival order picks the day's best on 38 of 500 days (7.6%); chance is 6.5%. Edge over a coin flip: $53/day.

## published (old fill, unobtainable)

`bt2y_trades_published_fill.json` -- 500 sessions, 6170 candidates over 499 days, median 12/day.

| arm | $/day | %% of bar | mean R | win | months green | worst DD |
|---|---:|---:|---:|---:|---:|---:|
| first | $721 | 181.6% | +0.722 | 66.7% | 25/25 | $-5993 |
| best | $4179 | 1052.6% | +4.187 | 99.0% | 25/25 | $-2000 |
| worst | $-982 | -247.4% | -0.984 | 1.0% | 0/25 | $-491021 |

Arrival order picks the day's best on 64 of 499 days (12.8%); chance is 10.1%. Edge over a coin flip: $199/day.

