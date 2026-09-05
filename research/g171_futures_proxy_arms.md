# G171 -- futures proxy arm + overlap check

What is different: the index-pool one-trade-a-day book (QQQ/SPY/IWM, retest-on) is now priced in futures points and run through every futures-only firm in FIRMS; the ES=F vs SPY overlap check says how much to trust the proxy.

- Candidates pre-map: 234, mapped: 234, dropped: {}

## Ratio (futures_close / etf_close, daily)

| pair | days | mean | stdev | min | max | latest |
|---|---:|---:|---:|---:|---:|---:|
| ES=F/SPY | 626 | 10.073 | 0.0379 | 9.8795 | 10.168 | 10.0261 |
| NQ=F/QQQ | 626 | 41.3024 | 0.1578 | 40.3887 | 41.7342 | 41.1222 |
| RTY=F/IWM | 626 | 10.1163 | 0.0379 | 9.8867 | 10.3063 | 10.0557 |

## Money ($/day, one-trade-a-day, mapped futures fill)

| window | days | $/day | win% | green months |
|---|---:|---:|---:|---:|
| full 2y | 234 | $-11.83 | 48.3% | 12/24 |
| H1 (<2025-09-01) | 112 | $48.34 | 49.1% | 7/12 |
| H2 (>=2025-09-01) | 122 | $-67.07 | 47.5% | 5/12 |

## Firms -- walk-forward PASS/FAIL on the real 2-year sequence

| firm | passed | fail_reason | days_used | months | cost | net_after_cost | rolling-252 pass% |
|---|---|---|---:|---:|---:|---:|---:|
| Topstep 50K Combine | False | trailing_drawdown | 13 | 1 | 49 | -1665.0 | 0.0 |
| Topstep 100K Combine | False | trailing_drawdown | 14 | 1 | 99 | -2702.78 | 0.0 |
| Topstep 150K Combine | False | trailing_drawdown | 18 | 1 | 149 | -4901.55 | 0.0 |
| Apex 50K Eval EOD | False | trailing_drawdown | 14 | 1 | 35 | -2638.78 | 0.0 |
| Apex 100K Eval EOD | False | trailing_drawdown | 14 | 1 | 85 | -2688.78 | 0.0 |
| Apex 150K Eval EOD | False | trailing_drawdown | 18 | 1 | 105 | -4857.55 | 0.0 |
| TPT Test 50K | False | trailing_drawdown | 13 | 1 | 102 | -1718.0 | 0.0 |
| TPT Test 100K | False | trailing_drawdown | 14 | 1 | 150 | -2753.78 | 0.0 |
| TPT Test 150K | False | trailing_drawdown | 18 | 1 | 200 | -4952.55 | 0.0 |
| MFFU Rapid 50K | False | trailing_drawdown | 13 | 1 | 80 | -1696.0 | 0.0 |
| MFFU Rapid 100K | False | trailing_drawdown | 14 | 1 | 150 | -2753.78 | 0.0 |
| Earn2Trade TCP 25K | False | daily_loss_limit | 1 | 1 | 150 | -150.0 | 0.0 |
| OneUp 100K | False | trailing_drawdown | 15 | 1 | 105 | -3695.46 | 0.0 |
| Lucid Trading | None | BLOCKED | None | None | None | None | None |

## Overlap check: ES=F/MES=F vs SPY, last 7 days, 1-min

```json
{
  "status": "OK",
  "es_signals": 3,
  "spy_signals": 4,
  "matched_pairs": 2,
  "unmatched_es_only": 1,
  "unmatched_spy_only": 2,
  "mes_series_fetched": true,
  "intrabar_ratio_at_match": {
    "n": 2,
    "mean": 10.0367,
    "stdev": 0.0012,
    "min": 10.0355,
    "max": 10.0379
  }
}
```

Simplified proxy detector (PDH/PDL break + retest to within 0.1%), NOT the shipped engine -- see the module docstring. Trust reading: basis is tight and signals largely co-occur
