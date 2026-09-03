# G7.1 adversarial verify — track `levels`, the "six runner target" claim

**Verdict: REFUTED.** The arithmetic reproduces exactly; the causal attribution does not.
The loss belongs to the arm's *fallback*, not to Austin's six.

Scripts: `research/g71_levelsv_check.py`, `g71_levelsv_split2.py`, `g71_levelsv_book2.py`,
`g71_levelsv_final.py`. Books re-run into `research/_v/`.

## 1. What reproduces

| | claim | my re-run |
|---|---|---|
| base | 2,437 / 49.5% / +0.5495R / 25-25 green | 2,436 / 49.5% / **+0.5492R** / 25-25 |
| six_target | 2,430 / 48.0% / +0.4630R / 23-25 | 2,429 / 48.0% / **+0.4621R** / 23-25 |
| paired dR | −0.0620 ± 0.0387, 807/2,353 moved | **−0.0626 ± 0.0387, 806/2,352 moved** |

Book identity is correct: base matches `research/bt2y_trades.json` (2,437 traded, +0.54948R,
76,019 signals) — the **current post-T23 book**, which supersedes the 2,595 post-T0 book
(`g71_sigfireverify.md:19`, `g71_ddverify.md:33`). Not the 1,017 book. That attack fails.
No look-ahead: probe `et` range is 09:35–10:59, **0 rows before 09:35**, so ORH/ORL
(fixed at the 09:34 close) are never read before they exist. The `six` branch is reachable
(63.5% of scale-armed rows). Error bar survives day-clustering: clustered 95% ±0.0462,
day-block bootstrap [−0.1082, −0.0172], P(dR≥0)=0.0032.

## 2. What breaks it — the fallback is the whole loss

`g71_levels_book.py:130` sets `t.runner_target = six if six is not None else t.target`.
On **48%** of shared trades no one of the six lies beyond the scale point, so the arm
silently swaps the shipped runner target (median 14.2R out, the whole dollar 81.4% of the
time) for `t.target` — 2R, or the 84% original. That is a *runner cap*, not "his six".

Paired dR decomposed on the base replay's own probe (`g71_levelsv_split2.py`):

| branch | n | moved | paired dR | 95% | share of −0.0626 |
|---|---:|---:|---|---|---|
| **A. one of the six really supplied the target** | 901 | 341 | **+0.0314** | ±0.0812 | **+0.0120** |
| **B. fallback → `t.target`** | 1,137 | 464 | **−0.1528** | ±0.0469 | **−0.0739** |
| C. six == shipped (inert) | 313 | 0 | 0 | — | 0 |

Where his six governs, the arm is **positive and inside the error bar**. 100% of the loss
is branch B.

## 3. The isolation arm (`--arm six_or_shipped`)

Apply the six wherever one qualifies; leave the shipped target where none does. This is
what "restrict the runner target to his six" means, with the fallback confound removed.

| arm | n | win | mean R | total R | green |
|---|---:|---:|---|---|---|
| base | 2,436 | 49.5% | +0.5492 | +1,337.8 | 25/25 |
| six_target (claim's arm) | 2,429 | 48.0% | +0.4621 | +1,122.4 | **23/25** |
| **six_or_shipped** | **2,436** | 48.5% | **+0.5584** | **+1,360.3** | **25/25** |

paired: `six_or_shipped` dR = **+0.0157 ± 0.0318** naive, ±0.0383 clustered,
bootstrap [−0.0219, +0.0557], **P(dR≥0)=0.78**. Month flips: **none**.

So: restricting the runner target to his six is **flat** (indistinguishable from zero,
directionally positive), keeps every month green, and does not change the trade count.
The 23/25 durability break and the −0.086R headline are artefacts of the 2R fallback.

## 4. Minor

Signals drifted 76,019 → 76,035 and traded 2,437 → 2,436 between the prior agent's run
(14:31) and mine (~17:40) — 0.04%, archive drift, immaterial, but the arm books are not
bit-reproducible.

## 5. If a fix is wanted (not applied)

```diff
--- a/research/g71_levels_book.py
+++ b/research/g71_levels_book.py
@@
-        if SIX_TARGET:
-            t.runner_target = six if six is not None else t.target
+        if SIX_TARGET and six is not None:
+            # Only rows one of the SIX can actually govern. Falling back to
+            # t.target (2R) on the 48% that have no six beyond the scale point
+            # caps the runner and is a SECOND intervention: it carries the
+            # whole -0.0626R paired loss (research/g71_levelsv.md).
+            t.runner_target = six
```
