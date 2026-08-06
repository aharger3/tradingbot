# H3 — does a veto in front of a wall pay for itself? (omen-3.4, T6)

**Design.** Pure partition of the existing population — no new data, no resimulation, no human input. Primary population = the **970 unique candle-bearing trades** in `backtest_charts_12mo.json` (the bar-path-bearing subset of the 1,289-trade engine run summarised in `backtest_metrics_full.json`; `POPULATION_N` in `research/omen34_inputs.md`). Each trade's realized R is its actual realised outcome, `(exit_price − entry)/risk × direction` — the trade as it really happened (all 970 are unscaled, so the final `exit_price` is the clean outcome; R-sign matches the engine `outcome` field on 969/970, the 1 mismatch is the lone scratch).

- **The veto (spec definition).** At entry, find the nearest **weight>=3.0 node in the trade's direction** (above entry for a long, below entry for a short). If that node sits closer than `thr` R from entry, the trade is vetoed — the best realistic outcome is under +1R against −1R of risk, so the trade is skipped. Weight>=3.0 nodes are exactly the two types per `research/levels.py`: **HOD/LOD (3.0)** and **$50-multiple psychological numbers (3.0)**; PDH/PDL/PMH/PML (2.5) and pivots/swings (2.0) fall below the >=3.0 cutoff and are excluded by construction. Nodes are computed from the trade's embedded candle window (`candles[:entry_i+1]`) — the same window the trade travelled, and the same node definition `research/h5_frontrun.py` uses, so the two rows share one level set.

- **Primary endpoint: mean realized R**, vetoed vs non-vetoed. Tested with a **Welch t on day-clustered means** (per-day mean R within each group, then a Welch two-sample t on the two vectors of day-means) and a **day-block bootstrap 95% CI on the difference** `mean_R_nonvetoed − mean_R_vetoed` (days resampled with replacement; within each resampled day both groups are rebuilt, preserving day-clustering and within-day composition, 10,000 resamples). Secondary: n, median realized R, win rate (R>0), and the veto rate as a fraction of all trades — for each group at each threshold.

- **Threshold sweep** at 0.8R, 1.0R, 1.2R, 1.5R. A real effect degrades smoothly across the sweep; an effect that exists at only one threshold is noise.

- **Two self-lie checks, both reported.** (1) Veto-rate sanity: if the veto fires on <5% or >40% of trades the threshold is measuring something other than what it claims — the rate is stated at each threshold *before* the verdict. (2) ATR confound: vetoed trades are not a random sample (they are trades near strong levels, which may differ in volatility), so ATR at entry is reported for both groups to keep a confound visible.


## Headline

The veto **does not pay for itself in any detectable way**. Across the four thresholds the veto fires on 0.8R→42.3%, 1.0R→49.6%, 1.2R→55.2%, 1.5R→64.0% of the 970 trades — **above the spec's 40% upper bound at every threshold**, so per the row's own diagnostic the threshold is measuring something other than what it claims. The mean-realized-R difference between vetoed and non-vetoed trades is tiny (within ±0.08 R everywhere) and its sign is inconsistent across the sweep — **the vetoed trades are actually higher in mean R at three of the four thresholds** (0.8R, 1.2R, 1.5R), and lower only at 1.0R, which is the opposite of the 'veto removes the losers' hypothesis at the very threshold (0.8R) where it should bite hardest. The day-block bootstrap CI on the difference **straddles zero at all four thresholds** (0/4 exclude zero). With no monotonic degradation and no threshold significant, the partition carries no signal: the veto as defined does not isolate a losing subset.


## Four-threshold sweep table

Realized R is in R units (risk = |entry − stop|). `diff = mean_R_nonvetoed − mean_R_vetoed`; a positive diff means the trades the veto removes are worse (the veto pays for itself). Win rate = fraction of trades with R > 0. ATR is the 14-bar 1-minute ATR at entry ($/share).

| thr | n_all | n_vetoed | n_nonvetoed | veto rate | mean R (vetoed) | median R (vetoed) | win% (vetoed) | mean R (non-vetoed) | median R (non-vetoed) | win% (non-vetoed) | diff (R) | bootstrap 95% CI on diff | Welch t (day-clustered) | df | p (Welch) | ATR vetoed | ATR non-vetoed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 0.8R | 970 | 410 | 560 | **42.3%** | +0.0412 | -1.0000 | 34.9% | +0.0092 | -1.0000 | 34.1% | -0.0320 | [-0.2230, +0.1581] | -0.860 | 386.5 | 0.39 | +0.8027 | +0.8509 |
| 1.0R | 970 | 481 | 489 | **49.6%** | +0.0115 | -1.0000 | 33.9% | +0.0337 | -1.0000 | 35.0% | +0.0223 | [-0.1653, +0.2106] | -0.673 | 408.6 | 0.502 | +0.7852 | +0.8750 |
| 1.2R | 970 | 535 | 435 | **55.2%** | +0.0303 | -1.0000 | 34.6% | +0.0134 | -1.0000 | 34.3% | -0.0169 | [-0.1997, +0.1651] | -1.111 | 401.4 | 0.267 | +0.7876 | +0.8832 |
| 1.5R | 970 | 621 | 349 | **64.0%** | +0.0501 | -1.0000 | 35.3% | -0.0261 | -1.0000 | 33.0% | -0.0763 | [-0.2537, +0.1021] | -1.372 | 368.3 | 0.171 | +0.7837 | +0.9137 |

