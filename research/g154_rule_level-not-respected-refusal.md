# g154 F5 -- level-not-respected-refusal

A level not being respected (candles closing through it or chopping on it instead of reacting off it) is tested here as a REFUSAL, not a downgrade dimension -- two arms, a hard veto and a softer co-occurrence gate, on the honest retest-on book, one-trade-a-day, size-gated.

Fired base rates (status=='fired', 10830 rows, NOT the one-a-day unit): level_not_respected (veto) 7176, + no-confluence (softer) 1606.

candidates/day (raw arrival stream, whole pool): **16.52**

## Baseline -- one trade a day, whole pool, size-gated

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $33.93 | +0.034 | 46.5% | 13/25 | $21405 | 1.000 |
| H1 | $135.71 | +0.136 | 49.6% | 9/12 | $13979 | 1.000 |
| H2 | $-67.85 | -0.068 | 43.4% | 4/13 | $21405 | 1.000 |

## Arm: veto

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $-34.64 | -0.035 | 45.7% | 10/25 | $40529 | 0.992 |
| H1 | $57.52 | +0.058 | 48.0% | 6/12 | $12038 | 0.988 |
| H2 | $-126.80 | -0.127 | 43.5% | 4/13 | $39702 | 0.996 |

delta $/day vs baseline: H1 -78.19, H2 -58.95.

| S recall set | n | baseline | veto |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 20.6% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 21.7% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| veto | 44.2% | 23 / 52 |

Arm survivor: **not a survivor**.

## Arm: softer

| split | $/day | mean R | win | months green | max DD | fires/day |
|---|---:|---:|---:|---:|---:|---:|
| (whole book) | $58.89 | +0.059 | 49.1% | 13/25 | $16978 | 1.000 |
| H1 | $127.09 | +0.127 | 50.4% | 9/12 | $16559 | 1.000 |
| H2 | $-9.32 | -0.009 | 47.8% | 4/13 | $16978 | 1.000 |

delta $/day vs baseline: H1 -8.62, H2 +58.53.

| S recall set | n | baseline | softer |
|---|---:|---:|---:|
| probe_s_sweep (34 S cards) | 34 | 44.1% | 44.1% |
| bar-backed S days (canonical_pool) | 345 | 49.0% | 42.0% |

| precision | pct | S / graded |
|---|---:|---:|
| baseline | 30.5% | 18 / 59 |
| softer | 35.5% | 22 / 62 |

Arm survivor: **not a survivor**.

## Verdict

The veto arm cuts **66%** of fired rows (7176 of 10830) -- the largest cut of any F5 candidate. That size means the veto arm's read comes from candidates/day and S recall, not $/day: 16.52 cand/day, but the recall panels above show how much of the S-day book it takes with it. **Overall survivor = False (basis: softer arm (co-occurrence gate); veto arm is a 66% cut and is judged on candidates/day and S recall, not survivor status).**
