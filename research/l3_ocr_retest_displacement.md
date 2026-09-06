# L3 -- OCR_RETEST_DISPLACEMENT (the one-candle-rule entry on the retest, with displacement)

Flag `OCR_RETEST_DISPLACEMENT` (default OFF, commit `90dce640`; repair commit follows this
file). Adds the strong-PA clause on top of retest and displacement, both already enforced
unconditionally upstream (`OB_RETEST_TYPES`, `omen_bot._has_displacement`). `OCR_STRICT`
means something else (also requires `clear_break` and `quick`) and was left untouched.

Rulebook sentence (`research/omen_recall.py`, and the spec's settled table row, which is
law): "OCR entry = retest of the OCR extreme after the break, with strong PA and
displacement (body >= STRONG_PA_MULT x avg body of prior 10, closing in the trade
direction)."

## The number

Unit **up_to_3_stop_win_or_2loss** (his day policy). Fill: honest **close**
(`ENTRY_FILL=close`). Exit: shipped engine -- 1R hard stop on the intrabar touch
(`DISASTER_STOP_R=1.0`), `SCALE_PLAN=hod_then_runner_be`, loss halt on. Universe: **core 11**
(`loop.json` `universe.row_filter`). Window 2024-09-04..2026-09-04, 499 sessions. 1R =
$1,000. Script: `research/loop_cycle.py --stage gate` (books built and priced independently
a second time by `research/l3_referee.py`, same numbers to the dollar).

| slice | $/day off -> on | green months off -> on | trades off -> on | gate |
|---|---|---|---|---|
| whole (25 months) | -$52 -> -$58 | 11 -> 10 | 769 -> 764 | fail |
| H1 (12 months) | +$9 -> -$47 (floor +$8.6) | 6 -> 5 | 382 -> 380 | fail |
| H2 (13 months) | -$111 -> -$68 (floor -$116.5) | 5 -> 5 | 387 -> 384 | **pass** |

**Decision: HOLD.** Both halves are checked; H1 fails (green months and $/day both fall
below its no-regression floor), so the row holds even though H2 passes. Flag stays OFF.

OCR-only slice, core-11, every row the detector produced (not day-policy reduced):

| | off | on |
|---|---:|---:|
| OCR detections | 3,098 | 180 (-94.2%) |
| of those, traded | 108 | 6 |
| mean R of the traded ones | -0.286 | +0.599 |

Six traded rows is a fifth of the 30-trade floor -- **not enough** for a verdict on the OCR
slice itself, direction only. Median shift to a later bar for OCR signals the flag keeps but
delays: not separately measured this row (the flag does not delay an OCR entry, it either
admits or rejects the same bar -- there is no "later bar" case to time, so this readout does
not apply to this flag; noted rather than fabricated).

Books: `research/tape/book_OCR_RETEST_DISPLACEMENT_off.json.gz` (book_id
`2c39ced2697c26cc`, equals the baseline exactly), `research/tape/book_OCR_RETEST_DISPLACEMENT_on.json.gz`
(book_id `c29a7dd5902cf457`). Both stamped, commit `90dce640`, 2026-09-05, `dirty_engine_py: []`.

## Sample-size rule

Every gate cell clears 380 trades and 12 months -- the gate itself carries a verdict on both
halves. The 6-trade OCR-traded cell does not and is reported as direction only.

## Refereed

`research/l3_referee.md` refuted this row's originally reported outcome (not its code): the
builder's background build died at 0 bytes and the report went out as `decision: not_enough`
with `h1_pass`/`h2_pass` both false and no book. The referee built both arms independently
and priced a clean **HOLD**, with **H2 passing** (not failing). This file replaces the
original report with the referee's measured numbers, confirmed here a third way by running
`research/loop_cycle.py --stage gate` against the same two committed books (identical to the
dollar).

Fixed in this repair, inside the one-change rule (a copy-to-delegate refactor plus a test,
not a new behavior):

- **omen_bot.py:531** -- `ocr_has_strong_pa` no longer re-derives the strong-PA arithmetic; it
  now calls `ocr_quality(candles, block, block_idx, break_idx, direction)["strong_pa"]`
  directly (both call sites in `signal_runner.py` already had `block`, `block_idx` and
  `break_idx` in scope). One clause, one definition now, not two that could drift.
- **research/test_t2_ocr.py** -- added an assertion that `ocr_has_strong_pa` equals
  `ocr_quality(...)["strong_pa"]` across the clean/doji/wrong-direction cases already built
  by this test, plus a standing check that `OCR_RETEST_DISPLACEMENT` is OFF by default.
- **omen_bot.py:531 docstring** -- the old "clauses the rulebook sentence never names" claim
  is dropped. It is corrected: the sentence does say "after the break", `clear_break` is
  exactly that test, and three of his marks name it directly
  (`probe_master_2026-08-29#fact_ocr_demote`, `recovered_reviews#TSLA_2026-01-23`,
  `recovered_reviews#PLTR_2026-02-18`). The conclusion (this flag implements only strong PA,
  per the spec's settled parenthetical) is unchanged and still correct; only the stated
  reasoning was wrong, and the docstring now says whether `clear_break` belongs in a future
  flag is an open follow-on question, not settled here.
- **research/tape/cycles.md / loop_state.json** -- the L3 row is now appended (cycle 3,
  `consecutive_holds: 3`), closing the referee's defect 4. Ran
  `research/loop_cycle.py --stage gate` against the already-built, already-committed books
  (rebuilt nothing, seconds to run).

Refuted, kept (cannot fix inside this row, per the referee's own note):

- Whether `clear_break` should also gate this flag is a follow-on row (a second flag), not a
  change to L3 -- the spec's settled parenthetical governs what L3 implements.
- `research/tape/cycles.md`'s pre-existing `MIN_PT1_R` row (full 28-symbol pool vs. this
  row's core-11) is the L2 referee's finding, not L3's, and is unfixed here.

Not refuted, unchanged: the flag's semantics (spec-conformant, verified against the code by
the referee section 4), the identity checks (OFF reproduces baseline byte-for-byte, ON
differs in exactly the one flag), and the verify gate (green at repair commit, re-run below).
