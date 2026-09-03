# Trendiness as a filter — the finding is real, and it is not tradeable

*2026-08-29. The one thing that moved your yes/no on the 30 cards was whether the day
trended. This is that turned into a filter and priced. **It does not survive being computed
before the trade.** One piece of it does survive, and it is not a filter.*

---

## The short version

1. **The finding reproduces, exactly.** Your yes-days scored 0.145, your no-days 0.072,
   p = 0.014. Recomputed from the raw bars, not by re-reading anyone's cached number.

2. **It holds up on 27x more of your marks.** Across all 812 days you have graded either S
   or refused — not just these 30 — trending days score 0.133 and refusals 0.101,
   p < 0.0001. So this is a real property of your eye, not a fluke of one homework page.
   It is about **half as strong** as the 30 cards made it look.

3. **The number is measured on the whole 9:30–11:00 chart, including every bar after the
   trade was over.** It is a description of a finished day. To trade on it you would have to
   know at 9:29 how the day is going to go.

4. **You cannot know that at 9:29.** I tried nine different ways — the premarket, yesterday,
   the last five days, the daily chart over ten and twenty sessions, the size of the gap.
   **Every one is a coin flip**, on your 30 cards and on all 812 graded days alike. Two of
   them lean the wrong way: your S days tend to come on stocks whose recent daily chart was
   *less* trendy, not more.

5. **Priced on the two-year book, no honest version makes money.** The best causal arm is
   +$46 a day one-trade-a-day with an error bar of −$41 to +$140. Nothing clears its own
   bar. The three arms that *do* clear their bar clear it **downward**: filtering on the
   daily chart's trend loses between $102 and $285 a day.

6. **And every version costs you S days.** The engine currently finds 163 of your 278. Cut
   the choppiest half of days by any measure and it finds 71 to 112 of them. You are 31
   points short of the recall gate; this spends 18 to 33 more.

**Verdict: do not wire a trendiness gate.** Same answer the earlier trend pass reached, by a
completely different road.

---

## What survived, and it is worth having

**The first thirty minutes tell you more about whether a day is yours than the whole session
does.**

Take the efficiency of 9:30–10:00 only — knowable at 10:00, no hindsight in it. Sort all 812
graded days by it:

| the first half-hour was… | how often that day turned out to be one of your S days |
|---|---:|
| choppiest quarter | **21.2%** |
| second | 25.6% |
| third | 39.4% |
| **trendiest quarter** | **50.7%** |

A day that opens clean is **two and a half times** more likely to be one you would trade.
That beats the whole-session number (46.3% vs 23.6%) — the score that can see the *future*
is a **worse** predictor of your grade than the score that only sees the first thirty
minutes. Statistically it is the strongest thing in this whole pass: p < 0.0001 on 812 days.

**It still is not a trade filter, and I have to be straight about why.** Under your
one-trade-a-day rule, **490 of 499 trades have already happened by 10:00**. A score that
arrives at 10:00 almost never gets a vote. That is not "tested and failed" — it is "never
gets asked". Where it is genuinely useful:

- **Picking what goes on your homework pages.** The deck builder's chop check is switched off
  today because the whole-session version threw away too many of your S days. This one is
  better and does not need hindsight.
- **A live read at 10:00** — "today opened clean / today is chop" — as information for you,
  not as a gate on the engine.

---

## How to compute it by eye

Same arithmetic at every timescale. On the chart in front of you:

> **Trendiness = how far it got ÷ how far it walked.**
>
> Take the close at the start and the close at the end. The distance between them is *how far
> it got*. Now add up every one-minute move, up or down, ignoring direction — that is *how far
> it walked*. Divide.

A straight line up scores 1.0. A day that ends where it started after grinding all morning
scores near 0. Your yes-cards averaged 0.145 and your no-cards 0.072 — so in your own terms,
**a day you like keeps about one step in seven; a day you refuse keeps one in fourteen.**

Both flavours use exactly this formula. The only difference is which bars go in:

- **the finding's version** — the 90 closes from 9:30 to 11:00. Hindsight.
- **the useful version** — the 30 closes from 9:30 to 10:00. Known at 10:00.

Your own words agree with the number. The three cards you tagged **"chop"** — HOOD 28 Nov,
AAPL 11 Mar, QQQ 22 Dec — average 0.072 against a 0.123 average across all 30. You were
reading this number off the chart without being given it.

