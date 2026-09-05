# g156 refuter #2 — multiplicity and sampling error on S classifier v0

**What is different now:** the F7 report's "honest zero" verdict is right, but its supporting
money number is weaker than the report admits — the +$13.51/day it quotes for `S_CLASSIFIER`
comes from 13 sessions out of 498, half of it from one day, sits inside a bootstrap CI that
straddles zero, and is **below the median of what the best of 25 random drop rules produces by
chance** (best-of-25 null median +$19.08 vs observed +$13.51, P = 0.849). **REFUTED on
multiplicity and sampling error.** The claim's own conclusion (does not clear the bar) stands and
is in fact under-stated: the flag is not a measured small win, it is indistinguishable from noise.

Fill for every figure below: entry = signal bar CLOSE, stops via `stop_rule.stop_fill_price`,
size-gated on `signal_runner.min_risk_floor`, 1R = $1,000, book
`research/bt2y_trades_retest_on.json` (498 sessions), one-trade-a-day unit
(`research/omen_metrics.first_of_day_arm`). Scripts:
`research/g154_rule_or-break-without-retest.py` (the claim) and
`research/g156_refute2_multiplicity.py` (this refutation).

## 1. Reproduction — exact

| figure | claimed | reproduced |
|---|---:|---:|
| baseline $/day | $33.93 | $33.93 |
| v0 $/day | $47.44 | $47.44 |
| Δ $/day | +$13.51 | +$13.51 |
| H1 Δ | +$8.56 | +$8.55 (rounding) |
| H2 Δ | +$18.46 | +$18.46 |
| precision | 30.5% (18/59) both arms | same |
| bar-backed S recall | 49.0% → 48.7% | same |
| candidates/day | 16.52 | 16.52 |

Construct check passed: the script's locally rebuilt baseline stream is pick-for-pick identical
to `omen_metrics.first_of_day_arm(size_gate=True)`.

## 2. Lookahead — clean

The predicate reads two fields stamped on the book row at fire time: `level` and
`downgrades`. `research/downgrade.no_retest` calls `_break_bar` (scans `j <= i`) and
`_retest_bar` (scans `after+1 .. i`); neither indexes past the signal bar `i`. No leakage found.

## 3. How much of the book actually moves

| | |
|---|---:|
| sessions whose pick changes | **13 of 498 (2.61%)** |
| total delta | $6,726 |
| carried by the single day 2025-11-20 | $3,370 = **50.1%** |
| carried by the top 5 days | $5,915 = **87.9%** |

Six largest movers: 2025-11-20 +$3,370 · 2025-06-17 +$1,953 · 2025-06-30 −$1,574 ·
2024-10-01 +$1,095 · 2026-02-27 +$1,071 · 2025-03-11 +$991.

## 4. Paired bootstrap over the 498 sessions (20,000 resamples)

| split | mean Δ $/day | 95% CI | P(Δ ≤ 0) |
|---|---:|---:|---:|
| whole book | +$13.46 | **[−$3.49, +$33.78]** | 0.067 |
| H1 | +$8.38 | **[−$14.25, +$33.04]** | 0.244 |
| H2 | +$18.47 | **[−$3.30, +$53.13]** | 0.083 |

Every interval straddles zero. **P(both halves positive under resampling) = 0.697** — the exact
gate F7 used to pick this rule flips in ~3 resamples out of 10.

## 5. Placebo — a random drop at the same rate does the same thing

The arm drops 175 of 6,889 sizeable stream rows (2.540%). Dropping 175 rows **at random** from
the same stream, 2,000 draws:

| | |
|---|---:|
| P(random-drop Δ ≥ observed +$13.51) | 0.069 |
| **P(random drop improves BOTH halves — F7's own selection gate)** | **0.220** |
| null Δ distribution | p5 −$17.81 · median −$1.05 · p95 +$15.61 · max +$35.69 |

One random drop in five passes the criterion the report calls the reason this candidate was the
correct pick.

## 6. Multiplicity — 25 rule families, 39 measured arms, one winner kept

The 25 `research/g154_rule_*.json` files contain **39 distinct measured arms** (threshold sweeps
inside a rule count: `cheap-stock-refusal` alone has under_$10 and under_$20). Drawing 25 null
arms and keeping the best:

| | |
|---|---:|
| best-of-25 null Δ, median | **+$19.08** |
| best-of-25 null Δ, p95 | +$29.12 |
| **P(best of 25 null arms ≥ observed +$13.51)** | **0.849** |

The observed effect is *below* the median of what pure noise produces once you take the best of
25 tries. No family-wise correction can rescue it.

## 7. The selection procedure read the validation half

F7 states it forward-selected on H1 and validated on H2. Its own justification is: *"of the 17
candidates … only one improves $/day in **both** halves."* That criterion reads H2, so H2 is not
held out and its +$18.46 is in-sample. A strict H1-only argmax over the non-survivors picks a
**different** rule: `cheap-stock-refusal` (under_$20) at H1 **+$10.60**, ahead of
`or-break-without-retest` at +$8.56. `or-break-without-retest` is the pick only because its H2
number was looked at.

## 8. What survives

- The **honest-zero conclusion survives** and is strengthened: precision flat at 30.5% (18/59,
  identical S set), bar-backed S recall 49.0% → 48.7%, target > 39.5% not met.
- The **+$13.51/day, "both halves positive"** framing does **not** survive. It is 13 sessions,
  one day is half of it, the CI straddles zero, a random drop clears the same gate 22% of the
  time, and best-of-25 noise beats it 85% of the time.
- Shipping the flag OFF is harmless. Any future write-up must not carry "+$13.51/day" as a
  measured gain — the correct sentence is "no measurable effect after multiplicity".

**Verdict: REFUTED (refuter #2, multiplicity / sampling error lens).**
