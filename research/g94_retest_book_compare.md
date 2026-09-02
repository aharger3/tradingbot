# g94 -- RETEST_REQUIRED, the real 2-year book

`RETEST_REQUIRED=1 python backtest_2y.py`. OFF book `research/bt2y_trades.json`, ON book `research/bt2y_trades_retest_on.json`.

Shared rows unmoved: **FAIL** (110975 shared, 49 moved). Population delta 160 OFF-only / 386 ON-only -- expected, from dedupe release and the 84% re-entry. Rows carrying the cap: **1786**.

| lane | metric | OFF | ON | delta |
|---|---|---:|---:|---:|
| full pool | cand/day | 18.8 | 16.5 | -2.3 |
| full pool | $/day | 27 | 25 | -2.0 |
| full pool | win % | 45.5 | 45.8 | +0.3 |
| full pool | green months | 10 | 13 | +3.0 |
| full pool | max DD $ | 25647 | 21709 | -3938.1 |
| index QQQ/SPY/IWM | cand/day | 2.3 | 2.2 | -0.1 |
| index QQQ/SPY/IWM | $/day | 49 | 65 | +16.0 |
| index QQQ/SPY/IWM | win % | 49.1 | 49.9 | +0.8 |
| index QQQ/SPY/IWM | green months | 13 | 15 | +2.0 |
| index QQQ/SPY/IWM | max DD $ | 19426 | 15665 | -3760.5 |
