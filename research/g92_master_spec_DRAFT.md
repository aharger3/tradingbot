# OMEN Master Spec — Analytical Core
**Source:** 162 marks decoded across 9 axes, each grounded against the tree at `C:/Users/aharg/Desktop/Projects/tradingbot`, each adversarially verified (0 REFUTED, 0 QUOTE_INACCURATE, 0 OVERSOLD returned).
**Book:** honest fill = `ENTRY_FILL=close` (`entry_fill.py:82`), stops via `stop_rule.stop_fill_price()`, `signal_runner.min_risk_floor` on. Every dollar below names that fill or says otherwise.
**Baseline being moved:** first-setup-of-day **$28/day, 45.5% win, 11/25 green months**; precision **39.5%** (of 100 days it trades, 60.5 he refused); ~**18.6** candidates surfaced/day against a target of **1–3**; oracle ceiling on the same book **$2,948/day, 25/25 green**; his bar **$397/day, every month green**.

---

## 1. THE SHORTLIST

Ranked by (evidence strength × expected precision lift) / build cost. Eight entries. Everything dropped is named at the bottom with the reason.

### 1. Wire the ratified S/A/C grader as the fire gate — and make the two live implementations agree first
| | |
|---|---|
| **What changes** | `signal_runner.py:2446` currently short-circuits (`if not ENABLE_DOWNGRADE_GRADER:`) — the eight-variable ladder in `research/downgrade.py::score()` (`score = tripped − confluence`, floored at C) never touches what fires. Separately `signal_runner.py::compute_austin_tier` (line 1742) implements a *different* S/A/C: T11(a) at lines 1759–1767 hard-caps a no-displacement B&R to **C**, skipping A entirely, which contradicts the ratified ladder (`omen-rulebook.md:266–296`, ballot q18, 2026-08-23: one trip = A). Ship: delete the second implementation, route `compute_austin_tier` through `downgrade.score()`, then gate firing on the result. |
| **Axis / cards** | `a_vs_s_boundary` (5/13 A-cards cite no_displacement; `HOOD_2025-11-07` cites exhausted, correctly excluded), `displacement` (`ACHR_2025-06-27` is the clean single-trip→A case), `confluence_and_s` (BR+OCR label alone rejected on 4/5 cards — matches `has_confluence()` as a +1, never a gate). |
| **code_status** | implemented-but-unwired (grader) + **two implementations disagree** (bug). |
| **Build** | medium. No new detection logic; a delete, a route, a flag default. |
| **Measurable effect** | This is the only change on the list that directly changes *which days fire*. Target: precision 39.5% → **≥50%** with S-day recall down no more than 5pp, fires/day 18.6 → single digits. |
| **Why it beat what I dropped** | It is the lane, literally: a classifier that fires 1–3× a day. Every other candidate moves dollars *after* selection, and memory already prices exits at **+0.06R** against day-selection's **+2.21R**. |

### 2. Swap the displacement test from body-size to separation
| | |
|---|---|
| **What changes** | `signal_runner.py:2009–2025 _bnr_displacement` and `omen_bot.py:388–400 _has_displacement` both test **body ≥ 1.5× avg body of prior 10 bars**. Austin's words describe *separation*: "from the original candles", "not of the level just the wicks". `research/g81_displacement.py` already ran this and `research/g81_displacement.md` already proposes `separation_atr()` — under a heading that reads "Proposed changes. Nothing is applied." |
| **Axis / cards** | `displacement` (his definition, 2 direct quotes), `a_vs_s_boundary` (5/13 A-cards), `mentor_ballot` (Neto: "ACTUAL SEPARATION FROM THE CANDLES TO THE KEY LEVEL"). |
| **code_status** | contradicted (shipped check measures the wrong thing); replacement written, unwired. |
| **Build** | small — the script exists, the swap is a function substitution in two files plus `downgrade.no_displacement`. |
| **Measurable effect** | Already measured, not forecast: the shipped body-check **costs 13.4pp of recall on his own S days** and buys **+0.0136R** — inside the ±1.5799R error bar, i.e. it buys nothing. Expect recall on S days +13.4pp at unchanged mean R. |
| **Why it beat what I dropped** | The only shortlist item whose effect size is already on disk instead of projected, and it currently *rejects his S days* — the exact failure the lane exists to fix. |

