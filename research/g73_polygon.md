# G7.3 / polygon — you are right, the book is shares. And the options data is already there.

Austin, 2026-08-29: *"we cant forget that all this data from backtests is shares even though
i payed for polygon options starter plan?"*

Right on both halves, and there is a third thing you did not ask that costs you money.

Scripts, both re-runnable, neither touches a mark file or the book:
`research/g73_polygon_fetch.py` (pulls and caches the real option bars; `--probe` runs the
six-call entitlement test in about two minutes) and `research/g73_polygon_reprice.py`
(read-only — it cannot make an API call and asserts that).

---

## The three sentences

1. **Real option prices for your own trades are already downloadable with the key in your
   `.env`** — actual 1-minute bars for the actual contracts, expired ones included, two
   years back. Nobody in this repo had ever asked for them. Every option price ever
   published here was produced by a formula.
2. **But that key is not on the Options Starter plan you think you are paying for.** It
   behaves exactly like Polygon's **free** tier, on options *and* on stocks: five calls a
   minute, two years of history, no snapshots. Starter is unlimited calls, and five years
   on stocks. **Go look at your billing.** Either $29 a month is buying you nothing, or the
   plan lapsed and nobody noticed.
3. **The $80 ThetaData subscription is not redundant, but it is no longer urgent.** Polygon
   gives you the option's *price*. ThetaData gives you the option's *spread*, and on the
   numbers below the spread is the only thing that decides the answer.

---

## 1. What the key actually grants — measured, not read off a web page

`python research/g73_polygon_fetch.py --probe`

| what I asked for | answer |
|---|---|
| 1-minute bars for an **expired** contract (`O:NVDA250613C00141000`, 13 Jun 2025) | **200 OK — 363 real minute bars** |
| the list of every contract **listed on a past date**, expired included | **200 OK** |
| daily open/high/low/close for that expired contract | **200 OK** |
| bid/ask — the NBBO quote tape | **403 not entitled** |
| the trade tape (every print) | **403 not entitled** |
| snapshot / greeks / IV / open interest | **403 not entitled** |
| 1-second bars | **403 not entitled** |
| anything before **2024-08-29** | **403 "your plan doesn't include this data timeframe"** |

Two things fall straight out of that table.

**The repo wrote options off on the strength of one wrong test.** Three separate documents —
`research/t2_options_tape.md` §A5, `research/t9_spread-and-tight-rr.md`, and this morning's
`research/g71_instrument.md` — say "Polygon options 403s on this key" and conclude there is
no options tape. All three tested the **snapshot** endpoint, which is the one options
endpoint the free tier does not carry. The *historical bars* endpoint, which is the one a
backtest actually needs, has been open the whole time. `g71_instrument.md` states as fact:
*"There is no options tape in this repo. Every option price ever published here is
Black-Scholes on Parkinson range vol."* The first half was true. The second half was
avoidable.

**The two-year window is exactly two years, and it rolls.** The first authorised day today
is **2024-08-29**, found by bisection. Your book starts 2024-08-21, so its first five
trading days are already outside the window, and one more falls off every morning. Whatever
you pull, pull it into the cache and keep it.

---

## 2. You are probably not on the plan you think you are

This is the part that is about your money rather than the strategy.

| | free **Basic** | **Starter** $29/mo | what your key does |
|---|---|---|---|
| API calls | 5 / minute | unlimited | **5 / minute** (measured: five succeed, the sixth is a 429) |
| options history | 2 years | 2 years | 2 years |
| **stocks** history | 2 years | **5 years** | **2 years** (a stock minute bar from 2024-06-13 is a 403) |
| minute bars | yes | yes | **yes** |
| snapshot, greeks/IV, open interest | no | **yes** | **no — 403** |
| 1-second bars | no | **yes** | **no — 403** |

Every row matches free Basic and none matches Starter. Meanwhile `polygon_feed.py` line 35
still carries the comment *"Stocks Starter (2026-07-08): unlimited calls, no rate cap"* with
the throttle deliberately switched off underneath it. That was true when it was written. It
is not true now.

Two consequences worth knowing:

- Anything that re-pulls bars is now silently about twelve times slower than the code
  assumes, and `_throttle()` is a no-op, so a bulk re-pull will 429 rather than wait.
- `data_archive/` holds 16,817 cached symbol-days, many from before 2024-08-29. **Those
  cannot be re-downloaded on this key any more.** If that folder is lost, the early part of
  the two-year book is not reproducible. Back it up.

Polygon rebranded to `massive.com` this year, which is a plausible way for a subscription to
change underneath you quietly. I cannot see your billing page; you can.

