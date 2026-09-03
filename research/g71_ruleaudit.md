# G7.1 / ruleaudit — the rule compliance table

**Question (Austin, 2026-08-29):** *"so are all the codebase rules not doing well?"* ·
*"besides s accuracy we need 100 percent rule following to my head"* ·
*"how much of it is just bugs and the codebase not following the rules."*

**Answer in one line:** of the 61 rules he has stated, **34 are implemented and faithful,
14 are implemented but diverge from his sentence, 9 are coded and shipped OFF, and 4 are
branches that can never evaluate true** — and the single most-repeated rule in the project
(*"wicks stop nothing out"*) is currently **violated on 100% of the traded book** by a
one-line placement bug in the disaster stop.

Counts: `research/g71_ruleaudit_counts.py` over `research/bt2y_trades.json`
(76,019 signals / 2,437 traded / 500 sessions / 28 symbols / 2024-08-21…2026-08-21,
generated 2026-08-29 03:14 by `backtest_2y.py`). Nothing here re-runs the engine; every
number is a count over the book the shipped engine produced. Recall gate re-run: `PASS`.

Sources of truth, in precedence order: `Austin's Vault/Projects/omen-rulebook.md`
(his sentences, dated) → `Trading-Bot-Rulesets.md` (numbered clauses from his notes) →
`research/EXTRACTED_TRADING_RULES.md` (Scarface boot-camp, *not his voice* — coverage
summarised in §4, never treated as a violation).

---

## 0. The headline bug — `DISASTER_STOP_R = 1.0` makes the disaster stop **be** the level stop

> *"A 1-minute **candle close** below is the exit. Max slippage −1.25R."* — ballot q1
> *"Stop-outs happen on the close, not the wick. A wick through the stop is not a stop-out."*
> — `Trading-Bot-Rulesets.md:167` (six mark ids)
> *"−1r is what we want max slippage −1.25"* — probe_master_2026-08-29, `fact_stop_floor_is_fiction`

`backtest_week._disaster_hit` (`backtest_week.py:379`) rests the disaster order at

```
disaster_stop_price(entry, abs(entry - stop), long, DISASTER_R)      # stop_rule.py:128
  = entry -/+ 1.0 * abs(entry - stop)        # DISASTER_STOP_R = 1.0, stop_rule.py:125
  = stop                                     # identically, for every row
```

because `risk` is **defined** as `abs(entry - stop)`. So the "cap that sits underneath the
level stop" sits **exactly on** it. It is tested with an intrabar **touch**
(`stop_rule.disaster_stop_hit:139`) and it is evaluated **before** the close-triggered
`_stop_hit` (`backtest_week.py:540-546`, `:585-586`).

**Measured, whole book:**

| claim | count |
|---|---|
| traded rows where the disaster-stop price equals the level-stop price | **2,437 of 2,437 (100.00%)** |
| losses booking exactly −1.0000R | **1,207 of 1,222 (98.77%)** |
| losses booking worse than −1.0000R | **0** |
| worst traded R in the book | **−1.0000** |

Three of his rules break at once:

1. **"Wicks stop nothing out"** — false. Every level stop in the book is now a wick stop.
   `stop_hit_on_close` is unreachable on any unscaled trade at its original stop.
2. **The −1.25R floor is unreachable code again.** `DIRECTION.md` invariant 1 records that
   this exact defect was fixed on 2026-08-28 (`research/t11_stop_fill_fix.md`, floor clamped
   303 of 475 losses). It **regressed on 2026-08-29** when the disaster stop shipped ON at
   R=1.0. The evidence pattern is the one `DIRECTION.md` calls "true of the file and circular
   as evidence": the book shows no row past −1.25R because no row *can* be.
3. **"A loss is not always exactly −1R"** (rulebook, Q&A 01) — the loss distribution has no
   left tail at all, by construction, which is the modelling error that sentence forbids.

**`fact_two_stops` verdict was `both`.** As shipped there is only one stop, and it is the
wrong one. Already priced, in the ticket that shipped it: `research/t1_two_stop_model.md`
§1 — arm `r100` (shipped) **+0.5378R at 42.8% win** against arm `clamp` (close-triggered,
−1.25R floor) **+0.6699R at 48.4% win**; the touch trigger kills **1,444 trades** a
close-only stop would have let run. The mean-R move is inside its bar; **the −5.6pp win rate
is not, and win rate is a money-gate leg.** Fix in §5.

---

## 1. Compliance table — Austin's rules (`omen-rulebook.md`, his sentences)

Legend — **impl**: Y implemented · N absent · OFF coded but shipped off · DEAD branch cannot be true.
**reach**: count over the 76,019-signal book that proves the branch evaluates true.

### 1a. Stops and exits

