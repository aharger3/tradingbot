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
