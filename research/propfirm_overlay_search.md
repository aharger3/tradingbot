# Prop-firm overlay search: can a followable overlay make the stream pass?

2026-09-26. Script `research/propfirm_overlay_search.py` → `research/propfirm_overlay_search.json`
(re-run: `python research/propfirm_overlay_search.py`, about 100 s on 8 cores). Follows PR #26
(`research/propfirm_gate.py`, 0/6 firms pass at flat $1,000/R, one trade a day).

**Fill, everywhere below:** the gate's own book, `research/bt2y_trades_retest_on.json.gz`
(RETEST_REQUIRED=1, 498 sessions, 2024-09-03 → 2026-09-02). Signal-bar CLOSE entry,
`stop_rule.stop_fill_price()` stops, size-gated on `signal_runner.min_risk_floor`. No new market
data: every overlay re-selects and re-sizes trades that are already in the book.

## The answer

1. **Nothing passes robustly. 0/6 firms.** Don't buy an eval on this.
2. **On the formal bar, 5 of 6 firms clear it.** The bar is ≥50% of start dates passing in both H1
   and H2, using the real trade order. The best is **Apex 50K EOD** with this overlay: all grades,
   at most 2 trades a day and one position at a time, stop for the day at −1R or +1R, sit out one
   session after 2 red days, **$300/R**. It passes **H1 66.9% / H2 70.8%**. Median time to pass is
   34 / 57.5 sessions. It makes **+$29.01 / −$10.29 a day**, so it loses money in the later half.
3. **Those pass rates come from the order the days happened to fall in, not from the stream.**
   Each half has about 130 overlapping 120-session windows. Their outcomes come in solid blocks, so
   each half is really only 2 or 3 independent evals. Shuffle the same days and the Apex pick
   passes **53.6% / 9.3%**. A zero-drift stream with the same volatility passes **31.1% / 28.0%**.
   In H2, every firm's pick does no better than zero drift. Every pick also uses "sit out after 2
   red days". That rule fits when losing days cluster, as they did in this sample.
4. **We also asked the i.i.d. question directly (stage 2).** We took all 9 overlays whose mean R per
   session is positive in both halves and tested every firm at $150–$500/R on shuffled days. The
   best is Apex again: S+A only, at most 5 trades a day, −1R/+1R day stops, 2-red-day cooldown,
   $250/R. It passes **36.0% / 29.4%**, below the bar and about what zero drift gets. In the real
   order it passes 40.0% / 60.8% and makes **+$20.92 / +$16.12 a day**. Commissions are not in
   those dollars.
5. **The blocker is still the edge, not the overlay** (g174, 2026-09-05). The best overlay stream
   makes +0.08R / +0.07R per session with an SD of about 1.7R, which is t ≈ 0.7 in each half. A
   risk overlay can reshape variance but can't create drift.

## Stage 1: best overlay per firm (max of min(H1, H2), real order)

Pass = a start date that PASSES `omen_metrics.evaluate_prop_challenge` within a 120-session window
that sits entirely inside its half. There are 130 starts per half. "Before" is the gate's own
stream (one trade a day, all grades, $1,000/R) scored on the same windows.

| firm | before H1 / H2 | best overlay | pass H1 / H2 | median sessions to pass | $/day H1 / H2 | shuffled H1 / H2 | zero-drift H1 / H2 | overlays clearing the bar |
|---|---|---|---|---|---|---|---|---|
| Apex 50K Eval EOD | 34.6 / 26.9 | all, max 2/day, −1R & +1R day stops, sit out after 2 red days, $300/R | **66.9 / 70.8** | 34 / 57.5 | +29.01 / **−10.29** | 53.6 / **9.3** | 31.1 / 28.0 | 33 / 2,997 |
| Take Profit Trader 50K | 26.9 / 22.3 | same as Apex | 64.6 / 70.8 | 35.5 / 57.5 | +29.01 / −10.29 | 49.1 / 10.2 | 28.2 / 27.5 | 34 / 5,994 |
| Topstep 50K Combine | 18.5 / 11.5 | S+A, max 3/day, −1R day stop, sit out after 2 red days, $200/R | 65.4 / 57.7 | 41 / 39 | +13.81 / +1.53 | 20.8 / 14.5 | 18.8 / 21.7 | 11 / 2,997 |
| MyFundedFutures Rapid 50K | 33.1 / 23.1 | same as Topstep | 65.4 / 57.7 | 41 / 39 | +13.81 / +1.53 | 22.3 / 13.4 | 21.4 / 20.4 | 8 / 2,997 |
| Alpha Futures 50K Standard | 7.7 / 6.9 | same as Topstep | 65.4 / 56.9 | 41 / 39.5 | +13.81 / +1.53 | 22.1 / 12.2 | 19.7 / 19.2 | 7 / 2,997 |
| Vanquish Advanced Options 50K | 14.6 / 6.9 | all, max 2/day, sit out after 2 red days, $250/R | 32.3 / 33.8 | 66 / 77.5 | +12.06 / −2.55 | 10.6 / 4.8 | 6.8 / 4.7 | **0** / 5,994 |

