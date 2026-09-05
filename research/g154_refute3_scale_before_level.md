# g154 refuter #3 -- scale-before-the-level: REFUTED

What is different now, in one sentence: the script's numbers reproduce byte for byte, but the price it shifts is the book's **2R profit target**, not the level -- so the arm does not test the rule it is named after, and the surviving $/day gain is a 0.043 R/trade paired difference whose 95% bootstrap interval is $[5.2, 86.2]/day, straddling zero.

Fill named on every figure below: signal-bar CLOSE entry (`entry` from `bt2y_trades_retest_on.json`), stops through `stop_rule.stop_fill_price`, size-gated one-trade-a-day picks from `research.omen_metrics.first_of_day_arm(size_gate=True)`, 1R = $1,000. Produced by `research/g154_refute3_scale_before_level.py`, which imports and calls the functions in `research/g154_rule_scale-before-the-level.py` directly.

## A. The shifted price is a 2R target, not the level

| check | value |
|---|---:|
| picks priced | 498 |
| `target` is exactly entry +/- 2R | 334 (67.1%) |
| `target` equals the book's own `level_px` | 0/498 (0.0%) |
| median target R-multiple | 2.00 |

The report's table header reads `baseline (target=level)`. It is not the level. The book carries `level_px` separately, and the baseline R-on-hit-only of 2.001 is the giveaway. Austin's rule is about resting the scale-out slightly inside the HOD/LOD; this arm nudges a fixed 2R profit target $0.02-$0.05 nearer to entry, which is a different rule with a different mechanism.

## B. Paired bootstrap on the headline arm (cents_005)

| split | days | delta R/trade | delta $/day | 95%% CI $/day | P(delta<=0) |
|---|---:|---:|---:|---:|---:|
| full | 498 | +0.0429 | +42.95 | [5.2, 86.2] | 0.013 |
| h1 | 249 | +0.0094 | +9.40 | [-35.4, 64.0] | 0.379 |
| h2 | 249 | +0.0765 | +76.49 | [17.1, 143.8] | 0.004 |

## C. 90%% of the whole result is 7 penny-exact touches

| check | value |
|---|---:|
| whole-book R delta the arm earns | +21.39R |
| trades converted into target hits by the $0.05 shift | 15 of 498 |
| trades that LOST a target hit | 0 |
| baseline outcome of the converted trades | {"stop_close": 0, "disaster": 14, "eod": 1, "no_bars": 0} |
| conversions where the bar's extreme equalled the shifted target TO THE PENNY | **7** |
| ... and they carry | **+19.30R = 90.2% of the whole delta** |
| conversions where it cleared by <= $0.01 | 11, +28.25R (132.1%) |
| conversions on a bar that ALSO closed past the level stop | 0 (0.0%) |

This is the refutation. The arm's entire edge is 15 trades out of 498, **14 of which the baseline booked as a -1R disaster stop** -- price ran to within a nickel of the 2R target and then collapsed. On 7 of them the 1-minute bar's extreme equals the shifted target exactly, to the cent, and goes no further; the walker books each as a full ~+2.7R swing. Those 7 alone are 90%% of the book-wide gain. A resting limit whose price the bar merely touches is the least reliable fill in this project -- it is the queue-priority coin flip, on the one bar where the market immediately reversed to a full stop-out. `simulate_exit`'s intrabar priority attack does NOT land (0 of 15 converted on a bar that also closed past the stop), and that is reported here as a check that failed; the exact-touch dependence is what does land.

## D. Concentration and multiplicity

| check | value |
|---|---:|
| H2 sessions | 249 |
| H2 sessions where the shift changed pnl at all | 88 |
| H2 total R delta | +19.05R |
| share of the H2 delta from its 5 largest trades | 72.8% |
| share from its 10 largest | 133.3% |
| arms tried in this one script | 3 |
| P(one arm passes 'both halves positive' under a coin-flip null) | 0.25 |
| P(any of 3 arms passes) | 0.578 |
| expected false survivors across the swarm's 25 candidates | ~14.5 |

| H2 day | sym | delta R |
|---|---|---:|
| 2026-05-12 | MSFT | +2.946 |
| 2025-10-24 | NFLX | +2.800 |
| 2025-11-24 | UBER | +2.760 |
| 2025-10-01 | SOFI | +2.722 |
| 2026-01-15 | SOFI | +2.636 |
| 2026-07-20 | MARA | +2.636 |
| 2025-10-21 | ACHR | +2.583 |
| 2025-10-31 | INTC | +2.571 |
| 2026-07-16 | SOFI | +2.545 |
| 2026-03-03 | ACHR | +1.187 |

## Verdict: REFUTED

The arithmetic reproduces byte for byte -- `$50/day -> $93/day`, H1 +9.40, H2 +76.50, precision 30.5%% unchanged, recall_100 5.9%% unchanged, all re-run from the committed script. It is refuted on four grounds, in order of weight:

1. **90% of the gain is 7 penny-exact touches.** 15 of 498 trades change outcome; 14 of those were -1R disaster stops that came within a nickel of the 2R target; on 7 the bar's extreme equals the shifted target to the cent. Remove those 7 and +19.30R of the +21.39R whole-book delta is gone.

2. **It does not test the rule it is named after.** The price shifted is the book's 2R profit target (67.1%% of picks are exactly 2R, median 2.00R), not the level -- `target` equals `level_px` on **0 of 498** picks. The report's own table header says `baseline (target=level)`.

3. **The H1 leg is a coin flip.** Paired bootstrap: H1 +9.40 $/day, 95% CI [-35.4, 64.0], P(delta<=0) = 0.379. The survivor rule needs H1 positive and H1 is indistinguishable from zero.

4. **Multiplicity.** 'Both halves positive' is a 1-in-4 null event; 3 arms were tried here (P(any) = 0.578) inside a 25-candidate sweep expecting ~14.5 false survivors. All 3 arms 'survived', which is itself the tell: a monotone knob that always helps at every size is arithmetic, not a rule.

Separately, and stated by the original script itself: the baseline is a single-stage proxy walker the shipped book never runs (`backtest_week._ladder_bar` is the real exit), so `$50/day` is not the engine's booked one-trade-a-day figure and `$93/day` is not a forecast of it.
