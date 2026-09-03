# G7.1 / rrcap — "fix rr cap you said its fixed its not"

**He is right, and both halves of that sentence are true at once.** The RR cap was
fixed in the **backtest** and was never touched in the **live/paper path**. The engine
he would actually trade still sells the whole position at exactly 2R and has no runner
at all.

| path | exit | rows that book more than 2R |
|---|---|---:|
| `backtest_week` / `backtest_2y` (shipped `SCALE_PLAN="hod_then_runner_be"`) | 50% at the session extreme, runner to the next structural level | **463 of 2,437 = 19.00%** |
| `live_scanner` -> `options_sizer` -> `paper_trader` | one limit at `entry +/- 2.0 x risk`, whole position | **0, by construction** |

Austin's threshold — *">10% of trades must be allowed to run past 2R"* — is **met in the
backtest (19.00%) and unreachable in the live path (0%)**. Every money number in
`DIRECTION.md` describes an exit the live path does not run.

Scripts, all committed with this report:
`research/g71_rrcap_dist.py`, `research/g71_rrcap_mfe.py`,
`research/g71_rrcap_runner_ceiling.py`, `research/g71_rrcap_live_proof.py`.
Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29, 500 sessions
2024-08-21 -> 2026-08-21, 76,019 signals, 2,437 traded, `LOSS_HALT` on (857 blocked).

---

## 1. Every cap / clamp / ceiling site in the engine

| # | site | what it caps | shipped state |
|---|---|---|---|
| 1 | `backtest_week.py:836-837` | blind 2R target `entry +/- 2*risk` | **dead** — `backtest_week.py:772` `if SCALE_PLAN: _ladder_bar(...); continue` skips the whole target branch |
| 2 | `backtest_week.py:805-806` | win books at `t.target` exactly | **dead** with #1 — `exit == target` on **2 of 2,437** rows (0.08%) |
| 3 | `backtest_week.py:322` | `run_r = 2.0` hard-coded in `SimTrade.pnl`'s Rule 6 branch | **dead** — `RULE6_ENABLED = False` (`:100`) |
| 4 | `backtest_week.py:851-858` | `runner_tgt = min(PDH/PMH beyond scale, floor(scale)+$1)` — the whole-dollar candidate is appended unconditionally, so `min()` can never aim more than **$1.00 past the session extreme** whatever level sits out there | **live in the backtest**, a real ceiling but not the binding one: best-case ladder R is >=2R on 67.75% of rows (median +2.83R) |
| 5 | **`options_sizer.py:25`** `DEFAULT_RR = 2.0`, consumed at `:202`, `:223`/`:228` (`stock_target = stock_entry +/- rr*stock_risk`), `:291` (`target_premium`), `:307` (`max_reward = risk*contracts*rr`) | the entire live exit | **LIVE AND BINDING** |
| 6 | `options_sizer.py:120` | the Discord card literally prints `(sell all at 2R)` | LIVE |
| 7 | `options_sizer.py:373` `build_futures_plan(rr=DEFAULT_RR)` | futures live path | LIVE, same cap |
| 8 | `paper_trader.py:132-143`, `:200` | `_check_target` closes the **whole** position at `stock_target` on an intrabar touch | LIVE — no scale rung, no runner |
| 9 | `position_sizer.py:9` `DEFAULT_RR = 2.0` | legacy sizer | not on the live path, same constant |
| 10 | `signal_runner.py:2956-2958` and `:3204-3206` | 84% re-entry gate `(tgt - close) >= 1.5 * (close - stop_chk)`, where `tgt` **is the 2R price** | LIVE (`RULE84_SOURCE` default `"0"`, `:321`) — a live **entry** gate whose input is the 2R cap |
| 11 | `signal_runner.py:1615-1622` `blocking_levels()` 2R path window | was a grade cap | **fixed** — `LEVEL_BLOCK_CAP = False` (`:181`), `MESH_S_VETO` default `"0"` (`:1222`) |
| 12 | `stop_rule.py` `MAX_LOSS_R = 1.25` | worst-case LOSS | correct, not an RR cap |

`live_scanner.py:631` calls `build_options_plan(...)` **without `rr=`**, so #5 is the
only exit the live book has. `research/g71_rrcap_live_proof.py` output:

