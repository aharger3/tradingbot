# rule7_rule10

Austin's two hardest rejections, encoded as features and tested for S/A/X tier separation. Built on top of `research/mark_features.py` (its loading, leakage discipline, and reference-level identification).

## Leakage rule (no bar at index > entry_i)

Enforced structurally, identically to `mark_features.py`: each mark's full RTH bar list is loaded once (`levels.load_rth_bars`) and **truncated to `bars[:entry_i+1]`** (`bars_trunc`, length entry_i+1) before any feature reads it. `find_break` scans `bars_trunc[:entry_i]`; the rule-7 retest scan and the rule-10 pivot scan both run over `bars_trunc` (max index entry_i); the reference level and direction come from `levels.levels_at_bar` called over `bars_trunc` (the same leakage-bounded call mark_features uses). No path -- direct or via `levels.py` -- indexes a bar beyond entry_i. Marks with no archive file or out-of-range entry_i are dropped (no bars -> no features).

## Counts

- Total marks: 159
- Usable (bars present, entry_i in range): **159**
- Dropped: 0
- Tier counts (usable): A=60, S=77, X=22

3.6's arms were n=48/45/12 (105 usable). The archive has since been expanded, so all 159 marks now have bars and the TOTAL tier arms are S=77/A=60/X=22. The separation tables below use the EFFECTIVE arms -- the non-null counts per feature (rule 7 loses the no-break + no-retest marks, rule 10 loses only the no-break marks) -- which is the n the MDE is computed at.

## Rule 7 -- null rate (no break identifiable)

- `bars_break_to_retest` null: **67/159** (42.1%)
  - no break identifiable (find_break found no close-through of the reference level): 56
  - break found but no retest bar reached the level before/at entry: 11
  - no reference level/direction: 0
- `left_pivot_count` null (no break -> no 'before the break' window): **56/159** (35.2%)

A high null rate is itself the finding: it means the engine's retested level (the nearest weight>=2 node to the entry close) often is NOT a freshly broken level -- price never closed through it from the other side in the bars leading to entry, so rule 7 and rule 10 are undefined for those marks. The break detector reused here is `mark_features.find_break` (close-through-from-other-side, eps = 0.10 * median bar range), the same one behind 3.6's `bars_since_break` (37/105 null there).

## Rule 7 -- bars break->retest (speed of the retest)

Cohen's d (pooled SD), 95% CI from a block bootstrap over whole trading days (10,000 resamples; resample (symbol,day) blocks with replacement, split the gathered marks by tier, recompute d; resamples where an arm has n<2 or zero variance are discarded), and the MDE at the n actually available (normal-approx planning formula: MDE = (z_.975 + z_.80) * sqrt(1/n1 + 1/n2); scipy is not installed).

| contrast | n_a | n_b | mean_a | mean_b | d | 95% CI | n_boot | MDE | verdict |
|---|---|---|---|---|---|---|---|---|---|
| S vs X | 41 | 11 | 1.610 | 2.000 | -0.305 | [-1.254, 0.648] | 10000 | 0.951 | UNDERPOWERED: |d|=0.31 < MDE 0.95; a real effect up to 0.95 is consistent with the data -- not a null |
| S vs A | 41 | 40 | 1.610 | 1.925 | -0.253 | [-0.689, 0.186] | 10000 | 0.623 | UNDERPOWERED: |d|=0.25 < MDE 0.62; a real effect up to 0.62 is consistent with the data -- not a null |

- **S vs X**: UNDERPOWERED: |d|=0.31 < MDE 0.95; a real effect up to 0.95 is consistent with the data -- not a null. n=41/11, d=-0.305. CI=[-1.254, 0.648], MDE=0.951.
- **S vs A**: UNDERPOWERED: |d|=0.25 < MDE 0.62; a real effect up to 0.62 is consistent with the data -- not a null. n=41/40, d=-0.253. CI=[-0.689, 0.186], MDE=0.623.

Direction: S mean=1.61 bars vs X=2.00, A=1.93. S has the FASTEST retests (fewest bars break->retest), which is the direction Austin's rule predicts for the top tier -- but the gap is small and below the MDE on both contrasts.

## Rule 10 -- left-side pivot count (20 bars before break)

Cohen's d (pooled SD), 95% CI from a block bootstrap over whole trading days (10,000 resamples; resample (symbol,day) blocks with replacement, split the gathered marks by tier, recompute d; resamples where an arm has n<2 or zero variance are discarded), and the MDE at the n actually available (normal-approx planning formula: MDE = (z_.975 + z_.80) * sqrt(1/n1 + 1/n2); scipy is not installed).

