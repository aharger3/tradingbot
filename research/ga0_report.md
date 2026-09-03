# THE EXIT LADDER — build report

**Lane:** exits. **Commits:** `617fdb06` (backtest_week.py, levels_ladder.py, self-check), `a4cd1025` (htf_levels.py). **Recon of record:** `b26f4b9c` (`research/g99_rung_recon.py`).

---

## 1. WHAT SHIPPED

| file | what landed | flag | default |
|---|---|---|---|
| `backtest_week.py` | runner-target guard at the trade-creation site (`:1361-1367`) — replaces a legacy-plan `runner_tgt` that sits inside 2R with the 2R price | `LADDER_RUNNER_GUARD` | **`"0"` — OFF** |
| `backtest_week.py` | `_ladder_bar_4` (`:940-1029`), a new sibling to `_ladder_bar`. Manages 1–4 rungs, trails the stop, books weighted fills. Legacy `_ladder_bar` untouched. | `OMEN_SCALE_PLAN=four_rung` | **unchanged (`hod_then_runner_be`)** |
| `backtest_week.py` | `SimTrade.rungs` / `SimTrade.fills` (`:326-366`), new first branch in `pnl` (`:582-591`) summing weighted R across fills | — | empty tuple/list, inert |
| `backtest_week.py` | 8 more env flags: `LADDER_WEIGHTS`, `LADDER_PSYCH_TOL`, `LADDER_PSYCH_STEP`, `LADDER_PT4_MODE`, `LADDER_PT4_R`, `LADDER_MIN_RUNG_GAP`, `LADDER_TRAIL`, `LADDER_TREND_TEST` | each | spec defaults |
| `levels_ladder.py` **(new)** | `build_rungs()` to the frozen §1.1 signature: PT1 session extreme, PT2 nearest named level beyond PT1, PT3 = 2R with psych/named substitution, PT4 runner (`max`/`rmult`/`structure`) | consumed only under `four_rung` | inert |
| `research/htf_levels.py` **(new)** | causal 1h/4h bucketing + pivots + whole-dollar levels | `LADDER_HTF_PIVOTS` | **`"0"` — and `=1` is a no-op that prints a warning. Not wired to anything.** |
| `research/_a_ladder_selfcheck.py` **(new)** | 35 checks, exit 0 | — | not in the `verify:` gate |
| `research/g99_ladder_ab.py` + `.json` | the A/B that produced the table below | — | **uncommitted / untracked** |

**Byte-identical when off — true, but not proved by anything committed.** Two independent reviewers replayed `simulate_day` at HEAD vs the parent commit with the shipped default env: 9,539 trades / 120 sessions, 0 diffs; and 1,612 trades / 120 sessions, 0 diffs. The proof cited *inside the shipped code* (`backtest_week.py:201-202` → `research/test_exit_ladder.py::test_shipped_default_byte_identical`) does not exist in the tree. Neither does `research/ga1_ladder_replay.py` (cited at `:264`) nor `research/fixtures/ladder_baseline.json`.

**Not shipped:** the exit replay rig, the mandated tolerance sweep, the 11 spec tests, the fixture, the book stamp.

---

## 2. WHAT IT IS WORTH

**The four-rung ladder does not beat a flat 2.5R target, does not beat a flat 4.0R target, and does not clear its own +0.200R pass bar. Do not ship `OMEN_SCALE_PLAN=four_rung`.**

**Fill and denominator, stated once.** Population: `research/bt2y_trades_retest_on.json`, first-of-day only, size-gated on `signal_runner.min_risk_floor` → **444 trades out of 498 sessions** (54 dropped by the gate, 0 missing bars). Entries and stops frozen at the book's own honest fills. Exits replayed bar-by-bar from `entry_i + 1`, **truncated at 11:00**, stop wins any tied bar. 1R = $1,000.

`python research/g99_ladder_ab.py`, run in this workflow:

