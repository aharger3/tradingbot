# g215 -- precision, with all the stats (OMEN 10.0, V3)

Answers Austin, 2026-09-05: *"precision 18/59 does not have all the stats."* Replaces the single line in `CLAUDE.md`'s "Precision footnote" with numerator, denominator, a Wilson 95% interval on every proportion, both the unit that number was computed on and the fuller all-fires unit beside it, and every breakdown that was missing.

Book: `research\bt2y_trades_retest_on.json` (498 sessions, 2024-09-03 -> 2026-09-02, `RETEST_REQUIRED`=True).

Marks: `research/marks_pool.canonical_pool()` -- built on `build_deck.mark_sources()` + `build_deck._judgement_key()` + `grade_read.grade_opinions()` (nine spellings), per `research/marks/LEDGER.md`. Austin's ladder is S/A/C/none (legacy B kept separate, X folded into none as an engine refusal, never a day-level grade); the engine's own ladder, reported alongside, is A+/A/B/C/X -- the two are never averaged together anywhere in this report.

## Contested labels

**72 symbol-days** are graded more than once with disagreeing grades (bucketed S/A/B/C/none), spanning 354 opinion rows across corpora. Precision/recall below use `marks_pool`'s own best-grade-wins resolution (S > A > B > C > none/X) -- this count is reported separately so a resolved conflict is never mistaken for a clean read.

| symbol-day | raw grades | sources (truncated) | resolved to |
|---|---|---|---|
| AAPL_2024-03-28 | S/X | austin_marks_v7.jsonl,derived_marks_v2.jsonl | S |
| AAPL_2025-01-13 | A/S | austin_marks_v7.jsonl,derived_marks_v2.jsonl | S |
| AAPL_2025-09-09 | C/X | austin_marks_v7.jsonl | C |
| AMD_2024-11-11 | A/S | austin_marks_v7.jsonl,derived_marks_v2.jsonl | S |
| AMD_2025-06-05 | A/S | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | S |
| AMD_2026-05-14 | A/C/S/X | austin_marks_v7.jsonl,austin_verdicts.json,derived_marks_v1.... | S |
| AMZN_2026-04-10 | A/X | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | A |
| AMZN_2026-07-17 | A/C | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_04_gra... | A |
| COIN_2025-10-21 | C/S/X | austin_marks_v7.jsonl,austin_verdicts.json,derived_marks_v1.... | S |
| COIN_2026-03-04 | A/X | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | A |
| COIN_2026-04-09 | A/S | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | S |
| GOOGL_2024-10-15 | S/X | austin_marks_v7.jsonl,austin_verdicts.json,derived_marks_v1.... | S |
| GOOGL_2025-08-07 | S/X | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | S |
| HOOD_2026-05-19 | A/X | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | A |
| INTC_2025-02-27 | S/X | austin_marks_v7.jsonl,derived_marks_v2.jsonl | S |
| INTC_2025-06-05 | A/X | austin_marks_v7.jsonl,austin_verdicts.json,derived_marks_v1.... | A |
| IREN_2026-05-21 | A/S | austin_marks_v7.jsonl,blind_marks_all.jsonl,marks_clean.json... | S |
| IWM_2024-02-28 | A/S | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_03_reg... | S |
| IWM_2025-09-05 | A/S | austin_marks_v7.jsonl,austin_verdicts.json | S |
| IWM_2025-10-21 | A/S | austin_marks_v7.jsonl,austin_verdicts.json,mark_batch_02_gra... | S |

(52 more not shown)

## Unit 1 -- one-trade-a-day arm

The single size-gated pick, arrival order, across all symbols, per calendar day (`omen_metrics.first_of_day_arm`). This is the actual one trade a one-trade-a-day account would have taken that day.

### one-trade-a-day arm

- fired items: **498** across 498 sessions -> fires/day **1.0**
- **precision** (fired he graded S / fired he graded at all): **30.5% (18/59) [20.3-43.1]**
- **recall** (bar-backed S days engine fired on / all 347 bar-backed S days): **5.2% (18/347) [3.3-8.0]**

**His grade, among graded fires (S/A/C/none, legacy B kept separate):**

