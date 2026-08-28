# X7 — every codebase that touches an entry, and whether it earns its keep

2026-08-28. Austin: *"there are so many codebases that factor into entries and we need
each one to have a significant purpose."*

**Headline: the shipped 2-year book of 1,017 trades is selected by ONE rule — the
first-with-trend-signal-of-the-day floor at `signal_runner.py:1516` — which sets the
grade on 969 of them (95.3%); turn it off and the book is 48 trades. Everything else
on the surface either fires on under 1% of signals or has no author.**

Provenance. Numbers below come from four places and each row says which:

| source | what it is | how to regenerate |
|---|---|---|
| `research/g3_arm_ow1.json` | the shipped 2-year book — 45,193 post-dedupe signals, 1,394 fired, 1,017 traded, 500 sessions, 28 symbols, mean R **+0.9551** | `python research/g3_onwatch_2y.py run --arm on` |
| `research/x7_launder_probe.py` (**new, this ticket**) | grade transitions through the SHIPPED router on 200 archived symbol-days: base grade → grade at `_emit` → grade after `_route`. 2,480 emitted signals | `python research/x7_launder_probe.py --days 200 --seed 11` |
| `research/_w1_book_stats.json` | the `ENABLE_KILL_B_FLOOR` arm | `python research/w1_sac_ladder_ab.py` |
| committed reports | `research/w12_bug_sweep.md`, `research/g4_dropped_s.md`, `research/g3_onwatch_2y.md`, `research/g13_floor_fix_ab.md`, `research/r3_downgrade_grader_ab.md`, `research/w3_recall_gate_fix.md`, `research/p7_84_rule.md`, `research/hallucination-audit.md` | — |

Line numbers are against **`c089b26b`**. Error bar on any mean-R A/B of this book is
**±0.0095 R** (narrow bar); the ±1.5799 R wide bar was retired 2026-08-28.

---

## 0. There is not one entry path. There are three, and they disagree.

This is the finding that reframes every other one. Three separate stacks take a
1-minute bar to a position, and no two of them share a router, an exit, or a sizer.

| | **LIVE** | **BACKTEST (every published number)** | **FORWARD / RECALL / DECKS** |
|---|---|---|---|
| driver | `live_scanner.py:268` `scan_once` | `backtest_2y.py:85` → `backtest_week.py:562` `simulate_day` | `research/t4_engine_recall.py:152` `run_day` |
| bars | Tastytrade DXLink, 60 s poll (`live_scanner.py:84`) | Polygon archive `data_archive/` via `polygon_feed` | same archive via `research/levels.py:52` `load_rth_bars` |
| router | `SignalRunner._route` (`signal_runner.py:1828`) | `BacktestRunner._route` (`backtest_week.py:449`) → `super()._route` | **`CaptureRunner._route` (`research/t4_engine_recall.py:135`) — a FORK that never calls `super()`** |
| second selector | `_tier()` (`live_scanner.py:491`): TRADE only if grade in {A+,A} **and** at/after 09:40 **and** first of the day **and** fewer than 2 consecutive losses. Everything else = WATCH, ding only | none | none |
| exit | `paper_trader.py:124` `exit_for` — blind 2R limit on a wick touch, stop on close. No 11:00 flat, no -1.25R floor, no scale-out | `SCALE_PLAN="hod_then_runner_be"` (`backtest_week.py:406` `_ladder_bar`) — 50% at the as-of-entry HOD/LOD, runner to the next key level, BE stop after the scale | `research/exit_lab.py:398` `policy_30_30_30_10` — 30% causal-HOD, ATR trail, **11:00 force flat, -1.25R floor** |
| sizing | `options_sizer.py:24` `GRADE_SIZE_PCT` — A+ 1.0 / A 0.8 / **B 0.6** / C 0.4 of $1,000; 84% re-entry **x2** | flat `RISK_DOLLARS = 1000.0` (`backtest_week.py:40`); 84% x2 removed 2026-07-10 as a martingale | R only, dollars applied afterwards |
| dedupe | `_cooled_down` 20 min per symbol+direction (`live_scanner.py:500`) | `DEDUPE_BARS = 30` bars per idea (`backtest_week.py:67`) | `DEDUPE_BARS = 30` (`t4_engine_recall.py:42`) |

**What that costs, measured.**

