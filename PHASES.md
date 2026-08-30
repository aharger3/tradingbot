# PHASES — the dispatch board

**Superseded 2026-08-29 by `OMEN-7.2.md`** as the dispatch board for this version — see its
own header. `DIRECTION.md` still holds the invariants and the current gate numbers; this
file is kept as the historical record of P1–P39 and is not re-read for current status.

Everything in the queue, grouped into phases that can be handed to a subagent as a unit.
`TASKS.md` holds the detail; this is the order and the parallelism. Lanes are from
`DIRECTION.md`: **green** runs unattended, **amber** runs then flags, **red** needs Austin.

To dispatch: say the phase number. Phases inside the same block are independent and can run
at once; blocks are sequenced because a later one reads an earlier one's answer.

Every trade count and R-figure below is a snapshot from when that phase ran (commit hash
given), not the current book. The current book is **4,508 trades** (`research/g72_after.md`,
2026-08-29) — see `DIRECTION.md` for the live gate numbers.

---

## Block 1 — the entry side (closed — all three done)

The binding constraint. G7 proved the exit is already at the top of its family, so
everything that closes the money gate is upstream of the fill.

| phase | task | lane | state |
|---|---|---|---|
| **P1** | ~~**G4 — what the grader throws away**~~ **DONE 2026-08-26** (`d8b04625`, `research/g4_dropped_s.md`): 7,219 dropped S attributed by branch — HTF bias 3,525 · colour 2,120 · B&R min-stop 1,385 · OCR 174. Only two are the grader. 303 fail on colour alone, 142 of those reach tradeable B. | green | done |
| **P2** | ~~**A1 — threshold sweep on `downgrade.py`**~~ **DONE 2026-08-26** (`d2b67c22`, `research/p2_threshold_sweep.md`): the distribution objection dissolved — 168/304/778 vs 28/27/3 was a units error (per-signal vs per-day-card); in his own unit the grader is at 29/23/6, distance 0.069. The real failure is *which* days: day-level agreement 21/58, S recall 12/28. **No threshold in the sweep fixes that** — which is what sends the work to Block 6. | amber | done |
| **P3** | ~~**G8 — BR+OCR confluence as its own setup**~~ **DONE 2026-08-26** (`research/p3_confluence.md`): `SignalType.BR_OCR_CONFLUENCE` labels every signal where `downgrade.has_confluence` holds. 29,815 of 45,175 detections re-labelled; the book is identical to the cent (1,016 traded, 52.95%, +0.9571R, +972.38R). Funnel — B&R alone 13,546 → 828 → 391 (50.1%, +0.888R) · OCR alone 1,811 → 70 → 16 (18.8%, −0.315R) · confluence 29,815 → 1,353 → 606 (55.6%, +1.030R). Routing unchanged; `CONFLUENCE_SETUP_ROUTES` default OFF. | green | done |

## Block 2 — retire the legacy ladder

Austin, 2026-08-26: *"no more A+, it's just S A C. That's what needs to be coded."*
Sequenced after P2 because wiring a grader whose thresholds are unratified guesses is the
exact mistake `downgrade.py`'s header exists to prevent.

| phase | task | lane |
|---|---|---|
| **P4** | **R3 — wire `downgrade.py` into detection**, behind a flag defaulting to the new ladder, with `_grade_pa` still reachable so every published number stays reproducible. Routing becomes: trade S, decide on A, skip C. `X` stops being a grade and becomes what it already means — the engine should not have fired. | red → green once P2 lands |
| **P5** | **Rename `LADDER_MODE`.** The exit ladder's modes are called `A` and `B`, which collide with grade letters in every table and conversation. Rename to something that cannot be read as a grade (`SCALE_PLAN` / `hod_then_runner`). Pure rename, no behaviour change. | green |
| **P6** | **Re-baseline everything on the new ladder.** Re-run the 2-year replay, the report, and G7 against S/A/C routing. Record which published figure moved and by how much (this is A2). | amber |

