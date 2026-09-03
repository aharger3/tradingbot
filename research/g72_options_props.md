# G7.2 / options_props — how deep are the options routes, actually

Researched 2026-08-29. Every URL fetched 2026-08-29 unless stated.
Script: `research/g72_options_props_sizing.py` (`--selfcheck` first). It reads
`research/bt2y_trades.json` (2,437 traded rows, 2,436 priced) and prices contracts with
`research/t7_real_contracts.py::Contract` — prior-session Parkinson sigma, **no same-day
range**, the un-retracted ex-ante pricer.

Extends `research/g71_propfirm.md` and `research/g71_instrument.md`. **It overturns one
conclusion in each.**

---

## 0. The honest count, up front

Austin asked *"how deep of options there are."* Here is the whole floor, counted:

| # | route | own capital | bot? | verdict |
|---|---|---|---|---|
| 1 | **Self-funded options account (tastytrade)** | $10,000, all of it his | **yes, explicitly** | **live today. The only route that clears every gate.** |
| 2 | T3 Trading Group (BD arcade) | ~$5,000–$7,500 contribution | yes — publishes API access | real, but needs SIE + Series 57 and a live track record he does not have |
| 3 | Maverick Trading (non-BD, bond model) | ~$12,200 y1 stock/options | unstated; discretionary-plan model | **over budget**, and the cheap tier on their site is the FX division |
| 4 | Black Eagle Financial Group | claims **none** | unstated | **publishes no numbers at all.** Cannot be evaluated. |
| 5 | Bright Trading (BD arcade) | deposit, amount undisclosed | unstated | Series 57 required; joint-back-office model, in-office culture |
| 6 | Employee desks — SMB, Chimera, Kershner, Seven Points, Hold Brothers, Trillium, DV, Optiver/IMC | $0 | firm's algos, not his | **these are jobs.** NYC/Chicago office, interview loop, you trade their book |
| 7 | Options-on-futures at a futures challenge firm | $0 | mostly banned | **no firm confirmed from primary source.** See §4. |
| 8 | Portfolio margin | **$100,000 floor** | n/a | 10× out of reach |

**Genuine options routes at ≤$10,000 of his own money that a robot may trade: two.**
One of them (T3) is gated behind a licence and a track record. The other is his own
brokerage account.

**The answer is #1, and the reason is new since `g71_propfirm.md` was written**: FINRA
deleted the pattern-day-trader rule effective **2026-06-04**. §5.

---

## 1. Why the prop-challenge industry has almost no equity options

Not conspiracy, structure. The challenge model needs a linear instrument it can auto-liquidate
against a trailing drawdown. Listed equity options are non-linear, need OPRA data licences,
OCC clearing, and Greek-level risk plumbing. So the two ends of the market split:

- **Challenge firms** (Topstep, Apex, TPT, MFFU, Elite, Tradeify, BluSky, Savius, Trade The
  Pool) sell a simulated futures or share account. Options are absent by design.
- **Broker-dealer arcades** (T3, Bright, Chimera, Seven Points, Hold Brothers) give real
  OCC-cleared options access — and require FINRA registration and a first-loss deposit.

There is essentially nothing in between. This is why the "options prop firm" listicles are
so thin: they recycle T3, Maverick, Black Eagle, and then pad with futures firms.

