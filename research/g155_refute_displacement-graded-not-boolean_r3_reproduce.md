# g155 F6 refuter #3 (reproduce-from-script) — `displacement-graded-not-boolean`

**Verdict: REFUTED.** The script reproduces byte for byte and there is no lookahead — but the
"survivor" label is produced by a rule that a *random* filter of the same aggressiveness passes
**51.5% of the time** (92.0% once you allow the four thresholds this script sweeps), while the arm
itself loses **$70/day** against baseline and its precision gain contains **zero additional S days**.

Fill for every dollar figure below: signal-bar CLOSE entry, `stop_rule.stop_fill_price` stops,
size-gated on `signal_runner.min_risk_floor`, 1R = $1,000, one trade a day via
`research/omen_metrics.first_of_day_arm` logic, book `research/bt2y_trades_retest_on.json`,
498 sessions, split at 2025-09-01. Produced by
`research/g154_rule_displacement-graded-not-boolean.py` (re-run by me) and the two refuter
scripts named at the bottom.

## 1. Reproduction — passes

Backed up the committed `.json`/`.md`, re-ran `python research/g154_rule_displacement-graded-not-boolean.py`
(81 s), diffed. **Both outputs identical, zero bytes changed.** Every headline number in the claim
is confirmed:

| quantity | claim | my re-run |
|---|---:|---:|
| baseline $/day | 33.93 | 33.93 |
| T=2.0 $/day | -36.03 | -36.03 |
| H1 delta | -91.47 | -91.47 |
| H2 delta | -47.78 | -47.78 |
| precision | 30.5 → 38.3 | 30.5 → 38.3 |
| recall_100 | 5.9 → 14.7 | 5.9 → 14.7 |

## 2. Lookahead — clean

`disp_ratio` reads `bars[break_bar]` where `break_bar <= entry_i`, and a 10-bar window strictly
*before* it. Nothing past the signal bar is touched. The P&L is the book's own honest close fill,
not re-derived. **No leakage. This is not the refutation.**

## 3. The survivor test is vacuous on money

```python
h1_ok = (primary["H1"]["usd_day"] > baseline["H1"]["usd_day"]) or prec_improves
h2_ok = (primary["H2"]["usd_day"] > baseline["H2"]["usd_day"]) or prec_improves
```

`prec_improves` is True, so both money clauses short-circuit. The verdict is decided by **one
comparison of one precision percentage**. What that clause is excusing:

| | baseline | T=2.0 | delta |
|---|---:|---:|---:|
| $/day (all) | $33.93 | **-$36.03** | **-$69.96** |
| H1 $/day | $135.71 | $44.24 | -$91.47 |
| H2 $/day | -$67.85 | -$115.63 | -$47.78 |
| green months | 13/25 | **9/25** | -4 |
| max DD | -$21,405 | **-$38,421** | -$17,016 |
| total over 498 sessions | +$16,897 | **-$17,933** | **-$34,830** |

Money across the sweep is the one clean dose-response in the whole table, and it points down:
$33.93 (no gate) → $9.34 (T=1.0) → $7.41 (T=1.5, shipped) → -$36.03 (T=2.0) → -$100.46 (T=2.5).
**No threshold beats no-gate.** By the script's own stated question — "does a DIFFERENT threshold
beat the shipped one" — the answer on money is that neither does, and the shipped boolean is
already costing $26/day against not filtering at all.

## 4. The precision gain has an identical numerator

Baseline 18/59 → T=2.0 18/47. **Same 18.** Decomposed (`g155_refute3_reproduce.py`):

- S days gained by the arm: **14** — `AAPL_2025-08-08, AMD_2024-10-02, AMZN_2026-05-12, META_2026-03-04, MSFT_2025-03-13, MU_2025-06-25, PLTR_2025-07-01, PLTR_2025-09-15, PLTR_2025-12-11, QQQ_2025-03-17, TSLA_2025-09-05, TSLA_2026-04-22, TSM_2026-07-07, UBER_2025-08-13`
- S days lost by the arm: **14** — `AAPL_2026-08-03, AMD_2026-05-13, AMZN_2026-01-14, AVGO_2024-11-04, AVGO_2025-08-14, BABA_2025-02-05, BABA_2025-04-01, COIN_2025-12-18, GOOGL_2024-11-20, GOOGL_2025-09-05, ORCL_2026-01-16, PLTR_2025-12-15, SOFI_2026-01-09, TSLA_2024-09-20`
- non-S graded removed 31, non-S graded added 19 → net -12 in the denominator.

78% of the "kept" S days are different symbol-days from the baseline's. The rule does not retain
S setups and discard non-S ones; it **reshuffles the book and swaps S days one-for-one**, and the
percentage moves only because 12 net graded rows left the denominator. **73.5% of all 498 days
change their pick** — this is a wholesale reshuffle, not a filter, measured on 47 graded days.

## 5. A random filter passes this test half the time

Null: drop each candidate independently with the arm's own drop rate (67.12%), rerun the same
first-of-day walk, score with the same functions. 400 replicates (`g155_refute3_null.py`):

| | null median | null p95 | observed T=2.0 | percentile |
|---|---:|---:|---:|---:|
| precision % | 34.5 | 44.9 | 38.3 | **74.5%** |
| recall_100 % | 5.9 | 11.8 | 14.7 | 98.8% |
| $/day | -$11.6 | +$51.1 (p95) | -$36.03 | 29.5% |

- **P(a random 67% filter is declared a "survivor") = 51.5%.** (P(precision > 30.5) = 76.8%,
  P(recall_100 ≥ 5.9) = 62.5% — the `≥` lets ties pass.)
- **P(at least one of the four swept thresholds survives) = 92.0%.** The script's `DEFAULT_T = 2.0`
  is documented as "chosen after the sweep", and it is precisely the threshold that maximizes both
  criteria. That is a 1-of-4 pick on the same data the test is scored on, before any correction
  for the **25** rule candidates in the F5 family (100 arms in total; expected false survivors
  under this null ≈ 23 of 25 rules).
- The arm's money sits at the **29.5th percentile** of random filters — a coin-flip filter of the
  same aggressiveness does better than this rule half the time.
- Precision across thresholds is non-monotone (30.5 → 36.1 → 34.0 → **38.3** → 31.2) and so is
  recall_100 (5.9 → 8.8 → 8.8 → **14.7** → 8.8): T=2.0 is a spike between two identical 8.8s. A
  genuinely graded read of displacement strength would show a trend. There is none.

## 6. Money delta is also not significant

Paired daily deltas, T=2.0 minus baseline, n=498: mean **-$68.80/day**, se $52.59, t = -1.31,
bootstrap 95% CI **[-$174.16, +$34.61]**. The baseline's own $/day CI is [-$60.77, +$134.33] —
it does not clear zero either. Nothing in this comparison is measurable at this sample size; the
one thing the data can say is that the point estimate is negative in both halves.

## Verdict

REFUTED. Reproduces exactly, no lookahead, honest fill — and none of that is in dispute. The claim
fails because the survivor criterion it passes is a 51.5% null event that a random filter clears,
the winning threshold was chosen post hoc from four on the scored data (92.0% family-wise null),
the precision gain adds zero S days and comes entirely from a shrinking denominator with a 78%
churned numerator, and the arm gives up $34,830 and 4 green months over the book to buy it.

Scripts: `research/g155_refute3_reproduce.py`, `research/g155_refute3_null.py`.
