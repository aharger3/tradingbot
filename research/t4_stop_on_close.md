# T4 — stop on the CLOSE, scratch the failed entry bar, ladder exit

12 months of archived 1-minute bars (2025-08-11 onward), pool `universe.MAJOR_15` (15 symbols), replayed through `backtest_week.simulate_day` — same engine, only the two flags move. Counted trades are fired A+/A/B (C is alert-only), $1000 risk per trade.

```
win_rate_wick: 48.5
win_rate_close: 53.5
trades_wick: 99
trades_close: 99
scratches_close: 0
arm84_wick: 1
arm84_close: 1
win_rate_blind2r: 48.5
win_rate_ladder_b: 53.5
pnl_blind2r: 45000.0
pnl_ladder_b: 52060.75
```

## Arms

| arm | stop trigger | exit | trades | W | L | scratch | win rate | P&L |
|-----|--------------|------|--------|---|---|---------|----------|-----|
| wick | wick through the level | ladder B | 99 | 48 | 51 | 0 | 48.5% | $21615.8 |
| close | candle CLOSE beyond the level | ladder B | 99 | 53 | 46 | 0 | 53.5% | $52060.75 |
| blind2r | candle CLOSE beyond the level | blind 2R | 99 | 48 | 51 | 0 | 48.5% | $45000.0 |

## What the arms say

**The stop trigger.** Moving the trigger from a wick to the close is worth +5.0 points of win rate (48.5% -> 53.5%) and $+30,445 over the same 12 months and the same 99 trades. Trade count is identical by construction — the change touches when a position exits, never whether it is taken — so this is a clean read: trades Austin would still have been holding were being closed at a wick.

**The exit.** With close-based stops, ladder B beats blind 2R on BOTH axes (53.5% / $52,061 vs 48.5% / $45,000) — not the win-rate-for-dollars trade the F1 A/B measured under wick stops. The two changes interact: scaling at 1R only pays when the runner is not being wicked out first. Austin's gate is a 55% win rate and ladder B lands at 53.5%, so it is close but not over the line.

**scratches_close is 0, and that is a real result, not a missing feature.** The scratch path is wired in `simulate_day` and `_arm_84` refuses to arm on it. It cannot fire on this population because every detector confirms on the bar close — a B&R long only fires when `current.close > level`, so the entry bar's close is on the right side of the level by construction. The rule is Austin describing a LIVE intrabar fill that fails before the bar closes; it will fire the moment an intrabar entry path exists, and on bar-close replay it cannot. Nothing was tuned to make this number zero.

**84% armings: 1 in 12 months.** `RULE84_STRICT` (default ON) only arms off an A+/A original that took a counted full stop-out, and T4(c) now also requires the stop-out to be a loss (not a scratch) before 11:00. The 2,843-row `research/rule84_candidates.jsonl` pool was built on wick stop-outs — this is the measurement that says how many of those survive the close rule: almost none.

## Per setup

| setup | arm | trades | W | L | scratch | win rate | P&L |
|-------|-----|--------|---|---|---------|----------|-----|
| break_and_retest | wick | 61 | 33 | 28 | 0 | 54.1% | $10173.54 |
| one_candle_rule | wick | 37 | 14 | 23 | 0 | 37.8% | $7379.76 |
| reentry_84_rule | wick | 1 | 1 | 0 | 0 | 100.0% | $4062.5 |
| break_and_retest | close | 61 | 37 | 24 | 0 | 60.7% | $29172.34 |
| one_candle_rule | close | 37 | 15 | 22 | 0 | 40.5% | $18825.91 |
| reentry_84_rule | close | 1 | 1 | 0 | 0 | 100.0% | $4062.5 |
| break_and_retest | blind2r | 61 | 29 | 32 | 0 | 47.5% | $26000.0 |
| one_candle_rule | blind2r | 37 | 18 | 19 | 0 | 48.6% | $17000.0 |
| reentry_84_rule | blind2r | 1 | 1 | 0 | 0 | 100.0% | $2000.0 |
