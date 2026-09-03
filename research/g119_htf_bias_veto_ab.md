# g119 -- HTF_BIAS_VETO, the real 2-year book: S recall and false fires

`omen_bot.HTF_BIAS_VETO` (default on). OFF book (lifted) `research/bt2y_trades_htfveto_off.json`, ON book (shipped) `research/bt2y_trades_htfveto_on.json`. Both built on commit `cacc69d905`, `RETEST_REQUIRED=1` fixed in both. `HTF_BIAS_VETO` is not a key in either book's `meta.stamp.flags` -- the stamp only captures `entry_fill`/`loss_halt`/`stop_rule`/`backtest_week`/`signal_runner` globals, and the flag lives in `omen_bot.py` -- so the two books are treated as a matched pair by construction, not re-verified against a literal flag stamp.

**Adversarial pass, 2026-09-03: this file's first cut was REFUTED.** The arithmetic reproduced exactly under independent re-derivation, but every headline delta sat inside its own sampling error, the full-pool and index lanes disagreed in sign on money, two of three '+green months' turned on $84 and $527 across ~20 sessions, the false-fire metric lumped `X`-only (an engine-detection refusal, not a day-level one) in with real refusals, and the verdict's win/lose logic was polarity-inverted (it happened to print the right English sentence only because the data made the wrong branch unreachable). This version drops the binary win/lose call, adds the paired-delta SE, the McNemar test for S recall, Wilson intervals for false fires, and the green-month flip margins, and reports both lanes in the verdict prose rather than the full pool alone.

