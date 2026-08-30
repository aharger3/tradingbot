# The order-type grid — what each way of getting in is actually worth

Austin, last night: *"now we're in the backtest and we're gonna start using market
orders limit orders trading with options part of our back test."*

This is the market-order and limit-order half. **Options are not priced here** —
see "What I did not do" at the bottom.

Script: `research/g80_ordertype_grid.py` · data: `research/g80_ordertype_grid.json` ·
book: `research/bt2y_trades.json` (4,508 traded signals, 500 sessions, 25 months).
1R = $1,000.

---

## The answer in one line

**None of the five order types gets you the book's money. The best of them makes
$68 a day and cannot be told apart from zero.** The shipped book's $683–$720 a day
is a price you get by knowing where the minute closed before you buy. Once you have
to actually send an order, one trade a day is worth **$33 to $68** — about **$700 to
$1,400 a month** — and every one of those five numbers has a 95% range that includes
losing money.

The one thing that is *not* ambiguous: **resting a limit order at the level loses
money outright.** Not "less money" — negative, with a range that never touches zero.

---

## The grid — one trade a day

Every row is the same 4,508 setups, the same stops, the same shipped exits. The only
thing that changes is how you get in. Dollars are per trading day across 500 sessions;
the range is a 95% interval built by resampling whole sessions.

| how you get in | days traded | days missed | win rate | **$ / day** | 95% range | months green | weeks green |
|---|---:|---:|---:|---:|---|---:|---:|
| **the book's fill** (control — not obtainable) | 499 | 0 | 64.5% | **$683** | $536 to $835 | 24 / 25 | 85 / 105 |
| **A · resting limit at the level**, stop under the fill bar | 479 | 20 | 19.2% | **−$252** | −$404 to −$89 | 6 / 25 | 35 / 105 |
| **A2 · resting limit at the level**, structural stop kept | 474 | 25 | 11.0% | **−$635** | −$728 to −$528 | 1 / 25 | 11 / 105 |
| **B · market at the signal minute's close** | 499 | 0 | 50.6% | **$48** | −$42 to $141 | 13 / 25 | 57 / 105 |
| **C · market at the next minute's open** | 499 | 0 | 52.4% | **$33** | −$51 to $117 | 12 / 25 | 56 / 105 |
| **D · limit for one bar, then market (chase once)** | 499 | 0 | 52.0% | **$68** | −$26 to $165 | 14 / 25 | 58 / 105 |
| **E · limit at the level, three-bar expiry, no chase** | 467 | 32 | 33.9% | **$46** | −$95 to $197 | 16 / 25 | 49 / 105 |

**B, C, D and E are a four-way tie.** $33 to $68 a day, all four ranges straddle zero,
and the spread between them is far inside this project's standing error bar. Do not
pick a winner out of that block. What separates them from the control is not
ambiguous at all: the control's range starts at $536 and the best of the four tops
out at $197.

## The same grid, taking every signal

| how you get in | fills | no-fills | win rate | mean R | $ / day | worst drawdown |
|---|---:|---:|---:|---:|---:|---:|
| **the book's fill** (control) | 3,821 | 687 | 59.5% | +0.5691 | $4,349 | $12,620 |
| A · resting limit, stop under fill bar | 1,666 | 2,842 | 20.2% | −0.2560 | −$853 | $443,281 |
| A2 · resting limit, structural stop | 1,378 | 3,130 | 12.6% | −0.5931 | −$1,634 | $817,396 |
| B · market at the close | 4,130 | 378 | 45.7% | −0.0098 | −$81 | $123,190 |
| C · market at the next open | 4,092 | 416 | 46.1% | −0.0070 | −$57 | $112,137 |
| D · chase once | 3,889 | 619 | 46.4% | +0.0277 | $215 | $66,127 |
| E · limit, three-bar expiry | 1,330 | 3,178 | 32.9% | +0.0914 | $243 | $33,582 |

Read the win rates, not the mean R. **Every mean-R gap in this table is inside the
project's ±1.5799R error bar, including the control's** — mean R cannot settle
anything here and is printed only because it is the engineering unit. The win rate
and the fill counts can: paying the market drops the win rate from 59.5% to about 46%,
and resting a limit drops it to 20%.

The drawdown column on A and A2 is not a drawdown in the usual sense. Those equity
curves simply go down and never recover, so "worst drawdown" is close to the total
loss.

---

## How often a limit order just misses

This is the part that gets forgotten. A limit that never fills is not a free pass —
the day still has to be traded or given up.

