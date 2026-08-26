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
| G2 | Autopsy **scratch**: 5 of 1,016 outcomes. Check the T4(b) failed-entry scratch and the EOD scratch actually fire on the ladder-B path. | Scratch is one of the two management pieces we built and cannot see working. | a replay case where a failed entry bar scratches, asserted in a test |
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
