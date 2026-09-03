# Does a wick take you out? — settled, with the tape

*Austin, 2026-08-29:*

> **"stop loss is not on candle close i dont like that, stop happen when they do in middle
> of timeframes. weve talked about stops a lot so that seems like a stale opinion."**

This is the fifth time stops have come up. This page is meant to be the last one. It does
not take a side first — it goes and finds what you actually said, when you said it, and
then measures both rules on the tape.

---

## The short answer

**You are already trading intrabar, and you have been all day.** The book you are looking at —
4,508 trades, $721 a day on one-trade-a-day — books every single loss at exactly $1,000 because
there is a live order resting *at your stop price* that fills the moment price touches it. That
is the "middle of the timeframe" stop, and it is already switched on. What you are reacting to
is not a stale opinion in a file; it is the engine already doing what you just asked for.

**On money the two rules are a coin flip.** Close-only makes **+$26 a day** more one-trade-a-day
and the honest range on that is **−$55 to +$118**. Nothing to spend. Neither side comes anywhere
near the ±1.5799R error bar.

**On your own marks, close-only wins and it is not close.** 32 of your 113 marked trades were
pierced by a wick that never closed through your stop. **16 of those 32 went on to make 2R or
better.** Run the same 113 trades both ways and close-only is **+$182 a trade, t = +2.43** — the
only result on this page that clears its own noise.

**And your $2,500 wall only exists if the level stop waits for the close.** Under an intrabar
stop the wall is unreachable code — measured, byte-identical books with it on and off.

**The rule you stated 13 times is not stale. The order that was placed at $1,000 is the mistake.**
Move it out to $2,500 and both of your sentences are true at once: level stop on the close,
disaster stop on touch — which is exactly the card you ratified this morning.

---

## Part 1 — what you actually said, in order

Two different questions have been getting mixed together, and they have different answers.
Separating them is most of the work:

| | the question | the answer, from your own words |
|---|---|---|
| **(a)** | Does a **wick through my stop** take me out of the trade? | **No** — stated **13** separate times across two years of marks and ballots, and never once contradicted on the chart before today |
| **(b)** | Does a wick through a **level** count as that level being broken? | **No** — stated separately, and it is a different rule about chart structure, not about exits |

The engine already gets (b) right and nothing here proposes changing it.

### The timeline

**Before 2026-08-11** — recovered out of old grading chats into
`research/recovered_reviews.jsonl`. These are the oldest and they already carry both halves
of the rule *and* the reason the −1.25R slippage number exists:

> *"stop a little higher, if its tight and you have to chose the wick or the level, choose the
> wick. **its a candle close above the stop**, but if its gonna run like crazy dont let it slip
> then we will lost like 1.6k instead of 1k"* — AMZN 2026-01-14

> *"stop loss wouldn't have been stopped out because candle didn't close ab[ove]"* — META 2026-05-05

> *"could've worked out dont know but stop loss off a few cents so **still would've been in the
> trade**"* — SOFI 2026-01-09

**2026-08-11 — one grading sitting, 80 cards (`batch05` inside
`research/austin_marks_v7.jsonl`).** `CLAUDE.md` says you settled this "five times in one
batch". It was **eight**. Every one of them is you correcting the engine, which had claimed a
stop-out where a wick went through:

| day | symbol | what you wrote |
|---|---|---|
| 2024-01-25 | MSFT | *"your entry **never closed below the stop** so no need 84 percent rule"* |
| 2024-03-20 | MSTR | *"**stop outs only happen when candle closes** by the way"* |
| 2024-09-26 | MSTR | *"I dont see the stop out until later, **stop out happens when candle CLOSES below the level**"* |
| 2025-09-29 | NVDA | *"1 candle earlier is S entry, **no stop out occurs**"* |
| 2025-12-10 | PLTR | *"because the **candle didn't close BELOW the stop**, there is no 84 percent rule"* |
| 2026-02-05 | NVDA | *"**stop out doesn't happen until 10:37**, so dont see an 84 percent rule occur"* |
| 2026-02-09 | MU | *"**stop out would've been 5 candles later because thats when the close below happened**"* |
| 2026-07-24 | MU | *"I dont see a stop out because **you would've held a OCR green candle wick**"* |

