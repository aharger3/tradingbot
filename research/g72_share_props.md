# G7.2 / share_props — the equity/share prop field, compared, and why Trade The Pool

Researched **2026-08-29**. Every URL below was retrieved that day.
Scripts committed with this note: `research/g72_consistency_sim.py` (the consistency-rule
bite), `research/g72_ttp_commission.py` (TTP's per-share commission in R).
Extends `research/g71_propfirm.md` — it is not re-run here, it is challenged.

---

## Headline, four sentences

1. **Trade The Pool still wins, but the prior research won for the wrong reason.**
   g71 ranked it on pass-rate arithmetic. The real reason it wins is that it is the only firm
   in this field that is simultaneously **(a) open to a US resident, (b) quoting real single
   US stocks, and (c) publicly, contractually supporting automated order entry.** Nine of the
   eleven firms on the brief fail at least one of those three, and most fail two.
2. **The automation gate — new fact #2 — is decisive and the prior research never applied it.**
   TTP's own Program Terms say *"Support for automated trading, including the specific
   integration with SignalStack, is currently in a beta state"*, while its Terms & Conditions
   §11.1 still say *"The User may not use any custom, algorithmic, or other automated trading
   software (collectively, 'Automated Trading Software') to execute trades."* **Both are live
   on the site today.** That contradiction is TTP's single largest risk, not its drawdown.
3. **TTP's biggest weakness for a one-trade-a-day robot is the consistency rule, and it is a
   function of risk-per-trade, not of the strategy.** Measured on the book: at the prior
   research's recommended **$250/trade on the $50k FLEX, the best day exceeds 50% of net
   profit on 20.4% of passing runs**; at **$150/trade it is 0.0%**. On MAX's 30% rule at
   $250 it is **79.9%**. The rule does not punish his edge — it punishes *finishing fast*.
4. **The runner-up is Funder Trading** (Chicago; NASDAQ/NYSE stocks and equity options; 80/20;
   firm covers losses). It is the only other firm putting a US resident into real US equities.
   It loses on cost transparency (recurring subscription, unpublished price) and on a
   **minimum 80 round-turn trades** requirement that a one-trade-a-day robot needs ~4 months
   to satisfy.

---

## 0. The three gates, applied before any rule is read

A firm has to clear all three before its consistency rule or drawdown type matters at all.

| gate | why | who fails |
|---|---|---|
| **US resident accepted** | Austin is a US resident. MetaQuotes pressure drove a wave of US bans in 2024 and most never fully reversed ([Finance Magnates, 2024-02-20](https://www.financemagnates.com/forex/breaking-prop-trading-firm-blue-guardian-joins-others-to-restrict-us-clients/): *"FTMO, The5ers, Alpha Capital Group, MyFundedFX, Audacity Capital, and many more"*) | City Traders Imperium (*"does not currently accept U.S. traders due to regulatory restrictions"*), FTMO, Seacrest Funded (= MyFundedFX), Blue Guardian (restricted, partially reopened via DXtrade) |
| **Real single US stocks** | The signal is break-and-retest on 29 US tickers at six intraday levels. Index CFDs and index futures do not carry NVDA, TSLA, PLTR, COIN | Sure Leverage (FX/indices/commodities/crypto on TradeLocker), Hantec Trader (FX/bullion/indices/energies/crypto), Blue Guardian, Seacrest, TradeDay (CME futures), **OneUp Trader (futures only — there is no OneUp equities product)** |
| **Automation permitted** | *"you will be trading it not me"* | FundedNext (US CFD clients are confined to Match-Trader, and *"EAs are available only on MT4/MT5 … so US clients cannot use them"*), Sure Leverage (EAs only on a separate EA Challenge, *"banned in all other funded stages"*), Seacrest (no EAs on MT5 except via STT) |

**Two firms clear all three: Trade The Pool and Funder Trading.** Everything else on the brief
is disqualified at gate 1 or 2, before a single consistency clause is read.

---

## 1. The field

### Cleared all three gates

| | **Trade The Pool** | **Funder Trading** |
|---|---|---|
| route | share-prop, evaluation | share/options-prop, subscription evaluation |
| instrument | **real US shares, warrants, ETNs, ETFs, ETPs tradeable on Nasdaq**; TraderEvolution platform routed to Interactive Brokers. **No options.** | **NASDAQ + NYSE stocks**, ≤1,000 shares per security on the challenge; funded lane adds **US equity options** |
| sizes | $5k / $25k / $50k / $100k / $200k buying power; scales to ~$450k | up to $100k, scaling to $200k–$250k (marketing) |
| cost to start | **one-time**, $47–$1,475 (FLEX $59 / $120 / **$285** / $545 / $1,475; MAX $47 / $97 / $230 / $435 / $1,100). No monthly fee. Non-refundable once traded | **recurring** TrueEdge Challenge subscription + separate market-data subscription. **Price is not published.** Third-party reviews report ≈$500/mo — **UNVERIFIED** |
| own capital required | **$0** | $0 (fees only); challenge cost reimbursed on funding |
| licensing required | none | none published |
| profit target | **6% of buying power** ($3,000 on $50k) | **$5,000** |
| max daily loss | FLEX **2%** of BP / MAX **1%** — a *Daily Pause*, not a fail: *"all open positions and orders are closed and the account is prevented from opening trades until the opening of the next trading day"* | **$500**, and **no more than 3 daily max losses per challenge** — the 4th is a fail |
| max drawdown | FLEX **4%** / MAX **3%** of BP. Static from the initial balance, then it *rises*: once equity reaches 3× the daily loss limit *"the max drawdown for the account will move to the initial balance"* | **$3,000** |
| drawdown type | **intraday equity** (*"the current equity (projected balance) at each moment"*), static floor, one upward lock. **Not trailing.** | UNVERIFIED whether intraday or EOD |
| consistency rule | *"The maximum position profit ratio is 30% unless otherwise specified; that is, the User's best position cannot be responsible for more than 30% (or the relevant ratio) of the total valid profit earned."* MAX = **30% eval / 70% funded**; **FLEX = 50% eval and funded** | not a % rule — instead **≥80 round-turn trades**, **win/loss ratio ≥1.20**, **BAT ≥40%** |
| other gates | min **10 positions** (FLEX) / **20** (MAX); each position ≥10 price ticks profit and ≥60 s hold; FLEX funded needs **3 × 0.5% profitable days per payout cycle**; 14-day inactivity can close the account | ≥**12 trading days inside a calendar month** (of 22); **no overnight — flat by 3:55pm ET** |
| time limit | **FLEX unlimited**; MAX Day 60 calendar days; MAX Swing 100 | rolling monthly while subscribed |
| payout split | **70/30** | **80/20**, 100% until challenge costs are repaid |
| payout frequency | min **$300** balance ($150 on $5k), **≥14 days** since last payout/activation, paid in 3–5 business days | UNVERIFIED |
| **automation** | **CONDITIONAL — the central finding, §2** | **UNVERIFIED — no published policy** |
| fits 09:30–11:00, 1 trade/day | **yes** — the FLEX 10-position minimum is met in 10 sessions | **weak** — 80 round turns at 1/day ≈ 80 sessions ≈ 4 months of subscription |
| notes | simulated environment (their own disclaimer); commission **$0.75 min/execution ≤150 sh, else $0.005/share** — measured drag in §5 | Chicago LLC, unregulated; its own Terms frame it as an educator; strict no-refund |

Sources: [tradethepool.com/program-terms/](https://tradethepool.com/program-terms/) ·
[tradethepool.com/the-program/](https://tradethepool.com/the-program/) ·
[tradethepool.com/terms-and-conditions/](https://tradethepool.com/terms-and-conditions/) ·
[quantvps.com/prop-firms/trade-the-pool](https://www.quantvps.com/prop-firms/trade-the-pool) (commissions) ·
[fundertrading.com/trueedge-challenge/](https://fundertrading.com/trueedge-challenge/) ·
[proprietaryfirms.com/funder-trading-review/](https://proprietaryfirms.com/funder-trading-review/).

### Disqualified, with the reason

| firm | route | why it is out |
|---|---|---|
| **OneUp Trader** | futures-prop | **There is no OneUp equities account.** NinjaTrader/Rithmic, CME futures only — *"traders are restricted to futures only – no forex, crypto, or equities."* Also the harshest consistency rule found: *"3 best days must total at least 80% of the best day"* |
| **Sure Leverage Funding** | CFD | No US single stocks — FX, stock **indices**, commodities, crypto on TradeLocker. EAs permitted **only** on a dedicated EA Challenge, *"banned in all other funded stages"*; 8% target / 8% DD one-phase; a floating-loss rule closes the account on a second 1% breach |
| **Hantec Trader** | CFD | No US shares — FX majors/minors, bullion, indices, energies, crypto. (EAs *are* allowed on One-Step and Two-Step, not on Instant Funding — a good automation policy attached to the wrong instrument) |
| **Seacrest Funded** (MyFundedFX) | CFD | US clients restricted; 5% daily / 8% max, real-time drawdown; EAs not allowed on MT5 except via STT Social Trader Tools |
| **City Traders Imperium** | CFD | *"does not currently accept U.S. traders."* Otherwise the best automation policy in the field: EAs allowed, source code submitted and verified on funded accounts |
| **Blue Guardian** | CFD | US registrations restricted; FX/indices/commodities/crypto, no single US stocks; *Guardian Shield* force-closes all trades at 2% unrealised loss |
| **TradeDay** | futures-prop | CME futures only, no equities; 3-day minimum |
| **FundedNext (stocks)** | CFD | Has TSLA/AAPL/META stock CFDs, but **US CFD clients are confined to Match-Trader, which has no EA support** — automation is structurally impossible for Austin |
| **FTMO** | CFD | Equity indices and stock baskets only; US clients restricted |
| **Lux Trading Firm** | CFD/DMA | 250+ stocks incl. TSLA; MT5 / MatchTrader / TradingView / Lux Trader DMA. Positioned for swing and long-horizon, not a 90-minute intraday window. **US client eligibility UNVERIFIED** |
| **Bright Trading** | real broker-dealer desk | Real equities on firm capital, but **SIE + Series 57 required and a ~$15,000 risk deposit** — above Austin's $10k buffer even after new fact #1 |
| **Seven Points Capital** | real broker-dealer desk | No capital contribution required, but it is an employed-trader desk (NYC/NJ/FL) with Series 57 registration — not a remote robot arrangement |

---

## 2. Automation — the gate g71 never applied, and TTP's live contradiction

This is the finding that most changes the answer, and it cuts **for** TTP, not against it.

**What TTP's Program Terms say** ([tradethepool.com/program-terms/](https://tradethepool.com/program-terms/), retrieved 2026-08-29):

> *"Support for automated trading, including the specific integration with SignalStack, is currently in a beta state."*
> *"a rate of no more than 2 requests/min should be targeted"*
> *"the trader is responsible for all trades conducted on the account regardless of whether manually or automatically created"*
> the Company reserves *"approval for any algorithm, integration, or client."*

**What TTP's Terms & Conditions say** ([tradethepool.com/terms-and-conditions/](https://tradethepool.com/terms-and-conditions/), same day), §11.1:

> *"The User may not use any custom, algorithmic, or other automated trading software (collectively, 'Automated Trading Software') to execute trades."*

and §10.1.7 additionally bans *"Using any software, artificial intelligence, ultra-high speed,
or mass data entry which might manipulate, abuse, or give User an unfair advantage."*

**Both documents are live.** The Program Terms are the more specific and more recent instrument
and are the ones the SignalStack launch was built on — TTP announced the integration publicly on
**2025-08-18** ([GlobeNewswire](https://www.globenewswire.com/news-release/2025/08/18/3135196/0/en/Trade-The-Pool-Launches-No-Code-Trading-Automation-with-SignalStack-Integration.html))
and publishes its own how-to videos
([Webhook, How it Works](https://tradethepool.com/trading-video/webhook-how-it-works/) ·
[Linking TTP and SignalStack](https://tradethepool.com/trading-video/how-to-link-ttp-and-signalstack/) ·
[Automated ORB Strategy](https://tradethepool.com/trading-video/orb-strategy-automated-signalstack/) —
note that the worked example is an **opening-range-breakout bot**, which is Austin's window and
close to his setup).

But §11.1 has not been amended to carve out the exception. **A firm that has both texts live can
enforce either one at payout time.** That is the risk, and it is not hypothetical: voiding a
payout for automation is the standard prop-firm failure mode.

### What the sanctioned path actually is, and what it costs

The permitted channel is a **webhook** — TradingView/TrendSpider alert → SignalStack → TTP order
— not a direct API client of Austin's own. SignalStack pricing
([signalstack.com/pricing](https://signalstack.com/pricing), retrieved 2026-08-29):

| plan | $/mo | signals/mo | $/signal |
|---|---:|---:|---:|
| Free | 0 | 5 | — |
| Basic | 27 | 50 | 0.54 |
| **Premium** | **97** | **250** | 0.39 |
| Pro | 340 | 1,000 | 0.34 |

*"a trade order successfully sent to a linked broker account"* is one signal; unused signals
expire monthly; claimed *"less than .45 seconds"* to the broker.

**Sizing it for this robot:** one trade a day, and each trade is entry + stop + target +
(possibly) a break-even move = 3–4 orders. ~21 sessions × 4 = **~84 signals/month**. Basic (50)
is too small; **Premium at $97/mo is the right tier**, and the 2-requests/min cap is a non-issue
for a setup that fires once a session. Budget **$97/mo on top of the one-time evaluation fee**.

An independent bridge, [TradersPost](https://traderspost.io/connections/trade-the-pool), lists
Trade The Pool as **"Coming Soon"** with a waitlist and explicitly states it is *"not affiliated
with, endorsed by, sponsored by, or authorized by Trade The Pool"* — so it is not a sanctioned
route today.

**Action before paying anything: email TTP support and get the automation carve-out in writing,
naming §11.1.** A one-line reply confirming SignalStack webhook entry is permitted on evaluation
*and* funded accounts converts the single largest risk in this comparison into a non-issue, and
costs nothing.

---

## 3. The consistency rule, measured on the book — not asserted

A consistency rule caps the share of total profit one position may contribute. **With one trade
a day, position == day**, so it becomes: *best winning day ≤ K × total profit*. That is exactly
the case Austin is worried about, and the book has a **9.500R** best day in it.

`research/g72_consistency_sim.py` bootstraps the 496-session daily-R series (the first traded
signal of each session; mean **+0.5809R**, **54.4%** win) over 20,000 paths per cell, walks each
to a pass or a drawdown breach, then measures the ratio the firm would actually compute — under
both readings of *"total valid profit"*: **GROSS** (winning days only, the strict reading) and
**NET** (the account's net gain, the kind reading).

| account (rule K) | risk/trade | pass % | median days | best/GROSS | **P(breach)** | best/NET | **P(breach)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| **TTP $50k FLEX (K = 50%)** | $100 | 98.6% | 50 | 11.8% | **0.0%** | 21.1% | **0.0%** |
| | **$150** | **99.7%** | 33 | 16.0% | **0.0%** | 27.0% | **0.0%** |
| | $200 | 99.2% | 24 | 19.8% | 0.6% | 32.8% | 4.2% |
| | **$250** *(g71's pick)* | 98.2% | 19 | 23.2% | **2.7%** | 38.6% | **20.4%** |
| | $400 | 92.6% | 11 | 32.5% | 16.5% | 50.6% | 51.5% |
| | $750 | 78.5% | 5 | 50.7% | 51.6% | 68.6% | 85.8% |
| **TTP $50k MAX (K = 30%, 60 d)** | $150 | 88.7% | 31 | 16.9% | 4.1% | 27.3% | 40.8% |
| | $250 | 93.6% | 19 | 23.5% | **28.4%** | 38.6% | **79.9%** |
| | $500 | 79.8% | 8 | 39.1% | 73.5% | 55.9% | 98.8% |
| **TTP $100k FLEX (K = 50%)** | $250 | 99.4% | 40 | 14.0% | **0.0%** | 24.6% | **0.0%** |
| | $500 | 98.3% | 19 | 23.3% | 2.8% | 38.6% | 20.6% |
| **TTP $25k FLEX (K = 50%)** | $150 | 96.9% | 16 | 26.5% | 6.7% | 43.6% | 29.4% |

### What this says

- **The consistency rule is a tax on speed, not on the strategy.** Every row where the rule
  bites is a row where he sized up to finish in under ~15 sessions. Risk **$150** on a $50k FLEX
  and the rule is unreachable under either reading; risk **$750** and it fires on half the runs.
- **g71's F4 ("survivable, but only just") was right in direction and understated in size.** F4
  measured the *cost in extra trading days* (0–1) and never measured *breach probability*. At its
  own recommended $250 the strict-reading breach is a tolerable 2.7% — but the NET reading
  breaches **20.4%** of the time, which is **twice Austin's stated 10% tolerance**. **The
  recommendation is only safe if TTP measures against gross winning profit.** That wording is
  worth an email too.
- **MAX is disqualified for this robot on the consistency rule alone**, independent of its 60-day
  clock. 28.4% / 79.9% at $250 is not a rule you plan around.
- **The bigger account dilutes the rule for free.** $100k FLEX at $250/trade is 99.4% pass and
  **0.0% breach on both readings** — the same dollar risk against a 2× target simply takes 40
  sessions instead of 19, and 40 days cannot be dominated by one. The extra $260 of evaluation
  fee buys the consistency rule away entirely.

---

## 4. Drawdown type — TTP is intraday, and that is the right way round for this strategy

| property | TTP | typical futures prop | why it matters to this robot |
|---|---|---|---|
| measured on | **intraday equity** — *"the current equity (projected balance) at each moment minus the balance (realized) at the start of the day"* | mostly EOD | intraday is normally the harsher choice — but this strategy holds **one position inside a 90-minute window and is flat by 11:00**, so open-equity excursion is bounded by that one position's own MAE. There is no overnight and no multi-day carry for an intraday floor to catch |
| floor | **static from the initial balance**, then locks **upward**: at 3× the daily loss limit *"the max drawdown for the account will move to the initial balance"* | usually **trailing** to the EOD peak | static is strictly better. A trailing floor converts every winning day into a tighter leash; TTP's does the opposite |
| daily limit | a **pause**, not a fail — positions closed, account locked until next session | Topstep same; Apex / TPT / MFFU have none | for a one-trade-a-day robot a daily pause is nearly free: it can only ever trigger on the one trade already taken |

**The intraday-vs-EOD question is close to moot for this strategy, and that is a point in TTP's
favour rather than against it.** The firms whose intraday drawdown *would* hurt are the ones
holding overnight — which TTP's Day accounts forbid anyway.

The one real cost: because the floor is static and does not trail, **the ratio that matters is
target ÷ max-loss**. On a $50k FLEX that is $3,000 ÷ $2,000 = **1.5 : 1** — the same ratio as a
Topstep 50K Combine and worse than Apex 50K EOD's 1.2 : 1. TTP is not generous here; it is
merely average, with a better *shape*.

---

## 5. Friction: what TTP's commission takes out of the edge

`research/g72_ttp_commission.py`, on the 2,437 traded rows of `research/bt2y_trades.json`:

```
shares/trade            p10    787   median   2,222   p90   6,667
TTP round-trip comm     p10 0.0079R  median  0.0222R  p90 0.0667R   mean 0.0342R
```

**Mean 0.0342R = 6.2% of the book's +0.5481R edge, from commission alone**, and it is
**invariant to risk-per-trade** (per-share pricing scales with the position). Add the
$0.01-spread cost from `research/g71_instrument.md` (shares, 0.0342R) and all-in friction is
**≈0.068R ≈ 12% of the edge**. Real but survivable — the same document puts the share book's
break-even at a **$0.156** round-trip spread.

Note this is *worse* than g71_instrument's fee row (0.0164R), which was costed on tastytrade's
commission-free equities. **Trading at TTP costs roughly 2× the commission of trading Austin's
own account.** That is the standing price of the leverage and should be subtracted before
comparing a funded account against self-funding.

---

## 6. The three questions, answered

### 6.1 Does Trade The Pool actually win, or did the prior research just stop looking?

**It wins — but g71 reached the right answer on the wrong evidence, and it did stop looking.**

What g71 got wrong or skipped:

- It **never applied the automation gate.** Fact #2 is the sharpest filter in this market. It
  eliminates FundedNext-for-US-clients, Sure Leverage's funded stages and Seacrest outright; it
  also nearly eliminates TTP (§11.1) and then *rescues* it via the Program Terms / SignalStack
  carve-out that g71 never found.
- It **never applied the US-residency gate.** CTI, FTMO, Seacrest and Blue Guardian are out
  before instruments are discussed. g71 lumped four of these into one row and dismissed them as
  "FX/CFD shops"; the accurate reason is stronger and simpler.
- It **missed Funder Trading entirely** — the one other firm giving a US resident real US
  equities *and* equity options, which is exactly the lane new fact #1 re-opens.
- It **stated TTP's max loss as "static from the initial balance."** It is static and then
  **locks upward** at 3× the daily loss limit. Directionally favourable, but the note was wrong.
- Its **F4 measured the wrong statistic** on the consistency rule (extra days, not breach
  probability) and so under-reported the hazard at its own recommended risk — see §3.

What survives: **shares on Trade The Pool, FLEX not MAX** — and the reason FLEX beats MAX is
sharper than g71 made it. It is not mainly the 60-day clock. It is that **MAX's 30% consistency
rule breaks 28.4%–79.9% of the time at the risk level g71 recommended**, and FLEX's 50% rule
does not.

### 6.2 What is TTP's single biggest weakness for a 1-trade-a-day robot?

**The unresolved automation contradiction — Terms & Conditions §11.1 versus the Program Terms'
SignalStack beta.** Every other weakness is a number that can be sized around. This one is a
binary, resolved after the money is made, by a counterparty with an incentive.

It is compounded by three things specific to this robot:

1. The sanctioned channel is a **webhook through a third party (SignalStack)**, not Austin's own
   client — one more link that can fail silently between signal and fill, on a strategy that gets
   exactly one shot per session.
2. Automation support is **self-described as "beta"**, and TTP *"reserves approval for any
   algorithm, integration, or client"* — approval that can be withdrawn.
3. **$97/mo of SignalStack** is a recurring cost that the one-time evaluation fee hides.

*Second-biggest*, and the one to size around: the **consistency rule at high risk-per-trade** —
because the fix is free (drop risk, or take the larger account) and the failure is not.

### 6.3 What is the runner-up, and under what condition is it the better pick?

**Funder Trading** (Chicago; NASDAQ/NYSE stocks and, on the funded lane, **US equity options**;
80/20; the firm covers 100% of live losses; challenge cost reimbursed on funding).

It becomes the better pick under **any one** of these conditions:

1. **Austin wants to keep trading options rather than shares.** This is the condition that
   matters most given new fact #1. Funder Trading is the only firm in this comparison that puts a
   US resident into *funded equity options* with no licensing exam and no five-figure capital
   contribution — precisely the lane g71 closed on the now-false premise that he had no capital.
   The $10k buffer would not be needed for the fees; it would be needed for the runway.
2. **TTP answers the §11.1 question badly**, or refuses to answer it in writing. Funder Trading
   has no published automation ban to contradict — though it has no published *permission*
   either, so this only helps once its own written answer comes back.
3. **He is prepared to run 4+ months.** The 80-round-turn minimum is ~80 sessions at one trade a
   day. If he is spending that time anyway, the 80/20 split (vs 70/30) and the loss coverage are
   better terms than TTP's.

Why it is not the pick today: **the price is not published anywhere**, it is **recurring**, and
third-party reports of ≈$500/mo are **UNVERIFIED**. At that rate an 80-round-turn challenge is
≈$2,000 before funding — 7× TTP's $285, and a fifth of the buffer — against a firm whose own
Terms describe it as an educator rather than a capital provider. **Get the price and the
automation policy in writing before treating it as live.**

*Distant third*, and only if he abandons single stocks: **Hantec Trader** and **City Traders
Imperium** have genuinely good automation policies (CTI verifies EA source code, which is a firm
that has thought about algos). Neither serves the strategy — CTI will not take a US resident, and
neither quotes NVDA.

---

## 7. What to do next, in order

1. **Email TTP support before buying anything** and get two sentences in writing: (a) is
   SignalStack webhook order entry permitted on evaluation **and** funded accounts,
   notwithstanding T&C §11.1; (b) is *"total valid profit"* in the consistency rule measured on
   **gross winning profit** or on **net profit**? Answer (b) moves the breach risk at $250 from
   2.7% to 20.4%.
2. **Buy the $50k FLEX at $285 and run $150/trade, not $250.** $150 is 99.7% pass, median 33
   sessions, and **0.0% consistency breach under both readings**. The extra ~14 sessions are the
   cheapest insurance in this document. If he wants $250 risk, buy the **$100k FLEX ($545)**
   instead — 99.4% pass, 0.0% breach.
3. **Budget SignalStack Premium, $97/mo.** Basic's 50 signals will not cover ~84 orders a month.
4. **Email Funder Trading for the subscription price and their written automation policy.** It is
   the only live options route for a US resident with $10k and no Series 57, and it is currently
   unpriceable.

---

## 8. Findings

**F1 — TTP has two live, contradictory automation policies (high).** Program Terms sanction
SignalStack; T&C §11.1 bans all automated trading software. Unresolved, this is the largest
uncontrolled risk in the recommendation, and only TTP can resolve it, in writing.

**F2 — the consistency rule's bite is a function of risk-per-trade, and g71 measured the wrong
statistic (high).** F4 reported the cost in extra trading days (0–1) and concluded "survivable."
Breach probability at the same recommended $250/trade is 2.7% (gross) / **20.4% (net)** on FLEX
and 28.4% / **79.9%** on MAX. Austin's stated tolerance is 10%. **Drop to $150, or take the $100k
FLEX** — both drive it to 0.0%.

**F3 — "OneUp Trader (equities)" does not exist (info).** OneUp is CME futures only. Its
consistency rule (*3 best days ≥ 80% of the best day*) is also the most hostile found to a
one-trade-a-day trader, so its absence costs nothing.

**F4 — TTP's max loss is not purely static; it locks upward (info, corrects g71).** *"Once equity
reaches 3× the Daily Loss limit … the max drawdown for the account will move to the initial
balance."* Favourable, and the opposite of a futures trailing drawdown, but g71's "static from
the initial balance" is incomplete.

**F5 — TTP's commission costs 6.2% of the book's edge, and it is not risk-adjustable (medium).**
Mean 0.0342R round trip ($0.005/share, $0.75 minimum per execution), invariant to
risk-per-trade. All-in with a penny spread, ≈0.068R ≈ 12% of +0.5481R. That is ~2× what the same
strategy costs in Austin's own commission-free equities account — the standing price of the
leverage, and it should be subtracted before comparing a funded account to self-funding.

**F6 — most of the "stock prop" market is index CFDs with US clients banned (info).** Of the
eleven firms examined, seven cannot serve this strategy for a reason that has nothing to do with
their rules: no US single stocks, or no US residents, or both. The genuine equity-prop field for
a US resident running a robot is **two firms wide**.
