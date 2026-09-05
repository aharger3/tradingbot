# g155 — F6 refuter #1 (lookahead/leakage lens): `scratch-exit-direction-match` — **REFUTED**

**What is different now:** the g154 numbers reproduce exactly and the lookahead lens comes back
clean, but the whole "survivor" verdict turns on **5 sessions out of 498** — and a placebo that
drops a *random* 2.78% of candidates passes the identical survivor gate **22.2%** of the time,
while beating the claim's own H1 delta 33.8% of the time and its H2 delta 54.2% of the time.

Script: `research/g155_refute_scratch-exit-direction-match_r1_lookahead.py`
(JSON: `research/g155_refute_scratch-exit-direction-match_r1_lookahead.json`)

**Fill named, once, for every number below:** signal bar **CLOSE** entry
(`bt2y_trades_retest_on.json` `meta.entry_fill == "close"`), `stop_rule.stop_fill_price` stops as
booked, size-gated on `omen_metrics._row_is_sizeable` (`signal_runner.min_risk_floor`),
1R = $1,000. Unit = one trade a day, arrival order across all symbols
(`research/omen_metrics.first_of_day_arm`). H1/H2 split at 2025-09-01, 249 sessions each.

---

## 1. Reproduction — exact

`python research/g154_rule_scratch-exit-direction-match.py` was re-run and prints the claim
byte for byte.

| figure | claimed | reproduced |
|---|---:|---:|
| baseline overall $/day | $33.93 | **$33.93** |
| arm overall $/day | $35.09 | **$35.09** |
| baseline H1 / H2 $/day | $135.71 / −$67.85 | **$135.71 / −$67.85** |
| arm H1 / H2 $/day | $137.60 / −$67.43 | **$137.60 / −$67.43** |
| H1 delta | +1.89 | **+1.89** |
| H2 delta | +0.42 | **+0.42** |
| precision | 30.5% → 30.0% | **30.5% (18/59) → 30.0% (18/60)** |
| S recall (100-card) | 5.9% → 5.9% | **5.9% (2/34) → 5.9% (2/34)** |

No reproduction defect. The refutation is not about arithmetic.

## 2. Lookahead lens — CLEAN (this is not why it fails)

The feature is `entry_dir = sign(Close[entry_i] − Open[entry_i])`. The book stamps
`entry_fill = "close"`, so `bars[entry_i].close` **is the fill price**, not information from after
it. Verified across the whole candidate book:

| check | result |
|---|---:|
| `bars[entry_i].close == row["entry"]` | **8,187 / 8,227** rows |
| mismatches | 40, all at **$0.005** (half-cent rounding of `entry`) |
| `entry_i` out of range | **0** |
| max abs difference | **$0.0050** |

Bars come from `data_archive` via `polygon_feed` (cache-only), and only index `entry_i` is ever
touched — `direction_match()` never indexes `entry_i + 1` or later. **No read past the entry bar.
No leakage.** The claim survives my assigned lens and dies on the next two.

## 3. The result is 5 days out of 498

The arm drops 2.78% of candidates (229 of 8,227). Because a dropped first-of-day candidate falls
through to the next one, almost every day picks the same trade anyway. Days where the arm's pick
differs from baseline:

| half | differing sessions | per-day $ delta | half $/day delta |
|---|---:|---|---:|
| H1 (249 sessions) | **3** | −$301, +$466, +$304 | **+$1.89** |
| H2 (249 sessions) | **2** | ≈$0, +$104 | **+$0.42** |

The "survivor" verdict is the sign of **four coin flips**. Note the H2 half is carried by a single
trade worth $104 spread over 249 sessions.

Paired daily deltas, both halves straddle zero:

| half | delta $/day | SE | t | 95% CI |
|---|---:|---:|---:|---|
| H1 | +1.89 | 2.55 | **0.74** | **[−3.10, +6.87]** |
| H2 | +0.42 | 0.42 | **1.00** | **[−0.40, +1.24]** |

