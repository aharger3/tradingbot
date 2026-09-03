# The one-candle rule: where it dies, gate by gate

*2026-08-29. Every number below comes from one instrumented two-year replay —
`research/g74_ocrgates_funnel.py` — which reproduced the shipped book exactly
(134,012 setups looked at, 4,508 trades, 500 sessions), plus the arm books built
by `research/g74_ocrgates_arm.py` and priced by `research/g74_ocrgates_price.py`.
No default was changed. 1R = $1,000.*

---

## The short version

**You already fixed it. Last night.**

The two mechanical causes on the record — the B→C demotion and the flat $0.50
minimum stop — were both **deleted twelve hours before you graded those 30 cards**,
in commit `43b3f59c` ("R3+R4: there is no B on the one candle rule, and no flat
minimum stop"). The "67 trades in two years" figure that made the one-candle rule
look broken is from the engine as it stood *before* that commit.

The engine you have now trades the one-candle rule **482 times in two years**, for
**$338,864**. It is 10.7% of every trade the book takes.

So the question "what refuses to let it trade" has already been answered once. What
follows is what is left.

---

## The funnel, side by side

Both setups are tested on every minute of every session. Break-and-retest gets
about **five swings a minute** — one for each level it watches. The one-candle
rule gets **one**. That is the first asymmetry and it is by design.

### The one-candle rule

| # | gate | where | killed | left |
|---|---|---|---:|---:|
| 0 | every bar, both directions | — | — | 2,048,716 |
| 1 | no order block / structure broken | `omen_bot.py:415` | 1,161,237 | 887,479 |
| 2 | the block candle is not isolated | `omen_bot.py:425` | 717,441 | 170,038 |
| 3 | no displacement off the block | `omen_bot.py:427` | 74,568 | 95,470 |
| 4 | price is not back at the block | `omen_bot.py:430` | 66,752 | **28,718 real setups** |
| 5 | **retest is not wick-only** | `signal_runner.py:51`, applied `:2880` / `:3142` | **21,728** | 6,990 |
| 6 | volume gate (switched off) | `signal_runner.py:52` | 0 | 6,990 |
| 7 | graded X — do not trade | `signal_runner.py:2555` | 5,693 | 1,297 |
| 8 | stop too tight (C-grade only) | `signal_runner.py:1906` / `:2594` | 333 | 964 |
| 9 | same idea again inside the window | `backtest_week.py:861` | 43 | 921 |
| 10 | C = alert only, never a trade | `backtest_week.py:313` | 157 | 764 |
| 11 | two-losses-and-done | `loss_halt.py:87` | 282 | **482 trades** |

### Break-and-retest

| # | gate | where | killed | left |
|---|---|---|---:|---:|
| 0 | every bar, both directions, **every level** | — | — | 10,076,639 |
| 1 | bar did not close back through the level | `omen_bot.py:643` | 7,431,091 | 2,645,548 |
| 2 | big wick against the trade | `omen_bot.py:657` | 603,539 | 2,042,009 |
| 3 | never broke the level | `omen_bot.py:686` | 1,208,864 | 833,145 |
| 4 | broke but never left it | `omen_bot.py:686` | 221,145 | 612,000 |
| 5 | left but never came back | `omen_bot.py:686` | 457,396 | 154,604 |
| 6 | retest too stale (>3 bars) | `omen_bot.py:690` | 24,352 | **130,252 setups** |
| 7 | graded X — do not trade (after the X-lift rescue, `signal_runner.py:2483`, which the one-candle rule is not allowed to use) | `signal_runner.py:2555` | 117,476 | 12,776 |
| 8 | stop too tight (C-grade, plus 66 killed by a floor the one-candle rule is exempt from) | `signal_runner.py:1906` / `:2585` | 3,887 | 8,889 |
| 9 | same idea again inside the window | `backtest_week.py:861` | 1,557 | 7,332 |
| 10 | C = alert only, never a trade | `backtest_week.py:313` | 2,412 | 4,920 |
| 11 | two-losses-and-done | `loss_halt.py:87` | 1,100 | **3,820 trades** |

**Read the two bottom halves together.** Once a setup has been *found*, the
one-candle rule survives routing **better** than break-and-retest does: 6.9% of
found setups become trades against 2.9%. The gap is not downstream any more. It
is at gates 1–5.

---

## The gates that hit the one-candle rule and not break-and-retest

There are five. Two of them were deleted last night. Three are still live, and
**none of the three appears anywhere in your rulebook.**

### 1. "The retest has to be wick-only" — 21,728 setups, 75.7% of everything found

`signal_runner.py:51` — `OB_RETEST_TYPES = ("wick_only",)`

**What it does.** When price comes back to the one-candle-rule candle, this asks
*how far in* it came. If only the wick tagged the candle, the setup is allowed
through. If the body dipped in and closed back out (`partial_body`, 11,875 kills)
or the bar closed inside it (`full_body`, 9,853 kills), the setup is thrown away
before it is ever graded.

**Who wrote it.** Nobody. The comment above it reads: *"30-day sweeps 2026-07-05:
partial_body retests were the leak (wick_only flips OB positive)."* That is a
30-day profit-and-loss sweep from July, encoded into the engine in the omnibus
commit `e1d346ca` on 2026-07-11. It is a curve fit on 30 days of data.

**Is it ratified?** No. `Projects/omen-rulebook.md` has nothing about retest depth
on the one-candle rule. What it does have, as your own definition, is *"we want
price to respect it and break and retest it"* — and a `full_body` close inside the
candle genuinely is the level not being respected, so the strictest third of this
gate is defensible. `partial_body` — wick and part of the body in, close back out —
is not obviously anything you have ever refused. **Break-and-retest has no
equivalent test at all**: it accepts any bar that touches the level and closes back
through it.

**How much of it is real.** I split the 21,728 kills by whether the bar would have
survived the next test anyway (the bar has to close back through the block to fire
at all). Over a 124-session sample:

| retest type | killed | would still have died at the next gate | **uniquely killed by this rule** |
|---|---:|---:|---:|
| `full_body` — closed inside the candle | 2,566 | **2,566 (100%)** | 0 |
| `partial_body` — body straddled the edge, closed back out | 3,145 | 1,937 | **1,208 (38%)** |

So the strict two-thirds of this rule costs nothing: a bar that closes inside the
one-candle candle fails the close-through test regardless. **Everything this rule
uniquely kills is one shape** — a bar that opened *inside* your one-candle candle
and closed back *out* of it. That is a reclaim, and on the face of it, it is price
respecting the candle at least as hard as a wick tag does. Scaled to the full book
that is roughly **4,500 setups**, and it is priced as the `wideretest` arm below.

This is the single biggest lever on the board and it is the one you should look at,
because it is a chart question, not a maths question.

### 2. "A stop wider than 0.4% of the price is not tradeable" — the maximum

`signal_runner.py:2903` (long) and `:3154` (short) — `if stock_risk /
current.close > 0.004: grade = TradeGrade.D`

**What it does.** Refuses any one-candle-rule setup whose stop is more than
0.4% of the share price away, on the reasoning written in the comment: *"stop
wider than 0.4% = 2R unreachable"*. Break-and-retest has **no maximum stop width
whatsoever**; it has a *minimum* instead (`min_risk_floor`, 0.15% of price).

**Who wrote it.** Nobody. Same omnibus commit, `e1d346ca`, 2026-07-11.

**Is it ratified?** It is worse than unratified — **it contradicts an answer you
gave this week.** `Projects/omen-rulebook.md`, 2026-08-29:

> *"we dont need to refuse trades that have a far level away for Q8, we just need
> to find other targets."*

A far target degrades the target; it does not veto the trade. This gate is a
refusal on exactly that reasoning, applied only to the one-candle rule.

### 3. The X-lift rescue that break-and-retest gets and the one-candle rule does not

`signal_runner.py:935` — `x_lift_qualifies()` returns `False` for anything that is
not a break-and-retest, so the T23 lever that pulls good setups back out of the
"do not trade" pile can never reach a one-candle-rule setup.

**Who wrote it.** This one **does** have an author: on 2026-08-29 you graded 40
signals the grader had killed, and 8 of the 9 one-candle-rule cards in that pile
came back "no". So restricting the rescue to break-and-retest was your call, on
your marks. It is listed here for completeness and because those 9 cards were
graded on the *pre-fix* engine.

### 4 and 5. The two that were already deleted — twelve hours before you graded

`43b3f59c`, 2026-08-29 00:50. Both of the causes on the record are gone from the
code. The old lines, quoted exactly:

```python
if stock_risk < 0.50:
    grade = TradeGrade.D
# Austin 2026-07-10 review + 12mo split: OCR only earns its keep at
# A-grade with a TIGHT stop (10tr 40%W +$2k); B-grade 19%W −$13k and
# wide stops 0-for-11 −$10k. Demote the rest to alert-only.
if grade.value == "B":
    grade = TradeGrade.C
```

**Yes — a grade above C was required to trade, and still is.** A `C` is an alert,
never a position (`backtest_week.py:313`: `status == "fired" and grade != "C"`).
The candle grader can only hand a one-candle-rule setup `A+`, `B`, `C` or `X`, and
the promotion to `A` further down (`signal_runner.py:1986`) only fires on a signal
that is currently `B`. So demoting every `B` to `C` left `A+` — a hammer sitting
exactly on the block — as the only grade that could ever trade.

Counted directly at the detection site over a 124-session sample: one-candle-rule
signals grade **X 1,569 · C 195 · B 108 · A+ 30**. `A+` is **1.6%** of them. That
single number is the whole of the old "67 trades in two years": the demotion did
not make the setup selective, it left one rare candle shape as the only way in.

### The trap the two of them made together

The flat $0.50 minimum and the 0.4% maximum were **mutually exclusive on any stock
under $125**:

```
risk >= $0.50   and   risk <= 0.004 x price   =>   price >= $125
```

Checked against the book rather than argued: of the 6,809 one-candle-rule signals,
**1,723 clear both rules, and the cheapest of them is priced at $131.76.** Fifteen
of your twenty-eight symbols traded below $125 during the window — ACHR, AMD,
BABA, HOOD, INTC, IREN, MARA, MU, NFLX, NVDA, ORCL, PLTR, SOFI, SPCX, UBER — and
on every one of them the one-candle rule was **structurally incapable of firing a
trade**, whatever the chart looked like. That is the same bug class as
`omen-rules-unreachable-in-code`: a real rule turned into a branch that cannot be
true.

Your ACHR card in yesterday's batch — the $7 stock you marked **yes** — could not
have traded under the old engine at any price action.

### What the $0.50 floor costs if it ever comes back

Measured on today's book, on the trades it would bench:

| | |
|---|---:|
| one-candle-rule trades it kills | **351 of 482 — 72.8%** |
| dollars it kills | **$305,179 of $338,864 — 90.1%** |
| of those trades, priced over $200 | 165 |
| priced $100–$200 | 109 |
| priced under $100 | 77 |

It is not only a cheap-stock problem, and that is the surprise: because the 0.4%
maximum caps the stop at $2.40 on a $600 name, a flat $0.50 floor squeezes the
allowed stop into a narrow band on *expensive* stocks too. It benches 30 of IWM's
31 trades, 29 of AAPL's 35, 27 of SPY's 33.

### For balance: one gate runs the other way

`MIN_STOP_PCT` (`signal_runner.py:2585`) throws away any signal whose stop is
under 0.08% of the share price. The one-candle rule is **exempt** from it, on your
R4 answer — *"no minimum stop distance on OCR, size to the stop."* It killed 66
break-and-retest signals in two years and zero one-candle-rule signals. That is the
only asymmetry pointing the other way, and it is ratified.

---

## The biggest gate of all is not a one-candle-rule gate

Of the 5,585 one-candle-rule signals thrown away for being graded X, **3,384 —
60.6% — were killed before a single candle was looked at**, by the
higher-timeframe trend veto (`omen_bot.py:242`). For break-and-retest the same
veto accounts for 50.7% of its X pile. It hits the one-candle rule harder, and it
is not a small effect: this is the largest single kill anywhere below detection,
for either setup.

**It has no author.** Ballot batch 02, question c6, you:

> *"we dont have any higher timeframe bias yet youll need to tell me what that is
> then."*

**And the record says it was already deleted.** `Projects/omen-rulebook.md`, under
*"Higher-timeframe bias is not a rule, so it is not a veto"*, says: *"`HTF_BIAS_VETO`
shipped ON and gated 47.0% of the two-year book on a formula (SMA20-of-hourly)
nobody wrote. **Deleted 2026-08-28**."*

It is not deleted. `omen_bot.py:29` reads `os.getenv("HTF_BIAS_VETO", "1")` and it
evaluated to `True` when this was written. The code's own docstring already flags
that *four* committed artefacts had this backwards; the rulebook is a fifth. The
decision is queued as R6 and is genuinely yours — but the board should stop saying
it is done.

Priced below as the `nohtf` arm.

---

## What the one-candle rule is actually worth today

Taking every signal the engine fires, over 500 sessions:

| | one-candle rule | break-and-retest | 84% re-entry |
|---|---:|---:|---:|
| trades | 482 | 3,820 | 206 |
| win rate | 42.9% | 63.4% | 25.2% |
| **average result per trade** | **+0.703R** | +0.608R | −0.135R |
| dollars a day | $678 | $4,646 | −$56 |
| two-year total | $338,865 | $2,322,799 | **−$27,815** |
| months green | 21 of 25 | 25 of 25 | 11 of 25 |
| weeks green | 60 of 105 | 102 of 105 | 28 of 105 |

**Your eye was right.** The one-candle rule wins less often than break-and-retest
and makes more per trade than either of the other two — the best average result in
the book. It is also the only one of the three you graded 80%.

**And the 84% re-entry rule loses money.** −$27,815 over two years, a $47,430
drawdown, red on 14 of 25 months. It is your lowest-precision setup on yesterday's
cards (6 of 10) and it is the only setup in the book with a negative expectancy.
That is not this ticket, but nobody should read the table above without seeing it.

### And the one-candle rule **on its own** is the best class in the book

Split by the label you asked for on 2026-08-29 — break-and-retest, one-candle
rule, and the two together as a third class:

| class | trades | win rate | average per trade | two-year total |
|---|---:|---:|---:|---:|
| **one-candle rule alone** | 141 | 31.9% | **+1.027R** | $144,757 |
| break-and-retest alone | 1,168 | 58.0% | +0.574R | $670,705 |
| BR + OCR together | 2,993 | 63.6% | +0.617R | $1,846,201 |
| 84% re-entry | 206 | 25.2% | −0.135R | −$27,815 |

**This is the same answer your eye gave.** On the 30 cards, one-candle rule alone
scored 8 of 10 and the two-together class scored 6 of 9 — *below* OCR alone, which
you said was backwards from what you expected. The money says the same thing: the
lone one-candle rule wins less than half as often and still makes nearly twice as
much per trade. It is a low-hit-rate, big-payoff setup, and averaging it into the
confluence class hides that.

For scale: on 2026-08-26, `research/p3_confluence.md` measured this exact slice at
**16 trades, 18.8% win, −0.315R**. It is now 141 trades at +1.027R. That is the
R3/R4 deletion, nothing else.

### The catch, and it is a big one

Under **one trade a day** — the way you would actually run it — the one-candle rule
is the first trade of the day on **9 days out of 499**. Break-and-retest takes the
other 490.

That is not a grading problem. It is the five-swings-a-minute asymmetry at the top
of this note: break-and-retest is watching six levels at once and almost always
arrives first. So opening the one-candle rule further will move the *all-trades*
book and will barely touch the *one-a-day* book. Both numbers are reported for
every arm below, and where they disagree, that is why.

---

## Pricing the unlock

Every row below is a full two-year rebuild with **one** thing changed, priced with
the same arithmetic the G7.2 board used. `head` is today's engine and reproduces
`research/bt2y_trades.json` exactly (134,012 setups, 4,508 trades), which is the
proof the harness is not lying.

The arms:

| arm | what changed |
|---|---|
| `head` | nothing — today's engine |
| `pre_r3r4` | the B→C demote **and** the flat $0.50 minimum put back (the engine as of yesterday morning) |
| `demote_only` | just the B→C demote back |
| `flat50` | just the flat $0.50 minimum back |
| `relfloor` | the **relative** minimum break-and-retest uses (`max($0.10, 0.15% of price)`) applied to the one-candle rule |
| `nomax` | the 0.4%-of-price **maximum** stop gate removed |
| `wideretest` | `partial_body` retests allowed as well as `wick_only` |
| `xlift_ocr` | the X-lift rescue allowed to reach the one-candle rule |
| `nohtf` | the one-candle rule exempt from the higher-timeframe veto |
| `merits` | `nomax` + `wideretest` + `xlift_ocr` |
| `allmerits` | `merits` + `nohtf` — the ceiling, not a proposal |

### Taking every signal the engine fires

| arm | trades | win rate | $/day | months green | weeks green | worst drawdown | two-year total | honest range on $/day vs today |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **head (today)** | 4,508 | 59.4% | **$5,268** | 25/25 | 100/105 | $11,105 | $2,633,850 | — |
| `pre_r3r4` | 4,158 | 61.3% | $4,770 | 25/25 | 100 | $11,166 | $2,385,239 | **−$811 to −$203** |
| `demote_only` | 4,401 | 60.6% | $5,120 | 25/25 | 101 | $11,338 | $2,560,106 | −$387 to +$65 |
| `flat50` | 4,198 | 60.8% | $4,719 | 25/25 | 99 | $11,166 | $2,359,340 | **−$856 to −$260** |
| `relfloor` | 4,263 | 60.2% | $4,715 | 25/25 | 99 | $11,105 | $2,357,298 | **−$836 to −$295** |
| `nomax` | 4,550 | 59.1% | $5,249 | 25/25 | 100 | $12,105 | $2,624,729 | −$124 to +$94 |
| `wideretest` | 4,682 | 58.4% | $5,303 | 25/25 | 100 | $11,245 | $2,651,416 | −$215 to +$282 |
| `xlift_ocr` | 5,289 | 54.3% | $4,762 | 25/25 | 99 | $16,419 | $2,380,771 | **−$944 to −$88** |
| **`nohtf`** | 4,902 | 58.3% | **$5,597** | 25/25 | 100 | $13,105 | $2,798,525 | **+$101 to +$572** |
| `merits` | 5,701 | 53.5% | $5,089 | 25/25 | 96 | $20,358 | $2,544,618 | −$663 to +$299 |
| `allmerits` | 5,811 | 53.7% | $5,276 | 25/25 | 96 | $17,156 | $2,637,962 | −$497 to +$511 |

The last column is a paired day-by-day resample, 10,000 times, on the same 500
days. **A range that straddles $0 means the arm did nothing you can bank.** Only
four arms clear their own error bar, and three of them clear it *downward*.

### One trade a day — the way you would actually run it

| arm | trades | win rate | $/day | months green | weeks green | worst drawdown | honest range vs today |
|---|---:|---:|---:|---:|---:|---:|---:|
| **head (today)** | 499 | 66.7% | **$721** | 25/25 | 87/105 | $5,993 | — |
| `pre_r3r4` | 498 | 66.5% | $713 | 25/25 | 86 | $5,993 | −$21 to +$2 |
| `flat50` | 498 | 66.5% | $711 | 25/25 | 86 | $5,993 | −$23 to $0 |
| `relfloor` | 499 | 66.7% | $721 | 25/25 | 87 | $5,993 | −$9 to +$7 |
| `nomax` | 499 | 66.5% | $703 | **24/25** | 87 | $5,993 | −$43 to +$4 |
| **`wideretest`** | 499 | 67.9% | **$739** | 25/25 | **89** | $5,993 | −$18 to +$56 |
| `xlift_ocr` | 499 | 65.7% | $649 | **24/25** | 84 | $6,993 | **−$142 to −$4** |
| `nohtf` | 499 | 66.7% | $724 | 25/25 | 86 | $5,993 | −$35 to +$44 |
| `merits` | 499 | 67.1% | $617 | **23/25** | 84 | $6,993 | **−$189 to −$21** |
| `allmerits` | 499 | 66.3% | $607 | **23/25** | 84 | $6,993 | **−$204 to −$31** |

**Nothing here moves.** That is the arrival-order problem, exactly as flagged
above: under one-a-day the one-candle rule is the first trade on 9 days out of
499, so no amount of opening it up changes what you actually take. The only
one-a-day movement in the whole sweep is *downward*, from the two arms that
include the X-lift.

### The one-candle rule's own slice

| arm | OCR trades | win rate | per trade | two-year OCR dollars |
|---|---:|---:|---:|---:|
| **head (today)** | 482 | 42.9% | **+0.703R** | $338,865 |
| `pre_r3r4` | **86** | 51.2% | +0.494R | $42,451 |
| `demote_only` | 338 | 49.1% | +0.687R | $232,227 |
| `flat50` | 133 | 41.4% | +0.223R | $29,680 |
| `relfloor` | 229 | 39.3% | +0.258R | $59,030 |
| `nomax` | 563 | 43.2% | +0.636R | $358,094 |
| `wideretest` | 744 | 42.7% | +0.594R | $441,984 |
| `xlift_ocr` | 1,587 | 37.7% | +0.168R | $266,100 |
| `nohtf` | 914 | 43.7% | +0.565R | $516,371 |
| `merits` | 2,114 | 39.8% | +0.229R | $484,706 |
| `allmerits` | 2,214 | 40.8% | +0.263R | $581,408 |

---

## What the sweep actually says

**1. The unlock you already shipped is worth $498 a day, and it is real.**
Putting the two old gates back costs **−$811 to −$203 a day** — it clears its own
error bar, which almost nothing on this project does. Over two years that is
**$248,611**. The one-candle rule went from 86 trades to 482.

**2. The costly half was the flat $0.50 floor, not the demotion.** On its own the
$0.50 floor costs **−$856 to −$260 a day**. On its own the B→C demotion is a
**null** (−$387 to +$65). Both had to go; only one of them was expensive.

**3. The min-stop sweep has a clean winner, and it is "none".**

| minimum stop on the one-candle rule | $/day | OCR trades | honest range vs today |
|---|---:|---:|---:|
| **none — today, your R4 answer** | **$5,268** | 482 | — |
| flat $0.50 | $4,719 | 133 | −$856 to −$260 |
| the relative rule break-and-retest uses (0.15% of price) | $4,715 | 229 | −$836 to −$295 |

**Importing break-and-retest's relative floor onto the one-candle rule would be
just as bad as the flat one.** "Size to the stop" was the right answer and this is
the first time it has been priced. Do not re-litigate it.

**4. The 0.4% maximum-stop gate is free to remove — and free to keep.** Taking it
out adds 81 one-candle-rule trades and moves the book **−$124 to +$94 a day**: a
null. The argument for deleting it is not money, it is that it refuses trades for
having a far target, which you ruled against on 2026-08-29. The argument for
keeping it is that it costs nothing. **This one is genuinely yours.**

**5. The wick-only retest rule is the best-behaved lever on the board.** Allowing
`partial_body` — the reclaim shape — adds **262 one-candle-rule trades**, and:

- all trades: $5,268 → **$5,303/day** (range −$215 to +$282, so: no measurable
  money either way)
- one trade a day: $721 → **$739/day**, win rate 66.7% → **67.9%**, weeks green
  **87 → 89**, months green still 25/25, drawdown unchanged
- it is the **only arm in the sweep that improves one-a-day durability at all**

It does not clear its error bar, so it is not money you can spend. But it is 262
extra trades for free, on the setup you grade 80%, with every durability number
flat or better. **This is the one to look at on a chart** — pull up a handful of
the shapes it lets in and say whether they are one-candle-rule setups.

**6. The X-lift must stay off the one-candle rule. You were right.** Letting it
reach the one-candle rule adds 1,105 trades and costs **−$944 to −$88 a day**, and
takes one-a-day down **−$142 to −$4 a day** with months green 25 → 24. Your 8-of-9
"no" on those veto-lane cards was the correct call and the money agrees. This is
also why the `merits` and `allmerits` combinations look bad — the X-lift is
dragging them.

**7. The unauthored higher-timeframe veto is where the money is, and it is not an
OCR question.** Exempting the one-candle rule alone from it:

- all trades **$5,268 → $5,597/day**, range **+$101 to +$572** — the only arm in
  the sweep that clears zero on the upside
- **+$164,675** over two years, 25/25 months green, 100 weeks green
- worst drawdown $11,105 → $13,105 — it costs you a bigger hole
- one trade a day: **nothing** (−$35 to +$44)

Caveat, stated plainly: this arm lifts the veto *and* the "neutral hour caps you at
B" rule, because they live in the same branch. And R6 is already open on this. What
this adds is that the veto is not merely unauthored — it is **the largest single
kill in the engine for either setup**, and the record says it was deleted a day
ago when it was not.


---

## The structural point underneath all of this

Your own definition, `Projects/omen-rulebook.md`, 2026-08-23:

> *"the OCR candle is a **level generator**, not a signal by itself — it
> manufactures a level, and then the ordinary break-and-retest machinery runs on
> that level."*

The code does not do that. The one-candle rule is a **separate detector with its
own, stricter geometry** (`omen_bot.detect_order_block_setup`): its own structure
test, its own isolation test, its own displacement test, and its own retest-depth
test that break-and-retest does not have. It never touches
`detect_break_retest` at all.

That is why every asymmetry in this note exists. If the one-candle rule fed the
ordinary break-and-retest machinery the way you described it, it would inherit
break-and-retest's gates — including the X-lift rescue — and would not carry a
wick-only retest rule or a maximum stop width, because break-and-retest has
neither. **Building it your way is a bigger change than any single gate here, and
it is the one that makes all five asymmetries disappear at once.**

**8. The best combination, and it is not a free win.** Everything the one-candle
rule carries that break-and-retest does not, removed — *except* the X-lift, which
arm 6 showed to be the one clearly harmful change (`best` in
`research/g74_ocrgates_price_best.json`):

| | today | `best` |
|---|---:|---:|
| trades | 4,508 | 5,512 |
| win rate | 59.4% | 56.3% |
| **all-trades $/day** | $5,268 | **$5,863** (range **+$181 to +$1,009**) |
| two-year total | $2,633,850 | $2,931,476 |
| months green | 25/25 | 25/25 |
| weeks green | 100/105 | 98/105 |
| worst drawdown | $11,105 | **$17,245** |
| **one-a-day $/day** | **$721** | $645 (range −$156 to $0) |
| one-a-day months green | 25/25 | **24/25** |
| one-candle-rule trades | 482 | 1,746 |

**+$297,626 over two years on the all-trades book, and it clears its error bar.**
But it costs **$6,140 of extra drawdown**, two green weeks, and it makes the
one-trade-a-day book *worse* — including breaking your every-month-green gate,
which is one of your three. Under your own policy this is a no as it stands. The
piece of it worth having is the higher-timeframe veto, on its own, where the
drawdown cost is $2,000 instead of $6,140 and one-a-day does not move.

---

## What I would put in front of you, in order

1. **Nothing is broken and nothing needs reverting.** The one-candle rule trades
   482 times for $338,865 at the best average result in the book. The premise that
   started this — 67 trades, something refusing to let it trade — was true
   yesterday morning and is not true now.
2. **One chart question, and it is the only thing here that needs your eye.** Pull
   up a few `partial_body` one-candle-rule retests — bars that opened *inside* your
   one-candle candle and closed back *out* of it — and say whether they are your
   setup. If yes, that is 262 extra trades, the same money, and the only
   durability improvement in the whole sweep (weeks green 87 → 89).
3. **One rule question you have half-answered.** The 0.4%-of-price maximum stop
   refuses one-candle-rule trades for having a far target. On 2026-08-29 you said
   *"we dont need to refuse trades that have a far level away, we just need to find
   other targets."* Removing it is free either way — the money is a null. Say
   whether the answer covers it.
4. **R6, the higher-timeframe veto, is worth more than everything else on this page
   put together** — +$101 to +$572 a day for the one-candle rule alone — and the
   board wrongly records it as deleted. Somebody should fix the board today whether
   or not you answer R6.
5. **Do not put any minimum stop back on the one-candle rule** — not the flat $0.50
   and not break-and-retest's relative one. Both are worth roughly −$550 a day and
   both clear their error bar. Your R4 answer is now priced and it was right.
6. **Not this ticket, but you should see it:** the 84% re-entry rule loses $27,815
   over two years at −0.135R a trade, red in 14 of 25 months, with a $47,430
   drawdown. It is the only negative-expectancy setup in the book.

---

*Scripts: `research/g74_ocrgates_funnel.py` (the two funnels, one instrumented
replay that reproduces the shipped book exactly) · `research/g74_ocrgates_arm.py`
(one arm, one rebuild, priced in-process) · `research/g74_ocrgates_price.py` (all
arms in parallel + the paired bootstraps). Outputs:
`research/g74_ocrgates_funnel.json`, `research/g74_ocrgates_price.json`,
`research/g74_ocrgates_price_best.json`. No engine default was changed; the recall
gate, the universe test, the stop-fill test and the runner-stop test were all run
after this work and are all green.*
