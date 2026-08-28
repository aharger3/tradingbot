# X10 — every open question in the repo and the vault, in one list

Swept 2026-08-28 at `c089b26b`. Measured by `research/x10_open_questions.py`
(`--selfcheck` green: 100 held-out cards, 935 judged symbol-days, 16 mark files).

**Headline: 34 items survive the sweep. 14 need Austin, 11 an agent can just run, 9 are
already answered somewhere and should be closed rather than asked — and the single
highest-leverage one is 60 ungraded cards, because W1's central refutation rests on the
59 he already did.**

The vault's `qa-queue.md` was verified 2026-08-28 and 11 of its 13 questions were already
answered in this repo. **None of those 11 are re-asked below.** They appear once, in
§4, so the next sweep does not resurrect them either.

---

## The four measured numbers this file publishes

Everything else here is provenance — which file answers which question. These four are
measurements, and `research/x10_open_questions.py` is the thing that made them.

| # | measurement | value |
|---|---|---|
| **M1** | `python research/regression_gate.py` at HEAD | **RED — 6 `s_grade` marks dropped** (`GOOGL 2024-10-15`, `IWM 2025-04-10`, `IWM 2025-12-01`, `IWM 2025-12-04`, `QQQ 2025-02-25`, `UBER 2025-09-11`) |
| **M2** | forward-clock freeze drift vs `research/omen6_frozen.json` (`40949c6a`, 2026-08-23) | **all 7 frozen files moved, 0 unchanged, 0 trades booked** |
| **M3** | SPY's claim on the held-out recall gate | **3 of 100 cards, and 0 of the 15 S days** |
| **M4** | SPY's claim on the whole judged corpus | **66 of 935 distinct judged symbol-days** (3rd behind TSLA 110, QQQ 72) |

M2 and M3 each change what an existing red-lane ticket is actually asking. See A2 and A4.

---

## 1. NEEDS AUSTIN — a judgement, a rule, or a contradiction between two things he said

Ranked by how much each unblocks. Every row names where the answer would live and
confirms it is not there.

### A1 · Grade the other 60 cards of the h2 3-lane deck *(this is R1, and it is now blocking a specific number)*

He graded **59** on 2026-08-28 (`research/marks/deck_marks_h2_3lane_2026-08-28.jsonl`,
59 rows, verified). W1 scored the S/A/C/X count-ladder against those 59 and got
**26/59 = 44.1% agreement against a 52.5% always-guess-`X` baseline** — a refutation of
the ladder. W1 §11 says in its own words: *"n=59 is small, and it is a FIRST READ …
every number in section 2 should be recomputed against 119 before anything is decided
on it."*

- **Answer would live:** a second `research/marks/deck_marks_h2_*` file. **Confirmed absent** — `deck_marks_h2_3lane_2026-08-28.jsonl` is the only one.
- **Instrument exists and is unopened:** `research/probes/omen-h2-3lane.html` (W7, shipped).
- **Default:** grade them. ~25 min. Nothing else on this list converts his time into a decided number as directly.

### A2 · The `C` floor — does 3-or-more downgrades floor at `C`, or die as `X`?

**A direct contradiction between two things he said, four days apart.**

| date | what he said | source |
|---|---|---|
| 2026-08-24 | 3+ downgrades **floors at C** | `Projects/omen-blockers.md`, "Already settled" table |
| 2026-08-28 | *"S A C grades are kept … revisit B trades and mold them into those grades or 'x' kill them"* | quoted in `research/w1_sac_ladder_ab.md` §1 |

`downgrade.score()` implements the floor; `signal_runner.SAC_TIER` implements the kill.
W1 §1, verbatim: **"If Austin meant the C floor to stand, the 3+ bucket becomes `C` and
most of the lost book comes back"** — the X reading takes the book from **1,017 → 48
traded rows**. One line of code either way.

- **Answer would live:** `Projects/omen-rulebook.md` or a ballot row. **Confirmed absent** — the rulebook carries the 2026-08-24 floor and has not been updated for the 2026-08-28 sentence.
- **Default:** the floor stands (`C`). The later sentence is about killing the letter `B`, not about re-flooring `C`, and reading it as a re-floor deletes 95.3% of the book on an inference.

### A3 · Is `C` tradeable, or alert-only?

Two live artefacts say opposite things, and both are code, not prose:

- `Specs/omen6-h2-master-spec.md` §1.2 — **`C` is tradeable.**
- `backtest_week.py:221-223` — `counted = status == "fired" and grade != "C"`, with the comment *"C is alert-only in live_scanner (SPEC2) — excluded from traded P&L"*.

A `C` also has to clear `_min_viable_stop` where a `B` does not, so this is not a
labelling question — it decides whether 331 rows exist. W12 finding 3 prices it at
**331 rows and 0.0857R of mean**.

- **Answer would live:** the rulebook's routing section. **Confirmed absent** — the rulebook says *"we only trade S trades and im thinking A +1"* (ballot c5), which settles S and A and is silent on C.
- **Default:** alert-only, as shipped. But say it out loud, because the spec currently contradicts the engine and W1 cannot be read cleanly until it does.

### A4 · R4 / Q12 — SPY back into the backtest universe *(reframed by M3, it is no longer a recall question)*

`universe.py:72` — `INCLUDE_SPY_IN_BACKTEST = False`, confirmed at HEAD.

**Measured this sweep:** SPY is **3 of the 100 held-out cards and 0 of the 15 held-out
S days** (M3). So flipping the flag **cannot move the held-out recall gate at all** —
the argument that has carried this ticket since 2026-08-22 (*"every recall number
ignores a quarter of your own judgements"*) is about the **in-sample** 120-card set, not
about the gate the project actually gates on. On the whole judged corpus SPY is 66 of
935 symbol-days (M4), real but third behind TSLA and QQQ.

What is genuinely at stake is money and durability re-baselining: every published pre-flip
figure moves, which is exactly why `DIRECTION.md` puts it in the red lane.

- **Answer would live:** `TASKS.md` R4 / qa-queue Q12. **Confirmed still open in both.**
- **Default:** flip it ON and re-baseline once. The cost is a day of number-churn; the benefit is that the 2-year book stops excluding a symbol he trades. **But note the recall argument is now dead**, so if the churn is unwelcome, leaving it off costs the gate nothing.

### A5 · R6 — what is higher-timeframe bias?

`omen_bot.py:29` — `HTF_BIAS_VETO` defaults **ON**, confirmed at HEAD. It gates **47.0%**
of the 2-year book (W12 finding 5) and it has no author: *"we dont have any higher
timeframe bias yet youll need to tell me what that is then."*

The case got much bigger on 2026-08-28. `research/w10_gate_autopsy.md` §6: lifting this
veto alone recovers **+40 of his 132 refused trading days** — more than the risk floor
(+35) — and it is the only arm in that report that produces a book which can actually be
sized. It is not free: **+1 held-out S day for +6 false fires**, and the book nearly
doubles while mean and median R both fall by 6–8× the narrow bar.

- **Answer would live:** a ballot row defining the formula, or a decision to delete. **Confirmed absent** — ballot batch 01 and 02 both contain his disavowal and no definition.
- **Default:** delete the veto and keep the value as a reported observation. That is P16's own recommendation and it is now backed by a second, larger measurement. It changes what the live scanner alerts on tomorrow morning, which is why it is his.

### A6 · The 84% reclaim tolerance, and `STRONG_PA_MULT = 1.5` which does NOT gate it

Two halves of one unowned rule. **CLARIFICATION:** `RULE84_LESSON=True` (line 104) short-circuits `_strong_pa` off the 84% code path entirely; the constant is used only in `_aplus_stack` (fires 2 times in 45,193 signals), never in the reclaim arming.

- **The tolerance:** he said *"as long as the close is not too far away from original entry"* and never gave the number. Ballot b01 q12–q15 settled everything else about the rule (re-entry of the price, close to reclaim, max two attempts, must match trend direction).
- **The constant:** `signal_runner.py:91` — `STRONG_PA_MULT = 1.5` is an unowned constant nobody stated. Its comment was corrected to clarify it is NOT the 84% rule gate.

- **Answer would live:** `research/rule_ballot_batch0{1,2}.jsonl`. **Confirmed absent** from both.
- **Default:** set the tolerance to the project's one tolerance unit — **25% of the previous candle's range** (`BAR_EXTREME_FRAC = 0.25`, `signal_runner.py:365`) — and leave `STRONG_PA_MULT` to `_aplus_stack` only.

### A7 · R8 (TASKS lane) — is a stop built from the entry bar's own extreme the stop he actually uses?

His 2026-08-28 *"out on that same close"* retired the wide error bar and closed the
timing half. The structural half is untouched: `signal_runner.intrabar_stop` derives the
stop **from the entry bar**, so the stop is not independent of the bar it is measured
against — **790 of 792 ambiguous rows are exactly this by construction** (P26/T3).

- **Answer would live:** a ballot row. **Confirmed absent.**
- **Default:** yes, it is the stop he uses — he places stops off the setup candle's extreme and has said so about OCR (*"would the candle be good to use as the stop?"*, card 11). Ratify it and the last piece of the intrabar file closes.

### A8 · The tight-stop gate — apply it to every grade, delete it, or retune `STOP_RANGE_MULT`?

W12 finding 1: `_min_viable_stop` **keeps rows worth +0.6188R and rejects rows worth
+1.0861R**, and it is consulted on `C` only — so it is both sign-backwards and applied
inconsistently. `STOP_RANGE_MULT = 0.75x` is another UNMENTIONED constant. W10 adds the
counterweight: lifting it *removes* 12 trades on the shipped route, because a tight `C`
that fires claims the level under `NO_REPEAT_ENTRIES` and blocks the entry behind it.

- **Answer would live:** a ballot row. **Confirmed absent.**
- **Default:** apply it to every grade (consistency first), then re-measure. Do not retune the constant in the same move — that is two changes wearing one flag.

### A9 · `level_not_respected` — is it a property of the level's history, not of the entry?

**Wrong-signed on 62.7% of the book** (W9: tripped +1.0046R vs clean +0.8711R) and the
single biggest driver of the `C` bucket. Three faithful readings have been implemented
and all three failed (P15). His words — *"has to hold the level or candle period.
chopping around is not respecting"* — may describe the level's history **before** the
setup, which is a different variable with a different anchor.

- **Answer would live:** a ballot row. **Confirmed absent.**
- **Default:** do not guess a fourth reading. Ask him one question: *before the break, or after?* Everything else follows from that.

### A10 · Card 11 — the OCR case he says he is conflicted on

`Projects/omen-rulebook.md` §"He is openly unresolved on one case", quoting him:
*"technically this has both BR OCR but the red candle is large and not very clear … the
wick ended up as the proper stop but i'm conflicted here and contradicting myself."*
The rulebook's own instruction: **"Do not code past this."**

- **Answer would live:** the next ballot, as its own question. **Confirmed absent** from batch 01 and 02.
- **Default:** the stop-usability test wins — if the candle is usable as the stop, it counts as an OCR. That is the rule he has stated three other times.

### A11 · Do the two `+1`s stack? *(PHASES.md R8 — note the number collision, see D6)*

Two independent upgrades now exist: BR+OCR confluence, and P19's `multi_level_confluence`
(≥5 of 6 levels). P19 **capped the total at +1 because he has never been asked**. If they
stack, a setup with both goes S at two downgrades instead of one — a routing change.

- **Answer would live:** a ballot row. **Confirmed absent.**
- **Default:** keep the cap at +1. Confluence is *"rare — under 1 in 5"* by his own answer; two simultaneous confluences should not be able to buy a grade back on their own.

### A12 · `break_then_rejection` — measured from the first break of the session?

W12 finding 2: the branch **cannot fire** as written (10 of 45,175, 0 traded) — the
fourth instance of the project's named unreachable-rule bug class. Anchoring it on the
session's first break instead makes it **40% of the book**. Those are two different rules,
not a threshold apart.

- **Answer would live:** a ballot row. **Confirmed absent.**
- **Default:** anchor on the session's first break. It matches the *"first retest is best, fresh level"* line already in the corpus, and a rule that trips 10 times in two years is not a rule.

### A13 · Should the 84% arm gate be re-keyed to `S`?

W12 finding 4: killing `B` takes the arm population **7 → 156** as a side effect.
`RULE84_ARM_SGRADE` already exists, default OFF. The rulebook line is *"you need an A+
entry"* — and `_grade_pa`'s `A+` is a different ladder from his.

- **Answer would live:** ballot / rulebook. **Confirmed absent** — the rulebook line predates the two-ladders correction.
- **Default:** re-key to `S`. Under his own ladder, `S` **is** the equivalent of A+, and `research/omen-2y-backtest.md` already says so.

### A14 · `STOP_TRIGGER_BUFFER_FRAC` — the unresolved 25%-candle reading

Ships at **0.0** (`research/exit_lab.py:62`, confirmed at HEAD). Vault issue 17 carries
this as unresolved: does a stop need the close to be one tolerance unit (25% of the
previous candle's range) **beyond** the level, or is any close beyond it enough?

- **Answer would live:** ballot b01 q1/q3 (which priced the stop's floor and its close-trigger). **Confirmed absent** — neither mentions a buffer.
- **Default:** keep it at 0. *"Close beyond"* is the rule he settled five times; adding a buffer is a fifth number nobody asked for.

---

## 2. DECIDABLE BY AGENT — the default, and what it would take to just run it

### D1 · Re-freeze the forward clock *(PHASES.md R7)*

**MEASURED (M2): all 7 frozen files have moved, 0 unchanged, and the book holds 0
trades.** `python research/omen6_forward.py score` prints *"REFUSING TO SCORE"* and names
`signal_runner.py`, `omen_bot.py`, `universe.py`, `research/exit_lab.py`. The forward
holdout — the project's one honest out-of-sample instrument — has been dead since P16
and is getting deader with every W commit.

- **Cost of re-freezing: exactly zero.** `freeze --force` VOIDS the book; the book is empty.
- **Default:** `python research/omen6_forward.py freeze --force`, then let it run.
- **Why it is still listed:** `CLAUDE.md` reserves `--force` for him by convention. It is one word, and the measured loss is 0 trades — the only reason not to run it is that the engine is still moving daily, in which case re-freeze **after** A2/A5 land, not before.

### D2 · Put the recall gate under a `verify:` so it cannot go red unnoticed again

**MEASURED (M1): `research/regression_gate.py` is RED at HEAD** — 6 `s_grade` marks
dropped. This is not new (W3 diagnosed it, `ENABLE_MIN_RISK_FILL_CLAMP` makes it exit 0
and ships OFF by Austin's call). What is new is that **nothing runs it**. It was red from
`5e3677ea` on 2026-08-11 to G12 on 2026-08-27 — 16 days — before anybody noticed.

- **Default:** add `verify: python research/regression_gate.py` semantics as a non-blocking reporter, or a test that asserts the dropped-mark set is exactly those 6. Flipping the flag stays Austin's.

### D3 · Re-align the 47 S-tier symbol-days stranded in `recovered_reviews.jsonl`

`research/marks/LEDGER.md` counts **47 S-tier symbol-days that exist only in
`recovered_reviews.jsonl`'s unmatched 135**, excluded for having no bar index. W4 calls
this *"the highest-value unclaimed job found on the way"* and notes it **needs zero new
grading**.

- **Watch the collision:** qa-queue **Q7** defaulted "no" to *re-verifying* the 47. That was about re-grading low-confidence rows. This is bar-index alignment on rows he already graded — different work, and Q7 does not block it.
- **Default:** do it. It is the only way to grow the S denominator without his time.

### D4 · Delete `research/W4-HANDOFF.md`

The file's own first line: *"The source-mining agent should read this and then DELETE
THIS FILE."* W4 is done and its finding is in `research/w4_recall_sources.md`.

### D5 · Re-scrape the Circle `a-setups` space with metadata

`circle_data/a-setups/posts.json` holds **652 further text+image pairs with no author and
no date**, so they cannot be tied to a session and were not nominated. W4: *"Re-scraping
that space with metadata is a cheap way to grow this list."* An untracked
`circle_rescrape.py` already exists in the working tree.

- **Default:** run it, dedupe through `build_deck.py::marked_card_ids()`, append to the 198.

### D6 · Reconcile the R-numbering — three tickets currently mean two things each

| number | `TASKS.md` says | `PHASES.md` says |
|---|---|---|
| **R6** | (absent) — but `research/p25_midcandle_entry.md` uses R6 for "instrument fix" | "what is higher-timeframe bias?" |
| **R8** | "the stop is derived from the entry bar's own extreme" | "do the +1s stack?" |
| R3 | present (downgrade grader) | **absent** |
| R5, R7 | **absent** | present |

`Projects/OMEN.md` adds a third state: *"R5/R7/R9 closed by the grill."* R7 is
**not** closed — M2 proves the freeze guard is refusing right now.

- **Default:** `TASKS.md` red lane becomes the single canonical list; `PHASES.md` links to it instead of restating it. Renumber nothing that already appears in a committed report.

### D7 · Correct `omen6_backtest_truth.md` §2 where it is quoted

W10 §6: *"'this is a detection problem, not a filter problem' does not survive this
sample."* On the 271 symbol-days of his own book the engine **sees 261/271 = 96%** and
takes 129/271 = 48% — detection is **7%** of the gap, grading is **93%**.

- **Default:** correct the sentence in place, in the W0 style (keep the old text, label it retired, point at W10).

### D8 · Recompute W1 §2 against 119 cards once A1 lands

Mechanical. `research/w1_ladder_vs_marks.py` already does it against 59.

### D9 · Close three items `DIRECTION.md` still carries as open

- *"ON WATCH has no A/B on the 2-year rig"* → **done**, `research/g3_onwatch_2y.md`: +0.1135R, 12× the narrow bar.
- *"the 317 that never fired are un-autopsied"* → **done**, `research/g10_arming_funnel.md`: `rr15` kills 92 of 318, replayed at +0.617R, below the book's own mean.
- *"the 84% rule… the detector remains unmeasured"* → same file, same answer.

### D10 · Measure the third ladder, or delete it

`signal_runner.py:363` — `HTF_OPPOSITION_VETO = "hard"`, **hardcoded, non-configurable**,
feeding `compute_austin_tier()`, a **third** S/A/C/X ladder in a project whose own
doctrine is *"two grade ladders, never mix."* Its own code comment says *"the one clause
Austin has not settled"* and *"T8 A/Bs it"* — and **`research/t8_verdict_measure.md`
does not exist** (confirmed). It is reported-only today and gates no trade.

- **Default:** delete `compute_austin_tier` or gate it behind a flag defaulting OFF, and say so in `DIRECTION.md`'s two-ladders table. A third ladder nobody reads is a fourth way to mix them.

### D11 · Price the "no cap" answer so R5 can be written down

Not a question for him — see §4, R5 is **answered three times over**. A3 already measured
that a per-symbol S cap is **structurally invisible** to a day-level recall metric
(byte-identical across {none, 1, 2, 3}). The job is documentation: write *"no cap"* into
`Projects/omen-rulebook.md` §"He contradicts himself on the S cap", and mark the ballot
row's `"conflict"` field resolved.

---

## 3. STALE — about code or a number that no longer exists

| item | why it is stale |
|---|---|
| `HANDOFF.md` (whole file) | A 2026-06-10 session note about DXLink quotes and a put-side sizer bug. Nothing in it is OMEN 6. It is the file `DIRECTION.md` tells agents to read third, and it has been superseded for 11 weeks. |
| `omen-blockers.md` §2 — *"no measured edge at any recall"*, **+0.0787R**, 905 trades, 6 of 13 months red | A2 established that **+0.0787R and +0.957R were never the same measurement** — that figure is the 12-month yfinance rig, not the 2-year archive. Quoting them side by side is the error A2 was written to stop. |
| `omen-blockers.md` §3 — *"28 S-days, three symbols"* | The held-out gate is now 100 cards across **27 symbols** with 15 S days (M3). The three-symbol framing predates OMEN Test 1. |
| `omen-blockers.md` §8 — *"Corpus B is stale"* | About `backtest_charts.json` predating the omen-3.7 label split. The 2-year book `research/g3_arm_ow1.json` replaced it as the substrate for every W report. |
| `omen-blockers.md` §9 — *"the engine only trades the first 26 minutes"* | **Fixed and settled.** `PHASES.md`: entries run 09:35 → 10:59, 55.4% in the opening half hour, 140 after 10:30. |
| `map.md` — *"whether the graded set is too narrow"* | Answered twice: Q8 settled the roster at 12 names, and the held-out set already spans 27 symbols. |
| `map.md` — *"the downgrade-variable list exists nowhere"* | The eight are closed (ballot a8) and W9 has measured every sign. |
| `DIRECTION.md` "Known open bugs" | 2 of its 5 bullets are struck through as answered and 2 more are answered by G3/G10 (D9). The section needs one pass, not five. |
| `Projects/OMEN.md` — *"R5/R7/R9 closed by the grill"* | R7 is not closed; M2 shows the freeze guard refusing at HEAD. |

---

## 4. ANSWERED ELSEWHERE — close these, do not ask them

The qa-queue's own verified table covers Q1–Q13; it is correct and is not restated. What
follows are the items **outside** that table which are still being carried as open
somewhere.

| carried as open in | the answer, and where it lives |
|---|---|
| `TASKS.md` R3 — *flip the downgrade grader?* | **Measured, and it is a no.** `research/r3_downgrade_grader_ab.md`: held-out S recall **3/15 in both arms — zero gain** — false fires 12/42 → 14/42, money −0.1289R (14× the narrow bar), S durability 23/25 → 21/25. W1 then refuted the ladder against his own 59 verdicts (44.1% vs a 52.5% baseline). The *decision* is his; the *measurement* is finished and should not be re-run. |
| `PHASES.md` R5 / rulebook §"He contradicts himself on the S cap" / batch-02 `"conflict"` field | **Answered three times, and the third answer wins.** c3 = 2, c4 = 3, then the 2026-08-27 grill: *"my cap is just the prediction, so why cap it?"* → **no cap.** A3 then proved a cap is structurally invisible to the recall metric. Nobody wrote it down — that is D11, a documentation job, not a question. |
| `map.md` — *"whether replacing `_grade_pa` with the downgrade count lifts recall"* | **It does not.** R3 (zero held-out gain) and W1 (44.1% agreement) both answer it, from opposite directions. |
| qa-queue Q7 — *re-verify the 47 extra S rows?* | **Superseded**, per the qa-queue's own table: W4 found 198 better-provenanced days. But the *bar-index alignment* of those 47 is live and unclaimed — D3. Do not conflate them. |
| `omen-blockers.md` §1 — *"the grader throws away 93%"* | Superseded by G4's branch attribution (7,219 dropped S, by gate) and again by W10 (grading = 93% of the gap on his own book). The claim survives; the number is two generations old. |
| `omen-blockers.md` §4 — *"OCR is defined but not built"* | Partly answered by G8: 29,815 detections re-labelled `br_ocr_confluence`, funnel published. The level-generator half is still unbuilt — that is a build ticket, not a question. |
| `map.md` — *"break-even fill slippage"* / qa-queue Q9 | **Largely dissolved.** Ballot b01 q1/q3 priced the stop (close beyond, floor −1.25R), the live wick bug was fixed at `76a15fce`, and W0 retired the wide bar. No separate haircut number is needed. |

---

## 5. What this sweep covered

**Repo:** `CLAUDE.md`, `DIRECTION.md`, `TASKS.md` (all lanes), `PHASES.md`, `HANDOFF.md`,
`Specs/omen6-h2-master-spec.md` (via `Desktop/specs/`), every `research/*.md` matching
`open question|unresolved|needs austin|not measured|not stated|no author|still open`,
and a `TODO|FIXME|XXX|HACK` grep over every `.py` / `.js` / `.html` outside
`.claude/worktrees` — **zero hits**, which is worth stating: the open questions in this
project live in prose, not in code comments.

**Vault:** `.scratch/omen-6/qa-queue.md`, `.scratch/omen-6/map.md` ("Not yet specified"),
all 19 files in `.scratch/omen-6/issues/`, `Projects/OMEN.md`,
`Projects/omen-blockers.md`, `Projects/omen-rulebook.md`, `Projects/omen-decks.md`,
`Projects/omen-2y-backtest.md`, `Projects/omen-corpus-wayfinder-survey.md`.

**Out of scope, deliberately:** `omen-corpus-wayfinder-survey.md`'s own open questions are
about the **corpus** repo (`research/open_questions.md`, `research/decisions_for_austin.md`
— **neither exists in tradingbot**, confirmed). They are a different project's queue and
are not folded in here.

## Provenance

Script: `research/x10_open_questions.py` (`--selfcheck` green). Commit: `c089b26b`.
Substrate for M3/M4: `research/marks/probe_omen_test1_2026-08-27.jsonl` and the 16 mark
corpora `CLAUDE.md` names. M1 shells out to `research/regression_gate.py`; M2 reads
`research/omen6_frozen.json`.

**One caveat carried honestly:** M4's S-day count (48) is a **floor, not the canonical
154** — grade lives under different keys across the corpora and this script reads only
`grade` and `answers.grade`. The SPY *symbol-day* count (66 of 935) does not depend on
grade parsing and is exact. **No default was changed, no flag was flipped, no mark file
was touched, and nothing was re-frozen.**
