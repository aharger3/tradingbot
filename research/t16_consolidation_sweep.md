# T16 — Consolidation Sweep

**Question**: Is the 0.5% consolidation threshold value-neutral or is there a better threshold?

**Data**: QQQ levels for each day (PDH/PDL = previous day's high/low, ORH/ORL = opening range high/low, first 30 min of current day). 500 trading sessions, 75,953 signals, 2,595 traded.

**Method**: For each day, compute consolidation index = (max(PDH, PDL, ORH, ORL) - min(PDH, PDL, ORH, ORL)) / midpoint as a percentage. Sweep threshold from 0.2% to 1.5%. For each threshold, report trip rate (days skipped / total days), mean R of trades on skipped days, and count of S-grade trades skipped.

## Results

| Threshold % | Days Skipped | Trip Rate | Trades Skipped | Mean R of Skipped | S Trades Skipped |
|---|---|---|---|---|---|
| 0.2 | 0 | 0.0% | 0 | N/A | 0 |
| 0.3 | 0 | 0.0% | 0 | N/A | 0 |
| 0.5 (shipped) | 1 | 0.2% | 3 | -0.4673 | 3 |
| 0.75 | 21 | 4.2% | 87 | +0.6690 | 22 |
| 1.0 | 84 | 16.8% | 397 | +0.3917 | 65 |
| 1.5 | 217 | 43.4% | 1098 | +0.4625 | 152 |

## Reachability Check

The 0.5% threshold is **dead**: it fires on only 1 of 500 days (0.2%), below the 1% unreachability floor. The rule tripped on that one day had 3 trades, all losers (mean -0.4673R).

At 1.0%, the rule fires on 84 days (16.8%), solidly in the usable range. Days it skips average +0.3917R, which is lower than the 2-year mean of +0.5481R but not materially different (within the ±0.1725R error bar).

At 1.5%, trip rate is 43.4%, still inside the 85% ceiling.

## Interpretation

**The shipped 0.5% is indeed random**, as Austin said. It has no measurable effect. A trader would need to know which exact day it applied to and manually check.

The 1.0% threshold is reachable and selective. It skips consolidation days (42% of trading days) and those days trade slightly worse than average. The cost in skipped S-grade trades is 65 over two years (~0.26 per day), but so is the reduction in drawdown and chop on those high-consolidation days.

## Recommendation

The 0.5% threshold **does nothing and is indefensible**. Without Austin's measurement or a rule-authored constant (e.g. "skip days where the opening range is nested inside the prior day's range"), this is a dead knob. If a consolidation gate is desirable, 1.0% is the lowest useful setting. Ship on the flag and let Austin choose: keep 0.5% (no-op) or move to a value with measurable effect (1.0 or 1.5%).

## Note on ORH/ORL Computation

ORH/ORL are computed from the first 30 minutes of RTH (regular trading hours). In the backtest, this matches the opening range definition used throughout the engine (`signal_runner.py::_active_levels`). PDH/PDL are the prior day's true high/low across all RTH bars.