## Block 3 — the rules that barely fire

| phase | task | lane |
|---|---|---|
| **P7** | ~~**G1 — 84%-rule three-arm A/B**~~ **ANSWERED 2026-08-26** (`40fdadd3`, `research/p7_84_rule.md`): the gate, not the detector, is the bottleneck — 7 of 472 arming opportunities survive it, and opening it produces 116 re-entries worth +0.792R, below the book's own mean. Keep `RULE84_STRICT=1`. | done |
| **P8** | ~~**G2 — the dead scratch branch**~~ **DONE 2026-08-26** (`research/p8_scratch.md`): unreachable over **43,374 trades**, closest approach **+0.0001 bar-ranges**, zero crossings. The rule is a *live fill correction* (`Trading-Bot-Rulesets.md` clause 2) and the backtest already holds the information it exists to recover — `detect_break_retest`'s `no_confirm_close` return IS the scratch. Branch deleted, book byte-identical (0 of 45,175 rows differ). `ENTRY_SCRATCH=level` (default OFF) is the nearest expressible rule and costs **−107.06R**: it cuts 70 winners with 185 losses while win rate *rises* to 61.9% on the shrunken denominator. Keeper: bar-1 holds-the-level splits the book **+1.3097R vs −0.0844R**. | green |
| **P9** | **G3 — ON WATCH at 2-year scale.** Shipped and on by default, but only ever A/B'd over the 120 graded day-cards. Flip `ON_WATCH=0` against the full rig and report the delta in recall and mean R. | green |
| **P13** | **G10 — the 317 armings that never fired.** P7 opened the 84% gate to 433 armings and got 116 signals. Which of the six re-entry conditions kills the other 317 is unknown. Instrument the way `p7_84_rule.py` instrumented the arm gate. | green |
| **P14** | **G11 — clause 2's scratch in the LIVE path.** P8 proved the backtest cannot hold it. `paper_trader.py` marks on **wicks** and has no `scratch` outcome at all. Scope what an intrabar quote costs before writing anything. | green |

---

## Block 6 — rule ballot batch 02 (2026-08-27) — **the live block**

28 answers, `research/rule_ballot_batch02.jsonl`. Master spec:
`Desktop\loop\queue\omen-v6.1-grader-truth.md`. This is the first time Austin has put
numbers on the eight variables, and it broke two things and added five.

**Bug fixes — these run first.**

| phase | task | lane | ballot |
|---|---|---|---|
| **P15** | **`level_not_respected` — three faithful readings, all dead. STOPPED, nothing committed to the grader** (`8f5cb36b`, `research/p15_level_respect.md`). Committed form: trips 62.8% of the book, delta **+0.104R** — wrong sign. Wrong-side test on the flat 12-bar window: **+0.385R**, worse. Wrong-side test anchored on `_break_bar` (the way `no_displacement` / `stale_retest` / `break_then_rejection` / `no_retest` all are): trips **13 of 45,175, 0 of 1,016 traded** — degenerate. Selftest green at 400/0 each time, so the harness agrees on what is being computed; what is computed is a variable with nothing to find. **This is the fourth instance of the unreachable-rule class** — detection already requires the level to hold, so the post-break population has no violations left. See P25. | green | a1 a2 a3 |
| **P25** | **Is "the level" even the right anchor?** Every P15 attempt measured bars *after* the break against the trade's stop level. Austin's words — *"has to hold the level or candle period. chopping around is not respecting"* — may be about the level's **history before this setup**: a level price has already been chopping on is a bad level to break-and-retest, which is a property of the level, not of the entry. That is a different variable with a different anchor and it has never been built. **Ask him before building it** — three faithful readings have already failed and a fourth guess is not the answer. | red | a1 a3 |
| **P16** | **`htf_bias` has no author.** *"we dont have any higher timeframe bias yet youll need to tell me what that is then."* G4 puts **3,525 of 7,219** dropped S signals on this veto — the largest single killer in the engine — and nobody wrote the rule. `8797aee6` already found the facet was really "call vs put". Default: delete the veto, keep the value as a reported observation, hand Austin one paragraph and one number. | green→red | c6 |
| **P17** | **`STALE_BARS` 15 → 10.** Ratified: *"1m always needs fast happenstance… ill say 10."* Near-no-op (fires on 0.2%) — record it as ratified anyway. | green | b11 |