---

## The measurement, in full

### The reproduction

| | your yes-days | your no-days | |
|---|---:|---:|---|
| the 30 cards | **0.1450** (n=21) | **0.0724** (n=9) | p = 0.014 |
| **all 812 days you have graded** | **0.1329** (278 S) | **0.1009** (534 refusals) | **p < 0.0001** |

Sorted by trendiness, the ten trendiest of the 30 cards are ten yeses out of ten; the ten
choppiest are five of ten. The recomputed score matches the homework page's stored value to
five decimal places, so there is no arithmetic drift between this pass and the finding.

### What is knowable at 9:29 — the whole point

| score, computed only from bars before 9:30 | on the 30 cards | on all 812 graded days |
|---|---|---|
| premarket, 4:00–9:29 | coin flip (p 0.43) | coin flip (p 0.54) |
| premarket, 8:00–9:29 | coin flip (p 0.19) | coin flip (p 0.75) |
| yesterday's 9:30–11:00 | coin flip (p 0.93) | leans **backwards** (p 0.051) |
| the last five days' average | coin flip (p 0.62) | coin flip (p 0.30) |
| yesterday's last hour | coin flip (p 0.38) | — |
| daily chart, 10 sessions | coin flip (p 0.53) | leans backwards (p 0.16) |
| daily chart, 20 sessions | coin flip (p 0.40) | leans backwards (p 0.09) |
| size of the overnight gap | coin flip (p 0.89) | coin flip (p 0.15) |
| **9:30–10:00, known at 10:00** | coin flip (p 0.66)\* | **p < 0.0001** |
| the whole session — **hindsight** | p = 0.014 | p < 0.0001 |

\* 30 cards is too few to see it; 812 days is not. That is the same lesson the 80%-vs-60%
headline taught this morning.

**Nothing you can know before the opening bell predicts whether the morning will trend.**
That is a real result and it is the one that kills the idea.

### The money, on the two-year book

Book: 500 sessions, 4,508 trades. Unfiltered it makes **$5,268 a day** taking everything and
**$721 a day** one-trade-a-day, 66.7% win rate, 25 of 25 months green, 87 of 105 weeks green,
worst hole $5,993. Every arm below is that book with the loss-halt rule re-run on the
survivors, and every dollar figure uses the same arithmetic the last board used.

The only score that can both see the decision and be honest about it is the one measured at
the entry minute itself:

| cut the choppiest… | trades kept | $/day one-a-day | vs now | win% | months | weeks | worst hole | your S days found |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| — (today) | 4,508 | $721 | — | 66.7 | 25/25 | 87/105 | $5,993 | 163/278 |
| 10% | 4,215 | $701 | −$20 [−77, +31] | 66.7 | 25/25 | 88/105 | $5,993 | 154 |
| 30% | 3,557 | $726 | +$5 [−71, +82] | 68.1 | 25/25 | 90/105 | $5,000 | 130 |
| 40% | 3,181 | $767 | **+$46 [−41, +140]** | 69.3 | 25/25 | 91/105 | $5,000 | 124 |
| 50% | 2,767 | $751 | +$30 [−70, +138] | 69.4 | 24/25 | 88/105 | $5,000 | 112 |
| 70% | 1,751 | $721 | −$0 [−117, +116] | 71.6 | 24/25 | 86/105 | $6,750 | 82 |

Every row's error bar straddles zero. The win rate climbs nicely — 66.7% to 71.6% — but the
dollars do not follow it, because the trades being thrown away were winners too.

The arms that *do* clear their error bar, all of them 9:29-knowable, all of them negative:

| filter | trades kept | $/day one-a-day | vs now | your S days found |
|---|---:|---:|---|---:|
| daily chart 10-session trend, choppiest 30% cut | 3,287 | $619 | **−$102 [−208, −0]** | 105/278 |
| daily chart 10-session trend, choppiest 60% cut | 2,472 | $569 | **−$152 [−284, −23]** | 76/278 |
| daily chart 10-session trend, choppiest 70% cut | 1,531 | $436 | **−$285 [−447, −122]** | 43/278 |
| daily chart 20-session trend, choppiest 50% cut | 2,486 | $540 | **−$181 [−310, −52]** | 71/278 |
| premarket efficiency, choppiest 70% cut | 1,562 | $528 | **−$193 [−358, −29]** | 51/278 |

