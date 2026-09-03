# The 25 cards you graded on 29 August — what they actually say

*Every number here comes from two scripts you can re-run:
`research/g73_marks25_precision.py` (writes `g73_marks25_precision.json`) and
`research/g73_marks25_retest_cents.py`. Your answer file
`research/marks/probe_g71_homework_s3_2026-08-29.jsonl` was opened read-only and
is byte-identical to the committed copy.*

---

## Lead with the money

Those 25 symbol-days are the engine's **own** shortlist — its own grader looked at
two years of tape and said "these are S trades". On those 25 days the engine
actually pulled the trigger on 13 of them, took 17 trades, and **lost $5,886**.
On the 9 of those days that you also called S, it lost **$3,568**.

So the headline "64% of the engine's S calls match your eye" is true and it is
not worth what it sounds like. Agreeing with you about which *day* is good is not
the same as agreeing with you about which *minute* to buy — and the minute is
where the money is. That is the rest of this page.

---

## 1. The 64%, and why you should not rank the three setups

| what the engine claimed | you said yes | rate | 95% confidence |
|---|---:|---:|---|
| **all 25 cards** | 16 of 25 | **64.0%** | 44.5% – 79.8% |
| the 84% re-entry rule | 6 of 10 | 60.0% | 31.3% – 83.2% |
| the one candle rule | 6 of 8 | 75.0% | 40.9% – 92.8% |
| break-and-retest | 4 of 7 | 57.1% | 25.1% – 84.2% |

**Do not read the middle column.** Every one of those confidence ranges is
**52 to 59 points wide** — wider than the gap between any two of them. Tested
directly, no pair separates: 84% vs OCR p = 0.64, 84% vs B&R p = 1.00, OCR vs
B&R p = 0.61. The honest sentence is *"the engine's S calls land somewhere
between four-in-ten and eight-in-ten, and this sample cannot tell the three
setups apart."*

The 64% is also **not** comparable to the 37.7% precision on the board. That one
asks "did the engine fire on a day Austin refused entirely" over an unselected
corpus. This one asks "of the days the engine's own S-grader already picked, how
many does Austin's eye also call S". Different question, different sample. They
must never be quoted side by side as if one improved on the other.

---

## 2. Your nine rejections are a specification. The engine fails eight of them.

| your reason | times | does the engine have this check | did it fire |
|---|---:|---|---|
| **no displacement** | 3 | yes — `downgrade.no_displacement` | **0 of 3** |
| **chop** | 3 | only partly — the engine knows chop *on a level*, not chop as a market state | **0 of 3** |
| **late** | 2 | **no** | — |
| level not respected | 1 | yes — `downgrade.level_not_respected` | **0 of 1** |
| no retest | 1 | yes — `downgrade.no_retest` | **1 of 1** |
| other (free text) | 2 | — | — |

**One out of ten.** The engine's ladder agreed with exactly one of the ten
reasons you gave.

### The three things you can see that the engine cannot compute at all

These are the most valuable lines on this page.

**1. "Late" is not in the engine, in any form.** The engine does have something
it calls `[late]`, but it means *"this level was already broken earlier in the
session, so it's dirty"* — a level-history test, not a clock test. The only
clock rule in the whole system is the 09:30–11:00 window. You rejected AMD
2025-09-08 partly because 10:37 is late; the engine's window says 10:37 is
perfectly fine, and the engine's card for that day **is** 10:37. Same for
HOOD 2025-11-28 at 10:21, and for ORCL 2025-02-18 where you wrote *"took too
long for the entry"*. Three of the nine rejections carry a lateness idea, and
there is nowhere in the code that idea could live.

**2. "Chop" as a state of the day.** The engine's nearest thing,
`level_not_respected`, only counts closes sitting *on the broken level*. Your
chop rejections (HOOD, AAPL 2026-03-11, QQQ 2025-12-22) are about how the whole
chart looks. There is a number already sitting on every card that might capture
it — a session efficiency ratio computed by the card pre-filter — and **nothing
in the engine gates on it**. On three cards it is a hint, not a result; it is
worth a proper measurement.

**3. Displacement is broken, and the sample shows exactly how.** The engine tests
displacement in two places and both fail here:

- `downgrade.no_displacement` fired on **none** of your three no-displacement
  rejections. Worse, the one card where it *did* fire — INTC 2026-03-24 — is a
  card you said **yes** to.
- The legacy `[nodisp]` tag fired on **all 7** break-and-retest cards, yes and no
  alike. A flag that is always on carries no information.
