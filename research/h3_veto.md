# H3 — Does a veto in front of a wall pay for itself? (omen-3.4 / T6)

A pure analysis over the existing engine trade population
(`backtest_charts_12mo.json`, 974 records). No new data, no human input.

> **Headline: no. The veto does not pay for itself.** On the faithful engine-S/R
> "wall" node set, vetoed and non-vetoed trades are statistically indistinguishable
> on mean realized R at **every** threshold (0.8 / 1.0 / 1.2 / 1.5R): Welch p =
> 0.40–0.89, and every day-block bootstrap CI on the difference **crosses zero**.
> The difference sign is unstable (it flips *positive* at 1.0R — vetoed trades
> look marginally *better* there), which is itself the signature of noise. Median
> realized R is −1.000 and win rate ≈ 34% in **both** arms at every threshold, so
> the two populations are the same shape, not just the same mean. A coarse
> round-number variant trends negative (vetoed worse) but is never significant and
> is volatility-confounded (see the ATR check). The highest-value row in the
> version returns a clean null: removing these trades removes nothing.

## The veto (definition)

At entry, if the nearest node of weight ≥ 3.0 in the trade's direction sits closer
than `T·R`, the trade is vetoed — the best realistic outcome is under +1R against
−1R of risk. "In the trade's direction" = for a call, the nearest qualifying node
strictly *above* entry; for a put, the nearest strictly *below* entry. Distance is
`|node − entry|`; risk `R = |entry − stop|`. The whole population (974 records) is
partitioned into vetoed / non-vetoed. Primary endpoint = **mean realized R**
(continuous, computed from each record's actual `exit_price`: `(exit−entry)/R` for
calls, `(entry−exit)/R` for puts; loss = −1.000, win = +1.972 mean, 1 scratch).

## Node set — and why the engine S/R levels, not round numbers