| arm | mean R | **$/trade** | win | months green | max DD |
|---|---:|---:|---:|---:|---:|
| the book today | +0.038 | $38 | 46.0% | 12/25 | −$20,416 |
| blind 2R | +0.040 | $40 | 35.1% | 13/25 | −$30,286 |
| flat 1.5R | +0.048 | $48 | 41.9% | 13/25 | −$23,767 |
| flat 2.5R | +0.098 | $98 | 32.7% | 14/25 | −$25,583 |
| **flat 4.0R** | **+0.153** | **$153** | 27.7% | 13/25 | −$37,314 |
| four-rung 30/30/30/10 | +0.092 | $92 | 40.8% | 12/25 | −$16,980 |
| four-rung 50/20/20/10 | +0.073 | $73 | 46.8% | 13/25 | −$17,804 |

Reference points, same book: available while still alive **+2.141R** (median +1.015R, `research/g97_mfe.py`). His bar is **$397/day**.

**The column is per trade, not per day.** The script passed `n=444` (trades) into `g86.stats` as `n_days`, while the book's own denominator is 498 sessions. Per session: book **$34**, four-rung 30/30/30/10 **$82**, flat 4.0R **$136**. Every dollar in the table is 12.2% high against the ruler CLAUDE.md's $28/$397 figures use.

**A reviewer ran the same 444 rows through the *actual shipped* `_ladder_bar_4`, not the replica:** `LADDER_TRAIL=be` → **+0.0946R/trade**; `LADDER_TRAIL=prev_rung` → +0.0344R (and that arm is corrupted, see §3.4). So the shipped engine agrees with the replica's +0.092 and the verdict does not turn on the duplication.

**Two defects make the hurdle itself untrustworthy, and they push opposite ways.** (a) The flat arms are scored on a *wick* stop (`g97.walk`) while the ladder arms use the house close stop; rescored under the house rule, flat 4.0R goes to **+0.3127R ($312/trade)** — the gap widens. (b) 46 of 444 trades are still open at 11:00 and marked to that close; on **resolved trades only**, flat 4.0R is **−0.0075R** and the best flat arm is flat 1.5R at +0.0455R — the hurdle collapses. Both are real; neither has been resolved.

**What follows.** The ladder is dead at these defaults. The spec's own FAIL-FAST fallback — ship a flat 4R single rung — is **not yet earned either**, because that arm's entire edge is 46 unrealized 11:00 marks. Ship nothing from this lane until the replay runs to the close the engine actually manages to and both arms use one stop rule.

The one piece with measured leverage that survives is the **runner guard**, and its effect is smaller than its reach: over a 60-symbol-day / 612-trade slice it changed `runner_target` on 74 rows but changed the **exit** on only **30**, moving $68,333 → $72,189 — because `hod_then_runner_be` moves the stop to breakeven after PT1, so the runner usually BE-stops before either target. Reach is not effect.

---

## 3. WHAT IS BROKEN

### 3.1 Provenance — a ladder book is indistinguishable from a shipped book (CRITICAL)

`research/book_stamp.py:56-64` — **none of the 10 `LADDER_*` flags is stamped.** `engine_flags()` returns a byte-identical dict (sha `e656d8ec…`) for defaults, for `LADDER_RUNNER_GUARD=1`, and for `LADDER_WEIGHTS=50/20/20/10 + LADDER_PT4_R=8.0 + LADDER_TRAIL=prev_rung + LADDER_TREND_TEST=qqq`. Two demonstrably different books get the same stamp. This is verbatim the failure fixed for `RETEST_REQUIRED`/`S_GATE`/`RULE_710_ENABLED` on 2026-09-02, three lines above where these belong.

`research/book_stamp.py:118-125` — `levels_ladder.py` is absent from `ENGINE_PY`, so an uncommitted edit to the module that computes every rung price will not mark the book dirty.

### 3.2 The certifying test does not execute the shipped code (CRITICAL)

