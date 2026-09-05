# g157 -- the ML ceiling (F8)

**One sentence: on the judged symbol-days with a book candidate, a gradient-boosted model's out-of-fold precision at the rule engine's own recall is reported below; it is measured only, never wired into detection.**


- judged symbol-days: 120, days with archived bars: 120, days with >=1 book candidate: 120
- label: `y=1` iff Austin graded that day S; A/C/none all count as 0
- feature row = day's FIRST book candidate only (arrival order, bar index = time of first candidate)

- S-day rows: 28 / 120 (23.3%)

- months (CV groups): 4


**Rule engine's own recall on this row set: 17.9%** (fraction of S-day first-candidates the legacy grader did not skip/X).


## Logistic regression (5-fold GroupKFold CV by month)

- ROC AUC (out-of-fold): 0.492

- precision at engine's recall (17.9%): **32.0%**

- precision/recall curve samples:


| recall >= | best precision |
|---:|---:|

| 0.25 | 32.0% |

| 0.50 | 25.9% |

| 0.75 | 23.3% |

| 1.00 | 23.3% |


## Gradient boosting (5-fold GroupKFold CV by month)

- ROC AUC (out-of-fold): 0.426

- precision at engine's recall (17.9%): **24.7%**

- precision/recall curve samples:


| recall >= | best precision |
|---:|---:|

| 0.25 | 24.7% |

| 0.50 | 24.7% |

| 0.75 | 23.9% |

| 1.00 | 23.9% |


## Baseline for comparison

- S-day rate in this row set (predict-all-positive precision): 23.3%


## What this is not

- Not wired into detection anywhere. `signal_runner.py` is unchanged.

- Label is a DAY-level grade attached to that day's first candidate row, not a per-signal ground truth -- Austin did not grade each candidate individually.

- Small-N: 120 rows across 4 months. A held-out AUC/precision computed from this many rows carries a wide error bar; treat this as a ceiling sketch, not a shippable number.
