# g171 refutation, refuter #2 — multiplicity and sampling error

**What is different now:** g171's money and ratio numbers reproduce exactly, but its headline
"every futures firm FAILS, rolling-252-session pass rate 0.0% for all" is an artifact of a
pass-rate statistic computed over **one** window. Recomputed over every possible start day at the
same $1,000 risk, the same firms pass **13.1%-27.6%** of the time. **VERDICT: REFUTED.**

Fill for every number below: signal-bar CLOSE entry, `stop_rule.stop_fill_price()` stops,
size-gated on `signal_runner.min_risk_floor`, index-pool first-of-day rows out of
`research/bt2y_trades_retest_on.json`, mapped to futures points by the daily futures/ETF close
ratio and sized by `sizing.dollars_futures` (1R nominal $1,000, contracts floored).
Reproduction script: `research/g171_futures_proxy_arms.py` (unmodified) driven from the
scratchpad harness described at the bottom.

## 1. Reproduction — every number in the claim is exact

Re-ran `python research/g171_futures_proxy_arms.py`. Byte-identical `firms` block; identical
money, ratio and overlap dicts.

| figure | claimed | reproduced |
|---|---:|---:|
| mapped days | 234 | 234 |
| full 2y $/day | -11.83 | -11.83 |
| H1 $/day | 48.34 | 48.34 |
| H2 $/day | -67.07 | -67.07 |
| ES=F/SPY ratio mean (stdev) | 10.073 (0.038) | 10.073 (0.0379) |
| matched overlap pairs | 2 | 2 |

So the arithmetic is not in dispute. The inference off it is.

## 2. The fatal defect: "rolling-252 pass rate" has n = 1

`rolling_252_pass_rate()` sets `window = min(252, n)`. The book has **234** mapped sessions, so
`window = 234` and `range(0, n - window + 1)` is `range(0, 1)` — **exactly one window**, which is
the same walk-forward pass already reported in the row beside it. Every JSON row confirms it:
`"rolling_252_windows": 1`. "0.0% for all" therefore means "the single eval that started on
2024-09-03 failed", restated as a percentage. It is not a pass-rate distribution and carries no
information about start-date sensitivity — which is the only thing that statistic exists to
measure.

## 3. Corrected rolling-start pass rate — the firms do not all fail

Every start day in the book, a 120-session eval from that day, same `evaluate_prop_challenge`,
same firm parameters, same $1,000 risk the arm shipped (214 starts each):

| firm | starts | pass% at 1R=$1,000 | best risk in sweep | pass% there |
|---|---:|---:|---:|---:|
| Topstep 50K Combine | 214 | **20.6%** | $3,000 | 28.5% |
| Topstep 100K Combine | 214 | 13.1% | $3,000 | 20.1% |
| Topstep 150K Combine | 214 | 14.0% | $3,000 | 19.6% |
| Apex 50K Eval EOD | 214 | **27.6%** | $2,000 | 36.4% |
| Apex 100K Eval EOD | 214 | 13.1% | $3,000 | 25.7% |
| Apex 150K Eval EOD | 214 | 14.0% | $3,000 | 19.6% |
| TPT Test 50K | 214 | 20.6% | $2,000 | 32.7% |
| TPT Test 100K | 214 | 13.1% | $3,000 | 25.7% |
| TPT Test 150K | 214 | 14.0% | $3,000 | 19.6% |
| MFFU Rapid 50K | 214 | 20.6% | $2,000 | 32.7% |
| MFFU Rapid 100K | 214 | 13.1% | $3,000 | 25.7% |
| Earn2Trade TCP 25K | 214 | **23.8%** | $3,000 | 35.0% |
| OneUp 100K | 214 | 16.8% | $3,000 | 29.9% |

The claim's "fails at day 13-18" is one draw from this distribution, and it is the *first* draw —
the eval was only ever started on the book's opening session. Start it a week later and roughly
one attempt in five clears a $50K combine.

This does not make a futures lane a good idea: a 20% clear rate on a stream whose mean is
statistically zero is gambler's ruin with a monthly fee attached, and a passed eval is not a
profitable funded account. But "0.0% pass rate, no futures lane is fundable" is a stronger and
different statement than the data supports, and it is the statement that was made.

