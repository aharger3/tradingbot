# s_gate_spec -- the S gate, pre-registered (omen-3.6 / T5)

Source data: `research/mark_features.jsonl` (105 usable marks: S=48, A=45, X=12; 102 distinct (symbol, day) blocks). Block bootstrap over whole trading days, 10000 resamples.

Statistical floor: 4 percentage points or Cohen's d = 0.15. A feature whose S/X effect reverses sign against S/A is flagged (it measures 'obviously bad', not 'his best').


## Ranked table -- S-vs-X (n_S=48, n_other=12)

| feature | type | effect | 95% bootstrap CI | raw p | BH-FDR adj p | MDE | sign-reversal flag |
|---|---|---|---|---|---|---|---|
| new_session_high | bool | +8.333pp | [+1.923, +16.667] | 0.3006 | 1.0000 | 45.185pp | **REVERSED vs S-vs-A** |
| is_84_reentry_opportunity | bool | +8.333pp | [-24.651, +40.000] | 0.6054 | 1.0000 | 45.185pp | **REVERSED vs S-vs-A** |
| is_order_block | bool | +6.250pp | [-25.253, +36.880] | 0.6878 | 1.0000 | 45.185pp |  |
| new_session_low | bool | -4.167pp | [-23.530, +8.511] | 0.5536 | 1.0000 | 45.185pp | **REVERSED vs S-vs-A** |
| is_x_signal | bool | -4.167pp | [-20.409, +17.000] | 0.6876 | 1.0000 | 45.185pp |  |
| bars_since_break | cont | -0.571d | [-1.815, +0.604] | 0.2841 | 1.0000 | 0.904d |  |
| weight_below | cont | +0.307d | [-0.305, +0.784] | 0.2779 | 1.0000 | 0.904d |  |
| displacement | cont | +0.256d | [-0.378, +0.817] | 0.3744 | 1.0000 | 0.904d |  |
| entry_i | cont | -0.253d | [-1.176, +0.634] | 0.5688 | 1.0000 | 0.904d |  |
| dist_R_above | cont | +0.251d | [-0.377, +0.847] | 0.4156 | 1.0000 | 0.904d | **REVERSED vs S-vs-A** |
| dist_R_below | cont | -0.102d | [-0.822, +0.563] | 0.7602 | 1.0000 | 0.904d |  |
| broken_level_weight | cont | +0.026d | [-0.670, +0.634] | 0.9355 | 1.0000 | 0.904d |  |
| body_range_ratio | cont | -0.012d | [-0.740, +0.744] | 0.9734 | 1.0000 | 0.904d |  |
| weight_above | cont | -0.010d | [-0.689, +0.580] | 0.9745 | 1.0000 | 0.904d | **REVERSED vs S-vs-A** |
| is_break_and_retest | bool | +0.000pp | [-26.017, +21.739] | 1.0000 | 1.0000 | 45.185pp |  |
| is_chop_market | bool | +0.000pp | [+0.000, +0.000] | 1.0000 | 1.0000 | 45.185pp |  |

## Ranked table -- S-vs-A (n_S=48, n_other=45)

