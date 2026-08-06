# H5 — Does targeting just short of a round number fill more often? (omen-3.4 / T5)

A pure resimulation over the existing engine trade population
(`backtest_charts_12mo.json`, 974 records). No new data, no human input.

> **Headline: underpowered, and the two endpoints concur against frontrun.**
> `n_discordant = 0`. The fill-rate endpoint is degenerate (no discordant pairs,
> McNemar undefined) — frontrun fills identically to the at-node arm. The realized-R
> endpoint says frontrun is *worse* (Wilcoxon p ≈ 0.021, day-block bootstrap CI
> [−0.071, −0.018] R). The two endpoints **do not disagree** in the "fill-up /
> R-down" way the spec warns about: there is no fill improvement to flatter
> ourselves with, and R is worse. Both point the same way. But `n_eligible = 16`
> and `n_discordant = 0 ≪ 250`, so this is a small-sample, single-population
> result — **not a settled verdict**.

## Setup

For every trade whose target lies within one tick of a round-number node of
weight ≥ 3.0, two counterfactuals are simulated from the **same** 1-min bar path
(both arms share the original stop and the embedded `candles`):

- **A — at_node:** target = the round-number node.
- **B — frontrun:** target = `node − direction × max(1 tick, 0.10 × ATR_1m)`.

This is a **paired** design (both arms from one trade); only discordant pairs
carry information for the fill endpoint.

- **Tick** = $0.01 (US equity minimum increment).
- **ATR_1m** = mean true range of the pre-entry 1-min bars (fallback: all
  embedded bars), per trade.
- **Fill model = the engine's own** (`backtest_week.simulate_day`): a target
  fills when a bar's wick reaches it (high ≥ target for calls, low ≤ target for
  puts), **stop takes priority** on a bar where both hit, and an unresolved trade
  scratches at the last close. Realized R = (exit − entry)/risk for calls,
  (entry − exit)/risk for puts; loss = −1 R, scratch = R at last close.

### Fidelity check

Re-running the resim with each trade's **original** target reproduces the
recorded `outcome` on **974 / 974 (100.0%)** of trades. The bar-path fill model
is faithful to the engine, so the counterfactuals are trustworthy.

### Node weighting — caveat (T3 absent)

The omen-3.4 weighted-node module (`research/levels.py`, T3) is **absent** on
this checkout — the same blocker documented in `research/target_autopsy.md`
(T4). The spec's "node of weight ≥ 3.0" is therefore not computable in its full
confluence form (round numbers + HTF levels + pivots, weighted). H5 is
explicitly the **Osler (2003) round-number** hypothesis, and round numbers are
price-derivable, so the faithful no-new-data subset is implemented here:

- nodes = equity round numbers; **weight = whole$ → 3, $5-multiple → 4,
  $10/$50/$100 → 5**. `weight ≥ 3.0` ⟺ a round number (whole dollar or coarser)
  — the Osler round number for equities is the whole dollar, so the threshold
  is set so that baseline round number qualifies.
- Under a **coarser** weighting ($10-multiple = 3, the literal "rounder" reading)
  the eligible set is **0** (the engine's 2R targets do not land on $10 marks;
  see measurement below). The underpowered verdict is unchanged either way.

The engine trades options off stock R-multiples with **blind 2R targets**
(`target = entry ± 2·risk`); it does not target round numbers by construction.
That is the structural reason H5 has so few subjects here.

## Eligible population

| Eligibility (target within 1 tick of…) | count |
|---|---|
| weight ≥ 3 round number, whole-dollar weighting (primary) | **16 / 974** |
| $10-multiple (coarsest literal weighting) | 0 / 974 |
| any engine S/R level (PDH/PDL/PMH/PML/ORH/ORL) — context only | 11 / 974 |

The 16 eligible trades span 15 trading days (one day has 2), 10 calls / 6 puts,
across 12 symbols. Frontrun offsets range $0.02–$0.38 (median ≈ $0.08); i.e.
frontrun sits only a few cents in front of the round number.

## Endpoint 1 — fill rate (McNemar on discordant pairs)

| | frontrun filled | frontrun not | total |
|---|---|---|---|
| at_node filled | 6 | **0** | 6 |
| at_node not | **0** | 10 | 10 |
| total | 6 | 10 | 16 |

- `n_discordant = 0` (b = 0, c = 0).
- **McNemar is degenerate** — there are no discordant pairs, so no test is
  defined; the fill-rate *result* is that frontrun fills **identically** to
  at-node (6/16 both arms).
- `n_discordant = 0 < 250` ⟹ **the fill test is underpowered**; per the spec,
  no p-value is quoted as though it settled anything (there is no p-value to
  quote).

