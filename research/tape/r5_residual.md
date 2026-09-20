# R5: the -$87 (ladder step 8/"11") vs -$52 (baseline) residual

**Cause: step 8's book still trades grade-C signals and is measured by
straight sum(pnl)/sessions, not the loop's own day-policy unit — baseline
does neither.**

`RETEST_REQUIRED=0` ruled out: `reconcile_fwd_8_universe_29_to_11.json.gz`'s
stamp has `RETEST_REQUIRED=True`, same as `baseline_2026-09-13.json.gz`. Only
`DAY_POLICY` differs (`3fires_stop_win_or_2loss` vs `first3`, an env leak from
the 2026-09-05 loop cycle) — a no-op: step 8 has days with up to 54 trades,
so no per-day cap was built in (`g211_reconcile_ladder.py` never calls
`day_policy.apply_to_book`).

Real cause, two disclosed-but-never-reversed ladder choices:
1. **Grade C.** `backtest_week.py:633`: "C is alert-only ... excluded from
   traded P&L." Baseline's core-tier traded rows are 0% grade C. Ladder step 1
   ("add_C_grades") puts C back in, never removed: step 8 is 49% grade C
   (2,820/5,788 rows), net **+$33,035.53**.
2. **Unit.** `loop.json`'s `"unit": "up_to_3_stop_win_or_2loss"`
   (`loop_cycle.py::up_to_3_rows`) derives -$52.00/day, not a straight sum.
   Step 8's -$87 is `sum(pnl)/498 sessions` over all 5,788 rows (verified:
   -$43,475.61/498 = **-$87.30**) — never re-lensed through that unit.

Combined on step 8's book: drop grade C (5,788→2,968), apply `up_to_3_rows`
(→755) → **-$41.06/day** (-$40.82 at 501 sessions). Closes $46 of the $35
gap, ~$11/day short of -$52 — residual is the 498-vs-501 session window plus
this trades-only book lacking `loss_halt`-halted rows `up_to_3_rows` uses for
day-order context. Reproduce: filter the step-8 book to `grade != "C"`, group
by `day`, cap 3/day stop-on-win-or-2loss, vs baseline's core tier (0% grade C).