- And the tag exists **only** on the break-and-retest path. Two of your three
  no-displacement rejections are one-candle-rule cards, where **no displacement
  test of any kind runs at all**.

### The one time it agreed — and confluence overrode it

AVGO 2025-12-03. You rejected it for **no retest**. The engine's `no_retest`
fired too. Then the confluence +1 cancelled it out, the day graded S, the card
was served to you, and the engine traded it and lost $1,000.

That is the S = one-downgrade-plus-confluence arithmetic working exactly as
written, on the one card where the engine's own check had it right. Worth your
attention: **should confluence be allowed to rescue a missing retest?**

---

## 3. The entry minute — this is the finding

21 of your 25 notes carry a time. 20 parse; `9:%5` on IWM 2026-08-06 is a typo
and is **not** guessed at. Of those 20, three are you evaluating a candidate you
then rejected, and two are narration (on MSFT 2024-09-13 you wrote *"9:47 is
what you liked"* — that is you reading the engine's mind, not naming your own
entry — and worth noting, the engine's first signal that day was 09:47 to
the minute; on TSM 2025-11-26 the 9:35 is an obstacle you point at). That leaves
**15 clean "this is where I'd get in" timestamps**, and every classification is
written down next to the sentence it came from in the JSON.

On those 15:

| compared against | median gap | exact | within 1 min | within 3 min |
|---|---:|---:|---:|---:|
| the signal on the card you were shown | **+24 min late** | 1 | 3 | 3 |
| the *nearest* signal the engine had that day | **+0 min** | 5 | 7 | 8 |
| the first signal of the card's own setup family | **+24 min late** | 0 | 2 | 2 |

Read those two rows together, because together they are the answer:

> **The engine's eyes are on time. Its trigger finger is half an hour late.**

Somewhere on the day the engine usually does see something at your minute — the
median gap to its *nearest* signal is zero. But the signal it promotes to S,
the one it put on your card, is a **median 24 minutes** after you would have been
in. By arm: break-and-retest is essentially exact (median −0.5 minutes), while
the one candle rule is **+44.5** and the 84% rule **+31**. The 84% rule is a
re-entry so some lateness is built in; the one candle rule has no such excuse.

### Then the harder number

Look at the minute itself, ±2 bars, on those same 15 cards:

- On **7 of 15** the engine has **no signal at all** within two minutes of your
  entry — COIN, GOOGL, AAPL 2026-04-17, SPY 2025-05-21, INTC, ACHR 2026-04-13,
  META. Not a bad grade. Nothing.
- On the other 8 it does have a signal, and on **5 of those 8 it took no trade** —
  it saw the setup and graded it `X`, which in this system means *"I should not
  have fired"*. ACHR 2026-06-16 is the clean example: four signals at your
  minute, all four graded S on your ladder, all four graded X by the legacy
  grader, zero trades.
- It actually **traded at your minute on 3 of 15 — 20%.**

**This corrects the board.** `DIRECTION.md` currently says the engine is *"never
silent on his S days — 0 of 34 — and its timing is exact (median +0.0 bars)"*.
That was measured at the level of a whole day. At the level of the minute you
would have pressed the button, it is silent 47% of the time and it trades 20% of
the time. Both statements are true; only the second one is about trading.

That is the honest answer to *"8% of the book was a candle late or early"*.
Measured against the engine's own nearest signal, the timing looks fine.
Measured against **you**, half the entries do not exist and the ones that do
arrive 24 minutes after the bus left.

---

## 4. Five things you said that read as rules — ballot candidates, not code

Nothing below has been wired into anything. These are questions for you.

**a. Confluence rescuing a downgrade — CONFIRMED, in your own words.**
On MSFT 2025-08-29 you wrote *"BR OCB confluence, not perfect because no
displacement but you get a +1 9:38 is the entry"*. That is precisely the
arithmetic in `downgrade.py`: one downgrade, plus confluence, still S. It is the
first time you have stated it unprompted while grading. (The engine reached the
same S on that card by a different route — it never noticed the missing
displacement at all.)

**b. Displacement is required of EACH part, not the pair — NEW, and the engine
cannot express it.** NVDA 2025-06-24: *"technically it is an OCR and BR just
neither of the parts have displacement"*. Today the engine computes displacement
**once**, on the bar that broke the trade's level. The confluence test
(`has_confluence`) checks that a break-and-retest and a one-candle-rule are both
present and geometrically usable — and never asks whether either one displaced.
So "the BR displaced but the OCR didn't" is currently unsayable. **This is a new
variable, not a tuning.**

