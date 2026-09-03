# G7.2 `target25` -- re-priced on the current book

Book `research/bt2y_trades.json` (generated 2026-08-29T18:38:17), **4508 traded rows** replayed from `data_archive/`. Gaps: {'day': 0, 'bar': 0, 'index': 0}. Same rig as `research/g71_exitfam.py` F1/F3/F4: both shipped stops live (level stop on the close floored at -1.25R, resting -1.0R disaster stop on touch), paired bootstrap error bar (10,000 resamples of the per-row difference). $1,000 = 1R.

**This is not the book the +$40 figure in `research/g71_exitfam.md` was measured on.** That file's book had 2,437 traded rows. Between that measurement and this one, the reject-suppression bug (G7.2) was fixed and the book was regenerated -- it is now **4508 traded rows**. Everything below is re-derived from scratch on the book actually on disk.

## 1. The change under consideration: aim 2.5R instead of 2R

| arm | n | win% | $/trade | months green | weeks green | paired delta vs flat_2R (95% CI) | real? |
|---|---:|---:|---:|---:|---:|---|---|
| flat_2r (the shipped plan) | 4508 | 51.7% | $+547 | 25/25 | 102/105 | baseline | -- |
| **flat_2.5r** | 4508 | 45.4% | $+580 | 25/25 | 102/105 | +33 [+9, +56] | **yes** |

**Verdict: SURVIVES.** Aiming 2.5R instead of 2R is worth **$+33 a trade** on this book, 95% paired interval [$+9, $+56]. Win rate 51.7% -> 45.4%. Months green 25/25 -> 25/25. Weeks green 102/105 -> 102/105.

## 2. Confirmed, not changed

| arm | n | win% | $/trade | months green | weeks green | paired delta (95% CI) | real? | note |
|---|---:|---:|---:|---:|---:|---|---|---|
| flat_5r vs flat_2r | 4508 | 28.6% | $+609 | 24/25 | 94/105 | +62 [-0, +122] | no | wins only 28.6% of the time |
| break-even at 1R vs never | 4508 | 13.9% | $+637 | 25/25 | 76/105 | +70 [+13, +127] | **yes** | |
| 15-min time stop vs no clock | 4508 | 44.3% | $+605 | 25/25 | 99/105 | +37 [-73, +145] | no | |
| 30-min time stop vs no clock | 4508 | 36.5% | $+610 | 25/25 | 92/105 | +43 [-58, +143] | no | |
| 45-min time stop vs no clock | 4508 | 32.3% | $+612 | 25/25 | 91/105 | +45 [-48, +138] | no | |
| first adverse close vs no clock | 4508 | 10.9% | $+590 | 25/25 | 83/105 | +23 [-40, +84] | no | |

