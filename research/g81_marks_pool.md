# One canonical S/A/C/none pool — the count is 309, and 154 / 207 / 288 are all stale

**Script:** `research/marks_pool.py` → `research/marks_pool.json`. Read-only — every mark file
was opened for reading only, none for writing. Run it yourself: `python research/marks_pool.py`
takes about a second and prints every number below, then self-checks them against pinned
constants.

**The one-line answer to the question asked:** none of 154, 207, or 288 is the right number
tonight. **288 was right as of last night.** It is now short by 21 — tonight's g71 homework
deck (`research/marks/probe_g71_homework_s3_2026-08-29_complete.jsonl`, the 30 cards Austin
just graded) spells its S-call in a field none of the eight known spellings recognize, and
21 of those 30 are "yes." **The current true count is 309 S days.**

---

## 1. What "one canonical view" means here

`research/build_deck.py` already owns the two hard parts of this problem — which files to
read (`mark_sources()`) and how to turn any row into a `SYMBOL_YYYY-MM-DD` key
(`_judgement_key()`) — and `research/grade_read.py` already owns reading a grade out of a
single row, eight spellings deep. `research/marks_pool.py` adds the two things neither of
those does:

1. A **ninth spelling** (§2) — found by running the existing eight-spelling reader against
   tonight's file and getting `None` back on all 30 rows.
2. A **canonical grade per symbol-day** — `build_deck.graded_days()` returns a *set* of
   grades per day when more than one corpus has an opinion; nothing before tonight collapsed
   that set to one answer. `marks_pool.canonical_pool()` does, with a stated rule (§4).

Nothing in this file writes to a mark corpus. `git status` after running it shows only
`research/marks_pool.py` and `research/marks_pool.json` — the reader and its own generated
report — untracked/modified; no file under `research/marks/`, `austin_marks_v7.jsonl`, or
any of the other named corpora is touched.

---

## 2. The spellings — five in the board note, eight as of last night, nine as of tonight

Austin's grade — `S` / `A` / `C` / `none` — is spelled across **nine field names** in the 20
corpora on disk. `research/g71_board.md` said "five different fields"; that was already an
undercount when it was written, because two families of `answers.*` fields (four field names)
already existed and weren't being read by anything at the time. `research/grade_read.py`
closed that gap and got to eight. Tonight's homework deck opens a ninth.

| # | field | example value | rows carrying an opinion | of which "S" |
|---|---|---|---:|---:|
| 1 | `austin_tier` | `"S"` | 673 | 206 |
| 2 | `tier` | `"S"` | 312 | 125 |
| 3 | `austin_grade` | `"S"` | 60 | 35 |
| 4 | `grade` | `"S"` | 578 | 78 |
| 5 | `verdict` | `"s"` (lowercase) | 162 | 78 |
| 6 | `answers.grade` | `["S"]` | 258 | 30 |
| 7 | `answers.your_grade` | `["S"]` | 12 | 3 |
| 8 | `answers.s` / `answers.s_call` | `["s"]` | 115 + 25 | 37 + 5 |
| 9 | **`answers.is_s`** | **`["yes"]` / `["no"]`** | **55** | **37** |
| — | `_no_trade` | `true` (a refusal, no grade field at all) | 143 | 0 |

Row counts can double-count a single symbol-day (a bar-level corpus can carry several rows
for one day), which is why these don't sum to 1,178 — they're a spelling census, not a
day census.

**Spelling 9, in full:** two files use `answers.is_s` — `research/marks/probe_g71_homework_s3_2026-08-29.jsonl`
(25 rows, an earlier autosave) and `..._complete.jsonl` (30 rows, the final export; the 25 are
a strict subset of the 30). Before `marks_pool.py`, **`grade_read.read_grade()` returns `None`
for all 30 rows of the complete file** — verified directly:

```
read_grade({"card_id":"BABA_2024-09-05","grade":None,"answers":{"is_s":["yes"]}, ...}) -> None
```

