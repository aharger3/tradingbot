# F6 refuter #2 — g154 `displacement-graded-not-boolean` is REFUTED

**What is different now, in one sentence:** the rule's survivor verdict is a coin
flip — a placebo that throws away a *uniformly random* 67.12% of the same
candidates clears the identical survivor gate **49.7% of the time**, the
precision "win" adds **zero** S days (18/59 → 18/47, same numerator, Fisher
p=0.42), and the money it costs is real: **−$69.73/day, 95% CI
[−$172.79, +$30.75]**, negative in both halves.

Fill, unchanged from the claim: signal-bar CLOSE entry, `stop_rule.stop_fill_price`
stops, size-gated on `signal_runner.min_risk_floor`, 1R = $1,000, book
`research/bt2y_trades_retest_on.json`, 498 sessions, one-trade-a-day unit
(`research/omen_metrics.first_of_day_arm` walk). H1/H2 split 2025-09-01.
Scripts: `research/g154_rule_displacement-graded-not-boolean.py` (theirs, rerun)
and `research/g154_refute2_disp_bootstrap.py` (mine).

## 1. It reproduces exactly — the arithmetic is not the problem

| figure | claim | my rerun |
|---|---:|---:|
| baseline $/day | 33.93 | **33.93** |
| T=2.0 $/day | −36.03 | **−36.03** |
| H1 delta | −91.47 | **−91.47** |
| H2 delta | −47.78 | **−47.78** |
| precision | 30.5 → 38.3 | **30.5 → 38.3** |
| recall_100 | 5.9 → 14.7 | **5.9 → 14.7** |

`git diff` on the committed `.json`/`.md` after rerun: empty. **No lookahead
either** — `_break_bar_idx` walks backwards from `min(entry_i, …)` and the
10-bar body window sits further back still, so nothing reads past the signal
bar. The claim is arithmetically honest. It is the *inference* that fails.

## 2. The survivor gate is satisfiable by noise — 49.7% of the time

The gate is `(H1 up OR precision up) AND (H2 up OR precision up) AND
recall ≥ baseline`. Both halves lose money here, so the gate collapses to
"precision went up and recall did not fall". Placebo: keep each judgeable
candidate with probability 1 − 0.6712 (T=2.0's own drop rate), same
non-droppable population (`ratio is None` kept), same picker, 1,000 draws.

| placebo statistic (n=1000, seed 20260905) | value |
|---|---:|
| **survivor gate passes** | **49.7%** |
| precision rises above baseline at all | 75.9% |
| precision ≥ the claimed 38.3% | 25.4% |
| recall_100 ≥ the claimed 14.7% | 2.0% |
| $/day ≤ the claimed −$36.03 | 30.8% |
| precision p05 / p50 / p95 | 25.0 / 34.5 / **44.4** |

**All four swept thresholds' precisions (36.1, 34.0, 38.3, 31.2) sit inside the
placebo's 5–95 band [25.0, 44.4].** The "graded" curve is not distinguishable
from randomly discarding two thirds of the book.

## 3. The precision win is pure denominator — it finds no extra S

| arm | S / graded | precision |
|---|---:|---:|
| baseline | **18** / 59 | 30.5% |
| T=2.0 | **18** / 47 | 38.3% |

Identical numerator. The arm removed 12 graded non-S days and not one graded S
day was added. Fisher exact two-sided **p = 0.4171**. The recall move is
2/34 → 5/34, **p = 0.4275**. Neither reaches significance on its own.

## 4. Multiplicity: this is the arm you would expect to find by chance

- `DEFAULT_T = 2.0` is annotated *"chosen after the sweep"* in the script and is
  the **argmax of precision** among the 4 thresholds tried. Post-hoc.
- 25 rule candidates × 4 thresholds each = **~100 arms** in the batch.
- Placebo joint tail (precision ≥ 38.3 **and** recall ≥ 14.7): **1.1%**
  → expected count in 100 arms: **≈1.1**. Exactly one such arm exists. This one.

## 5. And it costs money, in both halves, with the CI to match

Paired bootstrap over the 498 sessions (same resampled days score both arms,
2,000 draws):

| split | mean Δ$/day | 95% CI | P(arm better) |
|---|---:|---:|---:|
| all | −69.73 | [−172.79, +30.75] | 9.3% |
| H1 | −95.08 | [−246.37, +53.89] | 10.4% |
| H2 | −42.90 | [−185.90, +98.36] | 28.0% |

The CI straddles zero — this is not a *proven* loser either. That is the point:
the book cannot resolve a $70/day move, so a rule whose only positive readings
are two Fisher-insignificant proportions on 34 and 47 denominators has
established nothing.

## Verdict

**REFUTED.** The rule reproduces and has no lookahead, but its survivor status
is a 49.7% null event, its precision gain adds zero S days and is p=0.42, its
recall gain is p=0.43, its headline threshold is the post-hoc best of four, and
it loses $70/day on the honest fill. Do not ship, and do not carry
"displacement-graded-not-boolean survives" forward as a finding.
