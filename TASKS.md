# TASKS — the queue

Rules of this file: one line per task, newest work at the top of its section, and
**nothing lands in Done without a commit hash and the number that moved**. Lanes are
defined in `DIRECTION.md` (green = run it unattended, amber = run it and flag it,
red = needs Austin).

---

## Green — unattended

| # | task | why it matters | check that proves it |
|---|---|---|---|
| G10 | **Autopsy the 317 armings that never fired.** P7 opened the 84% gate and got 433 armings but only 116 signals; nobody knows which of the re-entry detector's conditions (reclaim close, candle colour, >20% off the day's extreme, >=1.5x remaining reward, before 11:00, 2-attempt cap) kills the other 317. Instrument them the way `research/p7_84_rule.py` instruments the arm gate. | The gate is settled; the detector is now the binding constraint on this rule. | a per-condition funnel over the 433 armings |
| G11 | **Clause 2's scratch in the LIVE path.** `Trading-Bot-Rulesets.md` clause 2 says an intrabar entry that closes back beyond the level scratches at that close and does not arm the 84% rule. P8 proved the backtest cannot hold it (it never takes that entry). `paper_trader.py` marks positions on **wicks** against `stock_stop` and has no `scratch` outcome at all, and `live_scanner.py` only reacts to `stop` / target. Obeying the rule live needs an intrabar quote, not a 1-minute bar — scope that first. | The one place the rule is real is the one place it is unimplemented. | a paper position that scratches and does not arm 84% |
| G3 | **ON WATCH A/B on the 2-year rig**, not just the 120 day-cards. Reuse `t61_onwatch_ab.py`'s flag switch against `backtest_2y.py`. | The other big management piece, unmeasured at scale. | two runs, one table, delta in recall and mean R |
| G5 | **Corpus sweep for unstated rules** we already coded. Run `corpus_query.py` over every constant in `parameter_catalog_draft.md`; mark each CONFIRMED / CONTRADICTED / UNMENTIONED. | Cheapest unattended lane; catches hallucinated rules. | an updated `hallucination-audit.md` with dates |
| G6 | **Per-symbol floor**: decide and implement a minimum-sample rule so reports stop printing GOOGL n=21 next to COIN n=104. | Half the per-symbol table is noise presented as signal. | reports suppress or grey sub-threshold rows |

## Amber — do it, then flag

| # | task | why it matters |
|---|---|---|
| A1 | Sweep `downgrade.py`'s eight thresholds against the 120 graded day-cards. Austin's corpus is 28 S / 27 A / 3 C; today's grader produces roughly 13% / 24% / 62%. | The distribution is the first evidence the guessed numbers are wrong. |
| A2 | Re-run every published OMEN figure on the 2-year rig and record which moved. | Several live numbers come from a 12-month yfinance run that no longer matches the engine. |

## Red — needs Austin

| # | task | the question only he answers |
|---|---|---|
| R1 | Grade the outstanding deck / master homework. | The only unrecoverable input in the project. |
| R2 | Ratify or reject the S/A/C thresholds after A1. | "Is this chart an S?" — nothing else can answer it. |
| R3 | Wire `downgrade.py` into detection and retire `_grade_pa`. | Trades change the day this lands. |
| R4 | `INCLUDE_SPY_IN_BACKTEST` — SPY is 30 of his 120 graded symbol-days but excluded from `CORE_SYMBOLS`. | Q12 in the Q&A queue, still open. |

---

## Diagnosed, awaiting a decision

**G9 answered, and the answer is no again (2026-08-26).** `research/p10_structure_trail.md`:
14 structure-trail policies x two clock arms over the same 1,016 signals. Longs ride while
1-minute structure holds and exit on a CLOSE below the last confirmed swing low (the
`omen_bot.py::MarketStructure` fractal). **Nothing beats the incumbent** — best whole book
+0.914R vs ladder B's +0.957R, best on S +1.267R vs +1.283R. Weight taken at the HOD rung
beats weight left on the trail monotonically (+0.897 → +0.906 → +0.914, pure trail +0.827),
4R/5R partials subtract, and the noclock arm is worse for every variant. **The new number is
the ceiling**: a stop-respecting hindsight oracle returns **+3.501R** inside the 11:00
window, so 2.0R of room exists and the incumbent captures 27.3% of it. The 473 losing
signals average +0.647R of oracle and 33.8% offered +1R or better before dying — winners and
losers are not separable from price alone. The exit family is closed; the constraint is
information at entry.

