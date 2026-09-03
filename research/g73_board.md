# The board — Saturday 29 August, evening

Five agents ran this afternoon. **Nothing was committed or pushed, no judgement file was
touched, and all four safety tests are green** — I re-ran them myself just now. Your 25 new
answers are saved, staged and visible to git. Your judged days now count **1,178, up, never
down**. The stop-fill test that was red on this morning's board is green again, 80 checks,
fixed the way the board asked (the test controls the resting order; no engine code changed).

---

## 1. The $721 a day is at prices you could not have paid

This is the biggest thing found today and it re-prices every dollar on the board.

Eighty-three per cent of the trades in the book are filled at a price the minute had
**already traded before the signal existed**. Only an order already resting at the level
gets that price. A person tapping a button does not, and neither does a robot reacting to
the close of the bar.

The split is brutal and it is straight out of the book, no model needed:

- 3,748 trades filled at an intrabar price average **+0.71R**.
- 760 trades filled at the price you could actually see — the signal minute's close —
  average **about zero** (−0.02R).

Every dollar of the edge is in the fills.

| one trade a day, 500 sessions | per day |
|---|---:|
| the book as published | **$721** |
| paying the signal minute's closing price | **$111** |
| a robot buying the next minute's open | **$131** |
| you, one minute late | **$161** |
| you, two minutes late | **$194** |
| you, five minutes late | **−$81** |

Every one of those bands touches or crosses zero. Note where the collapse happens: **at zero
delay.** Your reaction time is not the problem — the price is.

Two things soften it. First, **490 of your 499 one-a-day trades happen between 9:30 and
9:59**, so this is a half-hour job, not a 90-minute one. Second, this is a re-pricing of the
same trades, not a rebuild — a real rebuild also changes which trades fire. That rebuild is
one command and about forty minutes of computer time, and it is the first thing an agent
does next. Until it comes back, **$111 a day is the honest floor and $721 is the ceiling**,
and nobody should build anything expensive in between.

---

## 2. Options are real, and the tape has been free on your key the whole time

Three separate write-ups in this repo concluded there was no options data. All three tested
the one options endpoint your plan does not include. I re-ran the check myself this evening:
**minute bars on expired option contracts come back fine, two years back**. Quotes, trades,
snapshots and anything older than two years come back blocked.

So for the first time the real option prices for your own trades could be used. On 204 real
trades in COIN, TSLA and PLTR, both instruments priced off the same two minute closes:

| per trade | result |
|---|---:|
| shares | **−$20** |
| options at the middle of the spread | **+$56** |
| options after commissions | **−$7** |
| options, commissions, 2c round-trip spread | **−$108** |
| options, commissions, 5c round-trip spread | **−$260** |

Options and shares are the **same trade** until the spread bites. Only the nickel case
clears its own error bar. **The spread is now the whole options question**, and it is the one
thing this key will not tell you — that is what the $80 data month would buy, and it is worth
buying when you want that answer, not before.

Two things only the real tape could say. **On three days out of four a same-day-expiry
contract did not exist on these names** — every options number this project has ever
published assumed one did. And risking $1,000 ties up about **$16,200 of premium**, not the
$8,000 that was modelled — still far cheaper than shares, but not by the factor claimed.

One live setting is wrong and I did not touch it: the sizer assumes each contract moves 50
cents per dollar of stock; measured, it is 42. **It is risking about $840 where it thinks it
is risking $1,000.**

---

## 3. Your stop: you have been trading intrabar without knowing it

You ratified this morning: **level stop on the candle close, disaster stop on touch.** Both
are your rules and they do not conflict. But the disaster order was parked at *exactly the
same price* as the level stop, so **every ordinary wick kills the trade** and all 1,775
losses in the book book exactly −$1,000. You have been looking at an intrabar book while
believing it was a close-only one. Your new sentence was a correct reaction to a wrong order
price, not a wrong rule.

The record is stronger than the repo said: **thirteen dated sentences** say the level stop is
close-only, eight of them in one sitting. The repo said five.

- **Your own tape:** 32 of your 113 marked trades were wicked through the stop without
  closing through. **16 of those went on to make 2R or better.**
