# V3 referee — precision with all the stats

**Builder commit: `b5267e46`** (row V3, `research/g215_precision.py`).
Referee code: `research/v3_referee.py`. Referee ran at HEAD `b5267e46`, which is
`origin/main`; `git merge-base --is-ancestor 1539dd7f HEAD` succeeded.

**Verdict: UPHELD.** Every published number reproduces exactly from independent
code that never imports `g215_precision.py` or `marks_pool.py`. Three
documentation defects are recorded below; none of them moves a number.

---

## What I re-derived, and how

`research/v3_referee.py` reads the mark corpora through the two canonical
readers the row names — `build_deck.mark_sources()/_rows()/_judgement_key()`
and `grade_read.grade_opinions()` — then applies its **own** best-grade-wins
resolution, its **own** first-of-day size-gated pick over the book, its **own**
`data_archive/<SYM>/<DATE>.csv` bar-backed test, and its **own** closed-form
Wilson interval. It does not call the builder's script, its pool module, or
`omen_metrics.first_of_day_arm`.

Book: `research/bt2y_trades_retest_on.json`, 498 sessions, 2024-09-03 →
2026-09-02, `RETEST_REQUIRED=True` per its own stamp. Honest fill (the bar
close is the fill in this book), shipped exits.

| cell | builder | referee | match |
|---|---|---|---|
| judged symbol-days (`marked_card_ids`) | 1323 | 1323 | yes |
| graded symbol-days after resolution | 1269 | 1269 | yes |
| bar-backed S days | 347 | 347 | yes |
| contested symbol-days / opinion rows | 72 / 354 | 72 / 354 | yes |
| unit 1 (one-trade-a-day pick) precision | 30.5% (18/59) [20.3–43.1] | 30.5% (18/59) [20.3–43.1] | yes |
| unit 1 recall | 5.2% (18/347) [3.3–8.0] | 5.2% (18/347) [3.3–8.0] | yes |
| unit 1 fires/day | 1.0 | 1.000 | yes |
| unit 2 (all-fires) precision | 28.5% (169/592) [25.1–32.3] | 28.5% (169/592) [25.1–32.3] | yes |
| unit 2 recall | 48.7% (169/347) [43.5–53.9] | 48.7% (169/347) [43.5–53.9] | yes |
| unit 2 fires/day | 10.313 | 10.313 | yes |

**Wilson checked by hand** for 18/59: p = 0.305085, centre = p + z²/2n =
0.337639, margin = z·√(p(1−p)/n + z²/4n²) = 0.121916, denominator = 1 + z²/n =
1.065109 → [20.254, 43.146] → **[20.3, 43.1]**. The builder's interval is
correct and is a Wilson score interval, not a normal approximation.

## Two sensitivities the builder did not run

