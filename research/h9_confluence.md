# H9 — does confluence weight track outcome? (omen-3.4, T7)

**Question.** Every weight in T2's table (HOD/LOD 3.0; PDH/PDL/PMH/PML 2.5; psych $50-multiple 3.0 / $10-multiple 2.5 / $5-multiple 2.3 / whole-dollar 2.0 / half-dollar 1.5; floor & swing pivots 2.0) is a guess at which levels carry more liquidity. This measures whether that ordering is real: does the weight of the level nearest the entry price at the entry bar actually rise with realized R?

**Design.** For every candle-bearing engine trade, rebuild the level node set visible at the entry bar — whole/half psychological numbers (always price-derivable) plus HOD/LOD and 3-bar swing pivots over the embedded 1m window up to entry (the trade's own bar path; `entry_i` is the engine's index into that window by construction) — take the node nearest the entry price, and read its weight (T2 weights; tie at equal distance → stronger level wins). Realized R = `(exit_price - entry)/risk * direction`. Three tests over ALL trades, not a subgroup: (1) Spearman rho with a day-block bootstrap 95% CI; (2) binned mean realized R by weight bucket, one bucket per distinct T2 weight, with an n for every bucket, plus a monotonicity check across consecutive buckets; (3) OLS of realized R on weight with day-clustered standard errors.

**Population.** The **970 unique candle-bearing trades** in `backtest_charts_12mo.json` — the bar-path-bearing subset of the 1,289-trade engine run summarised in `backtest_metrics_full.json` (`POPULATION_N` in `research/omen34_inputs.md`). **970 exceeds the spec's ~780 floor, so achieved power is adequate** (the test runs on the full population, not a powered subgroup). A robustness cross-check runs the same design on the **792 unique candle-bearing trades** in `backtest_charts.json` (793 raw records, one duplicate removed) — the file the spec's "roughly 780" framing maps to; both clear 780.

**Why not the hand-marked corpus.** `research/marks_clean.jsonl` carries **no realised outcome** — its fields are symbol/day/entry/stop/target/entry_i/rr/side/tier/setups/management/note (verified: no exit_price, pnl, or outcome). `rr` there is the *planned* target R, not realised R. So the corpus T4/T5 used for target analysis cannot answer H9's realised-R question, and is not used here. This is the realised-outcome asymmetry between the two corpora and is reported, not hidden.

**Outcome space.** The engine auto-targets 2R and stops at 1R, so realized R is essentially three-valued — `−1` at the stop, `+2` at the target, and a thin tail of partial exits (mean realized R across the 970 = +0.0227). Spearman and the binned means operate on that discrete outcome directly; this is the space the test lives in, not a method defect.


## Headline

**No.** Spearman rho = +0.0580 (day-block bootstrap 95% CI [-0.0071, +0.1258], **CI includes 0**): the weight of the nearest level does **not** track realized R. The T2 weight ordering is not measurable as a monotone relationship with outcome in this population.


## 1. Spearman rho (nearest-node weight vs realized R)

- **Primary (970 trades, 12mo):** rho = **+0.0580**, day-block bootstrap 95% CI = **[-0.0071, +0.1258]** (10,000 resamples, days resampled with replacement, rho recomputed on the pooled resample each draw).

- **Robustness (792 unique trades, charts):** rho = **+0.0681**, bootstrap 95% CI = [-0.0050, +0.1452].

- CI includes 0 in the primary → the correlation is not statistically distinguishable from zero at the day-clustered level.


## 2. Binned mean realized R by weight bucket

Each distinct T2 weight present is its own bucket (the natural binning — the weight vector is discrete). Sorted ascending; `mean R` is the average realized R over trades whose nearest entry node carries that weight; `win rate` is the share that hit the 2R target.


**Primary (970 trades, 12mo)**

| weight | n | mean R | median R | win rate | nearest-node type makeup |
|---:|---:|---:|---:|---:|---|
| 1.50 | 23 | +0.3043 | -1.0000 | 43.5% | psych_half:23 |
| 2.00 | 713 | -0.0431 | -1.0000 | 32.3% | psych:290, swing_low:220, swing_high:203 |
| 2.30 | 33 | -0.0909 | -1.0000 | 30.3% | psych:33 |
| 2.50 | 21 | +0.5714 | +2.0000 | 52.4% | psych:21 |
| 3.00 | 180 | +0.2040 | -1.0000 | 40.0% | HOD:95, LOD:76, psych:9 |
| **total** | **970** | | | | |

