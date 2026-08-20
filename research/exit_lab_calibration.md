# Exit-lab calibration (T3)

Replay of the 64 marked trades. The causal-HOD exit bar is compared
to Austin's marked `exit_i`; a hit is within 5 bars. Threshold to pass: 0.5.

hod_rule_within_5_bars: 0.734375

hits: 47
total: 64
misses: 17

## Misses (rule exit bar vs Austin exit_i)

| symbol | date | entry_i | side | rule | austin | diff | reason |
|---|---|---|---|---|---|---|---|
| TSLA | 2026-05-19 | 19 | S | 35 | 24 | 11 | rule=35 austin=24 diff=11 |
| TSLA | 2026-05-19 | 28 | S | 35 | 29 | 6 | rule=35 austin=29 diff=6 |
| TSLA | 2026-06-10 | 12 | L | 90 | 21 | 69 | rule=90 austin=21 diff=69 |
| TSLA | 2026-06-11 | 14 | S | 90 | 15 | 75 | rule=90 austin=15 diff=75 |
| TSLA | 2026-06-12 | 17 | S | 31 | None |  | no marked exit_i |
| TSLA | 2026-07-09 | 16 | L | 33 | 19 | 14 | rule=33 austin=19 diff=14 |
| TSLA | 2026-07-10 | 14 | S | 64 | 17 | 47 | rule=64 austin=17 diff=47 |
| TSLA | 2026-07-23 | 14 | S | 23 | 16 | 7 | rule=23 austin=16 diff=7 |
| TSLA | 2026-07-31 | 23 | S | 27 | 43 | -16 | rule=27 austin=43 diff=-16 |
| QQQ | 2026-06-30 | 14 | L | 23 | 7 | 16 | rule=23 austin=7 diff=16 |
| QQQ | 2026-07-01 | 13 | S | 90 | 16 | 74 | rule=90 austin=16 diff=74 |
| QQQ | 2026-07-16 | 8 | S | 17 | 9 | 8 | rule=17 austin=9 diff=8 |
| QQQ | 2026-07-23 | 6 | L | 14 | 8 | 6 | rule=14 austin=8 diff=6 |
| QQQ | 2026-07-27 | 24 | L | 90 | 26 | 64 | rule=90 austin=26 diff=64 |
| SPY | 2026-07-21 | 20 | S | 90 | 22 | 68 | rule=90 austin=22 diff=68 |
| SPY | 2026-07-27 | 22 | S | 31 | 25 | 6 | rule=31 austin=25 diff=6 |
| SPY | 2026-08-03 | 21 | L | 30 | 21 | 9 | rule=30 austin=21 diff=9 |