## 4. The survivor gate is a null event

The gate is `(H1 $/day up AND H2 $/day up) OR precision up`, with recall not falling. Precision
went **down** (30.5 → 30.0), so the flag was earned entirely by the two positive $ deltas.

- **Exact sign-flip** over the 5 non-zero swapped days: **8 / 32 = 25.0%** of sign assignments pass
  the same gate. A fair coin clears this bar one time in four.
- **Placebo** — drop a random 2.78% of candidates through the identical selection machinery
  (`_row_is_sizeable`, fall-through-to-next), N=500, seed 20260905:

| placebo statistic | value |
|---|---:|
| passes the same survivor gate | **111 / 500 = 22.2%** |
| H1 delta p5 / p50 / p95 | −$31.76 / −$3.92 / +$20.74 |
| H2 delta p5 / p50 / p95 | −$21.45 / **+$1.51** / +$21.57 |
| random drops beating the claim's H1 (+1.89) | **33.8%** |
| random drops beating the claim's H2 (+0.42) | **54.2%** |

The claim's H2 delta is **below the median of pure noise**. Its H1 delta is at the 66th percentile
of noise. Nothing here is distinguishable from dropping candidates at random.

**Multiplicity.** 25 rule candidates were tried against a gate a null passes ~22–25% of the time.
Expected spurious survivors from noise alone: **≈5.6 of 25**. Family-wise, the probability that at
least one of 25 nulls clears this gate is `1 − 0.778²⁵ ≈ 99.8%`. Bonferroni-adjusted, this row's
evidence would need p < 0.002; its unadjusted per-half t-statistics are 0.74 and 1.00. It carries
**no** family-wise significance.

## 5. The "load-bearing" descriptive split is also not significant — and points the wrong way

The g154 report calls its selection arm noise and nominates the descriptive split as the real
result, declaring it "NOT flat". With CIs attached it is not a finding either:

| bucket | n | mean R | 95% CI | S rate | 95% CI (Wilson) |
|---|---:|---:|---|---:|---|
| entry_dir == trend_dir | 7,995 | −0.0228 | [−0.0492, +0.0035] | 29.9% (285/952) | [27.1, 32.9] |
| entry_dir != trend_dir | 229 | −0.1497 | [−0.2934, −0.0060] | 50.0% (10/20) | **[29.9, 70.1]** |

- mean-R gap 0.1269, SE 0.0745, **t = 1.70, 95% CI [−0.019, +0.273]** — straddles zero.
- the S-rate confidence intervals **overlap**, and the 20.1pp gap rests on **20 graded mismatch
  cards**. Per `never-oversell-his-marks`: 10 S out of 20 judged rows is a hint, not a diagnosis.
- the two axes **contradict each other**. Mismatched candidates have the worse realized R but the
  *higher* S rate — Austin grades them S at 50% vs 29.9%. The arm drops the mismatches, i.e. it
  discards the bucket his marks like best, which is exactly why arm precision fell 30.5 → 30.0 and
  green months fell 13 → 12 while $/day rose $1.16.

## 6. Standing objection the numbers cannot fix

There is no scratch exit in `backtest_week.py`, `stop_rule.py` or `signal_runner.py`
(`backtest_week.ENTRY_SCRATCH = ''`, `SCRATCH_PROBE_ON = False` in the book stamp). The rule's
source is one ballot line — *"im ok with implementing scratch"* — a conditional yes on an unbuilt
feature. Even had the split been real, it would gate nothing that exists.

## Verdict

**REFUTED.** Reproduces exactly; the lookahead lens is clean; but the survivor flag is a
five-session, four-coin-flip artifact that a random drop of identical size reproduces 22.2% of the
time, with both halves' CIs straddling zero, precision and green months moving the wrong way, and
the fallback descriptive split neither statistically significant nor directionally consistent with
his marks. Do not carry this rule into F7.
