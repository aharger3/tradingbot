# g172 -- Vanquish refresh: S=1R, classifier ON/OFF, no O1 winner, SPX/XSP arm

**What is different now:** the Vanquish sweep is re-run against the candidate stream S actually sizes live (row L5: S sizes to a flat 1R / $1,000, A and C size to $0 and never trade), not the old any-grade first-of-day arm -- so this file answers whether a real S-only account clears a Vanquish eval, not a hypothetical one that also traded B/C.

Book: `bt2y_trades_retest_on.json` (RETEST_REQUIRED=1, shipped default), 498 sessions, 2024-09-03 .. 2026-09-02.

**O1: no winner (REFUTED).** O1 (16-arm day/window/tier/veto grid, incl. S_CLASSIFIER on/off) found no arm positive in both H1 and H2, baseline included -- REFUTED, nothing shipped. This file adds no selection lever beyond the S-only restriction (already landed, live sizing, row L5).

## S_1R_classifier_off (n=313 candidates)

2024-09-03 .. 2026-09-01, 161 in H1 (< 2025-09-01), 152 in H2 (>= 2025-09-01).

- **No risk level tested passes (stock-R).**
- Headline $1,000/trade (stock-R, == S's live 1R unit): FAIL (trailing_drawdown)
- Options skin (delta 0.42 + $0.05 spread, LOW CONFIDENCE), headline $1,000/trade: FAIL (trailing_drawdown)
- **Rolling-start pass rate** (252-session windows, at the best/headline risk level found above): **0.4%** overall (254 starts) -- H1 starts 0.6% (161), H2 starts 0.0% (93).

## S_1R_classifier_on (n=313 candidates)

2024-09-03 .. 2026-09-01, 161 in H1 (< 2025-09-01), 152 in H2 (>= 2025-09-01).

- **No risk level tested passes (stock-R).**
- Headline $1,000/trade (stock-R, == S's live 1R unit): FAIL (trailing_drawdown)
- Options skin (delta 0.42 + $0.05 spread, LOW CONFIDENCE), headline $1,000/trade: FAIL (trailing_drawdown)
- **Rolling-start pass rate** (252-session windows, at the best/headline risk level found above): **0.4%** overall (254 starts) -- H1 starts 0.6% (161), H2 starts 0.0% (93).

## SPX/XSP arm -- SPY-only S candidates (index-only insurance)

Same S-only, classifier-off candidate rule, restricted to `sym == 'SPY'`. "SPY signals x10 as SPX" names the mechanism (SPX prices ~10x SPY's per-point value, so an equivalent single-leg long position needs ~10x the dollar risk per contract) -- it is not a separate multiplier applied in this file, since the sweep already spans that dollar range and this book has no real SPX/XSP bid-ask, margin, or contract-size data to re-price against. This arm answers a CANDIDATE-COUNT question: is there enough SPY-only S-tier signal at all, in case Vanquish's Advanced Options universe turns out to be index-only (AUGUR.md's open question, still unresolved).

- n=10 SPY-only S candidates, 2024-12-23 .. 2026-06-24
- No risk level tested passes.

## Modeling choices stated explicitly

- S=1R candidate stream: `sgrade == 'S'`, first sizeable per day -- the exact restriction row L5 landed for live sizing (A/C size to $0 and never trade).
- S_CLASSIFIER v0 predicate: `level in ('OR high','OR low') and 'no_retest' in downgrades`, identical to `research/g160_tweak_grid.py::_classifier_drop` -- REFUTED (F7), reported for completeness only, per the row's own instruction.
- O1: REFUTED, no winner -- no day/window/tier/veto lever is layered on top of the S-only stream here.
- Options skin: `spread_R = DEFAULT_SPREAD / (stock_risk * DEFAULT_DELTA)` (options_sizer.py's own R7 round-trip formula), subtracted from every trade's R once. `DEFAULT_DELTA=0.42`, `DEFAULT_SPREAD=0.05`, imported not restated. LOW CONFIDENCE: this repo has no real options bid/ask tape to check the flat $0.05 estimate against.
- Vanquish rules unchanged from g120: 10% profit target / 5% EOD-anchored trailing drawdown / no daily loss limit / min 4 trading days / no single day over 30% of accumulated profit. $499/mo while in eval, $249 reset once if the eval never passes over the whole book.
- SPX/XSP: CONDITIONAL and CANDIDATE-COUNT ONLY -- see the arm's own section above. Not re-priced for SPX/XSP contract size, margin, or spread.