| # | his sentence (quoted) | impl | file:line | reachable? (proof) | matches exactly? | divergence |
|---|---|---|---|---|---|---|
| S1 | *"A 1-minute candle close below is the exit."* | **DEAD** | `backtest_week.py:540` `_stop_hit`; `stop_rule.py:40` | **0 of 2,437** — pre-empted on every row by `_disaster_hit:379` | **NO** | §0. The close trigger is unreachable; wicks stop trades out |
| S2 | *"Max slippage −1.25R."* | **DEAD** | `stop_rule.py:58,61` `MAX_LOSS_R` | **0 of 1,222 losses** book worse than −1.000R | **NO** | §0. Floor is unreachable code, second time |
| S3 | *"−1r is what we want max slippage −1.25"* (two stops, `both`) | Y (mis-placed) | `stop_rule.py:125` `DISASTER_STOP_R=1.0` | 2,437/2,437 coincide with the level stop | **NO** | one stop exists, not two |
| S4 | *"stops are wherever makes sense live … wick of OCR, candle entered on, break and retest of a level stop loss that level"* | **OFF** | `signal_runner.py:1122` `STOP_PLACEMENT="entry_bar"`; arms incl. `routed` at `:1120` | `routed` reproduces the shipped book **byte-for-byte** (`research/t24_stop_taxonomy.md` V1) — the detectors already route | partial | the FILL overwrites the choice: `intrabar_stop` (`:1406`) moves the B&R stop onto the entry bar's extreme on **803 of 947 traded B&R rows (84.8%)**. The R denominator is the entry bar, not his level |
| S5 | *"breakeven … you wait for candle closes"* (BE stop is close-based) | **Y** | `backtest_week.py:578-600`, `_stop_fill_px:351` | BE ends ~20 rows | yes | P37 landed |
| S6 | *"if we dont hit price target 1, we dont raise the stop to BE, but we need to run stats on with enough movement raising to BE"* | **Y (arm OFF)** | `backtest_week.py:160-161` `BE_TRIGGER="pt1"`, `BE_MOVE_R=0` | `mfe` arm never fires at default | yes (his default) | the *stats* he asked for exist (R11/T11); the arm ships off, correctly |
| S7 | *"ladder 30 / 30 / 30 / 10, fixed"* (q5) + *"only managing a 10 percent position"* (c7) | **N** | `backtest_week.py:144` `SCALE_PLAN="hod_then_runner_be"` = **50% / 50%** | 100% of scaled rows use 50/50 | **NO** | P24 open. Priced at 0.002R whole-book, **+0.074R on the S subset** |
| S8 | *"tranche 1 at HOD"* (q4) | **Y** | `backtest_week.py:846-857` `scale_level` = causal session extreme | every scaled row | yes | — |
| S9 | *"flat by 11:00 — only the 10% runner may still be live"* (q6, c7) | partial | `signal_runner.py:1043` `SESSION_END=11:00:00` | **0 of 2,437** entries at/after 11:00; last entry 10:59 | entry half yes | the runner is 50%, not 10% (S7). P22 closed the entry half, left this |
| S10 | *"you cant refute let runners run and cut losers quicker"* | **N** | — | — | **NO** | no structure-trailed runner exists; `research/p10_structure_trail.md` tested a mechanical trail, not this |
| S11 | *"The target is the next structural level, not 2× risk"* / b4 *"its about sizing for the mean 2rr, so if there are no other levels to target … harder to trade"* | **N** | `backtest_week.py:836-837` `target = entry ± 2*risk` | **52,239 rows plan exactly 2.000 R:R** | **NO** | P21/P32 unbuilt. `mean R = wT−(1−w)` ⇒ a flat 2R target can never mean 2.0R. **This is the money gate** |
| S12 | *"C is data collection … the priority is always S"* (C never traded) | **Y** | `backtest_week.py:283` `counted` excludes `C` | **0 C rows traded** of 3,053 | yes | — |
| S13 | two-consecutive-loss halt, account-wide (R31 `both`) | **Y** | `loss_halt.py:47,51`; `live_scanner.py:573` | **857 signals halted** | yes | ships ON at his number |

### 1b. Entries, the clock, the window

