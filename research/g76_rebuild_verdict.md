# The two-year book, rebuilt at prices you could actually have paid

*2026-08-29. Every number here is re-derived from the archive by scripts named at
the bottom. Nothing was committed or pushed, no mark file was opened for writing,
and the four safety tests are green.*

---

## The answer first

**$721 a day is dead.** It is not obtainable at any reaction speed, including
zero. Rebuilt so that every entry is a price you could have paid:

| one trade a day, 500 sessions | per day | honest range | per month |
|---|---:|---|---:|
| the book as published | $721 | $577 to $870 | $14,415 |
| **A — paying the signal minute's close** | **$28** | −$71 to $131 | $556 |
| **B — a robot buying the next minute's open** | **$0** | −$98 to $101 | $7 |
| **C — a resting order at the level** | **$114** | −$42 to $279 | $2,287 |
| **C — one order a day, placed and left alone** | **$86** | −$56 to $233 | **$1,724** |
| **D — you, one minute late** | **−$103** | −$177 to −$26 | −$2,070 |
| **D — you, two minutes late** | **−$68** | −$150 to $16 | −$1,355 |
| five minutes late | −$104 | −$171 to −$31 | −$2,081 |

**Not one of these clears zero.** The resting order is the only one that is even
pointing the right way, and its range still crosses zero. One and five minutes
late are the only bands that miss zero — and they miss it on the wrong side.

The recommendation is at the bottom. The short version: **about $1,700 a month,
and you cannot tell it from nothing.**

---

## 1. Where the money was coming from

One line, `signal_runner.py` line 1330:

```python
return min(max(level, candle.low), candle.high)
```

The engine fires when a minute CLOSES back through a level. When that closing
price sits near the top of the minute, the engine does not pay the closing
price. It pays **the level** — a price somewhere lower down inside the same
minute. That price is real; the minute traded there. But the closing price is by
definition the **last** trade of the minute, so a price below it happened
**earlier in the minute — before the signal existed.** Only an order already
sitting at the level gets filled there.

**3,841 of the 4,508 trades in the book — 85% — are filled that way.** The split
is the whole story and it needs no model at all:

| | trades | average | win rate | two-year total |
|---|---:|---:|---:|---:|
| filled at a price the minute had already traded | 3,841 | **+0.70R** | 64.2% | $2,680,251 |
| filled at the price you could see — the close | 667 | **−0.07R** | 31.8% | −$46,401 |

### One trade, in full

**HOOD, 2 July 2025, 09:39.** That minute opened at 93.57, dipped to 93.15, ran
to 93.81 and closed at 93.78. The signal is *"the minute closed back above the
level"* — so it did not exist until 93.78 printed, at the end of the minute.

The book buys at **93.38**, with the stop at 93.15. 93.38 traded during the dip,
somewhere in the middle of that minute. By the time the signal existed, price was
40 cents higher — **the trade was already 1.74R in profit at the moment it came
into being.** It is booked as +10.07R, **$10,074**.

**ORCL, 4 December 2025, 10:11** is the same shape: opened 208.29, low 208.26,
high 208.68, closed 208.66. The book buys at **208.26 — the exact low of the
minute** — stop 207.92, and books +9.62R, **$9,618**. Already +1.18R before the
signal existed.

### And that head start is the entire edge

Measured across all 4,508 trades — how much profit each one is already showing at
the instant its signal comes into existence:

| | published book | paying the close |
|---|---:|---:|
| typical trade is already up | **+0.44R** | 0.00R |
| average trade is already up | **+0.58R** | 0.00R |
| already up half an R | 44.8% | 0% |
| already up a full R | 17.5% | 0% |

**The published book earns +0.584R per trade. It starts each trade +0.580R in
front.** The measured edge and the free head start are the same size.

---

## 2. This is a rebuild, not a re-pricing

Yesterday's figure — *"pay the close and it's $111 a day"* — kept the same 499
trades and changed only what they cost. That understates the damage, because the
price you pay is chosen **before** the engine decides whether the trade is worth
taking: it feeds the minimum-risk floor, the too-wide-stop skip, where the target
goes and how big the position is.

Rebuilt end to end — same 500 sessions, same 28 symbols, same rules, same
two-loss halt — **only 17% of the published book's trades survive into the honest
version — 754 of them.** The other 83% are different trades entirely.

That is why the rebuilt number ($28 a day) is well under the re-priced one ($111).

### Everything you can take, not one a day

| | trades | win rate | per day | honest range | per month | months green | worst drawdown |
|---|---:|---:|---:|---|---:|---:|---:|
| the book as published | 4,508 | 59.4% | $5,268 | $4,601 to $5,960 | $105,354 | 25 of 25 | $11,105 |
| A — the close | 4,333 | 44.4% | −$271 | −$561 to $21 | −$5,420 | 8 of 25 | $193,835 |
| B — next minute's open | 4,309 | 45.5% | −$125 | −$436 to $204 | −$2,504 | 11 of 25 | $132,034 |
| **C — resting order** | 1,803 | 32.2% | **$355** | **$12 to $722** | **$7,108** | 16 of 25 | $40,357 |
| D — one minute late | 3,924 | 39.6% | −$671 | −$927 to −$398 | −$13,428 | 4 of 25 | $347,116 |
| D — two minutes late | 3,779 | 38.6% | −$772 | −$1,016 to −$519 | −$15,447 | 4 of 25 | $386,167 |
| five minutes late | 3,755 | 36.9% | −$808 | −$1,021 to −$574 | −$16,168 | 2 of 25 | $424,387 |

**The resting order is the only model in this whole exercise whose range misses
zero on the upside**, and it only just does.

