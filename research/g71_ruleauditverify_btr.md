# G7.1 / ruleauditverify — `break_then_rejection` is NOT unreachable by construction

**Claim under test** (track `ruleaudit`, `research/g71_ruleaudit.md` §1d G6 + §2 row 4):

> `break_then_rejection` is a branch that can never be true — the fourth instance of the
> unreachable-rule bug class. `_break_bar` returns the MOST RECENT close through the level,
> so a close back through it afterwards is unrepresentable by construction.

**Verdict: the COUNT reproduces, the MECHANISM is false.** The branch evaluates `True` on
demand, in the shipped file, unmodified. What kills it in the book is not `_break_bar`'s
recency — it is the argument the callers pass as `level` (the **stop**), evaluated at the
**entry bar**. Diagnosis and fix both change.

## 1. What reproduces

| check | result |
|---|---|
| `break_then_rejection` trips over `research/bt2y_trades.json` | **0 of 76,019** — reproduced exactly (`research/g71_ruleauditverify_btr_hits.py`) |
| trips among the 2,437 traded rows | **0** — reproduced |
| right book? | yes. On-disk `bt2y_trades.json` meta = 76,019 signals / 2,437 traded / 500 sessions / 2024-08-21…2026-08-21, generated 2026-08-29 03:14. The 2,595-trade figure is the superseded pre-T23 book (`g71_ddverify.md:33`, `g71_ladder_verify.md:79`); no 1,017-trade book is on disk |
| exact re-run of the engine (not a re-count of the book) | `research/g71_ruleauditverify_btr_exact.py` re-ran `simulate_day` + `dg.score(dbars, t.entry_idx, t.stop, …)` on AAPL (3,865 signals) and ACHR+MARA+SOFI (8,011 signals) with **unrounded** stops: **0 trips**. The 0 is real, not a book artifact |

## 2. What is false — the branch is reachable, in the shipped file

`research/g71_ruleauditverify_btr_reach.py`, nine synthetic bars, `downgrade.py` untouched:

```
LONG  _break_bar(i=8) = 4          # the up-cross
LONG  break_then_rejection = True  # the claim says this can NEVER be True
SHORT break_then_rejection = True  # mirrored
score().tripped = ['break_then_rejection']
```

Geometry: break up through the level at bar 4, close back below at bar 5, and **stay** at or
below the level through the entry bar. No new up-cross exists, so `_break_bar` still returns
4 and the rejection at 5 sits after it. The "most recent cross" semantics do **not** make a
later close-back-through unrepresentable; they only make it unrepresentable *when price
re-crosses upward before the entry bar* (control case in the same script: `_break_bar` moves
to 6, branch goes False).

It also fires on **real bars**: replaying every book row with the book's 2dp stop,
`break_then_rejection` is `True` on **18 of 76,019** rows (ACHR ×6, MARA ×3, SOFI ×2,
BABA ×2, INTC, MSFT, ORCL, PLTR, UBER). Those 18 do not survive the unrounded stop, but they
are real market geometry, not a construction impossibility.

## 3. The actual blocker (the correct diagnosis)

**Theorem.** For a long, `break_then_rejection(bars, i, L, True)` ⟹ `bars[i]["c"] <= L`.

*Proof.* True requires a close `< L` at `br+1` or `br+2`, with index `≤ i`. Take the largest
such `j`. If `j == i` the conclusion holds. If `j < i` and some later bar closed `> L`, let
`m` be the first — then `bars[m-1].c <= L < bars[m].c`, an up-cross later than `br`,
contradicting `br` = most recent (`research/downgrade.py:180-190`). ∎ (mirrored for shorts.)

So the branch is really asking: *is the entry bar itself on the wrong side of the level?*
Both shipped call sites pass the **stop** as `level`:

- `backtest_2y.py:151` — `dg.score(dbars, t.entry_idx, t.stop, …)`; comment at `:148`:
  *"Level proxy is the stop."*
- `signal_runner.py:2114` — `level = sig.get("stop")`, scored at `len(bars) - 1`.

A long entry whose bar closes at or below its own stop is close to definitionally absent:
**212 of 76,019 (0.28%)** at 2dp, **0** at full precision across the 11,876-signal exact
re-run. That, not `_break_bar`, is why the count is 0.

