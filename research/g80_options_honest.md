# Options on honest fills

**Every options number in this repo was priced on an entry you cannot get.** This file
re-prices the two-year book as same-day contracts on the two entry prices you *can* get,
and the short answer is that the instrument does not rescue the strategy and the spread
decides whether it helps at all.

Script: `research/g80_options_honest.py`. Data: `research/g80_options_honest.json`.

```
python research/g80_options_honest.py             # every table below (~4 min, offline)
python research/g80_options_honest.py --selfcheck # the checks this file makes
```

Both repo gates re-run green after this work (`research/regression_gate.py`,
`research/test_runner_stop.py`). Nothing was committed, no judgement file was opened, no
engine file was edited, and no network call was made.

---

## The answer, in dollars

One trade a day, $1,000 of risk a trade, same-day at-the-money contracts, 500 sessions.

| what you pay to get in | contracts | shares | months green |
|---|---:|---:|---|
| **market order at the close of the signal minute** | **$242 – $346 a day** | $187 a day | 20–21 of 25 vs 17 of 25 |
| a limit resting at the level | $670 – $719 a day | $607 a day | 23–24 of 25 vs 23 of 25 |
| *(the published book's own entry — not obtainable)* | *$1,011 a day* | *$860 a day* | *25 of 25 both* |

The range on each honest row is the volatility assumption, and section "the volatility
number was 20% too high" says which end to believe: the lower figure uses the multiplier
this repo inherited, the higher one uses the multiplier that actually matches real option
prints. **Call it about $300 a day, roughly $6,000 a month, on the order type you can
really send.**

Against the last published headline of $721 a day, that is a **59% haircut**, and it is a
haircut on top of the one the fill audit already applied. The money gate — average 2.0R a
trade, which is $2,000 — is not close. The best honest arm books $346 a trade.

Two things about that table before anything else:

- **The limit-at-the-level row is not the better order type. It is a smaller, luckier
  book.** It fills 2,058 of the book's 4,508 trades and misses 20 sessions entirely, and
  the reason it looks good is that it only takes the trades where price came back to the
  level — which is most of the way to knowing the answer. Section "the limit order only
  exists for half the book" is the whole story.
- **Every figure here is before the spread**, and the spread is bigger than the edge.

---

## What "honest fill" means, exactly

Two order types, both computed here from the archived one-minute bars.

**Market at the close of the signal minute.** The confirmation exists when the minute
closes, you send a market order, you pay where the minute ended. Always fillable — it
fills on 4,508 of 4,508 traded rows. This is the honest baseline and it is what the rest
of this file leans on.

**A limit resting at the level.** You put the order out before the signal, at the level
the setup is built on. It fills at the level, and only if that minute actually traded
there: a buy limit fills when the minute's low reaches it, a sell limit when the high
does. No touch, no trade.

**The published fill** is the book's own recorded entry price. It is in every table as
the control, never as an answer. The sibling reconciliation already established that it
hands the trade an average half-R head start before the trade has done anything.

The shares side of this file is not a new simulation. It is the same flat-2R rig the
sibling reconciliation used — same close-triggered stop, same −1.25R floor, same target
on touch — and it reproduces that report's honest-fill figures exactly: **$187 a day one
trade a day, $650 a day taking everything.** That reproduction is asserted in
`--selfcheck`, so if this file ever drifts from that one, the check says so.

---

## The full table

500 sessions, 2024-08-21 to 2026-08-21. Intervals are 95%, resampled over whole trading
sessions (a session with no trade counts as $0 and stays in the draw).

| order type | instrument | trades | win rate | $/day | 95% interval | months green | worst drawdown |
|---|---|---:|---:|---:|---|---:|---:|
| market at close | **contracts, 1/day** | 499 | 41.7% | **$242** | [$86, $402] | 20/25 | $14,997 |
| market at close | shares, 1/day | 499 | 43.1% | $187 | [$54, $322] | 17/25 | $17,925 |
| market at close | contracts, everything | 4,472 | 38.4% | $843 | [$268, $1,421] | 18/25 | $89,792 |
| market at close | shares, everything | 4,508 | 39.2% | $650 | [$149, $1,153] | 17/25 | $71,252 |
| limit at level | contracts, 1/day | 479 | 57.2% | $670 | [$521, $814] | 23/25 | $13,124 |
| limit at level | shares, 1/day | 480 | 57.1% | $607 | [$468, $742] | 23/25 | $11,727 |
| limit at level | contracts, everything | 2,051 | 56.4% | $2,640 | [$2,239, $3,051] | 25/25 | $10,770 |
| limit at level | shares, everything | 2,058 | 56.6% | $2,524 | [$2,154, $2,898] | 25/25 | $10,280 |
| *published fill* | *contracts, 1/day* | *499* | *64.5%* | *$1,011* | *[$860, $1,162]* | *25/25* | *$9,164* |
| *published fill* | *shares, 1/day* | *499* | *64.3%* | *$860* | *[$723, $994]* | *25/25* | *$9,703* |

At the tape-matched volatility (see below) the honest contract rows become **$346 a day**
(market at close, 21/25 green, [$185, $513]) and **$719 a day** (limit at level, 24/25
green, [$568, $865]).

**Win rate is the thing to look at.** Paying the close takes it from 64% to 42%. That is
not the instrument — the shares side moves the same way, 64% to 43% — it is what the
head start was worth. The exit mix moves with it: 2,524 targets and 1,920 stops on the
published fill become **1,685 targets and 2,678 stops** when you pay the close. The
strategy stops out more often than it wins, and it is still positive because the winners
are 2R and the losers are capped.

**Durability survives.** Every month green is the standing bar and the honest arms miss
it — 20 of 25 on the market order, 23 of 25 on the limit order — but the contract is
*better* on that axis than the stock in every arm, never worse.

---

## Do options beat shares?

Yes, in direction, in every arm, on the same trades. **No, by an amount this project's
own error bar cannot see, and the spread is larger than it.**

| order type | volatility | per day, one trade a day | 95% interval | per trade |
|---|---|---:|---|---:|
| market at close | inherited (1.2x) | **+$56** | [+$5, +$104] | +$55 = +0.055R |
| market at close | tape-matched (1.0x) | **+$154** | [+$103, +$205] | +$159 = +0.159R |
| limit at level | inherited (1.2x) | +$61 | [+$37, +$85] | +$67 = +0.067R |
| limit at level | tape-matched (1.0x) | +$110 | [+$84, +$138] | +$119 = +0.119R |
| *published fill* | *inherited* | *+$145* | *[+$115, +$177]* | *+$151 = +0.151R* |

Read that last column, not the interval. **The standing error bar on this project is
±1.5799R per trade. The largest of these differences is 0.159R — a tenth of the bar. On
the project's own standing rule this is a tie, and I am calling it a tie.** The paired
per-day intervals separate from zero, but they are a different and much tighter
statistic: the same trades, paired, resampled over 500 sessions. They say the *direction*
is reliable. They do not license "options are worth $154 a day" as a standalone claim.

So: **roughly $50 to $150 a day, direction reliable, size inside the noise, and about to
be eaten by the spread.**

---

## The spread, and it decides the answer

**Nobody in this repo has ever read a real bid/ask on a same-day contract on these
names.** The data plan does not authorise the options snapshot and the broker session has
never been logged. Everything below is a parameter sweep, and it is the single number
most likely to flip the answer.

Here is why it flips it. For $1,000 of risk the option position is a **median 26
contracts — 2,600 shares of exposure — bought at a wide quote**, while the stock position
is a **median 1,226 shares bought at a penny quote**. The two do not pay the same toll,
and the option pays it on twice the exposure.

Market order at the close, one trade a day, dollars a day after the round trip:

| option round trip | stock round trip | contracts | shares | contracts − shares |
|---|---|---:|---:|---:|
| $0.02 | $0.01 | $162 | $166 | **−$4** |
| **$0.05** | $0.01 | **$44** | $166 | **−$123** |
| $0.10 | $0.01 | −$154 | $166 | −$321 |
| $0.05 | $0.02 | $44 | $147 | −$103 |

At the tape-matched volatility the option side is $265 / $145 / −$56 across the same three
option spreads, so it takes a **two-cent** round trip for the contract to be ahead and a
**ten-cent** one to put it under water outright.

**A nickel round trip is the assumption this repo has been carrying, and at a nickel the
contract loses to the stock by $123 a day.** The whole options case rests on a quote
nobody has looked at. That is the one measurement that would settle this file, and it is
a week of logging, not a modelling job.

---

## The −1.25R floor, on contracts

The floor is written for the stock. On the stock it is doing real work here — every
stop-out in every arm lands at exactly −1.25R or better, worst row −1.25R. **On the
contract it does not exist, and the contract routinely loses more than it.**

| order type | contract rows past −1.25R | worst contract row | worst stock row |
|---|---:|---:|---:|
| market at close | **1,337 of 4,472 (29.9%)** | **−5.93R** | −1.25R |
| limit at level | 565 of 2,051 (27.5%) | −2.52R | −1.25R |
| *published fill* | *1,144 of 4,472 (25.6%)* | *−2.86R* | *−1.25R* |

Nearly a third of trades lose more on the contract than the stock rule says a trade may
lose, and the worst single trade loses **six times its risk** while the stock stop was
never breached by more than a quarter. The mechanism is not slippage: a stop that
triggers on the *stock* does nothing to cap the *option*, and the gap is paid in decay
while the trade waits.

Capping the contract's loss at −1.25R with a real premium stop would **add $457 a day
taking everything and $53 a day one trade a day** on the market-at-close arm. Read that
as an upper bound, not a plan: this calculation caps the loss that was actually booked,
and a live premium stop would also fire on trades whose premium dipped and came back. The
honest statement is that the floor is a lever on the contract, not just a safety rail,
and it has never been priced on the instrument he actually trades.

Position sizes for context: a median 30–48 contracts depending on arm, up to the 200 the
five-cent risk floor allows, with a median **$5,000 to $8,600 of capital at risk** to
carry $1,000 of modelled risk. That is a real financing constraint nobody has stated.

---

## The volatility number was 20% too high

There is one real options tape in this repo: 276 cached one-minute option bars from an
earlier real-contract pass. 214 of them still match rows in the current book.

**Priced the way this repo prices — the prior session's range times 1.2 — the model asks
$0.39 more than the tape printed, on a median real premium of $1.89. It is 33% too
expensive.**

| volatility multiplier | model minus tape, mean | median |
|---|---:|---:|
| 0.8x | −$0.28 | −$0.21 |
| 0.9x | −$0.04 | −$0.09 |
| **1.0x** | **+$0.20** | **+$0.03** |
| 1.1x | +$0.44 | +$0.23 |
| **1.2x (inherited)** | **+$0.68** | **+$0.39** |
| 1.5x | +$1.40 | +$0.88 |

**One times the prior session's range is the multiplier that matches real option prints.
1.2x is not.** That is why every honest arm above carries two numbers, and it is why the
higher one is the better guess.

**And the earlier report that said the model was unbiased was measuring a filtered
sample.** Its scoring filter requires the entry premium minus the modelled stop premium
to be positive; on a real-quoted row the entry premium is the *tape's* and the stop
premium is the *model's*, so that test silently throws away exactly the rows where the
model prices above the tape. **It drops 124 of these 214 rows, and the median error on
the rows it drops is +$0.92.** The conclusion "not measurably biased" was drawn from the
90 rows that happened to agree. That is a real correction to a committed report, it is
reproducible from the same cache file, and it is the reason the volatility multiplier in
this file is quoted two ways instead of one.

---

## The five-cent floor: already fixed, and what is left

The brief warned that the sizer floors the stop premium at five cents but builds the
target off the unfloored number, over-reporting reward by up to 3.8x. **I checked, and
that is fixed in the working tree.** On a case built to make the floor bind — $10 stock,
$1 stop, half-delta — the plan prints a $2,750 max reward and the reward recomputed from
its own premiums is $2,750 exactly. The dollars now come out of one function with one
clamp, and the plan exposes the real ratio (2.778) beside the nominal one (2.5).

My own measurement floors both legs anyway, because it has to: the exit premium is
floored at five cents the same way the stop premium is, since a long option cannot be
worth less than a tick. **It is worth almost nothing here — $843 a day both-floored
against $834 unfloored taking everything, and no difference at all one trade a day. 49 of
4,472 rows exit at the floor.** So the bug was real, it is fixed, and even unfixed it
would not have moved this file's answer.

The one cosmetic thing left is that the plan's printed ratio is the nominal one; the
proposed diff is at the end.

---

## The limit order only exists for half the book

The limit-at-the-level row looks like the best honest arm. It is not an arm — it is a
different, smaller book.

**On 2,448 of the 4,508 traded rows (54.3%) the level *is* the stop.** The engine breaks
a level, waits, and puts the stop back at the level it broke; a limit resting there is a
limit at your own stop and there is no trade to take. On the remaining 2,060 rows the
entry the engine recorded was the level itself, which is exactly why that arm reproduces
so much of the published book's win rate — 57% against 43% on the market order.

The result: **2,058 fills on 480 of 500 sessions**, against 4,508 fills on 499 sessions
for the market order. And the sibling fill audit found the harder problem underneath:
where the level *is* touched, the first touch after the setup arms lands on an earlier
minute on 96.9% of traceable rows — so a genuinely resting order would already have been
filled, minutes before, holding a different position. **This arm is optimistic in timing
by an amount I did not correct for, and the honest reading is that it is an upper bound,
not an order type you can send.** The market-at-close arm is the one to plan on.

---

## Month by month

Market order at the close, one trade a day, contracts against shares, at the inherited
volatility (the more pessimistic of the two).

| month | trades | contracts | shares | green |
|---|---:|---:|---:|---|
| 2024-08 | 8 | −$1,156 | +$1,791 | shares |
| 2024-09 | 20 | +$267 | −$999 | contracts |
| 2024-10 | 23 | +$5,158 | +$2,031 | both |
| 2024-11 | 20 | +$18,164 | +$14,102 | both |
| 2024-12 | 21 | −$5,366 | −$5,165 | neither |
| 2025-01 | 20 | +$118 | −$1,387 | contracts |
| 2025-02 | 19 | +$1,007 | +$260 | both |
| 2025-03 | 21 | +$9,513 | +$5,931 | both |
| 2025-04 | 21 | −$4,897 | −$5,990 | neither |
| 2025-05 | 21 | +$11,718 | +$7,388 | both |
| 2025-06 | 20 | +$777 | −$1,033 | contracts |
| 2025-07 | 22 | +$18,585 | +$12,412 | both |
| 2025-08 | 21 | +$16,901 | +$10,694 | both |
| 2025-09 | 21 | −$10,327 | −$5,242 | neither |
| 2025-10 | 23 | +$1,966 | −$782 | contracts |
| 2025-11 | 19 | +$5,233 | +$3,459 | both |
| 2025-12 | 22 | −$10,062 | −$8,853 | neither |
| 2026-01 | 20 | +$9,454 | +$5,789 | both |
| 2026-02 | 19 | +$2,146 | +$5,032 | both |
| 2026-03 | 22 | +$18,473 | +$15,642 | both |
| 2026-04 | 21 | +$6,430 | +$9,943 | both |
| 2026-05 | 20 | +$3,561 | +$5,454 | both |
| 2026-06 | 21 | +$11,757 | +$11,039 | both |
| 2026-07 | 22 | +$5,571 | +$5,255 | both |
| 2026-08 | 12 | +$5,794 | +$6,111 | both |

Four months are red on both instruments and one is red on the contract alone; four are
green on the contract and red on the stock. **The contract wins the durability count 20
to 17 and it does it by turning small stock losses into small contract gains, not by
laundering the bad months** — December 2025 and September 2025 are worse on the contract,
not better.

---

## What is modelled, and what that costs the answer

**No option price in this file was read from a market.** The underlying bars, the entries,
the stops, the exits and the holding times are all real archived data. Everything with a
dollar sign on the option side is Black-Scholes, priced from the prior session's range.
Specifically:

1. **Volatility.** One number per symbol-day, from the previous session's high-low range.
   Ex-ante by construction — the check that fails the build if the day's own range ever
   enters the pricing path is in `--selfcheck`. There is no volatility surface, no skew,
   no term structure, no crush on the news days.
2. **The contract often did not exist.** These are same-day contracts. The earlier
   real-contract pass found that on roughly three quarters of symbol-days in this window
   there was no daily expiry listed for that name at all — daily expirations rolled out
   gradually across 2024–2026. **A material share of this book is priced on a contract
   that was never listed.** Trading the nearest weekly instead changes the decay framing
   enough that it is a different measurement, not a patch.
3. **The strike is the nearest dollar.** Names on $2.50 or $5 grids would round further
   from the money, so this is the friendly end of the assumption. Pricing perfectly at the
   money instead moves the headline $242 to $246 — it does not matter.
4. **The risk denominator is a counterfactual on every row.** One unit of risk is the
   premium lost when the stock reaches the stop *at that instant*, and no tape holds a
   price for a level the stock was not at. It is modelled everywhere, floored at five
   cents a share, and 112 of 4,472 rows sit on that floor.
5. **No commission, no slippage on size, no financing.** The sizer wants a median 26 and
   up to 200 same-day contracts filled at the mid. Nothing here models what that does to
   the quote.
6. **The exit is a flat 2R target with a close-triggered stop** — deliberately the simple
   control rig, not the shipped scale-out-and-runner machinery, so that the shares side is
   identical to the sibling reconciliation and the only thing that differs between arms is
   the price paid. The shipped exit is more generous; the sibling measured that gap at
   about 1.19x. **Apply that haircut and the honest contract figure is roughly $205 to
   $290 a day** rather than $242 to $346.

---

## What I did not do

- **I did not fetch a single real option quote.** The cached ones are keyed to a
  superseded book and store the option's price at the *published* entry minute and the
  *published* exit minute; both honest arms pay a different price and exit on a different
  minute, so not one of them answers this question. Re-fetching is about 13,000 calls
  across the arms and it was not run.
- **I did not read a real bid/ask.** The spread section is a sweep, and it is the number
  that decides the answer.
- **I did not correct the resting-limit arm for the timing problem** — that the level was
  usually first touched minutes earlier. That arm is an upper bound.
- **I did not rebuild the engine.** These are the trades the engine found, re-priced. A
  rebuild answers a different question and the sibling reports say so too.
- **I did not test the "late by N minutes" order types**, or a marketable limit, or
  anything between the two arms here.
- **I did not touch a single line of shipped code.** Every diff below is proposed, none
  is applied.

---

## Diffs proposed, none applied

1. **`research/t7_real_contracts.py` — the scoring filter selects on agreement.**
   `Contract.ok` requires `raw_risk > 1e-9` where `raw_risk = self.p0 - self.pstop`, and
   on a real-quoted row `p0` is the tape's price while `pstop` is the model's. That test
   drops a row exactly when the model prices above the tape, which is the bias it then
   reports as absent. Fix: compute the calibration on all matched rows, and drop rows for
   a *modelled* denominator only when both legs are modelled. Then re-issue that report's
   "not measurably biased" line — on the full sample it does not hold.

2. **The volatility multiplier should be 1.0, not 1.2.** Every options figure in this
   repo uses `HEADLINE_IV = 1.2`. Against the only real option prints available it is 33%
   too expensive, and 1.0 lands on the median. Fix: change the headline arm to 1.0 and
   keep 1.2 as the pessimistic sensitivity, in `research/t7_real_contracts.py` and
   anywhere downstream that quotes it. This is a published-figure change and it moves the
   honest contract headline from $242 to $346 a day.

3. **`options_sizer.py` — the printed reward:risk is the nominal one.** `rr` prints 2.5
   while `booked_rr` can be 2.78 on the rows where the five-cent floor binds. The dollars
   are correct; only the label is not. Fix: have the card print `booked_rr` as the ratio
   and keep `rr` as the target parameter. One line, cosmetic, and it should be checked
   against whatever reads `plan.rr` first.

4. **Nothing has ever floored the contract's loss.** The stock rule says −1.25R and the
   contract loses past it on 30% of trades, worst −5.93R. This is Austin's decision, not
   the engine's — a premium stop is a different instruction from a stock stop, and it will
   scratch trades the stock stop would have held. It should be put to him as a question,
   with the +$53 a day one-trade-a-day upper bound attached and the caveat that the upper
   bound assumes it never fires early.

5. **Log a week of real same-day option quotes on these names.** Everything above is
   downstream of a bid/ask nobody has looked at. At two cents the contract is level with
   the stock; at ten cents it is $321 a day behind. No amount of further modelling closes
   that.
