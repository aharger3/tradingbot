# Why the engine is 40 minutes behind you on the one-candle rule

*2026-08-29. Seven case studies, then the whole two-year book, then the price.*

**The one-sentence answer: the engine cannot trade the one-candle rule until the
session has drawn the level for it, and on your seven cards the candle it used as
that level had not printed yet when you entered — a median of 37 minutes later.
Break-and-retest is on your minute because its level was already on the chart
before the bell rang.**

It is one reason, seven times, not seven unrelated reasons. But the fix does not
pay, and the last section of this page is the part you should read.

---

## 1. What the engine was looking at, at your minute

I walked the engine's own detector, bar by bar, on all seven one-candle-rule
charts where you wrote the minute you would have entered.

| chart | you entered | the block candle printed | the engine entered | block was born this many minutes after you |
|---|---|---|---|---:|
| MSFT 2025-08-29 | 9:38 | **10:15** | 10:19 | +37 |
| NFLX 2025-07-08 | 9:38 | **9:58** | 10:01 | +20 |
| NVDA 2026-05-11 | 9:43 | **10:30** | 10:32 | +47 |
| SPY 2025-05-21 | 9:45 | **10:26** | 10:33 | +41 |
| SPY 2026-06-17 | 9:48 | **10:37** | 10:42 | +49 |
| ACHR 2026-04-13 | 10:09 | **10:30** | 10:33 | +21 |
| GOOGL 2024-10-29 | 10:47 | **10:56** | 10:59 | +9 |
| | | | **median** | **+37** |

**Seven times out of seven the candle the engine traded off had not happened yet
when you pulled the trigger.** Once that candle printed, the engine took a further
**three minutes**, median, to enter. So of the ~41 minutes it is behind you,
**37 of them are "the level did not exist yet"** and three or four are the
detector's own confirmation lag.

That answers the question the task asked in the three-way form: the setup was
**absent**, not detected-and-vetoed and not detected-and-suppressed. On none of the
seven was there a one-candle-rule setup sitting on the bench at your minute. There
was nothing to veto.

Where the chain died at your minute, in the engine's own words:

- MSFT, NFLX, NVDA — **no confirmed swing break yet.** The engine had not even
  established that the session had made a structural high or low, which is the
  precondition for an order block existing at all. It could not know one until
  9:51 / 9:43 / 9:56 respectively.
- SPY (both), ACHR — a swing break existed but **the block was gone**: price had
  closed back through the candle, which retires it.
- GOOGL — the block candle **was not isolated**: its neighbours overlapped it, and
  a rule of yours from July 2026 says an order block has to stand alone.

## 2. The contrast — why break-and-retest is on your minute

The break-and-retest detector trades PDH, PDL, PMH or PML. **Those four numbers are
on the chart before the market opens.** The opening range is fixed at 9:35. So the
detector's job is only to watch for the four-step dance — break, leave, come back,
close through — and the first time price does it, it can fire.

On your seven break-and-retest cards the engine's median was **your exact minute**:
9:56 vs 9:57, 9:39 vs 9:40, 9:47 vs 9:47, 9:52 vs 9:56. It was late on three of
them and for a different reason — you entered before price had closed back through
the level and it waits for the close.

Measured over the same 120 sampled sessions, both detectors, every bar:

| | fires in 9:30–10:00 | fires in 10:00–11:00 | |
|---|---:|---:|---|
| break-and-retest, on your four levels | **0.98%** of bars | 0.62% of bars | **1.6× more likely early** |
| one-candle rule | **0.10%** of bars | 0.40% of bars | **4× less likely early** |

And the reason, from the same run — the first condition that was false on each bar:

| what stopped the one-candle rule | 9:30–10:00 | 10:00–11:00 |
|---|---:|---:|
| **no confirmed swing break yet — there is no block to find** | **40.6%** | **1.1%** |
| the block is gone: price closed back through it | 25.5% | 53.1% |
| the block candle is not isolated | 28.3% | 36.2% |
| the move off the block was not forceful enough | 4.0% | 3.7% |

**Four out of every ten bars in your first half hour, the one-candle rule is not
being rejected — it has nothing to look at.** After 10:00 that is one bar in a
hundred. Break-and-retest has no equivalent line, because its level was drawn
yesterday.

## 3. It holds at book scale, not just on seven cards

Across all 4,508 trades in the two-year book:

- **One-candle-rule trades enter a median of 47 minutes into the session (≈10:17).
  Break-and-retest trades enter at 24 minutes (≈9:54). Gap: +23 minutes, and the
  honest range is +20 to +27.**
- Paired properly, inside the same symbol and the same day, on the 3,588 sessions
  where both setups appear: the first one-candle-rule signal comes **+23 minutes**
  after the first break-and-retest signal (range +21 to +24), and it is the later
  of the two on **76.9%** of them.
- The order block candle a one-candle-rule trade uses prints at a median of
  **10:15**, and the entry follows a median of **6 bars** later — 77.6% of entries
  are within ten bars of their own block. The lateness is in the block, not in the
  wait after it.
- On 120 sampled sessions, a *valid* order block first exists at a median of
  **10:21**, and on **57 of 120 days one never exists at all before 11:00**.

So the 41 minutes on seven cards is a real +23 minutes over 4,508 trades. Your
sample exaggerated it, but it did not invent it.