### 3. Cut `max_confirm_gap` from 3 to 1 and re-measure lateness
| | |
|---|---|
| **What changes** | `omen_bot.py:626–628, 705–707` lets the CONFIRM bar arrive up to 3 bars after the retest touch; the call sites (`signal_runner.py:2810, 3112`) pass no override, so the default 3 stands. Combined with close-only fill (`entry_fill.py:236`), the engine books the *close of the third bar after* the touch in the worst case. |
| **Axis / cards** | `entry_timing` — engine later than him in **7/7** literal-timestamp cards (median −10 min, mean −15.1 min); **10/12** comparable cards once candle-offsets are added (median −6.5 min). Zero cards show the engine early. His words: *"b candle right but entry is 3 candles earlier."* |
| **code_status** | implemented (a tunable, never tuned). |
| **Build** | small — one kwarg at two call sites, plus an A/B arm. |
| **Measurable effect** | Median engine-minus-Austin gap on the 12 timestamped cards: −6.5 min → target ≥ −3 min. Secondary read: $/day on the honest close-fill book must not fall below $28. |
| **Why it beat what I dropped** | It is the only *shippable* attack on entry lateness. The intrabar arm his marks actually ask for ("9:44 S entry as candle forming") requires reintroducing the look-ahead `entry_fill.py::_assert_causal` exists to forbid — see the drop list. |

### 4. Guard the runner target: it must sit beyond 2R, or be logged as a cap
| | |
|---|---|
| **What changes** | `backtest_week.py:1032–1043` computes `runner_tgt` purely as *nearest PDH/PMH or next whole dollar beyond the scale point* and **never compares it to `target`** (the 2R price computed 12 lines earlier at 1020–1021). Verified live in the tree today. `pnl()` (lines 396–402) never checks the distance either. Since `scale_level` is the session extreme as-of the entry bar, it can sit a few cents from entry, and the runner lands *inside* the 2R distance. |
| **Axis / cards** | `exit_ladder` — `QQQ_2024-08-26` and `QQQ_2025-02-25`; realized runner ≈ **0.41R** against a stated mean RR of 2.5 (`options_sizer.py:37 DEFAULT_RR = 2.5`, wired to nothing). |
| **code_status** | implemented and unguarded (confirmed bug). |
| **Build** | small (the assert/clamp). The *policy* — always push past 2R, or accept a nearer real level — is his call, not an engineering one. |
| **Measurable effect** | Mean realized runner R on the honest book: 0.41R → ≥2.0R, or a count of how many trades were capped and by how much. $/day on first-setup-of-day should rise; it cannot fall, since the guard only ever moves the runner further out. |
| **Why it beat what I dropped** | It's a live arithmetic bug in the rig that produces every published dollar figure, not a feature request. Ranked below 1–3 only because it is an exit lever, and exits are worth +0.06R. |

### 5. Give `path_target` a consumer — the level-first target policy that was stamped and never built
| | |
|---|---|
| **What changes** | `signal_runner.py:2052–2060` computes `blocking_levels(sig, levels)` and stamps `sig["path_levels"]` / `sig["path_target"]` with the comment *"what a level-first target policy takes as scale point 2 or 3, for the target policy (T5) to consume."* Grep of the working tree: written at 2059–2060, read **nowhere** (matches outside `signal_runner.py` are all `.claude/worktrees/` copies). T5 was never built. |
| **Axis / cards** | `exit_ladder` (raw 2R overridden by an HTF/whole-dollar level when one sits close — mechanism half-exists), `meta_process` (same complaint, mapped to the same field). |
| **code_status** | partial — the data exists, the consumer does not. Sibling of the CLAUDE.md unreachable-branch bug class: not a dead branch, a dead *field*. |
| **Build** | medium. |
| **Measurable effect** | $/day on the honest book, first-setup-of-day, against the $28 baseline; and green-month count against 11/25. |
| **Why it beat what I dropped** | Half the work is already committed and running on every signal. The 4-leg ladder (dropped) needs the same consumer built from zero *plus* a `SimTrade` rewrite. |

