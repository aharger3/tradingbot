# g154/F5 -- trend-conditional-scale-ladder

**What is different now:** measured Austin's claim that the scale-out ladder should vary with the day's regime -- a smaller first scale, more left to ride (50/20/10/10) on a trending day; earlier, heavier profit-taking (30/30/30/10) on a choppy day -- against a fixed 30/30/30/10 baseline applied every day, on the honest book.

Book `bt2y_trades_retest_on.json`, 498 sessions (H1 249 / H2 249), size-gated on `signal_runner.min_risk_floor`. 1R = $1000. H1/H2 split at 2025-09-01. Regime split point = the H1-IN-SAMPLE median trendiness (0.4097), held fixed and applied unchanged to H2 -- 278 trending / 220 choppy picks by that threshold, 0/498 picks had no bars/entry_i and fell back to the book's own recorded r for both arms.

This is an EXIT-SIDE arm: it cannot change which day trades. candidates/day 16.52, fires/day 1.000, recall_100 2/34, recall_all 18/345, precision 18/59 -- identical for baseline and candidate by construction.

**CAVEAT (read before trusting a green number):** `research/g151_rules_6.json` claim #3 already swept nine causal proxies of this exact 'trendiness' family and found every one a coin flip (two leaning backwards) on the finished-chart version of this measure. This row's predicate is another causal proxy of that family. Any improvement below is SUSPECT until F6 verifies the H1 split threshold was not implicitly fit to H2.

| arm | split | $/day | mean R | win | months green | max DD |
|---|---|---:|---:|---:|---:|---:|
| baseline (fixed 30/30/30/10) | all | $89 | +0.089 | 41.2% | 12/25 | $-20540 |
| baseline (fixed 30/30/30/10) | H1 | $218 | +0.218 | 43.0% | 8/12 | $-10504 |
| baseline (fixed 30/30/30/10) | H2 | $-40 | -0.040 | 39.4% | 4/13 | $-20540 |
| candidate (trend-conditional) | all | $69 | +0.069 | 46.2% | 13/25 | $-23047 |
| candidate (trend-conditional) | H1 | $191 | +0.191 | 49.0% | 8/12 | $-9712 |
| candidate (trend-conditional) | H2 | $-53 | -0.053 | 43.4% | 5/13 | $-23047 |

H1 delta $-27.00/day, H2 delta $-13.00/day. **survivor = False** (H1 and H2 both improve $/day vs. the fixed baseline, recall_100 not below baseline -- identical by construction here).

Full arm data: `g154_rule_trend-conditional-scale-ladder.json`.
