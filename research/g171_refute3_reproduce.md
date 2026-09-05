# g171 refuter #3 (reproduce-from-the-script lens) — VERDICT: REFUTED

What is different: g171's script reproduces byte for byte, and its money numbers are correct — but its "rolling-252-session pass rate 0.0% for all firms" is a bug, not a measurement, and it is the number that carries the headline. A true rolling-start pass rate on the same book, same risk, same simulator is **12.0%–26.5%**, not 0.0%.

## 1. Reproduction — PASS

Re-ran `research/g171_futures_proxy_arms.py` unmodified (imported as a module, `OUT_JSON`/`OUT_MD` redirected to scratchpad so nothing committed was touched).

| artifact | result |
|---|---|
| `g171_futures_proxy_arms.md` | `diff` empty — **identical** |
| `g171_futures_proxy_arms.json` | `diff` on sorted-key dump empty — **identical** |

Every quoted figure reproduces: 234 mapped days, 0 dropped, $-11.83/day, 48.3% win, 12/24 green; H1 $48.34/day 7/12; H2 $-67.07/day 5/12; ratios ES=F/SPY 10.073 (sigma 0.0379, 626 d), NQ=F/QQQ 41.3024, RTY=F/IWM 10.1163; overlap 3 ES / 4 SPY signals, 2 matched, intrabar ratio sigma 0.0012.

## 2. Fill and unit — CLEAN

- Book is `bt2y_trades_retest_on.json`, `meta.stamp.entry_fill = "close"`, `stop_rule` flags `DISASTER_STOP_R=1.0`, `RETEST_REQUIRED=True`. Honest close fill, as claimed.
- The script's local first-of-day selection returns **exactly the same 234 picks** as `research/omen_metrics.first_of_day_arm` restricted to `universe.INDEX_POOL` (set-compare of `(day, et, sym)`: 0 rows either side). Size gate present and equivalent.
- Sanity cross-check: the same 234 days priced as shares is **-$13.50/day, mean R -0.0135, 48.3% win, 12/24 green**. The futures mapping (-$11.83/day) differs only by micro-contract rounding shrinking realised risk below $1,000. The mapping is not manufacturing the loss.
- Multiplicity: one arm, no tuned constant. Clean.

## 3. Lookahead — MINOR, non-material

`fetch_daily_ratio` uses the **same trading day's 16:00 daily close** for both legs, then applies that ratio to a 09:30–11:00 entry/stop. That is a read past the entry bar, and it feeds position size via `stop_ticks`. Magnitude: ratio sigma/mean = 0.38%, and it only moves the contract count at a `floor()` boundary. Not material to any number above, but a prior-day ratio would be strictly clean.

## 4. THE REFUTATION — "rolling-252 pass rate 0.0%" is a degenerate single window

    window = min(252, n)                             # n = 234  ->  window = 234
    for start in range(0, max(1, n - window + 1)):   # -> range(0, 1)

With 234 mapped days and a 252-session window, **exactly one start exists**. The committed JSON confirms it: `rolling_252_windows: 1` on every firm row. The "rolling-252 pass rate" is therefore the very same walk-forward pass already in the row beside it, re-reported as a rate over a sample of one. It is not evidence that the eval fails from any start date — only that it fails from day 0.

