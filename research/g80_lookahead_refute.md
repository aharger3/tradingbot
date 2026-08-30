# I tried to break the look-ahead finding. It held — and one half of it is worse than reported

*2026-08-30. Every number here was recomputed from the archive by
`research/g80_lookahead_refute.py`, which writes `research/g80_lookahead_refute.json`.
No engine file was edited, no mark file was opened, nothing was committed or pushed.
The job was to refute the claim in `research/g76_rebuild_verdict.md`. It does not refute.*

---

## The answer first

The two-year book credits **$2,680,251** to trades that were filled at a price better
than the closing price of the minute that produced the signal. Of that:

| | trades | dollars |
|---|---:|---:|
| filled at a price **no order of any kind** could have got — the minute never returned to the level | **2,067** | **$1,504,056** |
| filled at the level, but a resting order would already have been filled **minutes earlier**, on a different trade | 1,669 | $1,064,639 |
| filled at the level, on this trade, in this minute — **genuinely obtainable** | **105** | **$111,556** |

Those three rows are the 3,841 and the $2,680,251, split with nothing left over.
**About $112,000 of the $2.68 million — 105 trades out of 4,508, 2.3% of the book —
is money a resting order would actually have collected on the trade the book says it
collected it on.** At most 404 trades from the middle row could join it — the
order-block and re-entry setups, where I could not trace when an order became
placeable and so counted every one of them in the best case. That is a deliberate
over-count, not an estimate.

**Verdict: not refuted.** One sentence of the claim is imprecise and I have corrected
it below. The finding it supports stands, and on the biggest single slice it stands
harder than the original report said.

---

## What I recomputed, and it matches to the trade

I rebuilt the count from `research/bt2y_trades.json` and the archived minute bars
without reading the original script's output.

| | mine | the rebuild report's |
|---|---:|---:|
| trades filled better than the signal minute's close | **3,841** | 3,841 |
| share of the book | **85.2%** | 85.2% |
| their average result | **+0.6978R** | +0.6978R |
| the 667 filled at the close | **−0.0696R** | −0.0696R |

Identical. As a separate check I re-ran the shipped fill routine on each trade's own
level and its own entry minute: it reproduces the booked entry price on **4,422 of
4,508 rows (98.1%)**, so the level recorded against each trade really is the level the
fill routine was handed, and everything below is reading the same numbers the engine
read. The 86 rows it does not reproduce are almost all the re-entry setup, where the
recorded level is not the price the fill routine used; they are small and I have not
chased them.

**The 85% figure is reproducible. That part of the claim is confirmed, not refuted.**

---

## The strongest counter-argument, priced

The argument I was asked to press hardest: *if the level was already known before that
minute opened, then an order sitting at the level is a legitimate fill and it is not
look-ahead.*

**The first half of that is true, and comfortably so.**

The level a trade breaks and retests is by construction older than the trade. Sorted by
where the level comes from, of the 3,841:

| where the level comes from | trades | fixed by an earlier bar |
|---|---:|---:|
| prior-day high/low | 365 | 365 |
| premarket high/low | 704 | 704 |
| the opening five minutes | 1,091 | 1,091 |
| an intraday swing high/low | 1,251 | 1,232 |
| the order-block candle | 324 | 324 |
| the re-entry rule's earlier fill | 106 | 80 (26 I could not resolve) |
| **total** | **3,841** | **3,796 — 98.8%** |

And the setup arms earlier still. The break-and-retest sequence demands that price
break the level and then *fully leave* it before any retest can count. I replayed that
state machine bar by bar against the archive — a replay that agrees with the shipped
detector on 3,810 of 3,820 rows — and on **all 3,402 break-and-retest trades it could
trace, the break and the leave were both complete strictly before the entry minute
opened**, a median of **five minutes** before it.

So the rebuild report's sentence *"the signal only exists once the minute closes"* is
**too strong and I am correcting it**: the level exists early, the arming exists early,
and an order could have been resting. Only the **confirmation** — the close back through
the level — waits for the end of the minute.

**That correction does not rescue the money, for two independent reasons.**

---

## Reason one: half these fills are not at the level at all

The fill line clamps the level into the minute's own range. Nobody had counted what the
clamp actually does. Splitting the 3,841 by what the booked price physically is:

| what the fill price is | trades | win rate | average | dollars |
|---|---:|---:|---:|---:|
| **the level itself** — the level traded inside that minute | 1,769 | 48.0% | +0.660R | $1,168,146 |
| **the minute's own low**, on a long, with the level *below* it | 1,070 | 77.5% | +0.705R | $754,040 |
| **the minute's own high**, on a short, with the level *above* it | 997 | 78.5% | +0.752R | $750,016 |
| everything else | 5 | 100% | +1.610R | $8,049 |

**2,067 trades — 53.8% of the group, $1,504,056 — are filled at the best price the
minute traded in the direction of the trade, on a minute that never came back to the
level.** A limit order resting at the level would not have been touched. It would not
have filled at a worse price; it would not have filled *at all*, and there would have
been no trade.

So the rebuild report's own line — *"only an order already resting at the level gets
it"* — is wrong on more than half of the trades it describes, and wrong in the
direction that makes things worse. **No order gets those.** They are not a fill
assumption you can argue about; they are the engine paying the minute's best price.

The report's own second worked example is one of them. **ORCL, 4 December 2025, 10:11**:
the level is the prior day's high at **207.92**, the minute's low is **208.26**, and the
book fills at **208.26** — the exact low. Price never reached 207.92 that minute. The
recorded $9,618 is not a resting-order fill; it is the low of the bar.

