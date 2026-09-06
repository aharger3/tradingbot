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

Decision: **hold**, because H1 fails the no-regression gate (a green-month drop is an
automatic fail regardless of the ±5% dollar-drop tolerance). `TREND_DEF` stays at its
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
same symbol/day/entry-minute/direction key), OFF vs ON — i.e. exactly the population the
new `_trend_ok` gate can remove:

| setup | fired OFF | fired ON | flipped ineligible (lost, OFF only) | of which traded | mean R of the flipped-and-traded set (OFF's own fill/exit) |
|---|---:|---:|---:|---:|---:|
| OCR (`one_candle_rule`) | 259 | 186 | **73** | 27 | **-0.1219R** (n=27) |
| 84% rule (`reentry_84_rule`) | 53 | 39 | **18** | 3 | **-0.3947R** (n=3, not enough for a verdict) |

Both flipped-and-traded means are negative — the gate is removing losing trades on average,
which is consistent with (but does not by itself explain) the whole-book $/day *falling*
$9/day: the mechanism is not "worse trades kept," it's dedupe-release. The 84% row also shows
**4 signals fired ON that never fired OFF** — this is the same release mechanism
`research/g94_retest_book_compare.py` and `research/g119_htf_bias_veto_ab.py` already
documented for `RETEST_REQUIRED` and `HTF_BIAS_GATE`: a capped/gated candidate is not
`fired`, so it releases `backtest_week`'s dedupe suppression window on that (symbol, day,
level), and a different candidate can then claim the slot. It is a real, structural
consequence of this class of gate, not a bug in this row's code.

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