**c. A retest tolerance — and we can price it exactly.** AVGO 2025-12-03:
*"9:33 can be a great break of pdl but the retest missed by a few cents"*.
Measured (`g73_marks25_retest_cents.py`): the break was the 09:30 bar closing
below the prior-day low at $379.79, price cleared it at 09:31, and the retest at
09:33 topped out at $379.70. **It missed by 9 cents.** That is **0.04 of a bar
range** and 0.024% of the price.

  The engine's retest step ships with **zero tolerance — an exact touch.** Your
  one tolerance unit, the 25%-of-a-bar-range figure used everywhere else in the
  system, would have been **51 cents** here — it would have let this through five
  times over. The only widened setting that exists is off by default and is set
  to a **whole** bar range, $2.03, which is far too loose.

  So the retest step is the one place in the engine that does not use your
  tolerance unit, and it is the reason a 9-cent miss kills a setup you liked.
  **Question for you: should the retest use the same 25% band as everything
  else?**

**d. Your own trade stopping out and reclaiming — flagged to the intrabar track.**
SPY 2026-06-17: *"i see a fake out S trade at 9:48 ... and if you went with my
trade it wouldve stopped out and reclaimed"*. You are describing a stop being
taken out intrabar and price coming back. That bears directly on the open
question about the resting −$1,000 order, and it is your own tape rather than a
simulation. **Handed to whoever owns `g73_intrabar_*`.**

**e. S and tradeable are not the same thing — and the ladder cannot say this.**
ACHR 2026-04-13: *"10:09 would never trade because look how the candles are but
jsut good for you to know"*. You graded it **S** and you would **not take it**.

  Today the ladder has four values — S, A, C, none — and `none` means *"I looked
  and refused the day"*. There is no way to record *"structurally this is a clean
  S and I still would not press the button"*. That is a **second axis**, not a
  fifth grade, and it may be the missing piece: a system tuned to reproduce your
  S grades would take this trade, and you would not.

  If that distinction is real, every recall number in this project is measuring
  the wrong target — we are chasing your *grades*, and what pays is your
  *trades*. **This is the one question on this page only you can answer.**

---

## 5. Where the engine stands after these 25

**Precision.** On the engine's own S nominations, your eye agrees **16 of 25 =
64%**, 95% range 44.5% to 79.8%. That is a new measurement, not an update to the
37.7% on the board — the 37.7% asks a different question on a different sample,
and this instrument asked a **yes/no** ("is this an S trade?"), so a "no" here
could still be an A or a C on your ladder. It is **not** evidence that the day is
a `none`, and it cannot be folded into the day-level precision number.

**Recall: these 25 cards cannot measure it, and must not be folded in.**
Every card was chosen *because* the engine fired and graded it S. On a sample
selected that way recall is 25 of 25 by construction. Pooling them would move
held-out recall from 163/278 (58.6%) to 179/294 (60.9%) **for free, without the
engine changing at all**. That is not an improvement; it is the same flattery
that the recall-router bug produced yesterday, arriving through a different door.

**So recall still reads 58.6% against a 90% gate**, unchanged, and the corpus
grows by 25 judged symbol-days (1,147 → 1,172) and 16 S days (287 → 303) — none
of which repeat anything you had already graded. Those 16 are worth their weight
in the *next* deck, not in this number.

**And the real standing:** the engine reaches your day 6 times in 10 and your
minute 2 times in 10. The gap between those two numbers — not the mean R, not
the exits — is where OMEN is losing.

---

## What I would do next, in order

1. **Answer 4(e).** Is "S but not tradeable" a real distinction? Everything
   downstream depends on which target we are chasing. One sentence from you.
2. **Answer 4(c).** Retest tolerance: exact touch, or your 25% band? It is a
   one-line change and it is measurable against the whole 2-year book.
3. **Build the lateness variable.** Three of nine rejections point at it and the
   engine has no organ for it. That is a measurement job, not a decision.
4. **Autopsy the 7 silent minutes** — COIN, GOOGL, AAPL, SPY, INTC, ACHR, META.
   Seven charts where you saw a trade and the engine saw nothing within two
   minutes. That is the highest-yield miss file this project has.

---

*Scripts: `research/g73_marks25_precision.py` → `g73_marks25_precision.json`
(precision, reasons, timing, displacement, money);
`research/g73_marks25_retest_cents.py` → `g73_marks25_retest_cents.json`
(the 9-cent measurement). Regression gate, universe test, stop-fill test and
runner-stop test all re-run green after this work; no engine file was touched.*