---

## 3. Can the two-year book be re-priced as options, for free? Yes.

That was the decisive question and the answer is yes, with one honest gap.

**What the free tier gives you is enough to price a trade.** For any trade in the book you
can look up which contracts were listed that day, pick the one a robot would buy (nearest
expiry on or after the trade, strike nearest the entry), and read that contract's real
traded price at the entry minute and at the exit minute. A real entry, a real exit, on a
real contract.

**What is missing is the bid and the ask.** Minute bars are *traded prices*, not quotes. So
this tells you what the contract was worth; it cannot tell you what it would have cost to
get in and out. That gap is exactly ThetaData's job (§5).

**One thing is unavoidably modelled: how many contracts to buy.** Risking $1,000 means
sizing off "what would this contract be worth if the stock hit my stop", and the stock
usually never went there, so no tape can contain that price. The repo's live sizer
(`options_sizer.py`) fills that hole with a flat guess, `DEFAULT_DELTA = 0.5`. Here it is
replaced by a number measured off the same real tape: fit the contract's price against the
stock's price over the minutes **before** the entry, and use that slope. No bar at or after
the entry minute is used, so it cannot see the future — which is the exact mistake that got
`research/t2_options_tape.md` retracted this morning.

### The re-priced result

`python research/g73_polygon_fetch.py` then `python research/g73_polygon_reprice.py`.
**COIN, TSLA and PLTR — the three most-traded names in the book — 213 trades sampled evenly
across all eight quarters, 212 of them matched to a real contract with a real tape (99.5%),
204 fully priced, 162 sessions, 2024-08-29 to 2026-07-31.**

The sample is not a flattering slice: on the book's own numbers those 204 rows make **+$565
a trade**, against **+$554** for the 213-row sample and **+$500** for all 819 traded rows in
these three names. Win rates 38.7% / 38.5% / 39.2%.

**Both instruments are priced off the same two minute closes** — the minute you entered and
the minute you exited. That matters. Your backtest fills the *stock* at a limit price inside
the bar the order was sitting in, and an option minute bar has no limit fill in it. Charging
the option for a head start the stock was handed is how you get a fake answer, so here both
sides pay the close. Doing it honestly costs the stock arm $585 a trade — the same optimism
`research/x9` already measured at −0.6653R.

| per trade, 204 trades | dollars | win rate |
|---|---:|---:|
| **shares**, at the minute close | **−$20** | 38.2% |
| **options**, real contract, real price, mid | **+$56** | 39.2% |
| options + tastytrade commissions | −$7 | 39.2% |
| options + commissions + a $0.02 round-trip spread | −$108 | 38.7% |
| options + commissions + a $0.05 round-trip spread | −$260 | 37.7% |

| dollars a day, these three names, 162 sessions | |
|---|---:|
| shares | **−$26 / day** |
| options, mid, no costs | **+$70 / day** |
| options + commissions | −$9 / day |
| options + commissions + $0.02 spread | −$136 / day |
| options + commissions + $0.05 spread | −$327 / day |

**The verdict — paired, and resampled ten thousand times on the same rows:**

| options minus shares | per trade | 95% band | |
|---|---:|---|---|
| at the mid, no costs | +$76 | −$73 to +$229 | inside the noise |
| + commissions | +$13 | −$136 to +$167 | inside the noise |
| + commissions + $0.02 spread | −$88 | −$237 to +$68 | inside the noise |
| + commissions + $0.05 spread | **−$239** | **−$395 to −$84** | **real — options lose** |

**On real prices the option is worth nothing over the stock before costs, and it is
measurably worse once the spread is a nickel.** That is the same conclusion
`research/t7_real_contracts.md` reached with a formula (+0.0941R against a ±0.1298R bar),
now confirmed on actual traded contract prices rather than Black-Scholes. `DIRECTION.md:45`
still tells a reader the instrument is worth +1.4988R. It is worth nothing, and this is the
second independent measurement saying so.

And notice which line decides it. Everything turns on the spread — the one number this data
cannot give you. That is exactly where the $80 goes.

---

## 4. Three things the tape says that no formula in this repo could

**1. You cannot buy 0DTE on these names most days, and the whole repo assumes you can.**
Only **23% of the 204 trades** could buy a same-day expiry. The rest bought 1, 2, 3 or 4
days out, because single stocks list weekly expirations and your 09:30–11:00 window is
usually not a Friday. Every options number ever published in this project — `t2`, `t7`,
`t8`, `t9`, `g71`, `g72` — priced a 0DTE ATM contract on **every** row. That contract did
not exist on three days out of four.

