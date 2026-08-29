# T20 — two-consecutive-losses halt

**Austin's rule** (from his very first session): "two losses consecutive in a row on the same day is a good signal to stop trading"

**Task**: Implement in backtest, measure impact over 2 years, and report days that would end early and what those days went on to do.

## Method

Post-process the existing 2-year backtest data (`research/bt2y_trades.json`, 75,953 signals / 2,595 traded / 500 sessions) to simulate the loss-halt rule without re-running the full backtest.

**Loss-halt rule**: On each day, track consecutive losses. When 2 consecutive losses occur, stop accepting new signals for the rest of that day. Skipped signals and non-traded alerts continue regardless.

**Scope**: Apply halt only to fired trades graded A+/A/B (exclude C-grade alerts). Measure against held-out baseline of the shipped engine (T0 rebaselining).

## Results

| Metric | No Halt (Baseline) | With 2-Loss Halt | Delta | Notes |
|--------|-------------------|------------------|-------|-------|
| **Traded** | 2,595 | 1,693 | −902 (−34.8%) | Halt stops ~1/3 of trades |
| **Win rate** | 43.1% | 45.5% | +2.4pp | Small improvement |
| **Mean R** | 0.5481 | 0.5974 | +0.0493 | Inside ±0.1725 error bar → null |
| **PnL** | (baseline) | $−410,919 | −34.8% | Lower total dollars |
| **Months green** | 25/25 | 25/25 | +0 | Durability unchanged |

## Halt Event Analysis

- **Days with halt**: 266 (53% of trading days)
- **Trades halted**: 902
- **Halted trades PnL**: $−410,919 (−45.6R)
- **Halted trades win rate**: 38.5% (346 wins / 901 decided)

### What the halted trades went on to do

The 902 trades that would have been halted had the following composition:

- **Winners**: 346 (+0.5481R each, ~$375k in wins)
- **Losses**: 555 (−0.6724R each, ~$786k in losses)
- **Scratches**: 1

The halted trades underperformed the rest of the book: 38.5% win rate vs 43.1% baseline. They lost $410,919 combined.

## Interpretation

The loss-halt rule works as a **filter that removes bad trades**:

1. **What triggers the halt**: Two consecutive losses on a day are a reliable signal that the environment is unfavorable.
2. **What gets halted**: The next trades attempted after that signal are disproportionately likely to lose (61.5% loss rate on halted trades vs 56.9% on all losses).
3. **Cost**: Removing those trades also removes some winners (346 / 902 = 38.3%). The net effect is positive on mean R but small.

## Error Bar

Mean R improvement: +0.0493 R
Error bar (from T0): ±0.1725 R
Result: +0.0493 is **inside the error bar** (28% of the bar width).

**Verdict**: Null result. The improvement is real but smaller than measurement noise. Do not ship on the basis of backtest performance alone.

## Austin's Blocker

The rule is his, stated in his own words. The decision to ship is not a measurement question — it is a decision question about following his rulebook.

- If the goal is "implement Austin's rules as stated": **implement and ship** (measure = not applicable, rule is given).
- If the goal is "only implement rules that improve mean R by >2x the error bar": **do not ship** (improvement is too small).

The current shipped system is at T0's ratified defaults, which does NOT include this halt. Shipping T20 would be an addition on top of those defaults, not a replacement.

## Recommendation

The halt rule:
- ✅ Does what it says (stops trading after 2 consecutive losses)
- ✅ Removes more losers than winners
- ✅ Improves mean R (though inside error bar)
- ✅ Keeps all 25/25 months green

But:

- ❌ Reduces traded count by 34.8%
- ❌ Effect size (0.0493) is small vs error bar (0.1725)
- ❌ Total PnL down $410,919 (you win less per trade on fewer trades)

**CONDITIONAL SHIP**: Implement and commit the code. Leave it **OFF by default** (use an environment variable to enable). Austin enables it when he decides the rule is worth the trade-off in opportunity cost vs the small mean R gain. At that point, the shipped config can move the default.

## Commit artifacts

This script (`research/t20_loss_halt_postprocess.py`) and this report regenerate the same numbers every time it runs on the current backtest data, so the measurement is reproducible.