- **Your marks, priced:** close-only is worth **+$182 a trade** on them, and it is the only
  version of this test that clears its own noise.
- **The book cannot decide it:** close-only is worth **+$14 a day**, error bar −$63 to +$102.

What it costs is the shape of a bad day, and only you can price that: **worst trade $1,000 →
$2,500, average loss $973 → $1,462, worst drawdown $5,993 → $10,365, and one green month
lost (25 of 25 → 24 of 25).** What it buys is **+4.6 points of win rate**, 66.7% → 71.3%.

The recommendation is the thing you already chose twice today: **level stop on the close,
disaster order resting out at $2,500 on touch.** One line, not applied.

And note how this ties to §1: **resting orders are what work when nobody is watching, and a
resting stop is exactly what a wick takes out.** Close-only means something has to be
watching every minute. That something is the bot, not you.

---

## 4. The engine agrees with you about the day, not about the minute

On the 25 cards you graded today — the engine's own best nominations out of two years — you
agreed with **16 of 25, 64%**. On those same 25 days the engine took 17 trades and **lost
$5,886** (I checked that against the book myself).

Fifteen of your notes carry the minute you would have entered. Measured against the whole
day, the engine's timing is exact — median zero minutes off. Measured **at your minute**:

- on **7 of 15** it has no signal at all,
- on 5 more it has one it grades "should not have fired",
- it actually took a trade on **3 of 15 — 20%**.

The direction doc says the engine is never silent on your S days and its timing is exact.
True for the day. **Not true for the minute, and the minute is where the money is.**

Two specifics worth your attention:

- **Three of your nine rejections were "too late", and there is nowhere in the engine that
  idea could live.** The only clock rule is the 9:30–11:00 window, which lets 10:37 through
  happily.
- **One rejection cost 9 cents.** On AVGO the retest missed the prior day's low by nine
  cents and the engine threw the setup away, because the retest is the only place in the
  system that demands an *exact* touch instead of your 25%-of-a-bar band — which would have
  been 51 cents there.

And one sentence of yours the grade ladder cannot hold: *"would never trade because look how
the candles are"* — on a card you graded S. If **S-but-not-tradeable** is real, then every
recall number in this project is chasing your grades when what pays is your trades.

---

## 5. The mentors are not beating you. They are not posting their losses

3,547 calls pooled, 2,305 replayable. If OMEN had traded only the days they called it makes
**$675 a trade against $564 everywhere else** — but the error bar runs −$35 to +$261, so
their day-picking is **not proven**, only suggestive.

What is proven:

- **Every one of the 54 dollar figures in those calls is a profit.** Zero losses. Smallest
  $268, median $3,093, largest $12,500.
- **The two trade-review channels hold 56 reviews and not one loss.**
- **Scarface posts 720 entries and follows up on 247.** The futures room follows up on 23 of
  588 and claims a 94.7% win rate.
- **Scored on the tape:** the calls he reports as wins genuinely score +0.43R and the ones he
  reports as losses genuinely score −0.82R — he is honest about what he reports. The 147 he
  **never mentions again score −0.14R**. Put the silence back in and his 79% becomes
  **47.5%**. Yours, one trade a day, is 66.7%.
- That gap clears its own error bar (p = 0.009), which almost nothing in this project does.

Their timing is *later* than yours, not earlier, and a perfect exit on their calls — selling
the exact session high — still only averages 1.21R, under your own 2.0 gate.

TradeZella cannot take this data: **there is not a single exit price anywhere in the
corpus.** Your own broker fills would import cleanly. That is a different project, and a
real one if you want it.

---

## What agents are doing next — no input needed from you

1. Rebuild the two-year book paying a fill you could actually get, then re-price every number
   on this page against it — one command, about forty minutes of computer time.
2. Back up the bar archive, because the 16,817 cached days from before last August can no
   longer be re-downloaded on this key.
3. Finish pricing the rest of the book on the real option tape — free, about a day of paced
   downloading.
4. Build the arming alert — *the break has happened, the retest is pending* — into the
   Discord bot you already have, so the ping arrives before the entry minute instead of on it.