```
options_sizer.DEFAULT_RR = 2.0
entry 100.00 stop 99.50 risk 0.50 -> stock_target 101.00  = 2.000 R  | max_reward $2000 / max_loss $1000 = 2.000
entry 250.00 stop 248.00 risk 2.00 -> stock_target 254.00  = 2.000 R  | max_reward $2000 / max_loss $1000 = 2.000
entry  35.00 stop 34.90 risk 0.10 -> stock_target  35.20  = 2.000 R  | max_reward $2000 / max_loss $1000 = 2.000
```

---

## 2. The commit that claimed the fix

Two commits are in the frame and **neither one touched the live path**.

- **`318dda08` — "R25: a level in the 2R path is a TARGET, not a cap"** (2026-08-29).
  Real, and it landed: `LEVEL_BLOCK_CAP True -> False`, `MESH_S_VETO` default `1 -> 0`,
  `path_levels`/`path_target` stamped on every signal. But it caps a **GRADE**, not a
  target. It made a level in the path stop being a reason to refuse the trade. It did
  not change where any trade exits, in either path. `git show 318dda08 --stat` ->
  `signal_runner.py | 27 +++--`, one file.
- **`6f3bcc5b` — "T5: the money gate is not an exit problem"** (2026-08-29). T5 is the
  ratified owner of **R9 "level target first, 2R fallback"**
  (`research/t0_ratified_rebaseline.md:269`). It measured 47 target/scale arms and
  **shipped nothing** — correctly, since 0 arms beat the shipped exit outside their own
  error bar and level-first cost **-0.1145R**. R9 therefore remains an unlanded ratified
  item, and the live path kept its flat 2R.

So the honest history: **the backtest's blind 2R was retired long before either commit**
(`SCALE_PLAN` default `"hod_then_runner_be"`, `backtest_week.py:120-128`), and nobody
ever ported that to `options_sizer` / `paper_trader`. "It's fixed" was said about the
backtest and is true there; his complaint is about the live card and is also true.

The stale sentence that keeps re-creating this confusion sits in two places and is now
**wrong for the shipped backtest**: `Austin's Vault/Projects/omen-rulebook.md:917,969`
and the same text in `DIRECTION.md` — *"Every row in the two-year book plans exactly
2.000 R:R."* Measured: `exit == target` on 2 of 2,437 rows.

---

## 3. Does the cap still bind? The numbers

`research/g71_rrcap_dist.py` over the 2,437 traded rows:

```
mean R +0.5495   median -0.1200   min -1.000   max +24.348
win rate 49.73% (1212/2437)
R == 2.000 exactly :   2  (0.08% of traded,  0.17% of winners)
R  > 2.000         : 463  (19.00% of traded, 38.20% of winners)
exit == target price:  2  (0.08% of traded)
winner buckets: <1R 407 | 1-1.5R 182 | 1.5-2R 158 | ==2R 2 | 2-3R 187 | 3+R 276
most common R value: -1.000 x1207 (the stop); the winners have no mode -- continuous
```

456 of the 463 rows past 2R are `scaled` rows: they got there **through the ladder**, not
through `t.target`. **In the backtest the 2R cap does not bind.**

Run the same engine with `OMEN_SCALE_PLAN=none` and it binds absolutely — T5's own
flat-2R row (`research/t5_structural-target.md` s1): **49.7% win, mean winner +1.999R,
mean +0.4904R, and 0% of trades exceed 2R.** That is the arm the live path runs.

## 4. What the exit still leaves on the table

`research/g71_rrcap_mfe.py` replays every traded row against its archived RTH bars
(0 skipped) using `stop_rule.py`'s one fill definition and no target:

```
booked   mean +0.5495R  median -0.1200   >2R  463 (19.00%)
MFE      mean +4.0291R  median +2.0263   >=2R 1231 (50.51%)  >=3R 923 (37.87%)  >=4R 740 (30.37%)
no-tgt   mean +0.5597R  median -1.0000   >2R  362 (14.85%)
capture (booked/MFE) over rows with MFE>=0.5R: n=2113, median 0.139
reached >=2R on tape but booked <2R: 766 rows (31.43%), mean booked +0.4793R, mean MFE +4.7009R
```