| contrast | n_a | n_b | mean_a | mean_b | d | 95% CI | n_boot | MDE | verdict |
|---|---|---|---|---|---|---|---|---|---|
| S vs X | 46 | 14 | 5.152 | 4.786 | 0.121 | [-0.459, 0.677] | 10000 | 0.855 | UNDERPOWERED: |d|=0.12 < MDE 0.86; a real effect up to 0.86 is consistent with the data -- not a null |
| S vs A | 46 | 43 | 5.152 | 5.558 | -0.121 | [-0.557, 0.297] | 10000 | 0.594 | UNDERPOWERED: |d|=0.12 < MDE 0.59; a real effect up to 0.59 is consistent with the data -- not a null |

- **S vs X**: UNDERPOWERED: |d|=0.12 < MDE 0.86; a real effect up to 0.86 is consistent with the data -- not a null. n=46/14, d=0.121. CI=[-0.459, 0.677], MDE=0.855.
- **S vs A**: UNDERPOWERED: |d|=0.12 < MDE 0.59; a real effect up to 0.59 is consistent with the data -- not a null. n=46/43, d=-0.121. CI=[-0.557, 0.297], MDE=0.594.

Direction: S mean=5.15 pivots vs X=4.79, A=5.56. S is cleaner than A (fewer left-side pivots, as the rule predicts) but noisier than X; the raw count does not monotonically order the tiers and both effects are far under the MDE.

## Rule 10 -- pivots within 0.2% of the level (noise at the level)

Cohen's d (pooled SD), 95% CI from a block bootstrap over whole trading days (10,000 resamples; resample (symbol,day) blocks with replacement, split the gathered marks by tier, recompute d; resamples where an arm has n<2 or zero variance are discarded), and the MDE at the n actually available (normal-approx planning formula: MDE = (z_.975 + z_.80) * sqrt(1/n1 + 1/n2); scipy is not installed).

| contrast | n_a | n_b | mean_a | mean_b | d | 95% CI | n_boot | MDE | verdict |
|---|---|---|---|---|---|---|---|---|---|
| S vs X | 46 | 14 | 1.565 | 1.929 | -0.204 | [-0.887, 0.369] | 10000 | 0.855 | UNDERPOWERED: |d|=0.20 < MDE 0.86; a real effect up to 0.86 is consistent with the data -- not a null |
| S vs A | 46 | 43 | 1.565 | 2.326 | -0.329 | [-0.727, 0.095] | 10000 | 0.594 | UNDERPOWERED: |d|=0.33 < MDE 0.59; a real effect up to 0.59 is consistent with the data -- not a null |

- **S vs X**: UNDERPOWERED: |d|=0.20 < MDE 0.86; a real effect up to 0.86 is consistent with the data -- not a null. n=46/14, d=-0.204. CI=[-0.887, 0.369], MDE=0.855.
- **S vs A**: UNDERPOWERED: |d|=0.33 < MDE 0.59; a real effect up to 0.59 is consistent with the data -- not a null. n=46/43, d=-0.329. CI=[-0.727, 0.095], MDE=0.594.

Direction: S mean=1.57 near-level pivots vs X=1.93, A=2.33. S has the FEWEST near-level pivots (least noise at the level) on both contrasts -- the right direction for the top tier -- and the S-vs-A d=-0.33 is the largest effect in this study, but its CI still includes 0 (MDE=0.59).

## Feature dictionary (rule7_rule10.jsonl)

One line per usable mark (mark with bars). Identity triple + tier +:

| key | meaning |
|---|---|
| `bars_break_to_retest` | Rule 7: bars between the break candle (last close-through of the reference level before entry) and the retest candle (first wick back to the level). null if no break / no retest. |
| `left_pivot_count` | Rule 10: count of 3-bar swing pivots (MarketStructure.update definition) in the 20 bars before the break. null if no break. |
| `left_pivots_near_level` | Rule 10: of those pivots, how many sit within 0.2% of the reference level (noise at the level). null if no break. |
| `break_index` / `retest_index` | bar indices of the break / retest candles (for audit). |
| `broken_level_price` / `direction` | the retested level and direction, recomputed the same way mark_features does (nearest weight>=2 node to entry close via levels.levels_at_bar). |
| `null_reason_r7` | why bars_break_to_retest is null: no_break / no_retest / no_ref, else null. |
