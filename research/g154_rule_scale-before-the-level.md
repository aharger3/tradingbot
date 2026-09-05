# g154 -- scale-before-the-level (F5)

**Scaling the target BEFORE the exact level (not resting at it) raised $/day in both H1 and H2 for at least one size of the shift.**

This rule changes ONLY the exit (the target price the day's already-picked trade scales out at). It never changes which trade fires, so candidates/day, fires/day, S recall, and precision are identical across every row below -- reported once.

book: `bt2y_trades_retest_on.json` -- 498 sessions. one-trade-a-day picks: 498.

candidates/day 16.52, fires/day 1.000

recall_100 2/34 (5.9%) | recall_all 18/345 (5.2%) | precision 18/59 (30.5%)

| arm | b | $/day | H1 $/day | H2 $/day | mean R | win% | months green | maxDD | target-hit% | Δhit pts | ΔmeanR | R-on-hit-only | survivor |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline (target=level) | $0.00 | $50 | $145 | $-45 | 0.050 | 35.1% | 12/25 | $28418 | 34.7% | -- | -- | 2.001 | -- |
| cents_002 | $0.02 | $76 | $161 | $-9 | 0.076 | 36.5% | 13/25 | $23548 | 36.1% | +1.4 | +0.026 | 1.956 (-0.045) | True |
| cents_005 | $0.05 | $93 | $154 | $31 | 0.093 | 38.0% | 13/25 | $21524 | 37.8% | +3.1 | +0.043 | 1.884 (-0.117) | True |
| atr_005 | 0.05xATR14 | $63 | $156 | $-29 | 0.063 | 36.3% | 12/25 | $23166 | 35.9% | +1.2 | +0.013 | 1.937 (-0.064) | True |

Fallback to cents_005 (ATR uncomputable): 0/498 rows on the atr_005 arm.

Survivor rule (per row spec): H1 AND H2 both improve $/day (precision cannot move for an exit-only rule, so it never supplies the improvement here) and recall_100 not below baseline (trivially true -- selection is identical). any_survivor = **True**.

Limitation, stated plainly: both arms run a SINGLE-STAGE proxy exit (one target, one stop) built for this comparison, not the shipped multi-stage SCALE_PLAN ladder (`backtest_week._ladder_bar`). The baseline row above is therefore NOT the book's own booked $/day (that number reflects the full ladder) -- it is the same single-stage walker run with the target AT the exact level, so the baseline-vs-candidate comparison is apples-to-apples even though neither side matches the shipped book's own headline number.
