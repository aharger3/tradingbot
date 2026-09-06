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
slice itself, direction only.

**Correction (this repair): the flag does delay the OCR entry.** The originally reported
"no later-bar case to time" claim was false. Comparing the first one-candle-rule signal of
the day, off vs. on, across the 174 symbol-days that keep a row in both arms
(core-11, same script, `research/l3_referee3.py`): **109 move to a later minute (median
+3 min, max +65 min), 65 are unchanged, 0 move earlier.** The flag rejects the weak-PA
candle at its own bar and the day's next one-candle-rule row (if any) becomes the kept
signal -- later in the session, not the same bar restated. Not enough to price on its own
(174 symbol-days, not a trade count), but the direction and the median/max are real and
were sitting in the same two books the whole time.

**Correction (this repair): where the -$3,090 whole-window delta comes from.** Pass 1's
claim that "the lost money is not in the OCR rows themselves" is wrong. Exact decomposition
of the unit `up_to_3_stop_win_or_2loss` total, off -$25,746/on -$28,836/day
(`research/l3_referee3.py`, `delta_decomposition`):

| | trades | $ |
|---|---:|---:|
| removed: one-candle-rule rows the flag drops from the pick list | 16 | +$2,899 (94% of the delta) |
| added: break-and-retest rows the dedupe-release mechanism lets in | 11 | -$191 (6%) |
| net | | -$3,090 |

one_candle_rule itself goes 17 trades / +$3,209 -> 1 trade / +$310. The dedupe-release
mechanism the original report leaned on is real but is a minor contributor, not the story.
Every cell above is under the 30-trade floor -- this is an arithmetic identity that explains
the delta, not a verdict on either sub-slice.

Books: `research/tape/book_OCR_RETEST_DISPLACEMENT_off.json.gz` (book_id
`2c39ced2697c26cc`, equals the baseline exactly), `research/tape/book_OCR_RETEST_DISPLACEMENT_on.json.gz`
(book_id `c29a7dd5902cf457`). Both stamped, commit `90dce640`, 2026-09-05, `dirty_engine_py: []`
**and `dirty_py_count: 1`** (a non-engine file was uncommitted at build time; no engine
module counted in `dirty_engine_py` was dirty, so no traded number is affected, but the
build was not from a fully clean tree and the original report did not say so).

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

## Refereed a second time (`research/l3_referee.md`, pass "L3 referee 3")

The number and decision survive a third independent implementation
(`research/l3_referee3.py`, imports nothing from `loop_cycle.py` / `l3_referee.py` /
`l3_referee2.py`) exactly: whole -$52 -> -$58/day (floor -$54.6), 11 -> 10 green, 769 ->
764 trades, FAIL; H1 +$9 -> -$47/day (floor +$8.5), 6 -> 5 green, 382 -> 380, FAIL; H2
-$111 -> -$68/day (floor -$116.6), 5 -> 5 green, 387 -> 384, PASS. **Decision unchanged:
HOLD, flag OFF.** Deep-equal check: OFF is byte-identical to the baseline across all
127,513 rows; book_id recomputed independently matches on both arms
(`2c39ced2697c26cc` off, `c29a7dd5902cf457` on); the stamps differ in exactly one flag key.

What was refuted was the row's write-up, not its code or its number, and both writing
defects and the disclosure gap are fixed above, in this same repair commit:

1. **"no later-bar case to time" was false.** 109 of 174 kept one-candle-rule symbol-days
   move to a later minute (median +3, max +65), 65 unchanged, 0 earlier -- and pass 2
   (`84608fb0`) had already named this exact defect before this repair; the file went
   unedited between passes and the builder's dispatcher report incorrectly said "no further
   action needed." Fixed in the OCR-only slice section above.
2. **"the lost money is not in the OCR rows themselves" was disproved.** Exact decomposition
   of the -$3,090 whole-window delta: 16 removed one-candle-rule rows account for +$2,899
   (94%), 11 released break-and-retest rows account for -$191 (6%); one_candle_rule goes 17
   trades/+$3,209 -> 1 trade/+$310. Fixed above; every cell stays under the 30-trade floor,
   arithmetic identity only, no verdict.
3. **`dirty_py_count: 1` at build time was never disclosed** alongside `dirty_engine_py: []`.
   Disclosed above; no engine module was dirty so no number changes.

Verify gate re-run after this repair: green (see command list below). No code or flag
semantics changed in this repair -- both defects were prose describing a real, already-built
result incorrectly; the fix is documentation, cross-checked against the two already-stamped,
already-committed books with a fourth independent re-derivation (this repair's confirmation
run of `research/l3_referee3.py`, output matches the numbers above to the dollar).

Verify: `python research/regression_gate.py && python research/test_runner_stop.py &&
python research/test_universe_single_source.py` -- green at repair commit.