| policy | setups it never filled | share of all 4,508 setups | **days where nothing filled at all** |
|---|---:|---:|---:|
| A · resting limit | 2,842 | 63% | **20 of 499 (4.0%)** |
| A2 · resting limit, structural stop | 3,130 | 69% | **25 of 499 (5.0%)** |
| B · market at the close | 378 | 8.4% | 0 |
| C · market at the next open | 416 | 9.2% | 0 |
| D · chase once | 619 | 14% | 0 |
| E · limit, three-bar expiry | 3,178 | 71% | **32 of 499 (6.4%)** |

The three-bar limit **never gets touched on 3,443 of the 6,170 candidate setups** —
the level simply does not trade again within three minutes of the signal. But it only
loses 32 whole days, because the day usually has another setup behind the first one.
Under the three-bar limit the day's trade is the first candidate only 156 times out of
467; it is the fourth-or-later candidate 147 times. Under the book's fill it is the
first candidate 458 times out of 499.

So the honest cost of a limit order is not mostly "you miss the day". It is **"you end
up trading a different, later, worse setup"**.

The 378–619 no-fills on the *market* policies are not missed orders. They are trades
where the price you pay leaves less than the engine's own minimum stop distance —
nothing to size — explained next.

---

## Why the resting limit loses, and why its raw number is fiction

There is a trap in this measurement and it is worth stating plainly, because the first
run of this rig produced **+$46,525 a day** for the resting limit and that number is
arithmetic, not money.

For the ordinary break-and-retest, **the stop is the level**. `signal_runner.py` sets
`stop = level_hi` and then hands the same price to the fill routine. So an order
resting at the level is an order to buy at your own stop loss. The shipped engine
already has an answer for that — Austin's own, written five times in the recovered
reviews (*"stop loss at the bottom of the wick you entered on"*) — and moves the stop
down to the low of the bar you got filled on. That is `intrabar_stop`, and it is what
policy A uses.

But when the fill happens on a bar whose low is a cent under the level, the stop is a
cent away. With risk fixed at $1,000 a trade, a one-cent stop is a hundred-thousand-share
position and an R-multiple with a one-cent denominator. Across the resting-limit book
the risk distance is a **median 2.3× tighter than the book's, 16× tighter at the 90th
percentile, and 234× tighter at worst**. That is where +$46,525 a day comes from. It is
not a trade anybody could put on.

So every policy in the tables above is filtered by one takeability test, applied
identically to all of them **including the control**: the fill has to sit at least the
engine's own minimum stop distance away — `max($0.10, 0.15% of price)`, the constant
`signal_runner.min_risk_floor` already uses with the comment *"an intrabar fill sitting
on the stop has no trade to size"*. That filter costs the control 687 of its 4,508 rows
and moves it from $720 a day to $683. It costs the resting limit 2,842 rows.

Both versions are in the JSON (`grid_as_specified` and `grid_size_gated`). Only the
gated one should be quoted.

**And the resting limit still loses after all that.** 20.2% win rate, −$252 a day one
trade a day, 6 green months out of 25. The mechanism is clean: the order fills a
median **3 minutes before the signal exists** (5,472 of 5,714 fills are ahead of the
signal bar), which is exactly the head start the earlier work found the book helping
itself to — but you buy it by putting your stop right underneath your entry, and you
get chopped out of four trades in five.

**That is the real result of this pass.** The head start in the book is not obtainable
by resting an order there. You can have the early fill or you can have a stop with room
in it. Not both.

---

## What was actually run

**The harness is the shipped engine, not a rewrite.** Exits come from
`backtest_week._ladder_bar`, called bar by bar exactly the way `simulate_day` calls it;
every stop fill goes through `stop_rule.stop_fill_price` via `backtest_week._stop_fill_px`;
the −1R disaster stop, the break-even move after the first scale, the 2R target and the
end-of-day scratch are the shipped ones because they are the shipped functions. The
minute bars come from the local archive; no network call was made and no request URL
was printed.

**Proof that it reproduces the book.** Re-running the *shipped* fill through this rig
over all 4,508 traded rows gives the **same outcome word on 4,503** and the **same exit
price on 4,488**. The published book's headline numbers come back: 59.4% win taking
everything, mean R +0.5838, $720 a day one trade a day, 25 of 25 months green — against
`DIRECTION.md`'s 59.4% / 0.58 / $721. The residual R difference averages −0.00049R
(≈ 45 cents a trade) and is arithmetic, not a different trade: the book writes entry and
stop rounded to the cent, so the risk denominator this rig divides by is the rounded one.

