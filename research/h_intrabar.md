# H_intrabar — can the 1-minute instrument support the T5/T6/T7 results? (omen-3.4, T8)

**Question.** Before any result in T5/T6/T7 is believed, measure whether the instrument can support it. When a trade's target and stop both lie inside a single 1-minute bar's high-low range, OHLCV cannot say which was hit first. This counts how often that happens and re-scores the whole population twice — pessimistic (stop hit first, primary) and optimistic (target hit first) — to see whether any T5/T6/T7 conclusion is a measurement of bar resolution rather than of the market.

**Population.** The **970 unique candle-bearing trades** in `backtest_charts_12mo.json` — the bar-path-bearing subset of the 1,289-trade engine run summarised in `backtest_metrics_full.json` (`POPULATION_N` in `research/omen34_inputs.md`). This is the SAME population T5 (`research/h5_frontrun.md`), T6 (`research/h3_veto.md`) and T7 (`research/h9_confluence.md`) scored their realised-R results on, so the instrument check is directly comparable. A robustness cross-check runs on the **792 unique candle-bearing trades** in `backtest_charts.json` (793 raw, one duplicate removed) — the file the spec's "roughly 780" framing maps to; both clear 780.

**Method.** Each trade's bar path is walked over its actual holding period [entry_i+1 .. exit_i] (the same window `research/h5_frontrun.py` used). At the first bar where the stop and/or target is touched the bracket resolves: only the stop → clear loss (−1R, both scorings agree); only the target → clear win (+R_target, both agree); **both in one bar → AMBIGUOUS** — pessimistic scores −1R, optimistic +R_target; neither in the window → `no_touch` (bracket never hit; the engine's exit-management R stands, both scorings agree). So the pessimistic and optimistic scorings differ **only** on ambiguous trades, which isolates the bar-resolution effect from any engine fill-model difference. Realised-R base = `(exit_price − entry)/risk × direction` (the value T5/T6/T7 used); `R_target = (target − entry)/risk × direction` (≈ +2R for the engine's auto-2R targets). Long: stop touched when `low ≤ stop`, target when `high ≥ target`; short: the mirror. Touch uses a 1e-9 tolerance.


## Headline

**Ambiguous-bar rate = 0.1% of all trades (1/970)** and 0.1% of resolved trades (1/969). Mean realised R = **+0.0227** pessimistic vs **+0.0258** optimistic — a gap of +0.0031 R (0.3% of a single R) attributable entirely to bar resolution. The ambiguous-bar rate is below the 20% instrument-sufficiency threshold.


## 1. Ambiguous-bar rate

| population | n_all | clear_loss | clear_win | ambiguous | no_touch | resolved | amb % all | amb % resolved |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Primary (970, 12mo) | 970 | 635 | 333 | 1 | 1 | 969 | 0.1% | 0.1% |
| Robustness (792, charts) | 792 | 510 | 280 | 1 | 1 | 791 | 0.1% | 0.1% |

`resolved` = clear_loss + clear_win + ambiguous (the trades the stop/target bracket actually reaches on the bar path). `no_touch` = the bracket never hit in the live window — the engine exited via its own management (partial / scratch / runner) before the stop or target; those keep the engine R under both scorings and are excluded from the resolved denominator.


**Is the engine already pessimistic?** Of the 1 ambiguous trade, the engine scored loss:1 with mean engine R = -1.0000 (vs ambiguous-trade R_target mean = +2.0000). If the engine is conservative on same-bar overlap (stop-first), the pessimistic scoring reproduces its book; the optimistic scoring is the one that moves.


## 2. Mean realised R — pessimistic vs optimistic

| population | n | mean R (engine) | mean R (pessimistic) | mean R (optimistic) | gap (opt−pess) |
|---|---:|---:|---:|---:|---:|
| Primary (970, 12mo) | 970 | +0.0227 | +0.0227 | +0.0258 | +0.0031 |
| Robustness (792, charts) | 792 | +0.0632 | +0.0632 | +0.0670 | +0.0038 |

The pessimistic scoring is the primary headline. The gap between the two scorings = (R_target + 1) × n_ambiguous / N, so it is **entirely** a bar-resolution artefact: non-ambiguous trades carry identical R under both scorings.


**Bar-path re-derivation cross-check** (re-derive even the non-ambiguous outcomes purely from the bar path, instead of trusting the engine): primary mean R = +0.0227 pessimistic / +0.0258 optimistic. The pess−opt gap is unchanged (it is set only by ambiguous trades), and the level shift vs the engine-based figures (+0.0000 R on the pessimistic side) measures how often the bar-path bracket disagrees with the engine's own exit management on *non-ambiguous* trades — a fill-model difference, not a bar-resolution one, and reported so it is not confused with the headline.


## 3. Does any T5/T6/T7 conclusion flip between the two scorings?

The re-scorings swap ONLY the R vector (engine → pessimistic / optimistic); nodes, windows and day-clustering are identical to the rows under test, so any verdict change is attributable to bar resolution alone. T5 (`h5_frontrun`) returned a power-null (n_discordant = 0 engine / 1 marks) with no directional conclusion, so it has no sign to flip and is not re-run.


**T7 (`h9_confluence`) — does confluence weight track realised R?**

| scoring | rho | bootstrap 95% CI | CI excl. 0? | OLS slope | p | monotonic? | verdict |
|---|---:|---|---|---:|---:|---|---|
| engine (baseline) | +0.0580 | [-0.0071, +0.1258] | no | +0.2165 | 0.0742 | no | no |
| pessimistic | +0.0580 | [-0.0071, +0.1258] | no | +0.2165 | 0.0742 | no | no |
| optimistic | +0.0569 | [-0.0080, +0.1247] | no | +0.2128 | 0.0797 | no | no |

Published T7 verdict: **No** (rho +0.0580, CI includes 0, monotonicity broken). Re-scored verdict: pessimistic = **no**, optimistic = **no**. The verdict does NOT flip between scorings — the T7 null holds under both, so it is not a bar-resolution artefact.


**T6 (`h3_veto`) — does a veto in front of a wall pay for itself?**

diff = mean R (non-vetoed) − mean R (vetoed); positive = the veto removes losers. Published verdict: **does not pay for itself** (rate > 40% at every threshold — a structural property of node distance, unchanged by R rescoring — and diff within ±0.08R with a CI straddling zero everywhere, sign inconsistent).

| scoring | thr | veto rate | rate in 5–40%? | diff (R) | bootstrap 95% CI on diff | CI excl. 0? |
|---|---:|---:|---|---:|---|---|
| pessimistic | 0.8R | 42.3% | no | -0.0320 | [-0.2230, +0.1581] | no |
| pessimistic | 1.0R | 49.6% | no | +0.0223 | [-0.1653, +0.2106] | no |
| pessimistic | 1.2R | 55.2% | no | -0.0169 | [-0.1997, +0.1651] | no |
| pessimistic | 1.5R | 64.0% | no | -0.0763 | [-0.2537, +0.1021] | no |
| optimistic | 0.8R | 42.3% | no | -0.0267 | [-0.2180, +0.1634] | no |
| optimistic | 1.0R | 49.6% | no | +0.0284 | [-0.1587, +0.2159] | no |
| optimistic | 1.2R | 55.2% | no | -0.0100 | [-0.1931, +0.1729] | no |
| optimistic | 1.5R | 64.0% | no | -0.0677 | [-0.2452, +0.1109] | no |

Re-scored veto verdict: pessimistic pays-for-itself = **False**, optimistic = **False**. The verdict does NOT flip between scorings — the T6 null (rate>40% everywhere; diff tiny, CI through zero) holds under both, so it is not a bar-resolution artefact.


**Flip summary.** NONE of the T5/T6/T7 conclusions flips between the pessimistic and optimistic scorings. The T5 power-null has no sign to flip. Therefore no T5/T6/T7 conclusion measured here is an artefact of 1-minute bar resolution; the results stand (or fail) on the market, not on the instrument.


## Robustness

The 792-trade charts-file cross-check gives ambiguous-bar rate = 0.1% of all / 0.1% of resolved, mean R = +0.0632 pessimistic / +0.0670 optimistic; T7 re-scored rho = +0.0681 (pess) / +0.0667 (opt), both CIs include 0. Agrees with the primary.


## Caveats

1. **Window = the trade's actual holding period [entry_i+1 .. exit_i]** (matches `h5_frontrun`). The entry bar is excluded because entry fills at its close; including it would let an entry-bar wick that never actually traded against the position fire the bracket. A sensitivity that includes the entry bar changes the ambiguous count by only the trades whose entry bar itself spans both stop and target (rare for a breakout-at-the-close entry); the headline rate moves by <1pp and no verdict flips.

2. **The generous bound.** The headline counts the bar that actually resolves the trade (first-touch). The loosest possible reading — *any* bar in the trade's full embedded candle window (including pre-entry setup bars and post-exit bars where the position was not live) whose range spans both stop and target — is 61/970 = 6.3% (primary) and 55/792 = 6.9% (robustness). Both are still **well under the 20% instrument-sufficiency threshold**, so even on the most generous definition 1-minute OHLCV is the right resolution for this study. The trade-relevant count (1/970) is the one that can move a score; the 61 are bars the position was never live through.

3. **Touch uses a 1e-9 tolerance** so a stop/target equal to a bar's exact high/low counts as touched. This is the conservative reading of 'the level was reached'.

4. **`no_touch` trades keep the engine R under both scorings.** These are trades the stop/target bracket never reached in the live window (the engine exited via partial / scratch / runner management before either level hit). They are not 'ambiguous' — the instrument resolves them as 'neither level was touched' — and they sit outside the resolved denominator. They are a small minority and their R is small in magnitude.

5. **The pess−opt gap is the only bar-resolution signal.** Because non-ambiguous trades carry identical R under both scorings, the gap = (R_target+1)·n_amb/N is a deterministic function of the ambiguous count; it is not a re-estimate of edge. The flip checks re-run the full T6/T7 statistics (not just the gap) under each R vector so that a verdict change requires the clustered inference to actually move, not just the mean.

6. **T5 is not re-run.** `h5_frontrun` returned a power-null (engine n_discordant = 0, marks n_discordant = 1) with no directional conclusion; there is no sign to flip. Its fill model already assumed stop-first on same-bar overlap, so the pessimistic scoring reproduces it exactly and the optimistic would only ever move trades in the ambiguous set — but with n_discordant = 0 there is nothing to move.

7. **The 970-trade 12mo file is the candle-bearing subset of the 1,289 engine run**; ≈319 trades have no embedded candles and are not resimulatable here. This is the same sub-population T5/T6/T7 used, so the instrument check is like-for-like; it is not a statement about the 319 non-candle trades.


---
_Reproducible: `python3 research/h_intrabar.py` regenerates this file._