Re-ran the honest version: **every one of the 234 start days**, 120-session cap, same `firm_kw`, same `evaluate_prop_challenge`, risk $1,000 (g171's own functions, `sizing.R_DOLLARS` unchanged):

| firm | starts | passed | true pass rate | best final equity |
|---|---:|---:|---:|---:|
| Topstep 50K Combine | 234 | 47 | **20.1%** | $5,122 |
| Topstep 100K Combine | 234 | 28 | **12.0%** | $7,381 |
| Topstep 150K Combine | 234 | 30 | **12.8%** | $11,203 |
| Apex 50K Eval EOD | 234 | 62 | **26.5%** | $5,122 |
| Apex 100K Eval EOD | 234 | 28 | 12.0% | $7,381 |
| Apex 150K Eval EOD | 234 | 30 | 12.8% | $11,203 |
| TPT Test 50K | 234 | 47 | 20.1% | $5,122 |
| TPT Test 100K | 234 | 28 | 12.0% | $7,381 |
| TPT Test 150K | 234 | 30 | 12.8% | $11,203 |
| MFFU Rapid 50K | 234 | 47 | 20.1% | $5,122 |
| MFFU Rapid 100K | 234 | 28 | 12.0% | $7,381 |
| Earn2Trade TCP 25K | 234 | 60 | **25.6%** | $4,090 |
| OneUp 100K | 234 | 36 | **15.4%** | $8,139 |

So: "**every** futures firm FAILS, rolling-252 pass rate **0.0%** for all" is false as written. The correct statement is: *an eval started on 2024-09-03 fails within 13–18 trading days; started on a randomly chosen day, 12–27% of Apex/Topstep/TPT/MFFU/E2T/OneUp evals clear the target.*

Two further corrections to the report's framing:

- **"13–18 days" are arm-trading days, not sessions.** The arm fires on 234 of 498 sessions, so the 13th arm-day is 2024-09-25 (**17 book sessions** in) and the 18th is 2024-10-03 (**23 sessions**).
- **Cost is understated** by the same factor: `months = ceil(days_used/21)` treats 13 arm-days as one month; in calendar time it is ~1.3 months, so Topstep/Apex would bill twice. Direction favours the arm, and it still fails from day 0.

## 5. What survives — the conclusion, not the number

Swept risk-per-trade from $50 to $3,000 (monkeypatching `sizing.R_DOLLARS`, everything else untouched) and re-ran the day-0 walk-forward for all 13 firms:

| risk/trade | mapped days | total | $/day | firms passing (day-0) |
|---:|---:|---:|---:|---|
| $50 | 150 | +$105 | +$0.70 | none |
| $150 | 227 | -$299 | -$1.32 | none |
| $250 | 234 | -$490 | -$2.10 | none |
| $1,000 | 234 | -$2,769 | -$11.83 | none |
| $3,000 | 234 | -$9,334 | -$39.89 | none |

The underlying stream's mean R is **-0.0135**; no sizing rescues a negative-mean stream in expectation, and lowering risk makes the profit target *harder* in R while only delaying the drawdown. **"No futures lane is fundable on tonight's book" is directionally right and survives the sizing sweep** — but it is established by the negative mean, not by the 0.0% figure the report cites, and a 12–27% one-shot pass rate at a $35–$150 eval fee is a materially different picture from "0.0%".

(Context on why the older rig disagrees: `research/g71_propfirm_sim_index_floor1.00.json` shows passing bands at $350–$550 risk — but its series `g71_propfirm_daily_index.json` has mean R **+0.71**, a pre-honest-fill / different-unit book. g171's honest stream is the right one; g71's futures bands are stale and should not be quoted against it.)

## 6. Overlap check — the stated statistic does not measure the proxy error

- **n = 2.** A sigma over two points (10.0355, 10.0379) is not a dispersion estimate. The report's own trust sentence ("basis is tight") is generated by `stdev < 0.01` on that n=2 sample.
- **It measures the wrong quantity.** The mapping uses the *daily-close* ratio; the check reports the internal spread of two *intraday* ES/SPY price ratios and never differences the two. Intraday mean 10.0367 vs the daily table's latest 10.0261 and mean 10.073 — the actual proxy error (~0.1–0.4%) is never computed.
- **Asymmetric levels.** `prior_day_levels` takes the full fetched session's high/low. For `ES=F` that is a ~23-hour session; for SPY it is RTH. The 1 ES-only / 2 SPY-only mismatches are partly an artifact of comparing overnight-inclusive PDH/PDL against RTH PDH/PDL, not an instrument difference.
- **`MES=F` is fetched and discarded** — `mes_series_fetched: true` is the only thing done with it, so the ticket's ES=F/MES=F leg is not actually checked.
- The 1-min fetch is a rolling "last 7 days" window: this section is not reproducible on any other date, and it re-ran identically only because I ran it the same day.

## 7. Verdict

**REFUTED.** Reproduction is exact and the money numbers, fill and unit are sound; the arm's *direction* holds. But the report's load-bearing statistic — a 0.0% rolling-252 pass rate on every firm — is a one-window artifact of `min(252, n)` with n=234, and the honest all-starts rate is 12.0–26.5%. The "fails every firm within 13–18 days" headline describes one start date, in arm-trading days, not sessions. The overlap check's sigma 0.0012 is an n=2 internal spread that does not measure the daily-vs-intraday basis error the mapping actually depends on.

Fix that makes the claim true: report the all-starts pass rate (loop `range(0, n)`, cap each start at `max_days`) and drop the "rolling-252" label, or state plainly that it is a single walk-forward pass.

Scripts: `research/g171_futures_proxy_arms.py` (unmodified, re-run); reproduction and sweeps run from the scratchpad, importing that module plus `research/omen_metrics.evaluate_prop_challenge` and `research/sizing.py` — nothing in the repo was modified by this pass.
