# One spelling for your S — the count is 288

**What changed:** your S grade was written down eight different ways across nineteen files,
so every tool in this repo counted a different number of S days. There is now **one function**
that reads all eight, and everything that matters reads the grade through it.

**The one true count: you have called 288 symbol-days S.**

Not 154, not 207, not 288-by-a-different-route. 288, produced by
`research/g72_onespelling_count.py`, which counts days through the same enumerator the
no-repeat guarantee uses and reads the grade through the new reader. Run it yourself; it takes
three seconds and prints every number in this note.

**What it is worth in dollars: nothing directly.** No trade changes, no money number moves.
What it fixes is the denominator. The recall gate — the one gate the whole project is aimed at
— has been scored on **34 cards, which is 12% of your 288 S days**, because the other 254 were
either in files nobody read or spelled in a field nobody looked at. Every "recall is 52.9%"
sentence ever published here was measured on an eighth of the evidence.

---

## The 48 you could not see

Of your 288 S days, **48 are invisible to anything that reads a grade field.**

The worst case is the one that matters most. `research/marks/probe_s_sweep_2026-08-28.jsonl` is
the 100 blind cards the project's recall number is scored on. All 100 rows say
`"grade": "none"` — that is the page's untouched default, not your answer. Your real answer,
including all **34 S calls**, sits in a different field inside the row. A tool that reads
`grade` sees **zero** S days in the sample the whole project steers by.

| how the grade is read | S days it can see |
|---|---:|
| a top-level grade field (what every reader did) | 240 |
| **all eight spellings (the new reader)** | **288** |
| the difference | **48** |

---

## Which file spells it which way

`judged days` counts the symbol-days in the file; `S rows` counts the ones you called S.

| file | judged days | S rows | field the grade is in |
|---|---:|---:|---|
| `austin_marks_v7.jsonl` | 479 | 139 | `austin_tier` |
| `austin_verdicts.json` | 162 | 78 | `verdict` (lowercase `s`) |
| `blind_marks_all.jsonl` | 260 | 50 | `tier`, plus 143 bare `_no_trade` refusals |
| `derived_marks_v1.jsonl` | 14 | 8 | `tier` |
| `derived_marks_v2.jsonl` | 18 | 10 | `austin_tier` |
| `mark_batch_02_grades.jsonl` | 60 | 35 | `austin_grade` |
| `mark_batch_03_regrades.jsonl` | 29 | 13 | `tier` |
| `mark_batch_04_grades.jsonl` | 35 | 4 | `tier` |
| `marks_clean.jsonl` | 117 | 50 | `tier` |
| `recovered_reviews.jsonl` | 176 | 57 | `austin_tier` |
| `marks/deck_marks_index_2026-08-19.jsonl` | 60 | 19 | `grade` |
| `marks/deck_marks_tsla_2026-08-20.jsonl` | 60 | 9 | `grade` |
| `marks/probe_autopsy_2026-08-23.jsonl` | 15 | 15 | `grade` |
| `marks/probe_head2head_2026-08-24.jsonl` | 9 | 0 | `grade` |
| `marks/deck_marks_h2_3lane_2026-08-28.jsonl` | 59 | 5 | `answers.grade` |
| `marks/probe_omen_test1_2026-08-27.jsonl` | 100 | 15 | `answers.grade` |
| `marks/probe_master_2026-08-29.jsonl` | 90 | 8 | `answers.grade`, `grade`, `answers.s` |
| `marks/probe_master_homework_2026-08-26.jsonl` | 51 | 16 | `answers.s_call`, `grade`, `answers.your_grade` |
| **`marks/probe_s_sweep_2026-08-28.jsonl`** | **100** | **34** | **`answers.s` only — `grade` says "none" on all 100** |

Eight names for one thing: `austin_tier`, `austin_grade`, `tier`, `grade`, `verdict`,
`answers.grade`, `answers.your_grade`, `answers.s` / `answers.s_call` — plus `_no_trade`,
which is you saying "nothing here" without a grade field at all.

---

## What was built

**`research/grade_read.py` — the one function.** `read_grade(row)` takes any row from any mark
file and returns your grade: `S`, `A`, `C`, `none`, or nothing at all when the row says
nothing. It knows all eight spellings. When a row contradicts itself — the S-sweep shape, where
one field says "none" and another says S — **the S wins**, because the "none" is a default
nobody touched and the S is an answer you gave.

It reads your ladder only. The engine's separate A+/A/B/C/X ladder is a different question and
never goes through this file.

**No mark file was opened for writing.** The readers got fixed; the data did not move. That was
the rule and it held.

**Where it is wired in:**

- `research/build_deck.py` — the file that decides which days you have already judged. It now
  gets the grade from the one reader, and it gained two functions anything can call:
  `s_days()` (your 288) and `graded_days()`.
- `research/t0_heldout_recall.py` — the script that publishes the recall gate. It used to reach
  into `answers.s` by hand. Same numbers out (checked before and after: byte-identical), but it
  can no longer be blinded by a page that renames a field.
- `research/test_no_repeat_guarantee.py` — two new cases pinning the two spellings that were
  invisible, plus a floor: **the S pool may never drop below 288**, and every S day must sit
  inside the exclusion pool. If a future page invents a ninth spelling, this goes red.

---

## The no-repeat guarantee got stronger, and here is the proof

`research/g72_onespelling_count.py` reimplements the *old* rule verbatim and diffs the two
exclusion pools:

| | symbol-days excluded from future decks |
|---|---:|
| before | 1,147 |
| after | **1,148** |
| days lost | **0** |
| days gained | 1 — `SPY_2026-08-03`, a card you annotated and left ungraded |

**Honest correction to the finding:** the 48 invisible S days were *already* excluded from new
decks. They got in through a catch-all — "this row has some answer in it" — not because
anything understood the grade. So the guarantee was right by accident. It is now right on
purpose, and pinned by a test. Nothing you have judged can be served to you again.

---

## Two things this uncovered that need a decision

**1. Thirty-five of your 288 S days are contested** — you called the day S in one sitting and
not-S in another. Most of them are explainable: an older file that a later file overwrote, or a
regrade pass where you changed your mind. Today the count treats "S anywhere" as S. Full list in
`research/g72_onespelling_count.json` under `S_days_contested_list`. The one that is genuinely
you-versus-you is **QQQ, 31 July 2026** — already on your decision list.

**2. A sixth hand-rolled reader is being written right now.**
`research/g72_recall278_paired.py` (the 278-day recall re-run) has its own grade reader inside
it. It belongs to another job so it was left alone, but it should import `grade_read` before it
publishes a number.

`research/g72_onespelling_readers.py` lists every script that still reads a grade field by
hand — **63 of them**, nearly all finished measurements whose published numbers must not move.
The rule going forward is one line: **any new S measurement imports `research/grade_read.py`.**

---

*Scripts: `research/grade_read.py`, `research/g72_onespelling_count.py`
(→ `research/g72_onespelling_count.json`), `research/g72_onespelling_readers.py`.
Every number above comes out of them. `python research/regression_gate.py` and
`python research/test_no_repeat_guarantee.py` both pass.*
