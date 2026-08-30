# Three books, three headlines, one file name — and what honest fills actually cost

*2026-08-30. An independent second look at the claim in `research/g76_rebuild_verdict.md`
that "$721 a day is dead" and that honest fills leave $0 to $114 a day. Everything below was
re-derived from the archive by `research/g80_dollar_reconcile.py`, which reads only — no
mark file was opened, no engine file was touched, nothing was committed or pushed, and no
request URL was printed. Bars came from the local cache; no API call was made.*

---

## The answer first

**The mechanism is real. The verdict is too harsh.**

Paying the close of the minute the signal fires, on the exact same trades the book already
found, is worth about **$157 a day — roughly $3,100 a month — and the 95% interval does not
touch zero.** It is small, it is not the $721, and it is not nothing.

| one trade a day, 500 sessions | per day | 95% interval | per month |
|---|---:|---|---:|
| the book as published | **$721** | $577 to $870 | $14,415 |
| same trades, paying the signal minute's close | **$157** | $45 to $270 | **$3,140** |
| what `g76_rebuild_verdict.md` says the same fill is worth | $28 | −$71 to $131 | $556 |

The two honest figures disagree by about 5x, and the reason is not arithmetic. It is that
the earlier report answered a different question — see section 5.

And a separate finding that fell out on the way: **all three published dollar headlines in
this project are correct, and none of them describes the same thing as any other.** That
reconciliation is section 2, and it is the piece worth keeping regardless of who is right
about fills.

---

## 1. Yes, $721 is the right number for the book on disk

Recomputed from scratch, from `research/bt2y_trades.json` as it sits in the working tree:

| | trades | win rate | per day | 95% interval | mean R |
|---|---:|---:|---:|---|---:|
| taking everything the engine fires | 4,508 | 59.4% | $5,268 | $4,596 to $5,958 | +0.5843 |
| one trade a day, first signal | 499 | 66.7% | **$721** | $577 to $870 | +0.7222 |

$720.76 a day, so $721. That figure is reproduced exactly, and so is the $5,268. The
starting point of the argument is sound.

---

## 2. The three books — the reconciliation

This is the deliverable if nothing else here survives.

**Four different files have been called `research/bt2y_trades.json` in the last four days.**
Every one of them is still recoverable. Priced on one arithmetic, they are:

| the file | built | setups looked at | trades taken | $/day everything | $/day one a day |
|---|---|---:|---:|---:|---:|
| working tree, **not committed** | 29 Aug, 18:38 | 134,012 | **4,508** | $5,268 | **$721** |
| last committed version | 29 Aug, 03:14 | 76,019 | **2,437** | $2,678 | $607 |
| the version before that | 29 Aug, 01:03 | 75,953 | 2,595 | $2,845 | $642 |
| the version before that | 26 Aug, 12:28 | 45,175 | 1,016 | $1,945 | $877 |

Now the headlines.

**`research/g71_board.md` says $305 a day and $2,700 a day, on 2,437 trades.** Both are
correct for the 2,437-trade book, which is the last one anybody committed. My recompute of
that book gives **$2,678 a day** taking everything — the $2,700. And its $305 is not the
book's own exit at all: it is the same trades with **every winner cut off at 2R**, because
that is the only exit the live path has. My recompute of that lens on that book gives
**$303 a day.** The board's own script, pointed at the 2,437 book, prints $611 for the
book's scale-and-runner exit and $305 for the live 2R cut; pointed at today's book it prints
$722 and $484. Every step lines up. The remaining pennies are a denominator: the board
divides by the 496 days that had a candidate, I divide by all 500 sessions.

**`research/g76_rebuild_verdict.md` says $721 a day, on 4,508 trades.** Correct for the
working-tree book, which is 15 hours younger than the committed one and has not been
committed at all.

So the chain, in one line each:

1. 2,437 trades, winners cut at 2R the way live actually exits → **$305 a day**.
2. Same 2,437 trades, letting the runner run the way the backtest does → **$607 a day**.
3. Rebuild after the fix that stopped a rejected signal from silencing the real one — 85%
   more trades — same runner exit → **$721 a day**.