5. Measure the 25%-of-a-bar retest band across the whole two-year book, so the answer is
   sitting there the moment you say yes.
6. Build a way to measure "too late", because that idea currently cannot be expressed
   anywhere in the engine.
7. Widen the mentor-day comparison with the sessions and bars it could not reach, since that
   error bar is the only thing standing between "suggestive" and "settled".
8. Keep your 25 new answers **out** of the recall score and put the 16 you agreed with into
   the next deck instead.

## How you can help — ordered by what it unblocks

1. **Open your Polygon billing page and tell me which plan you are on — 5 minutes.** The key
   behaves like the free tier on both stocks and options, so either the $29-a-month plan
   lapsed or you are paying for nothing; it also decides whether re-pricing the whole book
   takes twenty minutes or a full day.
2. **Yes or no: level stop on the candle close, disaster order resting at $2,500 — 2
   minutes.** It is what you chose twice today, and nothing changes until you say it, because
   it makes your worst possible trade $2,500 instead of $1,000.
3. **Yes or no: should the retest use the same 25%-of-a-bar band as everything else — 2
   minutes.** It is one line, and it is the only place in the engine that demands an exact
   touch.
4. **One sentence: is "S, but I would never trade it" a real distinction you mean — 5
   minutes.** If it is, we are measuring the wrong thing everywhere and should be chasing
   your trades, not your grades.
5. **Still waiting from this morning: yes or no on switching high-of-day / low-of-day on
   properly — 2 minutes.** Measured at +$338,000 over two years and seven more of your S
   days, with no month lost.
6. **Confirm the fallback: on a day you cannot look at your phone, the day is skipped and
   nothing fires on its own — 1 minute.** That single rule is what keeps this legal at every
   prop firm and what stops it becoming the robot they all ban.
7. **Send the prop firm one more question — 10 minutes to write, days for them to reply.**
   Ask whether a human tapping *confirm* on a page, which then places the order, counts as
   manual execution; their only blessed automation removes the human tap, which is the
   opposite of what you want.
8. **When the next deck is ready, grade it — 30 to 40 minutes, honestly, not two.** More of
   your marks is still the only thing that moves recall, and recall is 58.6% against a 90%
   gate.

---

## What did not survive checking

- **"Deleting the resting $1,000 order is worth +$154 a day"** — from this morning's board.
  Two independent full replays now say **+$14 a day, error bar −$63 to +$102**. The case for
  that change is win rate and risk shape. It is not dollars.
- **"83% of the book fills at the level"** — I checked this myself. 83% fill at a price that
  is *not* the signal minute's close, but only **41%** fill exactly at the level price. The
  half that matters holds: the trades paying a visible price earn about nothing.
- **"54 dollar figures across 112,000 messages"** — it is 54 among the 3,547 calls we could
  parse, not a sweep of every dollar sign in the rooms. Zero losses inside that slice still
  holds, and the follow-up rate and the tape test are the stronger evidence anyway.
- **"The engine is never silent on your S days and its timing is exact"** — true at the day
  level, wrong at the minute level. Silent at your minute on 7 of 15, traded on 3.
- **"You settled the wick question five times"** — it was eight in one sitting and thirteen
  dated overall. And one sentence long quoted as a stop-trigger rule (*"trends respect
  candles with wicks better"*) was you answering **where to put** the stop, not what fires it.
- **The $2,500 disaster wall can never fire while the order sits at $1,000** — the two
  versions of the book come out byte-identical. That is the third time this project has
  measured a rule that cannot be reached.
- **Your 25 new answers were deliberately kept out of the recall score.** Pooling them would
  have read 60.9% instead of 58.6% with no engine change at all — free flattery, the same
  shape as the bug that was fixed yesterday. **Recall stands at 58.6%.**

---

*Behind the numbers: `research/g73_oneclick_design.md`, `research/g73_polygon.md`,
`research/g73_intrabar_stops.md`, `research/g73_marks25_report.md`,
`research/g73_mentorbook.md`, and the scripts named inside each. I independently re-ran the
four safety tests, the Polygon entitlement probe, the fill-mode census, the money on your 25
cards and the judged-day count before writing this page.*
