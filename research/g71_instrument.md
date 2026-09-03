# G7.1 / instrument — what to trade, and what data to buy to know

Austin: *"need to figure out how to use options in numbers what service do we need?"* ·
*"tastytrade im logged in on my mac so you can try to cowork use it if you want"* ·
*"i want trades that can realistically be done by a robot and where it wont get killed or
destroyed by fills or too tight rr"*

Script: `research/g71_instrument_spread.py` (`--selfcheck` first, then no args).
Diagnosis pass — **no engine file was edited.** The one fix this track wants is a diff in §5,
not applied.

---

## Headline, three sentences

1. **The +1.4988R that `DIRECTION.md:45` still calls "the instrument" is a dead number.**
   It was retracted as fatally look-ahead-contaminated by `research/t7_real_contracts.md`;
   the live, ex-ante replacement is **+0.9629R contract vs +0.8688R underlying — a null
   result** (Δ +0.0941R against a ±0.1298R bar). The instrument is not where the money is.
2. **The instrument is still where the RISK is.** Costed on the current 2,437-trade book, a
   0DTE ATM option's friction is **0.0629R per penny of spread** against **0.0342R** for
   shares and **0.0196R for one whole ES tick**. Options die at a **$0.075 round-trip
   spread**; ES survives **27.7 ticks**.
3. **Buy ThetaData "Options Standard", $80/month** (`thetadata.net/pricing`, fetched
   2026-08-29). It is the only vendor in the comparison that serves every OPRA NBBO quote
   for **expired** contracts back to 2016-01-01 at $80, and OPRA charges nothing for data
   over 15 minutes old. One or two months closes every open options assumption in this repo.

---

## 1. Audit — what the repo already models, and what is real

| file | what it is | real or modelled |
|---|---|---|
| `black_scholes.py` | textbook BSM + analytic greeks + Parkinson range-vol, `python black_scholes.py` selfchecks parity/greeks/convexity | **model.** No I/O, no globals. Correct as far as it goes. |
| `options_sizer.py:41` `ENABLE_CONTRACT_R` | env flag, **default OFF**; ON, `premium_risk` becomes a BS reprice at the stock stop instead of `stock_risk × 0.5` | **model**, and inert in production |
| `options_sizer.py:39` `DEFAULT_DELTA = 0.5` | still the shipped fallback and what the live path actually uses | **flat linear delta** |
| `dxlink.py` | DXLink websocket, `fetch_quotes()` — one-shot bid/ask for a streamer symbol | **real, but LIVE ONLY.** No history. |
| `tastytrade_feed.py` | session auth + nested option chain + `fetch_option_quote` | **real, live only** |
| `polygon_feed.py` | `/v2/aggs/ticker/{sym}/range/1/minute/` — Polygon's **stocks** aggregates | **real underlying bars.** Polygon options snapshot returns `403 NOT_AUTHORIZED` on this key (`t2_options_tape.md` §A5, `t9` §3) |
| `market_data.py` | reads the same cached CSVs; SPY/VIX daily closes | **real underlying** |
| `futures_feed.py` | yfinance `ES=F/NQ=F/RTY=F`, **live only, never writes `data_archive/`** | real, unusable for backtest |
| `paper_trader.py:95-120` | premium stop fill = plan's own `premium_risk/stock_risk` ratio × underlying move | **linear**, explicitly "there is no options tape in this repo to do better" |

**There is no options tape in this repo.** Every option price ever published here is
Black-Scholes on Parkinson range vol. `research/t7_real_contracts.py` is the one exception
and only partly: it reaches real Alpaca 1-minute option **bars** (OHLC prints, not bid/ask)
on **276 of 1,016 rows (27.2%)**, and even there the R *denominator* is always modelled,
because a real tape cannot contain a price for a level the stock never reached.

### Is +1.4988R look-ahead-free? No. It is the dead one.

- `research/x13_new_angles.md:46` published it; `research/t2_options_tape.md:109` reproduced
  it to four decimals with an independent pricer.
