# G7.1 / track `ladder` — killing A+ and B, executably

**Austin:** *"A+ and B need to be gotten rid of thats a priority it has been for 5 session turns."*

**Answer in one line:** the letters can go today at **zero cost**, because they are not what
picks the trades — but the *grader swap* that has been called "killing B" is a different
change, and it is measured **negative on every gate**.

Measured on this repo at HEAD, 2026-08-29. Scripts: `research/g71_ladder_count.py`,
`research/g71_ladder_bt2y_arm.py`, `research/g71_ladder_recall_arm.py`.

---

## 0. DIRECTION.md's claim: confirmed, and now worse than it says

DIRECTION.md: *"968 of those 1,016 are `B` only because `_calibration_grade` floors the
first with-trend signal of the day, inside 90 minutes, to B."* That is the pre-T0 book.
On the committed T0 book (`research/bt2y_trades.json`, 2026-08-29 03:14 — 76,019 signals,
2,437 traded) the same count reads:

| where a traded row got its tradeable letter | rows | share |
|---|---:|---:|
| `_calibration_grade` arrival floor `C -> B` (tag `[floor B: first with-trend signal of the day]`) | **1,370** | **56.2%** |
| `_apply_x_lift` un-vetoing a `_grade_pa` `X` and writing a bare `B` (tag `[x-lift:clean]`) | **582** | **23.9%** |
| `_grade_pa`'s own candle-shape verdict | **485** | **19.9%** |

**Confirmed.** `_grade_pa` — the legacy ladder — chooses **19.9%** of the traded book.
80.1% is selected by arrival order or by a lever whose entire job is to *overrule* the
ladder. And in the traded book the ladder is not a ladder: **2,361 B / 72 A / 4 A+**
(96.9% / 3.0% / 0.2%).

So: **yes, the removal is mostly a rename.** Say that to Austin plainly.

Deleting the arrival floor and keeping everything else: traded **2,437 -> 1,067**, mean R
**+0.5495 -> +0.4631**, total R **+1,339 -> +494**. *That* is the gate. The letters are not.

---

## 1. Every call site of the legacy ladder

### Produces the letters

| file:line | what |
|---|---|
| `omen_bot.py:96-101` | `TradeGrade` enum — `A_PLUS/A/B/C/X` (+ `D` alias) |
| `omen_bot.py:250-285` | `PriceActionAnalyzer._grade_pa` — the ladder itself, four returns per side |
| `omen_bot.py:214-247` | `grade_trade` — HTF veto + neutral cap `A+/A -> B` |
| `omen_bot.py:80-86` | `HIS_LADDER` / `his_grade` — the display-only rename shipped 2026-08-28 |
| `signal_runner.py:2342-2361` | `_grade_trade`, the one grading seam (`ENABLE_DOWNGRADE_GRADER`, default off) |
| `signal_runner.py:2373-2392` | `_downgrade_grade` — pushes his S/A/C back through `DOWNGRADE_TIER` (`signal_runner.py:627`) |
| `signal_runner.py:1980-2001` | `_grade_for_levels` — `A->B`, `B->A`, the `A+` stack, the `A+ -> A` demotion |
| `signal_runner.py:2059-2061` | `_calibration_grade` arrival floor `C -> B` |
| `signal_runner.py:2487` | `_apply_x_lift` — writes a bare `TradeGrade.B` |
| `signal_runner.py:2138, 2214` | `_sac_ladder_grade` / `_arrival_ladder_grade` — his S/A/C mapped out through `SAC_TIER` (`signal_runner.py:738`) |
| `signal_runner.py:2209` | `_arrival_ladder_grade(s_promote=True)` writes `TradeGrade.B` |

### Reads the letters — these are behaviour

