# g95 -- is the oracle real edge, or max-of-N?

Book `research/bt2y_trades_retest_on.json` (RETEST_REQUIRED on), full lane, one trade a day, 1R = $1,000, honest close fill.

| policy | $/day |
|---|---:|
| first of day | $25 |
| coin flip among the day's candidates | $-26 |
| **oracle** (best of day, hindsight) | **$2684** |
| null oracle (max of the same N random draws) | $2763 |
| anti-oracle (worst of day) | $-991 |

## Q1

THE ORACLE IS ARITHMETIC. Taking the max of the same number of random draws from the book's own outcome pool reaches the same place (real is 97% of null, inside the null's own range). It is NOT proof the setups are there -- it is proof that 18 draws have a big maximum. No classifier can chase it.

## Q2 -- features that beat first-of-day

14 of 81 stamped feature-values beat first-of-day on an all-day basis.

| feature | $/covered day | $/all day | days |
|---|---:|---:|---:|
| dow = Wed | $212 | $44 | 103 |
| dow = Mon | $111 | $21 | 96 |
| vol_regime = wild | $110 | $43 | 192 |
| setup_label = other (84% re-entry) | $85 | $37 | 218 |
| setup = reentry_84_rule | $85 | $37 | 218 |
| level = not-his: prior entry (84%) | $85 | $37 | 218 |
| downgrade = ocr_not_respected | $65 | $57 | 435 |
| pool = index | $65 | $51 | 388 |
| tripped = 4 | $61 | $52 | 426 |
| tier = experimental | $51 | $51 | 493 |
| level = PMH | $50 | $35 | 343 |
| dow = Tue | $45 | $9 | 103 |

## Q3 -- the classifier's specification

Chance rate is **7.4%**. To clear the $397/day bar a picker must find the day's best **15.6%** of the time -- 2.1x better than chance.