Confirmations that the challenge lane has no equity options:
- **Topstep** — *"Stocks, options, forex, spot crypto, and CFDs are not available"*
  ([help.topstep.com permitted products](https://help.topstep.com/en/articles/8284224-permitted-products-per-exchange)).
- **Trade The Pool** — *"Trading activity is limited to those instruments which are available
  on the trading platform, generally consisting of stocks, warrants, exchange-traded notes
  (ETNs), exchange-traded funds (ETFs), and other exchange-traded products (ETPs) which are
  tradeable on Nasdaq."* Options absent
  ([tradethepool.com/program-terms/](https://tradethepool.com/program-terms/)).
- **Savius** — site lists ES/MES, GC/MGC, SIL and CME/NYMEX/COMEX/CBOT futures. No options
  anywhere on the page ([savius.com](https://savius.com/)), despite third-party listicles
  claiming "options on futures and spreads" — **that claim is UNVERIFIED and contradicted by
  the firm's own site.**
- **Tradeify** — futures only; no stocks, forex, options (UNVERIFIED, secondary source
  [proptradingvibes Tradeify CME guide](https://proptradingvibes.com/blog/tradeify-cme-contracts-guide)).

---

## 2. The broker-dealer arcades — real options, real deposits

### T3 Trading Group — the best of this category, and the only one that publishes an API

| item | what T3 says | source |
|---|---|---|
| options | *"Equity options trading is available for both Hedging Strategies and Speculation. We Allow Multiple Legs and Spread Trading (with Compliance and Risk Approval)."* | [t3trading.com/trading/](https://t3trading.com/trading/) |
| **bot** | *"T3 offers API Access to multiple platforms through Instinet and co-location in various data centers (Carteret, Great River etc)"*; options routed by *"smart order routing through Dash Technologies"* | same |
| licence | *"SIE Exam and Series 57 Top Off"* — sponsored | [t3trading.com/proprietary-trader/](https://t3trading.com/proprietary-trader/) |
| capital | *"Traders are required to make a capital contribution to open an account. But every applicant is different."* No figure published. | same |
| split | *"competitive profit splits"* — no figure published | [t3trading.com/trading/](https://t3trading.com/trading/) |
| status | *"T3 Trading Group, LLC is a registered broker-dealer and member of FINRA and SIPC."* | same |

**Third-party figures, all UNVERIFIED against T3's own site:** capital contribution "often
around $5,000", "minimum $7,500 risk capital contribution"; commissions $0.001–$0.005/share;
splits 50/50 to 90/10; desk/data/software ~$200–$500/mo
([daytradereview.com T3 review](https://daytradereview.com/t3-trading-group-review/),
[Elite Trader thread](https://www.elitetrader.com/et/threads/review-of-t3.292453/)).
Also UNVERIFIED: *"T3 requires a track record and is not taking beginners"*
([bullishbears.com](https://bullishbears.com/t3-trading-review/)).

**Verdict:** the only options venue in this whole report that (a) is a real regulated
broker-dealer, (b) sells options access, and (c) advertises API/co-located automation. Cost
is inside the $10k buffer. The two blockers are the licence (§3) and the track record — the
OMEN book is a backtest, not a P&L statement.

### Maverick Trading — over budget, and the cheap tier is the wrong division

Their live capital-sharing table ([mavericktrading.com/capital-sharing](https://www.mavericktrading.com/capital-sharing)):

| tier | starting capital | performance bond | split | membership fee | monthly |
|---|---|---|---|---|---|
| Associate | $4,000 | $1,000 | 60% | $1,000 | $199 / $100 credit |
| Professional | $10,000 | $2,000 | 80% | $4,000 | $199 / $199 credit |
| Partner | $20,000 | $2,000 | 90% | $8,000 | $199 / $199 credit |

**Read the header before quoting this table.** It carries `WWW.MAVERICKCURRENCIES.COM` —
this is the **forex** division's ladder, not stock/options. Third-party sources consistently
price the **Stock/Options Division** at **$7,000 lifetime membership + $5,000 risk capital +
$199/mo** (≈ **$12,200 in year one**), capital $25k–$800k, split 70/75/80% by level
([tradersunion.com Maverick](https://tradersunion.com/brokers/prop/view/maverick_trading/),
[propfirm201.com](https://propfirm201.com/firms/maverick-trading),
[quantvps.com funded options accounts](https://www.quantvps.com/blog/funded-options-accounts)).
Maverick's own FAQ confirms the model — *"$199 desk fee"*, a *"trading bond"* before live
trading, refund of the membership fee once the trader has earned it back
([FAQ](https://www.mavericktrading.com/frequently-asked-questions-how-maverick-trading-works))
— but publishes no stock/options dollar figures. **The $7,000/$5,000 split is UNVERIFIED
against Maverick's own site.**

**Bot:** no published policy either way. The FAQ says *"we do not have volume requirements
and actively discourage high frequency trading."* One trade a day is not HFT, so this is
probably survivable — but the whole program is built on a human-written trading plan
defended to a human risk manager over a 3–6 month qualification with tests and a demo
period. **UNVERIFIED whether a bot may execute it.** Ask before paying.

**Verdict: out.** $12,200 exceeds the $10,000 buffer, and the qualification clock is
3–6 months before a dollar of firm capital moves.

### Black Eagle Financial Group — the one that looks perfect and publishes nothing

What their own FAQ actually says about capital: *"Not necessarily and most traders and
groups that trade with Black Eagle have not put up any capital."*
([blackeaglefg.com/faqs/](https://blackeaglefg.com/faqs/)). Platform is Sterling Trader Pro;
markets are *"US equities and options"*; payouts *"by the 5th of the following month"*.

Everything else — account sizes, evaluation fee, profit target, drawdown, split, licensing,
automation policy — **is not published anywhere on their site.** The concrete-sounding
figures that circulate ("$150–$500 one-phase evaluations up to $250,000", "5% daily / 10%
max drawdown", "8–10% profit targets", "10 minimum trading days", "no consistency rules",
Greek-based limits) come from **Black Eagle's own SEO blog posts**, not from a terms page
([their Maverick comparison post](https://blackeaglefg.com/black-eagle-and-maverick-trading-options-2026-comparison/),
[their options prop-firm post](https://blackeaglefg.com/prop-firm-for-options-trading-2/)).
Every direct page ends in *"reach out via our contact page."*

Independent verification: **none found.** No Forex Peace Army reviews
([forexpeacearmy.com listing](https://www.forexpeacearmy.com/forex-reviews/23118/black-eagle-financial-group-review) —
"does not have any reviews yet"). Their listed phone is a **+1 514 (Montreal)** number, and
no US broker-dealer registration was located. **Their FINRA/SEC registration status is
UNVERIFIED and should be checked on BrokerCheck before any money or personal data moves.**

**Verdict: cannot be evaluated.** A firm whose entire published risk framework lives in blog
posts written for search engines is not a route, it is a lead-generation funnel. If Austin
wants it on the table, the next step is a phone call demanding a written terms document —
not a wire.

### Bright Trading

Series 57 + SIE required, plus state exams. *"Applicants are required to provide a trader
deposit, to be determined on trader qualifications"* — **no figure published**
([stocktrading.com/stepstojoin/](https://stocktrading.com/stepstojoin/)). Classic
joint-back-office equity arcade. Options are part of the traditional Bright playbook
(dividend/box arbitrage), but their site publishes no options program terms. **UNVERIFIED**
on cost, split, and automation.

### The employee desks — SMB, Chimera, Kershner, Seven Points, Hold Brothers, Trillium, DV, Optiver/IMC

These are **jobs, not routes.** No capital contribution, because there is no arrangement —
you are hired, you sit in their office, you trade their book with their methodology.

- **Chimera Securities** — Union Square NYC office, *"trading the firm's capital within the
  first month"*, daily pre-market and post-market meetings, US equities only, no options
  mentioned ([chimerasecurities.com/new-traders](https://www.chimerasecurities.com/new-traders)).
- **Kershner Trading** — *"capital, trading applications and infrastructure to manual and
  algorithmic traders"*; member FINRA/SIPC ([kershnertrading.com](https://www.kershnertrading.com/)).
  Algorithmic-friendly, but a hiring process, not a subscription.
- **SMB Capital** — the public-facing product is **education**, not funding: the student
  equities program is priced at **$4,995** ([smbtraining.com](https://www.smbtraining.com/overview/smb-student-equities-training-program)).
  Buying the course is not a funded account.
- **Trillium / DV Trading** — salaried junior-trader roles, NYC, ~$40k–$88k base plus P&L
  bonus (UNVERIFIED, [Wall Street Oasis compensation thread](https://www.wallstreetoasis.com/forum/trading/trillium-trading-up-to-date-salarycompensation-info)).
- **Optiver / IMC / Jane Street** — institutional market-makers, quantitative interview
  loops, **not open to outside strategies at any price.**
- **Peak Capital Trading** — Vancouver, Andrew Aziz; the product is a **13-week bootcamp**,
  education-first ([peakcapitaltrading.com](https://www.peakcapitaltrading.com/)).

**Not routes for OMEN.** None of them will let a robot run Austin's own signal on his own
terms; that is the entire point of the arrangement.

### Not prop firms at all, despite appearing on every list

- **CenterPoint Securities** — a retail/professional **broker**, $30,000 minimum deposit
  (UNVERIFIED, [smartasset review](https://smartasset.com/investing/centerpoint-securities)).
  Nobody is funding anybody.
- **Sterling Trading Tech** — an **order-entry software vendor** (Sterling Trader Pro). It
  is what Black Eagle and the arcades run on. Not a counterparty.

---

## 3. The licensing question: Series 57

**When it is required.** FINRA Rule 1220(b)(4): a person must register as a **Securities
Trader** if, in equity/preferred/convertible-debt securities effected otherwise than on an
exchange, that person *"is engaged in proprietary trading, the execution of transactions on
an agency basis, or the direct supervision of such activities"*
([FINRA Rule 1220](https://www.finra.org/rules-guidance/rulebooks/finra-rules/1220)).
The trigger is **being an associated person of a broker-dealer**. It is a registration
obligation of the *firm* for its *people*, not a licence to trade your own money.

**What it costs and takes** ([finra.org Series 57](https://www.finra.org/registration-exams-ce/qualification-exams/series57)):

| item | fact |
|---|---|
| Series 57 fee | **$105** |
| Series 57 exam | **50 questions, 1h45m, pass at 70** |
| SIE co-requisite | **$100** (raised from $80 effective 2026-01-01), self-enrollable, **no sponsorship needed** |
| sponsorship | **Series 57 requires it.** *"Candidates must be associated with and sponsored by a FINRA member firm."* Form U4 through CRD. |
| plus | background check, fingerprints, proof of address, compliance approval (T3's stated process) |

**Total exam cost ~$205.** The barrier is not money — it is that the *firm* must file your
U4 first, so the licence and the arrangement are the same decision. T3 and Bright both
sponsor.

**When it is NOT required — and this is the part that matters:**

1. **Trading your own money in your own brokerage account.** No association, no registration.
   Route #1 needs nothing.
2. **Non-broker-dealer "prop" firms.** Maverick is not a BD; it funds through a bond-and-plan
   arrangement, so no Series 57. Every challenge firm (Topstep, Apex, TTP…) is likewise
   outside the BD perimeter — which is exactly why they can only offer simulated accounts.

**So the licence is not a gate on options per se. It is a gate on *someone else's real
OCC-cleared options account*.** Trade your own and it is moot.

---

## 4. Options on futures — the route that keeps getting claimed and never verified

CME lists options on ES/NQ/CL/GC, including daily (0DTE) ES options. If a futures prop firm
permitted them, that would be a $0-own-capital options route. Status, firm by firm:

| firm | claim | primary-source status |
|---|---|---|
| Topstep | — | **explicitly excluded**: options *"not available"* ([permitted products](https://help.topstep.com/en/articles/8284224-permitted-products-per-exchange)) |
| Apex | secondary sources say ES/NQ/CL options are allowed ([arxum](https://arxum.com/prop-trading-options/)) — and other secondary sources say *"Forex, options, or stocks are typically not available"* ([propfirmplus](https://propfirmplus.com/what-can-i-trade-on-apex-trader-funding/)) | **CONTESTED / UNVERIFIED.** apextraderfunding.com FAQ returns HTTP 403 to automated fetch; not confirmed either way |
| Elite Trader Funding | listicle says "options on futures", $80 entry, 100% of first $12,500 then 90% ([quantvps](https://www.quantvps.com/blog/funded-options-accounts)) | **UNVERIFIED** — their own site lists futures platforms and says nothing about options |
| Savius | listicle says "options on futures and spreads" | **CONTRADICTED** by [savius.com](https://savius.com/) — futures only |
| BluSky | listicle says "dedicated options accounts" | **CONTRADICTED** — self-describes as *"The Funded Futures Prop Firm"* ([blusky.pro](https://blusky.pro/)) |
| Tradeify | — | futures only (UNVERIFIED secondary) |
| FTMO | listicle says "beta options trading (limited)" | **UNVERIFIED**, and FTMO is CFD/FX — not US listed options |

**Nothing here survives contact with a primary source.** Treat "options on futures at a prop
firm" as unproven until a firm's own permitted-products page says so in writing.

**And even if one did**, `g71_propfirm.md` §2 already priced it: index-only signals fire on
**139 of 500 sessions (27.8%)**. ES options would delete 72% of his trading days before the
first fill.

### The bot problem, which sits on top of all of it

Austin's constraint — *"you will be trading it not me"* — kills most of this lane outright:

- **Elite Trader Funding** — *"prohibit the use of automated trading systems or unauthorized
  trade copiers"*, enforced **at payout review**; violations forfeit profits and can mean a
  permanent ban. Semi-automated with active monitoring only (UNVERIFIED secondary,
  [tradingfinder ETF rules](https://tradingfinder.com/props/elite-trader-funding/rules/),
  [TradersPost ETF guide](https://blog.traderspost.io/article/how-to-get-funded-with-elite-trader-funding)).
- **Savius** — *"Automatic third-party trading systems/bots"* prohibited; platform-native
  automation appears permitted ([savius.com](https://savius.com/)).
- **TopstepX** — no EAs, no bots, no trade copiers on funded accounts (UNVERIFIED secondary,
  [TradersPost prop automation rules](https://blog.traderspost.io/article/prop-firm-automation-rules-which-firms-allow-it)).
- **Trade The Pool** (shares, not options — noted because it is `g71_propfirm.md`'s
  recommendation) is the **exception that permits automation**: *"support for automated
  trading, including the specific integration with SignalStack, is currently in a beta
  state"*, *"a rate of no more than 2 requests/min should be targeted"*, and *"the trader is
  responsible for all trades conducted on the account regardless of whether manually or
  automatically created"* ([program terms](https://tradethepool.com/program-terms/)).

**A rule enforced at payout review is the worst possible failure mode**: he passes, trades
for months, requests the money, and it is refused. Any route whose bot policy is
"unstated" is a route where that outcome is live.

---

## 5. The self-funded route — and the fact that changes everything

### 5a. The pattern-day-trader rule is gone

`g71_propfirm.md` was written assuming a $10k retail account is capped at 3 day trades per
5 business days and that a one-trade-a-day strategy therefore needs $25,000 or a prop firm.
**That has not been true since 2026-06-04.**

- SEC approved FINRA's amendment to Rule 4210 on **2026-04-14**
  ([Federal Register, 2026-04-17](https://www.federalregister.gov/documents/2026/04/17/2026-07485/self-regulatory-organizations-financial-industry-regulatory-authority-inc-notice-of-filing-of)).
- FINRA **Regulatory Notice 26-10** eliminates *"day trade count requirements for designating
  a customer a 'pattern day trader'"* and *"the $25,000 pattern day trader minimum equity
  requirement"*, replacing them with **intraday margin standards**. **Effective 2026-06-04**,
  phase-in to 2027-10-20 ([finra.org RN 26-10](https://www.finra.org/rules-guidance/notices/26-10)).
- Counsel's read: the amendment removed the PDT definition, the $25,000 minimum, **and
  "day trading buying power" (the 4× equity intraday calculation)** entirely. Firms must now
  test for an *"intraday margin deficit"* on each margin account *"regardless of whether the
  customer engages in day trading"*, and may do so either by real-time blocking or by a
  single end-of-day calculation ([WilmerHale client alert, 2026-04-23](https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard)).
- The live text of [FINRA Rule 4210](https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210)
  now contains **no pattern-day-trader provisions at all** — checked directly, 2026-08-29.
- **tastytrade implemented on day one**: *"tastytrade was ready for day-1 implementation of
  the new rule on June 4th, 2026."* Accounts must instead hold *"equity proportional to their
  actual intraday market exposure"*, and repeated intraday deficits still trigger a **90-day
  restriction** ([tastytrade PDT article](https://tastytrade.com/learn/markets/industry/pattern-day-trading/)).

**Consequence: a $10,000 account may now day-trade one setup a day, every day, in a margin
account, legally, at his own broker.** The single strongest historical argument for renting
someone else's capital just evaporated. `g71_propfirm.md` does not know this.

### 5b. What a $10,000 account can hold

Long options are **not marginable**: options with nine months or less to expiry require
deposit of **100% of the premium** (Reg T; LEAPS >9 months take 75%)
([Cboe strategy-based margin](https://www.cboe.com/us/options/strategy_based_margin),
[FINRA margin topic page](https://www.finra.org/rules-guidance/key-topics/margin-accounts)).
So on 0DTE the account balance **is** the ceiling — margin status buys him nothing on the
debit, only on the day-trade count. **Portfolio margin is irrelevant**: FINRA Rule 4210(g)
sets a **$100,000** minimum equity ($150,000 with only partial real-time monitoring)
([FINRA Rule 4210 interpretations, valid from 2026-06-04](https://www.finra.org/rules-guidance/guidance/interps-4210-202606)).

He does **not** need a cash account. But it stays as a fallback if a broker's phase-in is
slow: cash accounts were never subject to PDT, and since T+1 settlement (2024-05-28) options
proceeds settle next business day — so one trade a day recycles cleanly, with good-faith
violations as the only trap.

### 5c. What $10,000 actually buys — measured on the book

`python research/g72_options_props_sizing.py`, 2,436 priced rows:

**The debit is the constraint, not the risk.**

```
debit / risk ratio   p10 3.9x   median 8.1x   p90 16.1x   max 56.9x
```

To risk $1 on a 0DTE ATM contract he must lay out about **$8 of cash**. So:

| cash ceiling | max risk/trade, p10 row | median row | p90 row | worst row |
|---|---:|---:|---:|---:|
| $10,000 | $622 | $1,240 | $2,558 | **$176** |
| $5,000 | $311 | $620 | $1,279 | $88 |
| $2,500 | $156 | $310 | $639 | $44 |

**Fraction of the book he can afford at a fixed risk:**

| risk/trade | $10,000 | $7,500 | $5,000 | $2,500 |
|---|---:|---:|---:|---:|
| $150 | 100.0% | 99.9% | 99.8% | 91.2% |
| **$250** | **99.8%** | 99.4% | 95.5% | 65.6% |
| $500 | 95.5% | 87.0% | 65.6% | 19.3% |
| $1,000 | 65.6% | 44.4% | 19.3% | 3.4% |

**The joint constraint — integer contracts, debit capped, one trade a day:**

| account | target risk | rows tradable | cash-capped below target | realised risk (median) |
|---|---|---:|---:|---:|
| $10,000 | **$250** | **2,424 / 2,436 (99.5%)** | **4 (0.2%)** | **$241** |
| $10,000 | $500 | 2,431 (99.8%) | 107 (4.4%) | $490 |
| $10,000 | $1,000 | 2,435 (100.0%) | **814 (33.4%)** | $980 |
| $5,000 | $250 | 2,424 (99.5%) | 98 (4.0%) | $240 |

At **$250/trade in a $10,000 account, 99.5% of the two-year book is affordable and only
0.2% of rows get cut down by the cash ceiling.** At $1,000/trade a third of the book is
silently under-sized — the account stops being able to express its own signal.

**Fee drag is flat in risk, which is the good news for a small account:**

| risk/trade | fees as % of risk (median) | p90 | rows that cannot buy 1 contract |
|---|---:|---:|---:|
| $100 | 5.87% | 17.90% | 69 (2.8%) |
| $250 | 5.78% | 17.65% | 12 (0.5%) |
| $1,000 | 5.73% | 17.64% | 1 (0.0%) |

Contracts scale with risk, so commission is ~**0.058R** whatever he sizes — there is no
small-account penalty. Median 1-contract granularity is **$22 of risk**, fine enough that
$250 is not a lumpy number.

**Ceiling, at the book's own mean R (+0.5501R over the 2,436 priced rows), one trade a day,
~250 sessions:**

| risk/trade | R/yr | gross $/yr, before spread |
|---|---:|---:|
| $100 | +138R | $13,753 |
| **$250** | **+138R** | **$34,382** |
| $500 | +138R | $68,765 |

**Read the "before spread" hard.** `g71_instrument.md` §3 measured 0DTE option friction at
**0.3146R at a $0.05 round-trip spread** and put the death threshold at **$0.075**. On
138R/yr that is roughly **-79R/yr at a nickel**, i.e. **most of the gross**. Nobody in this
repo has read a real NBBO on a real 0DTE contract. **That, not the funding route, is the
open question that decides whether this makes money at all** — and it is the $160
ThetaData purchase `g71_instrument.md` already recommended.

### 5d. Why nothing beats it on his constraints

| gate | self-funded | T3 | Maverick | Black Eagle | futures challenge |
|---|---|---|---|---|---|
| own capital ≤ $10k | **$10,000** | ~$5–7.5k + $205 exams | ~$12,200 | claims $0 | ~$100–$400 |
| trades **equity options** | **yes** | yes | yes | claims yes | **no** |
| **a robot may trade it** | **yes, explicitly** | yes (API, co-lo) | unstated | unstated | mostly **banned** |
| 1 trade/day 09:30–11:00 | **yes** | yes | yes | unstated | yes |
| licence needed | **none** | SIE + Series 57 | none | unstated | none |
| time to first trade | **days** | weeks–months (U4, exams, track record) | **3–6 months** | unknown | days |
| he keeps | **100%** | 50–90% | 70–80% | unknown | 80–100% |
| capital ceiling | his own $10k | scales | to $800k | claims $250k | to $300k |
| counterparty risk | **none** | FINRA/SIPC BD | 29-year-old firm | **unverifiable** | simulated accounts |

**tastytrade explicitly permits automation.** Their Open API Terms of Service: *"A third
party integrator is permitted to buy, sell or otherwise trade on behalf of a customer or
client who has enrolled in the Autotrading services of that third party integrator"*, with
*"sole responsibility ... for errant order instructions sent as a result of software
malfunction"* on the integrator
([tastytrade Open API terms, updated 2023-05-17](https://assets.tastyworks.com/production/documents/USA/open_api_terms_and_conditions.pdf),
[tastytrade.com/api/](https://tastytrade.com/api/)). The repo already speaks this protocol —
`dxlink.py` and `tastytrade_feed.py` authenticate and pull the option chain today.

The trade-off is honest and worth stating: **he keeps 100% of a small number instead of 70%
of a bigger one, and there is no firm absorbing his losses.** At $250/trade the arithmetic
above is ~$34k/yr gross of spread at the book's own mean R — not income replacement on its
own. The self-funded account is the **only route that can start this month with a bot**, and
it is the track record that unlocks T3 later.

---

## 6. Findings

### F1 — `g71_propfirm.md`'s core premise is dead (high)

It ruled out every options route on *"he has a credit line, not capital"* and never
considered the self-funded account, because it assumed PDT. **The PDT rule was eliminated
effective 2026-06-04**, and the $10,000 buffer is real. §5. Its §0 fork ("shares on TTP vs
index futures") is a false dichotomy: there is a third option and it is the best one.

### F2 — a bot ban voids most of the funded lane, and it is enforced at payout (high)

Elite Trader Funding, TopstepX and Savius all restrict or ban automation, and ETF enforces
**at payout review**. The only funded firm found with a written *permission* is **Trade The
Pool** (SignalStack, beta, 2 req/min) — and Trade The Pool **does not offer options**. So on
Austin's stated constraint, the funded-account lane and the options lane do not intersect
anywhere except T3.

### F3 — Black Eagle publishes no terms and cannot be verified (high)

Every number attached to Black Eagle in this report or any listicle comes from Black Eagle's
own blog. Their FAQ, advantages, and home pages carry no account sizes, no fees, no
drawdown, no split, no automation policy. No independent reviews exist. Registration status
unverified. **Do not send money or a U4 to this firm without a written terms document.**

### F4 — the debit, not the risk, is the sizing constraint, and $250/trade is the number (medium)

Median debit/risk is **8.1×**. At $250/trade a $10,000 account can express **99.5%** of the
book with **0.2%** of rows cash-capped; at $1,000/trade **33.4%** of rows are silently
under-sized. Fee drag is flat at ~**0.058R** across risk levels, so there is no penalty for
starting small. `research/g72_options_props_sizing.py`.

### F5 — "options on futures at a prop firm" is unverified everywhere it is claimed (medium)

Four separate listicle claims (Elite, Savius, BluSky, FTMO) were checked against the firms'
own sites; two are contradicted outright and two are unconfirmed. Apex is genuinely
contested. And index-only fires on **27.8%** of sessions (`g71_propfirm.md` §2), so the lane
is narrow even if it exists.

### F6 — the spread, not the route, is the unresolved risk (high, inherited)

The $34,382/yr headline in §5c is **gross of spread**. At a $0.05 round-trip 0DTE spread,
friction is 0.3146R/trade and the edge is mostly gone; the death threshold is $0.075
(`g71_instrument.md` §3). **No real NBBO has ever been read in this repo.** Picking a
funding route does not answer this, and it is the bigger question.

---

## 7. Recommendation

**Trade it in his own tastytrade account. $10,000. $250 risk per trade. 0DTE ATM. Bot on
the Open API.**

Because, in the order that decides it:

1. **It is the only route that satisfies all four of his constraints at once** — ≤$10k of his
   own money, real equity options, a robot may legally trade it, and one trade a day
   09:30–11:00 is nobody's business but his. Every other route fails at least one, and most
   fail the robot.
2. **PDT is gone since 2026-06-04.** The reason this route did not exist in
   `g71_propfirm.md` no longer exists.
3. **$250 is the measured number, not a guess.** 99.5% of the two-year book fits, 0.2% of
   rows get cash-capped, fee drag 0.058R.
4. **No licence, no interview, no 3–6 month qualification, no payout-review bot audit.** He
   can be live this month.
5. **It builds the one asset every arcade wants and he does not have: a live track record.**
   Six months of real statements is what turns T3 from "not taking beginners" into a real
   second step at a larger size.

**Second choice, and only after a track record exists: T3 Trading Group.** Real broker-dealer,
real OCC-cleared equity options, publishes API and co-location access, capital contribution
inside the buffer, and it sponsors SIE + Series 57 for ~$205 of exam fees. Its blockers are
sequencing, not money.

**Do not pay Maverick** ($12,200, over budget, 3–6 months to firm capital, bot policy
unstated). **Do not wire Black Eagle** anything before a written terms document.

**Before scaling past $250/trade, buy the ThetaData month** (`g71_instrument.md` §2, $80).
The spread is the only thing between +138R/yr and zero, and the routing decision does not
touch it.

---

## 8. What did not run / what is still open

- **No firm was contacted.** T3's capital contribution, T3's split, Bright's deposit, and
  Maverick's stock/options figures are all "contact us" on the primary sites; every figure
  here is marked UNVERIFIED where it came from a third party. **A single phone call to T3
  closes the most important one.**
- **Apex's options-on-futures status is genuinely unresolved** — their FAQ returns HTTP 403
  to an automated fetch and secondary sources disagree.
- **Black Eagle's FINRA/SEC registration was not checked on BrokerCheck** (interactive form,
  not fetchable). Do this before anything else if that route stays open.
- **Broker phase-in of the new intraday margin rule was not surveyed.** tastytrade confirms
  day-one implementation; other brokers have until **2027-10-20** and may still enforce a
  PDT-shaped policy of their own. Confirm at the broker he actually uses.
- **No options approval level was verified** for buying long calls/puts at tastytrade. It is
  the lowest tier everywhere, but it is an application, not an entitlement.
- **Tax treatment was not costed.** Short-term capital gains on every trade; SPX/XSP index
  options would carry §1256 60/40 treatment and cash settlement, which is a real execution
  refinement for the SPY setups and a separate ticket.
- **The recall gate is untouched.** This track edits no detection file;
  `g72_options_props_sizing.py --selfcheck` asserts no engine imports it and that the t7
  pricer carries no same-day `drange`.