Nothing contradicts anything. Two of the three steps are an exit choice and a bug fix, not
a disagreement about money. **What is wrong is that a number nobody can reproduce from the
repository is the one being quoted**: the 4,508-trade book that carries $721 exists only as
an uncommitted file on this machine. If it is lost, $721 is unrecoverable and the last
defensible headline drops back to $607.

**Proposed, not applied:** commit the working-tree book, or stop quoting $721.

---

## 3. The head start is exactly as described

The claim under the whole argument is that the engine books a price that had already traded
*earlier in the same minute* — before the signal existed. Measured directly off the archived
bars, with no model at all: for every one of the 4,508 trades, how far in front is it
already at the instant its signal comes into being?

| | this measurement | what `g76_rebuild_verdict.md` reported |
|---|---:|---:|
| typical trade is already up | **+0.43R** | +0.44R |
| average trade is already up | **+0.580R** | +0.580R |
| already up half an R | **44.8%** | 44.8% |
| already up a full R | **17.5%** | 17.5% |
| fills that are not the minute's closing price | **87.5%** | 85% |

And the punchline reproduces to three decimals: **the book earns +0.584R per trade and
starts each trade +0.580R in front.** The measured edge and the free head start are the same
size. That is not disputed here, and it should not be disputed anywhere. It is the single
most important number this project has produced.