**Same `_break_bar`, same real bars, a different `level` argument** — sweeping each row's
prior-30 distinct closes as candidate levels (`research/g71_ruleauditverify_btr_book.py`,
8,437 rows: all 2,437 traded + 6,000 sampled non-traded):

```
rows with >=1 level where the branch is TRUE: 6,716 of 8,437 (79.6%)
candidate (row, level) pairs true:           25,139 of 209,408 (12.00%)
```

A branch true on 12% of the price grid is not dead code.

## 4. Consequences for the ruleaudit

1. **§2 row 4 is misfiled.** The register's own precedent (row 3, `level_not_respected`
   anchored on `_break_bar`, 13 / 45,175) is the same species: rare-under-the-shipped-call,
   not unreachable. Row 4 belongs beside row 3, not beside rows 1/2/5.
2. **The implied fix is wrong.** Rewriting `_break_bar` to return the *first* cross would
   move `no_displacement`, `stale_retest`, `no_retest` and `has_confluence` — carrying
   38,263 / 490 / 10,356 / 50,510 trips — to chase a variable that trips 0.
3. **The finding underneath is bigger than the one reported.** `no_displacement`,
   `stale_retest`, `level_not_respected`, `no_retest`, `break_then_rejection` and
   `has_confluence` all take `level`, and every shipped caller hands them the **stop**. Six
   of the ten ladder variables are measuring a break of the *stop price*, not of the level in
   Austin's sentence. `break_then_rejection` is the only one where that substitution is
   *provably* fatal (§3), which is why it alone reads as dead — the other five degrade
   silently.
4. **"Eight variables is really seven plus chase"** is arithmetically true on this book
   (7 of 8 `CHECKS` trip; `chase` ships ON) but is a property of the caller, not of the
   grader. Restore a real level argument and it is eight.

## 5. Fix — NOT applied (diagnosis pass). Change the branch's scan, not `_break_bar`.

The rejection to detect sits *between the break and the entry*, whether or not price
re-crossed afterwards. That is a scan over every crossing in the window, and it leaves the
other five level-anchored variables untouched:

```diff
--- a/research/downgrade.py
+++ b/research/downgrade.py
@@ -256,14 +256,22 @@ def counter_trend_not_respected(bars, i, level, is_long):
 def break_then_rejection(bars, i, level, is_long):
     """Austin, unprompted: it broke, then immediately gave it back."""
-    br = _break_bar(bars, i, level, is_long)
-    if br is None:
-        return False
-    for j in range(br + 1, min(br + 1 + REJECT_BARS, i + 1)):
-        back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
-        if back:
-            return True
-    return False
+    # EVERY cross in the window, not just the most recent one. Anchoring on
+    # `_break_bar` (most recent) made this true only when the ENTRY bar itself
+    # closed on the wrong side of the level -- 0 of 76,019 signals, because the
+    # callers pass the trade's own stop as `level` (backtest_2y.py:151,
+    # signal_runner.py:2114). research/g71_ruleauditverify_btr.md has the proof.
+    for br in range(max(1, i - 30), i + 1):
+        prev, cur = bars[br - 1], bars[br]
+        crossed = ((prev["c"] <= level < cur["c"]) if is_long
+                   else (prev["c"] >= level > cur["c"]))
+        if not crossed:
+            continue
+        for j in range(br + 1, min(br + 1 + REJECT_BARS, i + 1)):
+            back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
+            if back:
+                return True
+    return False
```

**Do not ship this without measuring it.** It changes the S/A/C ladder that
`live_scanner.py:30` (`ENABLE_SAC_LADDER=1`) routes on, and the prior question — whether
`level` should be the stop at all — is the one that decides whether any of these six
variables mean what Austin said.

Scripts: `research/g71_ruleauditverify_btr_reach.py` (synthetic reachability),
`research/g71_ruleauditverify_btr_hits.py` (full-book scan, 76,019 rows),
`research/g71_ruleauditverify_btr_book.py` (level sweep on real bars),
`research/g71_ruleauditverify_btr_exact.py` (engine re-run, unrounded stops).
