# T7 -- eye-match agreement (engine tier vs Austin's grade)

Scorer: `research/t51_eye_match.py` on `austin_marks_v7.jsonl`.
For each mark, the shipped engine is replayed over that (symbol, day); the nearest routed signal within +-2 bars of the marked entry supplies the engine's tier. No fire within tolerance is its own column (`no-fire`), never dropped -- a silent engine on an S bar is the failure this project exists to fix.

- marks scored: **475** (skipped 4 non-S/A/C/X grades; 21 marked (symbol, day) pairs absent from the archive -> silent)
- unique (symbol, day) days replayed: **362**

## Confusion matrix

Rows = Austin's grade; columns = engine's tier. `no-fire` = the engine produced no routed signal within +-2 bars of the marked entry.

| Austin \ Engine | S | A | C | X | no-fire | row total |
|---|---|---|---|---|---|---|
| **S** | 3 | 0 | 24 | 0 | 112 | 139 |
| **A** | 4 | 0 | 21 | 0 | 147 | 172 |
| **C** | 0 | 0 | 8 | 0 | 8 | 16 |
| **X** | 2 | 0 | 48 | 0 | 98 | 148 |
| **col total** | 9 | 0 | 101 | 0 | 365 | **475** |

## Agreement

- **exact agreement (overall): 2.32%**  (11/475)
- exact per Austin-grade:  S=2.16%,  A=0.0%,  C=50.0%,  X=0.0%
- **adjacent agreement (off by one tier): 15.37%**  (73/475)
- **Cohen's kappa: 0.0106**  (agreement vs chance; <0 less than chance, 0 chance, >0.41 moderate, >0.61 substantial)

## Directional error rates

- **over-grading: 0.42%**  (2/475) -- engine says S, Austin says C or X
- **under-grading: 28.63%**  (136/475) -- Austin says S, engine says C, X, or did not fire

- **S recall: 3/139** -- of Austin's S bars, the share the engine also called S within +-2 bars

---

marks_scored: 475
exact_agreement: 2.32
kappa: 0.0106
over_grade_rate: 0.42
under_grade_rate: 28.63
s_recall: 3/139
