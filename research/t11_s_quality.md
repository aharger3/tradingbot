# T11 — giving S a quality bar it has to earn

Replayed over **183 marked equity-pool (symbol, day) pairs** from `research/austin_marks_v7.jsonl`. `s_precision` = share of the engine's S bars that Austin graded S within ±2 bars. Accepted signals only, 30-bar per-idea dedupe.

```
s_fires_per_day_before: 0.8
s_fires_per_day_after: 0.1
s_plus_per_day: 0.1
s_precision_before: 10.88
s_precision_after: 22.22
mesh_vetoed: 47
confluence_bars: 4
rule7_window_fitted: 8
rule7_s_retained: 91.9
level_retired_3rd_touch: 63
```

## Before / after

| arm | fires | S fires | S/day | S-precision | mesh vetoed | levels retired | confluence bars |
|-----|-------|---------|-------|-------------|-------------|----------------|-----------------|
| before | 164 | 147 | 0.8 | 10.88% | 36 | 0 | 4 |
| after | 162 | 18 | 0.1 | 22.22% | 47 | 63 | 4 |

## T11(a) — Rule 7's window, fitted to his S marks

Retest-bar distribution: for each S mark, the freshest retest across the levels the engine had live on that bar; for each non-S engine fire, the level it was keyed to. `s_retained` is the share of his S marks a window keeps, `non_s_kept` the share of non-S fires it also keeps — the number the window has to cut.

n(S marks) = 62, n(non-S fires) = 144

| window (bars) | s_retained | non_s_kept |
|---------------|------------|------------|
| 1 | 61.3% | 34.7% |
| 2 | 72.6% | 48.6% |
| 3 | 79.0% | 63.2% |
| 4 | 80.6% | 74.3% |
| 5 | 82.3% | 81.9% |
| 6 | 88.7% | 85.4% |
| 7 | 88.7% | 89.6% |
| 8 | 91.9% | 91.0% |
| 9 | 95.2% | 93.1% |
| 10 | 96.8% | 93.1% |
| 11 | 96.8% | 93.1% |
| 12 | 98.4% | 94.4% |
| 13 | 98.4% | 94.4% |
| 14 | 100.0% | 95.1% |
| 15 | 100.0% | 95.8% |
| 16 | 100.0% | 96.5% |
| 17 | 100.0% | 96.5% |
| 18 | 100.0% | 96.5% |
| 19 | 100.0% | 100.0% |
| 20 | 100.0% | 100.0% |

Smallest window retaining >=90% of his S marks: **8 bars** (91.9% retained), which cuts 9.0% of non-S fires.

`RULE_710_ENABLED` stays **OFF**. The window that keeps 90% of his S marks also keeps nearly every non-S fire, so arming it would filter almost nothing while adding a fitted threshold — exactly what this row exists to avoid. Rule 10's pivot-count arm is unaffected and stays as coded.

## T11(b) — the two fitted/unsettled levers, measured not armed

| arm | fires | S fires | S/day | S-precision |
|-----|-------|---------|-------|-------------|
| after | 162 | 18 | 0.1 | 22.22% |
| s_gate | 156 | 19 | 0.1 | 21.05% |
| htf_or | 162 | 18 | 0.1 | 22.22% |

## Which clause did the cutting (one at a time, off the `before` engine)

| clause | fires | S fires | S/day | S-precision |
|--------|-------|---------|-------|-------------|
| none (baseline) | 164 | 147 | 0.8 | 10.88% |
| displacement gate only | 163 | 55 | 0.3 | 9.09% |
| mesh S-veto only | 164 | 42 | 0.23 | 21.43% |
| level retirement only | 163 | 146 | 0.8 | 10.96% |
| all three | 162 | 18 | 0.1 | 22.22% |

`S_GATE` on moves S-precision by -1.17 points and `HTF_OPPOSITION_VETO=fill_override` by +0.00. Neither is decisive at this n, so both defaults stay where they were: `S_GATE = False`, `HTF_OPPOSITION_VETO = "hard"`.

## What this actually achieved

S fires went from 147 to 18 over 183 days (0.8/day -> 0.1/day) and S-precision from 10.88% to 22.22%. Austin's target is 1-3 S+ a day across the 15 symbols; the S+ rank caps at 3/day by construction and lands at 0.1.

**The overshoot is the headline.** This row was written for an engine emitting S in the hundreds; on the marked population it was already emitting 0.8/day, and the quality clauses take it to 0.1/day — 18 S in 183 days. That is an order of magnitude BELOW his 1-3/day, so the S+ cap never binds and the rate target is missed from the other side. Precision roughly tripled, which is the direction asked for, but on 18 signals that is 4 agreements — too few to call a rate.

The clause ablation above says which clause to loosen first if Austin wants the rate back. Nothing here is tuned to hit a number: every clause is his own sentence implemented literally, and the measurement is what it is.