Durability goes with it. *Every month green* was true of the published book and
is true of nothing else: 8 of 25 paying the close, 16 of 25 on the resting order,
2 of 25 five minutes late.

---

## 3. The resting order, properly

This is the one that matters, so it gets the care.

**How it works.** The signal fires at the close of a minute. An order is left
sitting at the level, and it fills **only if price actually trades back through
that price on a LATER minute.** If price never comes back, there is no trade. The
stop and the target are set when the order is placed and do not move. This is not
look-ahead — every fill requires a trade that happened after the signal — and it
is exactly what you can leave in the market while you are at work.

**Whether it fills.**

- 3,426 orders over two years. **306 never filled — 8.9%.**
- Of the ones that do fill, **68% fill on the very next minute.** Median wait
  1 minute, average 3.2, and 9 in 10 are filled within 7 minutes.
- On 494 of the 500 days there was at least one order to place. On **39 of those
  days — 8% — the day's first order was never touched** and you would have had no
  trade at all.
- Not once in 3,120 fills did a gap leave you filled on the wrong side of your
  own stop.

**What it feels like.** 32% win rate. The average winner makes **+2.40R**, the
average loser costs **−1.00R**. That is a different animal from the published
book (59% win, +1.65R winners). You get a better price — but you only get it on
the trades that come back to you first, and those are disproportionately the ones
that then keep going. That is the price of the better price.

**Two versions, and the difference matters.**

- *Take whichever order fills first each day* — $114 a day, $2,287 a month. But
  you have to have placed an order on every signal to know which one fills.
- *Place one order a day, on the day's first signal, and leave it* — **$86 a day,
  $1,724 a month**, on 455 trades in 500 sessions. This is the version a person
  with a job can actually run, and it is the one I would quote.

**Where it is fragile.** Everything above assumes the minute you are filled on is
not a management minute — the same convention the published book uses for its own
entries. If instead the rest of that minute counts as live, the resting order
falls to **$274 a day taking everything (−$65 to $631) and $42 a day one order a
day**, and **it no longer clears zero.** The positive result is real but it is
one convention deep.

---

## 4. Two things I checked so nobody has to ask

**"You gave the honest models the wrong stop."** The book puts the stop at the
level. Austin's own rule is *"stop at the bottom of the wick of the candle you
entered on."* Rebuilt that way instead: paying the close gives **$298 a day
taking everything (−$167 to $781) and −$18 a day one trade a day.** It does not
rescue anything. The same change applied to the published book's look-ahead fill
pushes it to $6,728 a day — which is the point: the enormous figures come from
the fill, not from the trading.

**"Did the rebuild break the engine?"** The rebuild reproduces the published book
**exactly** when it is asked to keep the original fill — 4,508 trades, 59.4% win,
$721 a day one trade a day, $11,105 drawdown, every figure to the dollar. The
copied simulation loop is also checked trade-for-trade against the shipped one
across 160 symbol-sessions and matches on every field. If it can reproduce the old book
perfectly, the new numbers are the fill and nothing else.

---

## 5. What replaces $721 a day

**Recommendation: the resting order at the level — model C — one order a day.
About $1,700 a month.**

Say it with the range attached, because the range is the finding: **−$1,100 to
+$4,700 a month.** It is not distinguishable from zero.

Why C and not A or B:

1. It is the only model in the exercise that is pointing up rather than down.
2. It is the honest version of what the book has been pretending to do all along
   — the book's own fills ARE resting-order fills, they were just being credited
   without requiring the order to actually be touched.
3. It is the only one compatible with a day job. A and B need something watching
   every minute; D is a person tapping, and every version of a person tapping
   loses money.

Two caveats to carry with the number:

- Taking every trade instead of one a day reads **$7,100 a month** ($240 to
  $14,400) — but that is 3.6 trades a day and a **$40,357** drawdown, and it
  fails the every-month-green test 9 months out of 25.
- C stops clearing zero if the fill minute is treated as live.

**What this does to the three gates.** Money was already far short of the 2.0R
target at +0.72R; honestly filled it is **+0.095R**. Durability was the one gate
being met at 25 of 25 months green; honestly filled it is **14 of 25**. Nothing
here touches recall.

The strategy is not currently worth building sizing, brokerage or automation on
top of. What it is worth is the thing this rebuild also shows: **the fill is the
whole game.** A setup that has to be bought at the close of the minute that
confirms it earns nothing. The same setup bought on a pullback to the level
earns +2.40R when it works. The next question is not "which exit" or "which
grade" — it is *"which signals come back to the level, and can they be told apart
in advance."*

---

*Scripts, all re-runnable, none touching engine code, a mark file or the
published book:*
`research/g76_rebuild_engine.py` (the fill models, the pending-fill queue, and
the parity check against the shipped simulation),
`research/g76_rebuild_lookahead.py` (the proof and the worked examples →
`research/g76_lookahead.json`),
`research/g76_rebuild_book.py` (rebuilds one book per fill model →
`research/g76_book_*.json`),
`research/g76_rebuild_report.py` (prices every book on
`research/g72_suppress_price.py`'s own arithmetic, with 10,000-draw day-resampled
error bars → `research/g76_rebuild_numbers.json`),
`research/g76_rebuild_diag.py` (risk geometry, fill statistics, survival →
`research/g76_rebuild_diag.json`).
*Guardrails: mark files untouched, nothing committed or pushed, no engine file
edited, no API key printed. `regression_gate.py`,
`test_universe_single_source.py`, `t11_stop_fill_fix.py` and
`test_runner_stop.py` all re-run and green after this work.*
