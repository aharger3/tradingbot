# L1 -- the 1R first-target rule (MIN_PT1_R)

**The rule, his sentence:** *"we dont want to get in on a candle close of HOD/LOD because
thats always our first scale point, then the RR is shot."* Decided 2026-09-05, the /call 60
(quoted in `omen-10-0-spec.md`'s "What the call settled" table and `omen-rulebook.md`).

**What shipped.** `signal_runner.MIN_PT1_R` (default `0`, OFF): when set to a positive
number, any signal whose first scale point -- session HOD for a call / session LOD for a
put, the same as-of-entry-bar extreme `backtest_week`'s `hod_then_runner[_be]` scales its
first rung at (LADDER PT1) -- sits less than `MIN_PT1_R * R` from the entry is **dropped**
(`status="skipped"`, reason tagged `MIN_PT1_R`), not capped to C. A capped C still trades;
this rule does not let the signal through at all. Stamped in `research/book_stamp.py`
(`signal_runner.MIN_PT1_R`).

## The result: HELD OFF -- gate failed on H2

**Refereed correction (2026-09-05): the table below is full-29, not core-11.**
`research/loop_cycle.py::stage_gate` never reads `cfg["universe"]` from `loop.json` and
applies no `tier=='core'` filter -- it gated on all 28 symbols in the book. Fixing that
filter is row O4's (`loop_cycle.py` is shared loop-controller code, not this row's one
change); until it lands, this table is honestly labeled full-29. The **correct core-11**
column, re-derived independently from the same two stamped books
(`research/l1_referee.py`, no rebuild needed): OFF **-$52/day**, mean R -0.0335, 769 trades,
11/25 green -> ON **-$29/day**, mean R -0.0195, 751 trades, 11/25 green (H1 6->7, H2 5->4).
**The ON arm never turns positive on core-11** -- the "-$9 -> $29" full-29 headline below is
not the settled universe's number. The decision is unchanged on either universe: H2 fails
on both green months and the 5% dollar test both ways, so `MIN_PT1_R` stays OFF regardless
of which universe is used.

Every dollar figure below (full-29 table): **fill = close** (market at the close of the
signal bar, `entry_fill.ENTRY_FILL` default); **exit** = the shipped engine, 1R hard stop as
a resting order exactly 1R from entry filled on the intrabar touch,
`SCALE_PLAN=hod_then_runner_be`, account-wide two-loss halt on; **unit =
up_to_3_stop_win_or_2loss** (his day policy: up to 3 fired-and-traded signals a day in
arrival order, stop after the first win or the second loss); universe = **all 28 archived
symbols** (mislabeled `CORE_SYMBOLS` in the first cut of this file -- see correction above);
499 sessions, 2024-09-04..2026-09-04; script = `research/loop_cycle.py` (full-29) /
`research/l1_referee.py` (core-11, `research/tape/book_stamp.py` stamps both books). Books:

- OFF (`MIN_PT1_R` at its default): `research/tape/book_MIN_PT1_R_off.json.gz` --
  book_id `2c39ced2697c26cc`, fingerprint-matches the R3 baseline exactly (same commit path,
  same flags -- the code landing changed nothing on the default path).
- ON (`MIN_PT1_R=1.0`): `research/tape/book_MIN_PT1_R_on.json.gz` -- book_id
  `04b7f4f9778fc72a`.

**Full-29 (what the gate actually ran on):**

| | trades | $/day | mean R | win% | avg win/avg loss | green months | months |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book, OFF | 773 | -$9 | -0.0059 | 45.8% | 1.166 | 12 | 25 |
| whole book, ON | 767 | **$29** | 0.0188 | 45.1% | 1.273 | 12 | 25 |
| H1 (2024-09-04..2025-08-31), OFF | 378 | $72 | 0.0472 | 46.8% | 1.278 | 8 | 12 |
| H1, ON | 377 | $201 | 0.1322 | 46.7% | 1.522 | **9** | 12 |
| H2 (2025-09-01..2026-09-04), OFF | 395 | -$89 | -0.0567 | 44.8% | 1.049 | 4 | 13 |
| H2, ON | 390 | -$141 | -0.0908 | 43.6% | 1.020 | **3** | 13 |

**Core-11 (`universe.CORE_SYMBOLS`, the settled universe, `research/l1_referee.py`):**

| | trades | $/day | mean R | green months | months |
|---|---:|---:|---:|---:|---:|
| whole book, OFF | 769 | **-$52** | -0.0335 | 11 | 25 |
| whole book, ON | 751 | **-$29** | -0.0195 | 11 | 25 |
| H1, OFF | 382 | $9 | 0.0057 | 6 | 12 |
| H1, ON | 368 | $107 | 0.0721 | **7** | 12 |
| H2, OFF | 387 | -$111 | -0.0722 | 5 | 13 |
| H2, ON | 383 | -$164 | -0.1076 | **4** | 13 |

**H1 passes the no-regression gate on both universes** (full-29 green months 8->9;
core-11 6->7, $/day improves both ways). **H2 fails on both universes, on both criteria**:
green months fall (full-29 4->3, core-11 5->4) *and* the dollar column gets worse than the
5% no-regression band (full-29 -$89->-$141, core-11 -$111->-$164) -- an earlier draft of
this line said H2 failed "regardless of the dollar move," which understated it: the dollar
test fails on its own too. Because the gate must pass on both halves to ship ON, **the
default stays OFF** -- `MIN_PT1_R` lands in the code, stamped, and unused, on either
universe. `research/tape/loop_state.json`: `cycle_count: 1`, `decision: "hold"`,
`target_met: false` (full-29, per the unfixed loop_cycle.py filter; core-11 agrees).

