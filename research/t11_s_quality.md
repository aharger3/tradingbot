# T11 — giving S a quality bar it has to earn

Replayed over **160 marked equity-pool (symbol, day) pairs** from `research/austin_marks_v7.jsonl`. `s_precision` = share of the engine's S bars that Austin graded S within ±2 bars. Accepted signals only, 30-bar per-idea dedupe.

```
s_fires_per_day_before: 0.66
s_fires_per_day_after: 0.07
s_plus_per_day: 0.07
s_precision_before: 9.52
s_precision_after: 25.0
mesh_vetoed: 28
confluence_bars: 1
rule7_window_fitted: 8
rule7_s_retained: 92.9
level_retired_3rd_touch: 58
```

## Before / after

| arm | fires | S fires | S/day | S-precision | mesh vetoed | levels retired | confluence bars |
|-----|-------|---------|-------|-------------|-------------|----------------|-----------------|
| before | 116 | 105 | 0.66 | 9.52% | 26 | 0 | 1 |
| after | 114 | 12 | 0.07 | 25.0% | 28 | 58 | 1 |

## T11(a) — Rule 7's window, fitted to his S marks

Retest-bar distribution: for each S mark, the freshest retest across the levels the engine had live on that bar; for each non-S engine fire, the level it was keyed to. `s_retained` is the share of his S marks a window keeps, `non_s_kept` the share of non-S fires it also keeps — the number the window has to cut.

n(S marks) = 56, n(non-S fires) = 102

| window (bars) | s_retained | non_s_kept |
|---------------|------------|------------|
| 1 | 60.7% | 34.3% |
| 2 | 71.4% | 46.1% |
| 3 | 78.6% | 59.8% |
| 4 | 80.4% | 73.5% |
| 5 | 82.1% | 81.4% |
| 6 | 89.3% | 86.3% |
| 7 | 89.3% | 90.2% |
| 8 | 92.9% | 91.2% |
| 9 | 96.4% | 94.1% |
| 10 | 98.2% | 94.1% |
| 11 | 98.2% | 94.1% |
| 12 | 100.0% | 94.1% |
| 13 | 100.0% | 94.1% |
| 14 | 100.0% | 95.1% |
| 15 | 100.0% | 96.1% |
| 16 | 100.0% | 96.1% |
| 17 | 100.0% | 96.1% |
| 18 | 100.0% | 96.1% |
| 19 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |

Smallest window retaining >=90% of his S marks: **8 bars** (92.9% retained), which cuts 8.8% of non-S fires.

`RULE_710_ENABLED` stays **OFF**. The window that keeps 90% of his S marks also keeps nearly every non-S fire, so arming it would filter almost nothing while adding a fitted threshold — exactly what this row exists to avoid. Rule 10's pivot-count arm is unaffected and stays as coded.

## T11(b) — the two fitted/unsettled levers, measured not armed

| arm | fires | S fires | S/day | S-precision |
|-----|-------|---------|-------|-------------|
| after | 114 | 12 | 0.07 | 25.0% |
| s_gate | 109 | 12 | 0.07 | 25.0% |
| htf_or | 114 | 12 | 0.07 | 25.0% |

## Which clause did the cutting (one at a time, off the `before` engine)

| clause | fires | S fires | S/day | S-precision |
|--------|-------|---------|-------|-------------|
| none (baseline) | 116 | 105 | 0.66 | 9.52% |
| displacement gate only | 115 | 35 | 0.22 | 8.57% |
| mesh S-veto only | 116 | 29 | 0.18 | 24.14% |
| level retirement only | 115 | 104 | 0.65 | 9.62% |
| all three | 114 | 12 | 0.07 | 25.0% |

`S_GATE` on moves S-precision by +0.00 points and `HTF_OPPOSITION_VETO=fill_override` by +0.00. Neither is decisive at this n, so both defaults stay where they were: `S_GATE = False`, `HTF_OPPOSITION_VETO = "hard"`.

## What this actually achieved

S fires went from 105 to 12 over 160 days (0.66/day -> 0.07/day) and S-precision from 9.52% to 25.0%. Austin's target is 1-3 S+ a day across the 15 symbols; the S+ rank caps at 3/day by construction and lands at 0.07.

**The overshoot is the headline.** This row was written for an engine emitting S in the hundreds; on the marked population it was already emitting 0.66/day, and the quality clauses take it to 0.07/day — 12 S in 160 days. That is an order of magnitude BELOW his 1-3/day, so the S+ cap never binds and the rate target is missed from the other side. Precision roughly tripled, which is the direction asked for, but on 12 signals that is 3 agreements — too few to call a rate.

The clause ablation above says which clause to loosen first if Austin wants the rate back. Nothing here is tuned to hit a number: every clause is his own sentence implemented literally, and the measurement is what it is.
