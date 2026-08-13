# T4 -- the honest EV: pessimistic fill, R-capped, walk-forward

`research/t8_ev.md` reported **+0.914R per trade**. That number is in-sample, optimistically filled and uncapped -- all three of the assumptions omen-5.1 exists to strip out. This is the same two-year replay (2024-08-12 to 2026-08-10, 500 trading sessions, 29 symbols, $1,000 risk, `STOP_ON_CLOSE=1`, `LADDER_MODE=B`) scored under every combination of the three.

Population is the **traded** book -- fired, engine grade A+/A/B -- 1017 trades. Win rate counts decided trades only; EV is mean R per trade and counts every trade, scratches included. CIs are percentile bootstrap, 20,000 resamples, seeded (20260813), the method of `research/t8_significance.md`.

That is **not quite** the population the +0.914R came from: `research/t8_rows.json` holds 1047 traded trades over 501 days, 30 more than replay here. The difference is data, not logic -- see *Where the archive runs out* below, which measures it rather than waving at it.

## How the window was split

- **In-sample:** 2024-08-12 to 2026-02-09 -- 375 trading days (the first 75%), 698 trades.
- **Out-of-sample:** 2026-02-10 to 2026-08-10 -- 125 trading days (the final 25%), 319 trades.

Chronological, never shuffled. A random split would put next month's bars on the training side of a rule that reads its own history, which leaks the future into the past and quietly guarantees a good answer.

**This out-of-sample number is not a true holdout, and should not be sold as one.** Every rule in the engine was written and tuned while looking at the whole archive, these final days included. A real holdout is data that did not exist when the rules were fitted. What this split does buy is the one check available today: whether the edge is stable in time, or whether it lived in the earlier part of the window and has since decayed. Read it as the best available check, not as proof.

## The eight cells

| fill model | R cap | sample | trades | win rate | EV/trade | 95% CI |
|---|---|---|---|---|---|---|
| optimistic | uncapped | in-sample | 698 | 55.4% | **+0.837R** | [+0.670, +1.008] |
| optimistic | uncapped | out-of-sample | 319 | 53.9% | **+0.953R** | [+0.700, +1.218] |
| optimistic | capped at 2R | in-sample | 698 | 55.4% | **+0.351R** | [+0.255, +0.447] |
| optimistic | capped at 2R | out-of-sample | 319 | 53.9% | **+0.370R** | [+0.223, +0.517] |
| pessimistic | uncapped | in-sample | 698 | 55.4% | **+0.837R** | [+0.673, +1.008] |
| pessimistic | uncapped | out-of-sample | 319 | 53.9% | **+0.953R** | [+0.699, +1.214] |
| pessimistic | capped at 2R | in-sample | 698 | 55.4% | **+0.351R** | [+0.254, +0.449] |
| pessimistic | capped at 2R | out-of-sample **<-- the honest one** | 319 | 53.9% | **+0.370R** | [+0.223, +0.517] |

The two fill columns are identical, and that is a finding, not a bug. The pessimistic flag demonstrably bites: over the 44,633 signals the engine simulates it moved **26** fills, 0 of them on a trade the engine actually took. Of those 26, 25 are signals the engine skipped outright and 1 is a fired C-grade alert -- none of them reach the traded book, so the traded EV cannot move. `research/t51_fill.md` reached the same zero from the other direction.

This arm is a real replay of T2's committed flag, not a restatement of T2's file: `PESSIMISTIC_FILL` now lives in `backtest_week.py` (default ON) and both arms are driven through it. The 26 fills moved here match the 26 rows in `research/t51_fill_flip.jsonl` exactly, so the two rows agree on which bars the rule touches as well as on the traded-book answer of zero.

For reference, the same four assumption sets scored over the **whole** window, in-sample and out-of-sample pooled -- this is the row `t8_ev.md` was quoting:

| fill model | R cap | trades | win rate | EV/trade | 95% CI |
|---|---|---|---|---|---|
| optimistic | uncapped | 1017 | 55.0% | **+0.873R** | [+0.735, +1.015] |
| optimistic | capped at 2R | 1017 | 55.0% | **+0.357R** | [+0.276, +0.437] |
| pessimistic | uncapped | 1017 | 55.0% | **+0.873R** | [+0.736, +1.014] |
| pessimistic | capped at 2R | 1017 | 55.0% | **+0.357R** | [+0.275, +0.438] |

## Where the archive runs out

**12 of the 29 symbols have a `data_archive` that ends before the window does**, and the shortfall lands inside the out-of-sample quarter -- the one this report's headline comes from. 11 of them stop in July 2026:

