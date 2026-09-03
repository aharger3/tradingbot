# G7.1 `weeks` — adversarial verify of "every week green is arithmetically out of reach"

Scripts: `research/g71_weeksverify_adv.py`, `research/g71_weeksverify_adv2.py`.
Data: `research/_g71_weeksverify_adv.json`. Read-only pass; no engine file touched.

## Verdict: REFUTED as stated. The conclusion survives; the mechanism and two of the three evidence lines do not.

## 1. What reproduces exactly (give the claim this)

Re-derived from `research/bt2y_trades.json` without touching `_g71_weeks.json`:
2,437 trades / 105 ISO weeks, mu=0.5495, sigma=2.1192, mu/sigma=0.2593, 23.21 t/wk,
mean week 12.7532R, sd week 12.7014R, week Sharpe **1.0041**, drag **1.244**,
91/105 green. Requirement table reproduces to the digit: 50% -> p_wk 99.342%,
z **2.479**, n **141.5**, **6.1x**, mu/sigma **0.6403**; 80% -> 188.2; 95% -> 250.3.
**Book check passes**: 2,437 is the current book (`generated 2026-08-29T03:14:29`);
2,595 is the superseded T0 book (`research/g71_advscanners.md:89`), 1,017 is older
still. No look-ahead in the requirement path; ORACLE is correctly excluded.
The sqrt(n) law also survives an empirical block test on this book — pooling the daily
series into k-week blocks, observed vs Phi(sqrt(k)*Sharpe) is within 2.0 points at every
k from 1 to 8 (`block_scaling_test`). So the *arithmetic* is not the problem.

## 2. The killer: the Sharpe -> P(green) mapping is falsified inside the claim's own file

`research/g71_weeks.py` (`every_week_green_requirement` block) inverts
`P(green) = Phi(week_sharpe)`. Across the 25 rows of `_g71_weeks.json` that mapping is
well-behaved for iid-shaped policies (P0 err +2.4 pts, CAP-8 +5.2) and **badly wrong for
exactly the family that produces green weeks** — the path-dependent stop-when-green arms:

| policy | t/wk | week Sharpe | Phi(Sharpe) | observed | error | Sharpe the formula demands |
|---|---:|---:|---:|---:|---:|---:|
| W2-5 stop green or -5R | 2.51 | 0.601 | 72.6% | **93.3%** | **+20.7 pts** | 1.501 (**2.50x**) |
| W2-8 | 2.90 | 0.741 | 77.1% | **96.2%** | **+19.1** | 1.773 (2.40x) |
| W1 stop week when green | 3.04 | 0.823 | 79.5% | **97.1%** | **+17.7** | 1.902 (2.31x) |
| W2-3 | 1.99 | 0.498 | 69.1% | 84.8% | +15.7 | 1.026 (2.06x) |

The claim's sentence *"needs P(green)=99.34% per week, a weekly Sharpe of 2.479 against
today's 1.004"* states a **sufficient** condition under normality as if it were
**necessary**. It is not: W1 buys 97.1% at Sharpe 0.823, where the formula says 1.902 is
required. Deflating 2.479 by the family's measured 2.3-2.5x ratio puts the required Sharpe
near **1.0-1.07 — roughly where the book already is**, not 2.5x away. The "6.1x volume or
2.5x the per-trade edge" dichotomy is an artefact of the normal/iid assumption, and the
third route (path-dependent weekly stopping) is the one that empirically moves the number.
`research/g71_weeks.md` section 4d does cover W1; the claim as circulated drops it and keeps
only the falsified dichotomy.

## 3. "The window produces 6.64 candidates a day (~33/wk)" — wrong object

6.64/day is `counted` = fired&traded + halted = 3,294/496 — a **post-filter** stream, not
window output. From `research/bt2y_trades.json` status counts:

| | count | per week (105 wks) |
|---|---:|---:|
| fired **and traded** | 2,437 | 23.2 |
| fired, **not** traded (concurrency-blocked) | **1,050** | 10.0 |
| halted | 857 | 8.2 |
| `skipped_tight_stop` (engine filter) | 2,051 | 19.5 |
| **fired-or-halted signals** | **4,344** | **41.4** (8.69/day, not 6.64) |
| + tight-stop rejects | 6,395 | **60.9** |
| all detected rows | 76,019 | 724.0 |

