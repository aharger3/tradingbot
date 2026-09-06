# L1 referee — REFUTED (the numbers), decision upheld

Row **L1**, the 1R first-target rule (`MIN_PT1_R`). Builder commits **e073b94a** (code, flag
lands OFF) and **842b3f3c** (the books, the gate, `research/l1_min_pt1_r.md`). Referee script:
`research/l1_referee.py` — every figure below is re-derived from the two stamped books with
arithmetic written out longhand in that file; nothing is taken from the builder's own gate
output. Base check at start: `origin/main` = HEAD = `842b3f3c`, `1539dd7f` is an ancestor.

**Verdict: refuted.** The *decision* (hold, default stays OFF) is correct and survives every
way I sliced it. **Every published number is measured on the wrong universe**, and the
write-up names a universe it did not use.

---

## 1. The universe defect — the reason this is refuted

`research/l1_min_pt1_r.md` states, in the sentence that qualifies every dollar in the row:

> universe = `CORE_SYMBOLS` (11 symbols, rows with `tier=='core'`)

It is not. `research/loop_cycle.py::stage_gate` reads `cfg["unit"]`, `cfg["halves_boundary"]`,
`cfg["gate"]` and `cfg["targets"]` from `research/tape/loop.json` and **never reads
`cfg["universe"]`**. There is no `tier == "core"` filter anywhere in `loop_cycle.py`. The gate
therefore ran on all **28 symbols** in the book (`tier` counts in the OFF book: core 54,186 /
experimental 62,450 / other 10,877 rows).

`research/tape/loop.json`'s own `_comment` had already flagged this as a prerequisite the
loop controller did not yet meet:

> Two items the loop controller still needs before cycle 1 … (1) `universe` — the settled
> universe is CORE_SYMBOLS, so the unit function must run on rows with tier == "core"
> (loop_cycle.py reads the whole 29-symbol book today)

Cycle 1 ran anyway. The proof is arithmetic: my full-29 re-derivation reproduces the
builder's table to the dollar, and my core-11 re-derivation reproduces **R3's own
`baseline_figures` block in `loop.json`** to the dollar. Same book (`book_id`
`2c39ced2697c26cc` on both), two different universes, two different tables.

| unit = up_to_3_stop_win_or_2loss · fill = close · exit = shipped 1R hard stop + `hod_then_runner_be` · 499 sessions 2024-09-04..2026-09-04 · script `research/l1_referee.py` | trades | $/day | mean R | green | months |
|---|---:|---:|---:|---:|---:|
| **core-11** (loop.json `universe.row_filter`, what R3 measured) OFF | 769 | **−$52** | −0.0335 | 11 | 25 |
| **core-11** ON (`MIN_PT1_R=1.0`) | 751 | **−$29** | −0.0195 | 11 | 25 |
| core-11 H1 (…2025-08-31) OFF | 382 | $9 | 0.0057 | 6 | 12 |
| core-11 H1 ON | 368 | $107 | 0.0721 | 7 | 12 |
| core-11 H2 (2025-09-01…) OFF | 387 | −$111 | −0.0722 | 5 | 13 |
| core-11 H2 ON | 383 | −$164 | −0.1076 | 4 | 13 |
| **full-29** (what `loop_cycle.py` actually gated on) OFF | 773 | −$9 | −0.0059 | 12 | 25 |
| **full-29** ON | 767 | **$29** | 0.0188 | 12 | 25 |
| full-29 H1 OFF / ON | 378 / 377 | $72 / $201 | 0.0472 / 0.1322 | 8 / **9** | 12 |
| full-29 H2 OFF / ON | 395 / 390 | −$89 / −$141 | −0.0567 / −0.0908 | 4 / **3** | 13 |

The full-29 block matches `research/l1_min_pt1_r.md`, `research/tape/cycles.md` and
`research/tape/loop_state.json` exactly, so the builder's arithmetic is sound — it is the
population that is wrong.

What actually changes when the universe is corrected:

- The headline flips sign. On core-11 the ON arm **never turns positive**: −$52/day → −$29/day,
  a smaller loss, not a profit. The published "−$9 → $29" is a full-29 figure.
- Whole-book green months are **11 → 11**, not 12 → 12.
- H1 is **6 → 7** green, not 8 → 9. H2 is **5 → 4**, not 4 → 3.
- Trade counts are 769/751, not 773/767; `cycles.md`'s trade column (767) is a full-29 count.
- Fires/day is 1.541 → 1.505, not the published 1.549 → 1.537.