| symbol | last archived day | out-of-sample days covered |
|---|---|---|
| GOOG | 2026-02-23 | 9 / 125 |
| AVGO | 2026-07-10 | 104 / 125 |
| BABA | 2026-07-10 | 104 / 125 |
| COIN | 2026-07-10 | 104 / 125 |
| CRM | 2026-07-10 | 104 / 125 |
| HOOD | 2026-07-10 | 104 / 125 |
| IREN | 2026-07-10 | 104 / 125 |
| NFLX | 2026-07-10 | 104 / 125 |
| SOFI | 2026-07-10 | 104 / 125 |
| TSM | 2026-07-10 | 104 / 125 |
| UBER | 2026-07-10 | 104 / 125 |
| MARA | 2026-07-20 | 110 / 125 |

So the out-of-sample book scored above is 319 trades where T8's was larger. This is a thinner sample, not a different engine: every missing trade is a day whose 1-minute bars are absent from this checkout, and no trade present here is missing from T8's book.

`research/t8_rows.json` still holds those days, so the gap can be priced rather than apologised for. Scoring the **same** chronological 75/25 split on that fuller book (split at 2026-02-10, through 2026-08-11) gives:

| book | R cap | sample | trades | win rate | EV/trade | 95% CI |
|---|---|---|---|---|---|---|
| this checkout | capped at 2R | out-of-sample | 319 | 53.9% | **+0.370R** | [+0.223, +0.517] |
| t8_rows.json (fuller archive) | capped at 2R | out-of-sample | 349 | 55.7% | **+0.422R** | [+0.281, +0.564] |
| this checkout | uncapped | out-of-sample | 319 | 53.9% | **+0.953R** | [+0.699, +1.214] |
| t8_rows.json (fuller archive) | uncapped | out-of-sample | 349 | 55.7% | **+1.069R** | [+0.820, +1.328] |

The fuller book is **+0.052R** on the headline cell. The days this checkout is missing were, on balance, *good* ones -- so the number reported here is the more conservative of the two, and the verdict below does not depend on which book you use. Both CIs sit above zero. Treat the headline as a floor rather than a point estimate, and re-run this row on the Windows box, where the archive is complete, before quoting it to three decimals.

## What each assumption was worth

Each removed on its own, from the top-left cell (optimistic, uncapped, in-sample):

| assumption removed | EV moves by |
|---|---|
| pessimistic fill instead of optimistic | +0.000R |
| cap every trade at +2R | -0.486R |
| score the final 25% of days instead of the first 75% | +0.116R |

The fill model is worth **+0.000R** -- T2 already measured why: the stop is tested before every profit rung in both exit paths, so a bar that tagged a target and closed beyond the stop was **already** booking the loss before the flag existed. The R cap is the expensive one. Ladder B's runner has no ceiling, so a handful of trades carry most of the total R, and clipping them at 2R is what separates an edge from a tail.

## Which single number is the truth

**Use the pessimistic-fill, 2R-capped, out-of-sample cell: +0.370R per trade over 319 trades, 53.9% win rate, 95% CI [+0.223, +0.517].**

In plain English: that cell is the backtest with every flattering assumption taken away at the same time. It assumes you never get the friendly fill when one minute both touched your profit level and closed past your stop. It refuses to count the rare monster trade that ran ten times your risk, treating it as if you had taken twice your risk and walked. And it only scores the most recent quarter of the two years, the part of the history furthest from the days the rules were built on. If the number is still positive there, the edge is not an artifact of the three things that were making it look big.

It is positive, and the confidence interval stays above zero (+0.223R at the low end). On 319 trades that is a real, small edge: roughly +0.37 times your risk per trade, so at $1,000 risk about $370 a trade on average, before commissions and slippage on the options themselves -- which this backtest does not model.

Two honest asterisks on that number, both already priced above: the out-of-sample window is **not a true holdout** (the rules were fitted while looking at these days), and this checkout's archive is missing the last month for 12 symbols. Neither flips the verdict -- the fuller book scores the same cell *higher* -- but they are why the headline is a floor to trade from, not a precise expectancy.

Everything above that cell in the table is a more flattering assumption. Quote the honest cell, keep the others visible so it is obvious what each assumption was worth, and retire +0.914R -- it is the most optimistic corner of this table, not the engine's expectancy.

headline_ev_r: 0.370
headline_ev_ci_low: 0.223
headline_ev_ci_high: 0.517
headline_win_rate: 53.9
headline_trades: 319
headline_cell: pessimistic_fill/cap_2r/out_of_sample
edge_survives: yes