| what it could actually buy | share of trades |
|---|---:|
| 0 days to expiry (same-day) | 23.0% |
| 1 day | 24.5% |
| 2 days | 17.6% |
| 3 days | 20.1% |
| 4 days | 14.7% |

**2. Risking $1,000 ties up $16,220, not $8,000.** To lose exactly $1,000 when the stock
reaches your stop, the median trade needs **41 contracts at $4.18** — a **$16,220 cash
debit**. `g71_instrument.md` modelled that debit at $8,068 using a 0DTE contract that mostly
was not listed. The real number is **twice** it. Options are still far cheaper than shares —
the same trade needs roughly $109,000 of buying power as stock — but the gap is about 6.7x,
not 13x, and $16,000 committed to make a $1,000 bet is worth looking at squarely.

**3. The contract is thinner than the code thinks.** `options_sizer.py` ships
`DEFAULT_DELTA = 0.5` as a flat constant. Measured against the real tape, minute by minute,
the median is **0.42**. Sizing off 0.5 under-buys by about 16%, so the live sizer is risking
roughly $840 where it believes it is risking $1,000. Small, real, and free to fix now that
the number is measurable. **Not applied** — it moves a live sizing constant, which is yours
to say yes to.

---

## 5. Is the $80 ThetaData subscription still needed?

**Not redundant. Not urgent either. Do not buy it this month.**

`research/g71_instrument.md` recommended it this morning to close five open questions. Free
Polygon closes two of them outright and leaves three open.

| the open question | closed by free Polygon? |
|---|---|
| **the 72.8% of rows that could not be matched to a real contract** — Alpaca only lists *live* contracts, so three-quarters of the book was priced against a strike nobody could confirm existed | **CLOSED. 99.5% matched here** — the listing history for any past date is a 200, expired contracts included |
| **the IV level and the Parkinson-vol proxy** — every premium in this repo is a formula output | **CLOSED for price.** You no longer model the premium, you read it |
| **the round-trip spread** — a swept parameter in four documents, never once observed | **OPEN.** Bars are traded prices. No bid, no ask |
| **was there size at the offer** — the median trade wants 41 contracts | **OPEN.** Quote size ships with the quote |
| **IV crush on news days** | **OPEN.** Needs the quote tape |

The spread is not a detail — it is the whole answer. Look at the table in §3 again: at the
mid the option wins by $76 and that is noise; at two cents it loses $88 and that is still
noise; at five cents it loses $239 and **that clears its error bar**. The entire question
"should this robot trade options or shares" now rests on one number nobody has ever
observed. `g71_instrument.md` measured that this book dies at a **$0.075 round-trip option
spread** — a nickel and a half — against $0.156 on shares. That question is worth $80 and it
stays worth $80.

**But the order changed.** Before today ThetaData was the only way to learn anything at all
about options. Now it is the second question rather than the first, and it is a sharper
question than it was this morning: not "what is an option worth" — you can read that for
free — but "is the spread under five cents". One month, one measurement, then cancel.

Polygon's own paid tiers are the wrong way to buy that: quotes start at **Options Advanced,
$199/month**, two and a half times ThetaData's price for the same job.

**What the $29 Starter would buy, if you are being charged for it anyway:** speed. At five
calls a minute this 204-trade proof took about ninety minutes of paced downloading; all
4,508 trades in the book would take roughly a day. On unlimited calls it is about twenty
minutes. It buys nothing this analysis needed and it does not close a single question above.

---

## 6. What I did not do

- **No engine file was touched.** The four tests you named — `regression_gate`,
  `test_universe_single_source`, `t11_stop_fill_fix`, `test_runner_stop` — were run after
  these files were added, and all four exit 0.
- **No mark file was read, written or moved**, including this morning's
  `probe_g71_homework_s3_2026-08-29.jsonl`.
- **Nothing was bought and no call cost anything.** Polygon's plans are flat monthly; API
  calls are not metered. The whole exercise ran on the key already in `.env`.
- **This is 204 trades on three symbols, not the book.** The pull is cached and resumable —
  finishing it costs time, not money. `research/g73_polygon_cache/` holds every bar already
  fetched, so a re-run of the re-pricing is free and instant.
- **The −$1.25R floor on the premium side was not resolved.** `g71_instrument.md` flags it
  as a live-money hole: your stop triggers on the *stock*, and nothing caps what the
  *contract* loses while that happens. The tape can now answer it, but answering it properly
  needs the stop-out rows priced on the book's own fills, not minute closes, and that is a
  separate ticket.
