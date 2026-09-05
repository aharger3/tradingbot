# g154 refuter #2 — be-stop-after-enough-past-pt1: REFUTED

**What is different now:** the numbers in the claim reproduce exactly, but they are not
evidence — the gate that called k=0.50R a "survivor" fires on pure noise 41.5% of the time,
the whole $18/day rests on 45 of 498 trades, and a finer grid shows three other k values pass
the same gate with one that fails wedged between two that pass.

Fill for every figure below: entry = the signal bar CLOSE (the book's own `entry`), stops via
`stop_rule.stop_hit_on_close` + `stop_rule.stop_fill_price`, disaster stop at
`DISASTER_STOP_R = 1.0`, one-trade-a-day unit = `omen_metrics.first_of_day_arm(size_gate=True)`
with the `signal_runner.min_risk_floor` gate, 1R = $1,000. Book
`research/bt2y_trades_retest_on.json`, 498 sessions, H1/H2 split 2025-09-01.
Scripts: `research/g154_rule_be-stop-after-enough-past-pt1.py` (the claim, re-run verbatim) and
`research/g154_refute2_be_multiplicity.py` (this pass — it imports the claim's own `_sim`,
nothing is re-implemented).

## 1. Reproduction: exact

| figure | claim | my re-run |
|---|---:|---:|
| baseline $/day | $47 | $47 |
| k=0.50R $/day | $65 | $65 |
| H1 delta | +19 | +19 |
| H2 delta | +18 | +18 |
| precision | 0.3051 → 0.3051 | 18/59 → 18/59 |
| recall_100 | 0.0588 → 0.0588 | 2/34 → 2/34 |

No lookahead found. `_sim` starts at `idx + 1`, tests the bar's exits against the pre-arm stop,
and arms only after, taking effect the next bar. 0 of 498 picks book worse than −1.000R under
either arm. The arithmetic is honest. The inference is not.

## 2. The survivor gate fires on noise 4 times in 10

Paired bootstrap over the 498 sessions, 10,000 resamples, k=0.50R minus the same no-BE control:

| slice | observed delta | 95% CI | P(delta ≤ 0) |
|---|---:|---:|---:|
| full | +$18.25/day | [−$15.00, +$49.80] | 0.133 |
| H1 | +$18.88/day | [−$32.13, +$64.92] | 0.219 |
| H2 | +$17.63/day | [−$26.12, +$56.97] | 0.204 |

Every interval straddles zero. Resampling the *same* data, the claim's own gate
(H1 delta > 0 AND H2 delta > 0) reproduces in **62.2%** of resamples — a "survivor" that
survives its own data less than two times in three.

De-mean each arm's per-day delta so the true effect is exactly zero, then run the gate:

- P(one specific arm passes the gate | no effect) = **0.259**
- P(at least one of the 4 published k arms passes | no effect) = **0.415**

Splitting a book in half and asking for both halves positive is only a ~0.25 hurdle when the
two halves are drawn from one noisy distribution, and four correlated arms take it to 0.42.
Across the 25 candidates tried in F5, that gate is expected to hand back roughly ten spurious
survivors on noise alone. The claim's H1/H2 agreement is the least surprising thing about it.

## 3. Selection: the winner is a coarse-grid artifact and the surface is jagged

Fine sweep, k = 0.125 … 2.000 in 0.125 steps, same control:

| k | $/day | d_H1 | d_H2 | gate |
|---:|---:|---:|---:|---|
| 0.125 | $41 | −2 | −11 | fail |
| 0.250 | $51 | −4 | +11 | fail |
| **0.375** | **$72** | **+22** | **+29** | **PASS — beats the claimed winner** |
| 0.500 | $65 | +19 | +18 | PASS (the claim) |
| 0.625 | $65 | +21 | +15 | PASS |
| 0.750 | $54 | +17 | −2 | fail |
| 0.875 | $59 | +21 | +4 | PASS |
| 1.000 | $49 | +4 | +0 | fail |
| 1.125 – 2.000 | $47 | +0 | +0 | fail (identical to control) |

Two things fall out. First, the published 4-point grid only had ~3 informative points: the
book's targets are effectively all 2.0R (min 1.88, p25/median/p75 2.00, max 2.10), so arming at
entry ± (1+k)R for k ≥ 1.0 sits at or beyond the target and can never fire — every arm from
1.125R up is byte-identical to the no-BE control. Second, a genuine "far enough past PT1"
threshold would be smooth; this one passes at 0.375, 0.500, 0.625, **fails at 0.750**, passes
again at 0.875, then dies. A hole between two passing neighbours is a noise surface, not a
threshold, and 0.50R is not even the best point on it.

Bootstrap the selection: k=0.50 is the best-by-$/day arm in only **67%** of resamples
(0.25 in 14%, 1.00 in 12%, 0.75 in 7%). The reported k is not stable.

## 4. The edge is 45 trades, and it is the difference of two large noisy sums

Only **45 of 498 picks (9.0%)** book a different R at all. Their net is +9.089R = $18.25/day,
made of **+28.41R across 36 improved trades against −19.32R across 9 worsened ones**. Drop the
three biggest winners and the arm is $12/day; drop the three worst losers and it is $32/day.
A rule whose entire claim is the residue of two ~20R sums over 45 observations has no business
being called a survivor at n=498.

## 5. The baseline is not the shipped book

"$47/day" is not the engine's book — it is this script's own simplified full-position replay
(no scale-out, no partial-R blending) with arming disabled. The sibling refutation of the
`stop-placement-routed` claim (`research/g154_refute2_placebo.json`) ran the identical replay
machinery as a pure placebo and measured the model shift with no rule change at all:
**$33.93/day, 46.5% win, max DD −$21,405 (the book) → $46.93/day, 35.1% win, max DD −$28,794
(the replay)**. The replay itself is worth +$13/day and −11 points of win rate. So the claim's
+$18/day lives inside a model that already disagrees with the shipped ladder by more than half
that amount, and cannot be carried into `signal_runner.py` without being re-measured there.

## 6. The unchanged precision/recall is vacuous

`precision 0.3051 → 0.3051` and `recall_100 0.0588 → 0.0588` are identities, not results: an
exit-side predicate cannot change which day fires, as the claim's own script says. Listing them
as survival properties adds no evidence. Note also that no arm makes H2 profitable — the best
one moves H2 from −$52/day to −$34/day. The second year of the book loses money under every k.

## Verdict

**REFUTED.** Reproduces exactly; fails on multiplicity and sampling error. P(delta ≤ 0) = 0.13
overall with both halves straddling zero, the gate has a 41.5% family-wise false-positive rate
over the four arms tried (and 25 candidates were tried in F5), the winning k is a coarse-grid
artifact that a finer sweep beats and surrounds with a hole, 9% of picks carry the whole effect,
and the baseline it improves on is a replay model that is itself +$13/day away from the book.