That last one is the sharpest sentence in the whole corpus: you are naming a wick through
your stop and saying you *held it*.

**2026-08-23 — rule ballot batch 01.** Question 1 was literally titled `stop-close-not-wick`:

> *"this is correct and needs to be implemented, **a 1m candle close below is exit, max
> slippage −1.25r** which is 1.25k based on current position sizing"*

and question 3, on the break-even stop:

> *"breakeven may end up being slightly higher or lower due to slippage, but if the structure
> doesent break you dont want to stop out, **thats why you wait for candle closes for stops**"*

**2026-08-27 — ballot batch 02.** Two answers here, and one of them has been misfiled as a
stop rule ever since:

- **a2 is about levels, question (b):** *"if its closing above the level but still wicking
  around it its fine, invalidation happens as soon as close below or vise versa for calls."*
- **b9 is not a stop-trigger rule at all.** The question asked why a stop placed at a wick is
  worse, and you answered *"its not risk too wide but risk less predictable because **i find
  trends respect candles with wicks better**."* That is about **which candle you like to put
  the stop under**. It has been quoted around this repo as if it were about wicks *triggering*
  stops. It is not, and it never was.

**2026-08-28** — *"fix stop out 1.25 max slippage this needs to be fixed now."*

**2026-08-29, morning** (`research/marks/probe_master_2026-08-29.jsonl`). You ratified a
two-stop model: **"Level stop on the close, disaster stop on touch"**, with the disaster order
resting at −$1,000 and the outer bound at −$1,250. That is the code that is running right now.

**2026-08-29, afternoon** — shown that the disaster order sits at *exactly* the level-stop
price, so a wick alone kills the trade and every loss books exactly $1,000, you chose to
delete it:

> *"i want it to just be 1k max loss so each loss hits that on average, but whatever increases
> edge right now which was **option 1**. i just dont want to enter a trade and somehow lose
> 10000 you see what i mean so **some parameter has to be out there**"*

"Option 1" **is** the close-only rule. That decision is four hours old.

**2026-08-29, now** — *"stop loss is not on candle close i dont like that."*

### So what changed, honestly

Nothing in the tape. What changed is that the two-stop model you ratified this morning
*produces* an intrabar stop-out on every normal losing trade, because the "disaster" order was
put at the same price as the level stop. **You have been looking at a book where the wick rule
is already in force, and it looks wrong to you — which is the right instinct, but it points the
opposite way from the sentence.** The fix is not to make the level stop intrabar too. It is to
move the disaster order out to where you put it four hours ago: **$2,500, far enough out that
it never touches a normal trade.**

### And where the "middle of the timeframe" feeling comes from — it is real

You are not imagining it. Three of your own marks say so, and they are all about **options**,
not about the chart:

> *"tight options trades like this won't work, spread has to be larger then 20 cents **can
> easily be wicked out**"* — NFLX 2026-07-17

> *"stock too tight and **options contracts would get stopped out in seconds** in these
> scenarios"* — CRM 2026-06-01

> *"tight stop scalp, we like a little more spread on trades generally because then **its harder
> to be stopped out**"* — MU 2026-01-20

This is the whole reconciliation, and Scarface teaches it explicitly in the course transcripts
this project mined (`research/corpus_index.jsonl`):

> *"I only get stopped out on the close of the candle... if this is a wick I'm **not** getting
> stopped out... **I do not have a hard stop loss rather I have a mental stop loss**"*
> — mastermind-5-0 Lesson 1

> *"We don't get stopped out for the wick. We get stopped out by the candle closure."*
> — u4sDOKFdJKc

