# The mentor book — and why they average higher

*2026-08-29. Key `mentorbook`. Everything below comes from three scripts committed
beside this file:*

| script | what it made |
|---|---|
| `research/g73_mentorbook_replay.py` | `g73_mentorbook_data.json` — the mentor book, both halves |
| `research/g73_mentorbook_why.py` | `g73_mentorbook_why.json` — the six explanations, scored |
| `research/g73_mentorbook_tradezella.py` | `g73_mentorbook_tradezella.{csv,json}` — the import test |

*No mark file was opened. No network call was made (bars are cache-first, and days
with no CSV on disk were skipped and counted). Nothing was committed or pushed.
The four gates — `regression_gate`, `test_universe_single_source`,
`t11_stop_fill_fix`, `test_runner_stop` — are green.*

---

## The one-sentence answer

**They do not average higher. They average higher *in what they post*.**

You asked to pool the **trade reviews**. The two trade-review channels hold **56
reviews and not one of them is a loss** — 39 futures reviews, 17 options reviews,
zero losers between them. Across all 112,000 messages there are **54 stated dollar
figures and every single one is a profit**; nobody has ever posted a losing dollar
amount. Scarface posts an entry alert and then never mentions that trade again
**66% of the time**, and when those silent calls are scored against the tape they
look like the losers, not the winners. His claimed **79%** win rate becomes
**47.5%** once the silence is counted. OMEN, one trade a day, wins **66.7%**.

Pooling the reviews into their own backtest would have produced a system with a
100% win rate. That is the finding, not a bug in the pooling.

---

## 1. The mentor book, built anyway

3,547 pooled mentor instances funnel down like this:

| | count |
|---|---:|
| Pooled instances | 3,547 |
| − futures (no data product) | −588 |
| − symbol outside OMEN's 28 | −255 |
| − session outside the two-year book | −249 |
| − book found no setup at all that day | −150 |
| **Replayable** | **2,305** |

Those land on **1,921 distinct symbol-days**. OMEN actually took a trade on **669**
of them.

### If OMEN traded the days they called

| | trades | win | mean R | per trade | two-year total |
|---|---:|---:|---:|---:|---:|
| **On mentor-called symbol-days** | 819 | 59.8% | 0.675 | **$675** | $552,640 |
| Everywhere else in the book | 3,689 | 59.3% | 0.564 | $564 | $2,081,249 |

Difference **+$111 a trade**, 95% CI **−$35 to +$261**, p = 0.12. That is not a
finding. It is the same "moves less than its own error bar" result this project
gets every time.

*(This is not a re-run of the engine — `research/bt2y_trades.json` **is** OMEN's
replay of those sessions, same `simulate_day`, same stop rule, same exits. Joining
to it is the like-for-like comparison, and it is reproducible.)*

### And their own calls, scored on the tape

Only 49 of 3,547 instances state an entry price and 19 state a stop, so their real
P&L cannot be computed — ever. What can be computed: enter at the minute they
posted, in the direction they stated, risk = the average true range of the 15
bars **before** the post (no hindsight), resting −1R disaster stop on touch,
+2R target on touch, mark out at the close. OMEN's own risk model, their call.

| | trades | win | mean R | per trade |
|---|---:|---:|---:|---:|
| Every call with a direction and an intraday timestamp | 1,041 | 32.1% | −0.038 | **−$37** |
| Live alert rooms only (Scarface, Jdub, futures) | 235 | 31.5% | −0.055 | −$55 |

**This does not prove they lose money.** A mechanical bracket is not their trade —
they scale, they hold, they cut. What it proves is the *comparison* in section 2,
where the same instrument is pointed at reported and unreported calls side by side.

---

## 2. (f) Survivorship — tested first and hardest, and it is the whole answer

### 2a. The dollar-sign census

Across the entire corpus, **54 messages state a dollar figure**:

| | |
|---|---:|
| Positive | **54** |
| Negative | **0** |
| Smallest | $267.51 |
| Median | $3,092.50 |
| Largest | $12,500 |

Fifty-four coin flips landing heads is 1 in 18 quadrillion. This is not a trading
result, it is a posting rule.

### 2b. The reporting rate

A live alert room posts the entry. The follow-up is *optional*, and optional is
where the bias lives.

| channel | calls | followed up | never mentioned again | claimed win rate |
|---|---:|---:|---:|---:|
| **scarface-alerts** | 720 | 247 (34.3%) | **473** | **77.3%** |
| jdub-alerts | 131 | 9 (6.9%) | 122 | 50.0% |
| futures-alerts | 588 | 23 (3.9%) | 565 | 94.7% |
| post-your-gains | 380 | 380 (100%) | 0 | 63.5% |
| **futures-trade-reviews** | 45 | 39 (86.7%) | 6 | **100%** (39 W / 0 L) |
| **options-trade-reviews** | 19 | 17 (89.5%) | 2 | **100%** (17 W / 0 L) |
| chat / misc | 1,655 | 265 (16.0%) | 1,390 | 40.7% |

Notice the shape: **the more curated the room, the higher the win rate.** Casual
chat, where nobody is performing, runs 40.7%. The alert rooms run 77–95%. The
trade-review channels — the ones you asked me to pool — run **100%**.

post-your-gains reports 100% of its rows because a row only exists there *if*
someone posted a result — that channel is survivorship by construction, not by
habit.

### 2c. The tape test — the part that settles it

Live alert rooms only (post minute = call minute; retrospective channels are
excluded because a bracket entered at a 15:07 "today's P/L" post measures nothing).
Same synthetic instrument, three populations:

| what he said afterwards | calls | tape win rate | tape mean R |
|---|---:|---:|---:|
| **"win"** | 65 | 47.7% | **+0.431** |
| **"loss"** | 17 | 5.9% | **−0.824** |
| **nothing, ever** | 147 | 28.6% | **−0.143** |

