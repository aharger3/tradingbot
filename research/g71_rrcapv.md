# G7.1 / rrcapv — adversarial verify of track `rrcap`

**Verdict: REFUTED as stated.** The structural half of the claim holds; the
quantifier "0% of live trades can exceed 2R" is false, and the offered proof
cannot test it because both of its metrics are algebraic identities in `rr`.

## What survives (independently re-read, cites accurate)
- `options_sizer.py:25` `DEFAULT_RR = 2.0`; `:202` param; `:223`/`:228`
  `stock_target = stock_entry +/- rr*stock_risk`; `:291` `target_premium`;
  `:307` `max_reward = per_contract_risk*contracts*rr`. All lines are as cited.
- `live_scanner.py:631` calls `build_options_plan(...)` with no `rr=`
  (`symbol/direction/stock_entry/stock_stop/tasty_feed/max_loss` only).
  `live_scanner.py:494` `build_futures_plan(...)` likewise.
- `paper_trader.py:132-144` `_check_target` returns `target_premium` on an
  intrabar touch and `mark` (`:324-336`) books `pos.contracts` — the whole
  position. No scale rung, no runner: `RULE6_ENABLED = False` (`paper_trader.py:39`).
- No look-ahead: `live_scanner.py:395-401` marks against `candles[-1]` BEFORE
  `_emit_signal` opens (`:465`), so a position is never marked on its entry bar.

## What is false
1. **The proof is circular.** `research/g71_rrcap_live_proof.py` reports
   `(stock_target - entry)/risk` and `max_reward/max_loss`. Substituting
   `:223` gives `rr*risk/risk == rr`, and `:307` defines `max_reward` as
   `max_loss*rr`. Both return 2.000 for *any* input, including a broken sizer.
   They measure arithmetic, not the cap.
2. **1R is a PREMIUM quantity, and the stock-side 2R is not what gets booked.**
   `:294` `per_contract_risk = (entry_premium - stop_premium)*100` is 1R, and
   `paper_trader.realized_pnl` books against exactly that. `:290` floors
   `stop_premium` at $0.05 while `:291` keeps the UNfloored `premium_risk` in
   the target. Whenever the floor binds, booked R > rr.
3. **Measured, not argued.** `research/g71_rrcapv_premium_r.py` replays every
   traded row of the shipped book through the real `build_options_plan`
   (estimate fallback — which *is* the live path whenever the Tastytrade quote
   fails, `options_sizer.py:255-267`):

```
research/bt2y_trades.json  generated 2026-08-29T03:14:29  76,019 rows / 2,437 traded
booked target R  >2.0: 33 (1.35%)   ==2.0: 2404   <2.0: 0   sizing-rejected: 0
stop_premium floor bound on: 34 rows (1.40%)
worst: 7.523R MU 2026-07-31 882.00/914.80 $4.41/$0.05/$37.21 x2
       6.630R MU 2026-08-05 · 6.514R PLTR 2026-08-04 · 5.574R AVGO 2025-03-03
paper_trader end-to-end on the top row: 1R = $872.00, booked $6,560.00 = 7.523R
plan.max_reward SAYS $1,744.00 (= max_loss*rr) — under-reports by 3.8x
```
4. **A second reachable path: cent rounding.** A Tastytrade mid `(bid+ask)/2`
   need not land on a cent, and `:290`/`:291` each `round(...,2)`.
   `research/g71_rrcapv_rounding.py` sweeps $0.20–$8.00 mids x $0.05–$3.00
   premium risk: booked R ranges **1.7273 to 2.3333** with `rr` fixed at 2.0.
5. **Wrong book.** The report's book is 2,437 traded (`research/bt2y_trades.json`,
   also `research/g71_ladder_bt2y_noab.json`). `DIRECTION.md:20` and
   `research/t0_ratified_rebaseline.md:24,37` state the post-T0 book as **2,595
   traded**. The 1,017 figure is the pre-T0 book (`research/a2_bt2y_rerun.json`,
   2026-08-27). The 19.00% backtest figure was taken on neither cited book.
6. **Missing context that changes the meaning of "0%".** `live_scanner.py::_tier`
   returns TRADE only on `grade == "A+"` (4 A+ in this book) or on
   `reentry_84_rule` (grade-exempt). The live/paper book is near-empty, so "0%
   of live trades" is a statement over ~0 rows; and the 84% re-entry route is
   exactly how a B-grade row — all 33 of the >2R rows are grade B — reaches the
   sizer live.

## Corrected statement
The live path has no runner leg and no scale rung: `live_scanner.py:631` takes
`DEFAULT_RR = 2.0` and `paper_trader` closes the whole position at that one
target. But the target is 2R on the STOCK side only; booked R is a premium
ratio, and the `$0.05` `stop_premium` floor (`options_sizer.py:290`) plus cent
rounding put **33 of 2,437 traded rows (1.35%) above 2R, up to 7.52R** — with
`plan.max_reward` under-reporting them by up to 3.8x. That is a sizer defect,
not a runner: it fires when a wide stock stop is mapped onto a cheap contract.

## Scripts
`research/g71_rrcapv_premium_r.py`, `research/g71_rrcapv_rounding.py`. No engine
file touched.
