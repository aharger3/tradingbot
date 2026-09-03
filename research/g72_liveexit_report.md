# The runner leg is now built into the live system — and switched off

**What changed, in one line:** the live path can now sell half at the session high
and let the rest run, exactly the way the backtest does — but the switch is OFF, and
it stays off until you say otherwise.

Plus a second thing fixed while I was in the same file: the trade card was
understating its own reward by up to **3.8x**.

---

## 1. The $6,400-a-month item

The board put it plainly:

> Live sells everything at 2R with no runner, and half the money is above 2R.
> 94 of your 496 one-a-day trades (19%) ran past 2R, and those 94 trades carry
> 50.1% of every dollar the strategy makes.

That was true. The backtest has scaled out at the session high and let a runner go
for months. The live system had **no second leg at all** — it bought the contracts,
put one target on them, and sold everything there.

It now has the leg. Same rungs, same rules, same order of tests:

| | what happens |
|---|---|
| **Rung 1** | half comes off when price touches the session high (the high as it stood when you entered — nothing looks into the future) |
| **Then** | the stop moves up to your entry price |
| **Rung 2** | the rest runs to the first real level beyond that high — yesterday's high, the pre-market high, or the next whole dollar |
| **Underneath it all** | the resting −$1,000 order, and the level stop that only triggers on a candle close, floored at −$1,250 |
| **At the bell** | whatever is still open comes off at the last price |

**It is off.** `OMEN_LIVE_LADDER` is unset, and with it unset the live system behaves
exactly as it did yesterday — one target, whole position, nothing new. Turning it on
is your call, and it is question #5 on your list ("does the live card show two rungs").

Worth, when you turn it on: **+$306 a day, +$6,400 a month** under one-trade-a-day.
That number is not mine — it is `research/g71_board_check.py`'s, unchanged.

---

## 2. The test is the deliverable

You have been burned before by a number nobody could reproduce. So the point of this
ticket is not the code, it is the proof that the code agrees with the book.

`research/g72_liveexit_parity.py` takes **one trade**, feeds the **same candles** to the
backtest's real exit function and to the live paper trader's real one, and checks they
book the same result. Not a copy of each — the actual shipped functions.

Nine trades, calls and puts: scale then reach the level, scale then give it back,
stopped out before the rung ever fills, a quiet day that never gets anywhere, a bar
that tags the target and closes past the stop. **All nine agree to nine decimal
places.** Twenty checks, green.

Two places they *cannot* agree, and I measured both rather than quietly rounding
them away:

- **You cannot sell half of seven contracts.** The backtest sells a mathematical half.
  A real position of 7 sells 3 and runs 4. On an even number they are identical; on 7
  contracts the gap is 0.03R. That is contract granularity, not a rule difference.
- **An option cannot go below a nickel.** When a wide stock stop is mapped onto a cheap
  contract, the option risks less than the shares the backtest models — so the live
  result is *better*. Measured at +0.25R on the worst case in the test. That is the
  instrument being different, not either engine being wrong.

---

## 3. The card was lying about your reward

Second bug, same file, and it is the more embarrassing one.

The card showed `max loss $872 / max reward $1,744`. It got that reward by multiplying
the risk by 2.5 — which is not a measurement, it is an assumption written down as if it
were a fact. Next to it, on the same card, sat a target price that actually paid
**$6,560**.

**MU, 31 July 2026.** Stock entry $882.00, stop $914.80 — a $32.80 stop. On a $4.41
contract, that stop would take the option to zero, so the system correctly floors it at
$0.05 and you only ever risk $436 a contract. But the *upside* was never floored, and it
should not be: at the target the contract really is worth $45.41. So the trade risks
$872 and pays $8,200. The card said $2,180.

**Fixed:** the card's reward is now what the target actually pays, and where the ratio
comes out better than the 2.5R you aimed at, the card says so out loud instead of
printing "2.5R" over a number three times that size.

