# H intrabar — can the 1-minute bar resolve what happened? (omen-3.4 / T8)

A pure resimulation over the existing engine trade population
(`backtest_charts_12mo.json`, 974 records). No new data, no human input.

> **Headline: the instrument can resolve essentially every trade.** On 974/974
> records the engine's own bar-path fill model (stop-priority on ties) reproduces
> the recorded `outcome` exactly. The ambiguous-bar rate — trades whose target
> **and** stop both lie inside the single 1-min bar that resolved them, so OHLCV
> cannot order the two touches — is **1 of 974 = 0.10% of all trades and 0.10% of
> resolved trades**. Scoring the population pessimistic (stop hit first → loss,
> −1R; the primary, = the engine default) gives **mean realized R = +0.0216**;
> scoring it optimistic (target hit first → win, +R at target) gives **+0.0247**.
> The two headline numbers differ by **+0.0031 R** — one trade's worth — and **no
> conclusion in T5, T6, or T7 flips between the two scorings.** The ambiguous rate
> is two orders of magnitude under the 20% bar, so 1-minute OHLCV is the right
> resolution for this study and no finer data needs to be bought to believe the
> prior rows.

## What "the bar can't tell us" means

A trade resolves on the **first post-entry 1-min bar whose wick reaches the stop
or the target**. If, on that one resolving bar, the wick reached *only* the stop,
the trade is a clean loss; if *only* the target, a clean win — OHLCV orders it
unambiguously. The bar is **ambiguous** only when that single resolving bar's
high–low range contains **both** the stop and the target (call: `low ≤ stop` and
`high ≥ target`; put: `high ≥ stop` and `low ≤ target`). Then both levels were
touched somewhere inside one minute and the OHLCV cannot say which came first —
the trade's fate is a measurement of bar resolution, not of the market.

This is exactly the engine's own tie-break: `backtest_week.simulate_day` /
`h5_resim.resim` give the stop priority when both hit on one bar. The pessimistic
scoring here is therefore the engine default and reproduces the recorded
population; the optimistic scoring flips only the ambiguous bars to target-first.

## Validation — the model is faithful

Re-running the resim with stop-priority and comparing the implied outcome to each
record's stored `outcome`:

| check | result |
|---|---|
| resim (stop-priority) vs recorded `outcome` | **974 / 974 agree (100.0%)** |
| mean realized R, pessimistic resim | +0.0216 |
| mean realized R, from recorded `exit_price` | +0.0216 (identical) |

The pessimistic mean realized R matches the +0.0216 reported in `h3_veto.md` (T6)
to four decimals, and the per-trade `exit_price` mean matches the resim mean
exactly. The bar-path fill model is faithful, so the counterfactual optimistic
scoring (which shares the same bars and only changes the tie-break) is trustworthy
too.

## Ambiguous-bar rate

| denominator | n | ambiguous | rate |
|---|---:|---:|---:|
| all trades (POPULATION_N) | 974 | 1 | **0.10%** |
| resolved trades (win/loss via target or stop) | 973 | 1 | **0.10%** |
| scratch (resolved at last close, neither level touched) | 1 | 0 | 0% |

The single ambiguous trade:

| symbol | day | dir | grade | entry | stop | target | recorded | R(pess) | R(opt) |
|---|---|---|---|---:|---:|---:|---|---:|---:|
| IREN | 2025-09-10 | call | B | 31.655 | 31.54 | 31.885 | loss | −1.000 | +2.000 |

One bar in IREN's path spanned the full stop→target range; the engine recorded it
a loss (stop first), the optimistic scoring calls it a +2R win. That is the
entirety of the disagreement between the two scorings.

### Why a broader "any bar spans both" count does not change this

A looser count — *any* post-entry bar whose range contains both stop and target —
flags **14 trades (1.44%)**. But 13 of those 14 resolved **unambiguously on an
earlier bar** (a wick reached only the stop or only the target first, ending the
trade there). A later bar that subsequently spans both levels is unlived
hypothetical price action; the trade was already decided. Only the **resolving**
bar can create outcome ambiguity, and only 1 trade's resolving bar does. The 1.44%
figure is reported here so the choice of denominator is not buried; the operative
ambiguity is the 0.10% resolve-bar number.

## Population mean realized R — both scorings