| # | his sentence | impl | file:line | reachable? | matches? | divergence |
|---|---|---|---|---|---|---|
| E1 | *"I dont trade past 11 am"* / clause 3 (incl. the 84% leg) | **Y** | `signal_runner.py:1042-1043` | 0 of 2,437 at/after 11:00 | yes | — |
| E2 | *"Entries can happen any time in our window, I don't know where you got they can't be before 9:40"* (R12) | **Y** | `live_scanner.py:539` — `TRADE_FLOOR` deleted | 136 traded entries before 09:40 (5.6%) | yes | fixed |
| E3 | *"a golden rule the earlier in the day you trade, the more common it is for S trades"* | reported only | `backtest_2y.py` `slot` column | 09:30 slot = 17,169 signals | n/a | descriptive; nothing gates on it, correctly |
| E4 | *"good to note 1045 to 11 window is bad but keep."* | **Y** | no filter exists | 151 traded rows, **+0.6610R** | yes | kept as instructed |
| E5 | *"as candle forming not HOD/LOD"* / ON WATCH | **Y (never priced)** | `signal_runner.py:503` `ON_WATCH=1`, `near_session_extreme:1333`, `BAR_EXTREME_FRAC:499` | ships ON; **never A/B'd on the 2-year rig** (P9/P31 open) | partial | he later corrected it to a **decision clock at T−15s**, not a fill rule; and *"ON WATCH is not universal"* (card 7: a level at the entry ⇒ the close confirms) — no level condition in the code |
| E6 | *"an entry taken intrabar that then closes back beyond the level is not a loss — scratch out at close"* (clause 2) | **OFF** in backtest, **absent** live | `backtest_week.py:237` `ENTRY_SCRATCH=""`; `paper_trader.py` has no scratch outcome | 17 scratches in book, all EOD | **NO** | P8 proved the backtest cannot express it; **the live path still does not implement it either** (G11 open) |
| E7 | *"no repeat entries"* (q11) — unless entry + 84%-rule re-entry | **OFF** (ratified off) | `signal_runner.py:1026` `NO_REPEAT_ENTRIES=0` (R17: *"the 84% rule already handles re-entries"*) | **283 traded rows are 2nd+ on their symbol-day; 123 are 84% re-entries ⇒ 160 unsanctioned** | partial | R17 ratified OFF, but 160 rows are exactly the thing q11 forbids. The lever he *did* ratify for it (`sequence_gate`) is also OFF — see G12 |
| E8 | *"we need to increase trade size not so exact to 1-2, just however many engine sees we trade S"* (no cap) | **Y** | `live_scanner.py:554` `GOVERNOR_S_CAP=None`; `signal_runner.py:1235` `S_PLUS_PER_DAY=0` | uncapped | yes | — |
| E9 | *"Do not enter at the session extreme"* (`Trading-Bot-Rulesets.md:186`, clause 4, "a veto") | **OFF** | `signal_runner.py:1060` `SESSION_EXTREME_FRAC=0.0` | never fires | n/a | **superseded on purpose** by the 2026-08-23 ON WATCH answer (*"He takes them and refuses to pay the close"*). Recorded so nobody re-opens it |
| E10 | *"I never enter on breaks, I enter on retests with strong price confirmation"* | **Y** | `omen_bot.detect_break_retest:600` (4-step FSM) | 70,237 B&R detections | yes | — |
| E11 | order type — *"limit at the level, no chase"* (answered 2026-08-28) | **N (unstated)** | `signal_runner.py:1139` `STOP_FILL_ORDER="as_booked"` | both conventions expressible, neither declared | **NO** | P36. `research/t24_stop_taxonomy.md` V3: market-on-close takes the same book from **+0.8341R / 23-of-25 months** to **+0.0955R / 18-of-25**. ~90% of the measured edge rides on this |

### 1c. The 84% rule