| file:line | test today | what it gates on instead |
|---|---|---|
| `live_scanner.py:579` | `if grade != "A+": return "WATCH"` | `if grade != "S"` |
| `backtest_week.py:285` | `counted = status == "fired" and grade != "C"` | unchanged — `C` stays alert-only |
| `signal_runner.py:190` | `_SKIP_GRADES = ("X", "D")` | unchanged — `X` is not a grade |
| `signal_runner.py:2585` | `if sig["grade"] != "C" or _min_viable_stop(...)` | unchanged |
| `signal_runner.py:188` | `_GRADE_RANK = {"A+":4,"A":3,"B":2,"C":1,"X":0,"D":0}` | `{"S":3,"A":2,"C":1,"X":0,"D":0}` |
| `signal_runner.py:1976` | `LEVEL_BLOCK_CAP` rank test (**flag off**) | same map |
| `signal_runner.py:2043` | `COUNTER_TREND_CAP` rank test (**flag off**) | same map |
| `signal_runner.py:2499, 2507` | `S_GATE` / `RULE_710_ENABLED`, `grade in ("A+","A","B")` (**both off**) | `grade in ("S","A")` |
| `options_sizer.py:67` | `GRADE_SIZE_PCT = {"A+":1.0,"A":0.8,"B":0.6,"C":0.4,...}` | `{"S":1.0,"A":0.6,"C":0.4,...}` — see §5 |
| `backtest_week.py:456` | `RULE84_STRICT: t.grade in ("A+","A")` (**flag off**) | `t.grade == "S"` |

### Reads the letters — reporting only

`backtest_week.py:634, 927-935, 1047, 1065-1069` · `discord_bot.py:10, 70-72` ·
`live_scanner.py:13, 504, 517, 649` · `analyze_run.py:39, 42, 53, 78` · `gov_probe.py:39` ·
`rank_sim.py:59, 100` · `research/build_bt2y_report.py:26, 239, 313, 707`.
`daily_review.py:218` (`_tier_compliance`) reads `austin_tier`, not the legacy grade — safe.

### Tests that assert the letters

`test_his_ladder.py` (whole file) · `test_austin_tier.py:151,184,275,450,464,478` ·
`spec2_grading_check.py:34-84` (nine asserts straight onto `_grade_pa`) ·
`spec0b_levels_check.py:50-64` · `research/test_downgrade_grader.py:19,123-126` ·
`research/test_sac_ladder.py` · `research/test_rule84_source.py` ·
`research/test_t14_arrival_ladder.py`.

**Not affected:** `research/regression_gate.py` and `research/baseline_3.8.json` key on
Austin's `S/A/X` tiers and on `grade != "D"`, never on `A+/A/B`. Proved, not assumed — the
`noab` arm below returns card-for-card identical.

---

## 2. Four arms, measured

Recall: `research/t0_heldout_recall.py` unchanged — 100 blind cards of 2026-08-28 (34 of
them S), plus the 40 graded engine vetoes of 2026-08-29. Money: `backtest_2y.py` unchanged,
500 sessions, 28 symbols, driven by `research/g71_ladder_bt2y_arm.py`.

| arm | what it is | held-out recall | precision | fires on his `no` | traded | win | mean R | months green |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| **head** | shipped | **23/34 = 67.6%** | 39.7% | 35/66 | 2,437 | 49.7% | +0.5495 | **25/25** |
| **noab** | the RENAME — A+->S, A->A, B->A, C->C | **23/34 = 67.6%** | 39.7% | 35/66 | **2,437** | **49.7%** | **+0.5495** | **25/25** |
| **sac** | `ENABLE_SAC_LADDER=1` exactly as it ships | 20/34 = 58.8% | 45.5% | 24/66 | — | — | — | — |
| **sac_xlift** | + x-lift regraded on his ladder — **the removal diff** | **17/34 = 50.0%** | 41.5% | 24/66 | 1,592 | 44.7% | +0.5053 | 24/25 |
| **sac_all** | ladder is the ONLY grader (`_grade_pa` deleted) | 32/34 = 94.1% | 34.8% | **60/66** | 3,804 | **38.6%** | +0.6951 | 23/25 |

`noab` is not "close to" head. Its 2-year book is **row-for-row identical** — same 76,019
signals, same 2,437 traded, same entry/stop/R on every row. The only difference anywhere in
the file is **119 rows whose letter reads `B` instead of `A`**, and not one of them changes
what fired or what it made. That is the whole case for §4.

Read three things off that before anything else.

**`sac_all`'s 94.1% is bought, not earned.** It is the arm that literally deletes
`_grade_pa`, and it fires on **60 of the 66 cards Austin refused** and on **27 of 27**
vetoed days he graded `no`. Precision *falls* to 34.8%; the book goes to 3,804 trades at a
**38.6% win rate** and durability drops to 23/25. Its mean R does rise (+0.6951 vs +0.5495)
— by less than half the ±1.5799R error bar, on an arm that fires on nine of every ten days
he refused. A gate that fires on everything has perfect recall.