**The only thing in this whole sweep that reliably does anything is a trend filter making you
poorer.**

And for scale, what perfect hindsight would be worth if you could have it: cutting the
choppiest 70% of days by the finding's own number gives $974 a day, 77.5% win rate, 99 of 105
weeks green, a $4,000 worst hole — and finds only **60 of your 278 S days**. Even cheating,
the ceiling here is +$253 a day and it costs 37 points of recall.

### A mistake I made and caught

The first version of the sweep scored a 9:42 trade against the 9:30–10:00 efficiency — a
number that does not exist yet at 9:42. It printed **+$420 a day, 80.4% win rate, 101 of 105
weeks green**, and it was entirely fake. The rule is now written into the script: a score
knowable at 10:00 may only decide trades entered at or after 10:00, and everything earlier
passes through untouched. That is why the honest 10:00 arm moves nothing — 98.2% of your
one-a-day trades are already done by then.

---

## Is this the same thing as the earlier trend pass?

**No, and they answer different questions — but they land in the same place.**

The earlier pass (`research/g71_trend.md`) measured **direction**: is this trade with the
higher-timeframe trend or against it? It found the with-trend veto is already the single
biggest gate in the engine, that all 18 direction filter arms are inside their error bars,
that the *best* arm in the table is counter-trend, and that 20 of your 34 held-out S setups
are counter-trend on the engine's own definition.

This pass measures **whether there is a trend at all** — chop versus a clean run, blind to
direction. A day can be violently trending downward and score high here; the earlier pass
would call the same day "opposed" for a long trade.

Different question, different arithmetic, same verdict: **not a gate.** Two independent roads
to "archive it". The earlier pass's two side-findings — the two different functions both named
`htf_bias` feeding the same veto, and the live/backtest gap in `with_trend` — are untouched by
this and still want owners.

---

## What I would do

1. **Do not wire a trendiness gate.** No causal version makes money, all of them cost S days,
   and the recall gate is the one you are furthest from.
2. **Take the 9:30–10:00 score into deck building.** It is the best day-quality signal in the
   corpus, it is free, and the current chop check is off because the hindsight version was
   too blunt. This one is sharper and cheaper.
3. **Stop treating "the day, not the setup" as an instruction.** It is true about your eye and
   it is not available at 9:29. The actionable half of this morning's homework is still the
   **40-minute entry lag on the one-candle rule** — that one is a clock, and a clock is
   something the engine can be fixed to.

---

*Every number re-derivable. `research/g75_trendfilter_lib.py` (the one definition of the
score, in both flavours), `research/g75_trendfilter_cards.py` (the reproduction and the
causal test on the 30 cards), `research/g75_trendfilter_cache.json` via
`research/g75_trendfilter_cache.py` (one pass over the bar archive),
`research/g75_trendfilter_book.py` (the threshold sweep and the causality rule),
`research/g75_trendfilter_marks.py` (the 812-day cross-check and the S-day replay through the
real router), `research/g75_trendfilter_frontier.py` (money and recall on the same threshold,
plus the quartile table). Outputs: `g75_trendfilter_cards.json`, `g75_trendfilter_book.json`,
`g75_trendfilter_marks.json`, `g75_trendfilter_frontier.json`.*

*Housekeeping: `research/g75_trendfilter_cache.json` is 30 MB and is **not** covered by an
ignore rule — it rebuilds from its own script in 35 seconds. It joins the pile the last board
already flagged; do not run a blanket `git add` in this repo.*

*Guardrails: the mark file was opened read-only and is byte-identical; nothing was committed
or pushed; no engine file was touched; `stop_rule.stop_fill_price()` untouched;
`downgrade.py` untouched; no API key printed. All four protected tests re-run and green after
this work — `regression_gate.py`, `test_universe_single_source.py`, `t11_stop_fill_fix.py`,
`test_runner_stop.py`. The unfiltered book reproduces the last board's headline numbers
exactly (4,508 trades, $5,268/day, 59.4% win, 25/25 months, 100/105 weeks, $11,105 drawdown;
one-a-day 499 trades, $721/day, 66.7%, 25/25, 87/105, $5,993), and the recall replay
reproduces 163 of 278 = 58.6%.*