| # | his sentence | impl | file:line | reachable? | matches? | divergence |
|---|---|---|---|---|---|---|
| R84-1 | *"modifier, not a standalone"* (q12) | **Y** | `SignalType.REENTRY_84_RULE`, armed only from a stop-out (`backtest_week._arm_84:417`) | 388 detections / **123 traded** | yes | was 3 traded before R6; now healthy |
| R84-2 | *"it re-enters the price you entered on"* (q12) | **Y** | `backtest_week.py:467` `session.entry_price` | — | yes | — |
| R84-3 | *"what counts as reclaim = candle close"* (q13) | **Y** | reclaim clause `signal_runner.py:~2380/~2600` | — | yes | — |
| R84-4 | *"as long as the close is not too far from original entry"* → ratified default **one tolerance unit (25% of the previous candle's range)** | **OFF** | `signal_runner.py:350-351` `RULE84_RECLAIM_TOL=None` (**unbounded**), `_reclaim_tol_ok:354` returns True | the cap never binds | **NO** | P39 took this default; it was never applied. Any close, any distance, reclaims |
| R84-5 | *"attempts per day: two"* (q14) | **Y** | `signal_runner.py:1065` `RULE84_MAX_ATTEMPTS=2` | enforced at `:2961` | yes | — |
| R84-6 | *"84 percent rule can fire on S A or C"* (no grade gate at arming) | **Y** | `backtest_week._arm_84:454` `RULE84_STRICT` off | 123 traded | yes | fixed by R6/T3 |
| R84-7 | *"the candle must match the trend"* (q15) | **Y** | reclaim direction gate | — | yes | — |
| R84-8 | *"same stop unless a new stop makes more sense"* | **OFF** | `signal_runner.py:324` `rule84_source_stop`, gated by `RULE84_STOP_QUALIFIER=0` (`:~928`) | never called at default | partial | his qualifier is coded and disabled; the default (original stop) is his default, so the divergence is only the "unless" |

### 1d. Grading — the eight (now ten) variables

Trip counts over all 76,019 signals; money delta = traded mean R (tripped − clean). **A
downgrade whose delta is positive is marking better trades worse.**

| # | variable / his sentence | impl | file:line | trips | traded Δ mean R | verdict |
|---|---|---|---|---|---|---|
| G1 | `no_displacement` — *"the break has no force behind it"* (q18) | Y | `downgrade.py:163` | 38,263 (50.3%) | **+0.0112** | null-signed |
| G2 | `stale_retest` — *"ill say 10"* (b11) | Y | `downgrade.py:203`, `STALE_BARS=10:51` | **490 (0.64%)** | −0.0255 | ratified but near-degenerate |
| G3 | `level_not_respected` — *"has to hold the level or candle period. chopping around is not respecting."* / *"invalidation happens as soon as close below"* (a2/a3) | **Y, wrong test** | `downgrade.py:218-223` | **49,989 (65.8%)** | **+0.1291** | **counts closes within ε of the level on EITHER side. His rule is a close THROUGH it.** Wrong-signed; 4th failed reading; P38 unbuilt |
| G4 | `exhausted` — *"already made a large move … the move is spent"* | Y | `downgrade.py:226`, `EXHAUSTED_ATR=10.0:55` | 9,150 (12.0%) | **+0.3986** | wrong-signed; threshold is an unratified guess |
| G5 | `counter_trend_not_respected` — *"lowers probability each time"* (a4/a5="2") | Y | `downgrade.py:237`, `UNRESPECTED_COUNTER=2:61` | **69,537 (91.5%)** | −0.0992 | saturated. a4 describes a **graduated** cost; the code is binary at 2 |
| G6 | `break_then_rejection` — *"when a stock breaks above a level, and then a candle closes below the same level, it rejected it"* | **DEAD** | `downgrade.py:259-268` | **0 of 76,019** | n/a | **unreachable-rule bug.** `_break_bar:180` returns the **most recent** cross, so by construction no close back through can sit after it. The grader is 8 variables, not 9 |
| G7 | `no_retest` — *"breaks and doesn't retest the level"* | Y | `downgrade.py:271` | 10,356 (13.6%) | **−0.3677** | **the only strongly right-signed variable in the set** |
| G8 | `ocr_not_respected` — *"we want price to respect it and break and retest it"* | Y | `downgrade.py:317` | 20,021 (26.3%) | +0.0404 | null-signed |
| G9 | `chase` — *"don't buy the top"* (R22, ratified ON) | Y | `downgrade.py:419`, `CHASE_PCT=0.005:127` | 5,720 (7.5%) | **+0.3449** | ratified, and **wrong-signed on this book** — chasers book better |
| G10 | `large_counter_body` — *"large 75 percent red body candles … within range of other candles"* (b6) | **OFF** | `downgrade.py:337`, `ENABLE_LARGE_COUNTER_BODY=False:83` | **0** | — | his sentence, never executes |
| G11 | `multi_level_confluence` (+1) — *"count bull/bear PA and below/above at least 5/6 levels i watch a +1"* (b5) | **OFF** | `downgrade.py:375`, `ENABLE_MULTI_LEVEL_CONFLUENCE=False:91` | **0** | — | his sentence, never executes. P19 measured it **right-signed +0.250R** |
| G12 | `sequence_gate` — *"anytime there was an s a or c entry, a subsequent entry thats not 84 percent rule cannot be ranked the same quality"* (b2) | **OFF** | `downgrade.py:402`, `ENABLE_SEQUENCE_GATE=False:112` | **0** | — | his sentence, never executes. P20 measured it **right-signed −0.325R**, the only lever that cut false fires |
| G13 | `has_confluence` (+1) BR+OCR — *"that counts as +1"* | Y | `downgrade.py:450` | **50,510 (66.4%)** | **−0.0777** (traded yes vs no) | handed to two thirds of everything ⇒ **cannot discriminate**; and wrong-signed |
| G14 | *"S = zero · A = one · C = two"*, `score = tripped − confluence` | Y | `downgrade.py:527-528` | S 9,923 / A 17,639 / C 48,457 | yes | the arithmetic is his |
| G15 | *"3+ downgrades floors at C"* (2026-08-24, re-resolved 2026-08-28: *the floor stands*) | **Y in `downgrade.py`, VIOLATED in the live ladder** | `downgrade.py:528` (floor) **vs** `signal_runner.py:2136` `… else ("C" if net == 2 else "X")` | **2,387 of 6,395** non-X signals go to `X` instead of `C` under the live ladder | **NO** | `live_scanner.py:30` forces `ENABLE_SAC_LADDER=1`, so the **live path runs the reading he rejected**. Those rows leave the alert/corpus stream entirely |
| G16 | displacement exemptions — *"BR+OCR confluence · a bull/bear flag to start the day · a longer-timeframe thesis"* forgive a missing displacement (q18) | **N** | `signal_runner.py:2784`, `:3063`, `compute_austin_tier:1676` — cap to C with **no exemption test** | **37,339 signals (49.1%) carry both `nodisp` and `brocr`** and are capped anyway | **NO** | exemption 1 is computable today and is not applied |
| G17 | *"OCR = one candle that's the opposite colour of the way it's trending"* + *"price must respect it and break and retest it"* | Y | `downgrade.find_ocr:280`, `ocr_not_respected:317`; `omen_bot.detect_order_block_setup:403` | 5,394 OCR detections / 379 traded | yes | the B→C demote at the detection site is **lifted** (R3) — fixed |
| G18 | card 11 — *"would the candle be good to use as the stop?"* (stop-usability test wins) | Y | `downgrade.has_confluence:467` `usable = edge ≤ close` | — | yes | — |
| G19 | *"at/near HOD or LOD is NOT a downgrade"* (q16) | Y | absent from `VARIABLES` | — | yes | — |
| G20 | *"higher timeframe thesis … is a corpus merge project"* — not countable | Y | not in `VARIABLES` | — | yes | — |

### 1e. Routing, ladders, vetoes

| # | his sentence | impl | file:line | reachable? | matches? | divergence |
|---|---|---|---|---|---|---|
| L1 | *"we only trade S trades and im thinking A +1 (which is technically S)"* (c5) | **N in the book** | `signal_runner.py:492` `TRADE_S_ONLY = False` — **defined and read nowhere** (`test_austin_tier.py:143` asserts that) | — | **NO** | **2,139 of 2,437 traded rows (87.8%) are not his S.** By his grade: S 298 / A 525 / C 1,614 |
| L2 | *"a+ shouldnt exist. a+ and b shouldnt exist if they do."* | **N** | `signal_runner.py:188` `_GRADE_RANK` still A+/A/B/C/X; `omen_bot._grade_pa:250` | traded: **B 2,361 · A 72 · A+ 4** | **NO** | P34 open. The letter he deleted is 96.9% of the traded book |
| L3 | *"we dont have any higher timeframe bias yet youll need to tell me what that is then"* (c6) → **DELETE the veto** (2026-08-28) | **N — ships ON** | `omen_bot.py:29` `HTF_BIAS_VETO = getenv(...,"1")`; applied `omen_bot.py:242`, `signal_runner.py:2365` | **35,628 of 76,019 opposed (46.9%)**; 445 opposed rows still trade via `X_LIFT` | **NO** | P33/P16 open. A veto with no author gates half the book |
| L4 | *"keep both … don't let it cap you of S opportunities"* (R18, arrival order) | **OFF** | `signal_runner.py:778` `ARRIVAL_LADDER="off"` | never fires | partial | the incumbent `_calibration_grade` B-floor still selects the book; the S-safe promotion arm he asked for is off |
| L5 | X lift — *"clear break retest with displacement that happens quick and strong PA entry"* | **Y** | `signal_runner.py:904` `X_LIFT="clean"` | 3,191 B rows exist because of it | yes | T23; held-out S recall 18/34 → 23/34 |
| L6 | *"no minimum stop distance on OCR, size to the stop"* (R4) + *"I meant stock price not bid ask"* (R30) | **Y** | `signal_runner.py:915` `MIN_STOP_PCT=0.08`, OCR exempt at `:2585` | 2,051 `skipped_tight_stop` | yes | — |
| L7 | tight-stop gate — ratified *"applied to every grade first, then re-measured"* | **N** | `signal_runner.py:2594` `if sig["grade"] != "C" or self._min_viable_stop(...)` | consulted on **C only**; B/A/A+ bypass it entirely | **NO** | P39 took this default; not applied |
| L8 | *"the bottom-quartile premarket filter ships ON"* (P35, his explicit instruction, +0.1568R / 0 recall cost) | **N** | no `ranker` / `pm_score` exists in `signal_runner.py` or `backtest_week.py` | — | **NO** | ratified, never built |
| L9 | *"STOP_TRIGGER_BUFFER_FRAC stays 0"* | Y | no buffer constant in the trigger | — | yes | — |
| L10 | *"the two +1s do not stack, cap stays +1"* | Y | `downgrade.py:526` `confl = a or b` | — | yes | — |
| L11 | *"`STRONG_PA_MULT = 1.5` dies"* (P39 — replaced by the one tolerance unit) | **N — still live** | `signal_runner.py:99`, used `:2253`; mirrored `omen_bot.py:472` `OCR_STRONG_PA_MULT`, used `:500` | gates every 84% strong-PA test and every OCR quality score | **NO** | ratified dead, still load-bearing in two files |
| L12 | *"One tolerance unit: 25% of the previous candle's range"* | partial | `signal_runner.py:499` `BAR_EXTREME_FRAC=0.25`; `downgrade._eps:149` uses `0.25 × ATR` | ON WATCH ✓, stop slippage ✓ | partial | the 84% reclaim window (the third use) is **unbounded** — R84-4 |
| L13 | *"i never want to see stock repeats of stocks i have already graded"* | **Y** | `research/build_deck.py::marked_card_ids()` + `LEGACY_MARK_FILES` | — | yes | — |
| L14 | *"indecies not traded much either everything should be pretty balanced"* | partial | `universe.py` | **index 164 of 2,437 (6.7%)**; COIN alone 203 | **NO** | improved from 1.8% but still heavily under-weighted per name |
| L15 | *"I don't trade FVG or FLAG"* | Y | `signal_runner.py:805` `RETIRED_SETUPS` | 0 traded | yes | — |
| L16 | two competing implementations of *his* S/A/C | — | `compute_austin_tier:1656` (4 clauses) **vs** `downgrade.score:475` (10 variables) | both live, both reported | **NO** | one ladder, two definitions of `S`. `austin_tier` is reported; `sgrade` is what live routes on |

---

## 2. The unreachable-rule bug class — the register

`memory/omen-rules-unreachable-in-code.md`. A real rule becomes a branch that can never be
true. Confirmed instances, now **six**:

| # | rule | site | reach | status |
|---|---|---|---|---|
| 1 | T4(b) failed-entry scratch | `backtest_week` (deleted) | 0 / 43,374 | fixed (deleted, P8) |
| 2 | the −1.25R floor (fill at `t.stop`) | `backtest_week` pre-T11 | 0 / 45,193 | fixed 2026-08-28… |
| 3 | `level_not_respected` anchored on `_break_bar` | `downgrade.py` (P15 arm) | 13 / 45,175 | rejected, not shipped |
| 4 | `break_then_rejection` | `downgrade.py:259` | **0 / 76,019** | **OPEN** |
| 5 | lookahead guard inside `find_ocr` | `downgrade.py:293` | 0 / 853,010 | fixed (removed, W12) |
| 6 | **the −1.25R floor, again** — pre-empted by a disaster stop resting on the level stop | `stop_rule.py:125` + `backtest_week.py:379` | **0 / 2,437** | **OPEN — §0** |

Adjacent, same family: **`TRADE_S_ONLY` (`signal_runner.py:492`) is a constant read by no
code path**, and a repo test asserts that it stays that way. His routing rule has no
executable form.

---

## 3. What is going *well* (so the answer is not one-sided)

The window (E1), the deleted 09:40 floor (E2), the 84%-rule arming and 2-attempt cap
(R84-1/5/6), C-as-alert-only (S12), the loss halt (S13), the no-repeat guarantee on decks
(L13), the retired setups (L15), the OCR demote lift and the `X_LIFT` recall lever (L5),
the min-stop rule with the OCR exemption (L6), the BE-close convention (S5), stop
placement already routing structurally (S4, byte-identical), the grade arithmetic itself
(G14) and `no_retest` (G7) all match his sentences. **34 of 61 rules are faithful.** The
recall gate is green. Durability is 25/25 months.

---

## 4. `EXTRACTED_TRADING_RULES.md` — coverage, not compliance

That file is the Day-5/Day-6 boot-camp transcript (Scarface), **not Austin's voice**, and
his own rulebook narrows the engine to three setups. Implemented: **order block / one candle
rule** (`omen_bot.detect_order_block_setup:403`), **opening range** (OR high/low levels),
**84% rule / reclaim** (`REENTRY_84_RULE`), **break and retest** (`detect_break_retest:600`).
Not implemented, and **not violations**: gap-and-go, gap fill, opening drive, dip & rip,
pop & fade, first pullback, kill candle, relative strength / correlation buying, index
correlation rules, day-number theory. `Trading-Bot-Rulesets.md:410` "Written but not yet
implemented" lists seven more of *his* notes with no detector — wick-touch as a hard B&R
filter, pre-signal wick confidence, trendline second confirmation, order-block stop
selection (*"closest to the level that still clears 2:1"*), candle speed, OCR prior-visit
veto. All confirmed absent; the file's own header already says so.

---

## 5. Ranked violations by cost, and the top-five diffs

| rank | violation | evidence | cost |
|---|---|---|---|
| **1** | §0 disaster stop == level stop ⇒ wicks stop out, −1.25R floor unreachable, every loss exactly −1R | 2,437/2,437 rows; 1,207/1,222 losses at −1.0000R | `t1_two_stop_model.md`: **−5.6pp win rate** (48.4%→42.8%), 1,444 trades killed on a touch. Breaks his most-repeated rule |
| **2** | S11 flat 2R target | 52,239 rows at exactly 2.000 R:R | **the money gate is arithmetically unreachable**; 296 rows already run past +2R, mean MFE +4.10R |
| **3** | G3 `level_not_respected` wrong test / wrong sign | trips 65.8%, Δ **+0.1291R** | corrupts every S/A/C grade — **and his S bucket is the worst money bucket** (S +0.355 < A +0.530 < C +0.592) |
| **4** | L1+L2 routing: 87.8% of traded rows are not S; `B` is 96.9% of the book | `TRADE_S_ONLY` read nowhere | the book measures a system he says he would not trade |
| **5** | live ≠ backtest: `live_scanner.py:30` forces the SAC ladder, the book runs the legacy chain; and the live ladder kills net≥3 to `X` | live-tradeable ≈ **729 S signals** vs the book's **2,437** | **real-money blocker** (P27), plus 2,387 corpus rows lost |
| 6 | L3 `HTF_BIAS_VETO` ships ON with no author | 46.9% of signals opposed | rulebook says deleted; P16 says lifting frees only 60 S (1.7%) — low money, high rule cost |
| 7 | G16 displacement exemptions unimplemented | 37,339 signals (49.1%) are `nodisp`+`brocr` | capped to C against ballot q18 |
| 8 | G10/G11/G12 three ratified rules ship OFF | 0 trips each | P19 +0.250R right-signed, P20 −0.325R right-signed |
| 9 | L8 bottom-quartile filter never built | — | **+0.1568R, 23/25 months, zero recall cost**, he said ship it |
| 10 | R84-4 reclaim tolerance unbounded · L11 `STRONG_PA_MULT` alive · L7 tight-stop gate C-only | — | three P39 defaults never applied |
| 11 | S7 exit ladder 50/50 not 30/30/30/10 | 100% of scaled rows | +0.074R on the S subset |
| 12 | E11 order type unstated | — | ±0.74R of a +0.83R book rides on it |
| 13 | G4/G9 wrong-signed; G5 saturated at 91.5%; G13 confluence on 66.4% | — | four of ten grader inputs carry no information |
| 14 | E6 scratch absent from the live path | `paper_trader.py` has no scratch outcome | G11 open |
| 15 | E7 160 unsanctioned same-symbol-day repeats | 283 − 123 | q11 |
| 16 | L14 index share 6.7% | 164 / 2,437 | his balance complaint, partly addressed |

### Diff 1 — the disaster stop must rest at the cap, not on the level (rank 1)

```diff
--- a/stop_rule.py
+++ b/stop_rule.py
@@
-#   * DISASTER_STOP_R = 1.0  — where the disaster stop RESTS. A live order
-#     sitting at entry -/+ 1R that fills on an intrabar TOUCH. This is the loss
-#     he plans for.
+#   * DISASTER_STOP_R = 1.25 — where the disaster stop RESTS. It is the CAP, and
+#     a cap must sit UNDERNEATH the level stop or it replaces it. `risk` is
+#     defined as abs(entry - stop), so at 1.0 the resting order lands EXACTLY on
+#     the level stop on every row (2,437 of 2,437, research/g71_ruleaudit.md s0)
+#     -- the intrabar touch then pre-empts the close trigger and "wicks stop
+#     nothing out" becomes false for the whole book.
 #   * MAX_LOSS_R = 1.25      — the OUTER BOUND. Nothing may book past it, ever.
-DISASTER_STOP_R = 1.0
+DISASTER_STOP_R = MAX_LOSS_R
```

Effect, already priced (`research/t1_two_stop_model.md` §1, arm `r125`): worst trade back to
−1.250R, win rate 42.8% → 46.0%, the close trigger becomes the primary exit again, and the
−1.25R floor becomes reachable. It costs one month of durability (25/25 → 24/25) — **flag
that to Austin rather than deciding it**, because durability is a gate.

### Diff 2 — the target is the next structural level (rank 2)

```diff
--- a/backtest_week.py
+++ b/backtest_week.py
@@
-            # 84% signals carry the ORIGINAL trade's target; everything else 2R
-            target = sig.get("target") or (
-                sig["entry"] + 2 * risk if sig["direction"] == "call" else sig["entry"] - 2 * risk)
+            # 84% signals carry the ORIGINAL trade's target. Everything else
+            # targets the NEXT STRUCTURAL LEVEL beyond entry (Austin, b4 and
+            # 2026-08-28: "its about sizing for the mean 2rr, so if there are no
+            # other levels to target ... harder to trade"). A flat 2R target
+            # makes mean R = wT - (1-w) reach 2.0 only at a 100% win rate.
+            # TARGET_POLICY=r2 restores the flat-2R book every earlier figure
+            # was measured on.
+            target = sig.get("target")
+            if target is None and TARGET_POLICY == "level":
+                target = _structural_target(sig, candles[:i + 1],
+                                            pdh, pdl, pmh, pml, risk)
+            if target is None:
+                target = (sig["entry"] + 2 * risk if sig["direction"] == "call"
+                          else sig["entry"] - 2 * risk)
```

`_structural_target` is P21's level-availability check — the causal roster already exists as
`research/p21_target_availability.py::levels_for_entry`. When no tracked level sits ≥2R away
the row falls back (or, under P21's own arm, is not taken), which is the entry-side
information G7/G9 both closed on. **Ships behind `TARGET_POLICY`, default `r2`, until
measured.**

### Diff 3 — `level_not_respected` counts the wrong side (rank 3)

```diff
--- a/research/downgrade.py
+++ b/research/downgrade.py
@@
 def level_not_respected(bars, i, level, is_long):
-    """Austin's own words: candles CLOSING AT the level, or chopping on it,
-    instead of reacting off it."""
-    e = _eps(bars, i)
-    window = bars[max(0, i - 12):i + 1]
-    return sum(1 for b in window if abs(b["c"] - level) <= e) >= CHOP_TOUCHES
+    """Austin, ballot batch 02 a2/a3: "if its closing above the level but still
+    wicking around it its fine, invalidation happens as soon as close below or
+    vise versa for calls" / "has to hold the level or candle period."
+
+    Respect is a close on the CORRECT side, wicks included; only a close THROUGH
+    the level is disrespect. The committed form counted closes within a
+    tolerance of the level on EITHER side -- it trips on 65.8% of the two-year
+    book and points the WRONG WAY (+0.1291R traded delta), because it measures
+    proximity, not respect.
+
+    P38's anchor: the level's own history BEFORE this setup, not the bars after
+    the break -- three post-break readings have already failed.
+    """
+    e = _eps(bars, i)
+    br = _break_bar(bars, i, level, is_long)
+    hi = br if br is not None else i          # the level's history, pre-break
+    lo = max(0, hi - 12)
+    through = sum(1 for b in bars[lo:hi]
+                  if ((b["c"] < level - e) if is_long else (b["c"] > level + e)))
+    return through >= CHOP_TOUCHES
```

**If this reading also fails, delete the variable** — P38's own standing instruction. A
variable that trips on two thirds of the book in the wrong direction is worse than none.

### Diff 4 — `break_then_rejection` can never be true (rank 6, unreachable class)

```diff
--- a/research/downgrade.py
+++ b/research/downgrade.py
@@
 def break_then_rejection(bars, i, level, is_long):
-    """Austin, unprompted: it broke, then immediately gave it back."""
-    br = _break_bar(bars, i, level, is_long)
-    if br is None:
-        return False
+    """Austin: "when a stock breaks above a level, and then a candle closes
+    below the same level, it rejected it."
+
+    Anchored on the SESSION'S FIRST break, not `_break_bar`. `_break_bar`
+    returns the MOST RECENT cross, so a close back through the level after it is
+    unrepresentable by construction -- the variable tripped 0 times in 76,019
+    signals (research/g71_ruleaudit.md s2, bug-class instance 4).
+    """
+    br = _first_break_bar(bars, i, level, is_long)
+    if br is None:
+        return False
     for j in range(br + 1, min(br + 1 + REJECT_BARS, i + 1)):
         back = (bars[j]["c"] < level) if is_long else (bars[j]["c"] > level)
         if back:
             return True
     return False
+
+
+def _first_break_bar(bars, i, level, is_long):
+    """Index of the EARLIEST bar at or before `i` that CLOSED through `level`."""
+    for j in range(1, i + 1):
+        prev, cur = bars[j - 1], bars[j]
+        crossed = ((prev["c"] <= level < cur["c"]) if is_long
+                   else (prev["c"] >= level > cur["c"]))
+        if crossed:
+            return j
+    return None
```

### Diff 5 — the live ladder must not kill `C` (rank 5)

```diff
--- a/signal_runner.py
+++ b/signal_runner.py
@@ _sac_ladder_grade
-        his = "S" if net <= 0 else ("A" if net == 1 else ("C" if net == 2 else "X"))
+        # Austin, 2026-08-24 and re-resolved 2026-08-28: "3+ downgrades floors
+        # at C" -- C IS THE FLOOR, there is no X below it. The `else "X"` here
+        # was the 2026-08-28 "kill B" sentence read as a re-floor, which the
+        # rulebook explicitly rejects ("Reading it as a re-floor would take the
+        # book from 1,017 rows to 48"). live_scanner.py:30 forces this ladder
+        # ON, so the shipped LIVE path was running the rejected reading and
+        # dropping 2,387 of 6,395 non-X signals out of the alert/corpus stream.
+        his = "S" if net <= 0 else ("A" if net == 1 else "C")
```

`_arrival_ladder_grade` (`signal_runner.py:2166-2170`) already documents and implements the
floor correctly — which is exactly why the two ladders disagree today.

---

## 6. What is NOT a bug, so nobody re-opens it

- **E9 session-extreme veto OFF** — superseded by the ON WATCH answer, on purpose.
- **E7 `NO_REPEAT_ENTRIES` OFF** — R17 ratified it off; the residual 160 repeats belong to
  the OFF `sequence_gate` (G12), not to this flag.
- **E4 the 10:45–11:00 window** — measured negative, kept on his instruction.
- **The Scarface boot-camp setups (§4)** — out of scope by his own rulebook.
- **`downgrade.py` unwired in the backtest** — deliberate ("measure, then wire",
  `DIRECTION.md` invariant 6). The violation is that the **live** path wired it anyway
  without the backtest following (rank 5).

---

Artefacts: `research/g71_ruleaudit_counts.py` (every count above), this file.
No engine file was edited; every fix is a diff, not a commit.
