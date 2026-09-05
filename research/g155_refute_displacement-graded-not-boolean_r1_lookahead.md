# g155 F6 refuter #1 (leakage / lookahead lens) — `displacement-graded-not-boolean`

**Verdict: REFUTED.** The numbers reproduce byte-for-byte and the predicate is genuinely
causal — there is no lookahead in the bar arithmetic. It is refuted because the survivor
verdict rests entirely on a precision move that an information-free random filter beats
26% of the time, while the arm costs money in both halves, and because the headline
threshold was chosen by reading the same 34-card scoring set it is then scored against.

Claim under test: baseline $33.93/day → −$36.03/day, H1 delta −91.47, H2 delta −47.78,
precision 30.5 → 38.3, recall_100 5.9 → 14.7.
Script: `research/g154_rule_displacement-graded-not-boolean.py`.
Fill throughout: signal-bar CLOSE entry (`bt2y_trades_retest_on.json`, `meta.entry_fill =
"close"`, `PESSIMISTIC_FILL`, `DISASTER_STOP_R = 1.0`), stops via `stop_rule.stop_fill_price`,
size-gated on `signal_runner.min_risk_floor` through `omen_metrics._row_is_sizeable`,
1R = $1,000. One-trade-a-day unit = `research/omen_metrics.first_of_day_arm`. 498 sessions,
H1/H2 split 2025-09-01.

---

## 1. Reproduction — exact

Re-ran the script unmodified. Its emitted JSON is **identical** to the committed
`research/g154_rule_displacement-graded-not-boolean.json`, field for field. Every figure in
the claim is confirmed as printed. Nothing here disputes the arithmetic.

## 2. Lookahead lens — CLEAN, the predicate reads nothing past the signal bar

This was my assigned angle and the claim survives it.

| check | result |
|---|---|
| `entry_i` is an index into `pf.rth(pf.fetch_day(sym, day))` | confirmed — `backtest_2y.py:173` writes it as exactly that |
| `bars[entry_i].close` equals the book's `entry` (400-row random sample) | **399 / 400 ok**, 0 unreadable; the 1 flagged row is a sub-cent float edge (book 51.84 vs bar 51.84) |
| `max(break_bar_idx − entry_i)` over 400 resolved rows | **0** — the break bar is the signal bar or earlier, never later |
| the 10-bar body window | sits strictly *before* the break bar, so further back still |

`disp_ratio` is computable in real time at the moment of the fill. **No lookahead.**

## 3. The survivor test is vacuous — money never had to pass

```
h1_ok = (primary H1 usd > baseline H1 usd) or prec_improves
h2_ok = (primary H2 usd > baseline H2 usd) or prec_improves
```

Both money comparisons are **False** (H1 −91.47/day, H2 −47.78/day). `prec_improves` is a
single **global** boolean — precision is never computed per half — so one 7.8-point move
satisfies both halves at once and the H1/H2 structure does no work. `usd_improves` is
computed on line 333 and **never read**: a dead variable. The rule as executed is
"precision up AND recall_100 not down", nothing more.

## 4. The precision gain is a p = 0.26 null event

Null control, N = 300 each, same pick-then-gate walk, same 67.17% row-level drop rate
(5,526 of 8,227 candidate rows) — `scratchpad/r1_null.py`:

| filter | precision mean | p5..p95 | share of nulls ≥ 38.3% |
|---|---:|---|---:|
| **NULL A** — uniform random drop, same rate | 34.7% | [25.0, 44.4] | **26.0%** |
| **NULL B** — `disp_ratio` labels permuted across rows | 34.2% | [25.5, 43.1] | **21.7%** |
| the real T=2.0 arm | 38.3% | — | — |

Random dropping *by itself* lifts precision 30.5% → 34.7%, because it shrinks the
denominator. Fisher exact on 18/47 vs 18/59 (generous — the samples are nested, not
independent): **p = 0.42**.

## 5. The S numerator never moved, and the S set is 100% churned

| arm | graded_S | graded_any | precision |
|---|---:|---:|---:|
| baseline | 18 | 59 | 30.5% |
| T=2.0 | **18** | 47 | 38.3% |

Same count — but **zero overlap**. 14 of baseline's S days are dropped and 14 *different*
S days appear; **366 of 498 day-picks change**. `s_recall_all_bar_backed` is also flat at
18/347 → 18/347. A filter that reshuffles 73% of the book and lands on exactly 18 S days
again has demonstrated no ability to find S days. The precision move is the denominator
falling 59 → 47, nothing else.

## 6. recall_100 5.9 → 14.7 is 2 → 5 hits, and the threshold was chosen on that set

`DEFAULT_T = 2.0  # headline arm; chosen after the sweep, see main()` — the script says so.
T=2.0 is the argmax of *both* precision (38.3 vs 36.1 / 34.0 / 31.2) and recall_100 (5 vs
3 / 3 / 3) across the four thresholds. There is no holdout: the 34 sweep cards and the
59-day precision pool are simultaneously the selection set and the scoring set. **That is
the leakage in this claim — in the arm selection, not the bar arithmetic.**

5 hits sits at the 1.3rd percentile of NULL B, but max-of-4-thresholds inflates that to
~5%, and this batch ran **25 rule families** (`research/g154_rule_*.json`, 7 declared
survivors). At 25 families × 4 arms a 5% event is expected roughly 5 times by chance. Bare
counts: 2/34 → 5/34, one of which (BABA_2025-02-05) was *lost*, four gained.

## 7. The rule's own question answers NO

The script's stated test: grading beats the boolean iff some T ≠ 1.5 does better.

| arm | $/day (all) | green months | max DD |
|---|---:|---:|---:|
| **baseline, no filter** | **$33.93** | **13/25** | **−$21,405** |
| T=1.0 | $9.34 | 13/25 | −$20,985 |
| T=1.5 (shipped `DISP_BODY_MULT`) | $7.41 | 12/25 | −$34,369 |
| T=2.0 (headline) | −$36.03 | 9/25 | −$38,421 |
| T=2.5 | −$100.46 | 8/25 | −$50,357 |

Money falls monotonically as T rises, and **every threshold loses to no filter at all**.
The best-money threshold is T=1.0, not the headline. Green months 13 → 9; max drawdown
nearly doubles.

## 8. Money delta, paired by day

| split | n | mean delta $/day | 95% CI |
|---|---:|---:|---|
| all | 498 | −$68.80 | [−171.89, +34.28] |
| H1 | 249 | −$93.07 | [−245.07, +58.93] |
| H2 | 249 | −$44.54 | [−184.06, +94.99] |

The loss is not distinguishable from zero either — the book's error bar swallows it, as
`omen-error-bar-exceeds-arms` predicts. But the arm's central estimate is **−$34,800 over
the 498-session book**, and the survivor rule waived the money test rather than passing it.

---

## What would change my mind

A pre-registered threshold (T fixed to the shipped 1.5, or picked on H1 alone) scored on
H2 and on marks held out of the selection, showing precision above the NULL A p95 of 44.4%
with graded_S actually rising above 18. None of that is in the artifact.

Reproduced with `research/g154_rule_displacement-graded-not-boolean.py` (unmodified),
plus `scratchpad/r1_align.py` (entry_i alignment, break-bar offset) and
`scratchpad/r1_null.py` (NULL A / NULL B, N=300 each).
