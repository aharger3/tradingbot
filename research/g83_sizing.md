# The six-figure sizing page — what risk per trade reaches $397 a day

**The bar, ratified 2026-08-30:** $100,000 a year ÷ 252 sessions = **$397 a day** =
**$8,333 a month**. Every number below states its distance to that line.

Script: `research/g83_sizing.py` · data: `research/g83_sizing.json`,
`research/g83_series.json` · book: `research/bt2y_trades.json` (4,508 traded signals,
500 sessions, 25 months). 1R = $1,000.

```
python research/g83_sizing.py             # every table here (~4 min, offline)
python research/g83_sizing.py --selfcheck # the three claims this page rests on
```

---

## The answer, in the first line

**No. Six figures a year is not reachable on the current engine — not at any risk
size — and the thing that stops it is not the money, it is the green months.**

The money part is closer than expected. On the honest fill, one trade a day, same-day
at-the-money contracts before any spread make **$346 a day at $1,000 of risk**. That is
**87% of the bar**. Raise risk to **$1,148 a trade** and the arithmetic lands on $397 a
day exactly.

But that same policy is **green in 21 of 25 months, and it is green in 21 of 25 months at
every risk size**, because multiplying every day of a month by a positive constant cannot
change the sign of the month's total. **Sizing cannot buy durability.** He ratified
tonight that green months win when gates conflict, so this is a fail, not a trade-off.

**And the biggest 25-of-25-preserving risk number is $0.** Not "small" — there isn't one.
No honest-fill instrument in this book holds 25 of 25 green months at any size. The only
arms that do are the published-fill controls, and that fill is a price nobody can send.

---

## The three instruments, side by side

One trade a day, honest fill (market order paid at the close of the signal minute),
$1,000 of risk, 500 sessions. Every dollar figure scales linearly with risk.

| instrument | days it traded | **$ / day at $1k risk** | 95% range | **% of the $397 bar** | **risk that reaches $397** | **green months** |
|---|---:|---:|---|---:|---:|---:|
| **options** — same-day ATM contracts, *before spread* | 499 | **$346** | $180 to $508 | **87%** | **$1,148** | **21 / 25** |
| **shares** — after a penny round trip | 499 | **$167** | $33 to $304 | **42%** | **$2,382** | **16 / 25** |
| **options** — after a nickel round trip | 499 | **$145** | −$20 to $310 | **37%** | **$2,738** | **15 / 25** |
| **index futures** — SPY/QQQ/IWM setups only | 230 | **$51** | −$42 to $143 | **13%** | **$7,819** | **13 / 25** |
| *published fill, shares — control, not obtainable* | *499* | *$830* | *$696 to $963* | *209%* | *$478* | *25 / 25* |
| *published fill, contracts — control, not obtainable* | *499* | *$806* | *$649 to $959* | *203%* | *$492* | *25 / 25* |

Two rows in that table are worth sitting with.

**The control clears the bar twice over and the honest fill does not clear it at all.**
$830 a day against $167 a day, on the same 499 trades, same stops, same exits. The whole
difference is the price you are assumed to pay to get in. Sizing this page on the control
would have told him six figures needs $478 of risk a trade and is comfortably done. It is
not done.

**Index futures are a different, much worse business.** They are not 30% worse — they are
a quarter of the shares number, and they only trade on **230 of 500 sessions** because
NVDA, TSLA, PLTR and the rest have no future to trade. Half his days disappear. That
confirms what the earlier prop-firm work concluded from a different direction.

---

## 1 · What risk per trade reaches $397 a day

Risk per trade is a fixed dollar amount, so dollars are exactly linear in it:
`$/day(risk) = (risk / 1000) × $/day(at $1,000)`. The risk that reaches the bar is a
division, not a search.

| instrument | risk per trade for $397/day | that is | position it implies |
|---|---:|---|---|
| options, before spread | **$1,148** | 1.15× the current unit | median ~30 contracts, ~$4,200 of premium |
| shares, after a penny | **$2,382** | 2.4× | median **$492,000 of stock**, see below |
| options, after a nickel | **$2,738** | 2.7× | median ~71 contracts, ~$10,000 of premium |
| index futures | **$7,819** | 7.8× | and it only trades 46% of sessions |

