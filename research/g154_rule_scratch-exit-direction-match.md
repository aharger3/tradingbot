# g154 -- F5 scratch-exit-direction-match

**What is different now:** measured whether the entry candle's own direction (bullish/bearish close) agreeing with the trade direction (call/put) separates anything in the book -- S rate, realized R -- since there is no scratch exit built anywhere in this codebase for this precondition to gate.

## Descriptive split (the row's actual question)

candidates total: 8227 -- 97.22% match the trend direction

| bucket | n | mean R | S rate |
|---|---:|---:|---:|
| entry_dir == trend_dir | 7995 | -0.0228 | 29.9% (285/952) |
| entry_dir != trend_dir | 229 | -0.1497 | 50.0% (10/20) |

unreadable/doji bars excluded: 3

**split is NOT flat** (mean-R gap and S-rate gap both small) -- there is a real gap; a scratch-exit built on this basis is not ruled out by this split alone.

## Selection arm (for comparability only -- no feature exists to attach it to)

| pop | n | $/day | mean R | win | green/mo | max DD |
|---|---:|---:|---:|---:|---:|---:|
| baseline overall | 498 | $33.93 | 0.0339 | 46.5% | 13/25 | $-21404.68 |
| baseline H1 | 249 | $135.71 | 0.1357 | 49.6% | 9/12 | $-13978.64 |
| baseline H2 | 249 | $-67.85 | -0.0678 | 43.4% | 4/13 | $-21404.68 |
| arm overall | 498 | $35.09 | 0.0351 | 46.7% | 12/25 | $-21404.68 |
| arm H1 | 249 | $137.6 | 0.1376 | 50.0% | 8/12 | $-13512.28 |
| arm H2 | 249 | $-67.43 | -0.0674 | 43.4% | 4/13 | $-21404.68 |

candidates/day: 16.52 -- fires/day baseline: 1.0 -- arm: 1.0
S recall (100-card, baseline vs arm): 5.9% (2/34) vs 5.9% (2/34)
S recall (all bar-backed, baseline vs arm): 5.2% (18/347) vs 5.2% (18/347)
precision baseline vs arm: 30.5% (18/59) vs 30.0% (18/60)

## Survivor verdict

H1 delta $/day: 1.89 -- H2 delta $/day: 0.42
**survivor = True**

There is no scratch exit anywhere in backtest_week.py / stop_rule.py / signal_runner.py -- the source is one rule-ballot row, a CONDITIONAL yes ('im ok with implementing scratch'), not a built feature to gate. This measures only the stated precondition: does the entry candle's own color agreeing with the trade direction separate anything in the book we already have. 97.22% of all book candidates print an entry candle matching the trade direction. The descriptive split is NOT flat (mean-R gap 0.1269, S-rate gap 20.1pp) -- not ruling out the precondition the ballot's conditional yes rested on. The selection arm (S-indicator: drop mismatched candidates, fall through to the next) is reported for comparability with every other g154 script, not because a scratch-exit feature exists to attach it to. CAVEAT ON THE survivor FLAG: the arm drops only 2.78% of candidates, so its H1/H2 $/day deltas (1.89 / 0.42) are noise-sized, not a substantive improvement -- the survivor test passes technically but proves almost nothing on its own; the descriptive split above is the load-bearing result.