On the gate's own whole-history convention (every start, the firm's `max_days` or the rest of the
series, censored = fail), these picks read 41.6% for Apex, 45.0% for Topstep and 17.3% for Vanquish.
Starting from the first day, none of them passes. Trades per session: 1.26 for the Apex/TPT pick,
1.69 for the Topstep/MFFU/Alpha pick.

## Stage 2: best i.i.d. pass rate per firm (overlays with positive mean R in both halves)

The pass rate is averaged over 40 shuffles of each half's sessions. The overlay is re-applied to
the shuffled days, so the cooldown rules still act.

| firm | overlay | shuffled H1 / H2 | real order H1 / H2 | $/day H1 / H2 | clears 50%? |
|---|---|---|---|---|---|
| Apex 50K Eval EOD | S+A, max 5/day, −1R & +1R day stops, sit out after 2 red days, $250/R | **36.0 / 29.4** | 40.0 / 60.8 | +20.92 / +16.12 | no |
| Take Profit Trader 50K | all, max 5/day, −1R & +2R, 2-red cooldown, $400/R | 34.1 / 18.8 | 48.5 / 34.6 | +28.99 / +5.38 | no |
| Alpha Futures 50K | all, max 5/day, −1R & +2R, 2-red cooldown, $300/R | 32.3 / 15.3 | 31.5 / 31.5 | +21.75 / +4.04 | no |
| Topstep 50K Combine | S+A, max 5/day, −1R & +2R, 2-red cooldown, $500/R | 28.0 / 26.3 | 39.2 / 32.3 | +41.61 / +35.85 | no |
| MyFundedFutures Rapid 50K | S+A, max 5/day, −1R & +1R, 2-red cooldown, $500/R | 27.0 / 24.9 | 39.2 / 30.8 | +41.85 / +32.24 | no |
| Vanquish Advanced Options 50K | all, max 5/day, −1R & +2R, 2-red cooldown, $250/R | 25.6 / 4.3 | 23.1 / 0.0 | +18.12 / +3.36 | no |

Only 9 of the 333 distinct overlay streams have positive mean R in both halves. The best,
S+A / max 5 / −1R & +2R / 2-red cooldown, makes +0.083R and +0.072R per session.

## Method

- **Stream.** Same eligibility and order as `omen_metrics.first_of_day_arm`: fired-and-traded plus
  halted rows, size-gated, sorted by (day, et, sym). All candidates are kept, not just the first.
  `selfcheck()` asserts that the 1-trade / all-grades / no-stop overlay reproduces
  `first_of_day_arm` exactly, and that it reproduces the gate's all-starts pass rates for Apex and
  Topstep.
- **Overlays.** 441 specs collapse to 333 distinct daily series. Scored at 9 sizes
  ($100–$1,000/R) × 6 firms, plus stop-at-target for firms with a minimum-days rule, that is
  23,976 configs. The grid:
  - grade `sgrade` ∈ {all, S+A, S}. This is Austin's ladder from `downgrade.py`, which is measured
    only. It is used here as a filter, not as the engine's fire gate.
  - max trades/day ∈ {1, 2, 3, 5}, one position at a time. Exit minute = et + bars on 1m.
  - day loss stop ∈ {none, 1, 2, 3}R and day profit stop ∈ {none, 1, 2, 3}R, both on realized
    closes.
  - cooldown ∈ {none, sit out after a red day, sit out after 2 red days}.
  - stop-at-target: 0.1× size once the target is hit with consistency already satisfied. It changed
    nothing in any firm's top 5.
- **Halves.** H1 is day < 2025-09-01 and H2 is day ≥ 2025-09-01 (249 / 249 sessions), the same
  split as g174 and CLAUDE.md. A window never reads the other half.
- **Simulator.** `omen_metrics.evaluate_prop_challenge`, unmodified, with the six `FIRM_RULES` rows
  from PR #26. The daily loss limit is checked against the day's worst realized running P&L.

## Caveats (each one pushes the real number down, not up)

- **Instrument.** These R-multiples come from equity/options signals on 28 symbols. Futures firms
  trade index futures, so applying the book's R to an MES/ES account is an assumption that hasn't
  been tested (CLAUDE.md: "prop firms are futures desks").
- **Costs.** Commissions and futures slippage are not modeled. At micro sizing they run to tens of
  dollars per trade, which is the same order as the best H2 $/day above.
- **Daily loss limit.** It is checked on realized closes only. A winner's open drawdown isn't in the
  book.
- **Selection.** 23,976 configs were searched on about 5 independent evals of history. Any
  real-order pass rate here is an upper bound.
- **Unverified firm rules.** Apex, MFFU, Alpha's daily loss limit and TPT's trailing drawdown are
  flagged "verify" in `propfirm_gate.FIRM_RULES`.
