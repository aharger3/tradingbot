# G7.1 adversarial verify — track `samplesize`

**Verdict: REFUTED.** The arithmetic reproduces exactly (scipy, independent formulas);
both load-bearing *inputs* are wrong.

Scripts: `research/g71_ssverify_recall.py` (re-runs the sweep, writes nothing shared),
`research/g71_ssverify_power.py` → `research/g71_ssverify_power.json`.

## 1. The recall constant is one engine generation stale

`g71_samplesize_power.py:139,162,172,177,203` hardcodes `OBS = 0.529` / `observed_k = 18`,
copied from `research/t0_heldout_recall.json` (written Aug 29 02:55, commit `9edd2ba7`).
T11 / T4 / T23 landed after it.

Re-running `t0_heldout_recall.score_sweep()` against the current tree — same 100-card blind
sweep, same scorer, no engine edit:

```
n_S 34   fired_on_S 23   recall 67.6%   precision 39.7%
```

Four independent sibling G7.1 base arms agree (`g71_recall_base.json`,
`g71_scanners_recall_base.json`, `g71_ladder_recall_noab.json`,
`g71_ladder_recall_head.json` — all 23/34), **and so does this track's own companion
artifact**: `g71_samplesize_full_recall.json::calibration_100_card_sweep` = `fired_on_S 23,
recall_pct 67.6`. 18/34 is the *no-pivot / no-xlift* arm value
(`g71_recall_no_pivot.json`, `g71_scanners_recall_noxlift.json` — both 18).
`g71_samplesize.md:262` sees the 18-vs-23 gap and explains it as "report CIs", not as a
stale constant.

| claimed (@0.529) | corrected (@0.676) |
|---|---|
| p vs 0.90 = **7.5e-08** | **6.4e-04** (8,500x) |
| power to reject 0.90 at n=34 = **0.9987** | **0.9034** |
| n_S for 80% power vs gate = **11** | **23** ("eight times more than you need" → 1.5x) |
| 10pt unpaired per arm = **382** | **311** |
| power_10pt_unpaired at n=34 = **0.129** | **0.149** |

## 2. ψ = 0.30 is assumed, and the repo's own arms measure ~0.147

`g71_samplesize.md:81` calls 0.30 "realistic discordance"; nothing measures it. Measured
over 66 like-for-like arm pairs on the identical 34 S cards (same G7.1 batch):
**min 0.000, median 0.147, max 0.441** — and every ψ ≥ 0.30 pair involves the extreme
`sac_all` arm, a ±26–44 pt recall swing, not a 10-pt change.

At the measured median ψ = 0.147: **n_S for 80% power = 113, not 234**; **paired power at
n=34 = 0.325, not 0.181**. At the commonly measured ψ = 0.088, `n_mcnemar` returns `None`
(ψ ≤ δ) — a 10-pt move is not representable, and the Q3 table starts at 0.12 so it never
exposes the regime where its own model breaks.

## 3. Unit error: "25 cards" is 25 S cards, i.e. 99 graded cards

By the script's own `cards()` / `BASE_RATES` conversion, the Q4 row `n_S = 25` is **99
graded cards**. Austin's sentence is "25 card samples" → n_S ≈ 6.3 @0.2533, 8.5 @0.34.
Paired power there is **0.062–0.075 → 93–94% invisible**, not 86%.

## 4. Wrong instrument named

"the recall gate" is `research/regression_gate.py`, which runs on
`t4_engine_recall.py:37 = austin_marks_v2.jsonl` (159 rows / 151 days) and is a set-diff
regression check with **no 90% target and no binomial test**. The 34-card blind sweep
(`t0_heldout_recall.py:38`) is a separate measurement. The report documents this itself at
`g71_samplesize.md:138-150`, then the claim conflates the two.

## What survives

The *direction* survives: n_S = 34 is well-powered for "we are not at 90%" (0.90, not
0.999) and hopeless for "did that change help" (0.15 unpaired / 0.33 paired at measured ψ),
and running A/Bs paired on all 278 S days is still the right move. Every published digit
that depends on 0.529 or ψ=0.30 needs re-running.

## Fix (not applied)

```diff
--- a/research/g71_samplesize_power.py
+++ b/research/g71_samplesize_power.py
@@
-    OBS, GATE = 0.529, 0.90
+    # 23/34 on the blind sweep against the current tree (T11/T4/T23 landed after
+    # t0_heldout_recall.json was written); verified by research/g71_ssverify_recall.py
+    # and by g71_samplesize_full_recall.json::calibration_100_card_sweep.
+    OBS, GATE = 23 / 34, 0.90
@@
-            "observed_k": 18, "recall": round(18 / 34, 4),
-            "wilson95": [round(x, 4) for x in wilson(18, 34)],
-            "p_value_vs_0.90": binom_cdf(18, 34, GATE) * 2,
+            "observed_k": 23, "recall": round(23 / 34, 4),
+            "wilson95": [round(x, 4) for x in wilson(23, 34)],
+            "p_value_vs_0.90": binom_cdf(23, 34, GATE) * 2,
@@
-    for psi in (0.12, 0.15, 0.20, 0.30, 0.40, 0.50):
+    # 0.147 = measured median discordance over 66 like-for-like G7.1 arm pairs on
+    # the same 34 S cards (research/g71_ssverify_power.py). 0.30 is not "realistic".
+    for psi in (0.12, 0.147, 0.15, 0.20, 0.30, 0.40, 0.50):
```
and every `0.529` / `0.629` literal at lines 172, 177, 203 becomes `OBS` / `OBS + delta`.
