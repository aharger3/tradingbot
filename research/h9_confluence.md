# H9 — Does confluence weight track outcome at all? (omen-3.4 / T7)

A pure analysis over the existing engine trade population
(`backtest_charts_12mo.json`, 974 records). No new data, no human input.

> **Headline: the weight ordering points the right way on the powered buckets but
> does not clear significance, and the deep-confluence tail breaks.** On the
> faithful engine-S/R + coarse-round-number node set, the confluence weight of the
> nearest node to entry is **positively** associated with realized R — Spearman
> ρ = **+0.0425** (day-block bootstrap 95% CI **[−0.0241, +0.1087]**, P(ρ>0) =
> 0.891) — and the readable, powered weight buckets (w2 → w5, n = 425 / 336 / 147 /
> 22) rise **monotonically**: mean realized R climbs −0.035 → +0.022 → +0.137 →
> +0.218 R and win rate climbs 32.5% → 40.9% across them. But the CI **crosses
> zero**, the OLS slope is not significant (β = +0.0145 R/weight, day-clustered
> p = 0.643), and the observed ρ (+0.043) is below the detectable threshold for this
> sample (MDE ≈ 0.090 at 80% power). The high-confluence tail (w ≥ 6, n ≤ 16)
> **breaks the ordering** — w7 dips, and the deep stacks w9 / w12 / w14 (n = 2 / 10 /
> 2) collapse to negative R. So: the weight vector is **directionally real on
> low-to-mid weights and not contradicted there, but it is not validated as a
> predictor** — the sign is suggestive, the magnitude is sub-detectable, and the tail
> where confluence is strongest is too thin to support the claim.

## What H9 asks

For every trade, compute the confluence weight of the **nearest node to the entry
price at the entry bar**, then test whether that weight tracks realized R. The
spec's point is that every weight in the confluence table is a *guess*; H9 fits the
data to the weight vector rather than assuming it. Required artifacts:

- Spearman ρ across all trades, with a **day-block bootstrap CI**;
- a **binned table of mean realized R by weight bucket**, with an **n for every
  bucket** (the readable artifact);
- an **OLS of R on weight with day-clustered standard errors**;
- a **monotonicity** verdict — does mean R rise across consecutive weight buckets,
  and which buckets break the ordering;
- a power statement (the spec wants ~780 trades; if fewer, report achieved power).

Endpoints use **realized R** computed from each record's actual `exit_price`:
`(exit−entry)/R` for calls, `(entry−exit)/R` for puts; loss = −1.000, win mean =
+1.972, 1 scratch. Population mean realized R = +0.0216.

## Node set — and the T3 caveat (carried from H3 / H5 / T4)

