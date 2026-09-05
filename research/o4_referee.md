# O4 referee — the loop controller

**Builder commit: `8ecb043e`** ("O4: loop controller -- gate tests 27/27, smoke ok").
Referee: a different model, told to refute. Referee code: `research/o4_referee.py`
(committed beside this page). Referee run at HEAD `1f26cf73` (a sibling row landed
between the build and this review; `8ecb043e` is an ancestor of HEAD and of
`origin/main`).

**Verdict: UPHELD, with one defect.** Every number and every behaviour the builder
claimed reproduces from independent code. One real defect in the OFF arm's environment
handling is named below; it does not change any published figure (O4 published none)
but it will silently corrupt the first L-row that runs against a shell with the flag
already set.

---

## What was re-derived, and how

The referee script does **not** import `loop_cycle`'s arithmetic. The gate rule, the
sample floor and the day policy were re-written from the sentences in SWARM.md law 2/3
and the omen-10.0 spec's day-policy row, then diffed cell-by-cell against
`loop_cycle`'s own answers — on synthetic cells **and** on a real same-day A/B book
pair already on the box, `research/bt2y_trades_htfveto_{off,on}.json.gz` (both stamped
commit `cacc69d9`, built 2026-09-04 09:25, 496 sessions, 123,623 / 124,834 rows).

| check | result |
|---|---|
| C1 gate percentage, 13 cells (+100→95.1 / 95.0 / 94.9 / 150; −100→−104.9 / −105.1 / −50; 0→−1) | mine == theirs on all 13 |
| C2 green months may not fall, on its own | reproduces (13→12 fails, 13→14 passes) |
| C3 sample floor 30 trades / 12 months → no verdict, `pass: None` | reproduces; 30/12 exactly is "enough" |
| C4 boundary: a session **on** 2025-09-01 is H2 | correct (`day < boundary` / `day >= boundary`) |
| C5 the three units vs the spec's day policy | `every_signal`, `first_of_day` and `up_to_3_stop_win_or_2loss` all match my independent implementation; the day-policy unit stops on the first win, stops on the second loss, and caps at three |
| C6 the same gate re-derived on the **real** htfveto pair, all three units, both halves (6 cells) | mine == theirs on all 6 |
| C7 whole-window denominator vs the halves' | `meta.sessions` = 496 = 259 + 237; the docstring's SESSION-COUNT CAVEAT did not bite on this book |
| C9 OFF-arm `book_id` mismatch | returns `decision: "blocked"`, not `"hold"`; the ids compared are genuine `book_stamp.book_id` values; the ON arm is never built after a mismatch; the row-count diff is reported |
| C10 the phone line | `--dry-run` calls `notify_ntfy.push` zero times; a live run calls it exactly once; the text is `[OMEN] cycle 2: the one-R first-target rule -- held. $/day 40.0 -> 40.0, green months 4 -> 4` — plain English, the label only, **no flag name and no file name** |

The 5% direction is right in both signs: a fall of exactly 5% passes, 5.1% fails, any
rise passes, and on a negative baseline the rule reads "the loss may not get more than
5% worse" rather than "anything above a negative floor passes".

### The gate on real data (illustrative, not a verdict)

Re-derived from the two htfveto books, unit and half named, fill = the books' own
`entry_fill` stamp, exit = the shipped ladder, script = `research/o4_referee.py`:

| unit | half | $/day off → on | green months | trades (off) | months | gate |
|---|---|---|---|---:|---:|---|
| every signal | H1 | −$277 → −$108 | 5 → 5 | 2,081 | 13 | pass |
| every signal | H2 | −$629 → −$631 | 2 → 3 | 2,249 | 12 | pass |
| first of day | H1 | $55 → $107 | 6 → 8 | 259 | 13 | pass |
| first of day | H2 | −$65 → −$58 | 4 → 5 | 237 | 12 | pass |
| up to 3, stop on a win or 2 losses | H1 | $147 → $69 | 8 → 8 | 403 | 13 | **fail** |
| up to 3, stop on a win or 2 losses | H2 | −$111 → −$99 | 4 → 4 | 382 | 12 | pass |

These are **not** a verdict on the HTF-veto flag — they are the gate exercised on a
pair of books that happened to be on disk, and the pair predates the omen-10.0
baseline. They are here only to show the gate produces a mixed, non-trivial answer on
real rows rather than passing everything.

## The smoke run — reproduced, because the builder deleted the evidence

The report claims a `--stage all --dry-run --smoke` rehearsal: two 15-day books, 10
trades, $22/day both arms, `decision: hold`. The builder then deleted the books, the
logs and the ledger, so **nothing in the repo supports that claim** — the required
check "the smoke log exists" fails on the tree as committed.

I re-ran it myself. It reproduces exactly:

- both arms built with `backtest_2y.py --days 15`, window 2026-08-20..2026-09-04,
  10 sessions, 28 symbols (logs written to `research/tape/logs/`, exit 0)
- unit `first_of_day`, 10 trades, **$22/day on both arms** (a synthetic no-op flag),
  avg win $669 / avg loss $626, script `research/loop_cycle.py`, fill = the engine
  default stamped in the book
- `decision: hold` because H1 has 0 trades and H2 has 10 trades / 2 months — both
  under the 30-trade / 12-month floor, both reported as **"not enough"**, no verdict
- the books it wrote carry a full `book_stamp`: commit, `dirty_engine_py: []`, 70 flag
  values, `built_at`, window and session count

I deleted my own smoke books, logs, `cycles.md` and `loop_state.json` afterwards for
the same reason the builder did — so the first real cycle starts at cycle 1.

## The defect

**`build_book()` never unsets the flag for the OFF arm.** It does
`env = dict(os.environ)` and only ever *adds* keys, so if the flag under test is
already set in the ambient environment the OFF arm builds the flag **on**. The module
docstring's claim — *"the OFF arm (flag left at its current default -- env simply
unset)"* — is false. This repo has already been bitten by exactly this class of thing
(the settings `env` block shadowing `.env`).

Consequences, worst first:

1. If the ambient value equals `--on`'s value, both arms are the same book, the gate
   compares a book to itself, both halves pass, and the cycle reports **ship** for a
   change that was never measured.
2. Otherwise the OFF-arm `book_id` assertion catches it and the cycle reports
   `blocked` — noisy, but safe. `--smoke` skips that assertion entirely.

The fix is one line in `build_book`: `env.pop(flag, None)` on the OFF arm (the flag
name has to reach `build_book`, which today it does not). That is a change to
`loop_cycle.py`, which this referee row does not own — it is written up here for the
phase chief to assign.

## Smaller notes, no number moves

- **The 12-month floor has no margin on H1.** With `halves_boundary` 2025-09-01 and a
  730-day window, H1 is Sep-2024..Aug-2025 — exactly 12 months. Shorten the window at
  all and H1 falls to 11 months, `enough` goes false forever, and every cycle holds
  regardless of what the change does. Worth a guard, or a note in `loop.json`.
- **The halves use a different denominator from the whole window.** The whole window
  uses the book's flag-independent `meta.sessions`; each half counts the distinct days
  appearing in *that book's own rows*. On the real pair the two agreed (259 + 237 =
  496), so nothing is wrong today — but the halves' denominator is computed per book,
  so a flag that empties a whole day of candidates would shrink that arm's denominator
  and inflate its $/day. The docstring flags the undercount; it does not flag the
  per-arm asymmetry.
- **The stamp does not name the script.** `book_stamp.stamp` records commit, dirty
  flag, 70 flag values, date and (via `meta`) the window — but not the builder script.
  `cycles.md` carries a script column, so the loop's own ledger is covered. This is a
  `book_stamp.py` property, not O4's.
- **The spec's own ntfy template names the flag** (`[OMEN] cycle N: <flag> …`); the
  builder used the plain-English label instead. That is a deviation from the spec text
  and the correct call under SWARM.md's plain-English rule. Recording it so nobody
  "fixes" it back.
- The report's incidental claims all check out: no `notify_ntfy` module exists under
  `research/` (it is at the repo root, correctly reused); `research/test_loop_gate.py`
  is 27 tests and all 27 pass; the three sibling-agent files in the tree were left
  untouched and unstaged.

## Standard checks

| check | result |
|---|---|
| Sample-size rule respected in the report | yes — the only numeric result is the smoke, and both halves are reported as "not enough" with counts |
| Every dollar names fill / exit / unit / script | yes for the smoke ($22/day, engine-default fill, first-of-day unit, `backtest_2y.py --days 15` via `research/loop_cycle.py`); no other dollar published |
| Stamped books, stamp commit == row commit or ancestor | the row committed no book; the books it *builds* are stamped by `backtest_2y.py` — verified on my reproduction |
| One change per row | yes — `git show --stat 8ecb043e` is 5 files, 731 insertions, 0 deletions: `research/loop_cycle.py`, `research/test_loop_gate.py`, `research/tape/loop.example.json`, `research/tape/README.md`, `.gitignore`. No engine file touched, no flag changed |
| No mark file changed | confirmed — none of the mark corpora appears in the commit or in `git status` |
| Verify gate green at the row's commit | ran it myself at `8ecb043e`: `regression_gate.py` PASS, `test_runner_stop.py` 70 checks ok, `test_universe_single_source.py` ok (29 symbols, 25 backtested, no private lists). Exit 0 |
| Plain English in anything Austin reads | yes — the only thing he sees is the ntfy line, and it carries the label, the dollars and the green months, nothing else |