Its *first* worked example goes the other way and I will give it up. **HOOD, 2 July
2025, 09:39**: the level is the premarket high at **93.38**, the break and the leave
completed at 09:33, and 09:39 is the first minute after that which trades down to
93.38. A limit order left at 93.38 since 09:33 fills at 93.38 in that minute. That fill
is real. It is one of the 105.

---

## Reason two: a real resting order fills earlier, on a different trade

For the 1,769 fills that *are* at the level, the order still has to be the first thing
the market touches. I walked forward from the bar the setup armed and found the first
minute that trades back to the level:

- **3,297 of 3,402** traced break-and-retest trades — 96.9% — had their **first touch
  of the level on an earlier minute than the entry minute.**
- **105** — 3.1% — had it on the entry minute itself.

That is not a quibble about price. The price is the same either way. It means the
resting order was already filled minutes earlier, on a minute that had not yet closed
back through the level, so the position it is holding is a different position with a
different starting point and a different outcome. The book cannot claim both the level
price and the confirmation that arrived several minutes after the order would have
been hit.

This is exactly why the rebuild report's resting-order model — which requires the touch
to come *after* the signal — is not the over-correction it looks like. If anything it
is the wrong correction in the other direction: the honest resting order fills *before*
the signal, not after.

---

## Is the +0.70 / −0.07 split just selection?

Partly, and less than enough. The two groups genuinely are different animals: the
better-filled group sits on wider minutes (median range 0.30% of price against 0.22%)
with much more decisive bodies (0.61 of the bar's range against 0.45), and it is 89%
break-and-retest against 61%. So the comparison in the rebuild report is not a clean
one, and I would not lean on it.

The clean test is to hold the trades fixed and change only the fill. Re-pricing the
same 3,841 trades at their own closing price, exit price held where it is:

| | average |
|---|---:|
| as the book has them | **+0.698R** |
| the same trades, filled at the close | **+0.022R** |
| the 667 that really did fill at the close | −0.070R |

Selection is worth about **+0.09R** of the 0.77R gap. **The fill is worth the rest.**
And this is an upper bound on what survives — a close-filled trade carries a wider stop
and therefore a further-out target, which this calculation does not move.

The result also scales with the size of the head start, which is what look-ahead looks
like and not what an edge looks like:

| how far ahead the trade already was when the signal appeared | trades | average | win rate |
|---|---:|---:|---:|
| under 0.26R | 960 | +0.207R | 50.0% |
| 0.27 to 0.53R | 960 | +0.396R | 64.4% |
| 0.53 to 0.90R | 960 | +0.767R | 71.2% |
| over 0.90R | 961 | +1.420R | 71.2% |

Across the whole book the average trade is already **+0.580R** in front at the instant
its signal appears, and the book earns **+0.584R**. I get the same two numbers the
rebuild report got.

**One honesty note that cuts against every comparison on this page, the rebuild
report's included.** This project's standing error bar is **±1.5799R — ±$1,580 a
trade**. The +0.698 against −0.070 split, and the +0.698 against +0.022 re-pricing, are
both moves of well under that. On this project's own rule those are **ties**, and no
mean-R comparison here should be treated as decisive on its own. What is *not* a
mean-R comparison, and so not covered by that caution, is the counting: 2,067 fills
that no order could have received, and 105 that one could.

---

## What survives and what does not

| the claim, in pieces | verdict |
|---|---|
| 3,841 trades, 85% of the book, filled better than the signal minute's close | **stands — reproduced exactly** |
| the fill line is what does it, and the price printed earlier in the minute | **stands** |
| "the signal only exists once the minute closes" | **corrected.** The level and the arming exist a median five minutes earlier; only the confirmation waits for the close |
| "only an order already resting at the level gets it" | **wrong, and in the harsher direction.** True of 1,769. On 2,067 no order gets it, because the minute never returned to the level |
| the fills are not obtainable on the trades the book books them on | **stands — 105 of 4,508 obtainable, 2.3%** |
| the +0.70R against −0.07R split is the fill, not the trades | **mostly stands.** Selection explains about +0.09R of 0.77R; but both figures sit inside the standing error bar and neither should be quoted alone |
| the head start and the measured edge are the same size | **stands — +0.580R against +0.584R** |

I could not refute it. The one place I found the report overstating itself is a place
where the truth is worse, not better.

---

## What I did not do

- I did not rebuild a book. Every model number in the rebuild report — the daily
  figures, the month counts, the drawdowns — I took as given and did not re-derive.
  This page only tests the look-ahead claim underneath them.
- The arming replay covers break-and-retest only. For the order-block and re-entry
  setups I can say the level was fixed by an earlier bar, but not when an order could
  have been placed; the 404-trade upper bound above is what falls out of assuming the
  best case for all of them.
- 26 re-entry trades have a level I could not tie to an earlier bar, and 9
  break-and-retest trades could not be traced through the state machine. Both are
  reported as unresolved rather than assumed either way.
- The re-pricing holds the exit price fixed. A properly rebuilt close-filled trade
  would carry a wider stop and a further target; that rebuild already exists in the
  rebuild report and I did not repeat it.

---

## What this changes about what to do next

Nothing about the recommendation. It sharpens one thing: **the resting order at the
level is not available on 54% of the trades the book is quoting**, and on most of the
rest it fills before the signal rather than on it. If that model is going to be the
one quoted, it should be re-measured with the order placed at the arming bar and filled
on first touch — which is earlier than either version currently measured, and is the
only version a person with a day job actually runs.

---

*Script: `research/g80_lookahead_refute.py` → `research/g80_lookahead_refute.json`.
It reads the published book and the cached minute archive, calls the shipped fill
routine and the shipped break-and-retest detector rather than re-implementing either,
and writes nothing else. Guardrails: no mark file opened, no engine file edited,
nothing committed or pushed, no request URL printed.*
