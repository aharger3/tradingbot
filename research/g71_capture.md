# G7.1 track `capture` — the capture runner and `backtest_week.py`, diagnosed

Austin: *"you did nothing about it and didnt fix capture runner and backtest week py."*

He is right on both, and they are two different bugs, not one.

| | what is unfixed | proof |
|---|---|---|
| **capture runner** | `research/t4_engine_recall.CaptureRunner._route` is still a hand-rolled copy of `SignalRunner._route` that never calls `super()`. Named in commit `145d564e`, not fixed. | held-out S recall **23/34 (67.6%) harness vs 22/34 (64.7%) shipped router**; the extra card is a 0.0783%-of-price stop `MIN_STOP_PCT` rejects |
| **`backtest_week.py`** | the T11 stop-fill guard is **RED at HEAD** and is wired into no gate. `research/t11_stop_fill_fix.py` exits **1**, 12 of 64 checks. | `python research/t11_stop_fill_fix.py` → exit 1; `DISASTER_STOP=0 python research/t11_stop_fill_fix.py` → exit 0 |

Scripts that made every number below: `research/g71_capture_route_ab.py`,
`research/g71_capture_heldout_ab.py`, `research/g71_capture_t11_guard_check.py`.
No engine file was modified. No mark file was read for anything but scoring.

---

## 0. Locating "capture runner"

There is no `capture_runner.py`. `git grep capture_runner` returns nothing. The
name resolves to a class, and there are **nine** of them — every one a
`SignalRunner` subclass that overrides routing to record what the engine
rejected:

| file:line | class | delegates to `super()._route`? |
|---|---|---|
| `backtest_week.py:612` | `BacktestRunner` | **yes** — fixed omen-5.0 |
| `research/t4_engine_recall.py:133` | `CaptureRunner` | **NO** |
| `research/t3_session_extreme.py:43` | `CaptureRunner` | **NO** (also overrides `_emit`) |
| `research/t10_pivot_levels.py:35` | `Capture` | **NO** |
| `research/t11_s_quality.py:39` | `Capture` | **NO** |
| `research/t51_eye_match.py:55` | `Capture` | **NO** |
| `research/t51_s_bar.py:43` | `Capture` | **NO** |
| `research/t6_no_repeat.py:39` | `CountRunner` | **NO** |
| `test_austin_tier.py:364` | `_Capture` | **NO** |

`research/t4_engine_recall.CaptureRunner` is the one that matters: **30 tracked
research modules import `t4_engine_recall`**, including `research/regression_gate.py`
(the repo's `verify:` gate), `research/t0_heldout_recall.py` (the governing
held-out-recall number), `research/t23_stack.py`, `research/build_deck.py` (which
decides which cards Austin is served) and `research/miss_autopsy.py`.

---

## 1. capture runner — what is demonstrably unfixed

### 1.1 Own grade gate: yes. That is the whole bug.

`research/t4_engine_recall.py:141-160` re-implements routing. Its own docstring
says so and shipped anyway:

> `# T10: this replay does NOT delegate to super()._route (it labels the`
> `# rejection reason instead), so every gate the base grows has to be`
> `# named here or it is inert in exactly the rig that scores held-out recall`

`backtest_week.BacktestRunner` carried the identical bug and it was fixed in
omen-5.0 with the comment *"every gate the base grew after it was written was
therefore INERT in every backtest ever run"* (`backtest_week.py:618-628`). The
recall harness never got that fix. `145d564e` (2026-08-29) named it in its commit
body — *"the recall metric is measured on the wrong router"* — and left the code
alone. That is the "you did nothing about it".

**Gate inventory** (`research/g71_capture_route_ab.py`, static arm):

| gate in `SignalRunner._route` | armed at HEAD | present in `CaptureRunner._route` |
|---|---|---|
| `MIN_STOP_PCT` skip | **ON (0.08)** | **NO** |
| `austin_tier` compute | **ON** | **NO** |
| `mesh_blocked` stamp | always | **NO** |
| `_fired_ideas` bookkeeping | always | **NO** |
| `_fired_levels` bookkeeping | always | **NO** |
| `_apply_x_lift` | ON (`clean`) | yes |
| C tight-stop skip | always | yes |
| `S_GATE` / `RULE_710` / `LEVEL_RETIRE` / `ENFORCE_NO_REPEAT` / `NO_REPEAT_ENTRIES` | off | NO — inert *today*, silently inert the day any is flipped |

