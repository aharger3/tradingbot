# L4 — the 15-minute structure trend test (`TREND_DEF=structure15`)

**Rule, as the call settled it (2026-09-05):** *"trend = 15-minute structure (higher
highs / higher lows, or the reverse) on the 1m chart -- no indicator."* (`omen-rulebook.md`,
Decided 2026-09-05.) `research/omen_recall.py` confirms this is the settled semantics, word
for word.

**What was missing before this row.** Neither OCR (`research/downgrade.py::find_ocr`) nor
either 84%-rule block in `signal_runner.py` ever computed a real trend — both simply
*assumed* the trade direction **is** the trend (an uptrend's OCR candle is "the down
candle"; a stopped-out call reclaiming is "with the trend" only because it is a call).
`TREND_DEF=structure15` is the first actual read.

**What was built.** `signal_runner.structure15_trend(candles)` — a pure function, no new
state — aggregates completed 1-minute candles into consecutive 15-candle buckets from the
session start (a partial trailing bucket is dropped) and compares the last two buckets' own
high/low: higher-high-and-higher-low = `'bullish'`, lower-high-and-lower-low = `'bearish'`,
anything else (inside/outside bar, fewer than two full buckets) = `None` (abstain, same
convention as `daily_trend_bias`). `SignalRunner._trend_ok(is_long)` is a no-op (`True`)
unless `TREND_DEF == "structure15"`, and a no-op on `None` (unresolved trend never blocks a
trade — absence of a read is not evidence against it). Wired as an added `and` condition at
the four emission sites that assumed direction == trend: the OCR long/short blocks
(`signal_runner.py`, order-block detector) and both 84%-rule long/short blocks. `TREND_DEF`
is stamped in `research/book_stamp.py`'s `FLAG_SOURCES`. Default is `"off"` — byte-identical
to today; landed and verified OFF first (commit `355d7cc0`).

## The gate result: **HOLD**

| half | $/day before | $/day after | green months before | green months after | verdict |
|---|---:|---:|---:|---:|---|
| H1 (2024-09-04..2025-08-31) | $9 | -$30 | 6/12 | 5/12 | **fail** (green months dropped) |
| H2 (2025-09-01..2026-09-04) | -$111 | -$91 | 5/13 | 5/13 | pass |
| whole | -$52 | -$61 | 11/25 | 10/25 | (informational; the gate is per-half) |

Decision: **hold**, because H1 fails the no-regression gate on **both** columns: the
green-month count drops (6→5/12, an automatic fail on its own) and the dollar column also
misses its tolerance (+$9/day → -$30/day). Neither column passed; this is not a case where
the dollar column would have passed absent the green-month rule. `TREND_DEF` stays at its
current default (`"off"`). `research/tape/loop_state.json` cycle 4, `consecutive_holds`: 4,
`target_met`: false, `stop`: false.

- **fill**: close — market at the close of the signal bar (`entry_fill.ENTRY_FILL` default)
- **exit**: shipped engine — 1R hard stop resting at the level, intrabar-touch fill,
  `SCALE_PLAN=hod_then_runner_be`, account-wide two-loss halt on
- **unit**: `up_to_3_stop_win_or_2loss` (his day policy) on `universe.CORE_SYMBOLS` (11
  symbols, `tier=='core'`), 499 sessions 2024-09-04..2026-09-04
- **trades**: 769 (OFF) / 768 (ON) whole-book; 382/381 (H1), 387/387 (H2)
- **script**: `research/loop_cycle.py --config research/tape/loop.json --flag TREND_DEF
  --on structure15 --stage build|gate`
- **books**:
  - OFF: `research/tape/book_TREND_DEF_off.json.gz` (fingerprint-matches the R3 baseline
    `2c39ced2697c26cc` — confirmed at build time, code landing changed nothing at the
    default)
  - ON: `research/tape/book_TREND_DEF_on.json.gz`

Whole-book detail (mean R, avg win/loss), same unit/fill/exit as above:

| arm | trades | mean R | win% | avg win | avg loss | avg win/avg loss | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| OFF (default) | 769 | -0.0335 | 45.0% | $801 | $716 | 1.119 | -$52 |
| ON (structure15) | 768 | -0.0396 | 45.2% | $780 | $715 | 1.091 | -$61 |

**Sample-size rule applied:** both halves clear the 30-trade / 12-month floor (382/387
trades, 12/13 months), so this is a real verdict, not "not enough." The whole-book move
(-$52 → -$61, a $9/day drop) is inside the project's own ±$1.58R error bar and is reported
for completeness only — the gate ran, and failed, on the halves.

## How many signals flip direction-eligibility

Counted on the **fired** rows of the two stamped books (`status=='fired'`, `tier=='core'`,
same symbol/day/entry-minute/direction key), OFF vs ON. This is **not** exactly the
population the gate can remove — `_trend_ok` is wired only at the OCR and 84%-rule
emission sites (`signal_runner.py`), never at `break_and_retest` (`setup_label` `BR+OCR`,
3,695 fired core rows in the OFF book, 14x the size of the two gated setups combined) — but
`break_and_retest` still changes row-for-row between the two books (OFF 4,329 → ON 4,332
fired, -5/+8) purely from dedupe-release on the gated setups' neighbouring levels; it is
reported below for completeness, not as something the flag directly touches:

| setup | fired OFF | fired ON | flipped ineligible (lost, OFF only) | of which traded | mean R of the flipped-and-traded set (OFF's own fill/exit) |
|---|---:|---:|---:|---:|---:|
| OCR (`one_candle_rule`) | 259 | 186 | **73** | 27 | **-0.1219R** (n=27, under the 30-trade floor — not enough for a verdict) |
| 84% rule (`reentry_84_rule`) | 53 | 39 | **18** | 3 | **-0.3947R** (n=3, not enough for a verdict) |
| `break_and_retest` (ungated, for reference) | 4,329 | 4,332 | -5/+8 (net) | — | not a direction-eligibility flip; dedupe-release only |

**Neither flipped-and-traded mean clears the 30-trade floor.** Per this row's own
sample-size rule, "the gate is removing losing trades on average" is not a supported
reading of either row — both are reported as **not enough**, not as evidence for or against
the mechanism.

**The 18 `reentry_84_rule` removals are not all direction-test removals.** Re-derived
against the raw archived 1-minute bars, bar list truncated at the signal bar
(`research/l4_referee2_bars.py`, re-run in this repair): of the 91 fired-gated rows the
gate actually removes (73 OCR + 18 84%-rule), only **87 of 91** have a trend read that
disagrees with the trade direction at the signal bar; the other **4 — all 84%-rule**
(TSLA 2026-04-17 10:30, AMZN 2025-05-02 10:26, NVDA 2026-02-10 10:25, AAPL 2025-10-23
10:53) — have a trend read that *allows* the trade (bullish call, or abstain) and are
removed only because the OCR signal that would have armed the 84%-rule setup was itself
removed by the direction test upstream. So the direction test itself removes **14** of the
18 84%-rule rows, not 18; the other 4 are cascade removals.

**The trend read abstains (`None`) on 123 of the 312 fired gated rows (39%)** — it allows
102 (33%) and blocks 87 (28%). An abstention never blocks a trade (per `_trend_ok`'s design,
absence of a read is not evidence against it), so more than a third of the population this
gate could touch, it does not touch at all.

**The read is stale by construction.** Because the trailing partial 15-candle bucket is
dropped to avoid look-ahead, the trend used at the signal bar is as old as the last
*completed* bucket — 112 of the 312 gated rows (36%) are judged on a bucket pair 10 or more
minutes old, maximum 14. This is a correct engineering choice (no look-ahead), not a defect,
but it is an implementation detail the rulebook sentence does not specify and this report
did not previously disclose.

All four counts above (bucket alignment on 277 touched sessions, 87/91 direction agreement,
the 123/102/87 reach split, and the 112/312 staleness split) are re-derived directly from
raw archived bars in this repair, independent of the two stamped books —
`research/l4_referee2_bars.py`, confirmed 0 of 277 touched sessions have an off-grid first
bar (the 15-candle buckets are genuinely clock-aligned 15-minute bars).

The 84%-rule row also shows **4 signals fired ON that never fired OFF** — this is the same
dedupe-release mechanism `research/g94_retest_book_compare.py` and
`research/g119_htf_bias_veto_ab.py` already documented for `RETEST_REQUIRED` and
`HTF_BIAS_GATE`: a capped/gated candidate is not `fired`, so it releases `backtest_week`'s
dedupe suppression window on that (symbol, day, level), and a different candidate can then
claim the slot — visible on `break_and_retest` above too, a setup this flag never gates
directly. **This dedupe-release effect explains the ON-only rows, not the whole-book
$/day move.** The whole-book -$52 → -$61 ($9/day drop, informational, inside the project's
own error bar) has not been decomposed to individual days in this row; a prior L4 report
version claimed a specific ("worse trades kept") mechanism for a similarly-sized whole-book
change and that mechanism was refuted (the referee found the change concentrated in three
specific days, not a broad quality effect) — this report now makes no mechanism claim for
the whole-book number beyond "informational, inside the error bar."

## Note on this row's own process

A `--stage gate --dry-run` re-run (to re-print the JSON for this report) still executes the
full gate logic — `--dry-run` only suppresses the ntfy push, not the state/cycle-ledger
writes — and appended a second, byte-identical `TREND_DEF` row, pushing
`consecutive_holds` to 5 and tripping a false `stop`. Caught and repaired before commit:
the duplicate row is dropped from `cycles.md` and `loop_state.json`, both carrying a note.
Lesson for the next L-row: never re-run `--stage gate` to re-inspect output; read
`cycles.md` / `loop_state.json` instead.

The referee should re-derive every number above directly from `book_TREND_DEF_off.json.gz`
and `book_TREND_DEF_on.json.gz` — nothing here is forecast.

## Scope note

`_trend_ok` is wired only at the OCR (`one_candle_rule`) and 84%-rule (`reentry_84_rule`)
emission sites. `break_and_retest` (`setup_label` `BR+OCR`, 3,695 fired core rows in the OFF
book) is emitted at a separate site and the gate never runs on it — a silent scope decision
on a population 14x larger than the one this flag touches. Not a defect in the H1/H2 gate
result (the gate's decision is unaffected either way), but material to any reading of "how
much of the book this flag governs."

## Refereed

Pass 2 (`research/l4_referee.md`) refuted the published record while upholding the
**decision** (hold). Fixed in this repair, all inside this row (report-only; no code or flag
semantics changed, both books unchanged):

1. **Removed the false mechanism claim.** "The mechanism is not 'worse trades kept,' it's
   dedupe-release" is dropped. Dedupe-release is real and explains the ON-only rows (shown
   above); it was never shown to explain the whole-book $/day change, and a similar claim on
   a similarly-sized change was independently refuted (three-day concentration, not a broad
   quality effect). The report now states no mechanism for the whole-book move.
2. **Labelled the n=27 cell "not enough."** -0.1219R (n=27) is under this row's own 30-trade
   floor; the report no longer draws "the gate is removing losing trades on average" from
   it or from the n=3 cell.
3. **Corrected "exactly the population the gate can remove."** `break_and_retest` — ungated,
   3,695 fired core rows — still moves (-5/+8) via dedupe-release; the fired-row diff table
   is not scoped to only what `_trend_ok` touches. Added the `break_and_retest` reference row
   and the scope note above.
4. **Added the cascade-removal correction.** 4 of the 18 removed 84%-rule rows have a trend
   read that itself allows the trade; they vanish because the OCR that would have armed them
   was removed upstream. The direction test itself removes 14, not 18. (`research/l4_referee2_bars.py`, re-run in this repair, confirmed: 87 of 91 gated removals are direct
   trend disagreements, 4 are cascades, all on `reentry_84_rule`.)
5. **Disclosed the abstain rate and staleness.** 123/312 (39%) fired gated rows get no trend
   opinion at all (abstain, never blocks); 112/312 (36%) get a read 10+ minutes stale
   (maximum 14) because the forming bucket is dropped to avoid look-ahead. Neither was in the
   original report.
6. **Made the H1 fail explicit on both columns**, not phrased so the dollar column reads as
   passed.

Not fixed here, out of this row's scope (pass 2's own defects, in *its* document, not this
one — `research/l4_referee.md`'s row-join arithmetic and its "remove the $9,750 trade"
counterfactual): those are the referee's report, not `l4_trend_def.md`, and are not this
row's to repair.

Decision, `TREND_DEF` default, and both stamped books are **unchanged** by this repair —
only the report's prose and disclosed diagnostics changed. Verify gate re-run green; no
python under `research/regression_gate.py` / `test_runner_stop.py` /
`test_universe_single_source.py` touched.