`research/_a_ladder_selfcheck.py:87-149`. A line-level tracer scoped to `backtest_week.py` recorded **zero hits** on: the runner-guard block (`:1361-1367`), the four_rung rung-build (`:1326-1341`), the four_rung dispatch (`:1200-1201`), the entire "STOP WINS THE BAR" block (`:994-1005`), and the EOD flush (`:1401-1411`). `guard_probe()` is a hand copy of `backtest_week.py:1319-1367`; it sets `bw.LADDER_RUNNER_GUARD = True` and nothing reads it. `check("runner guard OFF by default changes nothing (0 rows)", True)` at `:142-145` is a literal — an assertion that cannot fail. The 278/444 reachability headline measures the copy, not the ship. Both the function docstring and the commit message claim the opposite ("the ACTUAL code path, not a re-derivation").

Four checks named "stop wins the bar" passed against the *disaster* branch (`:968-977`), a different code path.

### 3.3 "The stop wins the bar" is an unreachable branch (CRITICAL)

`backtest_week.py:965-1005`. `DISASTER_STOP_R = 1.0` puts the resting disaster order at **exactly `t.stop`**, and step 2 tests it on a **touch**, before step 4. So any bar that closes beyond the original stop has already touched it and exits at step 2. Counted on the real book: **0 of 444** trades exit through `_stop_hit` with `stop_lv == t.stop`; 214 exit on the disaster touch at exactly −1.000R. Over a separate 1,799-trade run: 1,189 disaster exits, 439 step-4 exits, and `PESSIMISTIC_FILL` clamp fired **0 times**.

Dead lines in the same block: `:970-973` (partial-remainder arithmetic — any fill sets `runner_stop`, which disables the disaster guard, so `remaining` is always 1.0), `:996-997`, `:1003-1004` (84%-rule arming, 0 of 439).

Consequence: under `four_rung` every original-stop loss books exactly −1.000R, the **−1.25R floor never binds**, and the self-check's "floor never breached" tests a path that does not run. This is the same shape as `research/x2_stop_floor_audit.md`.

### 3.4 A booked fill at a price the bar never traded (CRITICAL)

`backtest_week.py:996-997`. The clamp books remaining weight at `t.stop` — the **original** stop — even when the working stop has trailed into profit. Under `LADDER_TRAIL=prev_rung`, 4 of 444 rows book outside the stop bar's range. COIN 2025-02-24 put, entry 236.66, risk 0.94, resting stop 235.40; stop bar H/L 235.71/234.86; honest `stop_rule` fill 235.66 (**+1.064R** on 66.7% of the position); engine books **237.60** (−1.000R), 1.89 above the bar's high. Trade R goes +0.83 → −0.22. Same on AMD 2025-04-23, ORCL 2025-10-20, COIN 2025-12-18. This is the honest-fill sin of 2026-08-30, re-introduced. Every `prev_rung` number is corrupted.

Fix is one line: clamp to `stop_lv`, not `t.stop`.

### 3.5 `ENTRY_SCRATCH` + `four_rung` books $0.00 (CRITICAL)

`backtest_week.py:1195-1199` removes the trade without appending to `t.fills`; the new `if self.rungs:` branch at `:588` then sums an empty list → 0.0. Reproduced directly (entry 100.00, stop 99.00, scratch at 99.00 → `pnl = $0.00`). Over 4 symbols × 90 sessions: **753 of 3,687 trades (20.4%)** had rungs, zero fills, and booked $0.00; their real exits totalled **−714.8R**. `ENTRY_SCRATCH` is off by default but it is a documented A/B arm.

### 3.6 `htf_levels.py` makes the bug worse, not better (CRITICAL)

`research/htf_levels.py:204-206`. `htf_level_beyond` picks the **nearest** level beyond the current price with no distance floor and no reference to 2R. On 60 real size-gated first-of-day rows: median distance **0.545R**, min 0.043R, **72% inside 1R**, 9 of 60 inside 0.25R. A second reviewer, 80 calls: min **$0.005**, and 53 of 80 (66%) returned a level within `PIVOT_DEDUPE_FRAC` of the entry itself. g99 measured the confirmed `simulate_day` bug at 68.2% inside 2R; **this module is at 90%.** Austin's rule is "trumped by HTF levels *if one is close* [to 2R]" — this returns levels close to *entry*.