**The shares number is not fundable and nobody had said so.** At $1,000 of risk the median
share position is **$206,632 of stock** — the stops are that tight. At the $2,382 it takes
to reach the bar, the median position is about **$492,000**, and the 90th percentile is
over **$1 million**. Austin has said *"i dont have money just credit line."* The shares
route to six figures needs a half-million-dollar day-trading account, which is why the
option is the instrument he actually trades: the same $1,000 of risk is carried on a
median **$3,652** of premium. That is a 56× difference in capital and it has never been
stated in this repo.

---

## 2 · Blowing the account, and passing a prop challenge

### Blowing the account

Probability that equity falls 50% below where it started, inside one year (252 sessions),
i.i.d. bootstrap of the day series, 20,000 paths.

| account | shares @ $1k | shares @ $2,382 | options @ $1k | options @ $2,738 | index @ $1k | index @ $7,819 |
|---|---:|---:|---:|---:|---:|---:|
| $25,000 | 15% | **43%** | 31% | **63%** | 20% | **78%** |
| $50,000 | 2% | **20%** | 10% | **42%** | 3% | **66%** |
| $100,000 | 0.0% | 4% | 0.5% | **18%** | 0.0% | **44%** |
| $250,000 | 0.0% | 0.0% | 0.0% | 1% | 0.0% | 12% |

Read the shape, not the decimals. **Sizing up to reach $397 a day moves the ruin
probability from single digits to something between a fifth and four fifths**, and on
index futures it is a coin flip on a $100,000 account. The safe columns are the ones that
do not make the money.

There is no account size on that table where the index-futures route both reaches $397 a
day and has a ruin probability anyone would sign. On a $250,000 account it is 12% — one
year in eight ends with half the account gone, for a strategy that is green in 13 months
out of 25.

### Passing a prop challenge

Same bootstrap path walker as `research/g71_propfirm_sim.py` — imported, not rewritten —
with the honest day series substituted for the published one. Futures firms take index
futures only; Trade The Pool takes shares; **no prop firm on the challenge model allows
options at all** (`research/g71_propfirm.md` §0).

**Not one firm on the board has a ≥90% pass band on the honest fill. Not one, at any risk
level on the grid.** The earlier prop work found comfortable bands; those were computed on
the published fill.

| firm | ≥90% band | best pass rate on the whole grid | pass rate at the $397 risk |
|---|---|---:|---:|
| Earn2Trade TCP 25K (futures) | **none** | 79.7% | 78.7% |
| Topstep 50K Combine (futures) | **none** | 65.4% | 64.1% |
| Apex 50K Eval (futures) | **none** | 55.5% | 40.6% |
| Topstep 150K Combine (futures) | **none** | 35.2% | 65.0% |
| TTP 25K MAX day (shares) | **none** | 82.5% | 81.6% |
| TTP 100K MAX day (shares) | **none** | 81.2% | 80.1% |
| TTP 200K MAX day (shares) | **none** | 74.7% | 69.3% |
| TTP 100K FLEX day (shares) | **none** | 71.5% | 59.1% |

The best number on the board is **82.5%** — Trade The Pool's 25K MAX account on shares.
That means roughly **one attempt in six fails**, and each attempt costs the evaluation fee.
It is not hopeless; it is not the ≥90% the earlier work was written against.

**Do not read "months to pass" as good news.** The best-risk column passes in a median of
1 to 4 sessions, and that is exactly why it only passes two thirds of the time: at $2,750
of risk against a $3,000 target, **one good day funds you and one bad day ends you**. The
median is short because the distribution is bimodal, not because the challenge is easy.

---

## 3 · Does it keep 25 of 25 green months? No — and sizing cannot fix it

He ratified tonight that **green months win** when gates conflict. So this section
overrides section 1.

