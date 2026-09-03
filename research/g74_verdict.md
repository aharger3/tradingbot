# Verdict: the "one-candle rule is your most accurate eye" finding

*2026-08-29. I tried to break it. It broke.*

**The claim:** *"The one-candle rule is the engine's most accurate detector at 80%, and it is
blocked from trading by gates rather than by bad detection."*

**The verdict:** the first half does not survive. The second half was never measured by the
30 cards at all — it was measured somewhere else, on the two-year book, and that part still
stands on its own feet.

Every number below is re-derived from scratch in `research/g74_verdict_check.py` and
`research/g74_verdict_check2.py`. I did not reuse anybody's arithmetic. Your mark file was
opened read-only and is untouched.

---

## The short version

The 8-out-of-10 is real. What it means is not what it was read to mean.

1. **8 of 10 and 6 of 10 are the same answer.** At ten cards an arm, 80% could honestly be
   anywhere from 49% to 94%, and 60% anywhere from 31% to 83%. They overlap almost
   completely. Telling them apart would take **216 more cards**.

2. **25 of the 30 cards were signals the engine refused to trade.** Not one break-and-retest
   card and not one one-candle-rule card became a trade. Only the 84%-rule arm — the one that
   scored worst — was made of real trades.

3. **Five of the cards had a stop of five cents or less. Two had a stop of zero.** The TSLA
   card is a one-cent stop that the file records as a $164,500 win. The profit column on this
   homework is not usable, in either direction.

4. **On the one-candle rule you never once agreed with the engine's trade.** On seven cards
   you wrote a minute. Seven times out of seven your minute was earlier — a median of
   **41 minutes earlier** in a 90-minute window. On break-and-retest the engine was on your
   minute: four of seven within four minutes, median difference zero.

5. **The cards you graded are 1-in-482 of what the engine actually does.** The ten
   one-candle-rule cards all sat on one of your six levels. Of the 482 one-candle-rule trades
   in the book, **28 do — 5.8%.** Apply all three filters the graded cards passed and
   **exactly one trade of 482 qualifies.**

---

## Taking each one properly

### 1. The ranking is noise

| arm | score | where it could honestly be |
|---|---|---|
| one-candle rule | 8 of 10 = 80% | 49% – 94% |
| break-and-retest | 7 of 10 = 70% | 40% – 89% |
| 84% re-entry | 6 of 10 = 60% | 31% – 83% |
| **all thirty** | **21 of 30 = 70%** | **52% – 83%** |

One-candle-rule minus 84%: **+20 points, but honestly anywhere from −19 to +52.** Fisher's
exact test p = 0.63. Same story for the other two pairs. Nothing is separated from anything,
including from the 70% overall.

To call 80% different from 60% you need 82 cards per arm. You have 10.

**What does survive:** all three arms sit inside the same band, and neither of the two you
suspected was broken came out below it. *"They are not broken at spotting setups"* holds.
*"This one is the best"* does not.

### 2. The three arms are not the same kind of thing

The deck picks its cards cleanest-first — days where the engine raised no objection at all.
That works only if each setup has enough clean days to fill ten slots. Across two years:

| arm | days the engine calls S | of those, zero objections | clean cards the deck could take |
|---|---:|---:|---|
| break-and-retest | 5,467 | 1,111 | all 10 |
| one-candle rule | 964 | 156 | 9 of 10 |
| 84% re-entry | **70** | **6** | **3 of 10** |

The 84% rule has six clean days in two years. The deck took three of them and filled the
other seven slots with days the engine had already marked down. **The arm that scored lowest
was handed the worst cards, by construction.** That is a property of the deck, not of your eye
and not of the detector.

The break-and-retest arm has its own version of the problem: all ten of its cards are
near-zero-risk rows — median stop **4 cents**, two of them zero — which the engine discards on
sight. The one-candle-rule arm's median stop was 25 cents.

### 3. The money column is broken, and where it isn't, it doesn't follow you

Of the 30 cards, 25 were never traded. Their profit figure is computed off stops as thin as
one cent, which is why the biggest untraded "winner" anywhere in the book prints as
**$58 million on one signal**. Nobody should read those numbers.

Read them anyway, as an upper bound on how much signal is in there: your yes-cards and your
no-cards are **indistinguishable on money** — the chance a yes-card outperformed a no-card is
55%, coin-flip, p = 0.65. And the naive ranking comes out **backwards**: the one-candle-rule
arm is the *worst* of the three on these 30 cards (8 losses of 10, 2 winners) and the 84% arm
the best (5 winners of 10).

Either way the conclusion is the same: **this homework measured agreement, not profit.**
Nothing in it tells you a one-candle-rule trade makes money.

### 4. What actually moved your answer was the day, not the setup

I tested seven measurable things against your yes/no. Only one separated them:

| what | your yes-days | your no-days | separated? |
|---|---:|---:|---|
| **how much the day trended** | **0.145** | **0.072** | **yes, p = 0.014** |
| displacement of the impulse | 1.72 | 1.66 | no |
| how late the engine's entry was | 45 min | 61 min | borderline, p = 0.053 |
| how far away 2R was | 3.11 | 2.91 | no |
| engine objections raised | 0.19 | 0.44 | no |
| how many S signals that day | 3.4 | 3.6 | no |
| size of the stop | 36c | 31c | no |
| **which setup it was** | — | — | **no, p = 0.70** |

