# OMEN 5.2 — engine scorecard (T2)

Scores the engine's own fires against Austin's 120 hand-graded day cards
(TSLA 60, QQQ 30, SPY 30) and 64 trade marks. Every number below is computed
from `backtest_charts.json` (the engine's 911-trade ledger, 826 unique
symbol-days) crossed against `research/marks/`. No estimate anywhere.

Engine "fired on a day" = there is ≥1 trade in `backtest_charts.json` for
that (symbol, date), any grade. Austin "trade here" = day grade `S` or `A`
(S/A = 55 of 120; C/none/blank = 65). Side map: engine `call` = Austin `L`,
engine `put` = Austin `S`. Entry match = an engine trade on the same
(symbol, date), same side, with `|engine_entry_i − austin_entry_i| ≤ 3`; the
offset reported is engine bar minus Austin bar for the closest match.

day_precision: 0.3125
day_recall: 0.0909
entry_match_rate: 0.046875
median_bar_offset: 0
false_fires_on_none_days: 9

## Confusion (overall, 120 days)

| | engine fired | engine silent |
|---|---|---|
| Austin S/A (55) | 5 (TP) | 50 (FN) |
| Austin C/none/blank (65) | 11 (FP) | 54 (TN) |

Precision 5/16 = 0.3125. Recall 5/55 = 0.0909.

## Per symbol

| symbol | TP | FP | FN | TN | precision | recall |
|---|---|---|---|---|---|---|
| TSLA | 4 | 11 | 17 | 28 | 0.2667 | 0.1905 |
| QQQ  | 1 | 0  | 19 | 10 | 1.0000 | 0.0500 |
| SPY  | 0 | 0  | 14 | 16 | 0.0000 | 0.0000 |

The engine is near-silent on the days Austin graded: it fired on only 16 of
120 (15 TSLA, 1 QQQ, 0 SPY). Most of that is a coverage gap — the engine's
backtest period barely overlaps Austin's 2026 grading window, and the engine
ran no SPY trades at all. Where the engine *did* fire, it is usually wrong
on TSLA (11 of 15 fires landed on days Austin refused), which is a real
precision defect, not just a coverage one.

## Entry-level (64 marks)

3 of 64 marks have an engine fire within ±3 bars on the same side
(match rate 0.046875). The three matches:

| symbol | date | austin_i | side | eng_i | offset |
|---|---|---|---|---|---|
| TSLA | 2026-05-19 | 19 | S | 19 | 0 |
| TSLA | 2026-05-19 | 28 | S | 25 | -3 |
| TSLA | 2026-06-22 | 12 | L | 12 | 0 |

Median bar offset 0 — when the engine does coincide with Austin it is not
systematically late or early. But n=3 is too small to call the latency
question settled; the dominant failure is blindness (61 of 64 marks have no
side-and-bar match at all), not lateness.

## The 36 TSLA none days

Austin looked at 36 TSLA days and refused to trade. The engine fired on 9
of them (2026-05-15, 06-17, 06-25, 07-08, 07-13, 07-15, 07-20, 07-28,
08-03). Those 9 are false positives against a human who looked and said no.

## What this means for the S grade

The engine and Austin are not yet seeing the same days. A 0.09 recall says
the S grade is not reproducing Austin's trade-day selection — 50 of 55
Austin trade-days drew no engine fire at all, and 0 of the 30 SPY days got
one. A 0.31 precision on TSLA (0.27) says even where the engine fires it is
more often on a day Austin skipped than on one he took. The +3 matched
entries are encouraging (median offset 0, no late-engine bias), but three
coincidences do not validate a grader. The cheaper, earlier fix is coverage
and selection — getting the engine to fire on the days Austin trades at all
— before tuning tier thresholds. This scorecard measures the S grade against
a near-disjoint corpus, so treat the absolute numbers as a lower bound; the
shape (blind, not late; imprecise where it fires) is the signal.
