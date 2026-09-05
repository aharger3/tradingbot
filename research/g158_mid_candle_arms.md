# g158 -- mid-candle, categorized honestly

**What is different now:** every book signal was categorized by how far price actually pulls back into its own signal bar AFTER that bar fires, and the best mid-candle arm (MID25, resting a limit at 25% of the signal bar's range back toward the level) prices at $100/day against CLOSE's $34/day (beats it) -- fill: signal-bar CLOSE for CLOSE, a strictly-after-signal resting-limit touch for the MID arms, both through `stop_rule`-consistent exits (`g80_ordertype_grid.run_trade`), size-gated on `signal_runner.min_risk_floor`, 1R = $1,000. Script: `research/g158_mid_candle_arms.py`.

## Categories, all 8227 candidates (not just the one-trade-a-day pick)

| half | never-returns | close-only | mid-fillable |
|---|---:|---:|---:|
| H1 | 286 | 220 | 2954 |
| H2 | 331 | 294 | 4142 |
| ALL | 578 | 514 | 7096 |

Definitions: **never-returns** -- none of 25/50/75% of the signal bar's own range ever fills on a later bar (price ran away; close was the only price obtainable). **close-only** -- only the shallow 25% checkpoint fills. **mid-fillable** -- the 50% or 75% checkpoint fills (a meaningfully better entry existed later, in principle plannable).

## Arms, one-trade-a-day unit (`omen_metrics`-style first-of-day, size-gated)

| arm | combined $/day | % of $397 bar | H1 $/day | H2 $/day | mean R | win% | green months |
|---|---:|---:|---:|---:|---:|---:|---:|
| CLOSE | $34 | 8.6% | $136 | $-68 | +0.034 | 46.5% | 13/25 |
| MID25 | $100 | 25.2% | $164 | $35 | +0.100 | 47.2% | 16/25 |
| MID50 | $90 | 22.7% | $180 | $1 | +0.092 | 36.5% | 15/25 |
| MID75 | $-47 | -11.8% | $22 | $-116 | -0.052 | 28.1% | 8/25 |

No-fill reasons (MID arms, at the candidate level, top 6 each):

- MID25: {'limit_never_touched': 578, 'no_bars_after_signal': 39, 'risk_collapsed': 1}
- MID50: {'limit_never_touched': 1092, 'no_bars_after_signal': 39, 'risk_collapsed': 20}
- MID75: {'limit_never_touched': 1649, 'risk_collapsed': 142, 'no_bars_after_signal': 39}

## `near_session_extreme` and the ON WATCH block (`signal_runner.py` ~1426-1489)

`fill_price()` (signal_runner.py:1443) delegates every entry to `entry_fill.entry_fill_price`,
passing one verdict: `close_is_bad_fill()` (line 1417), which is true when either the signal
bar's OWN extreme was the close (`bar_extreme_veto`, T3(b)) or -- only when `ON_WATCH` is on --
the close sat within `BAR_EXTREME_FRAC` (25%) of the SESSION'S high/low
(`near_session_extreme()`, line 1470). That second condition is what "mid-candle" means in this
engine today: it never changes WHERE the trade enters (the close still decides whether to trade,
per Austin's 2026-08-23 ruling), only whether `entry_fill` is told the close is a bad price --
which currently still books the close anyway (`mode="close"` forced whenever
`entry_fill.needs_future_bars()`), so the verdict is presently a label with no live consequence,
not a price change. `ON_WATCH` is itself the one flag that could turn this arm's finding into a
live rule change; it defaults ON (`signal_runner.ON_WATCH = True`) and is already the current
default book's setting (`bt2y_trades_retest_on.json` stamps it True).

**The one dynamic that could change it: the 25% bar-range unit (`BAR_EXTREME_FRAC`) vs a
cents-based tolerance, and its measured effect.** g87 (`research/g87_retest_tol.py`) already
swept exactly this axis for the RETEST trigger and the answer was blunt: the best tolerance is
ZERO -- a limit resting exactly at the level -- and every widened tolerance (cents or fraction)
LOSES money, because `intrabar_stop` collapses the risk denominator toward the tolerance itself.
g158's own arms echo it from a different angle: MID25/50/75 rest a limit at fixed fractions of
the signal bar's own range rather than at a cents distance, and the categorization above shows
how often price actually gives that fraction back. A cents-unit version of the same three
checkpoints would move with volatility (a $50 stock's 25 cents is not a $500 stock's 25 cents)
where the bar-range unit already scales with the stock automatically -- which is the same reason
Austin rejected a cents unit for the retest tolerance on 2026-08-30 ("it doesn't follow the 25
percent candle unit ... its just if its close but didnt actually touch"). Nothing in this row
re-litigates that; it is recorded here because the row asked for the paragraph and the answer
routes through the same measured fact.


Nothing here is shipped. `signal_runner.py` and `entry_fill.py` were read, never edited.