1. **The live governor would have taken 14 trades in two years, not 1,017.** Over
   `g3_arm_ow1.json`: 17 of 45,193 signals grade `A+`/`A` (0.04%); all 17 are at or
   after 09:40; keeping only the first per day leaves **14 across 500 sessions**, mean
   R +1.1101. That is an upper bound — `consecutive_losses < 2` and the 20-minute
   cooldown cut further and are not modelled. **1,000 of the 1,017 rows in the book are
   grade `B`, and `_tier` never trades a `B`.** Every headline OMEN figure describes a
   book the live path does not take.
2. **Recall and money are measured through different routers.** `regression_gate.py:34`,
   `research/t70_test1_score.py:42` (the held-out 3/15 and 12/42 numbers) and
   `research/build_deck.py:34` (the cards Austin grades) all drive
   `t4_engine_recall.run_day`, whose `_route` fork omits every gate the base router grew
   after 2026-08-12: `NO_REPEAT_ENTRIES` (ships **ON**), `LEVEL_RETIRE_TOUCHES`,
   `compute_austin_tier`, `mesh_blocked`, `S_GATE`, `RULE_710`, `ENFORCE_NO_REPEAT`.
   `backtest_week.BacktestRunner._route` was fixed for exactly this on 2026-08-12 and
   its docstring says so; the fork in `research/` was never fixed. Priced on the book:
   57 `skipped_repeat_entry` + 21 `[retired:` rows would fire instead — **78 of 45,193
   (0.17%)**, of which **1** is a traded-grade row. Small today, wrong by construction,
   and it grows with any flag that lifts the grade distribution.
3. **`paper_trader.py:33` keeps its own `RULE6_ENABLED = False`**, a second copy of
   `backtest_week.py:75`. Live exits are blind 2R. The book's exits are a HOD ladder.
   The forward book's exits are `30_30_30_10`. Three policies, one system.

---

## 1. The pipeline — bar to placed trade

Numbered in execution order. `n` columns are the 2-year book (post-dedupe) unless the
row says *probe*, which is `x7_launder_probe.py` over 200 symbol-days / 2,480 emits.

### A. Before detection