Welch t is on day-clustered means: each group is collapsed to one mean R per day (vetoed group spans 207 days, non-vetoed 204 days at 1.0R; a day can appear in both vectors), then a Welch two-sample t compares the two day-mean vectors. The bootstrap CI resamples days with replacement and rebuilds both groups within each resampled day, so it respects the same clustering.


## Self-lie check 1 — veto rate (state before the verdict)

| threshold | veto rate | in 5%–40% band? |
|---|---|---|
| 0.8R | 42.3% (410/970) | **NO — > 40%** |
| 1.0R | 49.6% (481/970) | **NO — > 40%** |
| 1.2R | 55.2% (535/970) | **NO — > 40%** |
| 1.5R | 64.0% (621/970) | **NO — > 40%** |

The veto rate **exceeds 40% at all four thresholds** (42.3% / 49.6% / 55.2% / 64.0%). Per the spec's own diagnostic this means the threshold is measuring something other than what it claims. The reason is structural, visible in the node-type breakdown below: the nearest weight>=3.0 node in the trade's direction is the **session HOD/LOD in 98% of trades** (HOD for longs, LOD for shorts), not a distinct overhead/underfoot wall. HOD/LOD are computed up to and including the entry bar, so for a breakout entry — which by construction sits at the session extreme — the 'nearest wall in front' is the high/low the entry just made, a few ticks away. So 'distance to the nearest weight>=3.0 node in the trade's direction' is mostly 'how far the entry sits from the running session extreme', which is near zero for breakouts. The $50-multiple wall — the level the 'wall in front' story is actually about — is the nearest in-direction node in only 22/970 trades; the veto is dominated by a level (HOD/LOD) that tags the entry itself rather than a wall ahead of it.


## Self-lie check 2 — ATR confound (keep it visible)

| threshold | ATR vetoed | ATR non-vetoed | ratio (vetoed/non-vetoed) |
|---|---|---|---|
| 0.8R | +0.8027 | +0.8509 | 0.943 |
| 1.0R | +0.7852 | +0.8750 | 0.897 |
| 1.2R | +0.7876 | +0.8832 | 0.892 |
| 1.5R | +0.7837 | +0.9137 | 0.858 |

Vetoed trades have **lower ATR at entry** than non-vetoed trades at every threshold (ratio 0.86–0.94). The partition is therefore not a random sample: low-volatility trades are more likely to be vetoed, plausibly because in a tight range the entry sits close to the session HOD/LOD (so the 'wall' is within 1R by construction), whereas high-volatility trades have already extended away from the extreme. So any mean-R gap between the groups is entangled with a volatility difference, not a clean risk/reward effect. The confound is reported here rather than hidden; it is modest (~10% ATR gap) but it is the same direction at every threshold.


## Node-type breakdown (why the rate is high)

Nearest weight>=3.0 node **in the trade's direction**, across the 970 trades:

- LOD: 499 (51.4%)
- HOD: 439 (45.3%)
- psych50: 22 (2.3%)
- none: 10 (1.0%)

HOD/LOD dominate (938/970 = 96.9%); a $50-multiple is the nearest in-direction wall in only 22 trades (2.3%), and 10 trades (1.0%) have no weight>=3.0 node in the trade's direction at all (the entry sits beyond every $50-multiple in range and the session extreme is on the wrong side). Because the dominant node is the session extreme measured through the entry bar, the veto is essentially 'did the entry sit within `thr` R of the high/low of the session so far' — a description of where the entry is, not of a wall standing in front of the target.


## Does the effect degrade smoothly? (the spec's noise test)

| threshold | diff (R) | bootstrap CI | sign of diff |
|---|---|---|---|
| 0.8R | -0.0320 | [-0.2230, +0.1581] | vetoed > non-vetoed |
| 1.0R | +0.0223 | [-0.1653, +0.2106] | non-vetoed > vetoed |
| 1.2R | -0.0169 | [-0.1997, +0.1651] | vetoed > non-vetoed |
| 1.5R | -0.0763 | [-0.2537, +0.1021] | vetoed > non-vetoed |