**The removal diff costs 6 of his 34 S days.** 67.6% -> 50.0%. Held-out recall governs
here (DIRECTION.md's standing method finding: every A/B moves less than its own ±1.5799R
error bar, so gate on recall, never on mean R). The recall move is the evidence and it is
negative.

**And it breaks the only gate currently MET.** Durability 25/25 -> 24/25.

---

## 3. `ENABLE_SAC_LADDER=1` does not actually kill `B` — a live defect

`_route` runs `_calibration_grade` (which calls `_sac_ladder_grade`) and **then**
`_apply_x_lift` (`signal_runner.py:2493-2494`, `:2554`). `_apply_x_lift:2487` writes
`sig["grade"] = TradeGrade.B.value` unconditionally.

So with the flag on as shipped, **582 traded rows — 23.9% of the book — come back out of
the "his ladder" arm as a bare legacy `B`.** The flag documented as "the deeper kill" does
not kill `B`, and the arm is not the arm its docstring claims. That is the whole difference
between `sac` and `sac_xlift` above, and closing it costs 3 more of his S days
(20/34 -> 17/34).

`live_scanner.py:30` forces `ENABLE_SAC_LADDER=1` in the live process, so this is not a
research-only wart: the live scanner is running the half-swapped grader right now.

Minimal fix, independent of which ladder ships:

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ _apply_x_lift
-        sig["grade"] = TradeGrade.B.value
-        sig["reason"] = sig.get("reason", "") + " [x-lift:%s]" % X_LIFT
+        sig["grade"] = TradeGrade.B.value
+        sig["reason"] = sig.get("reason", "") + " [x-lift:%s]" % X_LIFT
+        if ENABLE_SAC_LADDER:
+            # G7.1: a lift that writes `B` re-introduces the letter the ladder
+            # exists to remove, on 23.9% of the traded book. The lift removes a
+            # veto; it does not get to name the grade.
+            self._sac_ladder_grade(sig)
         return True
```

---

## 4. The diff — the rename, which is free

`S/A/C/X` everywhere, no `A+`, no `B`; routed set, traded set, P&L and held-out recall all
identical. The only two branches that distinguish `A` from `B` are `_grade_for_levels`'
`A<->B` pair, and they collapse to no-ops once both letters land on his `A` — measured by
the `noab` arm, not argued.

```diff
--- a/omen_bot.py
+++ b/omen_bot.py
@@ -59,86 +59,66 @@
-# --- The one ladder Austin ever sees -----------------------------------------
-# ... (the HIS_LADDER block, omen_bot.py:59-79)
-HIS_LADDER = {"A+": "S", "A": "A", "B": "A", "C": "C", "X": "X", "D": "X"}
-
-
-def his_grade(letter) -> str:
-    """An engine working-state letter as the grade Austin uses. Never inverted:
-    his A covers two engine states, so the map is one-way by construction."""
-    if letter is None:
-        return "X"
-    return HIS_LADDER.get(getattr(letter, "value", letter), str(letter))
+# G7.1 (2026-08-29): the translation layer is gone because there is nothing left
+# to translate. `A+` and `B` were never grades -- they were working states in a
+# promotion lattice -- and the lattice's only A/B branches are no-ops once both
+# letters land on his `A` (research/g71_ladder.md section 5: the `noab` arm's
+# 2-year book and all 34 held-out S cards come back identical). The grade the
+# engine writes IS Austin's ladder now: S / A / C, and X for "should not have
+# fired at all".
 
 
 class TradeGrade(Enum):
-    """omen-3.7 T5: `D` and `X` both mean SKIP, so `X` is now the canonical
-    skip grade and `D` is kept as an alias (TradeGrade.D is TradeGrade.X) so
-    nothing that reads the old letter breaks. TradeGrade("D") still resolves
-    via _missing_. Pure rename — no semantics changed."""
-    A_PLUS = "A+"
-    A = "A"
-    B = "B"
-    C = "C"
-    X = "X"          # skip / do not trade
-    D = "X"          # alias of X — the old letter for the same thing
+    """Austin's ladder, and the only one. `X` is NOT a grade: it means the
+    engine should not have fired. `D` stays an alias of `X` so a caller holding
+    the pre-T5 letter still resolves."""
+    S = "S"
+    A = "A"
+    C = "C"
+    X = "X"          # not a grade -- the engine should not have fired
+    D = "X"          # alias of X -- the old letter for the same thing
@@ grade_trade, omen_bot.py:244-247
         base = PriceActionAnalyzer._grade_pa(candle, lookback_candles, or_high, or_low, is_long)
