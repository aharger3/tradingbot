# TASKS — the queue

Rules of this file: one line per task, newest work at the top of its section, and
**nothing lands in Done without a commit hash and the number that moved**. Lanes are
defined in `DIRECTION.md` (green = run it unattended, amber = run it and flag it,
red = needs Austin).

---

## Green — unattended

| # | task | why it matters | check that proves it |
|---|---|---|---|
| G1 | **84%-rule A/B**: run the 2-year rig at `RULE84_STRICT=1` (today) vs `0` vs gated on `sgrade == "S"`. Diagnosis is already done (see below) — this is the measurement. | The strict gate is calibrated against the wrong ladder. Three arms, one table. | three runs, mean R + recall for each, committed next to the script |
| G2 | **Delete or fix the T4(b) entry-bar scratch** — it has never fired in 2 years (see Diagnosed). Decide whether the rule needs a wider trigger or the code is genuinely unreachable. | Dead code that looks like a working rule is worse than no rule. | a replay case that scratches, or the branch removed with the reason |
| G8 | **Add a BR+OCR confluence setup type.** `downgrade.has_confluence` already detects it; give it its own `SignalType` so it can be routed, graded and counted like any other setup. | Austin asked for it directly, and confluence is already worth +6.5pts of win rate. | confluence signals appear as their own row in every per-setup table |
| G3 | **ON WATCH A/B on the 2-year rig**, not just the 120 day-cards. Reuse `t61_onwatch_ab.py`'s flag switch against `backtest_2y.py`. | The other big management piece, unmeasured at scale. | two runs, one table, delta in recall and mean R |
| G4 | **One Candle Rule recall**: 4,389 detected → 67 traded. Re-grade with `downgrade.py` and report S/A/C on the dropped 4,322. | Second-biggest recall leak after B&R. | grade distribution + how many land on a marked entry |
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

**The legacy grader is wick shape at one level type (2026-08-26).** `omen_bot.py:171`
`_grade_pa`: first line returns `D` if the entry candle is not the trade's colour — a long
whose retest bar closes red is dropped with no reference to structure. Then `A+` = hammer
at a key level, `B` = large wick at a key level, and `at_key_level` is hardcoded to the
**opening-range** high/low, so a retest of PDH/PMH/a pivot is not "at a key level" to it.
6,040 of the 7,219 dropped S signals broke a non-OR level. Austin, unprompted: "the candle
doesn't have to be so specific — you're just looking for PA to support your thesis."

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

**The T4(b) entry-bar scratch is dead code (2026-08-26).** All 5 scratches in the two-year
book are EOD scratches (held 303-344 bars). The failed-entry-bar scratch has **never fired**:
it needs the entry bar to close back through the level, and the entry rule requires a close
*through* the level, so the branch is unreachable by construction. The rule Austin stated is
real; the implementation cannot express it.

**The 84% rule is gated on the wrong ladder (2026-08-26).** `RULE84_STRICT` defaults to
`1`, which arms a re-entry only off an `A+`/`A` original — the rulebook line *"you need an
A+ entry"*. But that line is **Austin's** vocabulary, and `_grade_pa`'s `A+` is a different
scale that fires on 17 of 1,016 traded signals. Over two years: **473 traded losses, 472 of
them on an arming setup, 7 survive the strict gate, 3 re-entries ever fired.** The strict
reading discards 98.5% of the rule's opportunities. Under Austin's own ladder the
equivalent of "A+" is **S**, which `downgrade.py` can now score for every signal. G1
measures all three arms; R2/R3 decide.

## Done

| date | task | commit | number that moved |
|---|---|---|---|
| 2026-08-26 | 2-year replay + interactive report, both grade ladders attached | `04a6e60f` + follow-up | first S/A/C-filterable book: 1,016 traded signals, mean R +0.957 vs the 2.0 gate |
| 2026-08-26 | G9 — structure trail + far-target tail (P10) | `6c3f880f` | nothing beats ladder B: best +0.914R whole book / +1.267R on S; new ceiling number — stop-respecting oracle +3.501R, incumbent captures 27.3% |