Sorted by trend strength: **the ten trendiest days you said yes to all ten.** The ten
choppiest, five of ten. That is your own word — chop was your most-given reason for saying no,
three times.

And the arms were not balanced on it. The one-candle-rule arm drew the trendiest sessions of
the three (0.151 against break-and-retest's 0.103 — 46% more). Some of its 80% is that draw.

### 5. The load-bearing assumption fails outright

This is the one that matters for the unlock.

A one-candle-rule signal never names one of your levels — its "level" is an order block, which
is a candle. The deck could only use a day where the order block **happened to land on** one
of your six. That is true of **84 of 964** one-candle-rule S days: **8.7%**.

So the ten cards you graded are the 8.7% slice that looks most like your own setup. The
other 91.3% sits on a level you have said you do not watch, and you have never been shown one.

It is worse than that when you look at what the engine actually books today:

| of the 482 one-candle-rule trades in the book | count | share |
|---|---:|---:|
| sit on one of your six levels | 28 | 5.8% |
| are an S on your ladder | 131 | 27.2% |
| have zero objections against them | 21 | 4.4% |
| **all three at once — the profile of the 10 you graded** | **1** | **0.2%** |

**One trade in 482.** The homework and the trading barely touch. Removing the wick-only rule,
the 0.4% stop cap and the higher-timeframe veto has nothing to do with level coincidence, so
the ~1,260 extra trades an unlock would add come overwhelmingly from the 91% you have never
seen. Assuming they look like your ten is the whole argument, and it is unsupported.

---

## The one thing here that is not noise, and it points the other way

You wrote your entry minute on 20 of the yes-cards. That field is the most valuable thing on
the page, and it says something the headline missed completely:

| arm | how far behind you the engine was | within 4 minutes of you |
|---|---:|---|
| break-and-retest | **0 minutes** | 4 of 7 |
| 84% re-entry | +31 minutes | 0 of 6 |
| **one-candle rule** | **+41 minutes** | **0 of 7** |

Every single one-candle-rule card, the engine was late — by 12, 23, 24, 41, 48, 49 and 54
minutes. You enter at 9:38. It enters at 10:19.

So when you said yes to those eight charts, you were not agreeing with the engine's trade.
You were finding your own trade, most of an hour earlier, on a chart the engine had flagged
for a different reason. **"Late" is one of your own rejection words.** The honest reading of
the one-candle-rule arm is not *"the engine's best eye"* — it is *"the engine eventually gets
there, long after you would have."*

---

## What still stands, untouched by any of this

The gate work was priced on the two-year book, not on these 30 cards, so none of it depends on
the headline. I re-checked the three numbers it rests on and they reproduce exactly:

- one-candle rule: **482 trades, +0.70 per dollar risked, $338,865** — best per trade in the book
- break-and-retest: 3,820 trades, +0.61, $2,322,799
- 84% re-entry: 206 trades, **−0.14, −$27,815** — the only losing setup

So: don't put a minimum stop back on the one-candle rule; the higher-timeframe veto is still
worth looking at; the 84% rule still loses money. Those are book facts and they are unaffected.

**The one thread that keeps the story alive, and I will not pretend otherwise:** ranked by
those book numbers the order is one-candle rule > break-and-retest > 84% — the *same* order as
your 8/7/6. Three data points is not evidence, and the 84% rule scoring badly on both is
explained just as well by it being a tiny marginal rule with 70 instances in two years. But it
is the one thing that did not break, and it would be worth a real test.

---

## How much weight to put on it

**Low. Do not reorder any work because of the 80%.**

What you can take from the 30 cards:

- **Take:** all three setups land around 70% — neither of the two you suspected is broken at
  spotting setups. That was the question you asked and you got an answer.
- **Take:** the engine is on your minute for break-and-retest and 40 minutes behind you on
  the one-candle rule. Hard, repeatable, and worth chasing.
- **Take:** whether the day trends is what moves your answer, and the engine has no rule for
  chop at all.
- **Leave:** the ranking between the three setups.
- **Leave:** any claim that this homework says something about money.
- **Leave:** the idea that unlocking the gates gives you more of the ten charts you liked.

If you want the ranking answered properly, more cards of this kind will not do it. The deck
would have to be built from **trades the engine actually takes**, with the arms matched on how
confident the engine was and on how much the day trended, and it would need to keep asking
for the minute — that field, not the yes/no box, is where every hard finding in this pass came
from.

---

*Scripts, both re-runnable and neither touching engine code, a mark file or the book:
`research/g74_verdict_check.py` (precision, error bars, money, confounds, population) and
`research/g74_verdict_check2.py` (what the cards were, selection depth, entry minutes,
what predicts a yes). Outputs `research/g74_verdict_check.json`,
`research/g74_verdict_check2.json`, `research/g74_verdict_eligible.json`,
`research/g74_verdict_ocr_traded.json`. The eligibility census is the deck builder's own
`load_s_days()` called directly, not re-derived. Guardrails: mark files read-only and
unmodified, nothing committed or pushed, `signal_runner.py` and `omen_bot.py` clean, no API
key printed. All four protected tests re-run and green after this work:
`regression_gate.py`, `test_universe_single_source.py`, `t11_stop_fill_fix.py`,
`test_runner_stop.py`.*
