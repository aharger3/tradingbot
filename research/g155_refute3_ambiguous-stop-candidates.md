# g155 refuter #3 - ambiguous-stop-candidates: REFUTED

**What is different now:** the claim's script reproduces byte for byte and has no lookahead, but the rule LOSES money on both halves ($-4.36 H1, $-3.62 H2, $-4/day overall), loses a green month and widens max drawdown - it is called a survivor purely on a precision move of one single judged day (18/59 -> 19/60), and a rule-shaped coin flip passes that same gate 47.9% of the time, so over the 25 candidates tried the chance of at least one such null survivor is 100.0%.

Fill for every figure: signal-bar CLOSE entry as booked in bt2y_trades_retest_on.json; stop_rule.stop_fill_price stops; size-gated on signal_runner.min_risk_floor via omen_metrics._row_is_sizeable; one-trade-a-day first-of-day pick-then-gate; 1R=$1,000; H1/H2 split 2025-09-01.

## 1. Reproduction - exact

`python research/g154_rule_ambiguous-stop-candidates.py` re-run on base f8740f80 rewrites its own .json/.md byte-identically (`git status` clean).

| | claim | my run |
|---|---:|---:|
| baseline $/day | $33.93 | $33.93 |
| arm $/day | $29.94 | $29.94 |
| H1 delta | -4.36 | -4.36 |
| H2 delta | -3.62 | -3.62 |
| precision | 30.5 -> 31.7 | 30.5 -> 31.7 |
| recall_100 | 5.9 -> 5.9 | 5.9 -> 5.9 |

Everything in the claim reproduces. What the claim omits: green months **13 -> 12** and max drawdown **$-21404.68 -> $-21468.32**. Both worse. CLAUDE.md's durability gate is every month green.

## 2. Lookahead - none

`_compute_ambiguous` reads `bars[max(0,i-10):i]` for avg_rng and `bars[:i+1]` for the order block; `detect_order_block_setup` gets that same closed slice, so nothing past the signal bar is visible. The selection arm only reorders which already-booked row is taken. This axis does not refute.

## 3. What the drop actually does

| | |
|---|---:|
| days whose pick changed | 6 |
| of those, worse | 5 |
| of those, better | 1 |
| total $ moved | $-1990.19 |
| $/day | $-4.0 |

Judged (graded) days touched by the repick - this is the entire basis for the precision claim:

| day | side | symbol-day | his grade |
|---|---|---|---|
| 2024-09-18 | base | IWM_2024-09-18 | none |
| 2024-09-18 | arm | AVGO_2024-09-18 | none |
| 2025-06-26 | arm | COIN_2025-06-26 | S |

Precision moves 18/59 -> 19/60. That is **+1 S day and +1 graded day**. A single card is the whole survivor verdict.

And that card is `COIN_2025-06-26`. On that day the rule dropped NFLX@09:44 (**+$37.84**) and took COIN@09:49 instead, which booked the **full -1R, -$1,000.00**. The precision gain is the arm trading one more day Austin graded S and losing the maximum on it. Precision here counts the label, not the outcome - the rule bought +1.2 precision points for -$1,038 on that one day.

## 4. The $/day delta is noise, and it points the wrong way

Paired day-level bootstrap, 4000 resamples over the 498 sessions: point **$-4.0/day**, 95% CI **[$-14.1, $7.39]**, P(delta > 0) = **0.2162**.

## 5. Placebo - a null rule passes this gate routinely

The rule drops 1.19% of the candidates the selector actually walks. Drawing the same number of drops at random from the sizeable candidate pool, 4000 times:

| null-rule outcome | rate |
|---|---:|
| passes the full survivor gate | **47.9%** |
| passes on precision alone (as this rule does) | 28.3% |
| passes on $/day in both halves | 19.6% |

25 rule candidates were measured. Expected null survivors: **11.97**. P(at least one) = **100.0%**. The arm's own $/day sits at the **27.7th percentile** of the placebo distribution (placebo median $33.48/day) - it is not even a good coin flip.

## 6. Sign flip - dropping the CLEAN rows instead

Same k, drawn only from rows the rule calls clean (the exact inverse of the trader logic): $26.19/day, H1 $131.99, H2 $-79.61, precision 31.7%, recall_100 5.9% -> survivor = **True**. A gate the opposite rule can also pass is not measuring the rule.

## Verdict: REFUTED

- Reproduces exactly; no lookahead; honest close fill. Those axes are clean.
- It costs money on BOTH halves, loses a green month, and widens max DD.
- 'Survivor' rests on one judged card, on a gate a null rule clears 47.9% of the time across 25 tries.