- **Drop the ninth grade spelling** (`answers.is_s`, added by `marks_pool` on
  top of `grade_read`'s eight): unit-1 precision reads **29.3% (17/58)
  [19.2–42.0]**. One card, inside the interval. The headline does not hang on
  that spelling.
- **Drop `research/derived_marks_v*.jsonl`** (CLAUDE.md: "derived, low
  confidence"; best-grade-wins lets one of those rows override an
  `austin_marks_v7` X — e.g. `AAPL_2024-03-28` S/X → S): **nothing moves.**
  Bar-backed S stays 347, unit 1 stays 18/59, unit 2 stays 169/592. The S pool
  is not propped up by the derived corpora.

## Required checks

| check | result |
|---|---|
| Ladders never mixed | **pass.** Austin's S/A/C/none comes only from `grade_read`; the engine's A+/A/B/C/X comes only from the book's `grade` field. The per-engine-grade table is a cross-tab (engine bucket → his-S share), never an average of the two, and every such table is headed "NOT his ladder". `downgrade.sgrade` — the third ladder — is not read at all. |
| Script writes nothing under a mark path | **pass.** The only write-mode opens in `g215_precision.py` are lines 629 (`g215_precision.md`) and 648 (`g215_precision.json`). All mark reads are read-mode. `git status` after two runs shows no mark file, deck HTML or manifest touched. |
| CLAUDE.md diff touches only the footnote | **pass.** The diff (in `3c8e586d`) replaces lines 44–50 of the "Precision footnote" paragraph and nothing else in the file. The mandated sentence "Lane precision is the pick-level number — the bar is materially above 30.5% on the pick" survives verbatim. |
| No mark file changed | **pass.** `git show --stat` on both `3c8e586d` and `b5267e46` lists no `research/*marks*.jsonl`, no `research/marks/**`, no `mark_batch_*`, no `austin_verdicts.json`, no deck manifest. |
| Stamped books | **N/A.** The row writes no book. The book it reads carries a stamp and the report prints its flag value. |
| Every dollar names its fill/exit/unit/script | **vacuous pass.** The report contains no dollar figure. See defect C. |
| Sample-size rule | **partial.** See defect A. |
| Verify gate at `b5267e46` | **green, run by me.** `regression_gate.py` PASS (no baseline-fired mark went silent), `test_runner_stop.py` 70 checks ok, `test_universe_single_source.py` 29 symbols / no private lists. Tree at run time held one unrelated dirty file (`research/g210_fill_arms_v2.py`, another agent's) and my untracked referee script. |
| One change per row | **not verifiable from the row's own commit.** See defect D. |

## Defects (none change a number)

**A — sample-size labelling is applied only to the headline, not the
breakdowns.** `MIN_CELL_FOR_VERDICT = 5` is checked once, in `_unit_md`
(`g215_precision.py:427-430`), against the unit-level precision denominator. The
per-symbol, per-setup and per-engine-grade tables print every cell unlabelled,
including `AAPL 100.0% (1/1) [20.7-100.0]`, `BABA 100.0% (2/2)` and
`MSFT 0.0% (0/1)`. Every cell does carry its count and its interval, which is
most of what the rule asks; the missing half is the words "not enough" on a cell
that cannot carry a verdict. Twenty-seven of the twenty-eight per-symbol rows in
unit 1 sit under 30.

**B — the Plain English section makes exactly the cross-unit comparison the
report exists to stop.** `g215_precision.py:558-560` writes "Both units still
sit under the 39.5% candidate-level figure in CLAUDE.md". 39.5% is
candidate-level; 30.5% is pick-level and 28.5% is symbol-day-level. The
report's own opening paragraph and CLAUDE.md's footnote both say those units are
not the same scale. This sentence is in the part Austin reads.

**C — the Plain English section drops the word that carries the meaning.**
`g215_precision.py:548-551` reads "the engine's single pick landed on a day
Austin graded 18 times out of 59 graded picks", which parses as *graded at all*
rather than *graded S*. The number is right; the sentence describes a different
statistic. The same section names its book but never names its fill.

**D — the row's substance is not in the row's commit.** `b5267e46`, the hash
the builder reported, contains one `.gitignore` line and the untracking of
`g215_precision.json`. The actual deliverable — `g215_precision.py`,
`g215_precision.md`, the `daily_run.cmd` block and the CLAUDE.md footnote —
landed in `3c8e586d`, a `wip: auto-commit` that also bundled H1's
`daily_homework.py` change, H2's `g210_fill_arms_v2.{py,md}` plus twelve
`research/tape/fillarms_*.json.gz` books, and V1's `premarket_list_run.cmd`.
The auto-commit hook did this, not the builder, and V3's own content is one
coherent change. But no single commit isolates it, so "one change per row"
cannot be read off the history.

## Reproduction

    python research/v3_referee.py

Runtime ~40 s (dominated by reading every mark corpus twice more for the
sensitivities). `python research/g215_precision.py` regenerates the builder's
report in ~5 s and produced a byte-identical `g215_precision.md` to the one
committed — no drift between the committed report and the committed script.

---

# V3 referee — pass 2 (different model, told to refute)

**Builder commit: `b5267e46`** (substance in `3c8e586d`, see defect D above).
Pass-2 referee code: `research/v3_referee_pass2.py` and
`research/v3_referee_pass2b.py`. Ran at HEAD `ccd7fa06` = `origin/main`;
`git merge-base --is-ancestor 1539dd7f HEAD` succeeded and `b5267e46` is an
ancestor of HEAD.

**Verdict: UPHELD.** Every headline cell reproduces exactly under code that
shares no path with the builder's — pass 2 reads the corpora only through
`build_deck.mark_sources()/_rows()/_judgement_key()` and
`grade_read.grade_opinions()`, and re-implements the ninth spelling, the
cross-corpus resolution, the size gate, the first-of-day pick, the all-fires
reduction and the Wilson interval from their definitions. It never imports
`g215_precision.py`, `marks_pool.py` or `omen_metrics.py`.

Two new defects (E, F) are recorded. Neither makes a published number wrong
under the report's own stated definitions, and neither moves a decision:
every alternative sits inside the published interval. Both are undisclosed
denominator conventions on cells that are now law in `CLAUDE.md`.

## Independent re-derivation

| cell | published | pass-2 | match |
|---|---|---|---|
| judged symbol-days (`marked_card_ids`) | 1323 | 1323 | yes |
| graded pool after resolution | 1269 | 1269 | yes |
| S days total / bar-backed S | — / 347 | 349 / 347 | yes |
| contested symbol-days / opinion rows | 72 / 354 | 72 / 354 | yes |
| unit 1 precision | 30.5% (18/59) [20.3–43.1] | 30.5% (18/59) [20.3–43.1] | yes |
| unit 1 recall | 5.2% (18/347) [3.3–8.0] | 5.2% (18/347) [3.3–8.0] | yes |
| unit 1 fires/day | 1.0 | 1.000 (498 picks / 498 sessions) | yes |
| unit 2 precision | 28.5% (169/592) [25.1–32.3] | 28.5% (169/592) [25.1–32.3] | yes |
| unit 2 recall | 48.7% (169/347) [43.5–53.9] | 48.7% (169/347) [43.5–53.9] | yes |
| unit 2 fires/day | 10.313 | 10.313 (5136 / 498) | yes |

Book: `research/bt2y_trades_retest_on.json`, 498 sessions, 2024-09-03 →
2026-09-02, `RETEST_REQUIRED=True` from its own stamp. Honest fill (the bar
close is the fill in this book), shipped scale-out/trail exit.

**Wilson by hand, 18/59** (pass 2's own arithmetic, printed by the script):
p = 0.305085, centre = p + z²/2n = 0.337639, margin = z·√(p(1−p)/n + z²/4n²) =
0.121916, denominator = 1 + z²/n = 1.065109 → [20.254, 43.146] → **[20.3,
43.1]**. Confirmed a Wilson score interval, not a normal approximation.

All 59 graded unit-1 picks are enumerated by
`python research/v3_referee_pass2.py`, so the 18 S cells can be counted by eye.

**Ninth-spelling sensitivity, re-run independently:** dropping `answers.is_s`
gives unit 1 **29.3% (17/58) [19.2–42.0]** and unit 2 **27.0% (153/566)
[23.5–30.8]**, bar-backed S 347 → 323. Matches pass 1's unit-1 figure; the
headline does not hang on that spelling.

## Defect E — X-only symbol-days sit in the precision denominator, undisclosed

`marks_pool`'s own docstring calls X *"a refusal AIMED AT THE ENGINE — 'this
specific detection was wrong' — not a day-level 'I would not trade this'"*, and
`CLAUDE.md` says flatly **"`X` is not a grade"**. `g215_precision.md` repeats
this: X is *"folded into none as an engine refusal, never a day-level grade"*.
It then counts those symbol-days as **graded-and-not-S** in the precision
denominator.

| unit | X-only cells in the denominator | as published | X-only dropped |
|---|---:|---|---|
| unit 1, one-a-day | 7 of 59 | 30.5% (18/59) [20.3–43.1] | **34.6% (18/52) [23.2–48.2]** |
| unit 2, all-fires | 91 of 592 | 28.5% (169/592) [25.1–32.3] | **33.7% (169/501) [29.7–38.0]** |

Including them is defensible — at the pick level an X *is* "the engine should
not have fired here", which is exactly a false positive. That is probably the
right convention. But it is the opposite of the sentence the report prints two
paragraphs earlier, it is worth 4.1 points on the number `CLAUDE.md` now names
as the lane bar, and the report runs no sensitivity on it. Every alternative
lies inside the published interval, so **no verdict moves**; the fix is one
disclosure line and one extra row, not a new number.

Reproduce: `python research/v3_referee_pass2b.py`.

## Defect F — the recall denominator is not scoped to the book

Recall is published as *"did the engine fire on the S day at all"* over **all
347 bar-backed S symbol-days**. 37 of those 347 are days the engine could not
have fired on at any setting, because the book does not contain them:

| bar-backed S days | count |
|---|---:|
| all | 347 |
| inside the book window 2024-09-03..2026-09-02 | 321 |
| on one of the 28 symbols the book covers | 336 |
| **on a session the book actually contains** | **310** |

| recall | published | scoped to reachable days |
|---|---|---|
| unit 2, all-fires | 48.7% (169/347) [43.5–53.9] | **54.5% (169/310) [49.0–60.0]** |
| unit 1, one-a-day | 5.2% (18/347) [3.3–8.0] | 5.8% (18/310) [3.7–9.0] |

The published figure charges the engine for 37 days it was never run on. The
report explains at length why *unit 1's* recall is structurally low (one trade
a day can only land on one symbol) and says nothing about this, and the
un-scoped 48.7% is the figure that went into `CLAUDE.md`'s footnote. The
intervals overlap, so again **no verdict moves** — but the honest read of
detection recall on this book is 54.5%, not 48.7%.

Reproduce: `python research/v3_referee_pass2b.py`.

## Required checks, re-run by pass 2

| check | result |
|---|---|
| Pick-level precision + recall re-derived from the corpora | **pass**, exactly — table above. |
| Wilson checked by hand for one cell | **pass** — 18/59 → [20.254, 43.146]. |
| Two ladders never mixed | **pass.** Austin's S/A/C/none comes only from `grade_read` + the ninth spelling; the engine's A+/A/B/C/X comes only from the book's `grade` field; `downgrade.sgrade` is never read. `by_engine_grade` is a cross-tab (engine bucket → his-S share), headed "NOT his ladder", never an average across scales. The one place the two ladders share a letter is X, and the two X's never meet: the book's X lives in `by_engine_grade` only, his X only inside the pool's `none` bucket. |
| Script writes nothing under a mark path | **pass.** The only write-mode `open()` calls in `g215_precision.py` are lines 629 (`g215_precision.md`) and 648 (`g215_precision.json`). Every mark read is read-mode. `git status` after re-running the builder's script and both pass-2 scripts shows no mark file, deck HTML or manifest touched. |
| CLAUDE.md diff touches only the footnote | **pass.** `git show 3c8e586d -- CLAUDE.md` replaces exactly the "Precision footnote" paragraph (7 lines out, 18 in) and nothing else in the file. The mandated sentence *"Lane precision is the pick-level number — the bar is materially above 30.5% on the pick"* survives verbatim. |
| No mark file changed | **pass.** `git show --stat` on `3c8e586d` and `b5267e46` lists no `research/*marks*.jsonl`, no `research/marks/**`, no `mark_batch_*`, no `recovered_reviews`/`marks_clean`/`derived_marks_v*`/`rule_ballot_*`, no `austin_verdicts.json`, no deck manifest. Working tree likewise. |
| Sample-size rule | **partial** — pass-1 defect A stands. The per-symbol / per-setup / per-engine-grade tables print cells as small as 1/1 with no "not enough" label, though each carries its count and interval. |
| Every dollar names fill/exit/unit/script | **vacuous pass** — the report contains no dollar figure. |
| Stamped books | **N/A** — the row writes no book. The book it reads carries a stamp and the report prints its window and `RETEST_REQUIRED`. |
| One change per row | **not verifiable from the row's own commit** — pass-1 defect D stands: `b5267e46` is one `.gitignore` line plus the untracking of the regenerable JSON, and the deliverable landed in the `wip: auto-commit` `3c8e586d` alongside H1's `daily_homework.py`, H2's `g210_fill_arms_v2.*` plus twelve `research/tape/fillarms_*.json.gz`, and V1's `premarket_list_run.cmd`. |
| Report regenerates from the committed script | **pass** — re-running `g215_precision.py` left `research/g215_precision.md` byte-identical (`git status` clean on it). |
| Nightly wiring | **pass** — `research/daily_run.cmd` lines 80–86 run the script after the homework build, log-only and non-fatal, with a `PRECISION REPORT:` pointer line on both branches. |
| Verify gate at HEAD (`ccd7fa06`, `b5267e46` an ancestor) | **green, run by pass 2.** `regression_gate.py` PASS (no baseline-fired mark went silent; any_signal 75→80, s_grade 5→25, new fires only). `test_runner_stop.py` 70 checks ok. `test_universe_single_source.py` 29 symbols, no private lists. Tree carried one unrelated dirty file, another agent's `research/h1_referee.py`, left untouched. |
| Plain English | **partial** — pass-1 defects B and C stand: the "Plain English" section compares the pick-level 30.5% and symbol-day-level 28.5% against the candidate-level 39.5% (the cross-unit comparison the report exists to stop), and phrases the numerator as "a day Austin graded" where it means "graded S". |

## Reproduction

    python research/v3_referee_pass2.py     # ~40 s, headline + all 59 graded picks
    python research/v3_referee_pass2b.py    # ~40 s, defects E and F