**Monotonicity (primary).** Mean realized R does **NOT** rise monotonically across weight buckets (1.5:+0.304, 2.0:-0.043, 2.3:-0.091, 2.5:+0.571, 3.0:+0.204). Break(s): bucket w=2.0 (mean R -0.0431) below w=1.5 (+0.3043); bucket w=2.3 (mean R -0.0909) below w=2.0 (-0.0431); bucket w=3.0 (mean R +0.2040) below w=2.5 (+0.5714). The T2 ordering is contradicted at these points.


**Robustness (792 unique trades, charts)**

| weight | n | mean R | median R | win rate |
|---:|---:|---:|---:|---:|
| 1.50 | 19 | +0.4211 | -1.0000 | 47.4% |
| 2.00 | 571 | -0.0176 | -1.0000 | 32.7% |
| 2.30 | 31 | -0.2258 | -1.0000 | 25.8% |
| 2.50 | 21 | +0.5714 | +2.0000 | 52.4% |
| 3.00 | 150 | +0.3143 | -1.0000 | 43.3% |
| **total** | **792** | | | |

**Monotonicity (robustness).** Mean realized R does **NOT** rise monotonically across weight buckets (1.5:+0.421, 2.0:-0.018, 2.3:-0.226, 2.5:+0.571, 3.0:+0.314). Break(s): bucket w=2.0 (mean R -0.0176) below w=1.5 (+0.4211); bucket w=2.3 (mean R -0.2258) below w=2.0 (-0.0176); bucket w=3.0 (mean R +0.3143) below w=2.5 (+0.5714). The T2 ordering is contradicted at these points.


## 3. OLS — realized R on weight, day-clustered SE

- **Primary:** intercept = -0.4524, **slope on weight = +0.2165 R per unit weight**, day-clustered SE = 0.1213 (G = 237 day-clusters), t = 1.785, two-sided p = 0.07423.

- **Robustness:** slope = +0.2832, SE = 0.1357 (G = 233), t = 2.087, p = 0.03686.

- The slope is the R-per-unit-weight the T2 ordering would buy if it were real. Sign matches the Spearman sign; p >= 0.05 → not significant at the day-clustered level.


## Read

The tests do not support the T2 ordering as a monotone driver of outcome: rho = +0.0580 (CI includes 0), OLS slope = +0.2165 (p = 0.0742), and the binned means do not rise monotonically across weight buckets. The weight vector is a guess the data does not ratify here; the nearest-level weight is not a usable ranking of trade quality by outcome.


## Caveats

1. **Node set is the embedded-window subset of T2's vector.** From the trade's own embedded 1m window we recover psych numbers (1.5/2.0/2.3/2.5/3.0), HOD/LOD (3.0), and swing pivots (2.0). Prior-day levels — PDH/PDL/PMH/PML (2.5) and floor pivots (2.0) — are NOT in the embedded window, so the 2.5 bucket here comes only from $10-multiple psych numbers, and a separate 2.0 (pivot) channel is absent (it would overlap the whole-dollar 2.0 bucket anyway). The marks corpus, which CAN reach prior-day levels via `data_archive`, has no realised outcome (above) and so cannot test the full vector against R. The ordering among the weights that DO appear (1.5→2.0→2.3→2.5→3.0) is exactly the T2 ordering restricted to this subset.

2. **Nearest-by-price, not nearest-by-relevance.** The nearest node to an arbitrary entry price is usually a psychological number (round numbers are dense, every $0.50 below $100); HOD/LOD/swings only win when entry sits near a session extreme or swing. So the weight distribution is dominated by the dollar-magnitude of the nearest round number. This is what the spec asks for ("nearest node to the entry price"), but it means the test is partly a test of 'does the nearest round number's size predict outcome', which is a specific reading of 'confluence weight'.

3. **Tie-break biases toward stronger levels** at exact equal distances (entry exactly midway between a whole dollar and a half dollar, only possible below $100). This is rare and only affects the 1.5/2.0 boundary; direction chosen because a trader treats the stronger level as the confluence at a tie.

4. **Realized R is three-valued** (−1 / +2 / partial). Spearman with average-rank ties and the cluster-robust OLS both handle this; the binned means are the most readable artifact for a discrete outcome.

5. The 970-trade 12mo file is the candle-bearing subset of the 1,289 engine run; ≈319 trades have no embedded candles and are not resimulatable here. 970 > 780 so power is adequate; the 792-trade (793 raw) charts robustness is a strict subset and agrees.


---
_Reproducible: `python3 research/h9_confluence.py` regenerates this file._