The 6 winners reached the node, so they necessarily passed through the frontrun
level (it is a few cents closer to entry) — both arms fill. The 10 losers were
stopped before reaching *either* target — neither fills. There is **no** case
where the wick reached the frontrun level but stopped short of the round
number, which is the Osler touch-and-reverse case the hypothesis is about.

### Why zero discordant — a resolution limitation

The Osler mechanism is a **limit-order-queue microstructure** effect at the
round number, operating at sub-minute / tick resolution: a wick touches the
round number, the at-node limit sits behind a queue and does not fill, the
frontrun limit (just short) does. The resimulation has only **1-minute** bars and
a **wick-touch = fill** model, which by construction cannot represent "touched
but did not fill behind the queue." With the spec's offset
(`max(1 tick, 0.10·ATR_1m)` ≈ a few cents) being smaller than typical 1-min
wick noise, a 1-min wick that reaches within the offset of the round number
almost always touches the round number too — so the at-node arm, under this
model, fills whenever frontrun does. The model therefore **overestimates
at-node fills** and **underestimates** frontrun's true fill advantage. Resolving
the Osler hypothesis properly would require tick-level data and a queue-based
fill model, neither of which exists on this checkout. The fill endpoint here is
best read as "uninformative at 1-min resolution," not as "frontrun doesn't help
fills."

## Endpoint 2 — realized R (Wilcoxon signed-rank + day-block bootstrap)

Paired difference = R_frontrun − R_at_node over all 16 eligible trades.

- at_node mean R = **+0.125**
- frontrun mean R = **+0.080**
- mean difference = **−0.044 R** (frontrun worse)
- nonzero differences: **6 / 16** (the 6 shared winners); all 6 are negative
  (frontrun exits at the lower target → `−offset/risk` per winner). The 10
  shared losers contribute 0 (both arms stop at −1 R on the same bar).
- **Wilcoxon signed-rank:** W = 0, **p ≈ 0.021** (all 6 nonzero ranks are
  negative; no ties).
- **Day-block bootstrap (10 000 resamples, resample whole days with
  replacement):** mean-difference 95% CI = **[−0.071, −0.018] R**, P(diff > 0) =
  **0.00**.

The R cost is mechanical and not a discovery: every trade both arms win,
frontrun gives up exactly `offset/risk` ≈ 0.09–0.16 R (the "last tick on every
winner" the spec names). With zero extra fills to compensate, frontrun's net R
is worse. Note this Wilcoxon is itself a very small sample (6 nonzero diffs),
so the p-value is an estimate, not a decisive verdict — but its sign is
guaranteed by the geometry (frontrun can only tie or lose R on shared winners,
and ties on shared losers).

## Do the two endpoints agree?

**Yes — they concur, and both against frontrun.** The fill rate does not
improve (n_discordant = 0; identical 6/16 fill in both arms) and realized R is
worse (−0.044 R, Wilcoxon p ≈ 0.021, bootstrap CI excludes 0). The disagreement
the spec anticipates — fill rate up while realized R gets worse, the
"flattering endpoint" trap — **does not occur**: there is no fill-rate gain at
all, so there is nothing flattering to report. Stepping in front of the level
buys zero extra fills here and costs the last tick on every winner. The honest,
single statement: **frontrun does not help on this population** — but that
statement rests on 16 eligible trades and 0 discordant pairs, so it is a
small-sample, single-population finding, not a settled verdict. The fill
endpoint in particular cannot resolve Osler's queue mechanism at 1-minute
resolution and is uninformative rather than negative.

## Robustness notes

- **Coarser node weighting** ($10-multiple = weight 3): eligible = 0. The
  engine's 2R targets do not sit on $10 round numbers. The "underpowered /
  frontrun-not-beneficial" conclusion is unchanged — it holds a fortiori.
- **Resim fidelity** 974/974: the counterfactual fill model reproduces the
  engine's actual outcomes exactly, so the only model risk is the 1-min
  wick-touch = fill abstraction discussed above (which biases *against*
  finding a frontrun fill advantage, i.e. against H5).
- **Eligibility is strict (1 tick = $0.01).** Widening it would import trades
  whose targets are merely *near* (not at) a round number and would no longer be
  the spec's population; it is not done here.

## What would actually test H5

Tick-level (or at least sub-minute) price data plus a queue-aware fill model
(order-book depth at the round number, fill-probability < 1 on a touch). On the
existing 1-min population the Osler hypothesis is not resolvable — the offset is
smaller than the bar's wick, so "touched the round number" and "touched
just-short" are indistinguishable.