### 6. Flag-flip A/B on `STOP_PLACEMENT` (`entry_bar` → `routed`)
| | |
|---|---|
| **What changes** | Nothing structural — `signal_runner.py:1536–1568 placed_stop()` already implements `entry_bar` / `candle_entered` / `ocr_wick` / `broken_level` / `routed`, wired end-to-end through the min-risk floor and the R denominator. Default is `entry_bar` (line 1141, verified). `routed` sends B&R to the broken level and OCR to the OCR wick — which is what he describes when he gives a stop rationale. |
| **Axis / cards** | `stop_placement` claim 2 — every card where he states a stop rationale pins it to a structural anchor, never a fixed-distance offset. Note his *"i dont like bodies"* is **not** in tension with the code: every mode uses `candle.low`/`candle.high`, never open/close. |
| **code_status** | implemented, not default. |
| **Build** | trivial (env flag + one A/B run). |
| **Measurable effect** | The stop *is* the R denominator, so this moves every R and every dollar. Read mean R and $/day on the honest book; gate on green months (11/25 must not fall). |
| **Why it beat what I dropped** | Cheapest real experiment on the list — zero lines of new logic. |

### 7. Promote `g82.stop_candidates()` from probe-only to a measured downgrade variable
| | |
|---|---|
| **What changes** | `research/g82_master_homework.py:706–725` already computes up to **4** structural stop families per entry (candle extreme, level, `signal_runner.pivot_levels`, disaster-%) and filters to cards where all four disagree by more than one tolerance unit. It runs only in offline probe generation. Promote it to a 9th `downgrade.py` variable (default OFF) and *measure* — do not gate on it. |
| **Axis / cards** | `stop_placement` claim 3 (`META_2024-09-30`, **3 supporting / 76 relevant** — hint strength, and the claim says so itself), `veto_vocabulary` (ambiguous stop named as a minor but real refusal driver). |
| **code_status** | absent in the engine; computable today offline. |
| **Build** | small. |
| **Measurable effect** | Report only, first pass: does `ambiguous_stop=True` correlate with his `none` grades? If the sign is negative or flat, kill it — that is exactly what happened to `level_not_respected`. |
| **Why it beat what I dropped** | 3/76 is thin, but the computation exists and the measurement is nearly free. It ranks last of the survivors precisely because the evidence is thin. |

### 8. A/B `CORE_SYMBOLS` (10) against `live_scanner.DEFAULT_SYMBOLS` (29) on the honest book — offline only
| | |
|---|---|
| **What changes** | `universe.py:74–75` has a 10-name `CORE_SYMBOLS`; `live_scanner.py:65–67 DEFAULT_SYMBOLS` = 15+3+11 = **29**. The gap is real and current. Run the honest book both ways. **Do not flip the live default** — mentor ballot `rule_11` came back **skip**, which is not a yes. |
| **Axis / cards** | `mentor_ballot` rule_11 (`research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl`). |
| **code_status** | partial (infra exists, not wired). |
| **Build** | small. |
| **Measurable effect** | Mechanically cuts candidates/day toward the 1–3 target. Only counts as a win if precision rises *and* S-day recall holds — if his S days are spread across the 29, this is just amputation. |
| **Why it beat what I dropped** | It is the cheapest available cut to the 18.6-candidates/day number, and it is falsifiable in one run. It ranks last of the eight because he declined to endorse it. |

### Dropped, and why
| Dropped | Reason |
|---|---|
| **Chop as a veto** (15/22 refusals, 68% — the single most-checked reason) | The nearest wired analogue, `downgrade.level_not_respected`, is **wrong-signed** on the 2-year book: fires on 62.7% of trades, tripped trades average **+1.0046R (n=640)** vs clean **+0.8711R (n=377)** (`research/w9_downgrade_signs.md`, cited at `signal_runner.py:717–724`). `predicates.is_chop_market` is called by **zero** engine modules. Shipping a chop gate would re-create machinery he asked to be deleted (`TradeGrade.D`, removed 2026-08-24). Highest card count on the whole corpus, dropped anyway — this is the ruthless call. |
| **Intrabar / "as candle forming" entry** | His clearest entry-timing ask, and unbuildable honestly: `entry_fill._assert_causal` raises `LookAheadError` on any bar at-or-before the signal bar, and g88 found **89.6%** of the closest attempt's fills landed *before* the signal bar existed. The honest version is $275/day vs the shipped entry's $33 — real direction, 27% win, 15/25 green, not shippable. Goes to §3 as a question, not to the build. |
| **4-leg PT ladder (PT1 day-extreme → PT4 HTF/median)** | 1 card, and `backtest_week.SimTrade` is a 2-leg model. Large rewrite of `_ladder_bar` (642–736). Item 5 buys the same direction for a fraction of the cost. |
| **Trend-conditional scale split (30/30/30/10 vs 50/20/10/10)** | Zero code: `pnl()` hardcodes `0.5 * scale_r + 0.5 * run_r` (397–402). Needs an N-way split model *and* a trending classifier. Large, 1 card. |
| **`SCARFACE_CONTRACT` ratification (mentor rule_12)** | Already dead. `research/d1_scarface_ab.py` ran and concluded it is *"a no-op on the 12mo backtest P&L by construction"* — the realized-P&L path never imports `options_sizer`, and the sizer normalizes max_loss to a flat $1,000, so A == B bit-identical. The ballot instruction "run d1 then flip" is stale. |
| **Weekly/4H HTF trend + liquidity zones (rule_07)** | 1h bars are fetched for bias only (`backtest_week.py:813`); **no 4h data is fetched anywhere in the repo**. New data plumbing before any measurement. |
| **Surface {S, A} instead of S-only** | 7/22 take=yes cards were graded A, so the observation is real — but the fix *raises* fire count against a lane whose target is 1–3/day, and it re-scopes what THE LANE says we are building. Goes to §3 as a question for him, never shipped silently. |
| **"Earlier A/chop signal predicts the day's S trade" (3/3)** | `downgrade.sequence_gate` exists but points the *opposite* way (it penalizes later same-day entries). Building the predictive feature is medium work on 3 cards. |
| **`reject_entry_if entry_bar == break_bar`** | Nothing to gate: `omen_bot.py:615–724`'s 4-state FSM makes break-index and entry-index different by construction, in both B&R and OCR. See §5, contradiction 3. |