Handled in `marks_pool.py` itself (`row_opinions()` wraps `grade_read.grade_opinions()` and
appends the `answers.is_s` opinion), **not** by editing `grade_read.py`. That keeps every
number already published from `grade_read.py` — the 288-day S count in
`research/g72_onespelling.md`, the pinned floors in `research/test_no_repeat_guarantee.py` —
byte-identical. **Recommended follow-up, not done here:** add `"is_s"` to
`grade_read.ANSWER_YESNO_FIELDS`. It is a one-line, strictly-additive change (it can only add
opinions grade_read never had, never remove one), so it would raise the 288 floor, never break
it — but it moves a published number and this task's brief is read-only measurement, so it's
named here rather than applied.

Note the "no" side is a real answer too. Nine of the 30 rows say `answers.is_s: ["no"]`
(with a `why_not` reason — `chop`, `late`, `no_displacement`, `no_retest`, `level_not_respected`,
`other`) — a refusal, same as `grade: "none"` anywhere else, and it's counted as `none` below.

---

## 3. `grade: "none"` is a judgement, everywhere in this pool

Every corpus in this pool that says `grade: "none"`, `_no_trade: true`, `answers.s: ["no"]`,
`answers.is_s: ["no"]`, or a bare `X` on a mark row is Austin having looked and refused —
not a blank. `research/grade_read.has_judgement()` already treats these as equal, and
`marks_pool.py` inherits that rule unchanged: **560 of the 1,178 days in this pool carry no
S/A/B/C grade, and all 560 are refusals, not missing data.**

Two different *kinds* of refusal live inside that 560, and this report keeps them visibly
separate so neither swallows the other:

| kind | days | what it means |
|---|---:|---|
| explicit `none` (or `_no_trade`, or `answers.*: no`) | 368 | Austin looked at the whole day and would not trade it |
| `X`-only (every opinion on the day is literally `"X"`, nothing else) | 192 | Austin is refusing a *specific detected bar the engine proposed* — "this should not have fired" — not necessarily a verdict on the day itself (`research/marks/LEDGER.md`, `research/g72_onespelling.md`) |

Both fold into the single `none` count in the headline table (§5) because neither is an S/A/C
grade — but a script that wants "days he explicitly rejected as a whole" should use 368, not
560, and `research/marks_pool.json` carries both.

---

## 4. Resolving a symbol-day graded in more than one corpus

**357 distinct symbol-days appear in more than one mark file.** Two different corpora that
*agree* are not a conflict — that's just the same judgement seen twice, and the day-key pool
already dedups it for free. The question that needs a rule is disagreement.