-        if htf_bias == "neutral" and base in (TradeGrade.A_PLUS, TradeGrade.A):
-            return TradeGrade.B
+        if htf_bias == "neutral" and base is TradeGrade.S:
+            return TradeGrade.A
         return base
@@ _grade_pa, omen_bot.py:263-284 (both sides)
-            if (at_key_level and PriceActionAnalyzer.is_hammer_stick(candle, lookback_candles)):
-                return TradeGrade.A_PLUS
-            if at_key_level and PriceActionAnalyzer.has_large_lower_wick(candle):
-                return TradeGrade.B
+            if (at_key_level and PriceActionAnalyzer.is_hammer_stick(candle, lookback_candles)):
+                return TradeGrade.S
+            if at_key_level and PriceActionAnalyzer.has_large_lower_wick(candle):
+                return TradeGrade.A
             if candle.low <= or_high:
                 return TradeGrade.C
             return TradeGrade.D
-            # ... and the mirror-image short branch: A_PLUS -> S, B -> A
+            # ... and the mirror-image short branch: A_PLUS -> S, B -> A
```

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ -186,190 @@
-# T5 rename: "X" is the skip grade, "D" is its old letter — both rank 0 so
-# either spelling compares correctly.
-_GRADE_RANK = {"A+": 4, "A": 3, "B": 2, "C": 1, "X": 0, "D": 0}
+# G7.1: Austin's ladder. "X" is not a grade; "D" is its old letter -- both rank 0.
+_GRADE_RANK = {"S": 3, "A": 2, "C": 1, "X": 0, "D": 0}
 # Grade values that mean "skip" (TradeGrade.X, formerly TradeGrade.D)
 _SKIP_GRADES = ("X", "D")
@@ -627 @@
-DOWNGRADE_TIER = {"S": "A+", "A": "B", "C": "C"}
+DOWNGRADE_TIER = {"S": "S", "A": "A", "C": "C"}
@@ -738 @@
-SAC_TIER = {"S": "A+", "A": "A", "C": "C", "X": "X"}
+SAC_TIER = {"S": "S", "A": "A", "C": "C", "X": "X"}
@@ _grade_for_levels, signal_runner.py:1980-2001
-        if CLEAR_FOR_APLUS and grade in ("A+", "A", "B"):
+        if CLEAR_FOR_APLUS and grade in ("S", "A"):
             clear = (all(l <= entry for l in levels) if sig["direction"] == "call"
                      else all(l >= entry for l in levels))
-            if not clear and grade != "B":
-                sig["grade"] = TradeGrade.B.value
-                sig["reason"] += " [A->B: entry not beyond all levels]"
-            elif clear and grade == "B":
-                # Open road to new HOD/LOD = Austin's A context (30d: 67% win)
-                if GRADE_FIX and sig.get("signal_type") == SignalType.REENTRY_84_RULE:
-                    # B4/H2: 84% re-entries don't earn the clear-road A promotion
-                    pass
-                else:
-                    sig["grade"] = TradeGrade.A.value
-                    sig["reason"] += " [B->A: breakout conditions, clear of all levels]"
+            # G7.1: the old `A->B` cap and `B->A` promotion each moved a signal
+            # between two letters that are now ONE letter. Only the S leg of the
+            # cap survives -- the same demotion it always was.
+            if not clear and grade == "S":
+                sig["grade"] = TradeGrade.A.value
+                sig["reason"] += " [S->A: entry not beyond all levels]"
             if clear and sig.get("aplus_stack"):
-                sig["grade"] = TradeGrade.A_PLUS.value
-                sig["reason"] += " [A+: first break, displacement, strong PA, clear road]"
-            elif sig["grade"] == "A+":
+                sig["grade"] = TradeGrade.S.value
+                sig["reason"] += " [S: first break, displacement, strong PA, clear road]"
+            elif sig["grade"] == "S":
                 sig["grade"] = TradeGrade.A.value
@@ _calibration_grade, signal_runner.py:2059-2061
             elif ARRIVAL_LADDER in ("off", "s_promote"):
-                sig["grade"] = TradeGrade.B.value
-                sig["reason"] += " [floor B: first with-trend signal of the day]"
+                # G7.1: this writes Austin's letter for ONE DOWNGRADE onto a row
+                # whose downgrade count was never consulted. 56.2% of the traded
+                # book arrives here. The tag says so out loud so the rename does
+                # not hide what `B` was hiding.
+                sig["grade"] = TradeGrade.A.value
+                sig["reason"] += (" [floor A by ARRIVAL ORDER, not by grade:"
+                                  " first with-trend signal of the day]")
@@ _arrival_ladder_grade, signal_runner.py:2209
-            sig["grade"] = TradeGrade.B.value
+            sig["grade"] = TradeGrade.A.value
@@ _apply_x_lift, signal_runner.py:2487
-        sig["grade"] = TradeGrade.B.value
+        sig["grade"] = TradeGrade.A.value
@@ _route, signal_runner.py:2499 and :2507
-        if S_GATE and sig["grade"] in ("A+", "A", "B") and not is_s_gate(self.candles):
+        if S_GATE and sig["grade"] in ("S", "A") and not is_s_gate(self.candles):
-        if RULE_710_ENABLED and sig["grade"] in ("A+", "A", "B"):
+        if RULE_710_ENABLED and sig["grade"] in ("S", "A"):
```

