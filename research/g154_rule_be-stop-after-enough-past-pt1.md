# g154/F5 -- be-stop-after-enough-past-pt1

**What is different now:** measured Austin's own flagged-unresolved threshold -- how far PAST the first profit target (PT1) price must travel before the stop arms to breakeven -- on the honest book, instead of leaving it a stated-but-unmeasured question.

Book `bt2y_trades_retest_on.json`, 498 sessions (H1 249 / H2 249), size-gated on `signal_runner.min_risk_floor`. 1R = $1000. H1/H2 split at 2025-09-01. PT1 := entry +/- 1.0R (documented simplification -- see module docstring; the shipped ladder's causal PT1 rung is not reconstructable from this book alone).

This is an EXIT-SIDE arm: it cannot change which day trades. candidates/day 16.52, fires/day 1.000, recall_100 2/34, recall_all 18/345, precision 18/59 -- identical for baseline and every k below by construction. 2/498 picks fell back to the book's own recorded r (no bars, no entry-bar match, or exit ran past available data), identically for every arm.

## Baseline -- this script's own no-BE replay (same simplified model as every k arm, arming disabled)

| $/day | H1 $/day | H2 $/day | mean R | win | months green | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| $47 | $145 | $-52 | +0.047 | 35.1% | 12/25 | $-28794 |

## k-arm sweep (BE arms at entry +/- (1.0+k)R)

| k (R past PT1) | $/day | H1 $/day | H1 delta | H2 $/day | H2 delta | mean R | win | months green | max DD | survivor |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.25R | $50 | $142 | -3 | $-41 | +11 | +0.050 | 31.6% | 14/25 | $-28106 | False |
| 0.50R | $65 | $164 | +19 | $-34 | +18 | +0.065 | 33.4% | 13/25 | $-24680 | True |
| 0.75R | $54 | $162 | +17 | $-54 | -2 | +0.054 | 33.9% | 12/25 | $-27987 | False |
| 1.00R | $49 | $149 | +4 | $-52 | +0 | +0.049 | 35.1% | 12/25 | $-28794 | False |

## Verdict

Best-performing k: **0.50R past PT1**. Survivor (H1 AND H2 both improve $/day vs. this script's own no-BE replay baseline, recall_100 unaffected by construction): **True**.

Recall/precision cannot move for an exit-side predicate -- they are reported once, not per-k, and are identical to whatever the shipped one-trade-a-day arm already fires on this book.
