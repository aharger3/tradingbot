# The rare setups, funnel by funnel -- STATUS: script built and validated, full two-year replay incomplete

This ticket's script, `research/g81_rare_setups.py`, is written, syntax-checked, and
validated end to end on a 20-session smoke run (`--days 20`) that reproduced the expected
shape against `research/g74_ocrgates.md` and `research/p7_84_rule.py`'s own patterns. The
full 730-day two-year replay for the `default` arm was launched
(`python research/g81_rare_setups.py run --arm default --days 730 --out
research/g81_arm_default.json`, logging to `research/_g81_default_run.log`) but had not
finished writing its output when this session's time budget closed. The `confluence` arm
(`CONFLUENCE_SETUP_ROUTES=1`) was never started. **Items 1, 2 and 4 below are therefore
NOT settled on the full two-year book yet** -- everything else in this report (item 3, item
5, the funnel *shape*) is real, either because it does not depend on the replay length
(item 3 is a source-code check) or because it was measured on the existing real-router
30-card run (item 5).

**To finish:** the default-arm run may already be complete or still running --
check `research/_g81_default_run.log` and `ls research/g81_arm_default.json`. If it
finished, run the confluence arm (`... run --arm confluence --days 730 --out
research/g81_arm_confluence.json`, ONE ARM AT A TIME, same archive-contention caveat as
`p7_84_rule.py`), then `python research/g81_rare_setups.py report`, which regenerates this
file in full with every table item 1/2/4 need. Nothing further needs writing; the report
generator is done and was exercised successfully on the smoke data.

---

## What IS settled

### Item 3 -- the DIRECTION.md order-block claim: refuted, as of today

> "the order-block path demotes every B to C at the detection site, so it can never ship a
> tradeable grade on its own, and its $0.50 / 0.4%-of-price stop gates were tuned on a
> stale 12-month yfinance split."

Checked directly against `signal_runner.py`'s two order-block emit blocks (long ~line 2911,
short ~line 3184), not asserted from memory (`check_direction_claim()` in the script, and
independently confirmed by `grep -n "grade.value == .B.\|TradeGrade.C$" signal_runner.py`,
which finds the B->C demote only inside the break-and-retest blocks, never the order-block
ones):

| | in today's source |
|---|---|
| B->C demote present in the OCR path | **False** |
| flat $0.50 minimum present in the OCR path | **False** |
| 0.4%-of-price maximum stop present in the OCR path | **True** |

