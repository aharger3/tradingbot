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

Every dollar figure below: **fill = close** (market at the close of the signal bar,
`entry_fill.ENTRY_FILL` default); **exit** = the shipped engine, 1R hard stop as a resting
order exactly 1R from entry filled on the intrabar touch, `SCALE_PLAN=hod_then_runner_be`,
account-wide two-loss halt on; **unit = up_to_3_stop_win_or_2loss** (his day policy: up to 3
fired-and-traded signals a day in arrival order, stop after the first win or the second
loss); universe = `CORE_SYMBOLS` (11 symbols, rows with `tier=='core'`); 499 sessions,
2024-09-04..2026-09-04; script = `research/loop_cycle.py` (`research/tape/book_stamp.py`
stamps both books). Books:

- OFF (`MIN_PT1_R` at its default): `research/tape/book_MIN_PT1_R_off.json.gz` --
  book_id `2c39ced2697c26cc`, fingerprint-matches the R3 baseline exactly (same commit path,
  same flags -- the code landing changed nothing on the default path).
- ON (`MIN_PT1_R=1.0`): `research/tape/book_MIN_PT1_R_on.json.gz` -- book_id
  `04b7f4f9778fc72a`.

| | trades | $/day | mean R | win% | avg win/avg loss | green months | months |
|---|---:|---:|---:|---:|---:|---:|---:|
| whole book, OFF | 773 | -$9 | -0.0059 | 45.8% | 1.166 | 12 | 25 |
| whole book, ON | 767 | **$29** | 0.0188 | 45.1% | 1.273 | 12 | 25 |
| H1 (2024-09-04..2025-08-31), OFF | 378 | $72 | 0.0472 | 46.8% | 1.278 | 8 | 12 |
| H1, ON | 377 | $201 | 0.1322 | 46.7% | 1.522 | **9** | 12 |
| H2 (2025-09-01..2026-09-04), OFF | 395 | -$89 | -0.0567 | 44.8% | 1.049 | 4 | 13 |
| H2, ON | 390 | -$141 | -0.0908 | 43.6% | 1.020 | **3** | 13 |

**H1 passes the no-regression gate** (green months 8->9, $/day improves). **H2 fails**: green
months fall 4->3, which SWARM.md's gate treats as a hard fail regardless of the dollar
column (green months may never fall on either half). Because the gate must pass on both
halves to ship ON, **the default stays OFF** -- `MIN_PT1_R` lands in the code, stamped, and
unused. `research/tape/loop_state.json`: `cycle_count: 1`, `decision: "hold"`,
`target_met: false`.

**Fires/day before/after** (the loop's own `fires_per_day`, same unit/fill/exit/script as
above): whole book 1.549 -> 1.537 -- the gate removes almost no *fired* candidates outright
under the day-policy unit, because the day policy already caps a day at up-to-3 fires and a
dropped early candidate is very often replaced by the next arrival-order candidate on the
same day.

**How many signals the gate skips, and their mean R had they been taken.** Read at the
signal level (not the day-policy unit) across the full detected pool: **9,283 of the
131,530 ON-book signals** carry the `MIN_PT1_R` skip reason (script: the same two books,
diffed on `(sym, day, et, entry, stop, dir)`; ad hoc query, not committed as a script since
it only reads the two stamped books already committed this row -- rerun it from those two
`.json.gz` files if it needs reproducing). Narrowing to the ones that **would actually have
traded** in the OFF book (i.e., not already filtered by grade, dedupe, or the loss halt):
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
