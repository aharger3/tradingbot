# g213 -- instrument columns, T2

Baseline: `baseline_2026-09-05.json.gz` (book_id 2c39ced2697c26cc), unit `up_to_3_stop_win_or_2loss`, universe.CORE_SYMBOLS (tier=='core', 11 symbols), fill=close. 769 unit rows priced. Script: `research/g213_instruments.py`.

**Tree was dirty at build time (2 .py file(s) uncommitted).** Rebuild after committing this repair to get a clean-tree stamp if that matters for your use of this book.

Options priced from real Polygon 1-minute option aggregates for **20 of 769 rows (2.6%)**; the rest (749 rows) fall back to the 0.42-delta + $0.05-spread model. Referee pass 1 found the real coverage this low mainly because (a) Polygon Options Basic has a rolling ~2-year lookback -- a live probe got a 403 on a contract that returned 200 the night before -- and (b) the fetch loop used to `break` on the FIRST 403 instead of `continue`, so one out-of-window row ended the whole pass; both are now fixed (`continue`, permanently cached per-row so it never re-spends a call), but this report was NOT re-fetched against live Polygon as part of this repair, so the 20/769 coverage number itself is unchanged from before the fix. `instrument_source` on every row in `research/tape/instruments_2026-09-05.json.gz` says which.