**Green months are scale-invariant.** Risk is a fixed dollar amount per trade, so every
day of a month gets multiplied by the same positive constant, and the sign of the month's
total cannot change. A policy green in 21 of 25 months at $1,000 a trade is green in 21 of
25 months at $100 a trade and at $10,000 a trade. `--selfcheck` asserts this numerically
on all three instruments at 0.25×, 3× and 17.5×.

| instrument | green months, at **every** risk size | durability |
|---|---:|---|
| options, before spread | 21 / 25 | **FAIL** |
| shares, after a penny | 16 / 25 | **FAIL** |
| options, after a nickel | 15 / 25 | **FAIL** |
| index futures | 13 / 25 | **FAIL** |
| *published fill (control)* | *25 / 25* | *met — on a fill nobody can send* |

**The biggest 25-of-25-preserving risk number, as asked for, is $0.** There is no honest
policy in this book that is 25 of 25 at any size, so there is nothing to preserve. The
answer to "what is the biggest number that keeps durability" is that durability is already
gone before sizing is asked about, and sizing is the wrong knob for it. Selection is.

---

## 4 · Green weeks, green months, drawdown, months to funded

Bootstrapped over the day series, 20,000 draws. A five-session block is used for "week".

| instrument | P(green week) | P(green month) | P(green year) | worst drawdown @ $1k | worst drawdown at the $397 risk |
|---|---:|---:|---:|---:|---:|
| options, before spread | 67% | **79%** | 100% | $13,399 | **$15,378** |
| shares, after a penny | 68% | 70% | 96% | $19,365 | **$46,123** |
| options, after a nickel | 59% | 63% | 89% | $22,896 | **$62,695** |
| index futures | 48% | 57% | 78% | $17,646 | **$137,967** |
| *published fill, shares* | *94%* | *99%* | *100%* | *$10,295* | *$4,923* |

**A coin flip on the week, and one month in three or four red.** That is what living on
this engine feels like, and it is the honest version of a system whose committed headline
said 25 of 25.

The drawdown column on the right is the one to take to a broker. **$46,000 of drawdown to
make $100,000 a year on shares. $138,000 of drawdown to make $100,000 a year on index
futures** — more than the year's target, on a $100,000 account it is a wipeout twice over.

**Months to funded** (median over paths that pass, at the best risk): 1 to 4 sessions on
the futures accounts, 1 to 5 on the stock accounts, with the pass rates in section 2. The
long pole is not the time. It is that a fifth to two thirds of attempts never get there.

---

## 5 · The spread is what decides the options answer

This is the number most likely to flip this page, and **nobody in this repo has ever read
a real bid/ask on a same-day contract on these names.** It is a parameter sweep, not a
measurement.

| option round trip | $ / day at $1k | % of the $397 bar | risk that reaches $397 | green months |
|---|---:|---:|---:|---:|
| $0.00 (no spread — fiction) | $346 | 87% | $1,148 | 21 / 25 |
| **$0.01** | **$306** | **77%** | **$1,299** | 21 / 25 |
| **$0.02** | **$265** | **67%** | **$1,495** | 18 / 25 |
| $0.03 | $225 | 57% | $1,762 | 17 / 25 |
| **$0.05** (what the repo has been assuming) | **$145** | **37%** | **$2,738** | 15 / 25 |
| $0.10 | **−$56** | **−14%** | **never** | 11 / 25 |

**At a dime round trip the options route is negative and no amount of risk reaches
$397 a day, because scaling a loss up only loses faster.** At a nickel it needs 2.7× the
risk and is green 15 months in 25. At two cents it is a real business at 1.5× risk.

The gap between "a real business" and "unreachable" is **eight cents of quoted spread**,
and it is unmeasured. **That is the single most valuable week of work available in this
project right now** — log the broker's quotes on the names he actually trades for a week
and this page collapses from a range into a number.

---

## What I actually ran, and what reproduces