"33/wk" is also arithmetically 31.4 (3,294/105). The window's own output is **1.3x-1.8x**
what the claim quotes, and 1,050 rows over 2y are candidates the engine *did* produce and
the concurrency layer refused. 141.5/wk is still out of reach at 60.9/wk of pre-filter
candidates, so the conclusion holds — but the number offered as proof is not the number it
is called.

## 4. "Not a sizing question — P(green week) is scale-invariant" — only for a uniform multiplier

Invariance holds for `r_i -> c*r_i` with one c. It does **not** hold for per-trade weights,
and the book has `scaled`/`slot` fields. Causal test (no look-ahead), half/quarter size on
the 2nd+ trade of the same day:

| weight on 2nd+ trade/day | green weeks | % | week Sharpe |
|---|---:|---:|---:|
| 1.00 (shipped) | 91/105 | 86.7% | 1.004 |
| 0.50 | **92/105** | 87.6% | **1.029** |
| 0.25 | 88/105 | 83.8% | 0.979 |

Small and inside the error bar, but the claim's blanket *"There is no risk setting that buys
green weeks"* is proved only for the uniform case it tested.

## 5. Minor: the 1.244 "correlation drag" is 31% not correlation

`corr_drag = sd_week / (sigma*sqrt(E[n]))` charges week-to-week **count** dispersion
(Var(n)=59.2, sd_n=7.69 on E[n]=23.2) to correlation. Compound-random-n model
`Var = E[n]*sigma^2 + Var(n)*mu^2` predicts sd 11.05 vs observed 12.701, so drag against the
honest baseline is **1.149**; a 2,000-draw permutation that destroys all intra-week
correlation while keeping the counts still returns drag **1.074**. Only ~1.16x of the 1.244
is real correlation. The inversion also freezes drag at 1.244 while multiplying n by 6.1;
refitting `drag = 0.831 + 0.081*ln(t/wk)` and solving self-consistently gives **n = 137.7
(5.9x)** — a -2.7% correction, so this one does not change the answer, but the constant is
unjustified as written.

## 6. What is actually true

- No causal policy in the book reaches 105/105. Best is **W1 at 102/105**; resampling its own
  weekly series gives **P(all 105 green) = 4.96%**, W2-8 1.7%, W2-5 0.11%, P0 shipped ~0.
  "Every week green" is not a target the system hits — **conclusion upheld**.
- The reason is **not** "you'd need 141.5 trades a week". It is that the only lever that
  raises green-week share (stop the week when green) costs 86% of income and worsens the tail
  — which is `research/g71_weeks.md` section 4d, and is a *cost* argument, not an
  *arithmetic-impossibility* argument.

## 7. Suggested correction to `research/g71_weeks.md` section 4b/4c (not applied)

```diff
-**b) The arithmetic of the ask.** For a fresh 105-week stretch to come in all green at even
-coin-flip odds, each week needs P(green) = 99.34%, i.e. a **weekly Sharpe of 2.48**.
+**b) The arithmetic of the ask, for an iid-shaped policy.** For a fresh 105-week stretch to
+come in all green at even coin-flip odds, each week needs P(green) = 99.34%. Under the
+normal approximation that is a **weekly Sharpe of 2.48** — but that mapping is only valid
+for policies whose weekly R really is a sum of ~iid trades. It over-states the requirement
+by 2.3-2.5x for the stop-when-green family (W1 reaches 97.1% at Sharpe 0.82, where the
+formula demands 1.90), so read the row below as a bound on the *volume* route, not as the
+requirement itself.
-which the 09:30-11:00 window on 28 symbols does not produce (it produces 6.6 candidates a
-day, 33 a week, of which 23 are traded).
+which the current filter stack does not produce: the window fires 4,344 signals over 500
+sessions (8.7/day, 41.4/week — of which 23.2 are traded, 10.0 are concurrency-blocked and
+8.2 are halted), and 60.9/week including the 2,051 `skipped_tight_stop` rejects.
-**c) It is not a sizing question.** P(green week) is scale-invariant: halving risk per trade
-halves the dollars and leaves the green-week share exactly where it is. There is no risk
-setting that buys green weeks.
+**c) A uniform size change is not a lever.** P(green week) is invariant to one multiplier on
+every trade. Per-trade weights are not covered by that argument: half-size on the 2nd+ trade
+of a day moves 91/105 -> 92/105 (Sharpe 1.004 -> 1.029). The effect is inside the error bar,
+but it is not zero by construction.
```