**Fires/day before/after** (the loop's own `fires_per_day`, same unit/fill/exit/script as
above): whole book 1.549 -> 1.537 -- the gate removes almost no *fired* candidates outright
under the day-policy unit, because the day policy already caps a day at up-to-3 fires and a
dropped early candidate is very often replaced by the next arrival-order candidate on the
same day.

**How many signals the gate skips, and their mean R had they been taken.** Read at the
signal level (not the day-policy unit) across the full detected pool: **9,283 of the
131,530 ON-book signals** carry the `MIN_PT1_R` skip reason (script: `research/l1_referee.py`,
committed; the same two books, diffed on `(sym, day, et, entry, stop, dir)`). Narrowing to
the ones that **would actually have traded** in the OFF book (i.e., not already filtered by
grade, dedupe, or the loss halt):
**1,082 signals**. Their mean R, had they been taken, is **-0.065R** (win rate 47.2% on that
slice) -- consistent with the gate cutting a marginally-negative-R slice, but the day-policy
unit above shows most of what it removes gets backfilled by the next arrival-order candidate
on the same symbol-day, which is why the day-level $/day move (-$9 -> $29) is larger than
this slice's own R would predict on its own.

## Sample-size rule

773/767 trades and 25 months clears the 30-trade/12-month floor for a verdict on the whole
book and on H1 (378/377 trades, 12 months) and H2 (395/390 trades, 13 months) individually.
The verdict itself is **not enough to ship**: the whole-book move (-$9 -> $29, +0.0059R mean
R) is inside the ±1.58R error bar this project has measured for nearly every A/B here, and
the decisive fact isn't the dollar column at all -- it's the green-months regression on H2 (4
-> 3), which the no-regression gate treats as disqualifying by itself.

## What the referee can re-derive

Every number above (`before_whole`, `after_whole`, `before_h1/h2`, `after_h1/h2`, `h1.pass`,
`h2.pass`, `decision`) comes straight from `research/loop_cycle.py --stage gate`'s own JSON
output, run against the two stamped books named above -- rerun that command with
`--config research/tape/loop.json --flag MIN_PT1_R --on 1.0 --label "the 1R first-target
rule" --stage gate --dry-run` to reproduce it without re-appending the ledger.

## Refereed

`research/l1_referee.md` (commit `af028359`) refuted the first cut of this row on the
numbers while upholding the decision. Two defects, both addressed:

1. **Universe mislabel.** `research/loop_cycle.py::stage_gate` never applied the `tier=='core'`
   filter `loop.json`'s own `_comment` said cycle 1 needed, so the gate ran on all 28
   archived symbols while this file, `research/tape/cycles.md` and `loop_state.json` all
   said `CORE_SYMBOLS` (11 symbols). Fixed in this row's docs: the tables above now carry
   both universes, correctly labeled, with core-11 re-derived from the already-committed
   books via `research/l1_referee.py` -- no rebuild needed. **Fixing `loop_cycle.py`'s
   filter itself is out of this row's one-change scope** (it is shared loop-controller
   code, not the `MIN_PT1_R` flag) and belongs to row O4; until it lands, every cycle row
   in `cycles.md` and `loop_state.json` is a full-29 number under a core-11 label, this
   row's included -- `cycles.md`/`loop_state.json` are left as originally written by the
   controller for exactly that reason, and this file is the correction record for them.
   Decision is unaffected: H2 fails on both green months and the dollar test on both
   universes, so `MIN_PT1_R` stays OFF either way.
2. **X_LIFT ordering.** The gate sat *before* `self._apply_x_lift(sig)` in `_route` and only
   fired on grades outside `_SKIP_GRADES`, so none of the 4,384 X-graded rows `_apply_x_lift`
   promotes back to B (2,439 of them traded, 1,180 on core-11) were ever tested by it --
   the same ordering hazard the `S_CLASSIFIER` gate's own comment 25 lines below already
   calls out. **Fixed in this repair**: the `MIN_PT1_R` block now sits after
   `_apply_x_lift(sig)`, mirroring `S_CLASSIFIER`'s placement (`signal_runner.py`, one
   reorder, no new logic). Byte-identical on the default (`MIN_PT1_R=0`) path -- the
   reordered block is still gated on `MIN_PT1_R > 0`, so it is a no-op either side of the
   move when OFF; confirmed via `signal_runner.MIN_PT1_R == 0.0` and the unchanged
   regression/runner-stop/universe gates, all green post-move. This changes the ON-arm
   population (2,439 more rows now visible to the gate) but not the shipped default, so no
   book rebuild or re-gate was required to keep the hold decision valid; a future ON attempt
   for this flag must rebuild both books against the corrected code before it means
   anything.
3. **SWARM law-5 (script every published number).** The 9,283/1,082/-0.065R figures were
   published from an ad hoc, uncommitted query. Now cite `research/l1_referee.py`
   (committed by the referee, reruns against the same two stamped `.json.gz` books).