**The claim was true. It is not true today.** Both the demote and the flat minimum were
deleted in `43b3f59c` ("R3+R4: there is no B on the one candle rule, and no flat minimum
stop", 2026-08-29 00:50) -- twelve hours before Austin graded the 30-card deck this ticket
is scored against. The provenance half of the claim ("tuned on a stale 12-month yfinance
split") is confirmed by the deleted comment's own text, still readable in git history at
those lines: `"Austin 2026-07-10 review + 12mo split: OCR only earns its keep at A-grade
with a TIGHT stop..."`. **Only the 0.4% maximum survives.** On the 20-session smoke replay
it was already killing real setups (53 of 158 that reached emit -- the full two-year count
is pending, but the mechanism and the verdict do not depend on sample size: this gate is
still live, the other two are not). Its own provenance is still unnamed
(`research/g74_ocrgates.md` already flagged commit `e1d346ca` as having no rulebook
citation) -- that finding stands unchanged and this pass does not add anything new to it.

### Item 5 -- the 30 cards: which gate stopped the engine, per yes-card

Built from `research/g81_marks30_score.json` (the real router, already run on these exact
30 symbol-days -- `assert_real_router()` verified before that file was written). This is
real, complete, and does not depend on the pending replay.

**10 of Austin's 21 yes-cards booked in their claimed bucket; 11 did not.**

| card | bucket | his minute | gate |
|---|---|---|---|
| AAPL_2026-04-17 | 84 | 9:42 | booked (nothing stopped it) |
| COIN_2025-07-10 | 84 | 9:41 | booked (nothing stopped it) |
| INTC_2026-03-24 | 84 | 9:38 | booked (nothing stopped it) |
| META_2026-06-22 | 84 | 9:59 | booked (nothing stopped it) |
| NFLX_2026-05-26 | 84 | 9:47 | booked (nothing stopped it) |
| TSM_2026-07-07 | 84 | 9:38 | no 84-bucket fire that day -- router only accepted break_and_retest |
| ACHR_2026-06-16 | BR | 9:57 | booked (nothing stopped it) |
| AMD_2024-10-02 | BR | 9:36 | booked (nothing stopped it) |
| AMZN_2025-12-11 | BR | 9:40 | booked (nothing stopped it) |
| AVGO_2024-11-04 | BR | 9:47 | detected (raw) but graded X / skipped everywhere -- never fired |
| BABA_2024-09-05 | BR | 9:56 | booked (nothing stopped it) |
| QQQ_2024-08-26 | BR | 9:56 | detected (raw) but graded X / skipped everywhere -- never fired |
| TSLA_2025-09-03 | BR | 9:45 | detected (raw) but graded X / skipped everywhere -- never fired |
| ACHR_2026-04-13 | OCR | 10:09 | detected (raw) but graded X / skipped everywhere -- never fired |
| GOOGL_2024-10-29 | OCR | 10:47 | no OCR-bucket fire that day -- router only accepted break_and_retest |
| IWM_2026-08-06 | OCR | 9:55 | booked (nothing stopped it) |
| MSFT_2025-08-29 | OCR | 9:38 | no OCR-bucket fire that day -- router only accepted break_and_retest |
| NFLX_2025-07-08 | OCR | 9:38 | detected (raw) but graded X / skipped everywhere -- never fired |
| NVDA_2026-05-11 | OCR | 9:43 | no OCR-bucket fire that day -- router only accepted break_and_retest |
| SPY_2025-05-21 | OCR | 9:45 | detected (raw) but graded X / skipped everywhere -- never fired |
| SPY_2026-06-17 | OCR | 9:48 | detected (raw) but graded X / skipped everywhere -- never fired |

The AVGO_2024-11-04 and QQQ_2024-08-26 rows ("graded X / skipped everywhere") are exactly
the two router discards `research/g81_marks30_score.md` already named for autopsy (fired
at his exact minute, killed downstream) -- this table adds SPY_2026-06-17 to that same
shape from the OCR bucket. Full per-card detail (including no-cards):
`research/g81_cards.json`.

**Caveat on this table's `fired` column for the "84" bucket**, documented in the script:
`g81_marks30_score.json`'s `fired` list comes from `t4_engine_recall.run_day`, which
replays `detect_signals` bar-by-bar WITHOUT the armed `entry_price`/`entry_direction` state
`backtest_week.simulate_day` carries across bars for a 84%-rule reclaim. So a bucket=="84"
card can be booked with an empty `fired` list -- that is a blind spot in this particular
column, not a real gate; the `booked` column (which comes from the real `simulate_day` path)
is unaffected and is what drives the verdict in the table above.

### What the 20-session smoke run shows (directional only, NOT the two-year answer)

Run to validate the script, not to publish. Kept here only because it reproduces the shape
`research/g74_ocrgates.md` already found on an earlier commit, which is reassuring that the
instrumentation is wired correctly:

| setup | traded (13 sessions) | win rate | mean R |
|---|---:|---:|---:|
| break-and-retest | 107 | 57.0% | +0.745 |
| one-candle rule | 13 | 40.0% | +0.280 |
| 84% re-entry | 10 | 33.3% | +0.274 |

Scaled naively by 730/13 these are nowhere near "3 / 67" any more, consistent with
`research/g74_ocrgates.md`'s finding that R3/R4/R6 already fixed the two setups that
looked broken -- **but do not quote these numbers**, they are a 13-day sample and the
whole point of this ticket is the two-year, gate-by-gate table, which is the part still
pending.

The 20-session run's arm-gate funnel for the 84% rule (new instrumentation this pass, not
in `p7_84_rule.py` or `g74_ocrgates.md`) shows the shape to expect from the full run:
`stopouts 1418 -> stopouts_counted 77 -> arming_setup 77 -> grade_gate 77 -> armed 72 ->
emitted 21 -> fired 19 -> traded 10`. **The arming/grade gates are near no-ops today**
(`RULE84_ARM_ON` is every `SignalType` since R6, and the default grade gate is
unconditionally `True`) -- the bottleneck is the reclaim-detection step itself (armed 72 ->
emitted 21), not the arm gate `p7_84_rule.py` measured on an earlier, stricter commit.

---

## What is NOT yet answered

- **Item 1/2 -- the full two-year gate-by-gate funnel for all three setups**, with exact
  kill counts at every stage (`omen_bot.py`'s BR ladder, `signal_runner.py`'s OCR ladder,
  `backtest_week.py`'s 84%-rule arm ladder, all instrumented together in one replay by
  `research/g81_rare_setups.py run --arm default`). The mechanism and which single gate
  dominates ARE already known from `research/g74_ocrgates.md` (wick-only retest for OCR)
  and this session's smoke run (reclaim-detection for the 84% rule) -- only the exact
  two-year counts are pending.
- **Item 4 -- BR+OCR confluence, routed.** The script measures detections/trades/dollars-
  per-day/recall for `CONFLUENCE_SETUP_ROUTES=1` against the default (label-only) arm, and
  is ready to run; it was not started this session.
- Whether the two-year 84%-rule mean R stays negative (it was +0.274R on the 13-session
  smoke sample, not negative -- the earlier `research/g74_ocrgates.md` figure of -0.135R
  was measured on an EARLIER commit and pre-dates the working-tree changes to
  `backtest_week.py` found in this session, e.g. `DEDUPE_FIRES_ONLY` defaulting on. This is
  exactly why item 1/2 need the real two-year run rather than a citation of an old number --
  do not carry the -0.135R figure forward without re-measuring it.

## Reproduce

```
python research/g81_rare_setups.py run --arm default    --days 730 --out research/g81_arm_default.json
python research/g81_rare_setups.py run --arm confluence --days 730 --out research/g81_arm_confluence.json
python research/g81_rare_setups.py cards   # already run; research/g81_cards.json exists
python research/g81_rare_setups.py report  # regenerates this file with items 1/2/4 filled in
```

Run the two arms one at a time -- concurrent replays contend on the 1-minute archive (same
caveat `research/p7_84_rule.py` states). Each arm took roughly 8-15 minutes extrapolated
from the 20-session smoke run (20s); the working tree's `backtest_2y.py`/`backtest_week.py`
changes since the last committed run were not benchmarked at full length this session.

Nothing under `research/marks/` or any mark corpus was opened for writing. No engine
default was changed.
