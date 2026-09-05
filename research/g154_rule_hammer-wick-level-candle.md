# g154 F5 -- hammer-wick-level-candle

A visible wick on the level-generating candle is tested here two ways: the book's own 'hammer' tag (proxy) and a wick ratio computed directly from data_archive on the candle that set r['level_px'] (bars), reported side by side on the honest retest-on book, one-trade-a-day, size-gated. Neither arm survived.

Fired base rate (status=='fired', 10830 rows, NOT the one-a-day unit): hammer-tagged 1202 (spec: 1202/10830, confirmed).

candidates/day (raw arrival stream, whole pool): **16.52**

Level-bar coverage (causal search, data_archive only): found 8152/8227 (99.1%) of the stream's candidates. A row with no level bar found FAILS the bars-arm KEEP predicate (conservative).

## Baseline -- one trade a day, whole pool, size-gated

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

## Arm: proxy -- 'hammer' tag

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (hammer tag) (whole book) | $-88.69 | -0.108 | 38.4% | 5/25 | $63788 | 0.823 |
| (hammer tag) H1 | $-44.01 | -0.057 | 39.1% | 3/12 | $23603 | 0.775 |
| (hammer tag) H2 | $-133.38 | -0.153 | 37.8% | 2/13 | $40185 | 0.872 |

delta $/day vs baseline: H1 -179.72, H2 -65.53.

| S recall set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 2.9% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 12.8% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 37.0% | 20 / 54 |

Arm survivor: **not a survivor**.

## Arm: bars -- wick_ratio >= 0.2

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (wick_ratio>=0.2) (whole book) | $-71.32 | -0.073 | 43.2% | 8/25 | $47242 | 0.974 |
| (wick_ratio>=0.2) H1 | $-1.37 | -0.001 | 46.2% | 5/12 | $11017 | 0.960 |
| (wick_ratio>=0.2) H2 | $-141.28 | -0.143 | 40.2% | 3/13 | $44032 | 0.988 |

delta $/day vs baseline: H1 -137.08, H2 -73.43.

| S recall set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 23.5% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 21.2% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 37.5% | 21 / 56 |

Arm survivor: **not a survivor**.

## Arm: bars -- wick_ratio >= 0.3

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (wick_ratio>=0.3) (whole book) | $-42.07 | -0.045 | 43.1% | 9/25 | $38089 | 0.924 |
| (wick_ratio>=0.3) H1 | $-9.51 | -0.011 | 44.5% | 4/12 | $13552 | 0.888 |
| (wick_ratio>=0.3) H2 | $-74.62 | -0.078 | 41.8% | 5/13 | $29183 | 0.960 |

delta $/day vs baseline: H1 -145.22, H2 -6.77.

| S recall set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 20.6% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 14.5% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 45.1% | 23 / 51 |

Arm survivor: **not a survivor**.

## Arm: bars -- wick_ratio >= 0.4

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (wick_ratio>=0.4) (whole book) | $-37.90 | -0.045 | 43.8% | 11/25 | $37323 | 0.839 |
| (wick_ratio>=0.4) H1 | $-22.52 | -0.029 | 45.1% | 6/12 | $14247 | 0.775 |
| (wick_ratio>=0.4) H2 | $-53.29 | -0.059 | 42.7% | 5/13 | $30001 | 0.904 |

delta $/day vs baseline: H1 -158.23, H2 +14.56.

| S recall set | n | baseline | candidate |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 11.8% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 9.3% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| candidate | 35.4% | 17 / 48 |

Arm survivor: **not a survivor**.

## Proxy vs bars agreement

| threshold | both | only proxy (hammer tag) | only bars (wick_ratio) | neither | wick unavailable |
|---|---:|---:|---:|---:|---:|
| 0.2 | 442 | 704 | 2503 | 4048 | 530 |
| 0.3 | 284 | 862 | 1661 | 4890 | 530 |
| 0.4 | 179 | 967 | 1040 | 5511 | 530 |

If 'only proxy' and 'only bars' are both large relative to 'both', the 'hammer' tag is not measuring the same thing as an actual wick ratio on the level-generating candle -- read alongside whichever arm(s) above survive, not instead of them.

## Verdict

Survivor rule (per row spec): H1 AND H2 both improve $/day or precision, and recall_100 (both panels) not below baseline.

| arm | survivor |
|---|---|
| proxy (hammer tag) | False |
| bars (wick_ratio>=0.2) | False |
| bars (wick_ratio>=0.3) | False |
| bars (wick_ratio>=0.4) | False |

**any_survivor = False**