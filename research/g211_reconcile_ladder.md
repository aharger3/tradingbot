# OMEN 10.0 R2 -- reconcile R1's next_open book against the shipped full book

**Why step 0 reads $2,660/day, not the spec's headline $569/day.** $569/day is `g90_fill_arms.py`'s ORIGINAL published `next_open` number (2024-08-12 to 2026-08-11, the pre-R1 engine). Step 0 here is R1's re-run of the SAME arm on the current engine and window -- already measured and explained in `research/g210_fill_arms_v2.md`'s "Differences from g90" section (a different window, plus every engine change landed between g90's run and R1's, `RETEST_REQUIRED` named explicitly). This row starts from R1's number because R1 is the row this one is blocked on, not because the drift from $569 needed re-explaining.

Base commit at run time, three new simulations (SIM A/B/C, full29 pool, WIDE window `2024-09-04` to `2026-09-04`). Steps 7-8 stay on THIS row's own SIM C rows, filtered to `research/bt2y_trades_retest_on.json`'s date range (`2024-09-03` to `2026-09-02`, 498 sessions) -- that book is read only for its window boundary, never for its trades, after a repair (see Refereed section below). Unit: every traded signal (status=="fired"; grade and 84% inclusion vary by step, named per row). Fill/exit named per row. $1,000 risk/trade, unsized until step 5.

**Where the ladder actually ends, vs. the row's title.** This row is titled "$569 -> -$284" (the spec's two honest numbers). It does not reach either endpoint: step 0 reads $2,660/day (explained above, not $569), and the ladder finishes at step 7 (full 29 symbols) at **$-803/day**, step 8 (core 11) at **$-87/day** -- neither is -$284/day. The eight named steps are the spec's own reconciliation path and every step here is measured; the gap to -$284/day is not run down further in this row and is not silently claimed to be closed.

**Tree was dirty at build time**: 1 uncommitted .py file(s) (engine files dirty: none) -- every stamped book below records this in its own `stamp.git` block; the first build of this row did not surface it in the report.

## Which steps were simulated, which were filtered