It does not degrade — it **does not exist at any threshold**. The point estimate of the difference is within ±0.08 R everywhere, the bootstrap 95% CI straddles zero at all four thresholds, and the **sign is inconsistent** across the sweep: the vetoed mean R is higher at 0.8R, 1.2R and 1.5R, and lower only at 1.0R. A real 'wall within 1R hurts' effect would make `diff` (non-vetoed − vetoed) **largest and positive at the tightest threshold** 0.8R — that is where the veto removes the fewest, most-clearly-'blocked' trades, so if the rule works at all it works there — and would shrink smoothly toward zero as the threshold loosens and the vetoed set dilutes toward the population. Instead `diff` is **negative at 0.8R** (−0.032 R: the removed trades are slightly *better* than the kept ones) and never significantly positive at any threshold. Wrong sign at the strongest point, plus CI-through-zero everywhere, is the signature of noise, not a smooth effect.


## Verdict

The veto in front of a wall **does not pay for itself**. Two independent lines of evidence, both required by the spec, agree:

1. **The rate diagnostic fails.** The veto fires on 42–64% of trades — above the 40% bound at every threshold — because the nearest weight>=3.0 node in the trade's direction is the session HOD/LOD (through the entry bar) in 98% of trades, so the veto is tagging 'entry near the session extreme', a property of the entry, not a wall ahead of the target. The threshold is measuring something other than what it claims.

2. **The mean-R difference is null.** The primary endpoint — mean realized R, vetoed vs non-vetoed — shows a difference within ±0.08 R at every threshold, a day-block bootstrap 95% CI that straddles zero at all four thresholds, and a sign that is wrong at the strongest point: the vetoed trades are higher in mean R at 0.8R/1.2R/1.5R (lower only at 1.0R), so the veto removes trades that are if anything slightly *better* than the ones it keeps at the threshold where it should bite hardest. The Welch t on day-clustered means is not significant at any threshold (p = 0.8R→0.39, 1.0R→0.502, 1.2R→0.267, 1.5R→0.171). No monotonic degradation across 0.8/1.0/1.2/1.5R.

A visible confound does not rescue it: vetoed trades have ~10% lower ATR at entry, so the partition sorts on volatility as well as on 'wall distance', and even that confounded partition produces no mean-R gap. So the veto as defined removes trades indistinguishable in average outcome from the ones it keeps; it does not pay for itself. This is a null, reported as a null — the row's value is that the veto can be discarded as a trade-removal rule without losing expected R, *and* that the HOD/LOD-through-the-entry-bar node definition is the wrong way to operationalise 'a wall in front' (it tags the entry, not the wall); a $50-multiple / prior-structure-ahead version would be the cleaner test, but with only 22 trades where a $50-multiple is the nearest in-direction wall, that test is hopelessly underpowered on this population.


## Caveats

1. **Realized R is the actual trade outcome, not a resimulation.** `(exit_price − entry)/risk × direction`. All 970 trades are unscaled (`scaled=False`), so the final `exit_price` is the clean exit; R-sign agrees with the engine `outcome` field on 969/970 (the 1 mismatch is the lone scratch, R=0). This is a partition of realised outcomes, so it inherits the engine's exit management — it tests 'would removing these trades have helped the realised book', not 'would a different target have filled'.

2. **HOD/LOD are measured through the entry bar.** Consistent with `research/levels.py` and `research/h5_frontrun.py` (seg = bars[:entry_i+1]). This is exactly what makes the rate exceed 40%: a breakout entry defines a new session extreme, so the 'nearest wall in the trade's direction' collapses onto the entry. An alternative that excludes the entry bar (HOD over bars[:entry_i]) would measure the *prior* extreme — the wall just broken, now behind — and would change the rate; that is a different rule from the one the spec defines (weight>=3.0 node in the trade's direction) and is not the test run here.

3. **Welch t on day-clustered means collapses each group to per-day means.** Days with no trade in a group contribute no day-mean to that group's vector; a day can contribute to both vectors. This is the standard collapse-then-test cluster approximation; the day-block bootstrap is the clustered inference that backs the verdict (it resamples whole days and rebuilds both groups within each resample, so it respects the same within-day dependence).

4. **237 trading days underlie the 970 trades.** Clustering is by `day`; trades on the same day share a regime and are not independent, which is why both tests cluster on day rather than treating trades as i.i.d.

5. **$50-multiples are the only 'wall ahead of the target' node at weight>=3.0.** They are the nearest in-direction node in only 22/970 trades, so a veto defined on $50-multiples alone (the clean 'wall in front' reading) would be testable on ~22 trades — far under any power floor. The HOD/LOD dominance is what gives the veto a non-trivial sample size, and also what makes it measure the entry rather than the wall.


---
_Reproducible: `python3 research/h3_veto.py` regenerates this file._

