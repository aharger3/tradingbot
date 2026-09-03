# g114 -- runner profile: what separates a runner at entry time?

Book `bt2y_trades_retest_on.json`, first-of-day arm, size-gated on `min_risk_floor`, bar-ordered MFE-while-alive to 11:00 (g97's exact walk, reused not reimplemented).

**103/444 = 23.2% are runners** (MFE-while-alive >= 3.0R) -- matches g97's own 23.2%.

**85 causal arms tested** (71 categorical/tag values, 14 numeric fields), each a two-sided label-shuffle permutation test (5000 trials).

At raw p<0.05: **9 arms** (chance alone predicts ~4.2 false positives out of 85 tests at this threshold). Bonferroni (p<0.00059): **0 arms survive**.

## Categorical / tag / downgrade arms (top by p)

| field | value | n | runner%% in | runner%% out | diff (pp) | p |
|---|---|---:|---:|---:|---:|---:|
| rangeb | big range | 264 | 28.0 | 16.1 | +11.9 | 0.0046 |
| level_tf | 1D | 92 | 12.0 | 26.1 | -14.2 | 0.0056 |
| dow | Tue | 94 | 33.0 | 20.6 | +12.4 | 0.0142 |
| rangeb | quiet | 34 | 5.9 | 24.6 | -18.8 | 0.0166 |
| tag | chase | 152 | 16.4 | 26.7 | -10.3 | 0.0176 |
| downgrade | chase | 152 | 16.4 | 26.7 | -10.3 | 0.0176 |
| stopb | mid | 195 | 27.7 | 19.7 | +8.0 | 0.0578 |
| level | PDH | 54 | 13.0 | 24.6 | -11.7 | 0.0610 |
| level_name | PDH | 54 | 13.0 | 24.6 | -11.7 | 0.0610 |
| level | PDL | 38 | 10.5 | 24.4 | -13.9 | 0.0752 |
| level_name | PDL | 38 | 10.5 | 24.4 | -13.9 | 0.0752 |
| tier | core | 190 | 27.4 | 20.1 | +7.3 | 0.0876 |
| level | OR high | 75 | 30.7 | 21.7 | +9.0 | 0.0998 |
| level_name | not-his: OR high | 75 | 30.7 | 21.7 | +9.0 | 0.0998 |
| downgrade | no_retest | 29 | 10.3 | 24.1 | -13.8 | 0.1098 |
| rangeb | normal | 146 | 18.5 | 25.5 | -7.0 | 0.1160 |
| stopb | very wide | 71 | 15.5 | 24.7 | -9.2 | 0.1202 |
| vol_regime | wild | 173 | 27.2 | 20.7 | +6.5 | 0.1338 |
| vol_regime | calm | 138 | 18.8 | 25.2 | -6.3 | 0.1386 |
| tripped_bucket | tripped=3 | 144 | 18.8 | 25.3 | -6.6 | 0.1622 |

## Numeric arms (all, sorted by p)

| field | n | mean\|runner | mean\|non-runner | diff | p |
|---|---:|---:|---:|---:|---:|
| stop_pct | 444 | 0.3891 | 0.4924 | -0.1033 | 0.0060 |
| drange (day range %) | 444 | 4.8679 | 4.0820 | +0.7859 | 0.0194 |
| minutes_since_open | 444 | 10.4466 | 9.5455 | +0.9011 | 0.0332 |
| risk_dollars | 444 | 0.7649 | 0.9082 | -0.1433 | 0.1316 |
| dret (day return %) | 444 | 0.6488 | 0.1417 | +0.5071 | 0.1394 |
| tripped_n | 444 | 2.1748 | 2.3519 | -0.1771 | 0.1592 |
| n_downgrades | 444 | 2.1748 | 2.3519 | -0.1771 | 0.1592 |
| gap_abs | 444 | 1.6284 | 1.4322 | +0.1962 | 0.3719 |
| planned_rr (target R) | 444 | 2.0013 | 1.9992 | +0.0021 | 0.3849 |
| n_tags | 444 | 3.1262 | 3.1935 | -0.0673 | 0.4519 |
| s (engine score) | 444 | 4.5146 | 4.6012 | -0.0866 | 0.6099 |
| gap | 444 | 0.3906 | 0.2775 | +0.1130 | 0.6857 |
| entry_price | 444 | 219.2090 | 215.2779 | +3.9311 | 0.8222 |
| level_dist_r | 444 | 1.0000 | 0.9957 | +0.0043 | 1.0000 |