**The rule: best grade wins, ladder `S > A > B > C > none`** (`X` ties with `none` — see §3).
This is not a new invention: it's the exact rule `build_deck.s_days()` already applies to S
alone ("if any corpus calls the day S, the day is S" — the recall question is "did the engine
trade a day he liked," and one S bar answers that), carried uniformly down the rest of the
ladder rather than stopping at S.

**How many rows this affects: 70 symbol-days are contested (opinions disagree across
corpora), spanning 345 individual grade-carrying rows.** That's 5.9% of the 1,178-day pool.
None of it comes from tonight's homework deck — all 30 of those symbol-days were chosen
specifically because Austin had never judged them before (verified: zero of the 30 appear in
the contested list, and zero were already present in the pool before tonight's file was
added).

First 5 of the 70, for a feel of the shape (full list of 15 sampled in
`research/marks_pool.json` → `contested_days.sample`; all 70 keys are in the pool itself):

| symbol-day | raw grades seen | resolved to | which corpora |
|---|---|---|---|
| AAPL 2024-03-28 | S, X | **S** | austin_marks_v7, derived_marks_v2 |
| AAPL 2025-01-13 | A, S | **S** | austin_marks_v7, derived_marks_v2 |
| AAPL 2025-09-09 | C, X | **C** | austin_marks_v7 |
| AMD 2024-11-11 | A, S | **S** | austin_marks_v7, derived_marks_v2 |
| AMD 2025-06-05 | A, S | **S** | austin_marks_v7, austin_verdicts, mark_batch_02, mark_batch_03 |

Most of the 70 are the same shape as the first four rows: an early bar-level pass called it
A, a later regrade or the derived-marks pass called it S. That is consistent with
`research/g72_onespelling.md`'s note that most of its 35 S-contested days are "an older file
a later file overwrote."

---

## 5. Final counts

| grade | symbol-days | of which have archived bars |
|---|---:|---:|
| **S** | **309** | 303 |
| **A** | **237** | 228 |
| **C** | **58** | 58 |
| **none** | **560** | 542 |
| B *(legacy-ladder leak into a human file — kept separate, never folded into A or C)* | 14 | 14 |
| **total** | **1,178** | **1,145** |

**1,145 of 1,178 judged symbol-days (97.2%) have `data_archive/<SYMBOL>/<DATE>.csv` on disk
and can be replayed today.** Bar check: `os.path.exists(data_archive/<symbol>/<date>.csv)`,
identical to the check `research/g71_samplesize_corpus_audit.py` already uses. Restricted to
S days specifically: **303 of 309 (98.1%)** — higher than the 278-of-288 figure DIRECTION.md
and the board cite, both because the pool has grown (288 → 309) and because bars have been
archived for a few more symbol-days since that number was last measured.

---

## 6. Which of 154 / 207 / 288 is right

**None of them, as of tonight. All three were right for the question each one was actually
answering, and each has since been superseded:**

| count | where it's from | why it's not today's number |
|---:|---|---|
| **154** | `research/marks/LEDGER.md` | Deliberately the *narrow* pool: `austin_marks_v7.jsonl` ∪ the two canon deck files only. Excludes 15 other documented, completed grading-session files — not wrong for what it measured, just a much smaller pool than "every corpus." |
| **207** | `research/x6_recall_n.py` (cited in `research/g71_smeasure.md`) | Reads only the five literal top-level fields (no `answers.*` forms), and was run before the corpus grew to its current size. Re-running that same scalar-only method today gives **240**, not 207 — the extra 33 are corpus growth since x6 last ran, not a methodology fix. |
| **288** | `research/g72_onespelling.md` / `g71_smeasure_pools.py`, last night | The full eight-spelling union, correct at the time. **Short by 21 tonight** because it can't read `answers.is_s`, the ninth spelling this file adds (§2). Independently confirmed: running the eight-spelling-only method against tonight's corpus (`marks_pool.py`'s own reader with the ninth spelling disabled) reproduces **288 exactly**, and the 21-day gap to 309 is precisely the 21 "yes" rows in tonight's homework file — nothing else moved. |

**The current, correct count is 309.** It will move again the next time Austin grades a card,
by design — that's the point of `research/marks_pool.py` existing as a reusable function
instead of one more one-off script with its own hand-rolled reader.

---

## 7. Self-check

`python research/marks_pool.py` ends with:

```
total judged symbol-days: 1178
  S    309
  A    237
  C    58
  none 560  (of which 368 explicit refusal, 192 X-only engine refusal)
  B    14  (legacy ladder leak, kept separate)
bars available: 1145 / 1178
contested days (corpora disagree): 70, spanning 345 rows
wrote research/marks_pool.json
ok   self-check: all pinned counts match
```

The `__main__` block asserts every headline number above against a pinned constant and exits
non-zero if any of them move — a mark file changed (which should never happen — see
`CLAUDE.md`, "never lose a mark") or a future edit to `marks_pool.py`'s reading rule changed
what a row counts as. Either way, the fix is to re-read this report and update it, not to
silently re-pin the assert.

---

*Every number in this report comes out of `research/marks_pool.py`, run tonight
(2026-08-29/30). Full machine-readable detail — the field census, the 70-day contested list,
per-source row counts for every one of the 20 corpora — is in `research/marks_pool.json`.*