---

## 2. THE ONE CHANGE

**Ship shortlist #1: reconcile the two S/A/C implementations and wire the ratified grader as the fire gate.**

Everything else on the list moves dollars *after* the engine has already decided to trade. Only this one changes which days it trades, and the day-selection lever is worth +2.21R against exits' +0.06R.

**The exact change:** delete `compute_austin_tier`'s T11(a) hard-cap-to-C path (`signal_runner.py:1759–1767`), route the function through `research/downgrade.py::score()` (`S − tripped + confluence`, floored at C, per `omen-rulebook.md:266–296` ballot q18), and default `ENABLE_DOWNGRADE_GRADER=1` behind a new `S_CLASSIFIER_GATE` flag so the arm is reversible.

**The falsifiable test.** Honest book only: `ENTRY_FILL=close`, `stop_rule.stop_fill_price()`, `min_risk_floor` on. One trade per day, first setup of the day.

```
python research/g86_honest_ceiling.py          # $/day, win, green months
python research/t60_baseline.py                # precision / S-day recall
python research/regression_gate.py && python research/test_runner_stop.py
```

**PASS requires all four, measured against the same 25-month honest book:**

| metric | baseline | pass threshold |
|---|---:|---:|
| precision (of days it trades, share he'd have taken) | 39.5% | **≥ 50.0%** |
| S-day recall (his S days the engine still fires on) | current | **≥ current − 5.0pp** |
| first-setup-of-day $/day, honest close fill | $28 | **≥ $28** (no regression) |
| green months | 11/25 | **≥ 11/25** |

**FAIL** on any one of the four → the flag stays off and the result is committed as a measurement, not shipped. Precision above 50% bought by dropping more than 5pp of his S days is a fail, not a win — that is a ranker sneaking in through the back door.

**Not the pass bar, deliberately:** $397/day. One classifier change will not carry $28 to $397. The threshold above is "did the classifier get less wrong without going blind", which is the only thing this week can honestly answer.

---

## 3. WHAT THE MARKS CANNOT SETTLE

Ranked by how much an answer unblocks. Every one is answerable by pointing at a chart. None of them asks him to re-explain a rule he has already given.

**1. Mark the candle you would have entered on.** Serve 12–15 cards where the engine fired, with the engine's entry candle marked in one colour and *nothing else marked*. He clicks a candle. → Unblocks shortlist #3 and the entire entry-timing axis. Today all we know is a signed gap (7/7 late, median −10 min) with no target to close it to. This is the single highest-value hour of his time available.

**2. Which of these eight is displaced?** Four cards with a big body that stays inside the prior cluster; four with a small body that separates cleanly from it. Yes/no per card, no notes. → Unblocks shortlist #2 by settling body-size vs separation with contrast cases. The last displacement probe served 8 cards that all had the same ground-truth answer (§4), so we have 8 "no"s that discriminate nothing.

**3. Same setup, two days: which would you take?** `t1_AMZN_2025-08-22` and `AMZN_2025-11-21` side by side, both no-displacement A-grade entries, one on a trend day and one he called *"range chop day of hell"*. Pick one, or neither. → Unblocks whether displacement needs a day-regime term. Nothing in `downgrade.no_displacement` (188–197) reads day state; it is a flat boolean.

**4. Where does the runner come off?** Six charts with the 2R price drawn as one line and the nearest real level (PDH/PMH/whole dollar) drawn as another, sometimes inside 2R and sometimes beyond. He marks the exit. → Unblocks shortlist #4's *policy* (the guard is engineering, the choice is his) and shortlist #5's consumer.

**5. Two stops are drawn on this chart. Circle one, or write "no trade".** Start with `META_2024-09-30`, then 15 more from `g82.stop_candidates()`'s all-four-disagree filter. → Unblocks shortlist #7 and tells us whether "two stop options" is a veto, a downgrade, or a rendering artefact. Note both his `none` answers on the last stop-pick section read as *entry* refusals, not stop confusion — the pre-filter fix in §4 has to land before this probe is worth his time.

**6. You marked these seven "take". The engine would not fire on any of them.** Seven cards he graded A but said yes to. Keep / drop per card. → Unblocks the scope question the marks raise against THE LANE: the lane says "the 1–3 S setups", his marks say 7/22 of his takes were A-grade. This is a scope decision, not a measurement, and it should not be resolved by an agent.

**7. The engine can be honest or it can be early — pick.** Two charts of the same trade: one entry at the signal bar's close ($33/day, the shipped honest number), one at a limit resting after the signal bar (**$275/day**, 27% win, 15/25 green — honest, not shippable as-is). Which fill is the one he'd actually get? → Unblocks whether the entry-timing axis has any shippable ceiling at all. Frame it as two marked charts, not as a question about look-ahead.

---

## 4. INSTRUMENT BUGS — build list for the next deck

From the `meta_process` axis. None of these is a trading rule; all of them cost his time on the last page.

| # | Bug | Location | Fix |
|---|---|---|---|
| 1 | **Sampler is a plain shuffle, not stratified.** The displacement section served **8 consecutive cards with the same ground-truth answer**, so 8/8 "no" measured the deck, not him. | `research/build_probes.py:182` (`rng.shuffle(rows)`) | Group by the outcome field, interleave, then slice N. Localised to the row-selection step. |
| 2 | **`deep_is_s` has no structured `why_not`.** 25 refusals came back with reasoning only in free-text `notes.entry`, so no refusal can be counted. `render_is_s` and `render_take` both have the checkbox block; `render_deep` does not. | `research/g84_one_page.py:1085–1109` vs `860–863` / `1072–1075` | Add the `question("why_not", ...)` block with `hb.NO_REASONS` to `render_deep`. |
| 3 | **`stop_pick` has no quality pre-filter.** He had to editorialise that a trade was low-grade before he could answer the stop question — and both `none` answers turned out to be entry refusals, not stop confusion, which poisons the whole section. | card builder not located under `stop_pick` / `where_is_the_stop` in the current tree | Locate the builder first (name may have changed), then pre-filter to cards that already grade ≥A, and add an explicit "bad setup, skip" button so a refusal is recorded as a refusal instead of contaminating the stop answer. |
| 4 | **Entry and stop are not drawn on `trade_anatomy` cards**; OCR and level overlays are missing; the entry candle is illegible at deck scale. | same unlocated builder | Draw entry + stop as marked lines, render the level and OCR block, and zoom/highlight the entry candle. Static SVG, per the homework contract. |
| 5 | **No before/after diff harness for level computation.** Any change touching PDH/PDL/PMH/PML currently ships on a "low risk" assertion. `research/regression_gate.py` gates *detections* against a locked baseline, not level values. | new | Small script: dump PDH/PDL/PMH/PML across a fixed day sample, diff before vs after any levels change. Required for any level-code edit. |
| 6 | **Wording collapses two answers into one.** The `level_not_respected` checkbox reads *"level not respected — closing on it / chopping on it"*, so "chop" and "level not respected" are near-synonyms on the page he's answering — which is part of why they co-occur 8/9 times. | `research/g71_homework_build.py:222`, `research/g75_deck2_build.py:154` | Split into two checkboxes with disjoint wording, or drop one. The 8/9 co-occurrence cannot be interpreted until this is fixed. |

---

## 5. CONTRADICTIONS

Stated neutrally. Where a verbatim quote was not carried into the decode payload, that is said rather than paraphrased into quotation marks.

**1. No-displacement A-trades: worked, and lost both ways.**
- `t1_AMZN_2025-08-22` — graded such that the no-displacement entry *worked better*.
- `AMZN_2025-11-21` — same shape, both sides lost; his note calls it a **"range chop day of hell"**, and he flags the pair as contradicting each other himself.
No code resolves this: `research/downgrade.py:188–197` treats `no_displacement` as a flat boolean with no day-regime interaction term. → §3 question 3.

**2. Displacement: necessary, or one downgrade among eight?**
- 5/13 A-grade cards cite no-displacement as *the* downgrade reason, and `ACHR_2025-06-27` shows a single trip taking S → A.
- 2 cards graded **S** with "no displacement" stated, a named alternate confluence carrying them.
The ratified rule sides with the second reading (`omen-rulebook.md:281–297`: *"a setup with one downgrade and clean BR+OCR confluence is still S"*), and `downgrade.has_confluence()` implements it. `signal_runner.py::compute_austin_tier` sides with neither — it hard-caps to C *even when BR+OCR confluence is present*, per its own T11(a) comment at lines 159–167. Three answers, two of them in shipped code. → shortlist #1.

**3. "The engine enters on the break candle" vs the detector's control flow.**
- His `meta_process` complaint: the engine fires on the break candle instead of waiting for a confirmed retest (he has raised this more than once).
- `omen_bot.py:615–724`: the 4-state FSM (`seek_break → seek_leave → seek_retest → confirm`) makes `break_idx` and the entry candle different indices **by construction**, in both B&R and OCR paths. And `mentor_ballot` rule_03 grounds out the other way: entry already happens *on* the retest bar, mid-bar.
- Meanwhile the timestamp evidence says the engine is **late**, not early: 7/7 literal-timestamp cards, median −10 min.
Both cannot be true of the same code. Most likely the *symptom* is real and the *mechanism* is misnamed — what he is seeing is confirm-gap (up to 3 bars) plus close-only fill, not break-candle anchoring. Do not build `reject_entry_if entry_bar == break_bar`; it is already true. → §3 question 1 settles it with a chart, not an argument.

**4. Chop: the most-cited veto, and not a veto.**
- 15/22 refusals (68%) check chop — his single most-used reason.
- One CRM card is graded **yes** with the chop tag checked (card id not carried into the decode payload).
- The measurement disagrees with both readings: `level_not_respected` fires on 62.7% of the 2-year book and tripped trades average **+1.0046R (n=640)** vs clean **+0.8711R (n=377)**.
Three plausible resolutions and no way to choose from the marks: chop is a downgrade not a veto; or the checkbox wording (§4 bug 6) is measuring something else; or "chop" names 4 different states (level-chop, post-displacement collapse, range wall, trending-but-choppy) that only one of which is a veto. Not shipped either way.

**5. Retest tolerance: "a few cents give or take" vs zero.**
- His words: *"it doesn't follow the 25 percent candle unit, its just if its close but didnt actually touch, within a few cents give or take."*
- The sweep he authorised came back **zero** — a limit resting exactly at the level; every widened tolerance loses money (`research/g87_retest_tol.py`). Shipped default is `OMEN_RETEST_TOL_FRAC=0.0` (`signal_runner.py:1290`), i.e. exact touch.
Resolved in favour of zero **on detection**. Not resolved on execution: g87's headline `$469/day` was killed by g88 (89.6% of fills landed before the signal bar). Do not quote $469. The honest figures are **$33/day** shipped and **$275/day** for the strictly-after-signal limit.

**6. Bookkeeping correction, not a contradiction.** The mentor ballot census is **9 yes / 6 skip**, not 10/5 — yes on rules 1, 2, 3, 5, 6, 7, 9, 12, 14; skip on 4, 8, 10, 11, 13, 15 (`research/marks/probe_g84_all_in_one_STANDING154_2026-09-01.jsonl`, 9+6=15). The per-rule breakdown was right; only the two summary numbers were wrong. Separately, the phrase *"failed three implementations"* attributed to `downgrade.level_not_respected`'s docstring does not exist in that file or its history — the actual docstring is *"candles CLOSING AT the level, or chopping on it, instead of reacting off it."* Strike the phrase wherever it has been quoted. And `ENABLE_CHASE_DOWNGRADE` is **ratified and ON by default** (`downgrade.py:149–153`), not one of the three unratified additions — it must not be cited as precedent for adding an unratified variable.