Read it in three steps:

1. **He is not lying.** The calls he labelled winners really did work on the tape;
   the ones he labelled losers really did fail. The corpus is honest about what it
   reports.
2. **The gap is the silence.** Reported winners beat never-mentioned calls by
   **+0.574R**, 95% CI **+0.154 to +0.999**, permutation p = **0.009**. That is one
   of the very few results in this project that clears its own error bar.
3. **The silent calls look like losses**, not like an unlabelled mix of both.

### 2d. What the win rate actually is

| | |
|---|---:|
| Scarface's claimed win rate (177 W / 52 L) | **79.0%** |
| Silent calls in the same room | 138 |
| Of those, that worked on the tape | 40 |
| **Reconstructed win rate** | **47.5%** |
| OMEN, one trade a day | **66.7%** |

There is a second, smaller bias inside the claimed winners: 29 of the 177 are
scale/trim messages — *"first scale here"*, *"taking some off"*. A message like
that only gets typed when the trade is already working. The label is downstream of
the outcome.

---

## 3. The other five explanations, scored

| | explanation | measured worth | verdict |
|---|---|---:|---|
| **(a)** | Day selection — they call better days | **+$111/trade**, CI −$35 to +$261, p 0.12 | inside the noise |
| **(b)** | Symbol selection — reweight OMEN's book to their symbol mix | **+$29/trade** | nothing |
| **(c)** | Entry timing | median call is **64 min** after the open vs OMEN's **28**; 59% inside the first 90 min vs OMEN's 100% | they are *later*, not earlier |
| **(d)** | Exits, letting winners run | a **perfect** exit on their calls (sell the exact session high) averages **1.21R**; 50% of calls reach 1R, 32% reach 2R, **0.4% reach 4R** | the ceiling is 1.21R and it is an oracle |
| **(e)** | Position sizing | 49 entries, 19 stops, 76 R-multiples, 54 dollar figures, out of 3,547 | not measurable |
| **(f)** | **Survivorship** | claimed 79% → **47.5%**; 54 of 54 dollar posts positive | **this is it** |

Two side notes worth having:

- **Their direction adds nothing.** On the 701 cases where OMEN traded a
  mentor-called symbol-day with a stated direction, OMEN made **0.645R** when it
  agreed with the mentor and **0.704R** when it disagreed.
- **The only significant timing slice is negative.** Calls posted after 12:30
  score **−0.226R**, CI −0.383 to −0.057. Everything inside 09:30–12:30 is flat and
  indistinguishable.
- **(d) matters for a different reason.** Even an oracle exit on their calls tops
  out at 1.21R — below the 2.0R money gate. This is the same wall
  `Projects/omen-x-board.md` already found: exits are not where 2.0R comes from.

---

## 4. TradeZella

**Format of record:** TradeZella *Generic CSV* (the path for brokers TradeZella
does not sync). Read **2026-08-29** at
<https://help.tradezella.com/en/articles/8239862-how-to-import-trades-from-unsupported-broker-into-tradezella-via-generic-csv-file-upload>
— the article shows no explicit revision date, only "Updated this week" as of that
reading.

Twelve columns, seven mandatory, and **one row per execution, not per trade**:
*"You must enter each execution individually, including both buy and sell orders."*
A round trip needs at least two rows or TradeZella books an open position with no
P&L.

| column | present in corpus | status |
|---|---:|---|
| Date | 3,547 / 3,547 | mandatory — **have it** |
| Time | 3,547 / 3,547 | mandatory — **have it** |
| Symbol | 3,547 / 3,547 | mandatory — **have it** |
| Buy/Sell | 2,795 / 3,547 | mandatory — have it for 79% |
| Spread (asset type) | 3,547 / 3,547 | mandatory — **have it** |
| **Quantity** | **0 / 3,547** | mandatory — **missing.** No field exists; prose names a contract count in 91 rows |
| **Price** | **49 / 3,547** | mandatory — **entry only. Zero exit fills exist anywhere in the corpus** |
| **Expiration** | 0 / 3,547 | options-mandatory — **missing** (96 rows say something date-like in prose) |
| **Strike** | 0 / 3,547 | options-mandatory — **missing** (269 rows name a strike in prose) |
| **Call/Put** | 0 / 3,547 | options-mandatory — **missing** |
| Commission / Fees | 0 / 3,547 | optional |

**Rows that satisfy every mandatory column: 4. Rows that can CLOSE a trade: 0.**

`research/g73_mentorbook_tradezella.csv` is written with the correct header and
those 4 rows in it — no invented quantities, no guessed strikes, no back-filled
exits. It is a demonstration of the shape, not a useful import.

**The answer is no, and it is not a mapping problem.** TradeZella wants
executions; the corpus holds opinions. The exit fill does not exist in the data at
any confidence level, so no amount of parser work produces a round trip. The one
thing that *would* work — and it is a different project — is exporting **your own**
broker fills to this format, where every column is real.

---

## What this changes

Nothing in the engine. No rule was wired, no threshold moved, no published figure
changed. What moved is a belief: **"Scarface and Jdub average higher" is not
supported by the tape, and the corpus cannot be turned into a book that says
otherwise.** The 2,604 mentor instances remain what `corpus_sf/README.md` said they
were — dated opinions, useful as a second panel to score recall against, and now
also useful as a worked example of why a Discord win rate is not a win rate.

**The one thing only Austin can decide** is unchanged and still open: do these six
people's calls count as evidence about the engine? This report says their *claimed
results* do not. Their *day and symbol choices* still might — that is what the
+$111 CI is too wide to answer, and it is answerable with more days, not more
argument.