The last row is the durable half of the defect: flipping any of those five and
re-running `t0_heldout_recall.py` would return an unchanged number and read as a
null result, exactly the way X_LIFT's first cut did (`signal_runner.py:2456-2478`).

### 1.2 Measured cost

`python research/g71_capture_heldout_ab.py`, on `research/marks/probe_s_sweep_2026-08-28.jsonl`:

| | A: shipped `CaptureRunner` | B: delegating router |
|---|---:|---:|
| held-out S recall | **23/34 = 67.6%** | **22/34 = 64.7%** |
| of those hits, on symbols `universe.BACKTEST_SYMBOLS` trades | 16/23 | 15/22 |
| **book-reachable recall** | 16/34 = 47.1% | **15/34 = 44.1%** |
| false fires on his 66 "no" cards | 35 (53.0%) | 35 (53.0%) |
| precision | 39.7% | 38.6% |

The one card that separates the arms is **`QQQ_2025-09-23`**. The harness fires a
B&R put at entry `601.5392` / stop `602.01` — a stop **0.0783% of price**, under
`MIN_STOP_PCT = 0.08`. The book skips it (R30/T9, Austin's *"I meant stock price
not bid ask"*). So the published 67.6% is inflated by exactly the stop-width
artefact R30 exists to kill.

`python research/g71_capture_route_ab.py` over the 151 marked pairs in
`austin_marks_v2.jsonl`: fired entries 125 → 125 (net 0), 2 of 151 days differ,
both SPY (2 entries dropped by `MIN_STOP_PCT`, 2 re-admitted through dedupe), and
S recall 13/77 → 12/77.

### 1.3 The fix does NOT break the verify gate

Ran `research/regression_gate.check()` with the delegating router patched in:

```
baseline: any_signal 75, s_grade 5
current:  any_signal 83, s_grade 12
PASS: no baseline-fired mark went silent.        exit 0
```

(incumbent is `s_grade 13`; the gate only fails on a baseline-fired mark going
silent, and none does.)

### 1.4 Other answers for this class

- **own fill?** No. `CaptureRunner` is detection-only; it books no R.
- **own stop trigger?** No.
- **own symbol list?** No — `research/t4_engine_recall.py:56-58` imports
  `INDEX_POOL_SET`, `EQUITY_POOL`, `pool_for` from `universe.py`. Clean since
  OMEN 6 ticket 14.
- **stale config?** `ENTRY_CUTOFF = "11:00:00"` is hard-coded at
  `research/t4_engine_recall.py:48`, now redundant with
  `SignalRunner.detect_signals`'s own `in_session()` check
  (`signal_runner.py:2637`) — redundant, not wrong. `DEDUPE_BARS` is imported
  from `backtest_week.dedupe_window()` (R16), so that one cannot fork again.

---

## 2. `backtest_week.py` — what is demonstrably unfixed

### 2.1 The T11 guard is red and nothing runs it

```
$ python research/t11_stop_fill_fix.py ; echo $?
T11 STOP-FILL SELFTEST FAILED: 12 of 64 checks are wrong.
1

$ DISASTER_STOP=0 python research/t11_stop_fill_fix.py ; echo $?
t11 stop-fill selftest ok: 64 checks.
0
```

The 12 red checks, verbatim:

```
- long/short: close 1.6R past the stop -> the FLOOR, not the stop price  (got -1.0000R, want -1.2500R)
- long/short: close 1.1R past books -1.1R exactly                       (got -1.0000R, want -1.1000R)
- long/short: a wick through the stop with the close inside books NOTHING (outcome=loss, exit_idx=15)
  ... x2, once for the ladder path and once for the binary path
```

**Cause, measured not guessed.** Commit `68e276ca` (R1/R2) shipped the disaster
stop ON by default — `backtest_week.py:199-200`, `DISASTER_STOP=1`,
`DISASTER_STOP_R=1.0`. `stop_rule.disaster_stop_price` rests it at
`entry ± 1.0 × risk`; with `BNR_STOP_MODE = "level"` (`signal_runner.py:140`)
that is **the level stop's own price**, and `stop_rule.disaster_stop_hit` fills it
on an **intrabar touch**. Nobody re-ran `research/t11_stop_fill_fix.py` after that
landed; it is referenced in `CLAUDE.md:122` and `DIRECTION.md:105` but is not
invoked by `research/regression_gate.py`, which is the only thing the `verify:`
Stop hook runs.

**Consequences, in the shipped book** (`research/bt2y_trades.json`, 2,437 traded):

- **1,207 of 1,222 losses (98.8%) book exactly −1.0000R.**
- **0 losses worse than −1R. 0 at the −1.25R floor.** Worst trade −1.000R.
- `stop_rule.stop_fill_price`'s clamp arm is therefore **unreachable code** in the
  shipped configuration — the 8th instance of this repo's unreachable-rule class,
  and it is the *same rule* T11 made reachable eight days earlier.
- **A wick alone now stops a trade out.** `CLAUDE.md`'s hard rule — *"Wicks stop
  nothing out. Austin settled this five times"* — is false for any move past −1R
  under the shipped default, and neither `CLAUDE.md` nor `DIRECTION.md` says so.

This is not an argument to revert R1/R2. `research/t1_two_stop_model.md` priced
all four arms (`clamp` +0.6699R, `r100` +0.5378R, `r125` +0.5486R, `nofloor`
+0.5270R — every move inside its own bar) and Austin ratified `both`. The defect
is that **the guard that pins the other stop was left red and unwatched**, so the
next real fill regression will land silently.

### 2.2 The rest of the checklist — clean

- **own fill?** No. Three exit sites route through `_stop_fill_px`
  (`backtest_week.py:351`) → `stop_rule.stop_fill_price`. The guard's four
  single-source checks all PASS even at HEAD.
- **own stop trigger?** No. `_stop_hit` (`backtest_week.py:339`) →
  `stop_rule.stop_hit_on_close`; `_disaster_hit` (`:379`) →
  `stop_rule.disaster_stop_hit`.
- **own grade gate?** No. `BacktestRunner._route` (`:620`) delegates to `super()`.
- **own symbol list?** No. `backtest_week.py:38-40` re-exports from `universe.py`.
- **stale config?** `python research/test_t0_ratified.py` → **0 failed**. Every
  ratified default (R16, R17, R18, R20, R21, R22, R25, R26, R27, R30, R30b, R31,
  R31b, R33, R4) is asserted and holds.

### 2.3 The one thing T11 flagged in `backtest_week.py` and never fixed

`SimTrade.pnl`'s Rule 6 branch (`backtest_week.py:317-326`) hard-codes the runner
at `0.0` on a loss and `be_r = 1.0`, and never reads `exit_price` — so the
close-fill and the −1.25R floor cannot reach it. `RULE6_ENABLED = False`
(`backtest_week.py:100`), so it is unreachable today; it re-hides the floor on
that path the day the flag is turned on. T11 called it the 7th unreachable-rule
candidate and left it. Still there.

---

## 3. Diffs

### D1 — `research/t4_engine_recall.py`: delegate, don't re-implement

```diff
--- a/research/t4_engine_recall.py
+++ b/research/t4_engine_recall.py
@@ -133,26 +133,32 @@
 class CaptureRunner(SignalRunner):
     """Capture EVERY signal the engine produces (fired + D-grade/tight-stop
     skips) so we can separate detection (any signal) from filtering (fired
     only). Mirrors backtest_week.BacktestRunner, but records the status."""
     def __init__(self, symbol):
         super().__init__(post_to_discord=False, symbol=symbol, log_signals=False)
         self.captured = []
 
     def _route(self, signals, sig):
-        self._grade_for_levels(sig)
-        self._calibration_grade(sig)
-        # T10: this replay does NOT delegate to super()._route (it labels the
-        # rejection reason instead), so every gate the base grows has to be
-        # named here or it is inert in exactly the rig that scores held-out
-        # recall -- regression_gate, t70_test1_score and t0_heldout_recall all
-        # run through this class. `_apply_x_lift` is a no-op unless X_LIFT is
-        # set. research/test_t10_x_lift.py fails if this call disappears.
-        self._apply_x_lift(sig)
-        if sig["grade"] != TradeGrade.D.value:
-            if (sig["grade"] != "C"
-                    or self._min_viable_stop(sig["entry"], sig["stop"], sig["direction"])):
-                sig["status"] = "fired"
-                self._dir_fired[sig["direction"]] = self._dir_fired.get(sig["direction"], 0) + 1
-                signals.append(sig)
-            else:
-                sig["status"] = "skipped_tight"
-        else:
-            sig["status"] = "skipped_d"
+        """Capture ALL signals, but let the BASE decide which of them fire.
+
+        G7.1 (2026-08-29): this used to reimplement routing and never call
+        super(), so every gate the base grew after it was written was INERT in
+        the one rig that scores held-out recall -- MIN_STOP_PCT (R30/T9, ON at
+        0.08), the austin_tier computation, the mesh_blocked stamp and the
+        _fired_ideas/_fired_levels bookkeeping, plus every OFF-by-default gate
+        the moment anyone flips it. `backtest_week.BacktestRunner` had the
+        identical bug and was fixed in omen-5.0; this is the same fix, eight
+        days after 145d564e named it. Measured cost of the bug:
+        research/g71_capture.md -- held-out S recall read 23/34 = 67.6% on the
+        old router and 22/34 = 64.7% on the shipped one, the difference being
+        QQQ_2025-09-23's 0.0783%-of-price stop.
+
+        The subclass exists to CAPTURE what the base rejects, not to route
+        differently. Status labels keep their existing spellings --
+        `skipped_tight`, not backtest_week's `skipped_tight_stop` --
+        because miss_autopsy.py, w10_gate_autopsy.py and w5_silent_s_autopsy.py
+        read them.
+        """
+        before = len(signals)
+        super()._route(signals, sig)
+        if len(signals) > before:
+            sig["status"] = "fired"
+        elif sig["grade"] == TradeGrade.D.value:
+            sig["status"] = "skipped_d"
+        elif sig.get("level_retired"):
+            sig["status"] = "skipped_level_retired"
+        elif "[skip: repeat entry]" in sig.get("reason", ""):
+            sig["status"] = "skipped_repeat_entry"
+        elif "[skip: repeat idea]" in sig.get("reason", ""):
+            sig["status"] = "skipped_repeat_idea"
+        elif "[skip: stop under" in sig.get("reason", ""):
+            sig["status"] = "skipped_min_stop_pct"
+        else:
+            sig["status"] = "skipped_tight"
         self.captured.append(sig)
```

### D2 — `research/test_t10_x_lift.py`: check #6 now asserts delegation

D1 deletes the literal `_apply_x_lift` call the test greps for, so the test must
change in the same commit or it goes red on a correct fix.

```diff
--- a/research/test_t10_x_lift.py
+++ b/research/test_t10_x_lift.py
@@ -127,10 +127,11 @@
     print("6. every _route that scores held-out recall calls the lift")
     t4 = open(os.path.join(HERE, "t4_engine_recall.py"), encoding="utf-8").read()
     j = t4.find("def _route(self, signals, sig):")
     check(j > 0, "t4_engine_recall.CaptureRunner defines its own _route")
-    check("_apply_x_lift" in t4[j:j + 900],
-          "CaptureRunner._route calls _apply_x_lift -- this replay does not "
-          "delegate to super, and it is the rig regression_gate, t70_test1_score "
-          "and t0_heldout_recall all score on")
+    check("super()._route" in t4[j:j + 1600],
+          "CaptureRunner._route delegates to super, so it inherits the lift AND "
+          "every other gate -- it is the rig regression_gate, t70_test1_score "
+          "and t0_heldout_recall all score on, and a hand-rolled copy made every "
+          "new gate inert there (research/g71_capture.md)")
     bw = open(os.path.join(ROOT, "backtest_week.py"), encoding="utf-8").read()
     k = bw.find("def _route(self, signals: List[dict], sig: dict) -> None:")
     check(k > 0 and "super()._route" in bw[k:k + 900],
```

### D3 — `research/t11_stop_fill_fix.py`: green again, and it asserts the shipped default

Verified by `research/g71_capture_t11_guard_check.py`: part A is 64/64 green,
part B is 6/6 green.

```diff
--- a/research/t11_stop_fill_fix.py
+++ b/research/t11_stop_fill_fix.py
@@ -155,13 +155,29 @@
-def run(day, scale_plan=None):
-    """One replay. ``scale_plan=None`` keeps the shipped default."""
+def run(day, scale_plan=None, disaster=False):
+    """One replay. ``scale_plan=None`` keeps the shipped default.
+
+    ``disaster=False`` by default, and that is a statement, not a convenience.
+    Sections 1-3 pin the LEVEL stop's fill convention: close-triggered, filled
+    at that close, floored at -1.25R, wicks stop nothing. The R1/R2 disaster
+    stop (`68e276ca`, shipped ON at DISASTER_STOP_R = 1.0) is a different rule
+    -- a resting order filled on an intrabar TOUCH -- and with
+    BNR_STOP_MODE="level" it rests at the level stop's own price. Leaving it on
+    makes every level stop-out book exactly -1.0000R and lets a wick alone end
+    the trade, so the close-fill and the floor become unobservable and these 12
+    checks go red without anything in the fill path having regressed. Section 7
+    asserts the shipped default explicitly instead of ignoring it.
+    """
     prev = bw.SCALE_PLAN
+    prev_disaster = bw.DISASTER_STOP
     if scale_plan is not None:
         bw.SCALE_PLAN = scale_plan
+    bw.DISASTER_STOP = disaster
     try:
         return bw.simulate_day("TEST", "2026-01-05", day, pdh=None, pdl=None,
                                bias="bullish" if day[0].close < 150 else "bearish")
     finally:
         bw.SCALE_PLAN = prev
+        bw.DISASTER_STOP = prev_disaster
```

and, appended after section 6:

```diff
+# ---------------------------------------------------------------------------
+# 7. the SHIPPED default: the disaster stop on top of the level stop
+# ---------------------------------------------------------------------------
+
+print("\n7. shipped default (DISASTER_STOP=1, DISASTER_STOP_R=1.0)")
+
+for label, mk_day in (("long", long_day), ("short", short_day)):
+    t = only(run(mk_day(crater(15, 1.6)), disaster=True))
+    close_to(t.pnl / bw.RISK_DOLLARS, -1.0,
+             "%s: the resting -1R order takes the bar that closes 1.6R past"
+             % label)
+    t = only(run(mk_day(crater(15, 1.1)), disaster=True))
+    close_to(t.pnl / bw.RISK_DOLLARS, -1.0,
+             "%s: and the bar that closes 1.1R past" % label)
+    t = only(run(mk_day(wick_only(15)), disaster=True))
+    check(t.outcome == "loss" and t.exit_idx == 15,
+          "%s: a WICK alone ends the trade at the shipped default -- the level "
+          "stop's close rule is unobservable below -1R, and 1,207 of the book's "
+          "1,222 losses book exactly -1.0000R (research/g71_capture.md)"
+          % label)
```

### D4 — wire the guard in, so it cannot rot again

The T11 guard went red on `68e276ca` and stayed red for a day with nothing
noticing, for the same reason the recall gate was red for 16 days: nothing ran
it. It is 64 synthetic-bar checks, no archive, no network — cheap enough for the
Stop hook.

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -6,1 +6,1 @@ (CLAUDE.md line 6)
-verify: python research/regression_gate.py
+verify: python research/regression_gate.py && python research/t11_stop_fill_fix.py
```

### D5 — `backtest_week.py`, the branch T11 flagged and left

Not urgent (`RULE6_ENABLED = False`), but it is a live landmine on the day the
flag flips, and it is the item T11's own report says was "Not fixed — flagged."

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@ -317,10 +317,15 @@
         # Rule 6: BE scale taken -> two-stage P&L
         if self.be_taken:
             be_r = 1.0  # always 1R at breakeven
             be_pnl = be_r * risk_dollars * RULE6_SCALE_PCT
             if self.outcome == "win":
                 run_r = 2.0
                 run_pnl = run_r * risk_dollars * (1 - RULE6_SCALE_PCT)
             else:
-                run_pnl = 0.0
+                # T11: the runner does NOT book a flat 0R on a loss. Its stop
+                # was raised to break-even, but a stop triggers on the CLOSE and
+                # FILLS at that close (stop_rule.stop_fill_price), floored at
+                # -1.25R of the ORIGINAL risk -- a bar that closes through
+                # break-even books what it closed at, not zero.
+                sign = 1 if self.direction == "call" else -1
+                run_r = sign * (self.exit_price - self.entry) / risk
+                run_pnl = run_r * risk_dollars * (1 - RULE6_SCALE_PCT)
             return round(be_pnl + run_pnl, 2)
```

---

## 4. What is NOT in scope here, but is now measured

`research/g71_capture_heldout_ab.py` also prints the other half of T23's finding:
**7 of the harness's 23 S hits are on symbols `universe.BACKTEST_SYMBOLS` does not
trade** — ARM ×2, MSTR ×2, SMCI, ACHR, SPCX. Book-reachable held-out recall is
**15/34 = 44.1%**, not 67.6%. The remaining gap between 15 and T23's "1 of 34 on
the traded book" is session coverage and the entry pipeline, not the router, and
belongs to whichever track owns `backtest_2y`.

---

## 5. Reproduce

```
python research/g71_capture_route_ab.py         # static gate inventory + 151-pair A/B
python research/g71_capture_heldout_ab.py       # held-out S recall, both routers
python research/g71_capture_t11_guard_check.py  # proves D3 turns the guard green
python research/t11_stop_fill_fix.py            # exit 1 at HEAD, 12 of 64 red
DISASTER_STOP=0 python research/t11_stop_fill_fix.py   # exit 0, 64 of 64
python research/test_t0_ratified.py             # 0 failed
```