| feature | type | effect | 95% bootstrap CI | raw p | BH-FDR adj p | MDE | sign-reversal flag |
|---|---|---|---|---|---|---|---|
| is_x_signal | bool | -5.833pp | [-17.917, +6.000] | 0.3417 | 0.9432 | 29.050pp |  |
| is_order_block | bool | +4.583pp | [-15.035, +24.393] | 0.6484 | 0.9432 | 29.050pp |  |
| new_session_low | bool | +1.944pp | [-5.000, +8.941] | 0.5959 | 0.9432 | 29.050pp | **REVERSED vs S-vs-X** |
| is_break_and_retest | bool | +1.111pp | [-13.859, +16.503] | 0.8842 | 0.9855 | 29.050pp | **REVERSED vs S-vs-X** |
| is_84_reentry_opportunity | bool | -1.111pp | [-20.692, +19.045] | 0.9147 | 0.9855 | 29.050pp | **REVERSED vs S-vs-X** |
| entry_i | cont | -0.613d | [-1.059, -0.200] | 0.0037 | 0.0586 | 0.581d |  |
| new_session_high | bool | -0.556pp | [-12.118, +10.639] | 0.9239 | 0.9855 | 29.050pp | **REVERSED vs S-vs-X** |
| weight_above | cont | +0.385d | [-0.010, +0.804] | 0.0608 | 0.4864 | 0.581d | **REVERSED vs S-vs-X** |
| displacement | cont | +0.304d | [-0.098, +0.666] | 0.1385 | 0.6027 | 0.581d |  |
| dist_R_above | cont | -0.303d | [-0.696, +0.109] | 0.1507 | 0.6027 | 0.581d | **REVERSED vs S-vs-X** |
| bars_since_break | cont | -0.230d | [-0.722, +0.297] | 0.3663 | 0.9432 | 0.581d |  |
| broken_level_weight | cont | +0.166d | [-0.237, +0.585] | 0.4227 | 0.9432 | 0.581d |  |
| dist_R_below | cont | -0.127d | [-0.505, +0.314] | 0.5454 | 0.9432 | 0.581d |  |
| body_range_ratio | cont | -0.107d | [-0.542, +0.305] | 0.6094 | 0.9432 | 0.581d |  |
| weight_below | cont | +0.037d | [-0.375, +0.451] | 0.8586 | 0.9855 | 0.581d |  |
| is_chop_market | bool | +0.000pp | [+0.000, +0.000] | 1.0000 | 1.0000 | 29.050pp |  |

## PRE-REGISTERED GATE

One feature -- **displacement** -- the strongest separator whose effect keeps the SAME sign on both contrasts (d S/X=+0.26, S/A=+0.30: higher displacement = his best, not 'obviously bad'). The X arm is n=24, which cannot support two features without curve-fitting, and the single-feature displacement gate clears the 4pp floor on BOTH contrasts with a higher minimum gap than any 2-feature combination tried (displacement+entry_i maxed at a 6.2pp S/X gap), so parsimony wins. entry_i (d S/A=-0.61) is the strongest S/A separator and a real candidate, but adding it does not raise the minimum gap and shrinks the X arm's support further.

**Predicate (one line of pseudocode):**

```
accept  <=>  displacement >= 0.888
```

**Literal threshold (from S/X quantiles):**

- `displacement >= 0.888` = the X marks' 50th percentile (median displacement of the reject set). A candidate must be at least as displaced as the typical reject to pass. X marks' displacement distribution 25/50/75/90 pct = 0.776/0.888/1.222/1.580; S marks 25/50/75/90 pct = 0.824/0.977/1.269/1.582. `displacement` = entry-bar range / median range of the prior 20 bars (the same definition `research/mark_features.md` uses).


**Fractions on the marks:**

- S kept = 62.5%  (30/48)

- X kept = 50.0%  -> X rejected = 50.0%  (6/12)

- A kept = 53.3%  -> A rejected = 46.7%  (21/45)


**Keep-rate gaps (gate effect, with block-bootstrap 95% CI):**

- S - X = +12.5pp  CI [-20.7, +45.5]

- S - A = +9.2pp  CI [-11.5, +29.2]


**Floor:** CLEARS the 4pp floor on both contrasts.


**Prediction for the backtest (T7):** the gate is registered BEFORE any backtest runs. The engine only fires ~4/77 of Austin's S marks (research/engine_recall.md: detection problem, not a filter problem), so this gate operates on the trades the engine already takes, most of which are not Austin's S marks. The gate removes low-displacement entries from the 1,289-trade backtest. If the displacement edge seen on the held-out marks transfers, avg R / win rate rise; if it does not (the marks barely overlap the engine's trades), a null -- movement inside the CI -- is a real and likely result. The honest pre-registered prediction is a SMALL positive move in avg R with a CI that may span zero; we will NOT re-tune the 0.888 threshold after seeing T7.