**Where a resting order is allowed to start.** For break-and-retest, the shipped ordered
state machine is replayed bar by bar and the order may rest from the bar after price
broke the level and left it — the same replay used by the look-ahead check
(`research/g80_lookahead_refute.py`), imported rather than copied so the two reports
cannot drift. That traced 4,903 of 4,920 break-and-retest candidates. For the order-block
and 84% re-entry setups there is no state machine to replay, so the order rests from the
bar after the latest earlier bar whose own high or low *is* the level: 764 of 764 order
blocks, 379 of 486 re-entries. **107 re-entry setups could not be traced at all and are
counted as no-fills, not guessed at.**

**One trade a day is modelled properly.** The day's candidates are walked in signal order
and the first one that *actually fills* is taken. If the first setup's limit is never
touched, the day moves to the second, then the third. A day where nothing fills books $0
and is counted as a missed day.

**Order lifetime.** Resting limits are cancelled at 11:00, which is the engine's own
session end. The one-bar and three-bar limits expire on bar count.

---

## How this fits the two reports before it

It agrees with both and sharpens one of them.

The dollar reconciliation found that paying the signal minute's close gives **$187 a day**
one trade a day on a simple flat-2R exit. This rig, with the same fill and no size gate,
gives **$60 a day** with a 95% range of −$32 to $156. Those two ranges overlap, so they do
not contradict each other — but the gap is real and it has one cause: **the simple 2R exit
survives the honest fill better than the shipped scale-and-runner exit does.** On the book's
own fill the shipped exit is worth 84% of the simple one; on the honest fill it is worth
32% of it. That is worth knowing and is measured nowhere else.

The look-ahead work concluded that a resting order at the level is not the answer, because
on the majority of trades the level never trades in that minute at all, and where it does
the order would already have been filled minutes earlier on a different trade. This pass
prices that conclusion end to end and finds it is worse than "not the answer": the resting
order is **actively negative**, −$252 a day, and the version that keeps the structural stop
is −$635 a day.

---

## What I did not do

- **Options are not priced.** Austin asked for options to be part of the backtest and this
  pass is entry order types only. Everything here is stock-price geometry with risk fixed at
  $1,000. The one existing options read on this book — the same rows as at-the-money 0DTE
  contracts scoring +1.4988R — is quoted in `DIRECTION.md` and was not re-measured or
  re-checked here. **This is the biggest open piece.**
- **No spread, no slippage, no commission.** Every market fill above is the printed close or
  the printed open. A real market order pays the spread on top, so B, C and D are all
  optimistic — and they are already indistinguishable from zero.
- **No engine rebuild.** The trade list is the shipped book's; nothing was re-detected. This
  answers "what are the found trades worth under each order type", not "what would a rebuilt
  engine do".
- **The −1.25R floor is untested in this book.** The bonus finding from the reconciliation
  still stands: not one loss in the book on disk is worse than −1.000R, so the floor has
  never bitten. Every dollar figure here inherits that.
- **The size gate is a modelling choice, disclosed.** It uses the engine's own constant, but
  the shipped engine does not treat it as an absolute veto — a separate promotion lifts some
  sub-floor signals back into the book, which is why the control loses 687 rows to it. Both
  gated and ungated grids are published.

---

## Proposed changes — none applied

1. **Stop quoting $721 a day as the system's expectancy.** It is the value of a fill nobody
   can send. If a single honest headline is wanted, it is **$33 to $68 a day, call it $50,
   with a range that includes zero.**
2. **If an order type has to be chosen today, chase-once (D) is the one to write down** —
   $68 a day, always fills, 14 green months, the smallest drawdown of the market policies.
   But it is a tie with B, C and E and should be labelled as one, not defended.
3. **Do not build the resting-limit path.** It was the recommendation coming out of the
   earlier look-ahead work and it is measured here as a loser twice over.
4. **Re-measure the exit ladder on an honest fill.** The scale-and-runner exit loses two
   thirds of its value when the entry is paid for, and a flat 2R does not. That is a bigger
   lever than any of the five order types and nothing in the project has measured it.
5. **Price options next**, on the honest fill rather than on the book's fill. Every options
   number this project has is sitting on top of an entry price that cannot be obtained.

---

Both repo gates re-run green after this work (`research/regression_gate.py`,
`research/test_runner_stop.py`). No engine file was edited, no mark file was opened,
nothing was committed.