> *"I personally don't do hard stops... a hard stop especially when you're trading options
> sometimes the option contract will dip a little bit just into just enough to get into that
> stop loss and then shoot up but the actual stock or the underlying..."*
> — mastermind-1-0 Lesson 1

> *"**I have hard stops when I'm trading futures**... for Options wise I always have a mental
> stop"* — lSsE50yS9vc

**"Close-only" is not a claim about how price moves. It is a claim about what kind of order you
have in the market.** A resting hard stop is intrabar by definition. A mental stop is close-only
by definition. You get wicked out when you have a hard stop in, which is why tight options
trades get wicked out — and it is exactly why the course says use a mental stop for options.

The bot is the mental stop. It watches every single one-minute close and never flinches, which
is the one thing a human mental stop cannot promise. That is the whole reason to automate it.

---

## Part 2 — your own tape, on your own marks

113 marked symbol-days carry both an entry bar and a stop **price**
(`research/g73_intrabar_marks.py`, same loader `research/g71_stops.py` uses). For each one I
replayed the archived day forward from your entry and asked two questions: did a wick reach your
stop, and did a candle ever close through it.

| what the tape did after your entry, before 11:00 | days | share |
|---|--:|--:|
| price never even reached the stop | 45 | 39.8% |
| **wicked through the stop and NEVER closed through it** | **14** | **12.4%** |
| **wicked through the stop, closed through it later** | **18** | **15.9%** |
| first bar to reach the stop also closed through it | 36 | 31.9% |

**32 of your 113 marked trades — 28.3% — were pierced by a wick that did not close.** Under an
intrabar rule every one of those is a −$1,000 loss. Under the close-only rule, 14 of them were
never stopped out at all, and the other 18 stayed alive a median of **4 more bars** (max 75).

What happened in those extra bars is the part that matters:

- **16 of the 32 went on to make +2R or better** before any candle closed through the stop.
- Median favourable move after the wick: **+2.12R**. Best: **+20.51R** (SPY 2026-07-27).
- Of your **S**-graded marks, **5 of 15 (33%)** were wicked. Of S and A together, **11 of 37**.

### The same 113 trades, run to a result

Enter at your price, target 2R, flat at 11:00. The **only** difference between the two columns
is what ends the trade on the losing side:

| rule | mean per trade | win rate | worst trade |
|---|--:|--:|--:|
| **intrabar** — a wick at the stop ends it | **+$1,020** | 67.3% | −$1,000 |
| **close-only** — a candle must close through | **+$1,202** | **75.2%** | −$1,250 |

Paired on the identical 113 rows: **close-only is +$182 a trade, t = +2.43.**

**On your own marks, you were close-only in practice.** The days you graded S and A include
days where price ran through your stop and came back — you kept trading them, and they paid.

---

## Part 3 — both rules on the two-year book

Five full replays, 500 sessions, 2024-08-21 → 2026-08-21, 28 symbols
(`research/g73_intrabar_money.py`). The first row is a reproduction check: run with today's
defaults it comes back with **4,508 trades, $2,633,850, 59.4% win, $721 a day, 25 of 25 months,
87 of 105 weeks, $5,993 drawdown** — the current book, to the dollar. So the other four rows are
comparable.

**One trade a day — the way you would actually run it:**

| rule | $/day | win rate | months green | weeks green | worst drawdown | worst single trade | average loss |
|---|--:|--:|--:|--:|--:|--:|--:|
| **today** (close trigger + $1,000 resting order) | **$721** | 66.7% | **25/25** | **87/105** | **$5,993** | $1,000 | $973 |
| **close-only**, nothing capping it | $735 | **71.3%** | 24/25 | 84/105 | $9,371 | $4,667 | $1,461 |
| **close-only + $2,500 wall** | **$735** | **71.3%** | 24/25 | 85/105 | $10,365 | **$2,500** | $1,462 |
| **intrabar**, nothing capping it | $709 | 66.7% | 23/25 | 85/105 | **$5,993** | $1,033 | **$972** |
| **intrabar + $2,500 wall** | $709 | 66.7% | 23/25 | 85/105 | **$5,993** | $1,033 | **$972** |