The rig is `research/g80_options_honest.py`, **imported rather than re-implemented** — its
`build_many()` prices every traded row as both a stock position and a same-day at-the-money
contract off the archived one-minute bars, its `first_takeable_per_day()` does the
one-trade-a-day walk, and stop fills route through `stop_rule.stop_fill_price`. No network
call was made. `research/g71_propfirm_sim.py` is imported for the challenge specs and the
path walker.

`--selfcheck` passes and asserts three things rather than assuming them:

- **green months are scale-invariant** on all three instruments, checked at 0.25×, 3×, 17.5×
- **shares reproduce $187/day** and **options at 1.0× vol reproduce $346/day** — the two
  published figures in `research/g80_options_honest.md`
- **dollars are linear in risk per trade**

The spread sweep independently reproduces that file's published **$265 a day at a two-cent
round trip** and **$145 at a nickel**, to the dollar.

Both repo gates re-run green (`research/regression_gate.py`, `research/test_runner_stop.py`).
No engine file was edited, no mark file was opened, nothing was committed or pushed.

---

## What I did not do, and where this page could be wrong

1. **There are two honest-fill answers for shares and they differ by 3.5×, and this page
   used the generous one.** On the flat-2R exit rig used here, paying the signal minute's
   close is worth **$187 a day**. On the *shipped* scale-and-runner exit
   (`research/g80_ordertype_grid.md`, size-gated) the same fill is worth **$48 a day** and
   the best order type of five is **$68**. Both are measured, neither is wrong, and the
   difference is the exit ladder: the shipped exit keeps 84% of its value on the book's
   fill and only 32% of it on an honest one. **If the shipped exit is what he actually
   trades, every dollar number on this page is roughly a quarter of what it says, and the
   answer moves from "close but not durable" to "not close".** That re-measurement is the
   biggest open item and it is named as a recommendation in that file too.
2. **The resting-limit order type is not on this page, because the two reports that
   measured it disagree in sign** — `g80_options_honest.md` reads it at +$607 a day on
   shares, `g80_ordertype_grid.md` reads it at −$252 a day. They differ in exit ladder,
   stop handling and size gating. A sizing page must not average a contradiction, so this
   one uses only the market-at-close arm, where both reports agree.
3. **Index futures are modelled as the SPY/QQQ/IWM stock geometry, not as MES/MNQ/M2K.**
   Contract granularity, the tick size, and the overnight margin are not modelled. At
   $7,819 of risk the position is large enough that granularity rounds to nothing, but the
   futures row should be read as "the index setups, priced like stock", not as a futures
   backtest.
4. **Slippage beyond the quoted round trip is not charged**, on any instrument. Every
   market fill is the printed close.
5. **No compounding.** Risk is a fixed dollar amount throughout, which is what makes the
   linearity and the scale-invariance exact. A percentage-of-equity sizing would change the
   ruin numbers and not the green-month verdict.
6. **The −1.25R floor does not exist on the contract.** 1,337 of 4,472 option rows lose
   more than the stock rule says a trade may lose, worst −5.93R. Capping the premium at
   −1.25R with a real stop is worth about +$53 a day one trade a day — a lever on the
   instrument he actually trades that has never been priced properly.

---

## What this page recommends

1. **Stop sizing and start selecting.** The gap is not a sizing gap. At $1,000 of risk the
   best honest instrument makes 87% of the bar; the reason six figures fails is 21 green
   months out of 25, and no risk number touches that. Four red months is a selection
   problem.
2. **Log the option quotes for one week.** Eight cents of spread separates "a real
   business at 1.5× risk" from "negative at any risk". It is the cheapest decisive
   measurement left in the project.
3. **Re-measure the exit ladder on the honest fill** before believing any number on this
   page. If the shipped scale-and-runner is what he trades, this page is 4× optimistic.
4. **Drop index futures from the plan unless a prop seat is the point.** A quarter of the
   money, half the trading days, 13 green months in 25, and $138,000 of drawdown to reach
   the target. It exists only because prop firms will not fund options.
5. **If a prop seat is wanted, Trade The Pool 25K MAX on shares is the best square on the
   board** — 82% pass at the risk that targets $397/day. That is the honest best, and it is
   below the 90% the earlier work was written against.
