# G72 — where the catastrophic stop goes

Austin, 2026-08-29:

> "i want it to just be **1k max loss so each loss hits that on average**, but whatever increases edge right now which was **option 1**. i just **dont want to enter a trade and somehow lose 10000** you see what i mean so **some parameter has to be out there**."

## The number

# $2,500 — a real order, resting in the market, filled the moment price touches it.

Two and a half times the money you planned to risk. On the two-year book it would have
touched **145 of 4,726 trades (3.1%)**, turned **2 winners** into losses, and cost
**−0.0000 R** (SE 0.0024, t = −0.01) — the ledger of what it saves against what it costs
comes to **−$146 over two years**. It makes $10,000 on one trade structurally impossible,
with four times the margin.

Three things he also needs to hear, and none of them are smoothed over below:

1. **His $1,000-average-loss test fails, and it fails for a reason he chose.** With the
   resting order deleted the average loss is **$1,398**, not $1,000. No stop level fixes
   that. Only position size does — **$715 a trade instead of $1,000**.
2. **The board's option-1 numbers were flattered by a clamp that is not an order.** Its
   "worst trade $1,250, worst drawdown $13,700" comes from a `max()` in the backtest. Run
   the same construction on today's engine and it reads $1,250 / $14,299; take the `max()`
   out and the same book reads **$6,062 / $22,395**.
3. **The catastrophic stop has to fire on a touch, not on a close.** Measured: of the 178
   trades that lost more than $2,000, **178 of 178** reached that price intrabar before any
   candle closed there. A close-checked cap would have fired on none of them.

---

## The clamp — read this before any other number

`stop_rule.stop_fill_price()` clamps every close-triggered fill at −1.25 R. **That clamp is
not an order.** It is a `max()` that books a better price than the market gave. It is why
the board's option-1 book reports a worst single trade of exactly $1,250 — a number that has
nothing to do with the market and everything to do with a line of Python.

It is also not small. Against the same book with the clamp removed, it binds on **997
trades** and quietly erases **$452,010** of loss, worth **+0.0956 R of mean** (SE 0.0044,
**t = +21.9**) — bigger than any stop-placement or exit effect on the G71 board, and it is
not an effect at all.

Both rows below are the *same* arm on the *same* engine — resting order deleted, level stop
on the close. The only difference is whether the `max()` is left in:

| option 1, two ways | worst single trade | worst drawdown | mean R | win% |
|---|--:|--:|--:|--:|
| with the clamp left in (the board's construction) | $1,250 | $14,299 | +0.6686 | 63.0% |
| **with the clamp taken out — the honest fill** | **$6,062** | **$22,395** | +0.5716 | 62.9% |

(The board's own $1,250 / $13,700 is the top row measured on the earlier engine — see the
last section on how much the book moved this afternoon.)

This is the same failure mode `research/x2_stop_floor_audit.md` found in the −1.25 R floor
itself, and it is why every arm in the sweep below moves the clamp **out to the same number
as the resting order**. Sweeping a $3,000 cap against a book already clamped at $1,250
measures nothing: the clamp does all the work and the new level is unreachable code.

**And it means the honest case for option 1 is narrower than the board says.** Once the
clamp is priced, deleting the resting order is worth **+0.0169 R** (SE 0.0143, t = +1.19) —
nothing. What is real is the **win rate, 59.2% → 62.9%**, which is exactly the "wicks stop
nothing" effect: a bar that dips through the level and recovers is a loser with the order
resting there and a survivor without it. Durability holds either way, 25/25 months.

---

## (a) Every loss, with the resting order deleted and nothing capping it

Arm `none`: the level stop still triggers on the candle **close** and fills at that close
(`stop_rule.stop_fill_price` with the floor moved to infinity). 4,822 trades, 1,776 of them
losing.

| mean loss | median | 75th | 90th | 95th | 99th | worst |
|--:|--:|--:|--:|--:|--:|--:|
| **$1,401** | $1,291 | $1,574 | $2,007 | $2,385 | $3,330 | **$6,062** |

| losses past… | $1,250 | $1,500 | $2,000 | $3,000 | $5,000 | $10,000 |
|---|--:|--:|--:|--:|--:|--:|
| trades | 970 | 525 | **178** | 32 | 1 | **0** |

Total lost on losing trades **$2,488,196**, of which **$447,507** sits beyond $1,250.

**The $10,000 trade has never happened.** In two years, 4,822 trades, 28 symbols, the worst
single trade is **$6,062** and exactly one trade lost more than $5,000. His fear is not
groundless — it is *unrealised*. A cap is insurance against the halt, the gap, the headline
that is not in this sample, not against something the tape has already shown him.

---

## (b) The sweep

Every arm below deletes the resting order at the level-stop price (his option 1) and puts
**one** order at the catastrophic level instead, filled on an intrabar touch, with the fill
clamp moved out to the same number so nothing else caps the trade. 1R = $1,000, so a $2,500
level is literally `DISASTER_STOP_R = 2.5`.

| catastrophic level | binds on | of which real disasters | of which only wicked there | mean loss | $/trade | win% | months | weeks | worst trade | worst drawdown |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| $1,250 | 1,411 (30.9%) | 952 | 459 | $1,184 | $588 | 61.3% | 25/25 | 98/105 | $1,250 | $15,200 |
| $1,500 | 937 (20.2%) | 532 | 405 | $1,302 | $576 | 62.2% | 25/25 | 97/105 | $1,500 | $15,934 |
| $2,000 | 374 (7.9%) | 182 | 192 | $1,387 | $567 | 62.8% | 25/25 | 97/105 | $2,000 | $19,216 |
| **$2,500** | **145 (3.1%)** | 79 | 66 | **$1,398** | $570 | 62.8% | **25/25** | 96/105 | **$2,500** | $21,402 |
| $3,000 | 72 (1.5%) | 33 | 39 | $1,407 | $567 | 62.8% | 25/25 | 96/105 | $3,000 | $21,435 |
| $4,000 | 20 (0.4%) | 4 | 16 | $1,408 | $569 | 62.9% | 25/25 | 96/105 | $4,000 | $22,549 |
| $5,000 | 6 (0.1%) | 1 | 5 | $1,408 | $569 | 62.9% | 25/25 | 96/105 | $5,000 | $22,395 |
| none (uncapped) | — | — | — | $1,401 | $572 | 62.9% | 25/25 | 96/105 | **$6,062** | $22,395 |
| _today's engine — order rests at the level stop_ | — | — | — | $975 | $584 | 59.2% | 25/25 | 100/105 | $1,000 | $11,105 |
| _option 1 as the board measured it (clamped $1,250)_ | — | — | — | $1,151 | $669 | 63.0% | 25/25 | 102/105 | $1,250 | $14,299 |

**"Binds on" splits into two very different things, and the split is the whole argument.**
A cap can cut a real disaster short (the trade was going to lose more anyway), or it can
kill a trade that only *wicked* through the level and would have been fine. A resting order
cannot tell them apart — it fills on a touch.

| level | trades it touches | disaster it cuts | given back on trades that would have survived | winners it turns into losses | **net over 2 years** |
|---|--:|--:|--:|--:|--:|
| $1,250 | 1,411 (30.9%) | +$431,151 | −$342,624 | 72 | +$88,527 |
| $1,500 | 937 (20.2%) | +$264,016 | −$242,754 | 34 | +$21,262 |
| $2,000 | 374 (7.9%) | +$104,336 | −$114,822 | 7 | −$10,486 |
| **$2,500** | **145 (3.1%)** | **+$45,739** | **−$45,885** | **2** | **−$146** |
| $3,000 | 72 (1.5%) | +$20,156 | −$32,240 | 1 | −$12,084 |
| $4,000 | 20 (0.4%) | +$3,177 | −$15,186 | 0 | −$12,009 |
| $5,000 | 6 (0.1%) | +$1,062 | −$13,625 | 0 | −$12,563 |

Same thing with an error bar on it, paired row-by-row against the uncapped book:

| level | shared rows | change in mean R | SE | t |
|---|--:|--:|--:|--:|
| $1,250 | 4,559 | +0.0194 | 0.0096 | +2.01 |
| $1,500 | 4,640 | +0.0046 | 0.0077 | +0.59 |
| $2,000 | 4,712 | −0.0022 | 0.0045 | −0.49 |
| **$2,500** | 4,726 | **−0.0000** | 0.0024 | **−0.01** |
| $3,000 | 4,726 | −0.0026 | 0.0020 | −1.26 |
| $4,000 | 4,727 | −0.0025 | 0.0013 | −2.03 |
| $5,000 | 4,727 | −0.0027 | 0.0014 | −1.91 |

**Every level from $2,000 out is free within noise.** So the choice is not a money question
at all — it is purely "how far out do you want the wall".

---

## (c) The knee: $2,500, and it touches 3.1% of trades

Two curves cross here.

**The tail it has to cover**, off the uncapped book:

| a cap here | trades that lost more | share of the book | dollars of loss beyond it | share of all loss |
|---|--:|--:|--:|--:|
| $1,250 | 970 | 20.12% | $447,507 | 17.99% |
| $1,500 | 525 | 10.89% | $264,346 | 10.62% |
| $2,000 | 178 | 3.69% | $104,021 | 4.18% |
| **$2,500** | **77** | **1.60%** | $45,775 | 1.84% |
| $3,000 | 32 | 0.66% | $20,356 | 0.82% |
| $4,000 | 4 | 0.08% | $3,177 | 0.13% |
| $5,000 | 1 | 0.02% | $1,062 | 0.04% |

**The normal trades it must not touch.** A resting order does not care how the trade ended —
it fills the moment price reaches it. So the population that matters includes winners.
Maximum adverse excursion over the bars each trade was actually open, 1,200-trade sample,
760 of them winners:

| order here | trades whose worst moment reached it | share | **winners** whose worst moment reached it | share of winners |
|---|--:|--:|--:|--:|
| $1,250 | 363 | 30.25% | 28 | 3.68% |
| $1,500 | 225 | 18.75% | 10 | 1.32% |
| $2,000 | 85 | 7.08% | 2 | 0.26% |
| **$2,500** | **34** | **2.83%** | **1** | **0.13%** |
| $3,000 | 20 | 1.67% | 1 | 0.13% |
| $4,000 | 6 | 0.50% | 0 | 0.00% |

**$2,500 is where the two curves stop fighting.** It still covers the 77 trades that ran past
it — the entire $45,775 tail above it — while sitting outside the worst moment of **97.2% of
all trades and 99.87% of winners**. Moving it in to $2,000 destroys 3.5x as many winners
(7 against 2) and turns the ledger from −$146 to −$10,486, for $58,000 more coverage. Moving
it out to $3,000 halves the coverage and buys back essentially nothing — one winner either
way.

**It also happens to be the only level whose ledger balances exactly**: +$45,739 of disaster
cut against −$45,885 given back, net **−$146** on a book that makes $2.76M. That is not a
coincidence being read as a signal — it is a coincidence, and it is reported because it is
the level where "does the wall cost me anything" has the cleanest possible answer: no.

**What it touches: 145 trades in two years, about one every three and a half trading days**
— but only 79 of those bind because the trade was genuinely going bad, and only 2 were
winners. In four decimal places of mean R, it is free.

---

## (d) "Each loss hits $1,000 on average" — the honest answer

**No. With the resting order deleted, the average loss is $1,398, and $2,500 is not why.**

| | average loss |
|---|--:|
| today's engine (order resting at the level stop) | **$975** |
| option 1 as the board measured it (clamped $1,250) | $1,151 |
| option 1, honest, with a $2,500 catastrophic stop | **$1,398** |
| option 1, honest, nothing capping it | $1,401 |

Look at the sweep table again: the catastrophic level barely moves this number. $2,000 gives
$1,387, $3,000 gives $1,407, uncapped gives $1,401. **The average loss is set by option 1
itself, not by the wall.**

The reason is arithmetic, not engineering. Today the order rests exactly *on* the level stop,
so every loss fills there and books exactly −$1,000 — that is where "$975 average" comes
from, and it is the only way to get it. His own rule says a wick through the level is not a
stop-out; the trade only ends when a candle **closes** beyond it, and by then price is
already past. **1,649 of 1,776 losses — 93% — book worse than the $1,000 he planned**, by a
median of **$321**. **The $1,000 average loss and "wicks stop nothing" are the same trade-off
seen from two sides. He cannot have both, and he already chose the wick rule.**

**The one lever that does deliver a $1,000 average loss: risk $715 a trade instead of
$1,000.** Dollars are a sizing skin — scaling risk scales every loss *and* every win by the
same factor and leaves mean R untouched. At $715 a trade the average loss becomes
$1,398 × 0.715 = **$1,000**, with the same edge, the same win rate and a position ~28%
smaller. **This is a decision only he can make**, because it is his account size, not a
measurement.

---

## (e) Touch, not close — and a close-checked cap is not a cap

**On a touch. This is not a preference, it is the only thing that works, twice over.**

**First: a close-checked catastrophic stop is unreachable code.** The level stop already
triggers on the *first* candle that closes beyond $1,000 and fills at that close. Any
catastrophic level past $1,000 can only be reached by a close that is *also* beyond $1,000 —
so the level stop has already fired, on that same bar, at that same price. A close-checked
cap at any level therefore books exactly what the uncapped book books: **worst trade
$6,062**. Adding it changes nothing, on any row. This is the same bug class as the −1.25 R
floor that was dead code for months (`research/x2_stop_floor_audit.md`) and the T4(b) scratch
that could never fire (`research/p8_scratch.md`) — a real rule written as a branch that can
never be true.

**Second: the disasters are intrabar events, and the measurement is unanimous.** Replaying
the exit bar of every trade that lost more than each level:

| level | trades that lost more | reached it **intrabar** first | arrived only at a close | the bar **before** still closed inside $1,000 | where the trade stood at that prior close |
|---|--:|--:|--:|--:|--:|
| $2,000 | 178 | **178** | **0** | 155 of 157 | −$494 |
| $2,500 | 77 | **77** | **0** | 67 of 67 | −$439 |
| $3,000 | 32 | **32** | **0** | 28 of 28 | −$136 |

Read the last two columns. One bar before the disaster, the trade was still sitting at half
a planned loss — median **−$494** — and the next candle took it to double or triple. **The
whole move happens inside one candle.** There is no earlier close to react to, and there
never was.

His "wicks stop nothing" rule is untouched by this, because it was always a rule about the
**level stop**, which is a signal. This is a risk cap, and it is the one exception he already
named himself — *"Level stop on the close, disaster stop on touch."* What is changing is only
**where** the touch order sits: off the level stop, out to $2,500.

**One honest caveat about the model.** The backtest fills the resting order *at* its price.
A genuine gap — a halt reopening, an 08:30 headline — fills worse. The $2,500 wall is a wall
in normal conditions and a speed bump in the event it exists for, and no backtest on
1-minute bars can tell him otherwise. The number to remember is the direction: it converts an
open-ended loss into a roughly-$2,500 one.

**And it is not wired into the live path.** `disaster_stop_price` / `disaster_stop_hit` are
called only from `backtest_week.py`. `paper_trader.py` and `live_scanner.py` have no such
order at any level today.

---

## (f) Does the −$2,000 daily floor already do this? No.

Cross-checked directly: his chosen sequencing rule — **3 consecutive losses ends the day,
plus a −$2,000 floor on the day's realised P&L** — run over the uncapped book with no
per-trade cap at all.

| with the 3-loss cap and the −$2,000 daily floor, no per-trade cap | |
|---|--:|
| worst single trade | **$6,062** |
| single trades that alone lost more than $2,000 | **169** |
| single trades that alone lost more than $5,000 | 1 |
| days that still finished worse than −$2,000 | **137** |
| worst day | $8,976 |
| worst drawdown | $19,679 |

**The floor cannot reach inside an open position.** It is evaluated at the *next* trade's
entry moment against trades that have already **closed** — that is `walk_day`'s causality
discipline in `research/g71_losshalt_grid.py`, and it is correct, because when you place
trade #3 you do not yet know trade #2 loses. A day sitting at −$1,900 passes the floor, takes
one more trade, and that trade loses $6,062. The floor never gets a vote. **137 days finish
below −$2,000 despite the −$2,000 floor** for exactly this reason.

So: **not redundant. He needs both, and they do different jobs.**

- The **$2,500 per-trade wall** bounds one trade. It does not fix the day: with a $2,000 cap
  in place the worst day is still $7,465 and 120 days still finish below −$2,000.
- The **−$2,000 daily floor** bounds how many more trades he takes after a bad start. It does
  not bound any of them.

**Neither bounds the drawdown, and he should not expect them to.** Max drawdown is a
portfolio phenomenon — many losses in a row, not one big one (`research/x2_stop_floor_audit.md`
established this). The $2,500 wall moves worst drawdown from $22,395 to $21,402. Restoring
his close-only rule is what moves drawdown, and it moves it the wrong way:
**$11,105 → $22,395**. That is the real, unsmoothed cost of option 1 on the current engine,
and it is the opposite of what the board reported, because the board's number was clamped.

---

## What was measured, and what it does not cover

Ten full 2-year replays of `backtest_2y.py` — 2024-08-21..2026-08-21, 500 sessions, 28
symbols, ~133,900 signals per arm, `data_archive/` replay, zero fetches. (The signal count
moves by a few dozen between arms because the 84% re-entry arm is armed by stop-outs, so
changing an exit changes how many re-entries exist to grade.) **No engine file was edited.** `DISASTER_STOP` / `DISASTER_STOP_R` are the env knobs `backtest_week.py` already
ships; the fill clamp has no knob, so the child process rebinds
`backtest_week.stop_fill_price` to the *same* `stop_rule.stop_fill_price` with a different
`floor_r`. No fill, trigger or floor is reimplemented anywhere in this track.

**The book moved under this measurement, and that is checked rather than assumed.** A
concurrent workflow edited `backtest_week.py` and `backtest_2y.py` at 16:58 and 16:59 today —
between the board's numbers and these. The shipped book went from 76,035 signals / 2,436
traded / 49.5% win (board, 14:59) to **134,012 signals / 4,508 traded / 59.2% win** (17:03).
So the §6 figures in `research/g71_board.md` and the ones here describe different engines,
and the option-1 direction reverses on drawdown between them. The arms in *this* table are
comparable to each other: `none` was deliberately replayed twice, once in each parallel
batch, and the two books are **identical** — same 133,865 signals, same 4,822 traded, same
+0.5716 mean R, same −6.062 worst trade.

What this does not answer: the money gate is untouched (every arm sits near +0.57 R against a
target of 2.0), the instrument is options and every number here is in underlying-R space, and
the live path still has no disaster order at any level.

Reproduce:

```
python research/g72_catastrophic_stop.py --selfcheck     # 9 cases
python research/g72_catastrophic_stop.py run             # 10 arms, ~12 min at 5 jobs
python research/g72_catastrophic_stop.py analyse
python research/g72_catastrophic_stop.py report
```

The arm files are `research/_g72_*.json`, ~120 MB each and regenerable. They are **not**
covered by a `.gitignore` rule — do not `git add -A` in this repo without checking.

## The change, if he says yes

Two defaults in `backtest_week.py`, no new code — and they must move **together**, or the
$1,250 clamp makes the $2,500 level unreachable:

```diff
 # backtest_week.py
-DISASTER_R = float(os.getenv("DISASTER_STOP_R", str(DISASTER_STOP_R)))
+# G72: the resting order comes OFF the level stop (option 1 -- "wicks stop
+# nothing") and goes out to 2.5R as a catastrophic backstop. See
+# research/g72_catastrophic_stop.md: binds on 3.1% of trades, costs 1 winner in
+# 760, -0.0000R paired (SE 0.0024, n = 4,726).
+DISASTER_R = float(os.getenv("DISASTER_STOP_R", "2.5"))

 # stop_rule.py
-MAX_LOSS_R = 1.25
+MAX_LOSS_R = 2.5
```

**Both lines, or neither.** A fill clamp tighter than the wall makes the wall dead code —
that is the whole reason this page exists. And `MAX_LOSS_R = 1.25` is his own ratified number
(`rule_ballot_batch01` q1, *"max slippage -1.25r"*), so moving it is his call, not an
agent's. It is the third thing on this page that needs him, alongside the $2,500 level and
the $715 sizing question.