**New rules that were never coded.**

| phase | task | lane | ballot |
|---|---|---|---|
| **P18** | ~~**Variable 9 — the large counter body**~~ **DONE 2026-08-27** (`db439106`, `research/p18_p19_new_variables.md`, OFF via `ENABLE_LARGE_COUNTER_BODY`): **it does not discriminate.** Trips 57.2% of the book / 49.0% of cards, traded mean R **+0.968R tripped vs +0.939R clean — delta +0.029R, near-zero and wrong-signed for a downgrade.** Not the unreachable-branch failure P15 hit; the opposite — it fires on half of everything, close to `counter_trend_not_respected`'s 89.5%. Near-boundary check done first per the P15 lesson: containment excludes only 7.3%, so the containment clause is not what is blunting it. A finding for Austin, not a threshold to retune. | green | b6 |
| **P19** | ~~**Upgrade 2 — multi-level position confluence**~~ **DONE 2026-08-27** (`db439106`, OFF via `ENABLE_MULTI_LEVEL_CONFLUENCE`): **the first thing today that points the right way.** Six levels chosen **PDH, PDL, PMH, PML, ORH, ORL** — HOD/LOD excluded as tautologically on-side for a trade that already moved, T10 pivots excluded for having no fixed slot in a "5 of 6" count. Trips 23.9% of the book, money delta **+0.250R and right-signed** (+1.064R tripped n=582 vs +0.814R clean n=434). S count rises 129 → 147 at signal granularity. S > A > C ordering survives in every arm. **Capped at +1 total with BR+OCR — that cap is a choice, not a measurement.** See R8. | green | b5 |
| **P20** | ~~**The sequence gate**~~ **DONE 2026-08-27** (`73d3c903`, `research/p20_sequence_gate.md`, OFF via `ENABLE_SEQUENCE_GATE`): **correctly signed, and the first thing that cuts false fires.** 425 of the 1,016 traded signals (41.8%) are 2nd-or-later on their symbol-day; 3 are 84%-exempt. Traded mean R **+0.767R tripped (n=422) vs +1.092R clean (n=594), delta −0.325R.** Recall 12/28 → 8/28 but false fires **30/61 → 9/61** — that is the *opposite* of P15's distribution-lifting; this tightens. `NO_REPEAT_ENTRIES` was checked first per the P15 lesson and does **not** pre-empt it: it suppresses only symbol+direction+level matches, so most of the targeted population survives to `traded`. Second reading (fired-only, n=9) is too thin to trust and is reported as such. | green | b2 |
| **P21** | **Target availability gates the entry.** *"its about sizing for the mean 2rr, so if there are no other levels to target… harder to trade."* Is there a tracked level ≥2R away at entry? G7 and G9 both closed on *"the constraint is information at entry"* — **this is the first candidate for that information and it is the most valuable row on this board.** | amber | b4 |
| **P22** | ~~**The 11:00 boundary is manage-only**~~ **DONE 2026-08-27** (`8190951e`, `research/p22_1100_boundary.md`): the 11:00 half is clean — `ENTRY_CUTOFF` at `backtest_week.py:553,621`, zero entries at or after 11:00, latest 10:59. **The runner half is not.** See P24. | green | c7 |
| **P23** | ~~**The combination — nobody has run it.**~~ **DONE 2026-08-27** (`research/p23_combined_arms.py`/`.md`, all `ENABLE_*` flags stay `False`): **P20 alone wins, and stacking P19 on top of it dilutes rather than adds.** Five arms on the same 50/50 stratified hold-out (`p2_threshold_sweep.py`'s own split, imported not reimplemented), headline on HOLD: baseline gate −0.159 → P20-only **+0.046** (best on cards) and money-rig S mean R **+1.572R** (n=77, best on money too — the two rigs agree). P19+P20 together gives the *same* HOLD gate as P20 alone (+0.046, since P19's day-card marginal effect is zero — P18/P19's own finding), but on the money rig it pulls S n up to 91 while mean R drops to +1.469R: P19's extra +1 lets weaker signals back into the S tier alongside P20's cleaner set, exactly the overlapping-population interaction the ticket predicted. Adding P18 on top (P19+P20+P18) is worse on both rigs (HOLD gate +0.007, S n=57 at +1.337R) — P18's near-constant −1 does what a coarse downgrade does, it thins the S set without sorting it. S>A>C survives in every arm. **Read the win carefully before anyone acts on it** — P20's gate improvement is bought by cutting false fires 16/31 → 3/31 while S recall falls 5/14 → **2/14**. Two days. Ballot q20 settled that **recall governs** (complete engine misses of S trades matter more than tier accuracy), and the destination is ≥90% of his S-days — so on the gate that actually governs, the best arm here moves the *wrong way*. What it genuinely shows is that the S set P20 keeps is better (+1.572R on n=77 vs +1.313R on n=129), which is a precision result, not a recall one. TUNE picks a different best arm (P19+P20+P18 at +0.252) and that disagreement is reported, not averaged. | green | done |
| **P24** | **The shipped runner is 50%, Austin runs 10% — and it costs almost nothing.** `SCALE_PLAN="hod_then_runner_be"` splits 50% at the HOD / 50% runner (`backtest_week.py:475`); he says he manages *"a 10 percent position most of the time"*. **G7 already measured the alternative**: `30_30_30_10 / clock` (which leaves exactly a 10% runner) books **+0.955R** against the incumbent's **+0.957R** over the same 1,016 signals — a 0.002R difference. So this is a config mismatch between the default and his stated behaviour, **not** a measurement error, and it does not re-open the exit family. Worth noting the one place it points the other way: on the S subset `30_30_30_10` is **+1.357R vs +1.283R**, better by 0.074R on n=128 — matching his real sizing is mildly *better* on the set he would actually trade. Change the default to match what he does; do not expect a number from it. | green | c7 |

## Block 4 — exits, the one direction still open — **closed**

| phase | task | lane | state |
|---|---|---|---|
| **P10** | **G9 — structure trail + far-target scale-out.** G7 ruled out every mechanical trail (ATR14 / prior-bar, 5-bar consolidation exit) and showed `flat_5r` is the only policy the extra room helps. Untested: a tail riding to 4–5R behind a *structure* trail with no 11:00 clock, and partial exits at the far targets. | green | **done `6c3f880f`** — negative; `research/p10_structure_trail.md` |

## Block 5 — hygiene and validation

| phase | task | lane |
|---|---|---|
| **P11** | **G5 — corpus sweep.** Run `corpus_query.py` over every constant in `parameter_catalog_draft.md`; mark each CONFIRMED / CONTRADICTED / UNMENTIONED against what a trader actually said. The safest unattended lane in the project. | green |
| **P12** | **G6 — per-symbol sample floor.** COIN has 104 traded signals, SOFI and ACHR have 2. Suppress or grey sub-threshold rows so reports stop printing noise next to signal. | green |

## Needs Austin, always

| | |
|---|---|
| **R1** | Grade the outstanding deck / master homework. The only unrecoverable input in the project. |
| **R2** | Ratify or reject the S/A/C thresholds after P2. |
| **R4** | `INCLUDE_SPY_IN_BACKTEST` — SPY is 30 of his 120 graded symbol-days and excluded from `CORE_SYMBOLS`. |
| **R5** | **Max S trades per symbol: 2 or 3?** Ballot c3 says 2, c4 says 3 and then "cap at .8 s trades a day per symbol". P20 ships the downgrade and no cap until he picks. |
| **R6** | **What is higher-timeframe bias?** He says it does not exist yet. P16 measured it: the veto is blamed for 3,525 dropped S signals but lifting it frees only **60 (1.7%)** — mostly redundant, not mostly costly. Corpus verdict: the concept is CONFIRMED (his mentors teach HTF alignment), the SMA20-of-hourly formula is UNMENTIONED, his own ballot CONTRADICTS ownership. `HTF_BIAS_VETO` defaults ON so live behaviour is unchanged until he defines it or deletes it. |
| **R8** | **Do the +1s stack?** There are now two independent upgrades — BR+OCR confluence and P19's ≥5-of-6 levels. P19 capped the total at +1 because he has never been asked. If they stack, a setup with both goes S at two downgrades instead of one, and that is a routing change. |
| **R7** | **Re-freeze the forward clock.** `signal_runner.py` and `omen_bot.py` both moved in P16, so the guard now refuses to score against the `40949c6a` manifest. The book has **0 trades booked**, so re-freezing voids nothing — but `freeze --force` is the documented VOID operation and does not get run without him saying so. One word: re-freeze. |

---

## Block 7 — after T1 (2026-08-28) — **the live block**

T1 (`218a1c45`, `research/t1_entry_minute_autopsy.md`) refuted the hypothesis it was written
to test and the answer is better: over Austin's 34 fresh S days the engine is **never silent**
(0 of 34) and its timing on the 15 days it reaches his setup is **exact** (median +0.0 bars).
It finds the trade and grades it `X`. **The miss is grading, end to end** — so every phase in
this block is about what replaces `_grade_pa`, or about the fact that the live path does not
run this book at all.

Ordered cheapest-first by needle moved. Source: `Projects/omen-next-session.md`.

| phase | task | lane | moves |
|---|---|---|---|
| **P26** | **T1b — the targeted `X` lift.** Third independent confirmation that `_grade_pa`'s `X` veto is the recall killer: `g4_dropped_s` (7,219 of 7,485 S signals graded X and dropped), W1's arm table (`on_all` is the **only** arm that buys held-out recall, 6/15 vs 3/15, and pays with a **12.5×** book of 12,770 trades), and T1's 9-of-15. **Nobody has run the middle.** `on_all` lifts every veto indiscriminately; T1 says his S days are specifically `X`-graded **break-and-retest or one-candle-rule setups at a level, at the right minute**. Regrade only those. It is the only untried point on the curve between `off` and `on_all`. ~2 hr. | green | **recall** |
| **P27** | **T2 — reconcile `_tier()` with the backtest gate.** `live_scanner.py:546` promotes to TRADE only on `grade == "A+"`, which fires **twice in 45,193 signals**. The 1,017-trade book comes from `backtest_week`, a different gate. Under Austin's ladder `A+` reads as *"trade only S"* — right in spirit, wrong in reach, since the engine makes 2 S in two years. **Ship nothing else until the live path and the book trade the same set.** Note the 09:40 floor is a *backtest* constraint; live, the A+ gate kills everything before the floor is consulted. ~1 hr. | **red** | **real money — blocker** |
| **P28** | **T3 — the arrival-order ladder, and nobody has tried it.** W1's S/A/C ladder scored **44.1% held-out recall against the legacy 52.5%** and was shelved — but **968 of the 1,000 traded `B` rows are `B` only because of `_calibration_grade`'s first-with-trend-signal-of-the-day floor.** That is arrival order, not grade. W1's ladder threw arrival order away and kept only the downgrade count; the legacy grader keeps arrival order and has no downgrade count. **Test a ladder that keeps both.** Neither arm has been run, and it is the only untried hypothesis that could beat 52.5%. ~2 hr. | green | **recall** |
| **P29** | **T4 — drop the 09:40 `TRADE_FLOOR` in the backtest, re-score the 100 cards.** No longer a judgement call: the floor deletes **10 of his 34 S days (29%)**, 65% of his S entries land before 09:45, and `x8_time_blocks` already found 09:30–09:45 is the single best 15-minute block. Bounded and reversible. ~20 min. | green | **recall**, **money** |
| **P30** | **T6 — re-run the options tape ex-ante, plus the strike sweep.** T2's contract advantage was **90% look-ahead** (`drange` priced the premium at the entry minute). Every table in `research/t2_options_tape.md` is void until it is redone on prior-session sigma. His q24 0DTE/1DTE ATM±1 sweep lands here. This is also where the runner-exit question has to be answered, since the instrument is options, not shares — and the honest ceiling to beat is the **+1.4988R** contract read from the X board. | amber | **money** |
| **P31** | **P9/G3 still open — ON WATCH at 2-year scale.** Shipped ON by default, A/B'd only over the 120 graded day-cards, where it was +0 on every metric. It has never been flipped against the full rig. Cheap, and it is one of the few defaults nobody has priced. | green | hygiene |

**Needs Austin before it can run** (also in `Projects/omen-open-questions.md`):

| | |
|---|---|
| **R9** | **T5 — the ranker bottom-quartile filter.** +0.1568R, 23/25 months green, permutation P≈0.05%, **zero held-out recall cost** — the cheapest lever measured anywhere. It gets there by **removing 238 trades**, and he has asked for more trades, not fewer. His call, not an agent's. |
| **R10** | **`GOVERNOR_S_CAP` is an integer** and his answer was *".8 S trades a day per symbol"*, which an integer cannot express. |
| **R11** | **The −1.25R floor on contracts** — binds 4.3% of rows, caps the worst at −1.25R instead of −7.90R. |
| **R12** | **Order type** — parked by his q12, but T24 prices it at **+0.7386R of the +0.8341R book**. Most of the book's edge is sitting on an unanswered question. |

---

## Block 8 — decided 2026-08-28, nothing here is waiting on Austin

Two grilling rounds settled fourteen questions. Full record with his words:
`Austin's Vault/Projects/omen-rulebook.md`. These are the phases those answers create.

| phase | task | lane |
|---|---|---|
| **P32** | **The target is the next structural level, not 2x risk.** Every row in the book plans **exactly 2.000 R:R** — a hard cap at twice risk, set regardless of where the next real level sits, and the opposite of his own rulebook line b4. Since `mean R = wT − (1−w)`, a flat 2R target **cannot produce mean 2.0R at any human win rate**. This is the only change on the board that makes the money gate arithmetically reachable, and the room is on the tape already: 296 rows run past +2R, max +14.264R, mean MFE +4.0992R. Needs the level-availability check at entry, which is **P21 — now promoted from candidate to prerequisite.** | green |
| **P33** | **Delete `HTF_BIAS_VETO`.** It ships ON, gates **47.0% of the two-year book**, and has no author. Keep computing and reporting the value so it can be re-gated the day he defines the rule. Re-baseline everything it moves. | green |
| **P34** | **Delete the legacy letters.** `A+` / `A` / `B` / `X` come out of every report, label and gate — *"a+ and b shouldnt exist if they do."* **The routing switch does not move yet:** he chose fix-the-grader-first, because the S/A/C ladder measures **44.1% held-out recall against the legacy 52.5%**. Live routes on S the moment P26 or P28 beats 52.5%. | green |
| **P35** | **Ship the bottom-quartile filter ON** (`ranker[x13] >= p25`). +0.1568R, 23/25 months green, permutation P≈0.05%, zero held-out recall cost, and it drops the 25% of signals with the lowest premarket score — all four features computable at 09:29. Dropped rows book +0.44R, kept rows +1.11R. **Use T3's committed numbers; he explicitly asked for no new backtest to justify it.** | green |
| **P36** | **Order type is limit at the level, no chase.** Make the fill model say so explicitly instead of assuming it. T24 prices this at **+0.7386R of the +0.8341R book** — roughly 90% of the measured edge was riding on an unstated assumption. | green |
| **P37** | **Break-even slippage gets the initial stop's rule** — trigger on the close, fill at that close, so a BE exit can book a small loss instead of exactly zero. Retires the last unpriced assumption in the exit model. Expect it small (BE ends 20 of 1,017 trades); the point is that every runner figure was a ceiling until now. | green |
| **P38** | **Re-anchor `level_not_respected` on the level's history before the setup** — how the level behaved on prior touches, not how bars behaved after the break. All three failed implementations measured after. **If this one also fails, delete the variable** — it currently downgrades 62.7% of signals in the wrong direction, which corrupts every S/A/C grade the ladder produces. | green |
| **P39** | **The nine taken defaults**, each a small change with its reason recorded in the rulebook: C is alert-only · 84% tolerance = the one tolerance unit and `STRONG_PA_MULT` deleted · tight-stop gate applied to every grade before any retune · the `+1`s stay capped at +1 · `break_then_rejection` anchored on the session's first break · `STOP_TRIGGER_BUFFER_FRAC` stays 0 · the −1.25R floor binds on contracts · `GOVERNOR_S_CAP` deleted (**no per-day and no per-symbol cap — trade every S**) · card 11 counts as an OCR on the stop-usability test. | green |

**Out with him now:**

| | |
|---|---|
| **H1** | `research/probes/omen-x-vetoes.html` — 40 setups the engine found and refused, entry and stop drawn, one tap. Grades **P26's arm before it is built**. |
| **H2** | `research/probes/omen-test-2.html` — 97 unseen symbol-days, **88% engine-silent** against the S sweep's 50/50. The honest held-out recall sample; the 52.9% figure is measured on a deck that flatters it. |

---

## Settled, no longer open

- **The 09:30–11:00 window is correct.** The old "everything fires before 10:00" bug is
  gone: entries in the 2-year book run 09:35 → 10:59, 55.4% in the 09:30 half-hour, 44.6%
  after 10:00, 140 after 10:30. The 10:30 slot's 39.4% win rate is a *result*, not a bug.
- **Ladder B is not a grade.** It is `SCALE_PLAN` (`LADDER_MODE` before P5), the exit
  scale-out plan: 50% off at the first HOD/LOD after entry, stop to breakeven, runner to
  the next key level. The letter collision with grade B is a naming accident, fixed by
  P5 — the plan is now named `hod_then_runner_be` (was `"B"`).
- **Grades exist to route trades, and the downgrade system is the whole of it.** Grade =
  `S − (downgrades tripped) + (1 if confluence)`, floored at C. Nothing else feeds it.
- **Routing is settled** (ballot c5): *"we only trade S trades and im thinking A +1 (which
  is technically S)."* A-plus-confluence already scores S by the arithmetic, so there is
  nothing extra to build — P4 routes S and skips the rest.
- **Wicks are not evidence, closes are** (ballot a2, a3, b9). Third time this has been
  settled — once for stops, once for level respect, once for why wick-bearing candles are
  *preferred*: *"its not risk too wide but risk less predictable because i find trends
  respect candles with wicks better."*
- **Exhaustion is a filter, not an entry criterion** (ballot a7): *"this seems like a metric
  and has nothing to do with entering into trades. it sounds important to help rule out S
  trades automatically."* It stays a downgrade; it never becomes a trigger.
- **Earlier is better** (ballot c1): more volatility, trends easier to read. The 09:30 half
  hour carrying 55.4% of entries is the system working, not a clustering bug.
- **The eight-variable list is closed for now** (ballot a8), with the +1s Austin has already
  given riding on top of it.
