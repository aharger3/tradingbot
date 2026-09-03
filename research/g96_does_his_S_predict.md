# g96 -- does Austin's S label predict the engine's money?

Book `research/bt2y_trades_retest_on.json`, full lane, 1R = $1,000, honest close fill. 1246 judged symbol-days, 347 of them S; the engine had a candidate on 667 of them (201 S, 466 not).

| policy on the symbol-day | S days | non-S days | gap | perm p |
|---|---:|---:|---:|---:|
| first candidate of the day | +0.0351R (n=201) | -0.1222R (n=466) | +0.1573R | 0.0366 |
| every candidate (mean R) | -0.0508R (n=295) | -0.1122R (n=657) | +0.0614R | 0.2042 |

## Trading only the S symbol-days (first candidate)

162 sessions carry an S symbol-day. Total **$7066** = **$44 per S-session**, months green **11/24**.

## Read this before quoting it

Deck cards were selected by `build_deck`, not sampled at random, and often BECAUSE the engine fired. These are comparisons *within the judged pool*, never judged-vs-world. The permutation test is the honest read: given these days and these labels, is the split better than shuffling the labels?
