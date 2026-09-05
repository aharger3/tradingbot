# g154 F5 -- index-etf-avoid-unless-clear-htf

Candidate one-trade-a-day $/day moves from $33.93 to $33.17 (-0.76/day).

Austin's claim: index ETFs (SPY, QQQ) are avoided by default and traded only when the higher-timeframe direction is very clearly bullish or bearish. Predicate: DROP r if r['sym'] in ('SPY','QQQ') and not (r['aligned']=='with' and r['bias'] in ('bullish','bearish')). Measured over the honest retest-on book, one-trade-a-day, size-gated. Only SPY/QQQ candidates are touched -- IWM and every equity name is untouched, so any movement here can only come from SPY/QQQ occasionally being the day's arrival-order pick.

Base rates: cls=='etf' is **13316** of 127152 rows (expected 13316, confirmed). SPY+QQQ together are 8544 of those; of the 517 fired SPY/QQQ rows, the predicate drops 207.

candidates/day (raw arrival stream, whole pool): **16.52**

## Baseline -- one trade a day, whole pool, size-gated

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

## Arm: candidate

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.17 | +0.033 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $134.20 | +0.134 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

delta $/day vs baseline: H1 -1.51, H2 +0.00.

| S recall set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 47.5% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 31.0% | 18 / 58 |

Survivor: **not a survivor**.

## Verdict

This is a corroboration check on an existing measured decision (g91_lane_slice.py: index lane 2.3 cand/day, $51/day; pool stays FULL because narrowing it caps the ceiling at $437/day vs his $397 bar). It moves the whole-pool one-a-day arm. Overall survivor = **False**.
