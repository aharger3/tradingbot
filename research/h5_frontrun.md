# H5 — does targeting just short of a round number fill more often? (omen-3.4, T5)

**Design.** Pure paired resimulation over the existing population — no new data, no new human input. Primary population = the **970 unique candle-bearing trades** in `backtest_charts_12mo.json` (a superset of `backtest_charts.json`; both at repo ROOT) — the bar-path-bearing subset of the 1,289-trade engine run summarised in `backtest_metrics_full.json` (`POPULATION_N` in `research/omen34_inputs.md`). Each trade keeps the 1m bar path it actually travelled. A secondary cross-check runs the same design on the 117 hand-marked trades in `research/marks_clean.jsonl` (the corpus where T4's target autopsy found the round-number clustering), over `data_archive` bars for the 75/117 archived marks.

- **Qualification:** a trade enters the paired test only if its original target lies within one tick ($0.01) of a **weight>=3.0 node**. Per `research/levels.py` the only weight>=3.0 node types are **HOD/LOD (3.0)** and **$50-multiple psychological numbers (3.0)**; PDH/PDL/PMH/PML (2.5) and pivots/swings (2.0) are below the threshold and excluded by the spec. `node N` below = the nearest weight>=3.0 node to the trade's target.

- **Two arms, same bar path** (primary window = entry_i+1 .. exit_i, the trade's actual holding period; both arms share the trade's stop):

  - **Arm A `at_node`**: target = N (exactly the round number / HOD-LOD).

  - **Arm B `frontrun`**: target = N − direction × max(1 tick, 0.10 × ATR_1m) — a few ticks *inside* the level (below it for a long, above it for a short), the Osler "just short of the round number" placement.

- **Fill model (identical for both arms):** a limit fills when the bar wick touches the target; if one bar spans both stop and target, the stop fires first (standard conservative convention — this is the only place the OHLC model can encode a wick-touch-and-reverse, and it is what lets the queue effect bite). The asymmetry between arms is the target *price* only; the fill rule is symmetric, so the fill-rate test is data-driven, not assumption-baked.

- **Endpoints (the second decides):** (1) `target_filled` binary, McNemar on discordant pairs (b = at_node-only fills, c = frontrun-only fills); (2) mean realized R, Wilcoxon signed-rank on paired differences d = R_frontrun − R_at_node plus a day-block bootstrap 95% CI on the mean.


## Headline

The test is **severely underpowered**. The weight>=3.0 qualification is the binding constraint: only **11** of the 970 engine trades target within one tick of a weight>=3.0 node (all HOD/LOD; none within one tick of a $50-multiple — the engine's auto-targets are 2R prices, the closest any sits to a $50-multiple is 3 ticks), and **n_discordant = 0** for the engine. The hand-marked cross-check has 4 qualifying trades and **n_discordant = 1**. Both are far below the 250-pair power floor, so no p-value below is treated as settling anything.


## Primary result — engine population (970 candle-bearing trades)

- Qualifying trades: **11** / 970. Skips: not_within_1tick=959.

- Fill concordance: both filled 1, neither filled 10, at_node-only (b) = **0**, frontrun-only (c) = **0**.

- **n_discordant = 0** (b + c = 0 + 0).

- Fill rate — at_node: 1/11 = 9.1%; frontrun: 1/11 = 9.1%.

- **McNemar result: undefined** (b = c = 0; no discordant pairs). The two arms fill on exactly the same trades, so the fill-rate endpoint carries no information. Exact binomial p is vacuously 1.0.

- Realized R — mean at_node = -0.7267, mean frontrun = -0.7350, mean diff (frontrun − at_node) = -0.0083 R, median diff = +0.0000 R.

- Wilcoxon signed-rank result: W+ = 0.0, n_nonzero = 1 (zero-diff pairs dropped), z = 0.000, two-sided p = 1.

- Day-block bootstrap (10,000 resamples, days resampled with replacement): mean diff = -0.0084 R, 95% CI = [-0.0272, +0.0000] R.

- Node-type breakdown: HOD(n=6, b=0, c=0), LOD(n=5, b=0, c=0).


## Cross-check — hand-marked corpus (117 marks, 75 archived)

- Qualifying trades: **4** / 117. Skips: not_within_1tick=71, not_archived=42. Window = full remaining RTH session (marks carry no exit_i).

- Fill concordance: both 1, neither 2, at_node-only (b) = **0**, frontrun-only (c) = **1**.

- **n_discordant = 1** (b + c = 0 + 1).

- McNemar result: exact two-sided p = 1, b = 0, c = 1.

- Realized R — mean at_node = 0.0625, mean frontrun = 0.5858, mean diff = +0.5233 R. Wilcoxon: W+ = 2.0, n_nonzero = 2, p = 1; bootstrap 95% CI = [-0.0802, +1.6500] R.

- Node-type breakdown: LOD(n=3, b=0, c=1), HOD(n=1, b=0, c=0).


## Do the two endpoints agree?

**Engine (primary):** No discordant pairs (b=c=0): the fill-rate endpoint carries no information (b=c=0, no discordant pairs); the realized R nominally favours at_node (mean diff -0.0083 R, Wilcoxon p=1, bootstrap CI [-0.0272, +0.0000], not significant). With no fill discordance there is nothing for the two endpoints to disagree about — the test is null for lack of discordance, not by counter-evidence.

**Marks (cross-check):** The two endpoints do not contradict: fill rate nominally favours frontrun (b=0, c=1, n_discordant=1); the realized R nominally favours frontrun (mean diff +0.5233 R, Wilcoxon p=1, bootstrap CI [-0.0802, +1.6500], not significant); both nominally lean frontrun. But n_discordant=1 < 250, so the lean is a single-trial-size artefact, not evidence. The hypothesis is not settled.

Across both populations the two endpoints never *contradict* each other. In the engine they are silent (n_discordant=0; realized R nominally leans at_node only via the shave cost on the one shared winner, −0.008 R, not significant). In the marks both endpoints nominally lean frontrun (1 frontrun-only fill; +0.52 R mean diff) but on a single discordant pair, so the lean is a one-trial artefact, not evidence. The two populations' nominal leans even point opposite ways (engine at_node, marks frontrun), which is exactly what noise looks like at this sample size. So: no disagreement to report, and no agreement that means anything — the question is unsettled because n_discordant ≪ 250, not because frontrunning was shown not to work.


## Why the test is underpowered (read this before any p-value)

1. **The weight>=3.0 threshold is restrictive.** It admits only HOD/LOD and $50-multiples. The engine's auto-computed targets are 2R prices that almost never land there (0 of 970 within one tick of a $50-multiple; only 11 within one tick of HOD/LOD). The hand marks cluster on round numbers, but those are whole-dollar levels — weight 2.0 in `levels.py`, below the >=3.0 threshold — so only 4 marks qualify. The population the Osler story is *about* (round numbers) mostly sits below the spec's weight cutoff.

2. **The Osler shave is small relative to the failures.** The shave is max(1 tick, 0.10×ATR_1m) — a few ticks. The qualifying trades that fail do so by reversing to the stop *before price reaches even the shaved target*, so moving the target a few ticks closer does not convert the non-fill into a fill. The queue effect operates on wicks that reach the level and reverse; these trades do not reach the level at all.

3. **n_discordant is the honest headline, not any p-value.** Engine n_discordant = 0; marks n_discordant = 1. Both are far under 250. Quoting McNemar/Wilcoxon p-values here would imply a settled answer the data cannot support.


## Caveats

1. **Same-bar stop/tie convention.** Stop assumed first when one bar spans both stop and target. Standard conservative convention; applied identically to both arms, so it cannot manufacture a frontrun advantage — it only lets the geometric advantage (frontrun target closer to entry, touched earlier) show up. With n_discordant=0 (engine) it never did.

2. **Primary window = the trade's actual holding period (entry_i .. exit_i).** Both arms are evaluated only over the bars the trader was actually in the position. A full-candle-window robustness check on the engine gives the same null (n_discordant=0).

3. **Marks window differs.** Marks carry no exit_i, so the cross-check uses the full remaining RTH session. This is a different (looser) window than the engine primary; treated as a cross-check, not the headline.

4. **Weight>=3.0 nodes only** (HOD/LOD + $50-multiples). The Osler story is about round numbers specifically; HOD/LOD are included because the spec's threshold is weight>=3.0. The node-type breakdowns above separate them.

5. The primary population is the 970 candle-bearing engine trades, not the full 1,289 engine run (≈319 trades have no embedded candles and cannot be resimulated). This is a resimulation over realised paths, not an engine re-run.


---
_Reproducible: `python3 research/h5_frontrun.py` regenerates this file._

