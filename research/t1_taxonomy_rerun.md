# t1_taxonomy_rerun — omen-3.9 T1

Regenerated taxonomy after restructuring `classify_no_detection` so the order
block is evaluated **before** `no_break_retest` is assigned. Previously the
function returned `no_break_retest` the instant `detect_break_retest` was falsy,
so `detect_order_block_setup` (the One Candle Rule, per
`SignalType.ONE_CANDLE_RULE`) was never reached and could not appear in the
taxonomy at all. Both setups are now evaluated first, then a label is chosen.
Engine code is unchanged; this row touches `research/miss_autopsy.py` only.

One new reason was added to the vocabulary — `no_setup_any` — for the bar where
break-and-retest is falsy **and** no order block exists on either side (nothing
the engine knows how to trade). The existing reason strings are unchanged.

New semantics of `classify_no_detection`:

- B&R falsy **and** both OB sides `None` -> `no_setup_any`.
- B&R falsy **but** an order block exists -> `no_break_retest`, detail begins
  `OB present: <bullish/bearish>` (the candidate One Candle Rule entries).
- B&R truthy **and** both OB sides `None` -> `no_order_block` (unchanged).
- both present, neither built a signal -> `no_break_retest` residual (unchanged).

## Reason x tier (re-run over the 159 marks; sorted by S column, descending)

| reason | S | A | X | total |
|---|---:|---:|---:|---:|
| detected | 10 | 6 | 6 | 22 |
| no_setup_any | 29 | 22 | 4 | 55 |
| vetoed_htf | 10 | 12 | 5 | 27 |
| fired_wrong_bar | 10 | 6 | 1 | 17 |
| vetoed_stop_too_tight | 8 | 8 | 3 | 19 |
| no_reference_level | 7 | 5 | 2 | 14 |
| vetoed_candle_colour | 2 | 0 | 1 | 3 |
| no_break_retest | 1 | 1 | 0 | 2 |
| too_few_candles | 0 | 0 | 0 | 0 |
| consolidation_early_return | 0 | 0 | 0 | 0 |
| no_order_block | 0 | 0 | 0 | 0 |
| not_armed_84 | 0 | 0 | 0 | 0 |
| vetoed_stop_too_wide | 0 | 0 | 0 | 0 |
| vetoed_pa_grade_D | 0 | 0 | 0 | 0 |
| **total** | **77** | **60** | **22** | **159** |

`detected` is not a miss (the engine fired within +/-2 bars) but is shown so the
vocabulary table is complete.

## Grep lines (the runner greps for these)

no_break_retest_S: 27 -> 1
ob_present_S: 1

`27` is the omen-3.8 baseline figure for `no_break_retest` S marks (the "27
no_break_retest S marks" of `research/v38_verdict.md` / `t4_geometry_fix.md`).
On the current omen-3.9 priority-pools data the old code actually produced 30
(`research/miss_autopsy.md` at HEAD before this row: `no_break_retest | 30 | 23
| 4 | 57`); the 3.9 data commit added 3 such S marks. So the true movement on
current data is 30 -> 1, consistent with the 27-baseline drop reported above:
29 of those marks had no order block on either side and move to `no_setup_any`,
and the single remaining `no_break_retest` S mark is the lone One Candle Rule
candidate — `SPY 2025-03-18` (bearish order block). Either way the after-number
(1) is well under the 27 ceiling the row's done-when requires.

`ob_present_S` = the count of S marks now labelled `no_break_retest` whose
detail begins `OB present:` = **1**.

## How many of 3.8's seek_* marks now show `OB present:`

`research/t4_geometry_fix.md` split the 3.8 `no_break_retest` S marks into 6
`seek_break` (pre-window breaks), 6 `seek_leave` (chop-on-level, rejected by
design), and 17 `seek_retest` (genuine no-return). T8 cites the count of those
marks that now carry an order block — the candidate One Candle Rule entries
Austin is asked to confirm by eye ([[omen-3.9-homework]]).

Of those 29 marks (17 `seek_retest` + 6 `seek_leave` + 6 `seek_break`):

- **0 of 6 `seek_break`** now show `OB present:` — all six have no order block
  on either side and fall to `no_setup_any`.
- **0 of 6 `seek_leave`** now show `OB present:` — all six fall to `no_setup_any`.
- **1 of 17 `seek_retest`** now shows `OB present:` — `SPY 2025-03-18` (ei13),
  which carries a bearish order block. The other 16 fall to `no_setup_any`.

So **exactly 1** of the 29 marks now shows `OB present:` — `SPY 2025-03-18`. It
is the sole mark among 3.8's `no_break_retest` S set where an order block
exists without a break-and-retest, i.e. the only bar the One Candle Rule could
have caught that the old taxonomy was structurally blind to. Every other mark
in that set genuinely has neither setup, which is why the re-run's
`no_break_retest` S column collapses to 1 and a new `no_setup_any` bucket of 29
S marks appears.

## Method

Detection is the engine's own `SignalRunner.detect_signals` replayed bar-by-bar
via `research/t4_engine_recall.py`, exactly as `research/miss_autopsy.md`. The
only change is the labelling order inside `classify_no_detection`: both
`detect_break_retest` and `detect_order_block_setup` are evaluated before a
reason is chosen, instead of short-circuiting to `no_break_retest` on a falsy
break-and-retest. No engine code (`detect_break_retest`,
`detect_order_block_setup`, `omen_bot.py`, `signal_runner.py`) was changed.
