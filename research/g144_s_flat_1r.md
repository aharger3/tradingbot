Every S promotion in `live_scanner.py` now risks exactly $1,000 (RISK_DOLLARS,
his flat 1R) — before this fix a real S traded at only 60-80% of that.

## The bug

`live_scanner._emit_signal` sized every live options card off
`GRADE_SIZE_PCT[sig["grade"]]` — the retired A+/A/B/C/X engine ladder — not
off his own S/A/C tier. `signal_runner.SAC_TIER` maps `{"S": "A", "A": "A",
"C": "C", "X": "X"}`, so a signal carrying his true `sac_grade == "S"` always
displayed engine `grade == "A"` (`GRADE_SIZE_PCT["A"] = 0.8`) — or `"B"` if
the retest gate or another downstream C-cap had already dropped the engine
letter a rung, per the traded rows below. Neither ever hits 1.0. `_tier`
already gates `TRADE` on `sac_grade == "S"` alone (`test_live_tier_s_gate.py`),
so this was never a WATCH-vs-TRADE bug — every card that traded live was a
real S, sized wrong.

## The fix (`live_scanner.py::_emit_signal`)

```
size_pct = 1.0 if display_grade == "S" else 0.0   # display_grade = sig["sac_grade"]
if is_reentry: size_pct *= 2.0                     # 84% re-entry, unchanged
```

`GRADE_SIZE_PCT` is deleted from this function's body (kept in
`options_sizer.py` — the futures live path, `build_futures_plan`, still
reads it, and this row does not touch futures). A and C never reach TRADE
(his 2026-09-01 call: only S trades live), so their live budget is $0 —
no real money is ever sized against them; a WATCH card still displays a
plan, it just carries no risk.

## Before / after, 2-year book (`research/bt2y_trades_retest_on.json`, RETEST_REQUIRED=1, 498 sessions, 2024-09-03 → 2026-09-02)

Filtered to `traded: true` — the book's own "this promoted and booked" flag
(4,022 of 127,152 candidate rows). `sgrade` is `research/downgrade.py`'s
measured S/A/C ladder, the same letter `live_scanner.py` reads live as
`sac_grade`. Dollar figures are the sizing BUDGET handed to
`build_options_plan` (`DEFAULT_MAX_LOSS * size_pct`) — not a contracts count;
the book carries no options premium, so the row's "± contract rounding" is
real but not reproducible here. It is bounded by roughly one contract's
premium (a few dollars) against an $800→$1,000 (+25%) sizing error, so it
does not change the finding.

### S rows (657 traded) — old (engine-grade-keyed) vs new (flat S = $1,000)

| engine grade at trade time | n | old $/trade | new $/trade | delta |
|---|---:|---:|---:|---:|
| A | 16 | $800 | $1,000 | +$200 |
| B | 641 | $600 | $1,000 | +$400 |
| **mean/trade** | **657** | **$604.9** | **$1,000.0** | **+$395.1** |
| **total** | | **$397,400** | **$657,000** | **+$259,600** |

Every one of the 657 S rows now sizes to exactly $1,000 — script asserts
`every_flat == True`.

### A/C rows (3,365 traded) — old vs new (A and C do not trade live)

| | n | old total | old mean/row | new total | new mean/row |
|---|---:|---:|---:|---:|---:|
| A/C | 3,365 | $2,028,400 | $603 | $0 | $0 |

These never mattered as real risk before either — the live gate (`_tier`)
was already refusing to promote them to TRADE, so the $2.03M "old" figure
above was always a WATCH-card display number, never money actually risked.
The fix makes that explicit rather than implied.

## Fill

Signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops, size-gated on
`signal_runner.min_risk_floor` per the book's own stamp (`RETEST_REQUIRED:
True`, `MAX_LOSS_R: 1.25`, `DISASTER_STOP_R: 1.0`). This report changes only
the live SIZING budget, not the book's P&L or R-multiples — the 2-year book
already runs at a flat $1,000/trade risk model (`backtest_week.RISK_DOLLARS`)
that this bug never touched; the bug lived only in the live options-premium
sizing path (`options_sizer.build_options_plan`'s `max_loss` argument), which
this book cannot re-simulate without an options tape. The table above is the
budget that path would have been handed on each of these signals, not a
re-priced P&L.

Script: `research/g144_s_flat_1r.py`. Test: `research/test_s_flat_sizing.py`
(11 checks, all pass). Verify gate green (`regression_gate.py`,
`test_runner_stop.py`).