**Half the book (50.51%) touches 2R on the tape; 19.00% keeps it.** But removing the
target entirely books **+0.5597R vs +0.5495R** — a rounding error. The room is real and
the exit is not how you get it, which is T5's finding on 47 arms and the standing
`omen-selection-not-exits` memory. Do not sell a target change as a money-gate fix.

## 5. The ladder's own ceiling (`backtest_week.py:851-858`)

`research/g71_rrcap_runner_ceiling.py`, best case if both rungs fill, PDH/PMH omitted so
this is an **upper bound**:

```
ladder best-case ceiling R: mean +3.6951  median +2.8333  p90 +7.2449  max +42.7500
  ceiling >= 2.0R : 1651 (67.75%)   >= 3.0R : 1151 (47.23%)   >= 4.0R : 756 (31.02%)
scaled rows (n=1217): ceiling mean +2.8535 median +2.1667; >=2R on 665 (54.64%)
```

`cands.append(math.floor(scale_level) + 1.0)` is unconditional and `min()` is taken, so a
PDH sitting $4 out can never be the runner target. A genuine cap, not the one he is
hitting, and worth a separate ticket — not this one.

---

## 6. Proposed fix — NOT applied

The defect is **path parity**, not the number 2.0. Two steps; only the first is a diff.

**Step 1 (this diff): make the live multiple configurable and stop the card from lying.**

```diff
--- a/options_sizer.py
+++ b/options_sizer.py
@@ -22,7 +22,17 @@

 CONTRACT_MULTIPLIER = 100
 DEFAULT_MAX_LOSS = 1000.0
-DEFAULT_RR = 2.0
+# G7.1/rrcap: the live path's ONLY exit. `backtest_week` retired the blind 2R
+# target long ago -- its shipped SCALE_PLAN ("hod_then_runner_be") scales 50%
+# at the session extreme and runs the rest to the next structural level, and
+# 19.00% of the 2,437-trade book books more than 2R (research/g71_rrcap.md).
+# `live_scanner.py:631` builds its plan without `rr=`, and `paper_trader`
+# closes the WHOLE position at this target on an intrabar touch, so the live
+# path can never exceed 2R. Austin, 2026-08-29: "fix rr cap you said its
+# fixed its not." This constant IS the cap. It stays 2.0 until the runner leg
+# lands (step 2) -- widening the target on a position that has no runner is
+# the arm T5 priced at inside its own error bar -- but it is readable now, so
+# the two paths can be reconciled without a code edit.
+DEFAULT_RR = float(os.getenv("OMEN_LIVE_RR", "2.0"))
 DEFAULT_DELTA = 0.5  # ATM ~ 0.5
@@ -117,7 +127,9 @@
             f"Entry:      ${self.entry_premium:.2f}\n"
             f"Stop:       ${self.stop_premium:.2f}  (sell if drops here)\n"
-            f"Target:     ${self.target_premium:.2f}  (sell all at 2R)\n"
+            f"Target:     ${self.target_premium:.2f}  (sell ALL at "
+            f"{abs(self.stock_target - self.stock_entry) / abs(self.stock_entry - self.stock_stop):.3g}R"
+            f" -- no runner leg on the live path)\n"
             f"Contracts:  {self.contracts}  -> max loss ${self.max_loss:.0f} / max reward ${self.max_reward:.0f}\n"
```

`import os` is already present at `options_sizer.py:12`; `stock_entry != stock_stop` is
guaranteed by the `ValueError` raised at `:221`/`:226` and re-checked at
`live_scanner.py:605`.

**Step 2 (a track, not a diff): port `SCALE_PLAN="hod_then_runner_be"` into
`paper_trader`.** Live needs the same two rungs the book is measured on — 50% off at the
session extreme as of the entry bar, runner on the original stop to the next structural
level — sharing `backtest_week.py:851-858`'s target construction the way `stop_rule.py`
is already shared. Until that lands, no live/paper number is comparable to any figure in
`DIRECTION.md`, and 0% of live trades can run past 2R.

**Do not sell step 2 as a money-gate fix.** Section 4 measures the whole exit family at
+0.01R. It is a correctness fix so the live path books what the book books.
