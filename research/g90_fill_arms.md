# OMEN 8.0 R1 -- the four fill arms, priced against each other

`2024-08-12` to `2026-08-11`, 29 symbols (MAJOR_15, INDEX_POOL, OTHER_POOL), 11923 symbol-days. 925 traded signals (fired, engine grade != C, `reentry_84_rule` excluded -- see script docstring) form the ONE signal set every arm below is scored on. Blind 2R exit (`LADDER_MODE=None`), `STOP_ON_CLOSE=1` -- the committed stop rule, unchanged. $1,000 risk/trade.

## Result

| arm | trades | unfilled | win rate | mean R | months | green months | $/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| as_booked | 793 | 132 | 58.5% | +0.7552 | 25 | 25/25 | $1,443 |
| limit_level | 790 | 135 | 58.6% | +0.7537 | 25 | 25/25 | $1,435 |
| next_open | 925 | 0 | 41.8% | +0.2551 | 25 | 22/25 | $569 |
| chase_once | 785 | 140 | 35.1% | +0.0564 | 25 | 14/25 | $107 |

Trade counts by arm: {'as_booked': 793, 'limit_level': 790, 'next_open': 925, 'chase_once': 785}. **All four differ** -- the fill mode is genuinely changing which trades exist, not just relabeling P&L on an identical set.

## Verdict

**The +0.03R ceiling in `omen-blockers.md` does not reproduce.** as_booked (+0.7552R) and limit_level (+0.7537R) come out within 0.002R of each other, both 25/25 green months -- a properly non-lookahead resting-limit fill (order can only be placed once the signal exists, cancelled if unfilled after 12 bars, and a touch at the exact bar extreme does not count -- see the arm definitions above) does NOT collapse the edge the way the vault's headline number claims. as_booked's +0.7552R also lands close to the vault's pre-rebuild +0.72R figure, so this reconstruction is tracking the same quantity the vault's older numbers describe.

**Austin's actual method (next_open, market at the signal bar's close) pays +0.2551R, $569/day, 22/25 green months.** That is real and comfortably above zero -- not the dramatic collapse the ceiling claim describes, but also well below the as_booked/limit_level number: the fill is not free, it costs roughly 66% of the as-booked edge, mostly through a lower win rate (next bar's open has already moved past the confirmation price), not through the strategy having no edge at all.

**chase_once (+0.0564R, only 14/25 green months) is the arm that actually lands near the vault's +0.028R ceiling figure.** That is worth flagging plainly: it raises the possibility that whatever the lost 2026-08-30 rebuild measured was closer in spirit to 'pay up to get filled' than to a passive resting order -- but this is circumstantial (one number landing close to another), not a claim about what that code did, since that code is not recoverable from this repo (see below).

**Answering R1's question directly: the ceiling is not a property of the strategy at the honest-fill definition this script can reconstruct.** A genuinely obtainable resting-limit fill pays within noise of the naive back-dated one, and Austin's own stated method (market at candle close) still pays a real, positive, mostly-green-months edge. The one arm that resembles the vault's ceiling number is the one that pays up rather than waits -- an execution-discipline question, not a strategy-is-dead one.

## What could not be reconstructed

`signal_runner.py` on this repo's `main` (998fbfec, 2026-08-24) has ONE committed fill model (`fill_price`, line 601) -- there is no `as_booked`/`limit_level`/`next_open`/`chase_once` switch at `:1456` or anywhere else, on `main` or on any other branch, local or remote. `OMEN-7.3.md` and `research/g80_lookahead_refute.md`, the sources `omen-blockers.md` cites for the +0.72R -> +0.028R collapse and the 85.2%/2.3% obtainability split, are not in this repo either -- consistent with `omen-blockers.md`'s own note that the 2026-08-30 rebuild happened on `Desktop/Projects/tradingbot/` and was never pushed. This script is a from-scratch reconstruction built only from what IS committed (the structural `level` every `fill_price()` call site already carries, and each signal's position in its day's candle sequence); it is NOT a rerun of the lost code, and the specific 85.2%/2.3% split is not something this script can confirm or deny -- only the CONCLUSION drawn from it (does a principled honest fill collapse the edge to ~0). It does not, at this definition. Run on blind 2R exit mechanics (`LADDER_MODE=None`), not the shipped ladder-B scale-out, so the exit and fill questions stay separate per the spec's own boundary; `reentry_84_rule` signals are excluded (see script docstring). Whoever revisits this should treat `as_booked` here as the reproducible stand-in for the vault's 'void back-dated fill' and `limit_level` as the reproducible stand-in for its 'honest' one -- not as a byte-for-byte replay of numbers that no longer exist anywhere runnable.