Futures ratio (SPY->MES 10.0x, QQQ->MNQ 41.35x) is a rule-of-thumb, **not fit to data** -- no ES/MES or NQ/MNQ 1-minute bars exist under `data_archive/` on this box, so `research/g213_verify.py` reports this UNVERIFIED rather than checked against a 7-day overlap (the row's own fallback clause). IWM->M2K is defined but never exercised on this book: IWM is in `universe.INDEX_POOL` but not in `universe.CORE_SYMBOLS`, the tier this baseline trades.

**What the futures column actually measures (referee pass 1).** Integer-contract sizing pins `actual_r_dollars` to within about +-2 pct of $1,000 no matter what the SPY->MES / QQQ->MNQ ratio is, so `pnl = r * actual_r_dollars - commission` is barely more than shares-R minus $1.24/contract commission -- re-pricing all 99 rows at ratio shocks of +-0.5/1/2/5/10 pct moves $/day by about $1 and green months not at all. **This column cannot tell you anything about the SPY:SPX or QQQ:NDX basis; it tells you what commission does to the shares number.** Day margin (required by this row's spec, missing before this repair) is now reported per trade as an approximate, not-fit-to-any-broker figure (MES $50/contract, MNQ $100/contract) -- median notional on the futures-eligible rows is roughly $897,240.

**Futures is worse than shares on the same rows, not better (referee pass 1).** The published version set futures' $/day beside shares' whole-window $/day (99 rows vs all 769) as though matched. On the SAME 99 SPY/QQQ rows: shares $17/day, mean R 0.086, win 55.6%, 13/24 green months vs futures $12/day, mean R 0.058, win 52.5%, 12/24 green months -- futures loses to shares by commission alone.

Sample-size rule (SWARM.md): a cell under 30 trades or 12 months gets no verdict, just the count -- marked inline below. Only 20 rows are real-priced, so the real-vs-model split itself has no verdict either; it is a coverage number, not a comparison.

Why the options model column is this negative: at this engine's typical stop distance, a delta-sized position needs dozens of contracts to reach $1,000 of risk (median ~34 contracts across the model-priced rows here), and the round-trip spread cost scales with contract count. **Spread convention fixed this repair** (referee pass 1): it used to charge TWO full quoted widths ($10/contract round trip) on model rows and zero on the 20 real rows -- the only verified rows were the only rows exempt from the assumption that drove the headline. It now charges the standard ONE full width from mid ($5/contract). The 20 real-bar rows above are ladder-scale-out trades priced at a single entry-to-last-exit-leg option price, which does not price the same trade the shares row booked for scaled exits (most of the 20) -- this is a known, unfixed divergence between the option pricing and the shares pricing for scaled trades, not evidence about option convexity.

## Shares (769 trades)

- whole window: $-52/day, mean R -0.034, win 45.0%, 11/25 green months
- H1 (before 2025-09-01): $9/day, mean R 0.006, win 43.7%, 6/12 green months
- H2 (2025-09-01 on): $-112/day, mean R -0.072, win 46.3%, 5/13 green months

## Futures (99 trades)

- whole window: $12/day, mean R 0.058, win 52.5%, 12/24 green months
- H1 (before 2025-09-01): $71/day, mean R 0.375, win 63.8%, 9/12 green months
- H2 (2025-09-01 on): $-48/day, mean R -0.229, win 42.3%, 3/12 green months

## Options (769 trades)

- whole window: $-326/day, mean R -0.211, win 37.5%, 4/25 green months
- H1 (before 2025-09-01): $-303/day, mean R -0.196, win 36.0%, 3/12 green months
- H2 (2025-09-01 on): $-349/day, mean R -0.225, win 39.0%, 1/13 green months

## Shares, matched to the futures-eligible subset (99 trades)

- whole window: $17/day, mean R 0.086, win 55.6%, 13/24 green months

Single names (AAPL AMD AMZN GOOGL META MSFT NVDA PLTR TSLA) have no futures column (`instrument: "n/a"` on those rows) -- only SPY and QQQ trade as futures micros in this universe.

## Refereed (T2 repair, referee pass 1)

**Fixed in this repair:**

1. Spread convention: was charging two full quoted widths ($10/contract round trip); now charges the standard one full width from mid ($5/contract). Options headline moved from -$607/day 2/25 green to -$326/day 4/25 green.
2. Futures-vs-shares comparison: was comparing futures' 99-row $/day against shares' all-769-row $/day as though matched. Added the "Shares, matched to the futures-eligible subset" section above (same 99 rows, same denominator convention) -- shares $17/day beats futures $12/day on the identical rows; futures is worse by commission, not better.
3. Day margin (required by this row's spec, absent before this repair): added as an approximate, not-fit-to-any-broker figure per contract (MES $50, MNQ $100), plus notional, on every futures-priced row.
4. Fetch loop broke on the FIRST 403 instead of continuing; one out-of-window row ended the whole two-year pass. Now `continue`s (the 403 is cached permanently on that row so it never re-spends a call). Confirmed live during this repair's verify re-run: the TSLA 2024-09-05 row, real-priced when the original book was built, now returns a fresh HTTP 403 from Polygon -- direct evidence of the rolling ~2-year lookback the referee named as the real cause, not the 110-minute wall-clock cap.
5. "the 15 real-bar rows above" corrected to the actual real-bar count (computed, not a hardcoded number).
6. IWM->M2K wording corrected: IWM IS in `universe.INDEX_POOL`, just not in `universe.CORE_SYMBOLS` (the tier this baseline trades) -- the prior wording implied IWM was absent from universe.py entirely.
7. Dirty-tree-at-build-time is now disclosed in this report when `meta.git.dirty_py_count` is nonzero.
8. `g213_verify.py` now states explicitly that its 20-row check is the entire real-row population, not a sample of it, and verifies cache integrity only.

**Refuted, kept as a disclosed limitation (not fixable inside this row without a second change):**

1. The futures column is fundamentally insensitive to the SPY:SPX / QQQ:NDX basis it claims to model: integer-contract sizing pins `actual_r_dollars` within about +-2 pct of $1,000 regardless of the ratio used (re-priced at +-0.5/1/2/5/10 pct ratio shocks: $/day moves ~$1, green months unchanged). This is a structural property of integer sizing on a fixed-R book, not a bug this repair can code its way out of -- the report above now says plainly that this column reads as "shares R minus commission," not a futures venue simulation. Fixing it for real would mean pricing risk in index points directly rather than converting a shares-R figure, which is a second, larger change outside this row's scope.
2. 14 of the 20 real-bar option rows are ladder scale-out trades (30/30/30/10) priced as a single entry-close to last-exit-leg close, which does not price the same trade the shares row booked for scaled exits, and 4 of 20 flip P&L sign against shares on that account. Pricing each leg separately needs the per-leg exit clocks that `backtest_2y.py`'s ladder produces internally but does not export on this row's trade record -- a second change to what the baseline book carries, not something fixable inside `g213_instruments.py` alone.
3. Real-bar coverage remains 20/769 (2.6%) in this repair's output: the break-on-403 bug is fixed (see item 4 above), but a live 2-year re-fetch was not re-run as part of this repair (would cost a fresh ~110-minute background pass against Polygon's 5-calls/min limit); a future `--stage fetch` run will pick up more real coverage than this book has today.
4. Commits `07c35df8` and `ccd7fa06` (T2's original build) are both `wip: auto-commit` messages that do not name the row or number -- history cannot be rewritten under this project's never-rebase rule, so they stand uncorrected; this repair's own commit names the row and the number that moved.