**G7 answered, and the answer is no (2026-08-26).** `research/g7_exit_sweep.md`: eight exit
policies x two clock arms over all 1,016 traded signals. **Nothing reaches 2.0R.** Best on
the whole book is `30_30_30_10` at +0.955R against the incumbent ladder-B's +0.957R — the
incumbent is already the top of this family. Best on S is `flat_5r / noclock` at +1.383R
against +1.283R, +0.10R on n=128, inside the noise. Two structural reads: removing the
11:00 force-flat makes **every trailing policy worse** (the trail gives back more after
11:00 than it captures), and mean R rises monotonically with a fixed target
(1R +0.506 → 5R +0.913) without ever catching the scale-out ladder, while win rate falls
77.3% → 39.8%. **The exit is not the binding constraint; entry selection is.** What was not
tested is in the report and became G9.

**The legacy grader is wick shape, and it is not even the selector (2026-08-26, G4).**
`research/g4_dropped_s.md` attributes all 7,219 dropped S signals to the gate that
actually rejected them, by re-running `_grade_pa` over each entry bar in an instrumented
replay: **HTF bias opposed 3,525 · colour gate 2,120 · B&R min-stop 1,385 · OCR min-stop
153 · OCR wide-stop 21 · join collisions 15.** Only two of those are the grader. 303 rows
fail on the colour line *and nothing else*; delete that one `if` and 142 of them reach the
tradeable `B` tier. Austin, unprompted: "the candle doesn't have to be so specific —
you're just looking for PA to support your thesis."

**Correction carried by this ticket:** an earlier note here claimed `at_key_level` was
hardcoded to the opening range, so a PDH/PMH/pivot retest was invisible to the grader.
**That is false** — every `grade_trade` call site passes the level the setup actually
broke; the parameter is merely still *named* `or_high`. `research/t62_veto_autopsy.md`
corrected this on 2026-08-23 and G4 reproduces it: OR levels drop at 96.6%, everything
else at 96.4%, a 0.1-point gap. The 6,040-of-7,219 non-OR figure is real but is coverage,
not blame.

**And the grader is not what picks the trades.** 968 of the 1,016 traded signals (95.3%)
are `B` only because of `_calibration_grade`'s *first with-trend signal of the day, inside
90 minutes* floor. `_grade_pa` is effectively binary — `C` (alert) or `X` (silent) — and
the engine's real entry rule is arrival order. G7 said the exit is not the binding
constraint; G4 says the grade ladder is not either.

**The S supply is 58x bigger than the book (2026-08-26).** Over two years the downgrade
grader scores **7,485 signals as S**. The engine trades **128** of them. The other 7,225
are graded `X` by `_grade_pa` and dropped — 96.5% of Austin's S setups thrown away by a
candle-shape test. Split: 6,200 B&R, 1,025 OCR. This is the recall gate in one number, and
it says the shortage of S trades is a **grading** problem, not a market problem. Caveat
before anyone reads 7,485 as 7,485 trades: `NO_REPEAT_ENTRIES` scoping and the guessed
thresholds in `downgrade.py` (A1) both cut that number, probably hard.

**The 2.0R money gate is a runner problem, not a stop problem (2026-08-26).** Current book:
538 wins averaging **+2.669R** (median 2.193, max 14.26) against 473 losses at −1R. Mean R
+0.957. Solve `W x A - (1-W) = 2` on that book: at today's 53.2% win rate wins must average
**+4.64R**; at the S-grade 66.4% win rate they must average **+4.52R**. Capping losses
tighter than −1R cannot close the gap — there is no −1.25R tail to trim, the worst traded
outcome in two years is −1.000R. Austin called this before the arithmetic did.
`research/exit_lab.py` forces flat at 11:00 ET, which is the first thing to A/B (G7).