## 4. The risk grid the spec asked for was never swept

Spec P1 says to size with `research/sizing.dollars_futures` (MES/MNQ/M2K, **1R per firm's risk
grid**). `sizing.dollars_futures` reads a module-level `R_DOLLARS = 1_000.0` and takes no risk
argument, so the arm is pinned to a single risk point for every firm — $1,000 per trade against
Topstep 50K's **$2,000** trailing drawdown. Two consecutive losers end that eval by construction,
independent of any edge. `g71_propfirm_sim.RISK_GRID` (=$50 to $3,000) exists precisely to find
the passing band and was not used. Column 4 above is that sweep; it moves every row.

## 5. Sampling error — the money numbers are indistinguishable from zero

Paired bootstrap on sessions, 20,000 resamples, seed 7:

| window | days | $/day | 95% CI |
|---|---:|---:|---|
| full 2y | 234 | -11.83 | **[-107.10, +84.44]** |
| H1 | 112 | +48.34 | [-100.80, +201.68] |
| H2 | 122 | -67.07 | [-189.38, +56.13] |

H1 minus H2 gap: +115.41/day, 95% CI **[-76.20, +312.67]**, p(H1 <= H2) = 0.122. The H1/H2 split
in the claim is not a regime change; it is noise. Reporting "$48.34 vs -$67.07" as two findings
overstates a difference a two-sided test does not resolve.

## 6. Multiplicity — 13 rows, one sample

The 13 firm rows are not 13 independent tests. They are one P&L sequence read through 13
parameter sets, all starting on the same session, and 11 of the 13 fail in the same 13-18-day
band for the same mechanical reason (fixed $1,000 risk vs a $2,000-$5,000 trail). Treating
"13/13 FAIL" as convergent evidence double-counts a single draw. Note the direction: multiplicity
here inflates *confidence in the negative* rather than the usual false-positive risk — but it is
still an overstatement of evidence.

The overlap check has the opposite problem, and the claim already discloses it: **2** matched
pairs from a simplified PDH/PDL detector that is not the shipped engine. A stdev of 0.0012 on
n = 2 is not a basis-error distribution; it is two numbers. The correct reading is "untested",
not "tight".

## 7. Lookahead — real, immaterial

`ratio_for_day` uses the **same trading day's** futures/ETF closing ratio to map a 09:35 entry.
That close is not knowable at entry. Re-run with a strictly prior-day ratio: 234 days,
**-$11.78/day** against the shipped -$11.83 (233 of 234 contract counts change; P&L barely
moves). Real defect, not load-bearing. Flag it; do not rebuild for it.

## 8. What survives

- The mapping mechanics (ratio, tick sizes, M2K preset, contract flooring, dropped-row handling)
  are sound and reproduce exactly.
- The Lucid BLOCKED row is honest and correctly refuses to fabricate.
- The *direction* survives: this stream has no measurable edge, so no futures lane is worth
  funding. That conclusion is right, for a reason the report does not give.

## 9. What must be corrected before this is quoted

1. Delete "rolling-252-session pass rate 0.0%" — it is n = 1. Replace with the corrected
   start-day distribution in section 3, or drop the statistic.
2. Fix `rolling_252_pass_rate` (`window = min(252, n)` must not equal `n`; use a shorter window,
   e.g. the firm's own `max_days`, and step the start).
3. Sweep `RISK_GRID` per firm as P1 asked, or state plainly that the arm tests one risk point.
4. State the $/day figures with their CIs and drop the H1/H2 regime reading.
5. Say "untested" for the overlap check, not "tight".

## Reproduction

Harness in the session scratchpad (`refute.py`, `refute2.py`): imports
`research/g171_futures_proxy_arms.py` unmodified, calls its own `fetch_daily_ratio`,
`load_index_pool_book` and `build_futures_daily`, then (a) bootstraps sessions, (b) re-runs
`omen_metrics.evaluate_prop_challenge` over every start day crossed with a 10-point risk grid,
(c) rebuilds the daily map from a lagged ratio table. No file under `research/marks/` and no
`*.jsonl` mark corpus was read or written.