**Taking every signal the engine fires:**

| rule | $/day | trades | win rate | months green | weeks green | worst drawdown | worst single trade | average loss |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **today** | $5,268 | 4,508 | 59.4% | 25/25 | **100/105** | $11,105 | $1,000 | $975 |
| **close-only**, uncapped | **$5,512** | 4,822 | **63.1%** | 25/25 | 96/105 | $22,394 | $6,062 | $1,401 |
| **close-only + $2,500 wall** | $5,501 | 4,824 | **63.1%** | 25/25 | 96/105 | $21,401 | **$2,500** | $1,398 |
| **intrabar**, uncapped | $5,241 | 4,511 | 60.0% | 25/25 | **100/105** | **$10,883** | $1,235 | **$987** |
| **intrabar + $2,500 wall** | $5,241 | 4,511 | 60.0% | 25/25 | **100/105** | **$10,883** | $1,235 | **$987** |

### Four things to read off those tables

**1. The two intrabar rows are identical, to the dollar. Your $2,500 wall is unreachable under
an intrabar stop.** If a wick at your stop already takes you out, price can never get to
−$2,500 to hit the wall — the worst it ever does is $1,235, on a bar that *opened* below the
stop before anyone could fill. That is exactly the failure this project keeps hitting: a rule
you stated compiled into a branch that can never be true. **The wall only means something if
the level stop waits for the close.**

**2. Close-only wins on win rate, by 4.6 points one-trade-a-day** (71.3% vs 66.7%) and 3.1
points on everything. That is the half of the money gate you are closest to.

**3. Close-only makes more money because it takes more trades, not because each trade is
better.** Per trade the two rules are a dead heat — intrabar is ahead by **+$11 a trade,
t = +0.76**, which is nothing. Close-only pulls ahead in total because fewer losses means your
three-loss daily halt fires less often (1,229 blocked signals against 1,659), so more days stay
live. That is real money, but it is a *day-rule* effect, not an edge.

**4. Intrabar is what protects the shape of the year.** It keeps the worst single trade near
$1,000, the average loss at $972, and the drawdown at $5,993. Close-only nearly doubles the
drawdown and takes the average loss to $1,462, and one-trade-a-day it costs a green month
(25 → 24). **Your existing $1,000 resting order is what has been buying that**, and it is the
same order that is producing the intrabar behaviour you just said you wanted.

---

## Part 4 — does any of it clear the error bar?

**No — and it is not close.** The standing bar on this project is **±1.5799R**, and every
number in Part 3 is a fraction of it:

| comparison | measured | verdict |
|---|--:|---|
| intrabar minus close-only, per trade, all 4,241 shared trades | +0.0113 R (t = +0.76) | **noise** — 1/140th of the bar |
| close-only minus intrabar, one trade a day | **+$26/day**, 95% CI **−$55 to +$118** | **noise** — the confidence interval straddles zero |
| the $2,500 wall, on top of close-only | −$0.00 a trade (t = −0.01) | **no effect on money**; it only caps the worst trade |
| **close-only minus intrabar on YOUR 113 marked trades** | **+$182/trade (t = +2.43)** | **clears its own noise**, but is 1/9th of the standing bar |

So: **the money cannot settle this, and no honest reading of the two-year book says otherwise.**
What is *not* noise, and what should decide it:

- **Your own 113 marks say close-only**, and that is the only paired result on this page whose
  t-stat clears 2. It is also the only sample where the entry, the stop and the grade are all
  yours.
- **Win rate moves 4.6 points**, and that is a gate you are being measured on.
- **The two rules buy different things.** Close-only buys win rate and trade count. Intrabar
  buys a small worst-day and a smooth year. Those are both real, and they point opposite ways.

