# G7.1 — adversarial verify of track `smeasure`

Scripts: `research/g71_smverify_fields.py`, `g71_smverify_ladder.py`, `g71_smverify_arms.py`,
`g71_smverify_schema.py`. Substrate `research/bt2y_trades.json` (unmodified, HEAD).
Read-only; no mark file, engine file, or artifact touched.

## Verdict: REFUTED on the causal half, reproduced on the descriptive half

## 1. What reproduces exactly

Every headline figure re-derived from scratch, independent pooler, same result:

| figure | smeasure | mine |
|---|---|---|
| S days traded | 58/255 = 22.7% [18.0, 28.3] | identical |
| not-S days traded | 224/775 = 28.9% [25.8, 32.2] | identical |
| diff / z / p | −6.2 pts, z = −1.913, p = 0.0557 | identical |
| precision vs S-only | 20.6% [16.3, 25.7] | identical |
| routed arm | 71/255 = 27.8% | identical |

Wilson and two-proportion arithmetic hand-checked (z = −1.9128, p = 0.0558). Sound.

## 2. Substrate check: the right book

`research/bt2y_trades.json` = 76,019 signals / 2,437 traded / 500 sessions, generated
2026-08-29T03:14:29, clean against HEAD `145d564e` ("T23: the stack re-run"). This is the
**newest** book, not the 1,017-trade pre-T0 one. T0's 2,595 is the `t0_base` arm (all three
7.1 levers off); the shipped stack's book is 2,437. Substrate check **passes**.

## 3. REFUTED — "68.7 points of recall are destroyed by `_route`, not by detection"

`g71_smeasure.md:224` states it as the finding. The decomposition off the same file
(`g71_smverify_arms.py`):

| step on his 255 S days | rate | cost |
|---|---|---|
| `saw` = any record exists (smeasure) | 96.5% | — |
| `saw` = any **non-X** record | 35.3% | **−61.2 pts, `_grade_pa` X-skip** |
| routed incl. `halted` | 31.4% | −3.9 pts, `_route`'s own gates |
| routed excl. `halted` (smeasure) | 27.8% | −3.5 pts, **R31 loss halt** |

**89% of the 68.6-point fall is `_grade_pa`, i.e. detection/grading — the exact thing the
claim exonerates.** `_route` costs 3.9 points, not 68.7.

Two mechanical causes:

- **The `saw` arm counts non-signals.** 69,624 of 76,019 records carry legacy grade **X**
  (91.6%), and `backtest_week.py:635` shows `status == "skipped_d"` ⟺ `grade == "X"`
  exactly (69,624 = 69,624). CLAUDE.md: *"X is not a grade, it means the engine should not
  have fired."* A 96.5% `saw` rate built on X rows measures that the scanner produced a
  row, not that the engine saw the setup.
- **`routed` is not "cleared `_route`".** `loss_halt.py:110` rewrites `status` `"fired"` →
  `"halted"` for 857 signals **after** they cleared the router
  (`backtest_2y.py:213` runs `apply_to_book` on finished rows). `g71_smeasure_test.py:207`
  tests `status == "fired"`, so every router-passed signal a portfolio risk rule later
  killed is scored as a routing failure.

## 4. REFUTED — "precision of the traded book against his ladder is 20.6%"

His ladder is S/A/C/none and **A and C are tradeable** (CLAUDE.md: "A = one downgrade,
C = two"). The 775 "refused" days decompose (`g71_smverify_ladder.py`):

| his grade | eligible days | traded |
|---|---:|---:|
| S | 255 | 22.7% |
| A | 231 | 27.3% |
| C | 58 | 36.2% |
| **REFUSED** (none / X / `_no_trade`) | **486** | 28.8% |

Precision against S only = 20.6%. **Precision against his ladder's tradeable set (S∣A∣C)
= 50.4% [44.6, 56.1]** — 2.4× the published figure. "Against his ladder" is the wrong
label for an S-only numerator.

## 5. Survives — the descriptive core, and it gets worse

Re-run against the **real** refusal set (486 days, not 775):

| arm | S | REFUSED | diff | p |
|---|---|---|---|---|
| traded | 22.7% | 28.8% | −6.1 | 0.0765 |
| routed, fired-only (smeasure) | 27.8% | 33.3% | −5.5 | 0.1262 |
| **routed, incl. halted (correct)** | **31.4%** | **41.2%** | **−9.8** | **0.0091** |
| **saw, non-X (correct)** | **35.3%** | **45.1%** | **−9.8** | **0.0104** |

Dropping the 15 silent-day-autopsy S cards (selected *because* the engine was silent) moves
the traded arm 22.7% → 22.5%: not the cause.

So the claim's *direction* is right and understated — but its characterisation
"indistinguishable from zero, p = 0.056" holds only on the `traded` arm, and only because
the loss halt and the fired/halted mislabel add noise. **On both correctly-defined arms the
separation is significant and negative: the engine reaches his refused days ~10 points more
often than his S days, p ≈ 0.01.**

## 6. Uncontrolled confound the claim does not mention

An **unselected** book symbol-day trades at 18.2% (2,154 of 11,808). His S days 22.7%, his
refused days 28.8% — both *above* base rate, because the corpora were sourced from engine
candidates (decks built from what the engine surfaced). The S-vs-refused contrast is
therefore confounded by corpus sourcing, and no sourcing control is reported.

No look-ahead in the measurement itself. No unreachable branch: 58 S days do trade.
Provenance is disclosed correctly — 196 in-sample / 54 selection / 13 fit / **0 clean
hold-out**, which if anything biases toward separation and so does not rescue the engine.

## 7. Fix (diff, not applied)

```diff
--- a/research/g71_smeasure_test.py
+++ b/research/g71_smeasure_test.py
@@
 def book_index():
-    """(by_day, meta).  by_day[(sym, day)] = {'sigs','routed','traded'}."""
+    """(by_day, meta).  by_day[(sym, day)] = {'sigs','sigs_nonX','routed','traded'}.
+
+    `sigs` counts every record, and 91.6% of records carry legacy grade X --
+    "X is not a grade, it means the engine should not have fired" -- so `sigs`
+    is not a detection arm.  `sigs_nonX` is.
+
+    `routed` must accept status "halted" as well as "fired": loss_halt.py:110
+    rewrites "fired" -> "halted" AFTER _route passed the signal
+    (backtest_2y.py:213), so testing == "fired" charges the R31 portfolio halt
+    to the router."""
     d = json.load(open(BOOK, encoding="utf-8"))
     meta = d["meta"]
-    by_day = defaultdict(lambda: {"sigs": 0, "routed": 0, "traded": 0})
+    by_day = defaultdict(lambda: {"sigs": 0, "sigs_nonX": 0,
+                                  "routed": 0, "traded": 0})
     for t in d["trades"]:
         e = by_day[(t["sym"], t["day"])]
         e["sigs"] += 1
-        if t.get("status") == "fired":
+        if t.get("grade") != "X":
+            e["sigs_nonX"] += 1
+        if t.get("status") in ("fired", "halted"):
             e["routed"] += 1
         if t.get("traded"):
             e["traded"] += 1
     return by_day, meta
```

and the negative pool must be split on Austin's ladder, not on S-complement, before any
line calls it "days he refused" or calls an S-only numerator "precision against his ladder".
