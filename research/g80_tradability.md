# Tradability -- can a robot actually get filled on this book

Austin: "i want trades that can realistically be done by a robot." A stop too tight to survive
spread plus slippage is not a valid stop no matter what it does to the backtest. This is a
measurement pass, not a fix -- nothing in the engine changed, nothing was committed beyond the
script and this report.

## The spread proxy, stated plainly

We do not have a bid/ask quote feed for this book -- only 1-minute OHLCV bars. So the spread used
here is a **proxy**, not a real quote:

    spread_proxy = max($0.01, 10% x (entry minute's high - low))

That is 10% of the entry bar's own printed range, floored at one
cent so a flat minute doesn't return a zero spread. This is a stated assumption, not a fitted or
historically validated number. A trade is flagged **untradeable** if its stop distance
(|entry - stop|) is under **2x** that proxy -- a bot placing
a market order at that stop distance would routinely get stopped by the spread itself, before any
real move against the position.

## What ran

4508 traded rows in `research/bt2y_trades.json`. Bar lookup (entry-minute OHLC from
the cached `data_archive/<SYM>/<day>.csv` files) succeeded for 4508 of them
(0 failed -- entry_i out of range or a read error, excluded below).

## The headline

**19 of 4508 trades (0.4% of
the book) have a stop distance under 2x the estimated spread.** Removing them:

| book | trades | $/day (all) | $/day (one-a-day) | win rate | mean R | months green |
|---|---:|---:|---:|---:|---:|---:|
| as-is | 4508 | $5,278 | $703 | 59.2% | +0.584R | 25/25 |
| tradeable only | 4489 | $5,161 | $681 | 59.2% | +0.574R | 25/25 |

Standing error bar on this project is +/-1.5799R -- the mean-R gap above (+0.584R vs
+0.574R) is inside it, so call the mean-R read a tie. The dollar and trade-count
changes are not mean-R comparisons and are not subject to that bar the same way, but they still
carry the sampling noise of a 0.4%-of-book removal -- read them as
directional, not exact.

## The removed slice, by itself

19 trades (0.4% of the usable book), total
$58,286, mean R +3.068R, win rate
52.6%. The rest of the book: mean R +0.574R,
win rate 59.2%.

## Cross-check against g71_board.md / t9

g71_board.md calls the too-tight-stop artifact real, and calls tight-RR stops "the book's
R-blowup artifact, not its edge." On this proxy: the untradeable slice's mean R
(+3.068R) is higher than the
rest of the book's (+0.574R), and it is 0.4%
of the book by count but $58,286 of total P&L. **Agree** with
g71/t9's characterization: the untradeable slice is not dragging the book's R down -- if anything
it is carrying disproportionate R relative to its trade count, which is exactly the "blowup, not
edge" signature -- a handful of very tight stops swinging hard in both directions on R while
contributing dollars no robot could actually collect at that stop distance. Removing them is the
right call for a "can a robot do this" read regardless of which way the mean-R sign moved, because
the P&L they contribute is not obtainable at the stated stop with market-order fills against a
10%-of-range spread.

## Stop distance distribution (usable rows, n=4508)

| stat | cents | % of price |
|---|---:|---:|
| p10 | 14.00 | 0.141% |
| median | 48.00 | 0.240% |
| mean | 67.39 | 0.317% |
| p90 | 129.00 | 0.599% |

**182 of 4508 trades (4.0%) have a stop under 10 cents**
-- a distance that is at or below the typical quoted spread on several names in this universe
even before slippage, independent of the 2x-spread-proxy cutoff used above.

## What this does NOT show

This proxy is not a quote feed. It does not model actual bid/ask width per symbol per minute,
does not model slippage beyond the spread itself, and does not model whether a limit order at the
stop price would have filled at all in a fast market. It is one defensible estimate, stated
up front, applied uniformly. Treat the tradeable-only dollar figures as one more data point in the
same family as the other book reconciliations in `g80_dollar_reconcile.md`, not as a new ceiling
or floor on top of them.

## Reproduce

`python research/g80_tradability.py` -- reads `research/bt2y_trades.json` and the cached
`data_archive/<SYM>/<day>.csv` bars (no network calls; every symbol/day in the traded book is
already on disk), writes `research/g80_tradability.json` and this file.