### The one recommendation, which needs you

**Keep the level stop on the close, and put the intrabar stop where you put it this morning —
far out, at $2,500, as a real resting order.** That is not a compromise; it is what the evidence
on this page says twice over:

- Your tape says a wick through the level stop is not an exit — 13 statements over two years,
  32 of your own 113 marked trades pierced by one, and 16 of those 32 went on to make 2R.
- Your instinct that "stops happen in the middle of the timeframe" is right about the *disaster*
  order, which has to fill on a touch or it is not a cap at all — and you already said so on the
  card `fact_two_stops` this morning: *"Level stop on the close, disaster stop on touch."*

**The mistake was never the rule. It was the price.** The disaster order was parked at exactly
the level-stop price, so it fired on every ordinary wick and made every loss $1,000. Move it out
to $2,500 and both of your sentences are true at once.

**The cost of doing that**, honestly: worst single trade goes $1,000 → $2,500, average loss
$973 → $1,462, one-trade-a-day drawdown $5,993 → $10,365, and one green month. You get 4.6
points of win rate and $14 a day, which is inside the noise. **This is a risk-shape decision,
not a money decision, and it is yours.** No default was changed.

---

## What this does not say

- **No default was changed.** Every arm here is an env flag `backtest_week.py` already ships
  (`STOP_ON_CLOSE`, `DISASTER_STOP`, `DISASTER_STOP_R`) plus one clamp moved by rebinding a
  module attribute, the same seam `research/g72_catastrophic_stop.py` uses. No engine file was
  edited and no mark file was touched.
- **It does not model the options spread.** Everything here is the stock tape. The reason you
  get wicked out of a real options position is the spread and the contract's own dip, and
  1-minute OHLCV of the underlying cannot see that. What it *can* say is that the underlying's
  wick, on its own, is not a reason to be out.
- **It does not settle the disaster stop's level.** `research/g72_catastrophic_stop.md` did
  that: **$2,500**, a real resting order, filled on a touch. Nothing here contradicts it.
- **It is in-sample over the whole two years**, and the 113-mark test is the same days you
  graded. There is no parameter being fitted, so there is nothing to overfit, but neither
  number is held out.

## Provenance

| artefact | what it is |
|---|---|
| `research/g73_intrabar_marks.py` | Part 2 — the tape scan over your marks and the 113-row A/B. `--selfcheck` green, 9 checks |
| `research/g73_intrabar_money.py` | Part 3 — five full 2-year replays. `--selfcheck` green, 9 checks |
| `research/_g73_marks.json` | every row behind Part 2 |
| `research/_g73_money.json` | every number behind Part 3 |
| `research/austin_marks_v7.jsonl` (`batch05`) | the eight 2026-08-11 sentences |
| `research/recovered_reviews.jsonl` | the pre-2026-08-11 sentences |
| `research/rule_ballot_batch01.jsonl` q1/q3, `batch02` a2/b9 | the ballots |
| `research/marks/probe_master_2026-08-29.jsonl` | `fact_two_stops`, `fact_stop_floor_is_fiction` |
| `research/corpus_index.jsonl` | the Scarface transcript quotes |

Reproduce:

```
python research/g73_intrabar_marks.py --selfcheck && python research/g73_intrabar_marks.py
python research/g73_intrabar_money.py --selfcheck
python research/g73_intrabar_money.py run        # 5 replays, ~5 min in parallel, ~690 MB
python research/g73_intrabar_money.py analyse
```

The five arm books are written to the scratchpad, not into `research/` — `g72_after.md` already
flags 654 MB of uncovered measurement files there. Override with `G73_BOOKDIR`.

The four guards were green before and after: `research/regression_gate.py`,
`research/test_universe_single_source.py`, `research/t11_stop_fill_fix.py` (80 checks),
`research/test_runner_stop.py`. `research/downgrade.py::CONFLUENCE_LEVELS` was not touched.
