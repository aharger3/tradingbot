# mark_features

Feature vector at every *usable* marked bar (`research/austin_marks_v2.jsonl`).

## Counts

- Usable marks: **105**
- Dropped marks: **54** (no archived bars, per `research/bar_coverage.md`)
  - no_archive_file: 54
- Total marks: 159

## No-future-bars (leakage) rule — how it was enforced

Every feature reads only bars at index <= entry_i. Enforcement is structural, not aspirational. There are two paths and both are bounded:

1. **Direct computation** (body/range, displacement, new-session-H/L, `find_break`, and every `predicates.*` window): for each mark the day's full RTH bar list is loaded once and **truncated to `bars[:entry_i+1]`** (the `bars_trunc` variable, length entry_i+1). These computations are handed `bars_trunc` (or `candles` built from it), so by construction they cannot index a bar beyond entry_i — `predicates`' `window = candles[-(lookback+1):]` is a suffix of that truncated list (max index entry_i), `find_break` scans `bars[:entry_i]`, displacement/new-session use `bars[:entry_i]` and `bars[entry_i-20:entry_i]`.

2. **`research/levels.py` calls** (`levels_at_bar`, `atr_1m`): these routines take symbol/day/entry_i and reload the file internally, then slice themselves — they never receive the untruncated list from this script, and their internal slices are bounded at entry_i:
- `levels.hod_lod_nodes` uses `bars[:entry_i]` (strictly before entry).
- `levels.swing_pivots` uses `bars[:entry_i+1]`; its last possible fractal center is index entry_i-1 (it needs the entry bar only as the right neighbour), so it never reads past entry_i.
- `levels.atr_1m` slices `bars[:entry_i+1]`.
- `levels.prior_day_nodes` / `levels.prior_month_nodes` read **prior calendar days** only (earlier data, never the same day's future).
- `levels.psych_nodes` is price-derived (no bars).

No feature path — direct or via levels.py — ever reads a bar at index > entry_i. The bound is by construction (truncation for path 1, the documented internal slices for path 2), not by after-the-fact assertion.

## Feature dictionary

Each row of `mark_features.jsonl` carries the identity triple (symbol/day/entry_i) plus tier, then these features:

| key | meaning |
|---|---|
| `dist_R_above` | (nearest level node above entry close - entry close) / R; R = 14-bar 1m ATR. None if no node above or no ATR. |
| `weight_above` | weight of that nearest-above node (levels.py scale: HOD/LOD 3.0, psych$50 3.0, etc.) |
| `type_above` | type of that node (HOD/LOD/psych/swing_high/PDH/PMH/pivot_*) |
| `dist_R_below` | (entry close - nearest level node below) / R; same R. |
| `weight_below` | weight of the nearest-below node |
| `type_below` | type of the nearest-below node |
| `body_range_ratio` | entry bar body / entry bar range |
| `displacement` | entry bar range / median range of the prior 20 bars |
| `bars_since_break` | bars elapsed from the most recent break of the retested level to the entry bar (None if no break identifiable) |
| `broken_level_price` | price of the retested level (nearest weight>=2 node to entry close) |
| `broken_level_type` | type of that retested level |
| `broken_level_weight` | weight of that retested level |
| `direction` | 'call' if entry close > retested level else 'put' |
| `entry_i` | the entry bar's index into the RTH bar list (time-of-day proxy, included as a feature) |
| `time_of_day` | entry bar timestamp 'HH:MM' |
| `new_session_high` | entry bar high > prior session high (bars[:entry_i]) |
| `new_session_low` | entry bar low < prior session low (bars[:entry_i]) |
| `is_break_and_retest` | predicates.is_break_and_retest at the retested level/direction |
| `is_order_block` | predicates.is_order_block respected flag at direction |
| `is_84_reentry_opportunity` | predicates.is_84_reentry_opportunity (proxy: original_entry=broken level, original_stop=order-block far side) |
| `is_chop_market` | predicates.is_chop_market |
| `is_x_signal` | predicates.is_x_signal (reject signal) at the retested level/direction |
| `bar_coverage` | levels.py coverage code for the day ('rth' for all usable rows) |

## R-unit

Distances are in R-multiples where **R = the 14-bar 1-minute ATR** over RTH bars up to and including entry_i (`levels.atr_1m`). The marks carry no explicit stop price; ATR_1m is the data-grounded risk scale already used by `research/levels.py` (trader stops sit at ~0.84x ATR_1m), and it is derivable purely from past bars, so using it as the R-denominator neither leaks nor invents a stop. Every usable row has a real ATR (rows without archived bars are dropped), so no `dist_R_*` falls back to a synthetic scale.

## Per-feature null count

| feature | null count (of 105 usable) |
|---|---|
| `symbol` | 0 |
| `day` | 0 |
| `entry_i` | 0 |
| `tier` | 0 |
| `dist_R_above` | 0 |
| `weight_above` | 0 |
| `type_above` | 0 |
| `dist_R_below` | 0 |
| `weight_below` | 0 |
| `type_below` | 0 |
| `body_range_ratio` | 0 |
| `displacement` | 0 |
| `bars_since_break` | 37 |
| `broken_level_price` | 0 |
| `broken_level_type` | 0 |
| `broken_level_weight` | 0 |
| `direction` | 0 |
| `time_of_day` | 0 |
| `new_session_high` | 0 |
| `new_session_low` | 0 |
| `is_break_and_retest` | 0 |
| `is_order_block` | 0 |
| `is_84_reentry_opportunity` | 0 |
| `is_chop_market` | 0 |
| `is_x_signal` | 0 |
| `bar_coverage` | 0 |