- `research/t2_options_tape.py:193` reads `row.get("drange")` — **the full-session high-low
  range** — and feeds it to `parkinson_sigma`. That sigma sets the premium, the premium is
  the R denominator, so **the size of the day's eventual move set the unit the day's own
  result was scored in.** T2's own §A2 measured the leak at **−0.3153R, "91% of the
  instrument's advantage."**
- `research/t7_real_contracts.md` then retracted T2 outright ("**retracted, fatal**… ninety
  percent of that headline was the leak; ex-ante the contract was worth +0.0356R, not the
  reported +0.3575R") and re-ran it on prior-session sigma only: **contract +0.9629R vs
  underlying +0.8688R, Δ +0.0941R ± 0.1298R — null.**
- `research/t8_strike-sweep.md` independently swept {0DTE,1DTE}×{ATM−1,ATM,ATM+1} on the
  ratified book: every arm inside a ±0.16R bar of every other. **No strike or expiry choice
  moves the money gate either.**

### Two stale-fact bugs, both live right now

1. **`DIRECTION.md:45` still cites +1.4988R as the instrument's value**, and does so against
   the underlying's **+0.5481R** — which is a *different book* (2,595 rows) from the one
   +1.4988R was measured on (1,017 rows, underlying +0.9994R SINGLE). It is a retracted
   number compared against a book it was never measured on. Anyone reading `DIRECTION.md`
   cold concludes the instrument is worth +0.95R. It is worth **+0.09R ± 0.13R**.
   `PHASES.md:118` already says T2 is "void" — the two files contradict each other, and
   `PHASES.md` repeats +1.4988R in the same sentence as "the honest ceiling to beat."
2. **`research/t2_options_tape.md` carries no retraction banner.** `grep -in
   "retract\|void\|superseded"` on it returns nothing. The most detailed, most
   confident-sounding options document in the repo reads as live and is void.

---

## 2. What data service to buy

Requirement: real historical **NBBO bid/ask** on **0DTE** contracts, ≥1-minute granularity,
for the book's symbols, over **2024-08-21 → 2026-08-21**, including contracts that have
**already expired**. That last clause is what kills most of the field.

| vendor | 0DTE NBBO history? | expired contracts? | depth | price (fetched 2026-08-29) | verdict |
|---|---|---|---|---|---|
| **ThetaData Options Standard** | **yes — every NBBO quote reported by OPRA, tick level, any interval** | **yes — "expired, delisted, adjusted and non-standard options are all included"** | **from 2016-01-01** | **$80/mo** | **BUY** |
| ThetaData Options Value | no — 1-minute OHLC only, no NBBO | yes | from 2020-01-01 | $40/mo | too thin — the spread is the question |
| ThetaData Options Pro | yes | yes | from 2012-06-01 | $160/mo | overkill; 2016 depth already covers 2y |
| Polygon (now `massive.com`) Options Developer | **no — quotes are 15-min delayed only** | yes | 4y | $79/mo | fails the requirement |
| Polygon/Massive Options Advanced | real-time quotes; historical quote endpoint present but this repo's key **403s on the options snapshot** today | yes | 5y+ | $199/mo | 2.5× the price of the winner |
| Databento OPRA | yes, pay-as-you-go $/GB + a $199/mo Standard plan | yes | full | usage-based, **rate card not public** | good data, unpriceable without a sales call; OPRA is the largest feed in existence so $/GB is a real risk |
| Cboe DataShop "Option Quote Intervals" | yes — 1-min NBBO+size+OHLC, **from January 2012** | yes | 13y | **no list price**; cart quotes per symbol-day, sales at +1 800 307-8979 | usable, but a purchase order, not an API key |
| dxFeed | yes (Candlewebservice / HDL) | yes | full | "from $19/mo" retail, real historical volume is a sales conversation | same problem as DataShop |
| **IBKR TWS API** | **no** | **NO — "expired options data is not available"; `includeExpired` works for futures, not options** | — | free with account | **structurally impossible** |
| **Tastytrade API** | **no** | **no** | — | free with account | **live quotes only** |

### On "tastytrade im logged in on my mac so you can try to cowork use it"

Worth saying plainly: **Tastytrade cannot answer this question, and neither can being logged
in.** `dxlink.py` + `tastytrade_feed.py` already work; what they return is a *live* Quote
event for a *currently listed* contract. There is no historical-quote endpoint, and DXLink
Candle history does not cover expired option symbols. Being logged in on the Mac buys
nothing the repo does not already have.

**What Tastytrade IS for, and it matters:** it is the execution venue, and its published fee
schedule (below) is what makes the §3 arithmetic real rather than assumed. It is also the
right place to log a live NBBO sample *going forward* — `dxlink.fetch_quotes` against
tomorrow's 0DTE chain at 09:30–11:00 would produce a real spread series in a week. That is
the free path; it just cannot go backwards over the 2-year book.

### Recommendation

**ThetaData Options Standard, $80/month, cancel after two months.** $160 total.
Sources: [pricing](https://www.thetadata.net/pricing) (Value $40 / Standard $80 / Pro $160),
[subscription depth table](https://http-docs.thetadata.us/Articles/Getting-Started/Subscriptions.html)
(STANDARD = tick level, real-time, history from **2016-01-01**),
[OPRA fee guide, 2026-05-29](https://www.thetadata.net/articles/2026-05-29-opra-fee-guide-for-options-market-data)
— *"There are currently no OPRA fees for using or redistributing data that is over 15 minutes
delayed"*, so a purely historical pull carries **$0** exchange fees on top of the $80.

What $160 closes, all of which are currently open parameters:

| open question | where it is open | what ThetaData settles |
|---|---|---|
| A5 — the round-trip spread | `t2` §A5, `t9` §2, `x9` §2.2 — swept, never observed | the actual NBBO on the actual contract at the actual minute |
| A2 — the IV level | `t2` §A2 (the leak), `t7` (prior-session proxy) | real IV, no Parkinson proxy at all |
| A7 — flat vol surface / no IV crush | `t2` §A7, "unmeasurable without an options tape" | measurable |
| **the 72.8% modelled rows** | `t7` — Alpaca's reference endpoint only lists *active* contracts, so 740 of 1,016 rows could not be matched to a strike | `option/list/expirations` + `option/list/strikes` return what was **actually listed on that date**, expired included |
| A9 — fills at median 46, p90 142 contracts | modelled nowhere | NBBO **size** comes with the quote |

The 72.8% row is the one that is uniquely ThetaData's. T7 could not tell "no 0DTE existed
that day" apart from "we guessed the wrong strike," and it flagged that as unclosable by
retrying. It is closable by buying the listing history.

---

## 3. Options vs shares vs futures — the friction, measured

All numbers `python research/g71_instrument_spread.py`, on `research/bt2y_trades.json`,
**2,437 traded rows** (note: *not* the 2,595 T0/T9 cite — the book has moved since).
Premiums via `t7_real_contracts.Contract` — prior-session Parkinson sigma × 1.2, **no
same-day range**, asserted by `--selfcheck`. Fees are quoted from the tastytrade
[Commissions & Fees schedule, last updated 2026-07-30](https://assets.contentstack.io/v3/assets/blt7dc2e3d4a7071563/blt2b752fef372188fe/commissions-and-fees)
and the CME 2026 non-member rate (ES $1.18/side, MES $0.25/side, NFA $0.02/side).

### The R denominator — this is the whole story

| instrument | 1R is | p10 | median | p90 |
|---|---|---:|---:|---:|
| shares | $ of stock risk per share | 0.150 | **0.450** | 1.270 |
| 0DTE ATM option | $ of premium risk per share | 0.070 | **0.217** | 0.600 |
| ES | index points | 8.25 | **14.75** | 36.75 |

The option's 1R is a **2.1× thinner** unit than the stock's. A fixed cent of spread
therefore hurts 2.1× more, before anything about options is even discussed.

### Friction per trade, in R (spread crossed once round trip, plus all fees)

```
-- SHARES --                          -- 0DTE ATM OPTIONS --
spread    mean R  median  +fees       spread    mean R  median  +fees
$0.01     0.0342  0.0222  0.0506      $0.01     0.0629  0.0460  0.1412
$0.02     0.0683  0.0444  0.0848      $0.02     0.1259  0.0921  0.2041
$0.05     0.1708  0.1111  0.1873      $0.05     0.3146  0.2302  0.3929
$0.10     0.3417  0.2222  0.3581      $0.10     0.6293  0.4605  0.7075
fees alone            0.0164 R        fees alone            0.0782 R

-- ES / MES FUTURES --
one whole tick crossed        mean 0.0196 R   median 0.0169 R   p90 0.0303 R
ES fees ($5.00 round turn)    mean 0.0078 R
ES all-in, 1 tick + fees            0.0274 R
ES+MES blend (whole ES, MES rest)   0.0379 R
```

**Read the fee row on options.** $1.24/contract round turn × a **median 46 contracts** is
**0.0782R of pure commission per trade** — 4.8× the share book's 0.0164R, before one cent of
spread. On a book that means +0.55R, commissions alone are 14% of the edge.

### What kills each instrument

| instrument | book mean R | fees | dies at |
|---|---:|---:|---|
| shares | +0.5495 | 0.0164 | a **$0.156** round-trip spread |
| 0DTE ATM options | +0.5501 | 0.0782 | a **$0.075** round-trip option spread |
| ES futures | +0.5513 | 0.0078 | **27.7 ticks** of slippage |

ES is quoted **one tick wide** in RTH. The strategy would have to eat 28× the posted spread
before futures friction ate the edge. The $0.075 option number is this book's version of
T9's $0.095 (T9 measured the 2,595-row book and used contract R as the edge; this uses
underlying R on 2,436 rows, which T7 says is the same thing inside its bar). **A $0.075
round-trip 0DTE ATM spread is not comfortable headroom** — it is a nickel and a half, and
nobody in this repo has read a real one.

### "can realistically be done by a robot" — the fill-size question

| instrument | median size at $1,000 risk | the problem |
|---|---|---|
| shares | **2,222 shares, $434k notional** (p90 $751k, max $10.97M) | needs **$109k** of 4:1 day-trading buying power *per trade* (p90 $188k). Nothing to do with spread — it is a capital wall. |
| 0DTE ATM | **46 contracts** (p90 142, max 200); **18.9% of rows want ≥100 contracts** | a 100-lot at the mid on a 0DTE ATM is not a mid fill. Median **$8,068** cash debit, **34.4% of rows need >$10,000 debit to risk $1,000.** |
| ES | **1.36 contracts** — and **30.0% of rows want under one whole contract** | granularity, solved by MES (median 13.6 MES) at 0.0379R all-in |

**This is the real argument for options and it is not an edge argument.** Options turn a
$109k buying-power requirement into an $8k debit with a hard-capped loss. That is capital
efficiency and it is why the prop account exists. It costs **0.14R–0.39R a trade** in
friction to buy it (at $0.01–$0.05 spreads), against **0.05R–0.19R** for shares and
**0.03R** for ES.

### Verdict: which instrument

**Trade it as 0DTE ATM options, keep trading it as options, and stop expecting the
instrument to pay for the money gate.** Reasons, in order:

1. **Nothing else is affordable.** Shares need $109k of buying power per trade at 4:1;
   futures need a data purchase the repo has not made and a strategy that has never been run
   on ES (`t17_futures-feasibility.md`: `data_archive` holds **16,817 symbol-days, zero of
   them futures**). Options need $8k and cap the loss.
2. **The instrument is edge-neutral, not edge-positive** (T7 null, T8 null). Choosing it is a
   capital and risk decision, not a P&L one. `DIRECTION.md` currently says the opposite.
3. **Futures would be the cheapest instrument by 5–10×** on friction and it is not close —
   but ES is a *different market*, not a cheaper wrapper on the same signals. Five of OMEN's
   six levels transfer; PMH/PML does not (no premarket on a 23/5 session) and needs a rule
   from Austin. Treat "instrument" and "futures" as two separate decisions.
4. **The `−1.25R` floor is a real, unresolved risk on the option side.** `t2` §4 measured it
   binding on **4.3% of contract rows against 0% of underlying rows**, worst row **−7.9R**
   without it, and `paper_trader.py:110` says in its own comment the floor is not applied on
   the premium side. A stop that triggers on the *underlying* does not cap the *contract's*
   loss. That is a live-money hole, not a backtest artifact, and it is Austin's call.

### The one thing to fix in execution, cheap

**Median 46 contracts is a marketable-limit order, not a market order.** Austin, 2026-08-28:
*"market and limit orders a different beast."* Every figure in this repo is a mid fill, which
is neither. On a $0.075 death threshold, a market order on 46 lots of a 0DTE ATM contract is
the single most likely way this strategy dies in production, and it is invisible to every
rig here. The ThetaData purchase makes it measurable: NBBO **size** ships with the quote, so
"was there 46 lots at the offer at 09:42" becomes a query.

---

## 4. Recall gate

This track is a friction calculator on an already-selected book — same rows in, same rows
out. It cannot move held-out recall (18/34 = 52.9%) by construction, and it edits no
detection file. `--selfcheck` asserts `backtest_2y.py` / `backtest_week.py` /
`signal_runner.py` do not import it.

---

## 5. Proposed diff — NOT applied

Two stale published numbers. This is a diagnosis pass, so the diff sits here.

```diff
--- a/DIRECTION.md
+++ b/DIRECTION.md
@@ -42,9 +42,12 @@
 3. **Mean R 2.0 is arithmetically unreachable on the current exit.** `mean R = wT − (1−w)`;
    at 54% win the average *winner* must make **4.56R**, and every row plans exactly 2.000 R:R.
    The whole exit family is worth **+0.06R** against a 1.10R gap. What clears the gate is the
-   **instrument** (the same rows as 0DTE ATM contracts read **+1.4988R**) and **selection**
-   (one-trade-per-day oracle **+2.2125R at 76.6% win**). See `Projects/omen-x-board.md`.
+   **selection** lane (one-trade-per-day oracle **+2.2125R at 76.6% win**) and nothing else
+   measured. See `Projects/omen-x-board.md`.
+   **The instrument is NOT a lever and the +1.4988R that used to sit here is retracted.**
+   It came from `research/t2_options_tape.md`, whose sigma was the day's own full-session
+   range; `research/t7_real_contracts.md` re-ran it ex-ante and got **contract +0.9629R vs
+   underlying +0.8688R, Δ +0.0941R against a ±0.1298R bar — null.** `research/t8_strike-sweep.md`
+   swept 0DTE/1DTE × ATM±1 and every arm lands inside ±0.16R of every other.
```

```diff
--- a/research/t2_options_tape.md
+++ b/research/t2_options_tape.md
@@ -1,4 +1,13 @@
 # T2 — The options tape
+
+> **RETRACTED 2026-08-29 — FATAL. Do not quote any number in this file.**
+> The premium — and therefore the R denominator — was priced with Parkinson sigma built
+> from `drange`, the day's **full-session** high-low range, which is not knowable at the
+> entry minute (`research/t2_options_tape.py:193`). This file's own §A2 measured the leak
+> at −0.3153R, "91% of the instrument's advantage." The ex-ante replacement is
+> `research/t7_real_contracts.md`: contract **+0.9629R** vs underlying **+0.8688R**,
+> Δ +0.0941R ± 0.1298R — a **null result**. §4 (the −1.25R floor binding on 4.3% of
+> contract rows) and §7 (open questions) survive as directional flags only.
```

---

## 6. What did not run

- **No real NBBO was read.** Every spread figure in §3 is a swept parameter, exactly as in
  `t9` §2 and `t2` §A5. That is the purchase this report recommends, not a gap it closes.
- **No futures backtest.** `data_archive` has zero futures bars (`t17`); the ES column maps
  each row's own `stop_pct` onto `10 × SPY close` for that day, rounded to a real 0.25 tick.
  That is a **geometry transfer assumption**, not a measured ES result — it says "if the same
  stop geometry existed on ES," and nothing about whether the setups fire there.
- **ES intraday margin is broker-set** ($500–$2,500/contract is the usual retail band); not
  quoted from a source and not used in any calculation.
- **The `−1.25R` premium-side floor was not fixed**, only flagged. It needs Austin.
- **No Tastytrade live NBBO sample was logged.** `dxlink.fetch_quotes` could start one
  tomorrow at 09:30; that is a separate small ticket.