The omen-3.4 weighted-node module (`research/levels.py`, T3) is **absent** on this
checkout — the same blocker documented in `research/target_autopsy.md` (T4) and
`research/h5_frontrun.md` (H5). The spec's "node of weight ≥ 3.0" is therefore not
computable in its full confluence form (round numbers + HTF levels + pivots,
weighted). The faithful no-new-data node set is the engine's **own S/R level
set**, which is the only significance-filtered "wall" set present in the data: each
record carries `levels = {PDH, PDL, PMH, PML, ORH, ORL}` (prior-day / prior-session
high–low and opening-range high–low) — exactly the levels the engine grades and
caps trades on (`signal_runner._grade_for_levels`: "levels in the trade
direction"; record `reason` text: *"level $321.20 blocks 2R path"*). Without T3's
weights, the weight ≥ 3.0 qualifier collapses to "is an engine S/R level"; every
engine level is treated as a qualifying wall. This is the documented proxy, not a
hidden one.

**Why not round numbers (H5's weight ≥ 3 = whole dollar)?** Because for the *veto*
the spec's own sanity check fails. A whole-dollar node sits ahead of almost every
entry within 1R, so the veto rate would be:

| node set (weight ≥ 3 reading) | T=0.8 | T=1.0 | T=1.2 | T=1.5 |
|---|---:|---:|---:|---:|
| whole-dollar round numbers (H5 reading) | 52.9% | 61.6% | 67.4% | 76.2% |
| **engine S/R levels (primary)** | 20.3% | 23.9% | 28.1% | 33.8% |
| coarse round numbers ($10/$50/$100, robust) | 5.7% | 7.4% | 9.2% | 11.3% |

The whole-dollar reading is **over 40% at every threshold** — it fires on most
trades, i.e. "the threshold is measuring something other than what it claims"
(every dollar is not a wall). The engine S/R set sits inside the 5–40% band and
degrades smoothly upward as the threshold widens — the signature of a node set
that is actually picking out walls, not a price grid. (The coarse round-number set
is reported below as a robustness variant.)

## Four-threshold sweep — primary (engine S/R levels, N = 974)

Population mean realized R = +0.0216. `vetoRate` = fraction of all 974 trades
vetoed. `diff = mean_R(vetoed) − mean_R(non-vetoed)`; negative ⇒ vetoed trades are
worse (veto would remove bad trades). `gain` = lift in population mean R from
removing the vetoed trades (`= −vetoRate · diff`).

| T | group | n | mean R | median R | win% | vetoRate | ATR |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.8 | vetoed | 198 | +0.009 | −1.000 | 33.8% | 20.3% | 0.827 |
| 0.8 | non-vetoed | 776 | +0.025 | −1.000 | 34.5% | — | 0.867 |
| 1.0 | vetoed | 233 | +0.035 | −1.000 | 34.8% | 23.9% | 0.813 |
| 1.0 | non-vetoed | 741 | +0.017 | −1.000 | 34.3% | — | 0.873 |
| 1.2 | vetoed | 274 | −0.001 | −1.000 | 33.6% | 28.1% | 0.805 |
| 1.2 | non-vetoed | 700 | +0.031 | −1.000 | 34.7% | — | 0.880 |
| 1.5 | vetoed | 329 | −0.014 | −1.000 | 33.1% | 33.8% | 0.804 |
| 1.5 | non-vetoed | 645 | +0.040 | −1.000 | 35.0% | — | 0.886 |

**Primary endpoint — mean realized R, per threshold:**

| T | diff (ved−nonv) | pop gain | Welch t (day-clustered) | p (two-sided) | day-block bootstrap 95% CI on diff | P(diff<0) |
|---:|---:|---:|---:|---:|---:|---:|
| 0.8 | −0.016 | +0.003 | 0.573 (df=204) | 0.568 | **[−0.240, +0.218]** | 0.555 |
| 1.0 | **+0.018** | −0.004 | 0.844 (df=239) | 0.399 | **[−0.189, +0.235]** | 0.438 |
| 1.2 | −0.032 | +0.009 | 0.388 (df=285) | 0.698 | **[−0.230, +0.173]** | 0.623 |
| 1.5 | −0.054 | +0.018 | 0.143 (df=333) | 0.886 | **[−0.239, +0.136]** | 0.710 |

- **Every bootstrap CI crosses zero** (both endpoints straddle 0) at every
  threshold → no significant separation. `P(diff<0)` is 0.44–0.71, a coin-flip, at
  no point approaching the 0.025 the spec would need for a one-sided call.
- **The sign is unstable.** It is negative at 0.8R, *flips positive* at 1.0R
  (vetoed trades look +0.018 R *better*, population *gain* negative), then
  negative again at 1.2/1.5R. A real effect degrades smoothly; this oscillates
  around zero — the spec's own "if it only exists at one threshold it is noise"
  test, applied here, says the effect exists at **no** threshold.
- **Median R = −1.000 and win rate ≈ 34% in both arms at every threshold** — the
  distributions overlap completely, not just at the mean. The veto is not selecting
  a different kind of trade; it is selecting the same kind by a label that does not
  predict outcome.

## The two ways this row can lie to itself — both checked

### 1. Veto rate outside 5–40%

Reported at each threshold above. On the primary engine-S/R node set the rates are
**20.3 / 23.9 / 28.1 / 33.8%** — inside the 5–40% band at all four thresholds and
monotone increasing, so the threshold is measuring what it claims (a nearby wall,
not a price grid and not a rare accident). The whole-dollar round-number reading
(53–76%, over 40% everywhere) is the failed alternative, reported explicitly so the
choice is not buried. The coarse-round variant (5.7–11.3%) sits near the floor but
inside the band.

### 2. ATR confound — vetoed trades are not a random sample

Vetoed trades are, by construction, near strong levels and may differ in
volatility. ATR at entry (mean true range of pre-entry 1-min bars) by group:

| T | ATR vetoed | ATR non-vetoed | ratio (v/nv) |
|---:|---:|---:|---:|
| 0.8 | 0.827 | 0.867 | 0.95 |
| 1.0 | 0.813 | 0.873 | 0.93 |
| 1.2 | 0.805 | 0.880 | 0.91 |
| 1.5 | 0.804 | 0.886 | 0.91 |

On the primary node set the confound is **small and runs the *wrong* way** for a
spurious effect: vetoed trades are marginally *less* volatile (≈0.91–0.95× the
non-vetoed ATR). So the null is not hiding a volatility artifact — there is nothing
to hide, and the small ATR gap does not favor the vetoed arm. The confound is
visible rather than hidden, as required.

The coarse-round variant tells the opposite story and is the reason it cannot
salvage the result: there the vetoed ATR is **1.42–1.56 vs 0.78–0.82** non-vetoed
(≈1.8× — see robustness below) — i.e. trades vetoed on a $10/$50/$100 round number
are in much higher-volatility regimes, so their worse R is a **volatility-regime**
difference, not a wall effect. Per the spec's own check, that signal is confounded.

## Robustness — coarse round-number node set ($10/$50/$100, N = 974)

| T | vetoRate | mean R vetoed | mean R non-vetoed | diff | Welch p | bootstrap CI on diff | ATR v / nv |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.8 | 5.7% | −0.148 | +0.032 | −0.180 | 0.378 | [−0.534, +0.208] | 1.56 / 0.82 |
| 1.0 | 7.4% | −0.213 | +0.040 | −0.253 | 0.125 | [−0.557, +0.073] | 1.45 / 0.81 |
| 1.2 | 9.2% | −0.204 | +0.044 | −0.248 | 0.192 | [−0.521, +0.055] | 1.42 / 0.80 |
| 1.5 | 11.3% | −0.185 | +0.048 | −0.233 | 0.148 | [−0.499, +0.052] | 1.46 / 0.78 |

This variant trends the way the veto hypothesis hopes (vetoed trades worse,
diff −0.18 to −0.25, P(diff<0) = 0.82–0.95) — but (a) it is **never significant**
(Welch p = 0.12–0.38; every bootstrap CI's upper bound is positive, so all cross
zero), and (b) it carries the **large ATR confound** above (vetoed ≈ 1.8× the
non-vetoed volatility). The spec's lie-detector is explicit that a volatility
difference in the vetoed set makes the R-difference uninterpretable as a wall
effect — so this trend is read as a regime artifact, not a confirmation. A veto
that only "works" on a node set whose vetoed arm is a different volatility regime
is not a veto that pays for itself; it is a volatility screen wearing a wall's
clothes.

## Robustness — traded-only subset (alert_only = False, N = 761, engine S/R levels)

Restricting to trades actually taken (A+/A/B, excluding the 213 C-grade alert-only
records) does not change the null. Population mean R = +0.074.

| T | vetoRate | diff | Welch p | bootstrap CI on diff |
|---:|---:|---:|---:|---:|
| 0.8 | 17.6% | −0.006 | 0.757 | [−0.257, +0.254] |
| 1.0 | 20.8% | **+0.076** | 0.361 | [−0.160, +0.312] |
| 1.2 | 24.7% | −0.012 | 0.944 | [−0.238, +0.219] |
| 1.5 | 29.6% | −0.015 | 0.897 | [−0.232, +0.207] |

Same picture: every CI crosses zero, the sign flips positive at 1.0R, p = 0.36–
0.94. The veto does not separate taken trades either.

## Verdict

**The veto does not pay for itself on this population.** At no threshold (0.8 /
1.0 / 1.2 / 1.5R) does vetoing trades on the nearest in-direction wall produce a
significant difference in mean realized R: all four Welch p-values are ≥ 0.40 and
all four day-block bootstrap CIs on the difference cross zero. The difference
oscillates around zero (negative, positive, negative, negative) — the
non-smoothness the spec flags as noise. Median R (−1.000) and win rate (≈34%) are
identical in both arms. The one variant that trends negative (coarse round
numbers) is non-significant and, by its own ATR gap, a volatility-regime artifact
rather than a wall effect. The two lie-detectors (veto rate in 5–40%; ATR confound
reported) are both satisfied on the primary node set: the rate is in-band and
smooth, and the ATR gap is small and runs against a spurious effect. Removing
these trades removes nothing — the cleanest outcome the highest-value row can
return, and an honest null rather than a p-hacked veto.

### Caveat (T3 absent)

The weight ≥ 3.0 qualifier is proxied by "is an engine S/R level" because
`research/levels.py` (T3) is absent. A full confluence-weighted node set (round
numbers + HTF levels + pivots, with weights) could in principle concentrate the
veto on a sparser, stronger set of walls than the six engine levels and might
behave differently. This result is therefore "the veto over the engine's own wall
set does not pay for itself," not "no veto could ever pay for itself." Producing
T3 and re-running this row is the one path that could overturn the null; on the
data that exists on this checkout, the null stands.