`research/htf_levels.py:145,157` — an HTF pivot from the **current session can never be returned**: `pivot_levels` needs `i <= n-4`, and inside the 09:30–11:00 lane the cursor day contributes at most 2 buckets on 1h and 1 on 4h. Measured **0 of 1,349 pivots** from the cursor day across 20 rows × both timeframes. Every level is at minimum one full prior session stale.

`research/htf_levels.py:61-66` — bare `except Exception: return []`. With `fetch_day` patched to raise on every call, `htf_level_beyond` still returned `{'price': 160.0, 'name': 'whole $1'}`. A dead archive is indistinguishable from "no pivot was near".

**Lookahead itself is clean.** Independently verified three ways on the Agent A side (mutation of every post-decision bar: 0 of 400 pools changed; end-to-end scramble at K=20/35/55: 4,218 trades byte-identical; every rung traced to a causal source) and on the htf side (poisoning the cursor day and all 331 future sessions changed nothing; poisoning the prior session did change the answer, so the control is live).

### 3.7 Majors

| where | what |
|---|---|
| `backtest_week.py:1362` | The guard's floor is `target`, not 2R. `target = sig.get("target") or 2R`, and 84%-reentry signals carry the **original** trade's target: of 543 `reentry_84_rule` rows, **90.2% have R(target) < 2.0**, median 1.764R. On those rows the guard installs a sub-2R runner while calling itself the 2R floor, and can pull the target *nearer* (observed once: AMZN 2025-12-08, 1.691R → 1.667R). |
| `options_sizer.py:162-186` | An independent verbatim copy of the same `(scale_level, runner_target)` computation. `LADDER_RUNNER_GUARD` does not reach it. `live_scanner.py:613`, `:489` and `paper_trader.py:32-33` call it — so the **live Discord plan and the paper book keep publishing the inside-2R runner target with the flag on**. The bug is half fixed. |
| `backtest_week.py:1015`, `:963-968` → `backtest_2y.py:239` | The book's `exit` field is one leg's price while `r` is the weighted average. On 3,691 four_rung trades, **1,306 (35.4%)** disagree by >0.01R; a rig that recomputes R from `entry/stop/exit` — which the honest-fill research rigs do — reads **+0.080R** against the ladder's true +0.043R. |
| `backtest_week.py:1405-1411` | EOD flush hardcodes `outcome="scratch"` even after the ladder banked money. **168 of 11,226** four_rung rows are `scratch` with \|pnl\| > $1, **157 of them booking more than +1R**. Win rate and every outcome-filtered facet of a four_rung book is wrong, and `_arm_84` (which arms only on `outcome == "loss"`) sees a scratch. `t.scaled` is also never set on a laddered trade. |
| `backtest_week.py:177-183` vs `:1200-1205` | `OMEN_SCALE_PLAN` is neither case-folded nor validated. `Four_Rung`, `FOUR_RUNG`, `four-rung`, `fourrung`, `typo_plan` are all truthy but `!= "four_rung"`, so they fall into the **legacy** `_ladder_bar` where `SCALE_PLAN == "hod_then_runner_be"` is also False — disabling the breakeven arm. A silent third book, no error. `LADDER_TRAIL` and `LADDER_TREND_TEST`, added in the same commit, both `SystemExit` on a bad value. |
| `backtest_week.py:210-221` | `_parse_ladder_weights` divides by 100 and never normalizes. `"60/30/20/10"` → sums to **1.20** (a 1.2× book, ~20% inflated dollars); `"3/3/3/1"` → 0.10. The docstring promises "a 4-tuple summing to 1.0". Directly violates "size-gate every money number", and the weight sweep is exactly where such a vector gets typed. |
| `backtest_week.py:210-247` | A malformed `LADDER_*` var raises at **module import**, killing `backtest_2y.py`, `backtest_12mo.py`, `research/daily_homework.py` and ~40 research scripts on a run that never touches the ladder. `LADDER_WEIGHTS=banana` escapes as a raw unguarded `ValueError` before the intended message. |
| `backtest_week.py:279-292` | `LADDER_HTF_PIVOTS` is a flag with no effect. Proven: 5 symbols × 12 sessions, `four_rung`, `=0` and `=1` both give book_id `2cf683db…`. `grep -rn htf_levels --include=*.py .` finds no import. |
| `levels_ladder.py` coalesce (`:174-187`) | `min_gap_r` drops the **further** rung on a tie, so **PT4 is absent on 92 of 444 rows (20.7%)** and PT3 — the docstring's "always available" backbone — on 26 (5.9%). g97 showed the book's edge is a fat right tail; a plan with no runner on a fifth of its trades cannot reach it. |
| `levels_ladder.py:184-187` | Weights are assigned by **sorted position**, not rung identity. On the real 444: only **52 (11.7%)** run four rungs at all, and only **22 (5.0%)** are PT1+PT2+PT3+PT4 in order — i.e. actually 30/30/30/10. 292 run 33/33/33, 100 run 50/50. The "10% runner" slice lands on PT1 or PT2 on a real slice of the book. The arm labels in the §2 table are not what was measured. |
| `research/g99_ladder_ab.py:353-364` vs `:228-234` | Two stop rules in one table: flat arms via `g97.walk` (intrabar **wick**, exactly −1.000R) against ladder arms via `bw._stop_hit` (close) + `stop_fill_price`. 31 of 444 rows (7.0%) die on a wick without ever closing past the stop. House rule: wicks stop nothing. |
| `research/g99_ladder_ab.py:77,213,248-249` | Every replayed arm is truncated at 11:00 and the remainder marked to that close, while "book today" is a realized number (443 of 444 book exits land before 11:00). flat 4.0R's +0.1533R = 398 resolved trades at **−0.0075R** plus **46 open positions marked at +1.5450R** — 104% of the arm. The mark is one-sided by construction. |
| `research/g99_ladder_ab.py:101-187`, `:263-267` | Duplicate `build_rungs`, on a stale blocker note (`levels_ladder.py` exists on this branch). Fed the *shipped* pool (`backtest_week._named_level_pool`, which carries all six named levels in both directions plus `signal_runner.pivot_levels`) the ladders differ on **23 of 444 rows (5.2%)**. INTC 2024-09-17 put: replica `[21.285, 21.22, 19.76]` vs shipped `[21.285, 21.22, 21.0699, 20.96]` — a runner $1.20 apart on a $21 stock. |
| `research/htf_levels.py:192-196` | Pivot `kind` is discarded. **13 of 60** winning levels are a pivot **low** returned as an upside target. |
| `research/htf_levels.py:194-196` | Names carry only `HH:MM`, no date: 48 1h pivots → **12 distinct names**; `'pivot high @09:30'` covers 8 different prices spanning $190.34–$217.49. The intended consumer (`backtest_week.py:317`) keys a dict by name, so merging would **silently drop 36 of 48 (75%)** on last-write-wins. |
| `research/htf_levels.py:75-109` | Session-anchored bucketing: 1h yields `[60,60,60,60,60,60,30]`, "4h" yields `[240,150]` — **half of every 4h candle is 2.5h**, which biases pivot confirmation onto the stubs. Premarket is discarded by `pf.rth()`, so PMH/PML can never be an HTF level. Pivot windows also cross the overnight gap: **32 of 48** confirmation windows span more than one day. |
| `research/htf_levels.py:112-140` | **0.63–0.76 s per call, no cache** — 60 CSV day-parses per call, re-done per timeframe. 444 rows ≈ 5–20 min; the 4,508-trade book ≈ **3 hours per arm**. The A/B this lane needs is impractical to run. |
| verify gate | `grep -c 'levels_ladder\|LADDER_RUNNER_GUARD\|four_rung'` returns **0** for both `research/regression_gate.py` and `research/test_runner_stop.py`. The `verify:` line gates none of the new engine. `research/_a_ladder_selfcheck.py` is the only coverage and nothing runs it automatically; its own final line prints `"0 FAILED of (see above)"` — a pass/fail report with no denominator. |

