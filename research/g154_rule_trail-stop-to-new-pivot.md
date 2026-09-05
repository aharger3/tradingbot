# g154/F5 -- trail-stop-to-new-pivot

**What is different now:** measured Austin's trailing-stop claim -- once a trade has pushed favourably a second time after an initial hold, raise the stop to the newest, tighter 3-bar pivot rather than leaving it at the original structural stop -- on the honest book, reported on ALL traded rows (winners and losers), not winners only.

Book `bt2y_trades_retest_on.json`, 498 sessions (H1 249 / H2 249), size-gated on `signal_runner.min_risk_floor`. 1R = $1000. H1/H2 split at 2025-09-01.

This is an EXIT-SIDE arm: it cannot change which day trades. candidates/day 16.52, fires/day 1.000, recall_100 2/34, recall_all 18/345, precision 18/59 -- identical for baseline and candidate by construction. 3/498 picks fell back to the book's own recorded r (no bars, no entry-bar match, or exit ran past available data), identically for both arms.

| arm | split | $/day | mean R | win | months green | max DD |
|---|---|---:|---:|---:|---:|---:|
| baseline (no trail) | all | $143 | +0.143 | 41.6% | 12/25 | $-19724 |
| baseline (no trail) | H1 | $199 | +0.199 | 43.4% | 7/12 | $-19724 |
| baseline (no trail) | H2 | $88 | +0.088 | 39.8% | 5/13 | $-15891 |
| candidate (trail to pivot) | all | $98 | +0.098 | 35.1% | 12/25 | $-15075 |
| candidate (trail to pivot) | H1 | $131 | +0.131 | 36.5% | 7/12 | $-15075 |
| candidate (trail to pivot) | H2 | $64 | +0.064 | 33.7% | 5/13 | $-12783 |

delta $/day vs baseline: H1 -68.00, H2 -24.00.

## Verdict

Survivor (H1 AND H2 both improve $/day vs. this script's own no-trail replay baseline, recall_100 not below baseline -- identical by construction for an exit-side predicate): **False**.

Recall/precision cannot move for an exit-side predicate -- they are reported once, not per-arm, and are identical to whatever the shipped one-trade-a-day arm already fires on this book.