```diff
--- a/live_scanner.py
+++ b/live_scanner.py
@@ -13 @@
-from omen_bot import his_grade   # engine working state -> Austin's ladder
+# G7.1: no translation layer -- sig["grade"] is already S / A / C / X.
@@ -504, -517, -649 @@
-  ... Grade: {his_grade(grade)} ...
+  ... Grade: {grade} ...
@@ -579 @@
-    if grade != "A+":          # R12: no time floor -- the whole window trades
+    if grade != "S":           # R12: no time floor -- the whole window trades
```

```diff
--- a/options_sizer.py
+++ b/options_sizer.py
@@ -66,67 @@
-# "X" is the skip grade (T5 rename); "D" kept as its old letter — both 0%.
-GRADE_SIZE_PCT = {"A+": 1.0, "A": 0.8, "B": 0.6, "C": 0.4, "X": 0.0, "D": 0.0}
+# G7.1: the merged `A` inherits `B`'s 0.6, NOT the old `A`'s 0.8. `B` was 96.9%
+# of every trade the engine has taken and `A` was 3.0%, so sizing the merged
+# tier at 0.8 would quietly raise live size on 96.9% of the book. That is a
+# sizing decision and it is Austin's, not a side effect of a rename.
+GRADE_SIZE_PCT = {"S": 1.0, "A": 0.6, "C": 0.4, "X": 0.0, "D": 0.0}
```

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ -456 @@
-        grade_ok = t.grade in ("A+", "A")
+        grade_ok = t.grade == "S"
@@ -927,-928 @@
-              f"- Traded signals (A+/A/B, viable stop): **{n}** ...
-              f"- Simulated P&L (traded all A+/A/B): ...
+              f"- Traded signals (S/A, viable stop): **{n}** ...
+              f"- Simulated P&L (traded all S/A): ...
@@ -934 @@
-    for g in ["A+", "A", "B"]:
+    for g in ["S", "A"]:
@@ -1065,-1066 @@
-    top = wr([t for t in fired if t.grade in ("A+", "A")])
-    low = wr([t for t in fired if t.grade in ("B", "C")])
+    top = wr([t for t in fired if t.grade == "S"])
+    low = wr([t for t in fired if t.grade in ("A", "C")])
```

```diff
--- a/discord_bot.py
+++ b/discord_bot.py
@@ -10 @@
-from omen_bot import SignalType, Candle, his_grade
+from omen_bot import SignalType, Candle
@@ -69,-72 @@
-        # Austin's ladder only: S green, A teal, C yellow, X red. The engine's
-        # A+/A/B working states are translated by omen_bot.his_grade before they
-        # reach him -- see the HIS_LADDER block there.
-        grade = his_grade(grade) if grade else grade
+        # Austin's ladder only: S green, A teal, C yellow, X red. Nothing to
+        # translate -- the engine writes his letters (G7.1).
         grade_colors = {"S": 3066993, "A": 1752220, "C": 15844367, "X": 15158332}