*(The 87.5% vs 85% is a threshold, not a disagreement: the earlier count needed the head
start to exceed half a cent in dollars, mine needs it to exceed half a cent's worth of risk.)*

---

## 4. The test: same trades, same bars, same rules, one thing different

To ask "does the head start matter in dollars" without anything else moving, I ran **one
simulator twice.**

- Same 4,508 trades. Same archived minutes. Same stop levels the book chose. A flat 2R
  target measured from whatever price the arm paid. Stops trigger on the candle close and
  fill through the shared stop rule, floored at −1.25R; targets fill on a touch; the minute
  you open on is not a management minute.
- **Arm one pays the book's own fill.** **Arm two pays the close of the minute the signal
  fired.** Nothing else differs.

This is a plain flat-2R system with no scale-outs and no break-even move — deliberately.
It is not the shipped exit machinery and is not meant to be. It is meant to be *identical
on both sides*, so the gap between them is the fill and nothing else.

| | trades | win rate | per day | 95% interval | months green |
|---|---:|---:|---:|---|---:|
| **everything, book's fill** | 4,508 | 56.8% | $5,631 | $5,013 to $6,253 | 25 of 25 |
| **everything, paying the close** | 4,508 | **39.2%** | **$650** | **$149 to $1,153** | 17 of 25 |
| **one a day, book's fill** | 499 | 64.3% | $860 | $723 to $994 | 25 of 25 |
| **one a day, paying the close** | 499 | **43.1%** | **$187** | **$54 to $322** | 17 of 25 |

Paired session by session, paying the close costs **$4,981 a day** taking everything
(interval −$5,395 to −$4,583) and **$673 a day** one trade a day (−$785 to −$563). Both
comfortably outside any error bar this project has ever carried. **The fill is worth more
than the strategy.** That part is beyond argument.

The mechanism is visible in the exit mix: at the book's fill, 2,543 trades reach target and
1,936 stop. Paying the close, that flips to 1,699 target and 2,697 stop. You pay more, your
stop is further away, so your 2R target is further away too, and it stops being reached.
The win rate falls from 57% to 39% for that reason alone.

Every trade was still takeable at the close — **zero of 4,508** had a close already at or
through its own stop — so nothing was dropped to make the honest arm look better.

**One haircut to apply before quoting.** This simple flat-2R exit is *more generous* than
the shipped one: it makes $860 a day one-a-day where the real book makes $721, a factor of
1.19. Apply the same haircut to the honest arm and paying the close is worth **$157 a day,
$45 to $270, about $3,100 a month.**

---

## 5. Negative, zero, or small-positive?

**Small-positive, and the interval misses zero on the upside.**

$157 a day one trade a day, 95% interval $45 to $270. Taking everything, $608 a day after
that arm's own haircut (it overstates the book by 1.07, not 1.19), interval $139 to $1,079 —
but that is 9 trades a day and 8 red months out of 25, so it is not a thing a person runs.

This is where I part company with `research/g76_rebuild_verdict.md`. It puts the same fill
model at **$28 a day, −$71 to $131**, and concludes "not one of these clears zero" and "you
cannot tell it from nothing." On a same-trades test that conclusion does not hold: the
strategy paying the close is about five times bigger than that, and its interval is entirely
above zero.

**Why the two answers differ, and it is not a mistake by either.** The earlier report
*rebuilt* the book — it re-ran the engine with the honest price feeding the gates, so the
minimum-risk floor, the too-wide-stop skip and the position sizing all moved, and **only 17%
of the published trades survived.** 83% of what it prices are trades the engine never found.
That is a defensible thing to measure, and the report says so plainly.

But it answers *"what would this engine do if you rebuilt it to pay the close"*, not
*"what are the trades it already found worth if you pay honestly"*. Those are different
questions and the second one is the one a person asks before deciding whether to keep going.
The earlier report knew the same-trades answer — it names $111 a day in its own section 2,
in the same neighbourhood as my $157 — and then put the rebuild figure in the headline table
and the same-trades figure in a paragraph explaining why it was wrong. **The headline table
should carry both.**

So, precisely:

- **"$721 a day is dead" — holds.** Independently confirmed, exactly, by three separate
  measurements.
- **"The fill is the whole game" — holds.** Confirmed, and larger than any error bar here.
- **"Honest fills give $0 to $114 a day" — does not hold.** Same trades, honest price, and
  a proper interval: $45 to $270 a day, one trade a day.
- **"You cannot tell it from nothing" — does not hold** for the pay-the-close model. You
  can. It is small, but it is there.

---

## 6. Something else that turned up, and it points the same way

**Not one loss in any of the four books is worse than −1.000R.** Every stop in all four —
4,508 of them in the current book, zero exceptions — fills at exactly the stop price. The
−1.25R floor that the rules describe has never bitten, in any book on disk, because nothing
ever gets past −1.000R to be floored.

`DIRECTION.md` currently states that for this book "the floor clamps 303 of 475 traded losses
and the book means −0.1210R less." **That is not true of the file on disk.** Either the fix
did not reach the run that produced it, or the book predates the fix. Either way, **every
dollar figure in this note and in every report it reconciles is optimistic on a second,
independent axis** — losses are booked at the stop price rather than the worse close that
triggered them.

My matched-pair test above *does* apply the honest stop fill, on both arms, which is one
reason its book-fill arm is not a carbon copy of the published book.

**Proposed, not applied:** rebuild the two-year book with the shared stop fill actually
engaged, and re-quote both $721 and $157 afterwards. Both will fall.

---

## 7. What I did not test, and will not claim

- **The resting-order model** — the one the earlier report recommends and quotes at $1,700
  a month. I did not measure it. Nothing here confirms or refutes it.
- **The full rebuild.** I did not re-run the engine with honest prices feeding the gates, so
  I cannot say whether its 754-surviving-trades figure is right. I can only say it prices a
  different question.
- **The late-by-a-minute models.** Not measured here.
- **The scale-out and break-even machinery.** My simulator has neither, by design. It is a
  control, not a replacement for the shipped exits, and its absolute dollars should never be
  quoted without the 1.19 haircut.

---

## 8. The verdict, in one paragraph

The head start is real, it is exactly the size of the entire measured edge, and $721 a day
is not obtainable — all three confirmed independently, to three decimals. But the follow-on
verdict is too dark. Take the trades the engine already found and simply pay the price you
could see, and the strategy makes about **$157 a day, $3,100 a month, with an interval that
does not reach zero**. That is a real, small, unimpressive edge, not a nothing. And it sits
on top of a book whose stops are still booked a shade better than the rules say they should
be, so treat $157 as a ceiling rather than a floor. Meanwhile the three circulating
headlines — $305, $607, $721 — are all correct and all describe different objects, and the
one being quoted is the only one not committed to the repository.

---

*Script: `research/g80_dollar_reconcile.py` (book census across the working tree and every
committed version, the published-fill recompute, the model-free head-start measurement, and
the two-arm matched-pair simulation with 10,000-draw session-resampled intervals) →
`research/g80_dollar_reconcile.json`. Read-only; no mark file opened, no engine file edited,
nothing committed or pushed, no API key or request URL printed.*