| scoring | tie-break on ambiguous bar | mean realized R (N=974) |
|---|---|---:|
| **pessimistic (primary)** | stop hit first → loss, −1R | **+0.0216** |
| **optimistic** | target hit first → win, +R at target | **+0.0247** |
| delta (opt − pess) | — | +0.0031 |

The two headline numbers differ by +0.0031 R — exactly the one ambiguous trade's
+3.0R swing (−1 → +2) spread across 974 trades. Both numbers are positive; the
near-zero population mean does not change sign.

### Traded-only subset (alert_only = False, N = 761)

| scoring | mean realized R | ambiguous | ambig % all | ambig % resolved |
|---|---:|---:|---:|---:|
| pessimistic | +0.0737 | 1 | 0.13% | 0.13% |
| optimistic | +0.0776 | 1 | 0.13% | 0.13% |

Same picture: one ambiguous trade (the same IREN B-grade call), +0.0039 R delta,
no sign change. Restricting to trades actually taken moves nothing.

## Does any conclusion in T5, T6, or T7 flip?

**No.** One trade in 974 changes between the scorings, by 3.0R. The shift in the
population mean is +0.0031 R (full pop) / +0.0039 R (traded-only). Each prior row's
verdict is checked against that magnitude:

- **T5 (H5 frontrun).** Eligible set = trades whose target lies within one tick of
  a weight ≥ 3 round number (n_eligible = 16). The ambiguous IREN trade's target
  (31.885) is **not** within one tick of a whole dollar (nearest is 32, 0.115
  away), so it is **not in the eligible set** — neither arm of H5 touches it. H5's
  `n_discordant = 0` fill endpoint and its realized-R diff are byte-identical
  under both scorings. No flip.
- **T6 (H3 veto).** The null rests on Welch p ≥ 0.40 and **every** day-block
  bootstrap CI crossing zero, across thresholds 0.8–1.5R, on group sizes n ≈
  198–776. Moving one trade by 3.0R shifts a group mean by at most 3.0/198 ≈
  +0.015R (and only if IREN lands in that arm) — an order of magnitude below the
  CI half-widths (±0.13 to ±0.24R) and far short of moving any p-value across
  0.025. The sign-unstable, CI-crosses-zero picture is unchanged. No flip.
- **T7 (H9 confluence).** The verdict is "directionally real but sub-detectable":
  Spearman ρ = +0.043 (CI [−0.024, +0.109], crosses zero), OLS β p = 0.643, MDE ≈
  0.090 vs observed 0.043, with a thin high-weight tail that breaks the ordering.
  A single trade's R moving by 3.0 cannot move a 974-point rank correlation past
  its detectable threshold, cannot push the bootstrap CI off zero, and cannot
  un-break the n ≤ 16 tail. No flip.

**Statement per the spec:** since no conclusion in T5, T6, or T7 flips between the
pessimistic and optimistic scorings, those conclusions are measurements of the
market (such as they are), not artifacts of bar resolution. The one trade that
disagrees is a single-name, single-day, B-grade call whose outcome is genuinely
indeterminate at 1-min resolution — and it is alone.

## Is 1-minute OHLCV the wrong resolution?

**No.** The ambiguous-bar rate is **0.10%** — two orders of magnitude below the
20% bar the spec sets for "1-minute OHLCV is the wrong resolution for this study."
The instrument resolves 99.9% of trades unambiguously, and on the one trade it
cannot resolve, the two scorings agree on the sign of the population mean and on
every prior row's verdict. Buying finer data (tick/second bars) is **not**
required to believe T5/T6/T7. If the ambiguous rate had exceeded 20%, that would
have been a finding about what data to buy next, not a reason to stop — it does
not.

## Verdict

The 1-minute bar can tell us what happened on 999 of 1000 trades. Ambiguous-bar
rate = **0.10% of all trades, 0.10% of resolved trades** (1 / 974). Population
mean realized R = **+0.0216 (pessimistic, primary)** vs **+0.0247 (optimistic)**,
a +0.0031R delta driven entirely by one IREN B-grade call. No T5/T6/T7 conclusion
flips between the two scorings. 1-minute OHLCV is the correct resolution for this
study; no finer data is needed to believe the prior rows.

### Artifacts

- `research/h_intrabar.py` — resim, ambiguity classification, both scorings.
- `research/h_intrabar_results.json` — headline numbers (both scorings, both
  denominators, traded-only subset, per-grade breakdown).
- `research/h_intrabar_rows.json` — per-trade row (kind, R_pess, R_opt) for audit.