### 3.8 Gate status

`regression_gate.py` PASS · `test_runner_stop.py` PASS · `test_retest_gate.py` PASS · `_a_ladder_selfcheck.py` PASS (but see §3.2) · **`test_universe_single_source.py` FAIL** — 3 private symbol lists in `research/g83_futures_arm.py:67`, `research/g83_sizing.py:91`, `research/g83_verify_2.py:43`. Pre-existing, dated 2026-08-30; `git diff 617fdb06^ 617fdb06 --name-only` confirms the ladder commit did not touch them.

---

## 4. HUMAN BLOCKERS

Two. The spec listed six; four of them (what is PT2, what is a "medium average", the missing 10%, trend-vs-chop) only matter if the four-rung ladder ships, and it should not. Do not spend his time on them.

**1. Was the near runner target ever right?**
303 of 444 first-of-day trades carried a runner target inside 2R, median 1.300R, **79 of them under 0.5R**. Show 6 of those 79 as charts with both lines drawn — the actual runner target and the 2R price. *"Was the near one right on any of these?"*
Decides whether `LADDER_RUNNER_GUARD` flips to default ON. Until he answers it stays off.

**2. Are you still in the trade at 11:00, and where do you get out?**
This is the new one, and it is the biggest single hole in the measurement. Under a flat 4R target, **46 of 444 trades are still open at 11:00** and those 46 supply **104%** of that arm's entire edge — the arm's resolved trades are net negative (−0.0075R over 398). The replay stops managing at 11:00; the engine manages to the close. Show 6 charts of trades still running at 11:00 with the 11:00 price marked. *"Would you still be holding here — and where does this one end for you?"*
Decides the replay window, and therefore whether flat 4R is a real result or an accounting artefact. Every dollar figure in §2 depends on it.

