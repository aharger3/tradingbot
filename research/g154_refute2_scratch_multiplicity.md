# g154 refuter2 -- scratch-exit-direction-match: multiplicity and sampling error

**What is different now:** the claim reproduces to the cent, but its entire survivor verdict rests on 5 of 498 sessions changing hands, the paired-bootstrap CI on both halves straddles zero, and a random relabelling that drops the same number of candidates clears the very same survivor gate 60.1% of the time -- so over the 25 candidates tried this family expects 15.02 spurious survivors of exactly this kind.

Fill: signal bar CLOSE entry, stop_rule.stop_fill_price stops, size-gated on signal_runner.min_risk_floor, 1R = $1,000; one-trade-a-day unit = the claim script's pick_first_of_day (== omen_metrics.first_of_day_arm). Book bt2y_trades_retest_on.json, 498 sessions, H1/H2 split 2025-09-01. Script: `research/g154_refute2_scratch_multiplicity.py`.

## A. Reproduction

| field | rerun | published |
|---|---:|---:|
| baseline_usd_day | 33.93 | 33.93 |
| arm_usd_day | 35.09 | 35.09 |
| h1_delta | 1.89 | 1.89 |
| h2_delta | 0.42 | 0.42 |
| precision_base | 30.5 | 30.5 |
| precision_arm | 30.0 | 30.0 |
| recall100_base | 5.9 | 5.9 |
| recall100_arm | 5.9 | 5.9 |
| survivor | True | True |

reproduces exactly: **True**

## B. Footprint -- how much of the book the arm actually touches

| | |
|---|---:|
| sessions where the pick changed | 5 / 498 (1.00%) |
| total dollar delta over 2 years | $573.94 |
| single biggest session's share | 81.3% |
| top 3 sessions' share | 81.8% |

| day | delta $ | baseline pick | arm pick |
|---|---:|---|---|
| 2024-12-20 | 466.36 | MSFT 09:36 | INTC 09:37 |
| 2025-08-13 | 304.39 | AMD 09:49 | GOOGL 09:52 |
| 2024-09-23 | -301.36 | HOOD 09:37 | PLTR 09:43 |
| 2025-11-19 | 104.09 | NFLX 09:41 | QQQ 09:41 |
| 2025-10-16 | 0.46 | ACHR 09:37 | AMZN 09:48 |

H1's whole +$1.89/day is 3 swapped sessions; remove the single 2024-12-20 swap and the remaining 2 leave H1 at $0.01/day. 
H2's whole +$0.42/day is 2 swapped sessions; remove the single 2025-11-19 swap and the remaining 1 leave H2 at $0.00/day. **The survivor gate is decided by two individual trade swaps.**

_Bookkeeping: (day, et, sym) is not unique in the book -- 8227 rows collapse to 7920 keys -- so this refuter's drop set is keyed and the null draws the same number of KEYS. Reproduction is exact on every published field, so the collapse changes no pick._

## C. Paired bootstrap over sessions (10k resamples)

| slice | delta $/day | 95% CI | P(delta > 0) |
|---|---:|---|---:|
| overall | 1.15 | [-1.2, 3.92] | 0.8286 |
| H1 | 1.89 | [-2.42, 7.41] | 0.7729 |
| H2 | 0.42 | [0.0, 1.26] | 0.8642 |

P(H1 delta > 0 AND H2 delta > 0) under resampling: **0.6648**

## D. Label-permutation null -- same shape, no signal

Drop 208 candidates chosen uniformly at random from the readable book (the arm drops exactly 208), fall through to the next pick, score with the claim script's own gate. 2000 draws.

| | |
|---|---:|
| random relabelling clears the survivor gate | **60.1%** |
| ... via the $/day arm (both halves up) | 23.5% |
| ... via the precision arm | 51.0% |
| observed H1 delta's percentile in the null | 63.8% |
| observed H2 delta's percentile in the null | 45.9% |
| expected spurious survivors over the 25 candidates tried | **15.02** |
| P(at least one spurious survivor over 25 tried) | 1.0 |

## E. The descriptive split the report calls load-bearing

| | |
|---|---:|
| match S rate | 285/952 |
| mismatch S rate | 10/20 |
| S-rate gap | -20.1pp |
| Fisher exact two-tailed p | **0.0816** |
| mean-R gap (match minus mismatch) | 0.1269 |
| Welch t / p on mean R | 1.702 / 0.0887 |

Note the sign: the mismatch bucket has the WORSE mean R and the HIGHER S rate. Those two point opposite ways, which is what a 20-card sample looks like when nothing is there.