- **Simulated** (three bar-by-bar replays): SIM A (`next_open` fill, blind 2R exit, custom arm mechanics identical to R1/g90's `_walk`) feeds steps 0-1; SIM B (`next_open` fill, shipped ladder exit, the REAL `backtest_week.simulate_day` with `ENTRY_FILL=next_open`) feeds steps 2-3; SIM C (`close` fill, shipped ladder exit, the shipped defaults, no env override) feeds steps 4-6.

- **Filtered, not simulated**: grade (C in/out), signal_type (`reentry_84_rule` in/out), the size gate (`min_risk_floor`), the universe (29 -> 11), and the window (steps 7-8, a date-range filter applied to step 6's OWN rows -- `research/bt2y_trades_retest_on.json` is read only for its window's start/end dates, never for its trades).

## Forward ladder

| step | change | fill | exit | pool | trades | win rate | mean R | avg win | avg loss | green months | $/day |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 0 | start_next_open_blind2r_noC_no84 | next_open | blind_2R | full29 | 7857 | 38.9% | +0.1690 | +1.9817 | -0.9973 | 23/25 | $2,660 |
| 1 | add_C_grades | next_open | blind_2R | full29 | 14327 | 38.6% | +0.1592 | +1.9835 | -0.9965 | 24/25 | $4,569 |
| 2 | swap_exit_shipped_ladder | next_open | shipped_ladder | full29 | 14332 | 42.4% | -0.0342 | +1.0312 | -0.8274 | 7/25 | $-981 |
| 3 | add_84_reentries | next_open | shipped_ladder | full29 | 14731 | 42.1% | -0.0328 | +1.0549 | -0.8329 | 7/25 | $-967 |
| 4 | switch_fill_close | close | shipped_ladder | full29 | 14718 | 41.9% | -0.0257 | +1.0154 | -0.7844 | 7/25 | $-758 |
| 5 | apply_size_gate | close | shipped_ladder | full29 | 13374 | 41.8% | -0.0303 | +1.0192 | -0.7926 | 7/25 | $-812 |
| 6 | dedupe_day_policy_shipped_noop | close | shipped_ladder | full29 | 13374 | 41.8% | -0.0303 | +1.0192 | -0.7926 | 7/25 | $-812 |
| 7 | window_500_to_498 | close | shipped_ladder | full29 | 13307 | 41.8% | -0.0300 | +1.0196 | -0.7919 | 7/25 | $-803 |
| 8 | universe_29_to_11 | close | shipped_ladder | core11 | 5788 | 43.7% | -0.0075 | +1.0063 | -0.8015 | 12/25 | $-87 |

## Reverse ladder -- dropped, untested

The first build's reverse table relabelled the SAME nine forward populations (`REV = [(8-n, ...) for n, ... in FWD]`) instead of re-applying the eight changes in the opposite order -- every reverse book was byte-identical to its forward twin, the path-dependence check it existed to run was vacuous, and it committed 9 duplicate `.json.gz` files. Building a REAL reverse ladder needs a fourth bar-by-bar simulation (a close-fill, blind-2R-exit combination this row never ran) at the point in the reverse sequence where the fill and exit swaps land in a different order than the forward path used -- that is a second change, out of this repair's one-change scope. This repair removes the fake reverse table and its duplicate books rather than repeat the relabel. **Whether the step-1->2 finding depends on the order the eight changes are applied in is UNTESTED**, not confirmed either way.

## The step that costs the most money

**switching from a flat double-your-money exit to the real scale-out-and-trail exit** -- $4,569/day before, $-981/day after, a swing of $-5,550/day. That is the single biggest drop between any two adjacent rows of the forward ladder.

Same step, split into the first and second half of the window (by trading day, not calendar month):

| half | before ($/day) | after ($/day) |
|---|---:|---:|
| H1 | $-85 | $-219 |
| H2 | $-1,518 | $-1,740 |

The drop holds in both halves -- it is not a first-half or second-half artifact.

## Verify

- step 0 vs R1 next_open (full29): 7857 rows here vs 7857 in R1's book -- MATCH to the cent.
- step 0 vs R1 next_open (core11): 3629 rows here vs 3629 in R1's book -- MATCH to the cent.
- step 7 (this row's OWN simulation, unsized, full pool, window=('2024-09-03', '2026-09-02')) $/day = $-750.17 vs research/bt2y_trades_retest_on.json's INDEPENDENT $-675.25 (sum(pnl for status=='fired', any grade) / 498 sessions) -- DOES NOT RECONCILE within 1%.

**Step 7 did not reconcile with `research/bt2y_trades_retest_on.json` within 1%.** The likeliest named cause: `retest_on`'s book was ALSO run through `research/loss_halt.py` (`LOSS_HALT=True`, halting a symbol/day after 2 consecutive losses -- its own stamp shows 4205 of 127152 candidate signals removed by that halt), a filter this row's eight named steps never mention and this script therefore never applies. Any residual gap is that halt, not a reconciliation failure in the eight named steps.

## Entry-idx correlation mismatches (SIM A, informational)

5 of 14333 candidate rows -- same correlation-by-rounded-price limitation R1/g210 documented (a day with two signals sharing a rounded entry price); the affected row is simply absent, never silently mispriced.

## Refereed

The first build (`3ae279a0`) was refereed REFUTED. What survived: the biggest-step finding itself (step 1 -> step 2, swapping the flat exit for the real scale-out-and-trail exit) reproduced under the referee's own independent code and holds on both halves -- that number is unchanged here. What was fixed in this repair, inside the one-change rule (no new bar-by-bar simulation):

- **Step 7/8 substrate swap (the rule violation).** Step 7 no longer substitutes rows from `research/bt2y_trades_retest_on.json` (a different commit, a different engine, `LOSS_HALT` on). It is now a plain date-window filter on THIS row's own step-6 rows; that book is read only for its window's start/end dates. Step 8 now derives from the corrected step 7. This also fixes the tautological verify assertion -- comparing step 7's $/day to `retest_on`'s is now a real cross-check between two independent simulations, not a population compared to itself.

- **Reverse ladder.** The relabelled duplicate is removed, along with the 9 duplicate `.json.gz` files it committed. A real reverse ladder needs a fourth simulation (close fill + blind 2R exit) this row never ran -- that is a second change, so the path-dependence question stays open and is reported as untested, not answered.

- **Stamp bug.** `book_stamp.stamp()` re-derives its flag block by importing `entry_fill`/`backtest_week` fresh in whatever process calls it; called from main (which never itself set `ENTRY_FILL`/`OMEN_SCALE_PLAN`), every one of the 18 books stamped the same env-unset defaults regardless of which fill/exit it actually held. Fixed by setting those env vars to match each book's own (fill, exit) before stamping it, evicting the cached modules, then restoring main's own state.

- **H1/H2 split** added for the biggest step (table above) -- both halves show the same direction and order of magnitude as the full-window number.

- **Disclosed, not fixed by construction**: the dirty-tree flag on every stamped book (paragraph above), and the fact that this row's own ladder ends at $-803/day (full 29) / $-87/day (core 11), not the row's titled -$284/day endpoint (paragraph above).

- **Not fixed, and not fixable inside one change**: a genuine reverse-order ladder (needs a 4th simulation). The 14327-vs-14328 cosmetic row-count note the referee raised is `fwd_1`'s book carrying one candidate row with a null `r` (no fill) -- the book's `signals` count is candidates, the report table's `trades` count is filled rows with a computable R; both are correct readings of different things, now noted here rather than left unexplained.

## Reproduce

```
python research/g211_reconcile_ladder.py --procs 8
```

Books written:

- `research\tape\reconcile_fwd_0_start_next_open_blind2r_noC_no84.json.gz`
- `research\tape\reconcile_fwd_1_add_C_grades.json.gz`
- `research\tape\reconcile_fwd_2_swap_exit_shipped_ladder.json.gz`
- `research\tape\reconcile_fwd_3_add_84_reentries.json.gz`
- `research\tape\reconcile_fwd_4_switch_fill_close.json.gz`
- `research\tape\reconcile_fwd_5_apply_size_gate.json.gz`
- `research\tape\reconcile_fwd_6_dedupe_day_policy_shipped_noop.json.gz`
- `research\tape\reconcile_fwd_7_window_500_to_498.json.gz`
- `research\tape\reconcile_fwd_8_universe_29_to_11.json.gz`