---

## 5. WHAT I DID NOT DO

- **No fixes.** This pass was measurement and review only; nothing in §3 was corrected.
- **`research/ga1_ladder_replay.py` was never written**, so the mandated psych-tolerance sweep (`0.00r` … `0.50r`, cents, pct, crossed with `psych_step ∈ {0.50, 1.00}`) **never ran**. The precedence rule of §2 is entirely unmeasured — including its **mandatory null arm**. Everything in §2 is at the spec's stated defaults only.
- **P4 was never run.** No end-to-end `backtest_2y.py` re-measure, so the ±15% replay-vs-book check is open, and the replay cannot see `loss_halt` or the 84% re-entry cascade.
- **`research/test_exit_ladder.py` was never written** — all 11 spec tests, including `test_shipped_default_byte_identical` and `test_runner_guard_reachable`, are absent, and `backtest_week.py` cites them anyway. `research/fixtures/ladder_baseline.json` was never generated.
- **`LADDER_TREND_TEST` reachability was not checked on the 444-row population.** It was checked on an 8-symbol slice (daily 5,177 trending / 6,049 chop; qqq 6,401 / 4,825 — both inside the 15–85% gate there), which is not the pass-test book.
- **`LADDER_HTF_PIVOTS` was not wired.** The seam is unowned: `htf_levels.py` reads `data_archive` by symbol/day, `backtest_week` holds yfinance/Polygon `candles` in memory. Neither agent will pick a source of truth.
- **`research/book_stamp.py` was not updated** — no `LADDER_*` flags in `FLAG_SOURCES`, no `levels_ladder.py` in `ENGINE_PY`.
- **`options_sizer.py`, `live_scanner.py`, `paper_trader.py` untouched**, so the live/paper runner target is unguarded (§3.7).
- **`signal_runner.py` untouched** — detection is byte-identical, by design.
- **`research/g99_ladder_ab.py` and its JSON are uncommitted.** Nothing in §2 should be quoted until they are, per "every claim routes through a committed script".
- **No mark corpus was written, read-modified, or touched.** The four chart questions in §4 were not built into a deck.
- The pre-existing `test_universe_single_source.py` failure was left alone.

*Housekeeping:* mid-investigation a `git stash -u` was run and immediately `git stash pop`'d; `git status` after the pop matched the prior untracked set line for line. Nothing lost, flagged because it touched the tree.