Shared rows unmoved: **FAIL** (108132 shared, 107 moved, 0.0990%). Same mechanism g94 already found for `RETEST_REQUIRED` and reported as FAIL rather than hiding: a capped candidate is not `fired`, so it releases `backtest_week`'s dedupe suppression window and a different candidate can claim the same (day, symbol, entry-time, direction) slot, occasionally with a different stop. Population delta 184 OFF-only / 1175 ON-only rows -- the same release mechanism's larger, structural half (an opposed HTF bias trips far more often than a failed retest, so the effect is bigger here: 0.0990% moved vs g94's 0.044%, still two orders of magnitude below the row count either way). The adversarial pass isolated the 96 (of 496) full-pool days where the two arms' first pick differs and found the 21 days where ON's pick is entirely absent from the OFF book carry -$13,156 against a +$15,048 net across all 96 -- i.e. this artifact works AGAINST the ON arm's apparent money edge, not for it, so it is not the source of any headline number here.

Grade mix -- OFF {'A': 277, 'B': 9336, 'C': 16519, 'X': 97491} -> ON {'A': 175, 'B': 7978, 'C': 12530, 'X': 104151}

## Money -- one trade a day

| lane | metric | OFF | ON | delta |
|---|---|---:|---:|---:|
| full pool | cand/day | 19.1 | 16.2 | -2.900 |
| full pool | $/day | -2 | 28 | +30.000 |
| full pool | win % | 42.3 | 45.5 | +3.200 |
| full pool | mean R | -0.002 | +0.028 | +0.030 |
| full pool | green mo | 10 | 13 | +3.000 |
| full pool | max DD | 28972 | 22851 | -6121.060 |
| index QQQ/SPY/IWM | cand/day | 2.4 | 2.2 | -0.200 |
| index QQQ/SPY/IWM | $/day | 84 | 72 | -12.000 |
| index QQQ/SPY/IWM | win % | 51.0 | 50.3 | -0.700 |
| index QQQ/SPY/IWM | mean R | +0.084 | +0.072 | -0.012 |
| index QQQ/SPY/IWM | green mo | 13 | 16 | +3.000 |
| index QQQ/SPY/IWM | max DD | 12326 | 15561 | +3234.880 |

## Paired daily $ delta (ON-OFF), with its own noise

One-a-day pick stream, per-session ON minus OFF, over the union of days either arm picked a trade -- a missing day counts as 0 for that arm. Sample SE and a plain 95% interval, same convention CLAUDE.md already uses for g94 ('inside the +-1.58R error bar').

| lane | n | mean $/day | SE | 95% CI | straddles zero? |
|---|---:|---:|---:|---:|:---:|
| full pool | 496 | +30.34 | 30.66 | [-29.75, +90.42] | yes |
| index QQQ/SPY/IWM | 410 | -16.69 | 24.34 | [-64.40, +31.01] | yes |

## Green-month sign flips, with the margin each flip turned on

**full pool** (3 flip(s)):

| month | OFF | ON |
|---|---:|---:|
| 2025-03 | -2808.31 | +6335.51 |
| 2025-06 | -3824.91 | +84.05 |
| 2026-04 | -2991.90 | +527.09 |

**index QQQ/SPY/IWM** (5 flip(s)):

| month | OFF | ON |
|---|---:|---:|
| 2025-08 | -432.42 | +567.58 |
| 2026-04 | -652.42 | +316.52 |
| 2026-05 | -747.18 | +252.82 |
| 2026-06 | +28.79 | -2103.43 |
| 2026-08 | -193.93 | +806.07 |

## S-day recall -- canonical S days, in-universe, with a traded row

In-universe = a (symbol, date) pair with at least one row in that arm's (lane-filtered, common-window) book. `traded` reads the row's own `traded` field (`status=="fired" and grade != "C"`, `backtest_week.SimTrade.counted`) -- not recomputed. Because the veto only ever emits a `skipped_d` row (never removes the symbol-day), the in-universe sets are identical between arms -- verified per lane below, so this is a genuine paired comparison (McNemar exact test on the discordant traded/not-traded pairs).

| lane | OFF traded/in-universe | OFF recall | ON traded/in-universe | ON recall | delta (pts) | in-universe sets equal | discordant OFF/ON | McNemar p |
|---|---:|---:|---:|---:|---:|:---:|---:|---:|
| full pool | 126/294 | 42.9% | 121/294 | 41.2% | -1.7 | yes | 13/8 | 0.3833 |
| index QQQ/SPY/IWM | 26/70 | 37.1% | 24/70 | 34.3% | -2.8 | yes | 4/2 | 0.6875 |

## False-fire rate -- one-a-day picks graded non-S, of picks Austin graded at all

Denominator excludes days with NO canonical-pool opinion for that symbol-day (not counted as a false fire either way; the `unjudged` column names how many were dropped). `X`-only opinions (an engine-detection refusal per marks_pool.py, not a day-level one) are counted in the headline rate but broken out separately; the day-level rate excludes them.

| lane | OFF false/judged (unjudged) | OFF rate | Wilson 95% | ON false/judged (unjudged) | ON rate | Wilson 95% | delta (pts) | OFF breakdown | ON breakdown | day-level OFF/ON |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|
| full pool | 30/53 (443) | 56.6% | [43.3, 69.0] | 39/61 (435) | 63.9% | [51.4, 74.8] | +7.3 | {'A': 12, 'none': 14, 'x_only': 4} | {'A': 13, 'none': 19, 'x_only': 7} | 49.1%/52.5% |
| index QQQ/SPY/IWM | 35/67 (343) | 52.2% | [40.5, 63.7] | 33/63 (323) | 52.4% | [40.3, 64.2] | +0.2 | {'none': 11, 'x_only': 7, 'A': 14, 'C': 3} | {'none': 10, 'x_only': 7, 'A': 13, 'C': 3} | 41.8%/41.3% |

## Verdict

- mean R: OFF -0.002 -> ON +0.028 (+0.030)
- paired $/day (ON-OFF): +30.34, 95% CI [-29.75, +90.42], n=496 -- straddles zero
- green months: OFF 10 -> ON 13 (+3), 3 sign flip(s)
- S recall: OFF 42.9% -> ON 41.2% (-1.7 pts), discordant 13 OFF-only/8 ON-only, McNemar p=0.3833
- false-fire rate: OFF 56.6% -> ON 63.9% (+7.3 pts), Wilson 95% OFF [43.3, 69.0] ON [51.4, 74.8]
- index lane paired $/day (ON-OFF): -16.69, 95% CI [-64.40, +31.01] -- **DISAGREES WITH the full-pool sign**

**No binary win/lose call.** Every headline delta above sits inside a 95% interval that contains zero, S recall's discordant pairs are not distinguishable from a coin flip at p<0.05, and the full-pool and index lanes disagree in sign on money. **This A/B does not make a case for moving `HTF_BIAS_VETO` off its shipped default of ON** -- the honest conclusion is that the flag is unmeasurable at this sample size, not that either arm wins.

No invented statistical machinery beyond plain paired-sample SE, a Wilson interval and an exact McNemar test (stdlib `math.comb`, no scipy) -- the smallest tools that let 'inside noise' be checked rather than asserted.