**The decision is unaffected.** On core-11 H2 fails on both criteria — green months fall 5 → 4
*and* $/day gets worse than 5% (−$111 → −$164) — so the no-regression gate holds the change
either way. Default OFF is right. (Minor: the write-up says H2 fails "regardless of the dollar
move"; on both universes H2 fails the dollar test too, so the framing understates the fail.)

The fix belongs to the loop controller (`loop_cycle.py`, row O4), not to the flag: one
`row_filter` in `stage_gate`. Until it lands, **every cycle row in `research/tape/cycles.md`
is a full-29 number wearing a core-11 label**, and cycle 1's row should be re-run or annotated.

## 2. The X_LIFT ordering hole — the gate cannot see 2,439 traded rows

In `signal_runner._route` the gate is written as:

```
if MIN_PT1_R > 0 and sig.get("grade") not in _SKIP_GRADES:
    ...
self._apply_x_lift(sig)
```

`_SKIP_GRADES = ("X", "D")`, and `X_LIFT` is `"clean"` by default (stamped in both books). So
an X-graded signal that `_apply_x_lift` promotes back to `B` is **never tested by the RR
gate** — the gate has already returned by the time the lift happens. In the ON book that is
**4,384 x-lifted rows, 2,439 of them traded** (1,180 on core-11), and **0** of the 4,384 carry
the `MIN_PT1_R` skip tag. The rule is silently not applied to that population.

This is the known bug class in `research/omen-rules-unreachable-in-code`, and the codebase
already carries the warning 25 lines below this very gate, on `S_CLASSIFIER`:

> Placed AFTER `_apply_x_lift` on purpose: X_LIFT exists to rescue X-graded rows, and a drop
> applied before it would just get lifted straight back to B, which is exactly what the first
> version of this gate did.

`MIN_PT1_R` is placed on the wrong side of the same line. I did not price how many of the
2,439 would fail the RR test — the books do not carry the session extreme, so that needs an
engine re-run, not a query. The exposure is exact; the cost is untested.

## 3. What I checked and could NOT break

- **Book identity.** OFF `book_id` `2c39ced2697c26cc` **equals** the R3 baseline's
  (`research/tape/loop.json`, `baseline_2026-09-05.json.gz`). The `_emit` wrapper refactor
  (10 call sites rerouted to attach `session_hi`/`session_lo`) changed nothing on the default
  path — the fingerprint is byte-for-byte the baseline's, and neither key appears in the book
  rows. ON `book_id` `04b7f4f9778fc72a`.
- **Stamp diff, OFF vs ON:** exactly one flag, `signal_runner.MIN_PT1_R` `0.0 → 1.0`. Everything
  else that differs is bookkeeping (`built_at`, `out`, `rows`, `book_id`). Both stamps carry
  commit `e073b94a`, `dirty_py_count: 0`, `dirty_engine_py: []`, window 2024-09-04..2026-09-04,
  499 sessions. `e073b94a` is an ancestor of the row's commit `842b3f3c`.
- **Semantics vs the rulebook.** `research/omen_recall.py "RR gate first scale point HOD LOD 1R
  from entry"` returns, dated 2026-09-05: *"**RR gate: first scale point (HOD/LOD) must be >= 1R
  from entry.** Because: 'we dont want to get in on a candle close of HOD/LOD because thats
  always our first scale point, then the RR is shot.'"* The spec's settled table says the same
  and adds "skip the signal unless …". The code skips (`status="skipped"`, returns) rather than
  capping to C — correct; a capped C still trades. The measured point is right too: the gate
  reads `max(c.high for c in self.candles)` / `min(c.low …)` at emit time, and
  `backtest_week.py:1386` sets `runner.candles = candles[:i + 1]` immediately before
  `detect_signals()`, so it is *identically* the expression `backtest_week.py:1479/1484` uses
  for `scale_level` under `SCALE_PLAN=hod_then_runner_be` — LADDER PT1. The risk denominator is
  also right on this book: at `ENTRY_FILL="close"`, `sig["entry"]` already is the fill price
  (`entry_fill.py:236`), so nothing is re-priced after the gate. **Caveat, not a defect here:**
  under `SCALE_PLAN="four_rung"` PT1 comes from `levels_ladder.build_rungs` and need not equal
  the session extreme, so the gate would then measure a point the ladder does not scale at.
- **Default matches the decision.** `MIN_PT1_R = float(os.getenv("MIN_PT1_R", "0") or "0")` —
  OFF, and the decision is hold. Registered in `research/book_stamp.py` `FLAG_SOURCES`
  (line 92) and present in both stamps.
- **The uncommitted ad hoc query.** The write-up publishes "9,283 / 1,082 / −0.065R" and says
  outright it is "not committed as a script", which is a SWARM law-5 violation. Re-derived it
  myself: **9,283** ON-book rows tagged (core-11: 3,914); **1,082** of them traded in the OFF
  book (core-11: 475); mean **−0.0647R**; win 47.2% of all rows / 47.4% of decided ones. The
  numbers hold. The script now exists as `research/l1_referee.py`.
- **Sample size.** Every cell carrying a verdict clears the floor: core-11 whole 769/751 over
  25 months, H1 382/368 over 12, H2 387/383 over 13. No cell under 30 trades or 12 months is
  given a verdict anywhere in the write-up or here.
- **One change per row.** `git show --stat e073b94a` = `signal_runner.py` + `research/book_stamp.py`
  (one flag). `git show --stat 842b3f3c` = the write-up, two stamped books, `cycles.md`,
  `loop_state.json`. No engine file outside the row's scope.
- **No mark file touched** in either commit, and `git status` is clean apart from this
  referee's own two files.
- **Verify gate, run by me at `842b3f3c`:** `research/regression_gate.py` PASS (no
  baseline-fired mark went silent; any_signal 75→80, s_grade 5→25);
  `research/test_runner_stop.py` ok, 70 checks; `research/test_universe_single_source.py` ok,
  29 symbols, no private lists. All exit 0.
- **Plain English.** `cycles.md`'s label column reads "the 1R first-target rule" and the ntfy
  line format is "[OMEN] cycle 1: the 1R first-target rule — held. $/day … green months …" —
  no flag names, no ticket ids. That part is fine (the numbers in it are the full-29 ones).

## 4. Second-order note, not a defect

Dropping a signal releases the dedupe suppression window (`DEDUPE_FIRES_ONLY`: only a *fired*
signal claims it), so the ON book has **more** rows than the OFF book — 131,530 vs 127,513,
+4,017. `CLAUDE.md` warns about exactly this ("Any C-cap gate in this engine adds candidates as
well as removing them"). The write-up gestures at it ("backfilled by the next arrival-order
candidate") without naming the mechanism or the +4,017. It does not change the verdict, but any
reading of "the gate removes 9,283 signals" should be read as "removes 9,283 and creates 4,017".

## What the next agent should do

1. Add the `universe.row_filter` to `loop_cycle.py::stage_gate` (row O4's change, one line),
   re-run `--stage gate` on the two books already committed here, and correct
   `research/tape/cycles.md`, `research/tape/loop_state.json` and `research/l1_min_pt1_r.md`
   to the core-11 column above. No rebuild is needed — the books are stamped and correct.
2. Move the `MIN_PT1_R` block below `self._apply_x_lift(sig)` in `signal_runner._route`, then
   re-measure. That is a second change and belongs to its own row.

---
---

# L1 referee, PASS 2 — REFUTED (the numbers again), decision still upheld

Second-pass referee on the repair commit **`d062da84`** ("L1 repair: relabel core-11 vs
full-29 in the report, move MIN_PT1_R gate after `_apply_x_lift` — **no ON-arm number
changes**, decision (hold) unaffected on either universe"). Base check at start:
`origin/main` = HEAD = `d062da84`; `1539dd7f` is an ancestor. Pass-1 above is commit
`af028359`; the row's own commits are `e073b94a` (code) → `842b3f3c` (books, gate) →
`d062da84` (repair).

*Provenance note: the repo's `wip: auto-commit` hook swept this pass's four files (this
write-up, `research/l1_referee2.py` and the two post-repair books) into commit `ba639df0`
before the referee could commit them under its own message. Nothing else is in that commit and
no mark file is touched by it; the referee's own commit follows immediately and carries the
verdict in its message.*

Everything below is re-derived by **`research/l1_referee2.py`** (committed beside this file).
That script imports neither `loop_cycle.py` nor `g72_suppress_price.py` nor pass 1's
`l1_referee.py`: the day-policy unit, the month buckets, the green-month count, $/day and the
gate are all written out longhand, so a bug shared by the builder's script and pass 1's cannot
hide in both. Pass 2 also did what neither the builder nor pass 1 did — **rebuilt both arms
from raw bars at the repair commit** — which is where the refutation comes from.

**Verdict: refuted.** The *decision* (hold, `MIN_PT1_R` default stays `0`/OFF) is right on
every universe and on both the pre- and post-repair engine. **The repair's own headline claim
is false**: moving the gate past `_apply_x_lift` changes every ON-arm number, the row never
rebuilt the ON book, and three sentences now in `research/l1_min_pt1_r.md` are false against
the code sitting in the tree at the row's own commit.

## 1. What pass 1 asked for, and what actually happened

| pass-1 defect | status after `d062da84` |
|---|---|
| universe mislabel (full-29 numbers under a core-11 label) | **partly fixed** — `l1_min_pt1_r.md` now carries both universes correctly labeled, and I reproduce both tables to the dollar. But `research/tape/cycles.md` and `research/tape/loop_state.json` — the tape's own ledger, which is what the loop and Phase T read — still publish the full-29 figures with **no annotation at all**, and the plain-English line pushed to Austin carried them too. See §4. |
| `X_LIFT` ordering hole | **code fixed, numbers not re-measured** — the block now sits after `self._apply_x_lift(sig)`, mirroring `S_CLASSIFIER`. The move is genuinely a no-op on the default path (proved in §2). But the row kept the ON book built on the *old* ordering and asserted the arm was unchanged. It is not (§3). |
| SWARM law 5 (a script behind every published number) | **fixed** — the 9,283 / 1,082 / −0.065R figures now cite committed code, and I reproduce them exactly: 9,283 tagged rows (3,914 core), 1,082 of which traded in the OFF book, mean **−0.0647R**, win 47.4% of decided rows. |

## 2. What I could not break — the row's committed arithmetic is sound

Unit = `up_to_3_stop_win_or_2loss` · fill = **close** (market at the close of the signal bar,
`entry_fill.ENTRY_FILL` default) · exit = the shipped engine, 1R hard stop resting at exactly
1R filled on the intrabar touch, `SCALE_PLAN=hod_then_runner_be`, `LOSS_HALT` on · window
2024-09-04..2026-09-04, 499 sessions · script `research/l1_referee2.py`. 1R = $1,000.

- **Both published tables reproduce exactly.** full-29 OFF/ON: 773/767 trades, −$9/$29 per day,
  green 12/12; H1 378/377, $72/$201, 8/9; H2 395/390, −$89/−$141, 4/3. core-11 OFF/ON:
  769/751, −$52/−$29, 11/11; H1 382/368, $9/$107, 6/7; H2 387/383, −$111/−$164, 5/4.
  Every cell matches `research/l1_min_pt1_r.md` and, for full-29, `cycles.md`'s row
  (−9.0 → 29.0, 12 → 12, pass, fail, 767).
- **core-11 OFF *is* the R3 baseline**, to the dollar: 769 trades, −$52/day, −0.0335R, 11/25
  green = `loop.json`'s `baseline_figures.whole`. `tier == "core"` is exactly
  `universe.CORE_SYMBOLS` (11 symbols, checked set-equal).
- **Book identity.** OFF `book_id` `2c39ced2697c26cc` = the baseline's. ON `04b7f4f9778fc72a`.
  Stamp diff OFF vs ON is **exactly one flag**, `signal_runner.MIN_PT1_R` `0.0 → 1.0`; both
  stamps carry commit `e073b94a` (an ancestor of `d062da84`), `dirty_py_count: 0`,
  `dirty_engine_py: []`, window 2024-09-04..2026-09-04, 499 sessions.
- **"Byte-identical on the default path" is now measured, not asserted.** I rebuilt the OFF arm
  from raw bars at `d062da84`: `book_id` **`2c39ced2697c26cc`**, 127,513 rows — identical to the
  baseline and to the row's own OFF book. The reorder is a true no-op when the flag is 0.
- **Semantics match the rulebook sentence.** `omen_recall.py` returns, dated 2026-09-05:
  *"**RR gate: first scale point (HOD/LOD) must be >= 1R from entry.** Because: 'we dont want to
  get in on a candle close of HOD/LOD because thats always our first scale point, then the RR is
  shot.'"* The code *skips* (`status="skipped"`, `return`) rather than capping to C — right, a
  capped C still trades. And the point it measures is the right one: `signal_runner.py:2957-2967`
  sets `session_hi = max(c.high for c in self.candles)` at emit time, `backtest_week.py:1386`
  sets `runner.candles = candles[:i + 1]` immediately before `detect_signals()`, and
  `backtest_week.py:1479/1484` computes `scale_level = max(cd.high for cd in candles[:i + 1])` —
  the same expression, so the gate measures LADDER PT1 under `SCALE_PLAN=hod_then_runner_be`.
- **Default matches the decision.** `MIN_PT1_R = float(os.getenv("MIN_PT1_R", "0") or "0")` —
  OFF, and the decision is hold. Present in `research/book_stamp.py` `FLAG_SOURCES` (line 92)
  and in every stamp.
- **Sample size.** No cell carrying a verdict is under 30 trades or 12 months: smallest is
  core-11 post-repair H1 ON at 353 trades over 12 months.
- **One change per row.** `git show --stat d062da84` = `research/l1_min_pt1_r.md` +
  `signal_runner.py` (one block moved, no new logic). Within the one-flag rule.
- **No mark file touched** by `e073b94a`, `842b3f3c`, `af028359` or `d062da84`; `git status`
  clean apart from this pass's own files.
- **Verify gate, run by me at `d062da84`:** `research/regression_gate.py` PASS (no
  baseline-fired mark went silent; any_signal 75→80, s_grade 5→25); `research/test_runner_stop.py`
  ok, 70 checks; `research/test_universe_single_source.py` ok, 29 symbols, no private lists.
  All exit 0.

## 3. The refutation — the repair silently invalidated its own ON arm

The commit subject says "**no ON-arm number changes**". I rebuilt both arms from raw bars at
`d062da84` (same day, same 499-session window, `dirty_engine_py: []`; `dirty_py_count: 1` is
this pass's own uncommitted script). Books, stamped and committed beside this file:
`research/tape/book_MIN_PT1_R_off_postfix.json.gz` (`book_id 2c39ced2697c26cc`, identical to the
baseline) and `research/tape/book_MIN_PT1_R_on_postfix.json.gz` (`book_id b7af0b7a460fa148`).
Same unit, fill, exit, window and script as §2.

**core-11 (`universe.CORE_SYMBOLS`, the settled universe)**

| | trades | $/day | mean R | win% | green | months |
|---|---:|---:|---:|---:|---:|---:|
| whole OFF (unchanged) | 769 | −$52 | −0.0335 | 45.0% | 11 | 25 |
| whole ON, **as published** (pre-repair engine) | 751 | −$29 | −0.0195 | 44.6% | 11 | 25 |
| whole ON, **at the row's own commit** | 732 | **+$28** | 0.0193 | 33.9% | **14** | 25 |
| H1 OFF | 382 | $9 | 0.0057 | 43.7% | 6 | 12 |
| H1 ON, published / at `d062da84` | 368 / 353 | $107 / **$204** | 0.0721 / 0.1434 | 45.1% / 36.1% | 7 / **9** | 12 |
| H2 OFF | 387 | −$111 | −0.0722 | 46.3% | 5 | 13 |
| H2 ON, published / at `d062da84` | 383 / 379 | −$164 / −$145 | −0.1076 / −0.0964 | 44.1% / 31.9% | 4 / **5** | 13 |

**full-29 (what `loop_cycle.py::stage_gate` actually gates on)**

| | trades | $/day | green | months |
|---|---:|---:|---:|---:|
| whole OFF | 773 | −$9 | 12 | 25 |
| whole ON, published / at `d062da84` | 767 / 780 | $29 / **$84** | 12 / **11** | 25 |
| H1 ON, published / at `d062da84` | 377 / 380 | $201 / $271 | **9 / 7** | 12 |
| H2 ON, published / at `d062da84` | 390 / 400 | −$141 / −$99 | **3 / 4** | 13 |

Skip accounting moves the same way: tagged rows **9,283 → 14,929** (core 3,914 → 6,731), rows
that would have traded in OFF **1,082 → 2,927** (core 475 → 1,367), mean R of that slice
**−0.0647 → −0.0570**. The pre-repair ON book's skipped rows are graded C 4,699 / B 4,484 /
A 100 and **zero X** — the fingerprint of a gate running before the lift; post-repair the B
count nearly triples (10,363) as the lifted rows finally reach it. ON-book row count also grows
131,530 → 134,197, the dedupe-release effect `CLAUDE.md` already warns about: a dropped signal
never claims the suppression window, so this gate creates candidates as well as removing them
(full-29 fires/day actually *rises*, 1.549 → 1.563).

Three sentences in `research/l1_min_pt1_r.md` are false against the code at its own commit:

1. **"no ON-arm number changes"** (the commit subject) — every ON number changes.
2. **"The ON arm never turns positive on core-11"** — at `d062da84` it is **+$28/day**.
3. **"H2 fails on both green months AND the 5% dollar test on both universes"** — post-repair
   H2's green months do **not** fall on either universe (core-11 5 → 5, full-29 4 → 4). Only the
   dollar test fails. On full-29 the failing half even moves: H1 now fails (green 8 → 7) while
   H2's green column passes.

**The decision survives.** On the corrected engine, core-11 H1 passes (green 6 → 9, $9 → $204)
and **H2 still fails**: green months hold at 5, but $/day goes −$111 → −$145, a 31% worse loss
against a 5% band. Both halves must pass, so `MIN_PT1_R` stays OFF. But it is now a much nearer
miss than the row reports — whole-book core-11 green months **11 → 14** and $/day **−$52 → +$28**,
blocked by one half's dollar column alone — and the row's write-up gives the phase chief the
opposite impression.

## 4. Still open from pass 1 — the tape's ledger and the line Austin got

`research/tape/cycles.md`'s only row and `research/tape/loop_state.json`'s only history entry
still read `-9.0 -> 29.0`, `12 -> 12`, 767 trades. Those are full-29 numbers; `loop.json`
declares the loop's universe as core-11, and nothing in `cycles.md` says otherwise — the
correction lives in a different file. Post-repair they are wrong twice over (wrong universe
*and* wrong engine). `cycles.md` is a markdown table, not loop-controller code: annotating it
was inside this row's reach even if fixing `stage_gate`'s filter is O4's.

`stage_gate` pushes its plain-English line unless `--dry-run` is passed, and it did write
`cycles.md` and `loop_state.json`, so the notification Austin received almost certainly said the
first rule tested went from losing nine dollars a day to making twenty-nine. On the universe the
call settled, the honest before/after is a loss of fifty-two dollars a day going to a gain of
twenty-eight — different numbers, and the rule was held either way. Worth one corrected line
next to whatever he saw.

Minor, not charged against this row: the book stamp carries `out` but no explicit `script`
field, so "the script that made it" is inferred from the path. That is `research/book_stamp.py`'s
schema (an O-row), not L1's.

## What the next agent should do

1. **Re-run cycle 1 properly.** The two post-repair books are committed and stamped; point
   `loop_cycle.py --stage gate` at them (with O4's `tier == "core"` filter in place) and rewrite
   `cycles.md` / `loop_state.json` from that, rather than leaving cycle 1 as a full-29 row built
   on a superseded engine.
2. Re-read the near-miss before moving on: on the settled universe the corrected rule takes green
   months from 11 to 14 and the whole book from −$52 to +$28 a day, and is blocked only by H2's
   dollar column. A variant row (a softer threshold than 1.0R, or the gate scoped to one half's
   failure mode) is worth one cycle.
3. Any future ON attempt on this flag rebuilds **both** arms at the commit it reports from. The
   pre-repair pair should stay in the tape as the toggle column it is, labelled as pre-repair.

---
---

# L1 referee, PASS 3 — REFUTED (the report), decision upheld

Third-pass referee. **Builder's reported commit: `dc76f9b5`** ("bookkeeping: L1-L5 rows"),
citing the chain `e073b94a` (code) → `842b3f3c` (books, gate) → `af028359` (referee pass 1)
→ `d062da84` (repair) → `236b9f69` (referee pass 2) → `3d168491`. Base check at start:
`git fetch origin`; HEAD = `origin/main` = **`5e25270c`**; `1539dd7f` is an ancestor; tree
clean. Everything below is re-derived by **`research/l1_referee3.py`** (committed beside this
file), which imports neither `loop_cycle.py`, `g72_suppress_price.py`, `l1_referee.py` nor
`l1_referee2.py` — the day-policy unit, the month buckets, the green count, $/day, the
`book_id` fingerprint and the gate are all written out longhand, and the flag's *semantics*
are checked against raw archived bars rather than against any book.

**Verdict: refuted.** The decision (hold, `MIN_PT1_R` default `0`/OFF) is right on every
universe and on both engines, and I could not break it. **The builder's report is refuted on
three counts**: it reports the row as *upheld* by citing another row's referee commit, it
republishes the superseded pre-repair ON numbers as the row's result, and three of its
headline claims are false against the code that is actually in the tree.

## 1. The row was never upheld — the cited commit is L2's referee

The builder's report says the row was "refereed twice … then **upheld** on re-derivation
(`3d168491` referee pass 2 upheld)". `3d168491` is **row L2's** referee:

    3d168491  L2 referee (pass 2): upheld -- the repair's core-11 numbers reproduce to the
              dollar under independent code (-$52 -> -$57/day whole, H1 +$9 -> -$8 fail, …)

L1's referee pass 2 is **`236b9f69`**, and its subject reads:

    236b9f69  L1 referee (pass 2): refuted -- the repair's "no ON-arm number changes" is
              false; rebuilt at d062da84 the core-11 ON arm goes -$52 -> +$28/day and
              11 -> 14 green, H2 dollar column still holds it OFF

Both L1 referee passes on record are **refuted**. The row's own TASKS.md line (`dc76f9b5`)
correctly says "L1 refuted"; the report to the dispatcher says upheld. A refuted row reported
as upheld is the one failure mode the different-model referee rule exists to catch, so this
alone is a refutation.

## 2. The published numbers describe code that is no longer in the tree

`d062da84` moved the gate below `self._apply_x_lift(sig)` — the fix pass 1 asked for — and
that move is in the shipped engine at HEAD (`signal_runner.py:2959-2983`). The books the
report cites (`book_MIN_PT1_R_{off,on}.json.gz`, stamped commit `e073b94a`) were built
**before** that move. Pass 2 rebuilt both arms at `d062da84`
(`book_MIN_PT1_R_{off,on}_postfix.json.gz`); the report ignores them and republishes the
pre-move pair.

Unit = `up_to_3_stop_win_or_2loss` · fill = **close** (market at the close of the signal bar,
`entry_fill.ENTRY_FILL`) · exit = shipped engine, 1R hard stop resting exactly 1R from entry
filled on the intrabar touch, `SCALE_PLAN=hod_then_runner_be`, `LOSS_HALT` on · window
2024-09-04..2026-09-04, 499 sessions · 1R = $1,000 · script `research/l1_referee3.py`.

**core-11 (`universe.CORE_SYMBOLS`, the settled universe)**

| | trades | $/day | mean R | win% | green | months | fires/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF (= R3 baseline, both engines) | 769 | −$52 | −0.0335 | 45.0% | 11 | 25 | 1.541 |
| ON **as the report publishes it** (pre-move) | 751 | −$29 | −0.0195 | 44.6% | 11 | 25 | 1.505 |
| ON **at the shipped code** (post-move) | 732 | **+$28** | 0.0193 | 33.9% | **14** | 25 | 1.467 |
| H1 OFF | 382 | $9 | 0.0057 | 43.7% | 6 | 12 | 1.540 |
| H1 ON, published / shipped | 368 / 353 | $107 / **$204** | 0.0721 / 0.1434 | 45.1% / 36.1% | 7 / **9** | 12 | 1.484 / 1.423 |
| H2 OFF | 387 | −$111 | −0.0722 | 46.3% | 5 | 13 | 1.542 |
| H2 ON, published / shipped | 383 / 379 | −$164 / −$145 | −0.1076 / −0.0964 | 44.1% / 31.9% | **4 / 5** | 13 | 1.526 / 1.510 |

**full-29 (what `cycles.md`'s L1 row still prices)**

| | trades | $/day | green | months |
|---|---:|---:|---:|---:|
| OFF (both engines) | 773 | −$9 | 12 | 25 |
| ON, published / shipped | 767 / 780 | $29 / **$84** | 12 / **11** | 25 |
| H1 ON, published / shipped | 377 / 380 | $201 / $271 | **9 / 7** | 12 |
| H2 ON, published / shipped | 390 / 400 | −$141 / −$99 | **3 / 4** | 13 |

Every published cell reproduces exactly under this third implementation — pre-move core-11
769/751, −$52/−$29, 11/11; full-29 773/767, −$9/$29, 12/12; and pass 2's post-move figures
reproduce exactly too. **The arithmetic is sound in all three implementations; it is the
engine the ON book describes that is out of date.**

Three sentences in the builder's report are therefore false against the tree at HEAD:

1. **"The ON arm never turns positive on core-11."** At the shipped code it is **+$28/day**,
   and whole-book green months go **11 → 14**.
2. **"H2 fails on both green-months and >5% dollar regression."** At the shipped code H2's
   green months **hold at 5 → 5** on core-11 and **4 → 4** on full-29. Only the dollar column
   fails. The report's own strengthening of this line ("the dollar test fails on its own too")
   is the half that survives; the green-months half does not.
3. **"H1 passes on both universes."** At the shipped code full-29 **H1 fails** (green 8 → 7)
   while H2's green column passes — the failing half swaps universes.

Also wrong in direction, not only in size: **"the gate removes almost no fired candidates"
(fires/day 1.549 → 1.537)**. At the shipped code, full-29 fires/day **rises**, 1.549 → 1.563.
Dropping a signal releases the dedupe suppression window (`DEDUPE_FIRES_ONLY`: only a *fired*
signal claims it), so this gate creates candidates as well as removing them — ON-book rows
131,530 → 134,197, the effect `CLAUDE.md` already warns about for any C-cap gate here.

Skip accounting moves the same way and re-derives exactly: tagged rows **9,283 → 14,929**
(core 3,914 → 6,731), of which would-have-traded-in-OFF **1,082 → 2,927** (core 475 → 1,367),
mean R of that slice −0.0647 → −0.0570. The pre-move tagged set is graded C 4,699 / B 4,484 /
A 100 and **zero X** — the fingerprint of a gate running before the lift; post-move B nearly
triples (10,363).

**The decision survives all four gate evaluations.** pre-move core-11 hold (H2 fails both),
pre-move full-29 hold (H2 fails both), post-move core-11 hold (H2 dollar −$111 → −$145, a 31%
deeper loss against a 5% band), post-move full-29 hold (H1 green 8 → 7). `MIN_PT1_R` stays
OFF. But at the shipped code it is a **much nearer miss than the row reports** — core-11
−$52 → +$28/day and 11 → 14 green, blocked by one half's dollar column alone — and the report
hands the phase chief the opposite impression.

## 3. The tape still publishes the wrong row for L1

`research/tape/cycles.md`'s L1 row and `loop_state.json`'s cycle 1 are unchanged since
`842b3f3c`:

    | 2026-09-05 | the 1R first-target rule | MIN_PT1_R | hold | -9.0 -> 29.0 | 12 -> 12 |
      pass | fail | 767 | book_MIN_PT1_R_off.json.gz | book_MIN_PT1_R_on.json.gz |

Those are full-29, pre-move numbers. `loop_cycle.py::apply_universe_filter` has since landed
(L2's referee repair), and **every other row in the same table is core-11** — L1 is now the
only row in the ledger measured on a different universe and a superseded engine, with no
annotation in the file itself. `research/tape/README.md` and Phase T read this table. Two
lines of annotation, or a `--stage gate --dry-run` re-run against the postfix books, closes it;
neither is loop-controller code and both were inside this row's reach.

## 4. What I checked and could NOT break

- **OFF book identity.** `book_MIN_PT1_R_off.json.gz` `book_id` **`2c39ced2697c26cc`** —
  byte-for-byte the R3 baseline's (`loop.json baseline_book_id`, `baseline_2026-09-05.json.gz`),
  fingerprint recomputed here rather than read from the stamp. The postfix OFF book is the
  same id, so the `_apply_x_lift` reorder is a true no-op when the flag is `0`.
- **Stamp diff is exactly one flag.** OFF → ON and OFFPOST → ONPOST both differ in
  `signal_runner.MIN_PT1_R` `0.0 → 1.0` and nothing else. OFF → OFFPOST differ in **no** flag.
  Windows, sessions (499) and `entry_fill` (`close`) match across all five books;
  `dirty_engine_py: []` on every one; stamp commits `e073b94a` / `d062da84` are both ancestors
  of HEAD.
- **Semantics against raw bars, not against a book.** For 20 rows the ON book tagged skipped
  and 20 it fired, I reloaded `data_archive/<SYM>/<DAY>.csv`, took the RTH bars up to and
  including the entry minute, and recomputed the session extreme: **20/20 skipped rows have
  first-scale-point < 1R from entry, 20/20 fired rows have ≥ 1R**, no exceptions. This is the
  rulebook sentence `omen_recall.py` returns, dated 2026-09-05: *"**RR gate: first scale point
  (HOD/LOD) must be >= 1R from entry.** Because: 'we dont want to get in on a candle close of
  HOD/LOD because thats always our first scale point, then the RR is shot.'"* — and the spec's
  settled row, *"skip the signal unless the first scale point (HOD/LOD) is ≥ 1R from the
  entry"*. The code **skips** (`status="skipped"`, `return`), it does not cap to C; correct,
  a capped C still trades. The measured point is LADDER PT1: `signal_runner.py:3098-3108` sets
  `session_hi/lo = max/min` over `self.candles`, `backtest_week.py:1393` sets
  `runner.candles = candles[:i+1]` immediately before `detect_signals()`, and
  `backtest_week.py:1486/1491` computes `scale_level` as the identical expression under
  `SCALE_PLAN=hod_then_runner_be`. The `direction` key the gate reads is the one
  `signal_runner` actually sets (`"direction"`, not the book's exported `"dir"`) — checked,
  because reading the wrong key would silently treat every call as a put.
- **Default matches the decision.** `MIN_PT1_R = float(os.getenv("MIN_PT1_R", "0") or "0")`
  (`signal_runner.py:258`) — OFF, and the decision is hold. Listed in
  `research/book_stamp.py` `FLAG_SOURCES` (line 92) and present in all five stamps.
- **Gate placement is genuinely fixed.** The block sits at `signal_runner.py:2971`, after
  `self._apply_x_lift(sig)` at 2959, mirroring `S_CLASSIFIER` below it.
- **Sample size.** No cell carrying a verdict is under 30 trades or 12 months; the smallest is
  core-11 post-move H1 ON at 353 trades over 12 months. Whole-book cells run 732–780 trades
  over 25 months. The whole-book move is still well inside the ±1.58R error bar this project
  measures on nearly every A/B — the decision rests on the half-gate, not on the headline.
- **One change per row.** `e073b94a` = `signal_runner.py` + `research/book_stamp.py` (one
  flag); `d062da84` = `research/l1_min_pt1_r.md` + `signal_runner.py` (one block moved, no new
  logic); `842b3f3c` = the write-up, two books, the ledger. No engine file outside scope.
- **No mark file touched** by any commit in the chain (`e073b94a`, `842b3f3c`, `af028359`,
  `d062da84`, `236b9f69`, `ba639df0`, `dc76f9b5`) — checked by name against every corpus in
  `CLAUDE.md`'s list. `git status` clean apart from this pass's own two files.
- **Verify gate, run by me at HEAD `5e25270c`:** `research/regression_gate.py` PASS (no
  baseline-fired mark went silent; any_signal 75→80, s_grade 5→25);
  `research/test_runner_stop.py` ok, 70 checks; `research/test_universe_single_source.py` ok,
  29 symbols, no private lists. All exit 0.
- **Plain English.** `cycles.md`'s label reads "the 1R first-target rule" and the pushed line
  carries no flag names or ticket ids. The wording is fine; the numbers in it are not.

## 5. Residual defects, ranked

1. The report claims the row was upheld; both L1 referee passes on record are refuted, and the
   commit cited as the upholding pass belongs to row L2. (§1)
2. The report's ON numbers, and `TASKS.md`'s L1 line under commit `d062da84`, describe an
   engine that commit changed. The three false sentences in §2 follow from that. (§2)
3. `cycles.md` / `loop_state.json` cycle 1 still publish full-29 pre-move numbers under a
   core-11 loop config, unannotated, while every sibling row is core-11. (§3)
4. Not charged against this row: the book stamp carries `out` but no explicit `script` field,
   so "the script that made it" is inferred from the path — a `book_stamp.py` schema gap.

## What the next agent should do

1. Re-run cycle 1 against `book_MIN_PT1_R_{off,on}_postfix.json.gz` with the now-fixed
   `apply_universe_filter`, and rewrite `cycles.md` / `loop_state.json`'s L1 row from that.
   No rebuild is needed; both books are stamped and committed.
2. Correct `research/l1_min_pt1_r.md` and `TASKS.md`'s L1 line to the post-move figures, or
   label the existing ones "pre-reorder engine" beside them.
3. Read the near-miss before moving on: at the shipped code, on the settled universe, this rule
   takes the whole book from −$52 to +$28 a day and green months from 11 to 14, held OFF by one
   half's dollar column alone. A softer threshold than 1.0R is worth one cycle — and that cycle
   must rebuild **both** arms at its own commit.

---

# L1 referee, pass 4 — REFUTED (decision upheld, the write-up is not)

**Builder commit under review: `f298369f`** ("L1 repair: fix pass-3 referee defects"),
HEAD and `origin/main` at the time of this pass. Base check: `1539dd7f` is an ancestor of
HEAD, HEAD equals `origin/main`. Referee code: **`research/l1_referee4.py`** (committed
beside this file; the earlier passes' `l1_referee.py`, `l1_referee2.py`, `l1_referee3.py`
are left untouched as evidence). Nothing in `l1_referee4.py` imports `loop_cycle.py` or
`g72_suppress_price.py` — the unit, the halves split, the month-green count, the $/day
divisor and the gate are re-implemented from their written definitions, so an arithmetic
bug shared by the builder and the controller cannot hide.

**Verdict: refuted.** The decision — *hold, `MIN_PT1_R` stays OFF* — reproduces on all four
gate evaluations and is correct. But the repair, which existed only to remove false
sentences, published a new one, built its numbers on a tree it did not disclose was dirty,
and left the one program that renders the L1 arm reading the superseded book without
flagging it.

## Everything that reproduces

Unit `up_to_3_stop_win_or_2loss` (up to 3 fired-and-traded signals a day in arrival order,
stop after the first win or the second loss; candidate pool = fired-and-traded plus the
two-loss halt's own rows). Fill **close**. Exit **the shipped engine** — 1R hard stop as a
resting order filled on the intrabar touch, `SCALE_PLAN=hod_then_runner_be`, loss halt on.
Universe **core 11** (`loop.json` `universe.row_filter`, `tier == "core"`), full 29 shown
beside it. 499 sessions, 2024-09-04..2026-09-04. 1R = $1,000. Script
`research/l1_referee4.py`.

| engine · universe | OFF $/day · green | ON $/day · green | ON trades | H1 | H2 |
|---|---:|---:|---:|---|---|
| post-move (`d062da84`) · core 11 | −$52 · 11/25 | **+$28 · 14/25** | 732 | pass (6→9 green, $9→$204) | **fail** (green 5→5, $−111→$−145) |
| post-move (`d062da84`) · full 29 | −$9 · 12/25 | +$84 · 11/25 | 780 | **fail** (green 8→7) | **fail** (green 4→4, $−89→$−99) |
| pre-move (`e073b94a`) · core 11 | −$52 · 11/25 | −$29 · 11/25 | 751 | pass | fail (green 5→4, $−111→$−164) |
| pre-move (`e073b94a`) · full 29 | −$9 · 12/25 | +$29 · 12/25 | 767 | pass | fail (green 4→3, $−89→$−141) |

Every cell above matches the builder's corrected tables to the dollar. Also confirmed:

- **The OFF book is the baseline.** `book_MIN_PT1_R_off.json.gz` and
  `book_MIN_PT1_R_off_postfix.json.gz` both recompute to `book_id 2c39ced2697c26cc`, equal
  to `research/tape/loop.json`'s `baseline_book_id` and to the baseline book itself. Every
  stamped `book_id` recomputes to its stamped value (5 of 5).
- **One flag apart.** The ON stamp differs from its OFF stamp in exactly one entry, both
  pairs: `signal_runner.MIN_PT1_R` `0.0 → 1.0`. Nothing else moved.
- **The semantics are the rulebook's.** Austin, 2026-09-05 (`omen-rulebook.md`, via
  `omen_recall.py`): *"RR gate: first scale point (HOD/LOD) must be >= 1R from entry"*,
  from *"we dont want to get in on a candle close of HOD/LOD because thats always our first
  scale point, then the RR is shot."* The spec's settled row says the same. The code
  (`signal_runner.py:2971-2983`) skips — does not cap — a signal whose session HOD (call) /
  LOD (put) as of the signal bar sits under `MIN_PT1_R × |entry − stop|`, and
  `hod_then_runner_be` really does scale its first rung at that extreme
  (`backtest_week.py:149-158`). Candles are RTH-only (`polygon_feed.rth`, premarket
  excluded), so "session" means the session. Re-derived straight from
  `data_archive/<sym>/<day>.csv` on 40 tagged and 40 fired rows: **80/80 agree**, 0 disagree.
- **The default matches the decision.** `signal_runner.MIN_PT1_R` imports as `0.0` at HEAD;
  `.env` carries `MIN_PT1_R=0`. A held research arm does not default on, and this one does
  not. `MIN_PT1_R` is in `research/book_stamp.py` `FLAG_SOURCES`.
- **Sample size.** Every cell clears the floor: whole 769/732 trades over 25 months, H1
  382/353 over 12, H2 387/379 over 13. No verdict rests on a thin cell.
- **The verify gate is green at `f298369f`** — `regression_gate.py`, `test_runner_stop.py`
  (70 checks), `test_universe_single_source.py` (29 symbols, no private lists), run by me.
- **No mark file was touched** by any L1-era commit (`e073b94a`, `d062da84`, `ba639df0`,
  `529ca50b`, `f298369f`).
- **The two deleted scratch books were duplicates, not content.**
  `book_MIN_PT1_R_POSTFIX_{off,on}.json.gz` at `529ca50b` are blobs `1967f487…` / `da497c58…`
  — byte-identical to `book_MIN_PT1_R_{off,on}_postfix.json.gz` still at HEAD. Nothing lost.
- **The line Austin would see is plain English.** `loop_cycle.py`'s ntfy push uses the row's
  label ("the 1R first-target rule"), never the flag name.

## DEFECT 1 — a new false sentence, in the repair that existed to remove false sentences

`research/l1_min_pt1_r.md:167-169`:

> full-29 goes -$9 -> +$84/day, 12->11 green, but there **H1 fails** (8->7 green) while H2
> passes -- the failing half swaps universes between the two engines.

**H2 does not pass on full-29 at the post-move engine.** Its green column holds (4 → 4), but
the gate is green months *and* the 5% dollar band, and $/day goes **−$89.19 → −$99.35**, an
11.4% deeper loss. Rounded or unrounded, that fails. On full-29 post-move **both halves
fail**; the failing half does not swap universes, and the claim that it does is the whole
point of the sentence.

Pass 3's own wording was narrower and correct — "H2's **green column** passes"
(`research/l1_referee.md:296-298`). The repair widened a statement about one column into a
statement about the gate verdict. That is the same error class pass 3 charged (a headline
that outruns what was measured), reintroduced in the fix for it, which is why this pass is
refuted rather than upheld on a technicality.

## DEFECT 2 — the shipped-code numbers were built on an undisclosed dirty tree

Both post-move books stamp `git.dirty_py_count: 1` (`dirty_engine_py: []`). Neither
`research/l1_min_pt1_r.md` nor the dispatcher report says so; they are presented as the
shipped-code figures full stop. The stamp records the count but not *which* file, so the
disclosure cannot be reconstructed after the fact — it had to be written down at the time.
The pre-move books are clean (`dirty_py_count: 0`), which makes the omission louder, not
quieter: the arm the row now leads with is the one built dirty.

## DEFECT 3 — the tape still renders the superseded ON book, and this repair did not flag it

`research/build_tape.py:236` feeds `book_MIN_PT1_R_on.json.gz` — the **pre-move** arm,
`book_id 04b7f4f9778fc72a` — as the tape's `L1_on` source, and stamps it with
`flag_decision("MIN_PT1_R")`, which now reads the *corrected* row. So `omen-tape.html`
labels the superseded book with the corrected verdict. The repair fixed `cycles.md` and
`loop_state.json` and correctly declined to edit `TASKS.md` **while naming it**; it did not
name this one, and this one is the page Phase T and the summary artifact are built from.
Editing `build_tape.py` belongs to T1, not to L1. Disclosing it belonged here.

## Three things the row measured and did not say

Not charged as defects — the row's claims are not wrong about them, it is silent — but the
phase chief needs all three before deciding whether to spend a cycle on a softer threshold.

1. **The headline swing is indistinguishable from zero.** Paired by calendar day over the
   499 sessions, core-11 post-move: observed **+$79.8/day**, bootstrap 95% CI
   **−$83 to +$245**, 16% of 4,000 resamples at or below zero. "−$52 → +$28" is one draw
   from that interval. This is the project's usual result and it should be stated beside the
   number, not left for the referee.
2. **The ON arm hits the 2:1 target and loses the win rate to do it.** Post-move core 11:
   avg win **$2,004** / avg loss **$1,000** = **2.004** against OFF's 1.119, with the win
   rate falling **45.0% → 33.9%** (248 wins, 483 losses of 732). One of the call's three
   targets is "average winner = 2× average loser"; this arm is the first thing in the tape
   to reach it, and the row does not mention it.
3. **The skip is invisible in the book's own status column.** All 14,929 `MIN_PT1_R` rows
   land in `status: "skipped_tight_stop"`; only the free-text `reason` distinguishes them
   from a genuine tight-stop skip. Any downstream count of tight-stop skips on the ON book
   is really two causes added together.

## What the next agent should do

1. Fix the sentence at `research/l1_min_pt1_r.md:167-169`: on full-29 post-move **both**
   halves fail the gate (H1 on green 8→7, H2 on the dollar column −$89 → −$99). Nothing else
   in that section needs to move.
2. Add the dirty-tree disclosure for `book_MIN_PT1_R_{off,on}_postfix.json.gz`, and — since
   the stamp does not record which file — rebuild both arms clean before any *new* L1 number
   is published. The hold stands on the books as they are; a ship never could.
3. Hand T1 the `build_tape.py:236` line. One-line change, not L1's to make.
4. If a softer threshold gets a cycle, it must rebuild both arms at its own commit, on a
   clean tree, and report the interval with the point estimate.
