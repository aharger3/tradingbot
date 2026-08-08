# rule7_rule10 — Rule 7 & Rule 10 separation

Austin's two hardest rejections, encoded as features and tested for tier separation. Reuses `research/mark_features.py`'s loading + leakage discipline and `research/levels.py`'s level node set.

## Counts

- Usable marks: **159**
- Dropped: **0** (no archived bars / entry_i out of range). NB: the data archive has been filled in since 3.6 ran (3.6 dropped 54/159 for missing bars; all 159 now have RTH bars), so the arms here are larger than 3.6's n=48/45/12 — but the feature nulls below shrink the effective arms back down.
- Total marks: 159
- Tier arms (usable): S=77 A=60 X=22

## Leakage rule — how it was enforced

No feature reads any bar at index > entry_i. Enforcement is structural, by construction, not by after-the-fact assertion:

1. **Truncation (path 1):** for each mark the day's RTH bars are loaded once via `levels.load_rth_bars` and **truncated to `bars[:entry_i+1]`** (`bars_trunc`, length entry_i+1). Every feature here is handed `bars_trunc`:
- `mark_features.find_break` (the break candle) scans `bars[:entry_i]` — strictly before the entry bar.
- `find_retest` scans indices in `(break_i, entry_i]` — the entry bar is the highest index it can read, never beyond.
- `count_left_pivots` scans the whole `bars_trunc` for 3-bar centres, then keeps only centres with index `<= break_i-1 < entry_i`; every neighbour it touches is within `bars_trunc` (max index entry_i).

2. **`research/levels.py` (path 2):** `levels_at_bar` takes symbol/day/entry_i and reloads the file internally, then slices itself at entry_i (`hod_lod_nodes` uses `bars[:entry_i]`, `swing_pivots` uses `bars[:entry_i+1]` whose last centre is entry_i-1, prior-day/month nodes read earlier calendar days only). It never receives the untruncated list from this script.

The reference level itself is the nearest weight>=2 node to the entry close (the same selection `mark_features.compute_features` uses in 3.6); `direction` is `call` if entry close > that level else `put`. The break candle uses `find_break`'s transition test (a bar whose close crossed the reference level from the opposite side) — that is the bar whose *body closed beyond the reference level*; the wording of the row describes this break candle, and the transition framing is what distinguishes the break candle from the subsequent bars that also sit beyond the level.

## Rule 7 — speed of the retest

`bars_break_to_retest` = bars from the break candle to the first retest candle (the first bar after the break whose wick returns to the level, at or before the entry bar). Smaller = faster retest = what Austin wants.

**Null rate (no break identifiable): 56/159 = 35.2%** of marks with bars have no break candle and emit null. A high null rate is itself the finding: the retest-speed feature is undefined at its first step for 56 of 159 marks — the engine's retested level was never provably *broken* by a closing body in the bars leading to entry, so 'speed of retest' has no start point.

A further **20** marks have a break candle but no retest candle (no bar at or before entry whose wick returns to the level) — these are also null for `bars_break_to_retest` (the elapsed-bars value needs both endpoints). The total rule-7 null count is 76/159 = 47.8%; the headline rate above isolates the no-break case the row names.

Per-tier non-null counts (rule 7):

| tier | non-null | total | null rate |
|---|---|---|---|
| S | 34 | 77 | 43/77 |
| A | 38 | 60 | 22/60 |
| X | 11 | 22 | 11/22 |

Rule 10 (`left_pivot_count`) is null only on the no-break case (it is undefined whenever there is no break candle, since it counts pivots *before the level was broken*); the break-but-no-retest marks still carry a `left_pivot_count`. Its null rate is 56/159 = 35.2%, equal to the no-break rate.

## Separation tables

For each feature and each contrast (S-vs-X, S-vs-A): Cohen's d (S minus the other tier; positive = S larger), a 95% CI from a block bootstrap over whole trading days with 10,000 resamples, and the minimum detectable effect at the n actually available (alpha=0.05 two-sided, power=0.80). MDE_d is the Cohen's-d threshold; an observed |d| below it is underpowered, not a null.

### `bars_break_to_retest`

| contrast | n(S) | n(other) | pooled days | mean(S) | mean(other) | Cohen's d | 95% bootstrap CI | MDE (native) | MDE_d | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| S-vs-X | 34 | 11 | 45 | 1.91 | 2.45 | -0.343 | [-1.325, 0.564] | 1.536 | 0.972 | underpowered |
| S-vs-A | 34 | 38 | 70 | 1.91 | 2.08 | -0.109 | [-0.562, 0.385] | 1.011 | 0.661 | underpowered |

### `left_pivot_count`

| contrast | n(S) | n(other) | pooled days | mean(S) | mean(other) | Cohen's d | 95% bootstrap CI | MDE (native) | MDE_d | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| S-vs-X | 46 | 14 | 60 | 5.15 | 4.79 | 0.121 | [-0.468, 0.676] | 2.591 | 0.855 | underpowered |
| S-vs-A | 46 | 43 | 87 | 5.15 | 5.56 | -0.121 | [-0.563, 0.299] | 1.989 | 0.594 | underpowered |

### `left_pivot_at_level`

| contrast | n(S) | n(other) | pooled days | mean(S) | mean(other) | Cohen's d | 95% bootstrap CI | MDE (native) | MDE_d | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| S-vs-X | 46 | 14 | 60 | 1.57 | 1.93 | -0.204 | [-0.901, 0.367] | 1.524 | 0.855 | underpowered |
| S-vs-A | 46 | 43 | 87 | 1.57 | 2.33 | -0.329 | [-0.724, 0.094] | 1.374 | 0.594 | underpowered |

## Reading the result

3.6's arms were n=48/45/12 and detected nothing at 45pp. These features shed more marks to nulls (no break identifiable), so the separation arms are smaller still — especially S-vs-X, where the X arm shrinks to single digits. Where the verdict is **underpowered**, the observed d is below the Cohen's-d threshold the experiment could have reliably detected at this n; the honest report is the MDE, not a claim of no effect. A **detected** verdict means the bootstrap CI excludes zero.

## Statistics note

No numpy/scipy in this environment. Cohen's d uses the pooled-SD formula; the 95% CI is a block bootstrap over whole trading days (resampling days with replacement, 10,000 iterations, seed 20260808) so that same-day marks are not treated as independent. MDE = (z_0.975 + z_0.80) * s_pooled * sqrt(1/n1 + 1/n2) in native units, and the same expression without s_pooled gives the Cohen's-d threshold MDE_d.