```

Mechanical, reporting only, same substitution (`A+` -> `S`, `A`/`B` -> `A`):
`analyze_run.py:39,42,53,78` · `gov_probe.py:39` · `rank_sim.py:59,100` ·
`research/build_bt2y_report.py:26,239,313`.

### The one place the rename is not honest, and it must be said out loud

Under the rename, `_calibration_grade`'s arrival floor writes **`A`** — Austin's letter for
*one downgrade* — onto **1,370 traded rows whose downgrade count was never consulted.**
That letter is a lie about 56.2% of the book, and it is the same lie `B` was telling
wearing a better name. The diff puts the truth in the tag
(`[floor A by ARRIVAL ORDER, not by grade: ...]`) so the rename cannot hide it. The real
fix is §7.4.

---

## 5. What breaks

| thing | how it breaks | fix |
|---|---|---|
| `test_his_ladder.py` | its entire subject (`HIS_LADDER`, `his_grade`) is deleted | delete the file; replace with a check that no `"A+"` / `"B"` literal survives under `*.py` |
| `spec2_grading_check.py:34-84` | nine asserts on `TradeGrade.A_PLUS` / `.B` | mechanical substitution |
| `spec0b_levels_check.py:50-64` | asserts the neutral cap lands on `B` | expect `A` |
| `test_austin_tier.py:151,184,275,450,464,478` | fixtures carry `TradeGrade.B.value` / `"A+"` | `TradeGrade.A.value` / `"S"` |
| `research/test_downgrade_grader.py:123-126` | asserts `_grade_pa`'s alphabet is `{A+,B,C,X}` | `{S,A,C,X}` |
| `research/test_sac_ladder.py`, `research/test_rule84_source.py`, `research/test_t14_arrival_ladder.py` | assert `SAC_TIER` / `RULE84_STRICT` letters | mechanical |
| `research/build_bt2y_report.py:26,239,313,707` | carries a column literally labelled "Engine grade (legacy)" beside "Austin grade S/A/C" | the two columns become one — drop `grade`, keep `sgrade` |
| `research/bt2y_trades.json` | the `grade` column changes vocabulary (`sgrade` does not) | regenerate |
| live options sizing | `B`'s 0.6 becomes the merged `A` | pinned to 0.6 in the diff; needs Austin's yes |
| `journal/signal_log_*.jsonl`, every committed `research/*.md` per-grade table | historical text goes stale | leave — they describe the engine of their date |
| `research/regression_gate.py` / `research/baseline_3.8.json` | **does not break** — keys on `S/A/X` tiers and `grade != "D"` | none |

---

## 6. Before / after on the gates, measured not guessed

| gate | target | HEAD | after the RENAME (§4) | after the GRADER SWAP (`sac_xlift`) |
|---|---|---|---|---|
| **Recall** (held-out S) | >= 90% | 23/34 = **67.6%** | 23/34 = **67.6%** — card-for-card identical, same 11 misses | 17/34 = **50.0%** |
| precision, same 100 cards | — | 39.7% | 39.7% | 41.5% |
| **Money** | 55% win, +2.0R | 49.7% / **+0.5495R** on 2,437 | **identical, row for row** | 44.7% / **+0.5053R** on 1,592 |
| **Durability** | every month green | **25/25 — MET** | **25/25 — MET** | **24/25 — LOST** |

(`sac_all`, the full deletion of `_grade_pa`, for completeness: recall 94.1% bought at 34.8%
precision, 3,804 trades, 38.6% win, +0.6951R, durability **23/25 — LOST**.)

The rename is free. The grader swap costs 6 held-out S days, 5.0 points of win rate,
0.044R, and the one gate this project currently meets.

---

## 7. Recommendation

1. **Land the rename (§4).** It is what Austin asked for, literally, it costs nothing on
   any gate, and five session turns is long enough.
2. **Do not land the grader swap** on this evidence. Show him §2's table instead — in
   particular that deleting `_grade_pa` outright (`sac_all`) reaches 94.1% recall only by
   firing on 60 of the 66 days he refused.
3. **Fix `_apply_x_lift` (§3) whichever way this goes.** The live scanner forces
   `ENABLE_SAC_LADDER=1` and that arm currently writes a bare legacy `B` on 23.9% of the
   book, so what runs live is neither ladder.
4. **The letters were never the question. Arrival order is.** 1,370 of 2,437 traded rows
   (56.2%) are chosen by *being first with the trend inside 90 minutes*, not by any grade.
   Deleting that floor costs 56% of the book and 0.086R. That is the one decision worth
   Austin's minutes.