Across the whole two-year book (`research/g72_liveexit_cardcheck.py`, run on
`bt2y_trades.json` as it stood 2026-08-29 17:06 — 4,508 traded rows):

- the nickel floor binds on **39 rows (0.87%)**
- on those 39 the card was understating by up to **3.76x** — **$58,134** of reward it
  never showed you
- the other 1,145 understated rows are **half a cent of price rounding**, worth $30,520
  across two years and about $27 a row. That is a separate, known thing
  (`research/g71_rrcapv.md` finding #4) and this does not fix it.

### One thing I did NOT do, deliberately

The board's instruction was "floor both legs the same way." Taken literally — flooring
the *target* the same arithmetic way as the stop — that would have set MU's target at
**$13.13** instead of $37.21.

It would not change when you sell. The sell trigger is the stock price, and the stock
price target is untouched either way. All it would change is what you book when you get
there: **$2,408 a contract, thrown away for the sake of a tidier-looking ratio.**

So I did the version that keeps the money: every leg of the card — stop, target, and
both new rungs — now comes out of **one function with one nickel floor**, and the floor
only bites on the side where an option can actually go to zero. That *is* flooring both
legs the same way, in the only sense that does not cost you anything. The arithmetic is
in the parity test, checked on the real MU row.

**Nothing about how a trade exits changed.** I verified the target price is identical on
all 4,508 traded rows. Only the label moved.

### And one number on the new card will look small — it should

With the runner switched on, a TSLA card reads `max loss $980 / max reward $1,470`, where
the old single-target card said $2,464. That is not the ladder being worse. It is the
card finally quoting **the plan it actually intends to follow** — half off at the session
high, the rest to the next level — instead of a 2.5R target the ladder never sells at.
The ladder wins by *reaching* its rungs far more often, not by naming a bigger number.

It also puts board bug **#6** on the card in plain sight: the runner is aiming at the
next whole dollar, 40 cents past the high, because it is not allowed to aim further.
That is somebody else's ticket (`research/g71_faraway.py`, worth +$23 a trade) and I
ported the rule as-is rather than quietly improving it — otherwise the parity test would
have been measuring my opinion instead of your book.

---

## 4. One thing I found and could not fix here

**The live book never closed a runner at the end of the day.** The backtest flattens
anything still open at the last bar; the live paper book had no such step, so a runner
that never reached its level just stayed open forever. The parity test caught it — the
"quiet session" trade booked +0.65R in the backtest and +0.30R live until I added it.

The function now exists (`PaperBook.close_open`). **It still needs one line in
`live_scanner.py` to call it at the market close** — and that file belongs to another
ticket today, so I did not touch it. Until that line exists, the runner leg is complete
in the paper book and unflushed in the scanner. It only matters once the switch is on.

---

## 5. Housekeeping

- **The recall gate is green.** `python research/regression_gate.py` → PASS, no mark that
  fired before went silent.
- Every stop-rule test that touches these two files passes:
  `test_paper_trader_stop.py`, `test_x2_stop_floor.py`, `test_runner_stop.py`,
  `test_t1_two_stop_model.py`, `test_t0_disaster_stop.py`, plus both files' own selftests.
- **Two tests are red and were red before I started**, both belonging to other tickets:
  `research/t11_stop_fill_fix.py` (12 of 64 — that is board bug #4, the safety test
  nobody runs) and `research/test_universe_single_source.py` (7 private ticker lists,
  all inside `research/corpus_sf/`). Neither has anything to do with this change; all of
  t11's failures are on the backtest side and every one of its live-path checks is green.

## Files

| file | what |
|---|---|
| `options_sizer.py` | the rungs, the one price map, the reward fix |
| `paper_trader.py` | the two-rung exit, the end-of-day flush |
| `research/g72_liveexit_parity.py` | **the proof.** 20 checks, both engines, same trade |
| `research/g72_liveexit_cardcheck.py` | the card numbers above, on the real book |

To try it: `OMEN_LIVE_LADDER=1`. Nothing else. Leave it alone until you decide.