## 4. Now the price — and it goes the wrong way

The whole point of chasing the 40 minutes is that early trades should be better.
**On this setup they are not.**

| one-candle-rule trades | how many | win rate | per trade | total |
|---|---:|---:|---:|---:|
| entered 9:30–10:00 | 97 | 50.5% | **$525** | $50,931 |
| entered after 10:00 | 385 | **41.0%** | **$748** | $287,934 |

The early ones win more often and **make less money per trade**. The difference is
inside the noise either way (anywhere from $704 worse to $260 better), so the fair
statement is: *being early is worth nothing measurable on this setup, and there is
no sign at all that it is worth something positive.*

Break-and-retest, for contrast, is very slightly better early (+$91 a trade, also
inside the noise), and the 84% rule loses money at both ends.

**And the number that settles it.** If you delete every late one-candle-rule trade
from the book — the strongest possible version of "it should have been early or not
at all":

| | everything you fire | one-trade-a-day |
|---|---|---|
| Trades | 4,508 → 4,123 | 499 → **499** |
| Win rate | 59.4% → 61.2% | 66.7% → **66.7%** |
| Dollars a day | $5,268 → **$4,692** | $721 → **$721** |
| Months green | 25 of 25 → 25 of 25 | 25 of 25 → **25 of 25** |
| Weeks green | 100 of 105 → 100 of 105 | 87 of 105 → **87 of 105** |
| Worst drawdown | $11,105 → **$12,441** | $5,993 → **$5,993** |
| Two-year total | $2,633,850 → −$287,934 | $360,380 → **unchanged** |

Under the way you would actually run it — one trade a day — **nothing moves at
all.** Not a dollar, not a month, not a week. The one-candle rule supplies the
day's first trade on **9 days out of 499 (1.8%)**. Break-and-retest supplies the
other 98.2%. Making the one-candle rule punctual cannot change a book it barely
appears in.

And on the all-trades book, being late is where its money is: the 385 late trades
earn $287,934 of the arm's $338,865.

## 5. What was actually available at your minute

Widening the question from "why was the one-candle rule silent" to "what did the
whole engine see", within four minutes either side of your minute:

- **Two of the seven — it was not late at all.** On MSFT 2025-08-29 the engine
  fired a break-and-retest on your PML at **9:40** and booked **+$1,260**. On NVDA
  2026-05-11 it fired on your PDH at **9:44** and booked **+$3,430**. You wrote
  9:38 and 9:43. The trade you wanted was already in the book — under a different
  name, on one of your own levels, one minute away. (The card you were shown was a
  second, later signal on the same chart that never traded. I cannot recover which
  direction you meant from your note, so treat this as two strong coincidences, not
  two proofs.)
- **One of the seven** — SPY 2026-06-17 — had a signal on your exact minute, on the
  opening range, graded X and thrown away.
- **Four of the seven** — ACHR, GOOGL, NFLX, SPY 2025-05-21 — **nothing.** Not a
  signal of any setup, any grade, any status, on that bar or the four either side.

Book-wide, on 90 of the 385 late one-candle-rule days (23%), the engine had already
traded that same chart earlier that morning — and 72 of those 90 earlier trades
were break-and-retest.

## 6. What I would do with this

**Stop trying to make the one-candle rule early.** The lateness is real, it is
mechanical, I can name the line of code, and fixing it is worth nothing under
one-trade-a-day and is not clearly worth anything under the all-trades book either.
Three of your seven had no swing structure at all at your minute, so no amount of
remembering older order blocks would have helped them.

**The finding that survives is the one underneath it:** your early entries look like
break-and-retest trades on your own levels, and the engine's break-and-retest arm is
already 1.6× more likely to fire in your first half hour and already supplies 98% of
the one-a-day money. Twice out of seven it had your trade, within a minute, and it
won both.

So the question worth the next deck is not *"can the one-candle rule be made
early"*. It is **"when you enter at 9:38, is the engine's break-and-retest arm
already there — and if it is, why did you get shown the wrong signal?"** That deck
would be built from break-and-retest fires before 10:00, and it would keep asking
for the minute, because the minute is the only field on this homework that has
produced a hard finding twice running.

---

*Every number here comes from a re-runnable script, none of which touches engine
code, a mark file or the book. `research/g75_lateness_cases.py` (the seven case
studies and the seven controls, walking the shipped detector bar by bar),
`research/g75_lateness_whatelse.py` (what the whole engine saw at his minute, via
the same replay the recall gate uses), `research/g75_lateness_book.py` (the clock at
book scale, paired within symbol-day), `research/g75_lateness_cause.py` (when each
setup's level can exist at all), `research/g75_lateness_gatecensus.py` and
`research/g75_lateness_brcensus.py` (which gate does the killing, early vs late, and
its break-and-retest control on the same 120 sessions), `research/g75_lateness_price.py`
(the money, using the board's own arithmetic imported rather than re-typed). 1R =
$1,000. Guardrails: the mark file was opened read-only and is unmodified, nothing
was committed or pushed, no API key printed, and all four protected tests re-run
green after this work — `regression_gate.py`, `test_universe_single_source.py`,
`t11_stop_fill_fix.py`, `test_runner_stop.py`.*