| his grade | n | graded total | share [95% CI] |
|---|---|---|---|
| A | 13 | 59 | 22.0% (13/59) [13.4-34.1] |
| C | 3 | 59 | 5.1% (3/59) [1.7-13.9] |
| S | 18 | 59 | 30.5% (18/59) [20.3-43.1] |
| none | 25 | 59 | 42.4% (25/59) [30.6-55.1] |

**Per symbol** (engine's own precision within that symbol; his grade S vs all graded):

| symbol | fired | precision [95% CI] |
|---|---|---|
| COIN | 36 | 20.0% (1/5) [3.6-62.4] |
| AVGO | 32 | 50.0% (2/4) [15.0-85.0] |
| HOOD | 30 | 0.0% (0/3) [0.0-56.1] |
| GOOGL | 27 | 60.0% (3/5) [23.1-88.2] |
| META | 26 | 0.0% (0/2) [0.0-65.8] |
| TSLA | 25 | 25.0% (1/4) [4.6-69.9] |
| AAPL | 24 | 100.0% (1/1) [20.7-100.0] |
| PLTR | 23 | 50.0% (1/2) [9.5-90.5] |
| CRM | 23 | 25.0% (1/4) [4.6-69.9] |
| AMZN | 22 | 66.7% (2/3) [20.8-93.9] |
| AMD | 22 | 33.3% (1/3) [6.1-79.2] |
| MU | 21 | n/a (0/0) |
| BABA | 21 | 100.0% (2/2) [34.2-100.0] |
| NVDA | 19 | 0.0% (0/2) [0.0-65.8] |
| INTC | 18 | 0.0% (0/1) [0.0-79.3] |
| MSFT | 17 | 0.0% (0/1) [0.0-79.3] |
| NFLX | 17 | n/a (0/0) |
| ORCL | 16 | 33.3% (1/3) [6.1-79.2] |
| IREN | 15 | 0.0% (0/2) [0.0-65.8] |
| IWM | 11 | 0.0% (0/1) [0.0-79.3] |
| UBER | 11 | 0.0% (0/2) [0.0-65.8] |
| SOFI | 11 | 40.0% (2/5) [11.8-76.9] |
| ACHR | 10 | n/a (0/0) |
| TSM | 8 | n/a (0/0) |
| QQQ | 6 | 0.0% (0/1) [0.0-79.3] |
| MARA | 4 | 0.0% (0/2) [0.0-65.8] |
| SPY | 2 | 0.0% (0/1) [0.0-79.3] |
| SPCX | 1 | n/a (0/0) |

**Per setup:**

| setup | fired | precision [95% CI] |
|---|---|---|
| BR+OCR | 335 | 28.1% (9/32) [15.6-45.4] |
| break-and-retest | 161 | 36.0% (9/25) [20.2-55.5] |
| one-candle-rule | 2 | 0.0% (0/2) [0.0-65.8] |

**Per engine grade (A+/A/B/C/X -- `signal_runner.py::_grade_pa`, NOT his ladder):**

| engine grade | fired | precision [95% CI] |
|---|---|---|
| B | 494 | 30.5% (18/59) [20.3-43.1] |
| A | 4 | n/a (0/0) |

## Unit 2 -- all-fires unit

Every (symbol, day) that produced at least one size-gated candidate surviving to `traded` or `halted` -- the full pool of symbol-days the engine surfaced, not collapsed to the day's single pick.

### all-fires unit

- fired items: **5136** across 498 sessions -> fires/day **10.313**
- **precision** (fired he graded S / fired he graded at all): **28.5% (169/592) [25.1-32.3]**
- **recall** (bar-backed S days engine fired on / all 347 bar-backed S days): **48.7% (169/347) [43.5-53.9]**

**His grade, among graded fires (S/A/C/none, legacy B kept separate):**

| his grade | n | graded total | share [95% CI] |
|---|---|---|---|
| A | 113 | 592 | 19.1% (113/592) [16.1-22.4] |
| B | 12 | 592 | 2.0% (12/592) [1.2-3.5] |
| C | 33 | 592 | 5.6% (33/592) [4.0-7.7] |
| S | 169 | 592 | 28.5% (169/592) [25.1-32.3] |
| none | 265 | 592 | 44.8% (265/592) [40.8-48.8] |

**Per symbol** (engine's own precision within that symbol; his grade S vs all graded):

| symbol | fired | precision [95% CI] |
|---|---|---|
| COIN | 312 | 21.9% (7/32) [11.0-38.8] |
| PLTR | 285 | 31.0% (13/42) [19.1-46.0] |
| TSLA | 284 | 24.0% (18/75) [15.8-34.8] |
| AVGO | 278 | 28.6% (8/28) [15.3-47.1] |
| MU | 272 | 34.6% (9/26) [19.4-53.8] |
| AMD | 270 | 21.7% (5/23) [9.7-41.9] |
| HOOD | 264 | 32.1% (9/28) [17.9-50.7] |
| NVDA | 260 | 20.7% (6/29) [9.8-38.4] |
| META | 245 | 16.7% (4/24) [6.7-35.9] |
| ORCL | 236 | 22.7% (5/22) [10.1-43.4] |
| GOOGL | 219 | 31.2% (5/16) [14.2-55.6] |
| AMZN | 217 | 33.3% (6/18) [16.3-56.3] |
| AAPL | 196 | 32.1% (9/28) [17.9-50.7] |
| NFLX | 184 | 17.6% (3/17) [6.2-41.0] |
| BABA | 182 | 40.0% (6/15) [19.8-64.3] |
| INTC | 177 | 31.6% (6/19) [15.4-54.0] |
| IWM | 171 | 50.0% (5/10) [23.7-76.3] |
| MSFT | 165 | 28.6% (6/21) [13.8-50.0] |
| IREN | 163 | 17.6% (3/17) [6.2-41.0] |
| CRM | 143 | 20.0% (4/20) [8.1-41.6] |
| TSM | 140 | 58.3% (7/12) [32.0-80.7] |
| UBER | 132 | 27.8% (5/18) [12.5-50.9] |
| SOFI | 99 | 37.5% (3/8) [13.7-69.4] |
| QQQ | 95 | 54.2% (13/24) [35.1-72.1] |
| MARA | 57 | 25.0% (3/12) [8.9-53.2] |
| ACHR | 34 | n/a (0/0) |
| SPY | 31 | 0.0% (0/2) [0.0-65.8] |
| SPCX | 25 | 16.7% (1/6) [3.0-56.4] |

**Per setup:**

| setup | fired | precision [95% CI] |
|---|---|---|
| BR+OCR | 3904 | 27.7% (123/444) [23.7-32.0] |
| break-and-retest | 1143 | 32.4% (44/136) [25.1-40.6] |
| one-candle-rule | 83 | 16.7% (2/12) [4.7-44.8] |
| other (84% re-entry) | 6 | n/a (0/0) |

**Per engine grade (A+/A/B/C/X -- `signal_runner.py::_grade_pa`, NOT his ladder):**

| engine grade | fired | precision [95% CI] |
|---|---|---|
| B | 5073 | 28.3% (164/579) [24.8-32.1] |
| A | 63 | 38.5% (5/13) [17.7-64.5] |

## Plain English

On the one trade a day he'd actually take (Unit 1), the engine's single pick landed on a day Austin graded 18 times out of 59 graded picks (30.5%, 95% interval 20.3-43.1), matching the previously-published 18/59 exactly -- that number was correct, just bare. Judged against every bar-backed S day he has ever marked (347 of them), that one-a-day pick only ever lands on the S day itself 5.2% of the time (18/347) -- one trade a day can only ever hit one symbol, so this recall number is structurally low and is not a fair recall read on the engine's detection, only on the one-a-day policy's choice. Widen to every symbol-day the engine actually surfaced as a real candidate (Unit 2, 5136 fired symbol-days), and precision reads 28.5% (169/592) while recall -- did the engine fire on the S day AT ALL, on any symbol -- reads 48.7% (169/347). Both units still sit under the 39.5% candidate-level figure in CLAUDE.md and nowhere near his bar; the gap this project is closing has not moved, this report only stops it from being described with one bare fraction.