| # | stage | file:line | what it rejects | measured |
|---|---|---|---|---|
| 1 | universe | `universe.py:84` `BACKTEST_SYMBOLS` (24), `:72` `INCLUDE_SPY_IN_BACKTEST=False` | symbols | **LEAKS.** The book runs 28 symbols. 4 of them — ACHR, IWM, SPCX, **SPY** — are not in `BACKTEST_SYMBOLS`, carrying **26 of 1,017 traded rows (2.6%)** at +1.4722R. SPY contributes 4 trades that a recorded decision says must not exist. 9 of 27 symbols are under `MIN_SAMPLE_N = 20` (`universe.py:131`) |
| 2 | bar load | `research/levels.py:52` / `polygon_feed` / `backtest_week.py:486` `fetch_week` (yfinance) | days with no archive | three readers, see section 3 |
| 3 | prior-day / premarket levels | `t4_engine_recall.py:91`, `:79`; `backtest_week.py:486` premkt block | — | two implementations |
| 4 | HTF bias | `backtest_week.py:543` `htf_bias_for` (hourly SMA20) vs `t4_engine_recall.py:104` `htf_bias` (daily-close SMA20) vs `signal_runner.py:1277` `daily_trend_bias` | — | **three definitions of the same input**, and it drives the largest gate in the engine (#9) |
| 5 | session window | `signal_runner.py:1956` `in_session` (09:30-11:00) + `backtest_week.py:559` `ENTRY_CUTOFF` + `live_scanner.py:76` | bars outside the window | redundant by design (documented). `ENTRY_CUTOFF` is a third copy; `research/g10_arming_funnel.md` already found `before11` inside `_arm_84` to be dead for the same reason |

### B. Detection — `signal_runner.detect_signals` (`:1943`)

| # | stage | file:line | rejects | measured |
|---|---|---|---|---|
| 6 | level map | `:1979` `_active_levels` (PDH/PDL/PMH/PML/ORH/ORL) + `:2013` pivots (`pivot_levels`, `:935`) | — | pivots are **57.8%** of all signals (26,131 of 45,193) and **33.7%** of the traded book (343 of 1,017) |
| 7 | B&R geometry | `omen_bot.py:478` `detect_break_retest` — break/leave/retest/confirm, window 12, gap 3 | the bulk, upstream of the book | 40,800 of 45,193 signals are B&R. Internal funnel counters exist (`omen_bot.py:473` `BR_FUNNEL`) and **nothing reads them** |
| 8 | fill | `:2052` `fill_price` (`:884`) then `:2055` `intrabar_stop` (`:982`) then `:2066` `clamp_fill_to_min_risk` (`:1063`, flag OFF) | nothing — changes the PRICE | `ON_WATCH` A/B (`research/g3_onwatch_2y.md`, `47e60796`): OFF n=1,091 **+0.8416R** 24/25 months green; ON (shipped) n=1,017 **+0.9551R** 23/25. **The shipped arm buys +0.1135R by giving back a green month** |
| 9 | **HTF opposition veto** | `omen_bot.py:29` `HTF_BIAS_VETO` (ships ON), consumed `omen_bot.py:209` | **21,257 of 45,193 (47.0%) to `TradeGrade.D`**, all of them | the largest single gate. `research/p16_htf_bias.md`: with it off, 60 of the 3,525 dropped S signals reach a tradeable tier at +1.012R (n=60) |
| 10 | base grade | `:1714` `_grade_trade` to `omen_bot.py:182` `grade_trade` to `:218` `_grade_pa` | colour, at-level, wick shape | *probe:* **X 2,017 (81.3%) - C 387 (15.6%) - B 60 (2.4%) - A+ 16 (0.65%) - A 0**. The grader emits a tradeable tier on **3.06%** of signals |
| 11 | LATE cap | `:2072` | A+/A to B when the level was already broken | 25,752 of 45,193 signals carry `[late]` (57.0%) |
| 12 | A+ stack floor | `:2076` `_aplus_stack` (`:1436`) | promotes C/X to B | **2** `[A+:` promotions in 45,193 |
| 13 | D-to-C rescue | `:2079` | promotes X to C (alert) | *probe:* **134 of 2,480 (5.4%)** rows go X to C here |
| 14 | **minimum-risk floor** | `:2086` / `:2326` `floor_reference_risk` (`:1012`) vs `max(0.10, 0.0015 x close)` | to `TradeGrade.D` | *probe:* **it kills 68 of the 76 base-A+/A/B signals (89.5%)** and 336 base-C rows; **404 of 2,480 (16.3%) post-grade kills in total**. This is the single largest destroyer of tradeable grade in the engine, and `0.0015` is an **UNMENTIONED** constant |
| 15 | displacement gate | `:2093` / `:2331` `BNR_DISPLACEMENT_GATE` (ships ON) + `_bnr_displacement` (`:1418`) | A+/A/B to C when the break leg did not displace | 30,527 signals are `[nodisp]` (67.5%) — but the gate only fires on a base of A+/A/B, so its real reach is inside the 3.06%. See section 2b |
| 16 | PMH/PML alert-only cap | `:2099` / `:2335` | A+/A/B to C on premarket levels | 203 of 1,017 traded rows are PMH/PML anyway, at +1.0199R vs +0.9390R for everything else — the cap is not what keeps them out or lets them in |
| 17 | OCR min-stop / wide-stop / B-to-C | `:2189`, `:2194`, `:2196` (mirror `:2413`, `:2416`, `:2418`) | flat $0.50 floor; B to C; stop wider than 0.4% of price to D | 773 of 4,390 OCR signals exceed 0.4% (17.6%). OCR delivers **67 of 1,017 traded rows at +0.4414R**, the worst setup in the book |
| 18 | 84% re-entry | `:2236`-`:2285` (mirror `:2454`-`:2485`) | RR at least 1.5x, HOD proximity 20%, `RULE84_MAX_ATTEMPTS=2` | **3 fires in two years.** `research/p7_84_rule.md` (`40fdadd3`): the arming GATE, not the detector, is the bottleneck — 7 of 472 opportunities survive it |
| 19 | HTF_BIAS_GATE | `:2488` | nothing (flag OFF) | **0** `[htf-block]` rows. Also runs AFTER `_emit`, so it could only relabel, never prevent |
| 20 | confluence + pivot rank tags | `:2500`, `:2513` | nothing — labels | `[confluence:` **31** rows (0.07%); `[outranked:` **2** |

### C. Emit — `signal_runner._emit` (`:1800`)

| # | stage | file:line | rejects | measured |
|---|---|---|---|---|
| 21 | `_label_confluence` | `:1766` to `research/downgrade.py::has_confluence` | nothing — label | `[brocr]` on 29,830 of 45,193 (66.0%) |
| 22 | retired setups | `:1804` `RETIRED_SETUPS` = {FVG, FLAG} | FVG/FLAG signals | **0** — both detectors are already off at `:64` and `:68` (double-dead, section 2c) |
| 23 | session-extreme veto | `:1806` to `session_extreme_veto` (`:1675`) | `SESSION_EXTREME_FRAC = 0.0` | **0 rows.** Dead by configuration; the A/B (`research/t3_session_extreme.md`) chose 0.00 |

### D. Route — `signal_runner._route` (`:1828`)

| # | stage | file:line | rejects | measured |
|---|---|---|---|---|
| 24 | `_grade_for_levels` | `:1446`, level-block cap + clear-road A/A+ | caps A+/A/B to C when a level blocks the 2R path | `[capped C: level` **37** of 45,193 (0.08%), **0 of them traded**. `[A->B` 10, `[B->A` 11, `[A+:` 2 — the whole `CLEAR_FOR_APLUS` machine moves **23 signals in two years** |
| 25 | counter-day-trend cap | `:1513` | A+/A/B to C against the day trend | **9** rows (0.02%), 0 traded |
| 26 | **first-with-trend floor** | `:1516` | **promotes C to B, i.e. into the book** | **969 of the 1,017 traded rows (95.3%) exist because of this line.** Arm measured (`research/_w1_book_stats.json`, `ENABLE_KILL_B_FLOOR=1`): the book goes **1,017 to 48 trades**, mean R **+0.9551 to +1.3161**, months green **23/25 to 12/18** |
| 27 | S_GATE | `:1832` to `predicates.py:336` | flag OFF | **0** |
| 28 | RULE_710 | `:1839` to `rule_710_reject` (`:1260`) | flag OFF | **0** |
| 29 | mesh + austin_tier | `:1856`-`:1869` `blocking_levels` / `compute_austin_tier` (`:1157`) | **nothing — reported only** | `TRADE_S_ONLY` (`:358`) is read nowhere. The whole tier computation is a reporting field |
| 30 | level retirement | `:1878` `LEVEL_RETIRE_TOUCHES=2` | signals on a level already broken twice | **21** in the book, **all 21 already grade X**, so marginal rejection **0**. *probe:* 3 of 2,480 (0.12%). Also mislabelled: `backtest_week.py:462` tests `grade == D` before `level_retired`, so all 21 are filed as `skipped_d` |
| 31 | X-grade skip | `:1891` `_SKIP_GRADES` | **42,937 of 45,193 (95.0%)** | the mass rejection, and it is the sum of #9, #10 and #14 |
| 32 | `ENFORCE_NO_REPEAT` | `:1900` | flag OFF | **0** `[skip: repeat idea]` |
| 33 | **tight-stop gate** | `:1908` `_min_viable_stop` (`:1401`) | **805 of 45,193, and every one is grade `C`** | `research/w12_bug_sweep.md` #1: re-derived over the 1,017 traded rows, **732 (72.0%) would fail it**, and it **rejects the better half** — rejected mean **+1.0861R** vs kept **+0.6188R**, a 0.4673R gap = **49x the error bar**. Both its constants (`STOP_RANGE_MULT = 0.75`, the 0.5% / $0.20 pair) are UNMENTIONED |
| 34 | `NO_REPEAT_ENTRIES` | `:1921` (ships ON) | **57 of 45,193 (0.13%)** — 56 C, 1 A | absent from the recall/deck router entirely (section 0, point 2) |

### E. Simulate — `backtest_week.simulate_day` (`:562`)

| # | stage | file:line | rejects | measured |
|---|---|---|---|---|
| 35 | idea dedupe | `:634` `DEDUPE_BARS = 30` | same setup re-firing | **not measured** — the book is stored post-dedupe, so the pre-dedupe count is not recoverable from it. The live path uses a different rule (20 min, `live_scanner.py:500`) |
| 36 | `counted` | `:221` `status == "fired" and grade != "C"` | **377 alert-`C` rows** | `w12_bug_sweep.md` #3: no `C` has ever entered the book; the alert-`C` rows book **+0.4487R** |
| 37 | exit ladder | `:406` `_ladder_bar`, `SCALE_PLAN` | — | `research/g7_exit_sweep.md`: nothing in the family beats it; `research/p10_structure_trail.md`: nothing on the trail beats it either. **The exit is not the constraint** |
| 38 | sizing | `:230` `pnl`, flat $1,000 | — | diverges from live (section 0) |

---

## 2. What has an author, what is laundered, and what is dead

### 2a. Provenance — the UNMENTIONED constants still on the decision surface

`research/hallucination-audit.md` (`86d96f99`) swept 50 constants: 15 CONFIRMED, 2
CONTRADICTED, 33 UNMENTIONED. **Two of its importance calls are wrong today** and one
of its rows is stale — corrected here against the code and the book:

| constant | site | audit said | **what the book says** |
|---|---|---|---|
| **Calibration 90-min first-signal floor** | `:1516` | "LOW — calibration-era only" | **It selects 95.3% of the book.** It is the single most load-bearing line on the surface. The audit understates it by the whole book |
| **B&R_MIN_RISK `0.0015 x close`** | `:2086` / `:2326` | "HIGH — gates grade D" | correct, and bigger than stated: **89.5% of everything the grader rates tradeable dies here** (probe) |
| **STOP_RANGE_MULT `0.75`** | `:1401` | "HIGH — human-proof gate" | correct, and **wrong-signed**: it keeps the worse half (`w12_bug_sweep.md` #1) |
| **STRONG_PA_MULT `1.5`** | `:91`, used `:1444` | "CRITICAL — gates the 84% reclaim" | **it does not.** `RULE84_LESSON=True` (`:104`) short-circuits `_strong_pa` at `:2240` / `:2458`. Its only live consumer is `_aplus_stack`, which fires **2 times in 45,193** |
| **S-score weights** (clean+2, A+2, stop+2, non-PM+1, hammer+2, QQQ+1) | `:2103`-`:2110` | "HIGH — drives tier selection" | **it drives nothing.** The score is printed into `reason` and read only by `backtest_week.sscore_mult` (`:53`), gated on `OMEN_SSCORE_SIZING`, which is OFF. A label, not a gate |
| detect_break_retest window 12 / gap 3 | `omen_bot.py:478` | MEDIUM | LIVE and unmeasured — the shape of all 40,800 B&R signals |
| OCR/FVG/Flag `$0.50` min risk | `:2189` etc. | LOW | LIVE for OCR only; `g4_dropped_s.md` attributes 153 dropped S to it |
| 84% RR `1.5x` remaining, HOD 20% | `:2247`, `:2253` | MEDIUM / LOW | LIVE on a feature that fires 3 times in two years. `g10_arming_funnel.md`: `rr15` alone kills 92 of 318 armings |
| Traded-level dedupe `0.1 x risk` | `:1128` | LOW | LIVE, reaches 37 signals |
| CHASE_PCT, OB_VOLUME_MULT, F3 constants, consolidation skip, `_closes_strong` shape | — | LOW | **all dead** — see section 2c |

The audit's own arithmetic does not close: the summary says 33 UNMENTIONED, the table
lists **16 rows** (several bundle multiple constants). `signal_runner.py` alone carries
**66 module constants, 29 env-switchable**. A full re-count is a follow-up, not a
finding.

### 2b. The string-guard hole — real, sized, and currently near-inert

`_calibration_grade`'s floor is guarded by a **string test**:

```python
sig["grade"] == "C" and "capped C" not in sig["reason"]     # :1518
```

Four demotion sites write `capped C` (`_grade_for_levels` `:1466`, counter-trend
`:1515`, `S_GATE` `:1837`, `RULE_710` `:1848`). **Three do not**: the displacement gate
(`:2093`, `:2331`), the PMH/PML cap (`:2099`, `:2335`) and the order-block `B` to `C`
(`:2194`, `:2416`). A signal those three demote is indistinguishable from one the
grader scored `C` on its own, and the floor lifts it straight back to `B` — tradeable.

**Measured, not assumed** (`research/x7_launder_probe.py`, 240 symbol-days across two
seeds, 2,987 emitted signals): **9 untagged demotions (0.30%)**, of which **1** was
lifted back to `B` and fired. My own prior hypothesis — that the 785 `[nodisp]` rows in
the traded book were laundered — is **refuted**: those rows were graded `C` by
`_grade_pa` in the first place, so the gate never fired on them.

**But it is a loaded gun.** The hole is bounded by how often the base grader emits
A+/A/B, which is 3.06% today. `ENABLE_SAC_LADDER` moves 564 rows into A+/A/C, and R3's
`ENABLE_DOWNGRADE_GRADER` 1,310. Flip either and three named rules with their own A/B
histories start being silently undone. The fix is one line each: append
`" [capped C: ...]"` at the three sites.

### 2c. Dead — branches that cannot be true, and code nothing calls

The recurring bug class. Every row was **counted**, not read.

| what | site | why dead | lines |
|---|---|---|---|
| `WIDE(...)` retest tag | `omen_bot.py:583-587` | `DETECT_WIDE=False` means `rtol=0`, so the retest bar always `touched` and the branch is unreachable **by construction**. **0** `[wide]` in 45,193 | 8 |
| `_targets_session_extreme` to `C` | `:1098`, consumed `:1163` | `stop_level_name` in {"HOD","LOD"} is set **only** by the `HODLOD_PAIR` block, and `HODLOD_PAIR=False` (`:135`). 0 HOD/LOD rows in the book. Unreachable by construction | 7 + 15 |
| `BNR_STOP_MODE` retest/buffer arms | `:2043-2051`, `:2299-2307`; `out["retest_low/high"]` in `omen_bot.py:591` | `BNR_STOP_MODE = "level"` | 18 + 3 |
| `_closes_strong` | `:1628-1639` | **defined and never called anywhere in the repo** | 12 |
| `_volume_ok` | `:83`, called `:2182`, `:2215`, `:2407`, `:2434` | `OB_VOLUME_MULT = 0.0` means always `True` | 9 |
| FVG entry blocks x2 | `:2153-2182`, `:2378-2405` | `FVG_RETEST=False`, **and** FVG is in `RETIRED_SETUPS`. Dead twice | 58 |
| Flag entry blocks x2 | `:2210-2232`, `:2432-2454` | `FLAG_ENABLED=False`, **and** FLAG is in `RETIRED_SETUPS`. Dead twice | 46 |
| `HODLOD_PAIR` level block | `:1993-2007` | flag False | 15 |
| `S_GATE` + `predicates.is_s_gate` | `:1832-1837`; `predicates.py` (375 lines) | flag False | 6 + module |
| `RULE_710` + rule7/rule10 helpers | `:1839-1850`, `:1206-1277` | flag False | 84 |
| `ENFORCE_NO_REPEAT` | `:1894-1906` | flag False; superseded by `NO_REPEAT_ENTRIES` | 13 |
| `HTF_BIAS_GATE` + `daily_trend_bias` | `:2488-2497`, `:1278-1295` | flag False; **and** placed after `_emit`, so it could never prevent a trade | 28 |
| `session_extreme_veto` | `:1676-1699` | `SESSION_EXTREME_FRAC=0.0`; the A/B chose 0.00 | 24 |
| `rank_s_plus` | `:1132-1157` | reporting rank on a tier nothing routes on | 26 |
| `TRADE_S_ONLY` | `:358` | read nowhere, by design | 1 |
| `BreakAndRetestDetector` / `OneCandleRuleDetector` / `RuleOf84Detector` | `omen_bot.py:597-724` | `signal_runner.py:36` imports two of them and **calls neither**; only `backtester.py` (a superseded rig) and `align_reviews_v2.py` use them | 128 |
| `compute_plan` / `SizingPlan` | imported `signal_runner.py:41`, used nowhere in the file | dead import | 2 |
| `BR_FUNNEL` | `omen_bot.py:473` | counters written on every call, **read by nothing** | 4 |
| `research/build_levels.py` | whole file | **zero importers, zero callers** | 110 |
| `research/trend_gate.py` | whole file | in `omen6_forward.FROZEN_FILES` but **not reachable from any entry path or from the forward scorer** | 219 |

**Never-executed lines on the entry surface: about 318 in `signal_runner.py`, 128 in
`omen_bot.py`, and 110 + 219 in two whole `research/` modules — before counting the
comment blocks that document them.** `signal_runner.py` is 2,668 lines of which the
first 812 (30%) are constants and their commentary.

Two more corrections to the record, both live:

- `omen_bot.py:209` — the `HTF_BIAS_VETO` docstring was fixed by W12 (`f959cff5`) but
  the rule still has **no author** (R6, still open) and it is the biggest gate in the
  engine.
- `backtest_week.py:462` — the `elif` ladder tests `grade == D` before `level_retired`,
  so all 21 level-retirement rejections are reported as `skipped_d`. A reporting bug,
  not a routing bug.

---

## 3. Duplicates — where two modules compute the same thing

`universe.py` is enforced single-source by `research/test_universe_single_source.py`.
**Nothing else is**, and nine computations are forked:

| computation | implementations | verdict |
|---|---|---|
| **routing** | `SignalRunner._route` (`:1828`) - `BacktestRunner._route` (`backtest_week.py:449`, delegates, correct) - **`CaptureRunner._route` (`t4_engine_recall.py:135`, forked)** | the fork drives recall, the deck and the forward book. **MERGE — delegate like `BacktestRunner` does** |
| **exit** | `backtest_week._ladder_bar` (`:406`) - `research/exit_lab.POLICIES` (`:406`) - `paper_trader.exit_for` (`:124`) | three policies. `stop_rule.py` already proves the shared-predicate pattern works. **MERGE onto one policy object** |
| **swing pivots** | `signal_runner.pivot_levels` (`:935`, strength 2) - `research/levels.swing_pivots` (`:218`, 3-bar) - `omen_bot.MarketStructure.update` (`:270`) - `signal_runner.rule10_left_pivots` (`:1235`) - `research/rule7_rule10.count_left_pivots` (`:87`) - `research/p10_structure_trail.py:64` (copied, documented) | **six** definitions of "swing pivot", two of them different by design and four by drift |
| **level map** | `signal_runner._active_levels` + pivots (6 named types) - `research/levels.levels_at_bar` (`:231`: psych, HOD/LOD, swings, prior-day, floor pivots — **9 families**) - `research/build_levels.levels_for` (dead) - four deck-builder `levels_for` copies (`build_probes.py:57`, `build_h2_deck.py:97`, `build_omen_test1.py:194`, `t12_recover.py:64`) | **the levels that gate an entry and the levels a research rig scores it against are disjoint sets** |
| **displacement** | `signal_runner._bnr_displacement` (`:1418`) - `omen_bot._has_displacement` (`:341`) - `research/downgrade.no_displacement` (`:147`) - `predicates.is_s_gate` (`:336`) | four, all claiming `DISPLACEMENT_MULT = 1.5` |
| **HTF bias** | `backtest_week.htf_bias_for` (hourly SMA20) - `t4_engine_recall.htf_bias` (daily SMA20) - `signal_runner.daily_trend_bias` (daily SMA20) - `tastytrade_feed.fetch_htf_bias` - `futures_feed.fetch_htf_bias` | **five**, feeding the 47.0% gate |
| **min-risk floor** | `signal_runner.min_risk_floor` (`:1053`) and the literal `max(0.10, 0.0015 * current.close)` inline at `:2086` and `:2326` | the helper was added by W3 and the two call sites were **not** switched to it |
| **ATR** | `research/exit_lab.atr` (`:80`) - `research/downgrade._atr` (`:127`) - `research/levels.atr_1m` (`:71`) - `research/p2_threshold_sweep._atr` (`:160`) | four |
| **grade** | `omen_bot._grade_pa` - `research/downgrade.score` - `compute_austin_tier` - `_sac_ladder_grade` | four ladders, one of which (`compute_austin_tier`) routes nothing |

---

## 4. Verdict per module, ranked by lines removed

Deleting is the goal. Cost is stated for every row.

| rank | module / block | verdict | lines out | what the delete costs |
|---:|---|---|---:|---|
| 1 | `predicates.py` + `S_GATE` block | **DELETE** | ~381 | `research/mark_features.py` and `test_s_gate.py` import it; the S-gate A/B (`research/s_gate_spec.md`) is already published. Nothing in the book changes — 0 fires |
| 2 | `research/trend_gate.py` | **DELETE from FROZEN_FILES, KEEP the file** | 219 off the surface | it is not on any entry path; two research rigs import it. Keeping it in the manifest makes the freeze look stricter than it is |
| 3 | `omen_bot` detector classes x3 | **DELETE** | 128 | `backtester.py` (324 lines, superseded by `backtest_week`) and `align_reviews_v2.py` break. Delete those too and it is about 450 |
| 4 | `research/build_levels.py` | **DELETE** | 110 | nothing imports it. Zero |
| 5 | rule7 / rule10 + `RULE_710` | **DELETE** | 84 | `research/rule7_rule10.md` already published the negative result and `RULE7_MAX_BARS` records the fitted value. 0 fires |
| 6 | FVG entry blocks x2 | **DELETE** | 58 | Austin retired FVG 2026-08-24. Historical comparability is already preserved by `RETIRED_SETUPS`. 0 fires |
| 7 | Flag entry blocks x2 | **DELETE** | 46 | same. 0 fires |
| 8 | `HTF_BIAS_GATE` + `daily_trend_bias` | **DELETE** | 28 | superseded by `HTF_BIAS_VETO`, which is the same idea and actually fires. 0 fires |
| 9 | `rank_s_plus` | **DELETE** | 26 | S+ is a rank on a tier nothing routes on. Reporting only |
| 10 | `session_extreme_veto` + `SESSION_EXTREME_FRAC` | **DELETE** | 24 | the A/B chose 0.00 and is committed. 0 fires |
| 11 | `HODLOD_PAIR` block + `_targets_session_extreme` | **DELETE** | 22 | removing it also removes an unreachable branch in `compute_austin_tier` |
| 12 | `BNR_STOP_MODE` retest/buffer arms | **DELETE** | 21 | F2's A/B is committed (`research/f2f1_runs/session-notes.md`); both arms lost |
| 13 | `ENFORCE_NO_REPEAT` block | **DELETE** | 13 | superseded by `NO_REPEAT_ENTRIES`. Two rules for one sentence |
| 14 | `_closes_strong`, `_volume_ok`, the `compute_plan` import, `BR_FUNNEL` | **DELETE** | 27 | nothing calls them |
| 15 | `research/t4_engine_recall.CaptureRunner._route` | **MERGE — delegate to `super()`** | -14, +2 | **changes what the deck, the recall gate and the forward book see.** Priced: 78 of 45,193 signals (0.17%), 1 traded-grade row. Needs a baseline re-lock (`regression_gate.py --write-baseline`) |
| 16 | three exit engines | **MERGE onto one** | ~150 net | the three books stop being comparable to their own history until each is re-run. This is the expensive one |
| 17 | the three untagged cap sites | **FIX (3 lines)** | 0 | none. Do it before any grade-ladder flag ships |
| 18 | `_min_viable_stop` tight-stop gate | **BATTLE-TEST FIRST** | — | wrong-signed on 805 rejects at 49x the error bar (`w12_bug_sweep.md` #1). Removing it is a book change and Austin's call |
| 19 | `_calibration_grade` first-with-trend floor | **BATTLE-TEST FIRST — this is the whole selector** | — | removing it takes the book to 48 trades. G14 owns it |
| 20 | `compute_austin_tier` + `MESH_S_VETO` + `LEVEL_RETIRE_TOUCHES` | **KEEP, unrouted** | — | 0 marginal rejections today, but they are Austin's own sentences and the ladder work needs them |
| 21 | `universe.py` | **KEEP, and FIX the leak** | — | make `backtest_2y.py` read `BACKTEST_SYMBOLS`; 26 traded rows (2.6%) leave the book, including 4 SPY rows a recorded decision excludes |

**Total straight deletes (rows 1-14): about 787 lines, 0 measured change to the book.**

---

## 5. The frozen manifest — and why its price is currently zero

`research/omen6_forward.py:48` freezes seven files. Anything on that list changes the
forward book's meaning, so the ticket asks which surface items carry that extra price.
The answer today is **none of them, because the freeze has already lapsed.**

Measured (`research/omen6_frozen.json`, frozen `2026-08-23` at `40949c6a`, re-hashed
this session with the module's own normalised `sha256`):

| file | hash |
|---|---|
| `signal_runner.py` | **MOVED** |
| `omen_bot.py` | **MOVED** |
| `universe.py` | **MOVED** |
| `research/exit_lab.py` | **MOVED** |
| `research/levels.py` | same |
| `research/t4_engine_recall.py` | same |
| `research/trend_gate.py` | same |

**4 of 7 have moved, across 18 commits since the freeze**, and
`research/omen6_forward_book.jsonl` has **0 rows**. `check_frozen` would exit 2 on the
next `score`. So:

- **Nothing on the decision surface currently carries a forward-book cost**, because
  there is no forward book to void. Every "this VOIDS the forward book" warning in
  `signal_runner.py` (`ENABLE_STRUCTURAL_RISK_FLOOR`, `ENABLE_MIN_RISK_FILL_CLAMP`,
  `ENABLE_DOWNGRADE_GRADER`, `ENABLE_SAC_LADDER`) is, as of today, describing a cost
  that has already been paid and bought nothing.
- `research/trend_gate.py` is on the frozen list and on no entry path.
- The manifest does **not** cover `backtest_week.py`, `paper_trader.py`,
  `live_scanner.py`, `options_sizer.py` or `research/downgrade.py` — four of which
  change what trades and one of which changes the exit.

**Austin must be told this before the next freeze, not after**: re-freeze after the
delete pass, extend `FROZEN_FILES` to the modules that actually gate entries, drop
`trend_gate.py`, and start the clock — the honest holdout has not started yet.

---

## What this map does not measure

- **`DEDUPE_BARS = 30`** — the book is stored post-dedupe, so its rejection load is not
  recoverable from `g3_arm_ow1.json`. Needs its own instrumented run.
- **`detect_break_retest`'s internal funnel** — `BR_FUNNEL` counts it and nothing reads
  it. One `--dump-funnel` flag away from being an answer.
- **The live path end to end.** `_tier`'s `consecutive_losses` and `_cooled_down` cannot
  be replayed from the book, so **14 trades in two years is an upper bound**, not the
  live count.
- **`x7_launder_probe.py` is 240 symbol-days, not 500 sessions.** The laundering rate
  (0.30%, 9 of 2,987) is a sample; the mechanism is a code fact.