**G2 answered: the branch is deleted, and the rule is not backtestable (2026-08-26).**
`7979a61e`, `research/p8_scratch.md`. Instrumented over **43,374 created trades**: the entry bar's
close is on the good side of `sig["stop"]` and of the retested level **every single time**,
closest approach **+0.0001 bar-ranges**, zero crossings. It is not a threshold wanting
widening — the condition is consumed upstream, the same shape as `break_then_rejection` in
`research/p2_threshold_sweep.md`. **Why:** `Trading-Bot-Rulesets.md` clause 2 states the
rule as a *live fill correction* — Austin commits mid-candle without knowing the close and
scratches when the guess is wrong. The backtest never makes that guess: it reads bar `i`
complete, requires a close through the level, and only then back-dates the fill via
`fill_price`. `detect_break_retest`'s `no_confirm_close` return IS the scratch, taken
before the fill instead of after it. Branch deleted; the book is **byte-identical**
(0 of 45,175 rows differ across 15 fields), which is itself the proof it never fired.
**The nearest expressible rule was built and measured**: `ENTRY_SCRATCH=level` (default
OFF) scratches when the bar AFTER entry closes back through the retested level. It costs
**−107.06R** (+972.38 → +865.32, mean +0.9571 → +0.8517) because it cuts **70 eventual
winners** with the 185 losses, while the printed win rate *rises* 8.7 pts (53.2% → 61.9%)
purely on the shrunken denominator. Keep it off. **The keeper finding:** whether the bar
after entry holds the level splits the book **+1.3097R (n=759) vs −0.0844R (n=257)** — a
1.39R spread, sharper than anything the grader does, though only knowable one bar late.
Also queued: nothing in the LIVE path implements the rule either — `paper_trader.py` marks
on wicks and has no scratch outcome at all, and obeying clause 2 there needs an intrabar
quote, not a 1-minute bar.

**G1 answered: the gate is the bottleneck, and opening it buys nothing (2026-08-26).**
`research/p7_84_rule.md`: three arms of the arming gate over the 500-session replay.
Funnel, counted stop-outs -> arming setup -> grade gate -> before 11:00 -> signal:
strict **473 -> 472 -> 7 -> 5 -> 3**, loose **521 -> 472 -> 472 -> 433 -> 116**,
S-grade **477 -> 472 -> 43 -> 39 -> 12**. So the rule is dead in backtest because of
the GATE, not the detector — 7 of 472 opportunities survive it. The non-84% book is
identical to the cent in all three arms (1,013 trades, +966.17R), so every delta is
the re-entries alone. Whole book: strict +0.957R / 53.2% / 23-of-25 months green,
loose +0.942R / 52.1% / 25-of-25, S-grade +0.947R / 53.0% / 23-of-25. **Keep
`RULE84_STRICT=1`.** The loose re-entries are positive (+0.792R, n=79) but below the
book's own mean so they dilute; median −1.000R, 49 of 79 lose; and the 25/25
durability headline is one trade deep — drop the best re-entry from 2025-06 and it is
red again. The S arm is the worst (−0.073R) on n=7, a sample-size result rather than a
verdict on Austin's ladder. P11 row A8 agrees independently from the corpus side, and
it contradicts the LOOSE arm, not the shipped one. Next bottleneck is the detector:
433 armings produced 116 signals, and the 317 that never fired are un-autopsied.

## Done

| date | task | commit | number that moved |
|---|---|---|---|
| 2026-08-26 | G8 — BR+OCR confluence as its own setup type (P3) | `b55bd9c9` | 29,815 of 45,175 detections re-labelled `br_ocr_confluence`; book identical to the cent (1,016 traded / 52.95% / +0.9571R / +972.38R). Funnel detection → grade → traded: B&R alone 13,546 → 828 → 391 (50.1%, +0.888R) · OCR alone 1,811 → 70 → 16 (18.8%, −0.315R) · confluence 29,815 → 1,353 → 606 (55.6%, +1.030R) |
| 2026-08-26 | P5 — rename `LADDER_MODE` to `SCALE_PLAN` (`"A"`/`"B"` -> `"hod_then_runner"`/`"hod_then_runner_be"`); `OMEN_LADDER_MODE` kept as a deprecated alias | `d981ec2f` | none — pure rename; 45-day smoke replay produced byte-identical trades under the old env var and the new default |
| 2026-08-26 | G4 — what the legacy grader throws away, by branch | `d8b04625` | 7,219 dropped S attributed: bias 3,525 / colour 2,120 / B&R min-stop 1,385 / OCR 174; 303 fail on the colour line alone, 142 of those reach tradeable B; dropped-set expectancy n=588 +0.465R vs book +0.957R; 968 of 1,016 trades are B only from the first-of-day floor |
| 2026-08-26 | G1 — 84%-rule three-arm A/B (P7) | `40fdadd3` | 84% re-entries 3 -> 116 (loose) / 12 (S) fired; book mean R +0.957 -> +0.942 / +0.947; recommendation: no change |
| 2026-08-26 | 2-year replay + interactive report, both grade ladders attached | `04a6e60f` + follow-up | first S/A/C-filterable book: 1,016 traded signals, mean R +0.957 vs the 2.0 gate |
| 2026-08-26 | G9 — structure trail + far-target tail (P10) | `6c3f880f` | nothing beats ladder B: best +0.914R whole book / +1.267R on S; new ceiling number — stop-respecting oracle +3.501R, incumbent captures 27.3% |
