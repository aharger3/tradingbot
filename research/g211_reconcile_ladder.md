# OMEN 10.0 R2 -- reconcile R1's next_open book against the shipped full book

**Why step 0 reads $2,660/day, not the spec's headline $569/day.** $569/day is `g90_fill_arms.py`'s ORIGINAL published `next_open` number (2024-08-12 to 2026-08-11, the pre-R1 engine). Step 0 here is R1's re-run of the SAME arm on the current engine and window -- already measured and explained in `research/g210_fill_arms_v2.md`'s "Differences from g90" section (a different window, plus every engine change landed between g90's run and R1's, `RETEST_REQUIRED` named explicitly). This row starts from R1's number because R1 is the row this one is blocked on, not because the drift from $569 needed re-explaining.

Base commit at run time, three new simulations (SIM A/B/C, full29 pool, WIDE window `2024-09-04` to `2026-09-04`), plus a re-filter of the ALREADY-BUILT `research/bt2y_trades_retest_on.json` (commit `a89e90e2`, window `2024-09-03` to `2026-09-02`, 498 sessions) for steps 7-8 -- no fourth replay. Unit: every traded signal (status=="fired"; grade and 84% inclusion vary by step, named per row). Fill/exit named per row. $1,000 risk/trade, unsized until step 5.

## Which steps were simulated, which were filtered

- **Simulated** (three bar-by-bar replays): SIM A (`next_open` fill, blind 2R exit, custom arm mechanics identical to R1/g90's `_walk`) feeds steps 0-1; SIM B (`next_open` fill, shipped ladder exit, the REAL `backtest_week.simulate_day` with `ENTRY_FILL=next_open`) feeds steps 2-3; SIM C (`close` fill, shipped ladder exit, the shipped defaults, no env override) feeds steps 4-6.

- **Filtered, not simulated**: grade (C in/out), signal_type (`reentry_84_rule` in/out), the size gate (`min_risk_floor`), and steps 7-8 (window, universe) -- the last two read `research/bt2y_trades_retest_on.json`, a book already built on 2026-09-02, filtered the same three ways.

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
| 7 | window_500_to_498 | close | shipped_ladder | full29 | 10156 | 41.2% | -0.0283 | +1.0559 | -0.7992 | 11/25 | $-578 |
| 8 | universe_29_to_11 | close | shipped_ladder | core11 | 4660 | 43.1% | -0.0008 | +1.0599 | -0.8146 | 11/25 | $-8 |

## Reverse ladder (same nine populations, opposite order -- not re-simulated)

| step | change | fill | exit | pool | trades | win rate | mean R | avg win | avg loss | green months | $/day |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 8 | start_next_open_blind2r_noC_no84 | next_open | blind_2R | full29 | 7857 | 38.9% | +0.1690 | +1.9817 | -0.9973 | 23/25 | $2,660 |
| 7 | add_C_grades | next_open | blind_2R | full29 | 14327 | 38.6% | +0.1592 | +1.9835 | -0.9965 | 24/25 | $4,569 |
| 6 | swap_exit_shipped_ladder | next_open | shipped_ladder | full29 | 14332 | 42.4% | -0.0342 | +1.0312 | -0.8274 | 7/25 | $-981 |
| 5 | add_84_reentries | next_open | shipped_ladder | full29 | 14731 | 42.1% | -0.0328 | +1.0549 | -0.8329 | 7/25 | $-967 |
| 4 | switch_fill_close | close | shipped_ladder | full29 | 14718 | 41.9% | -0.0257 | +1.0154 | -0.7844 | 7/25 | $-758 |
| 3 | apply_size_gate | close | shipped_ladder | full29 | 13374 | 41.8% | -0.0303 | +1.0192 | -0.7926 | 7/25 | $-812 |
| 2 | dedupe_day_policy_shipped_noop | close | shipped_ladder | full29 | 13374 | 41.8% | -0.0303 | +1.0192 | -0.7926 | 7/25 | $-812 |
| 1 | window_500_to_498 | close | shipped_ladder | full29 | 10156 | 41.2% | -0.0283 | +1.0559 | -0.7992 | 11/25 | $-578 |
| 0 | universe_29_to_11 | close | shipped_ladder | core11 | 4660 | 43.1% | -0.0008 | +1.0599 | -0.8146 | 11/25 | $-8 |

## The step that costs the most money

**switching from a flat double-your-money exit to the real scale-out-and-trail exit** -- $4,569/day before, $-981/day after, a swing of $-5,550/day. That is the single biggest drop between any two adjacent rows of the forward ladder.

## Verify

- step 0 vs R1 next_open (full29): 7857 rows here vs 7857 in R1's book -- MATCH to the cent.
- step 0 vs R1 next_open (core11): 3629 rows here vs 3629 in R1's book -- MATCH to the cent.
- step 7 (unsized, full pool, window=('2024-09-03', '2026-09-02')) $/day = $-675.25 vs research/bt2y_trades_retest_on.json's own $-675.25 (sum(pnl for status=='fired', any grade) / 498 sessions) -- WITHIN 1%.

## Entry-idx correlation mismatches (SIM A, informational)

5 of 14333 candidate rows -- same correlation-by-rounded-price limitation R1/g210 documented (a day with two signals sharing a rounded entry price); the affected row is simply absent, never silently mispriced.

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
- `research\tape\reconcile_rev_8_start_next_open_blind2r_noC_no84.json.gz`
- `research\tape\reconcile_rev_7_add_C_grades.json.gz`
- `research\tape\reconcile_rev_6_swap_exit_shipped_ladder.json.gz`
- `research\tape\reconcile_rev_5_add_84_reentries.json.gz`
- `research\tape\reconcile_rev_4_switch_fill_close.json.gz`
- `research\tape\reconcile_rev_3_apply_size_gate.json.gz`
- `research\tape\reconcile_rev_2_dedupe_day_policy_shipped_noop.json.gz`
- `research\tape\reconcile_rev_1_window_500_to_498.json.gz`
- `research\tape\reconcile_rev_0_universe_29_to_11.json.gz`