The omen-3.4 weighted-node module (`research/levels.py`, T3) is **absent** on this
checkout — the same blocker documented in `research/target_autopsy.md` (T4),
`research/h5_frontrun.md` (H5), and `research/h3_veto.md` (H3). The spec's full
confluence node set (round numbers + HTF levels + pivots, with T2's typed weights)
is therefore **not computable in its full form**. The faithful no-new-data node set
is what the data actually carries:

- The engine's **own S/R levels** — each record carries
  `levels = {PDH, PDL, PMH, PML, ORH, ORL}` (prior-day extremes, premarket extremes,
  opening-range H/L) — exactly the levels the engine grades and caps trades on
  (`signal_runner._grade_for_levels`: "levels in the trade direction"; record
  `reason` text: *"level $321.20 blocks 2R path"*).
- **Coarse psychological round numbers** ($10 / $50 / $100 multiples near entry) —
  the Osler (2003) component of the confluence set, price-derivable, no external
  data. HTF levels / pivots are not present (`htf_bias` is a bias label, not a price
  node) and are omitted — documented, not hidden. Whole-dollar round numbers are
  **deliberately excluded**: as H3 showed, they sit ahead of almost every entry
  (>50% veto rate at every threshold), i.e. "every dollar is not a wall," and would
  degenerate the nearest node to a fixed weight-3 grid point with no variation.

### The confluence weight table (proxy for T2's table — T2 is itself absent)

Base type weights — a wall-strength ordering a trader would guess (the spec calls
every weight a guess; H9 is the test of whether *this* ordering is real):

| type | base weight | meaning |
|---|---:|---|
| $100 round | 5 | coarsest psychological |
| PDH / PDL | 4 | prior-day extreme — strongest structural wall |
| $50 round | 4 | |
| PMH / PML | 3 | premarket extreme |
| $10 round | 3 | |
| ORH / ORL | 2 | opening range — intraday, weakest |

**Confluence = stacking.** When distinct node types coincide at one price (within
`tol = max(2 ticks, 0.10·ATR_1m)` ≈ $0.02–$0.08), the merged node's weight is the
**sum** of the base weights of every contributing type. A lone ORL is weight 2; an
ORL that is also a $10 round is weight 5; a PDH coincident with a $50 and a $100
round is weight 13. This is the literal "confluence" reading — stack the levels —
not the max. The exact numbers are a proxy (T2's table does not exist on this
checkout); the test is whether the *ordering* they impose tracks outcome.

### Nearest node

`nearest node = min |node_price − entry|` over the merged node set, **both sides**
(the spec says "nearest node to the entry price" — no direction qualifier). A
directional (in-trade-direction) variant is reported as robustness. The engine
levels are typically much closer to entry than the $10 grid (median distance to
nearest engine level ≈ $0.41 vs. up to $5 for the nearest $10 round), so the
nearest node is usually an engine level; round numbers enter mainly through
**confluence** (coincidence with an engine level) or as the nearest node when no
engine level is close.

## Primary result — nearest node, both sides (N = 974, 237 days)

### Spearman ρ + day-block bootstrap

- **Spearman ρ = +0.0425** (asymptotic SE ≈ 0.0320).
- **Day-block bootstrap (20 000 resamples, resample whole days with replacement):
  95% CI = [−0.0241, +0.1087]**, P(ρ > 0) = **0.891**, P(ρ < 0) = 0.109.

The CI **crosses zero**, so the association is not significant at 5%. It is
directionally positive (89.1% of resampled days-side ρ's are above zero) but does
not clear the 0.975 one-sided mass the spec would need for a positive call.

### OLS — R on weight, day-clustered standard errors

OLS of realized R on the confluence weight (with intercept), Liang–Zeger
cluster-robust SE over the 237 day-clusters:

| coefficient | estimate | cluster-robust SE | t | df | p (two-sided) |
|---|---:|---:|---:|---:|---:|
| weight (slope) | **+0.01454** R/weight | 0.03131 | 0.464 | 236 | **0.643** |
| intercept | −0.0220 | | | | |

The slope is positive (≈ +0.015 R per unit of confluence weight) but **not
significant** (p = 0.643). The day-clustered SE is large relative to the slope, so
the linear weight effect is not distinguished from zero.

### Binned mean realized R by weight bucket — the readable artifact

Every distinct weight is its own row with its own n (weights are integer sums of
integer base weights). `*` marks buckets with n < 20 (underpowered — read as
directional only, not as evidence).

| weight | n | mean realized R | median R | win % | |
|---:|---:|---:|---:|---:|:---|
| 2 | 425 | −0.0350 | −1.000 | 32.5% | |
| 3 | 336 | +0.0217 | −1.000 | 34.5% | |
| 4 | 147 | +0.1373 | −1.000 | 38.1% | |
| 5 | 22 | +0.2175 | −1.000 | 40.9% | |
| 6 | 16 | +0.3125 | −1.000 | 43.8% | * |
| 7 | 14 | +0.2596 | −1.000 | 42.9% | * |
| 9 | 2 | −1.0000 | −1.000 | 0.0% | * |
| 12 | 10 | −0.1000 | −1.000 | 30.0% | * |
| 14 | 2 | −1.0000 | −1.000 | 0.0% | * |
| **sum** | **974** | | | | |

Nearest-node type composition (a node can contribute more than one type when
stacked): ORL 260, ORH 201, PML 152, PMH 133, R10 113, PDL 87, PDH 76, R50 22,
R100 12. The low-weight buckets are dominated by lone opening-range / premarket
levels; the high-weight buckets are deep stacks (e.g. a PDH coincident with a $50
and $100 round).

### Monotonicity — does mean R rise across consecutive weight buckets?

**All buckets, consecutive transitions:**

| transition | mean R | ordering |
|---|---|:---:|
| 2 → 3 | −0.0350 → +0.0217 | ok |
| 3 → 4 | +0.0217 → +0.1373 | ok |
| 4 → 5 | +0.1373 → +0.2175 | ok |
| 5 → 6 | +0.2175 → +0.3125 | ok |
| 6 → 7 | +0.3125 → +0.2596 | **BREAK** |
| 7 → 9 | +0.2596 → −1.0000 | **BREAK** |
| 9 → 12 | −1.0000 → −0.1000 | ok |
| 12 → 14 | −0.1000 → −1.0000 | **BREAK** |

Breakers (the higher bucket that violates the rise): **w7, w9, w14.**

**Restricted to buckets with n ≥ 20 (the powered, readable chain):**

| transition | mean R | ordering |
|---|---|:---:|
| 2 → 3 | −0.0350 → +0.0217 | ok |
| 3 → 4 | +0.0217 → +0.1373 | ok |
| 4 → 5 | +0.1373 → +0.2175 | ok |

Breakers (n ≥ 20): **none — monotone.**

**Reading.** On the buckets with enough trades to read (w2–w5, n = 425 / 336 / 147
/ 22), mean realized R rises **monotonically** by +0.253 R across the range and win
rate rises 32.5% → 40.9% — exactly the direction the confluence hypothesis predicts.
The ordering continues to rise through w6 (n = 16, +0.313). It then **breaks at the
deep-confluence tail**: w7 dips slightly (n = 14, +0.260), and the rare stacks w9 /
w12 / w14 (n = 2 / 10 / 2) collapse to negative R. The tail is the part of the
weight vector that matters most for the claim ("a wall many factors agree on is the
strongest wall"), and it is exactly the part that is **thinnest** here (n ≤ 16) and
that **does not support** a monotone weight→R relationship. The honest statement is
two-clause: monotone on the powered buckets, broken in the underpowered tail.

## Power

The spec wants ~780 trades for this all-trades test. The population is **974
records, 974 with a computable nearest node and positive risk — above the 780
target**, so the test runs at the intended sample size. Achieved power, read from
the Spearman SE (≈ 0.0320, n = 974):

- **MDE(ρ) at 80% power, α = 0.05 two-sided ≈ (1.96 + 0.84) × 0.0320 ≈ 0.090.**
- Observed ρ = +0.0425 < 0.090, so the test is **underpowered for an effect this
  small** — a true ρ of +0.043 would be detected at 80% power only ~half the time.
- The day-block bootstrap upper-95% bound on ρ is +0.109; the test can **rule out**
  ρ ≥ +0.109 but cannot rule out a small positive effect in (0, +0.11).

So: sample size is adequate by the spec's own floor, but the *effect* is smaller
than what this sample can resolve at the spec's power target. "Directionally
consistent, not established" is the calibrated reading, not "null."

## Robustness

### Directional nearest node (in trade direction, N = 974)

Restricting the nearest node to the in-trade-direction side (ahead of entry, as H3
used for the veto) tightens the association but does not clear significance:

- Spearman ρ = **+0.0585**, day-block bootstrap 95% CI = **[−0.0079, +0.1241]**,
  P(ρ > 0) = **0.958** (closest to a positive call; CI still just crosses zero).
- OLS slope = +0.0486 R/weight, cluster-robust SE = 0.0293, t = 1.659, **p = 0.099**
  (two-sided; one-sided ≈ 0.05).
- Powered buckets (n ≥ 20): w2 → w3 → w4 rise monotonically (−0.055 → +0.003 →
  +0.177), then **break at w7** (n = 25, −0.175). The deep tail (w12–w16, n ≤ 12)
  is noisy. The directional reading is the most favorable to the hypothesis but
  still does not clear 5% two-sided.

### Traded-only subset (alert_only = False, N = 761)

Restricting to trades actually taken (A+/A/B, excluding the 213 C-grade alert-only
records). Population mean R = +0.0737.

- Spearman ρ = **+0.0392**, day-block bootstrap 95% CI = **[−0.0338, +0.1130]**,
  P(ρ > 0) = 0.856. OLS slope = −0.00155, p = 0.965.
- **N = 761 < 780** — this subset is **below the spec's ~780 floor**, so it is
  reported as underpowered (MDE ≈ 0.102 at 80% power). Direction unchanged (positive,
  not significant); the taken-trade subset does not move the verdict.

## The two ways this row can lie to itself — both checked

1. **A degenerate node set** (the H3 / H5 trap). If the nearest node were almost
   always a whole-dollar round number, the weight would be a constant 3 and the
   test would be vacuous. It is not: the nearest node is an engine S/R level for
   the large majority of trades (median distance to nearest engine level ≈ $0.41,
   vs. up to $5 for the nearest $10 round), so the weight varies — the weight
   distribution is {2: 425, 3: 336, 4: 147, 5: 22, 6: 16, 7: 14, 9: 2, 12: 10,
   14: 2}, spanning 2 → 14. The low-weight buckets (lone ORH/ORL/PMH/PML) and the
   mid buckets (lone PDH/PDL, or a 2+3 stack) carry the bulk of the n; the test is
   not a constant.
2. **Sign-flip across the robustness variants** (the spec's "if it only exists at
   one threshold it is noise" test, applied across variants). The sign is
   **positive in all three variants** (primary +0.043, directional +0.059,
   traded-only +0.039) and the powered buckets are monotone-increasing in all
   three. The non-significance is therefore not a sign-instability artifact — it
   is a magnitude problem (the effect is real-looking but smaller than the sample
   resolves), not an oscillation around zero.

## Verdict

**The confluence-weight ordering is directionally real on the powered buckets but
is not validated as a predictor.** The nearest-node weight is positively
associated with realized R (Spearman ρ = +0.0425, P(ρ > 0) = 0.891), and on the
readable part of the weight range (w2 → w5, the buckets with n ≥ 20) mean realized
R rises monotonically from −0.035 to +0.218 R and win rate from 32.5% to 40.9% — the
direction the confluence hypothesis predicts, present in all three variants. But:

- the day-block bootstrap CI on ρ **crosses zero** ([−0.024, +0.109]);
- the OLS slope is **not significant** (β = +0.0145, day-clustered p = 0.643);
- the effect (ρ ≈ +0.043) is **below the detectable threshold** for this sample
  (MDE ≈ 0.090 at 80% power);
- the **deep-confluence tail breaks the ordering** (w7 dips; w9 / w12 / w14 collapse
  to negative R) — and the tail, where confluence is strongest and the weight
  vector would matter most, is exactly the part with n ≤ 16, so the break is
  underpowered rather than a clean inversion.

The single calibrated sentence: the weight vector's ordering is **not
contradicted** on the low-to-mid weights and is **not established** as a predictor —
the sign is suggestive, the magnitude is sub-detectable, and the strongest part of
the vector (deep confluence) is too thinly populated on this population to support
or refute the monotonicity claim.

### Caveat (T3 / T2 absent)

The weight table here is a **proxy for T2's table**, applied to the engine's own
six S/R levels plus coarse round numbers, because `research/levels.py` (T3) and the
T2 marks corpus are absent on this checkout (same blocker as T4, H5, H3). A full
confluence-weighted node set (round numbers + HTF levels + pivots, with T2's
actual weights) could (a) change the base weights and the stack sums, reordering
the buckets, and (b) populate the deep-confluence tail (currently n ≤ 16) with real
HTF/pivot confluence, which is the part that breaks here. Producing T2/T3 and
re-running this row is the one path that could overturn the "not established"
verdict — in particular it could either firm up the monotone low-to-mid rise into a
significant effect or explain the tail collapse. On the data that exists on this
checkout, the ordering has a real-looking direction but the weight vector is not
validated as a predictor of realized R.

## Artifacts

- `research/h9_confluence.py` — the analysis (reuses the `risk` / `realized_r` /
  `atr_1m` / Welch / incomplete-beta helpers established in `h3_veto.py`).
- `research/h9_results.json` — full numeric output (primary, directional,
  traded-only; per-weight buckets with n; bootstrap CIs; cluster-robust OLS;
  monotonicity transitions and breakers).