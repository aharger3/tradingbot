# G7.1 `levels` -- P21 re-run on Austin's six

Book: `research/bt2y_trades.json`, 2437 traded signals 2024-08-21..2026-08-21.

## Roster size actually seen at entry

| roster | mean levels/signal | max |
|---|---:|---:|
| six | 6.00 | 6 |
| hodlod | 8.00 | 8 |
| nine | 12.95 | 21 |

## has-2R-target split, by roster

| roster | slice | n | win% | mean R | total R |
|---|---|---:|---:|---:|---:|
| six | has 2R target | 1466 | 44.5 | +0.555 | +813.2 |
| six | no 2R target | 971 | 57.6 | +0.542 | +525.8 |
| hodlod | has 2R target | 1810 | 43.9 | +0.594 | +1075.4 |
| hodlod | no 2R target | 627 | 66.7 | +0.421 | +263.7 |
| nine | has 2R target | 1810 | 43.9 | +0.594 | +1075.4 |
| nine | no 2R target | 627 | 66.7 | +0.421 | +263.7 |

## The directional test Austin's rule makes

His b4 says a setup with no level to target is HARDER. So losers should lack a target MORE often than winners. `no-target share` below is that share; a POSITIVE gap (losers > winners) is the rule working.

| roster | no-target share of losers | of winners | gap |
|---|---:|---:|---:|
| six | 33.6% (n=1225) | 46.1% (n=1212) | -12.5 pts |
| hodlod | 17.1% (n=1225) | 34.5% (n=1212) | -17.4 pts |
| nine | 17.1% (n=1225) | 34.5% (n=1212) | -17.4 pts |

## Austin's S grade only

| roster | slice | n | win% | mean R | total R |
|---|---|---:|---:|---:|---:|
| six | has 2R target | 178 | 44.9 | +0.399 | +71.1 |
| six | no 2R target | 120 | 57.5 | +0.289 | +34.6 |
| hodlod | has 2R target | 210 | 43.3 | +0.379 | +79.6 |
| hodlod | no 2R target | 88 | 65.9 | +0.297 | +26.1 |
| nine | has 2R target | 210 | 43.3 | +0.379 | +79.6 |
| nine | no 2R target | 88 | 65.9 | +0.297 | +26.1 |
