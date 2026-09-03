# G7.2 — The instrument decision: where the robot should trade, and what the $10,000 is for

Written 2026-08-29. Every web source below was read on **2026-08-29**.
Supersedes the recommendation in `research/g71_propfirm.md`, which was made on a premise
that turned out to be wrong (§3) and never asked whether a robot was allowed to trade at all.

Numbers reproduce from `research/g72_buffer_math.py`, `research/g72_consistency_sim.py`,
`research/g72_volume_check.py`, `research/g72_ttp_commission.py`, on
`research/bt2y_trades.json` (500 sessions, 2024-08-21 → 2026-08-21).

---

## 1. The answer, in one sentence

**Buy one Trade The Pool $200,000 FLEX Day evaluation for $1,475, leave the other $8,525 in
the bank, and let the account set the risk — about $450 on a typical setup and $550 on
average, never above $1,000 — but send the email in §7 first, because Trade The Pool's own
contract currently says two opposite things about whether a robot may trade there.**

If that email comes back badly, the fallback is your own tastytrade account with $10,000,
trading **shares**, not options — see §3 and §6.

### The one thing that will surprise you

**You do not pick the risk per trade. The account picks it.**

Risk is `how much stock you buy × how far away the stop is`. Trade The Pool's "$200,000" *is*
the amount of stock you're allowed to buy. On a typical setup in your own book the stop sits
**0.223%** away, so the most you can possibly lose on one trade is `$200,000 × 0.223% = $446`.

That kills the old advice. `g71_propfirm.md` said *"$50,000 account, $250 a trade."* A $50,000
account can only ever risk **$112** on a typical setup. To risk $250 you'd need $112,000 of
buying power. **That recommendation could not have been executed.**

It also means the account size is not a comfort setting — **it is your paycheck**:

| account | one-time fee | max risk on a typical trade | **your take-home per month** |
|---|---:|---:|---:|
| $50,000 FLEX | $285 | $112 | **$1,716** |
| $100,000 FLEX | $545 | $223 | **$3,437** |
| **$200,000 FLEX** | **$1,475** | **$446** | **$6,611** |

Fees from [tradethepool.com/the-program/](https://tradethepool.com/the-program/), read
2026-08-29. Income is after the 70/30 split and after the measured volume haircut (§4).
Income scales with the account; the fee does not. **$5.2k more in fees buys $4.9k more per
month.** That is the whole argument for going straight to the $200k.

---

## 2. Why this one and not the others

Only routes that survive all four of your constraints get a row: real US stocks or options,
under $10,000 of your own money, a robot may trade it, and one trade a day in the
09:30–11:00 window is fine.

| route | costs to start | your money at risk | **robot allowed?** | you keep | first payout |
|---|---:|---:|---|---|---|
| **Trade The Pool $200k FLEX** ← the pick | **$1,475 once** | **$1,475** | **contradicts itself** — see §5 | 70% | ~7 weeks |
| Trade The Pool $50k FLEX | $285 once | $285 | same contradiction | 70% | ~7 weeks |
| **Your own tastytrade account** ← the fallback | $0 | **$10,000, all of it** | **yes, in writing** | 100% | immediate |
| Funder Trading (TrueEdge) | ~$500/mo **UNVERIFIED** | ~$2,000 over 4 months | **not published — silence** | 80% | ~4 months |
| T3 Trading Group | 2 exams (~$205) + capital contribution **UNVERIFIED** | $5,000–$7,500 **UNVERIFIED** | **advertised, but not for options** — see §3 | negotiated, unpublished | no challenge |
| Black Eagle Financial | $150–$500 **UNVERIFIED** | unknown | **not published — silence** | unpublished | unpublished |
| Maverick Trading | ~$12,200 year one **UNVERIFIED** | over your budget | **not published — silence** | 70–80% **UNVERIFIED** | 3–6 months to qualify |

**Why Trade The Pool wins.** It is the only firm that (a) quotes the actual stocks you trade,
(b) takes US residents, (c) has ever written down that a robot may trade there, and (d) puts
none of your money in the market. Nine other stock/CFD firms were checked and eliminated
before their rules even mattered — seven don't offer real US single stocks, and two won't take
a US resident (`research/g72_share_props.md`).

**Why not the $50k.** It has a hard ceiling of **$1,716/month**. Trade The Pool does grow
funded accounts — *"your account will be scaled once you've reached a 10% validated profit
target… buying power increases by 5%"*
([tradethepool.com/the-program/](https://tradethepool.com/the-program/), 2026-08-29) — but at
+5% per milestone a $50k account takes **23 milestones, about 46 months, to reach $150,000 of
buying power.** Nearly four years to reach what $1,475 buys today.

**Why not two or three accounts at once.** The $10k could buy five $285 challenges. It buys
you nothing. One robot trading one signal takes the *same trades on the same days* in every
account — they don't diversify, they all pass together or all fail together. And Trade The
Pool bans it outright: *"Copy trading is defined as entering any position within 30 minutes of
entering the same position in another account, regardless of size or entry price. Copy trading
is allowed only between 2 accounts (not more)"*
([program terms](https://tradethepool.com/program-terms/), 2026-08-29). **Your robot firing
one signal into two accounts is copy trading by their definition.** $200k is the legal ceiling
on this signal at this firm.

### DISQUALIFIED — these firms ban the robot, in their own words

This is the cleanest reason on the board, so here it is with the rule quoted. **The account
that matters is the funded one — the one holding your money.** A firm that allows bots in the
test and bans them once funded is worse than one that bans them outright, because you pay,
pass, trade for months, and get refused at the door.

| firm | the rule, verbatim | where it bites |
|---|---|---|
| **Apex Trader Funding** | *"The use of automation is strictly prohibited on all account types, including any form of AI, Autobots, algorithms, fully automated trading systems, and HFTs… immediate closure of your PA or Live account and forfeiture of all funds and balances."* — [support.apextraderfunding.com Prohibited Activities](https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities) (see note) | Everywhere. This was g71's best futures pick. |
| **Take Profit Trader** | *"No Trading bots/Algos — We do not allow any automated or bot trading of any kind. All trades must be manually executed by the trader."* — [PRO Account Rules](https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules), dated 2025-11-26 | The funded account. The test rules don't repeat the ban — that's the trap. |
| **Topstep** | *"Automated trading via the ProjectX API is prohibited in the LFA."* — [Live Funded Account Parameters](https://help.topstep.com/en/articles/10657969-live-funded-account-parameters) | The real-money tier only. Bots are fine in the Combine and the Express Funded account — [TopstepX API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access) says *"Yes."* |
| **Earn2Trade** | No permission published anywhere. The only clause touching software bans *"software, artificial intelligence, ultra-fast data entry techniques that could potentially… provide an unfair advantage"*, with *"permanently closing the trader's account"* on the menu. — [Prohibited Conduct](https://help.earn2trade.com/en/articles/9286647-prohibited-conduct-in-earn2trade-evaluations-and-in-the-livesim-live-trading-environment) | Silence + permanent closure = don't. |
| **FundedNext** | US clients are locked to the Match-Trader platform *precisely because* MetaTrader isn't available to them, and Match-Trader has no bot support. — [help.fundednext.com](https://help.fundednext.com/en/articles/8020763-is-ea-allowed-in-fundednext) | The robot is structurally impossible, not just banned. |
| **Alpha Futures** | *"Fully automated bots, EAs, and AI trading systems remain prohibited… semi-automated workflows are allowed only when the trader is actively watching."* **UNVERIFIED** — secondary source only | Contradicts "a robot trades this, not me". |

**Note on Apex:** its own site returns an automated-fetch block (HTTP 403), so this quote is
corroborated across five independent sources rather than read off the page directly. Treat it
as strongly established, not primary-confirmed. It doesn't change the answer — Apex is futures
anyway, and futures deletes 72% of your trading days (§6).

**Cleared but irrelevant:** MyFundedFutures genuinely permits bots in writing (*"Traders may
make use of automated trading strategies tailored to their own specific settings"* —
[Fair Play](https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices)),
and so does Tradeify. Both are futures-only, so both lose 72% of your days regardless.

---

## 3. How deep the options routes actually are

**Honest count: six doors. One is verified open. The other five are shut, unwritten, or need a
licence.**

| # | route | real US options? | robot allowed? | fits in $10,000? | verdict |
|---|---|---|---|---|---|
| 1 | **Your own brokerage account** | yes, incl. 0DTE | **yes, in writing** | yes | **OPEN** |
| 2 | T3 Trading Group | yes | **advertised firm-wide, not for options** | probably (**UNVERIFIED**) | needs a phone call + 2 exams |
| 3 | Black Eagle Financial | claimed | **nothing published** | claims no capital needed | can't be evaluated |
| 4 | Funder Trading | on the funded lane only | **nothing published** | ~$2,000 over 4 months | needs a phone call |
| 5 | Maverick Trading | yes | **nothing published** | **no — ~$12,200** | over budget |
| 6 | Bright Trading | not published | **nothing published** | deposit undisclosed | needs Series 57 + state exams |

Everything else in the market is futures-only, foreign-currency-only, a salaried job in a New
York office, or bans bots.

### Yes — the earlier research was wrong, and here is exactly how

`research/g71_propfirm.md` closed the entire options lane with one sentence: *"T3 / Maverick /
Black Eagle want $7,500–$12,200 of his own capital plus licensing. He has a credit line, not
capital."* **That premise was false — you have $10,000.** So the door has to be re-opened, and
it was.

It also made two errors that matter more than the money one:

1. **It never asked whether a robot was allowed.** Not once, for any firm. Its own top futures
   pick, Apex, bans bots and forfeits your funds for using one.
2. **It recommended a risk-per-trade the account cannot execute** ($250 on a $50k — §1).

**But re-opening the door did not find a better room.** Each options route fails for its own
reason, and none of them is money any more:

- **T3 Trading Group** is the serious one, and the claim that it permits robots on options
  does **not** hold up. Its site lists four separate products — Equities, **Options**, Futures,
  **Algorithmic Trading** — and the API/co-location language lives entirely under *Algorithmic
  Trading*. The **Options** section says only: *"Equity options trading is available for both
  Hedging Strategies and Speculation. We Allow Multiple Legs and Spread Trading (with
  Compliance and Risk Approval). T3 employs smart order routing through Dash Technologies."*
  ([t3trading.com/trading/](https://t3trading.com/trading/), read 2026-08-29). No API, no bots,
  and "Compliance and Risk Approval" means a human signs off. **T3 advertises algorithmic
  trading as a firm capability; nothing on their site says a robot may trade options there.**
  On top of that: SIE + Series 57 exams (~$205 in fees), a background check, fingerprints, a
  U4 filing, and a capital contribution they refuse to publish — *"every applicant is
  different."* And third-party reports say they want a live track record you don't have yet.
- **Black Eagle Financial** looks perfect on paper — real options, 0DTE, and their FAQ says
  *"most traders and groups that trade with Black Eagle have not put up any capital."* Then it
  publishes **nothing else**. I read their FAQ directly on 2026-08-29: account sizes, fees,
  profit splits, drawdown limits and automation rules are **all absent**. Every number
  circulating about them traces back to their own marketing blog. No independent reviews
  exist. **Do not send money or file paperwork without a written terms document.**
- **Maverick Trading** is $12,200 in year one for the stock/options division — over budget, and
  3–6 months of qualification before any capital moves. Watch out: their public pricing page
  shows a tier at about $2,200 that looks affordable. **That table is for their forex
  division**, not stocks and options.

**The buffer changes the money answer and the answer doesn't change.** What blocks the options
lane now is licences, silence, and bot policies — not your bank balance.

### And the thing nobody has measured

Even on your own account, the options number is the shakiest in this whole file. Options are
thin: `research/g71_instrument.md` measured that at a **5-cent** round-trip spread, friction
eats **0.39R of a 0.52R edge**, and at **7.5 cents the edge is exactly zero**. **Nobody in
this repo has ever read a real option bid/ask.** That is why the fallback in §1 says shares,
not options — and why the $80 ThetaData month in `g71_instrument.md` is worth more than the
difference between any two accounts on this page.

---

## 4. What the $10,000 should do

All figures 12 months, 21 trading days a month, bootstrapped over your 496 real trading days
using your actual rule (first signal, keep going until the day is green, stop after three
losses — 1.74 trades a day, +0.5166R each).

| path | cash you spend | **money at risk** | month 1 | steady state | 12-month cash | **chance you lose the $10k** |
|---|---:|---:|---:|---:|---:|---:|
| **$200k FLEX** ← the pick | **$1,475** | **$1,475** | **$0** | **$6,611/mo** | $74,377 | **0.00%** |
| $100k FLEX | $545 | $545 | $0 | $3,437/mo | $37,096 | 0.00% |
| $50k FLEX | $285 | $285 | $0 | $1,716/mo ceiling | $18,419 | 0.00% |
| Own account, shares, 2:1 | $10,000 | **$10,000** | +$1,107 | compounds | equity $33,473 | 0% if the book is right / see below |
| Own account, shares, 4:1 | $10,000 | **$10,000** | +$2,058 | compounds | equity $87,422 | 0% if right / **19.9% at zero edge** |
| Own account, 0DTE options | $10,000 | **$10,000** | +$1,332 or +$219 — **depends entirely on the unmeasured spread** | unknown | equity $11.8k–$40k | same shape, **fatter tail** |
| T3 / Maverick / Black Eagle | $5,000–$12,200 **UNVERIFIED** | **50–100% of the buffer** | — | — | — | your capital is the drawdown |

**Read the "money at risk" column, not the "12-month cash" column.** Those 12-month equity
figures are +774% a year. No strategy does that live. They are the shape of the model, not a
forecast.

### The two families have opposite failure modes, and that is the decision

Ask: *what happens if the backtest is wrong?* Here is the same question run at every level of
wrongness, where "half the edge gone" and "all of it gone" are the interesting rows:

| how wrong the backtest is | **$200k FLEX pays you** | fees spent | **own $10k at 4:1** | chance it drops under $5,000 |
|---|---:|---:|---:|---:|
| not wrong at all | $6,217/mo | $1,548 | $87,938 | 0.0% |
| a third of the edge gone | $4,129/mo | $1,908 | $43,480 | 0.0% |
| **half the edge gone** | **$2,182/mo** | $2,929 | $20,760 | 0.0% |
| **all of it gone — zero edge** | **$440/mo** | **$5,738** | **$7,279** | **19.9%** |
| actually a losing strategy | $115/mo | $8,183 | $3,810 | **72.5%** |

**Read the zero-edge row.** On a strategy that makes literally nothing: the prop route still
hands you $5,282 over the year, burns $5,738 in fees, and **leaves $4,262 of your buffer** —
you never had more than $1,475 exposed at any moment. Your own account is down to $7,279 with
a one-in-five chance of being under $5,000 — and that half is gone in a way you cannot trade
back, because the account is now too small to earn.

**Borrowing is the dial that turns "the backtest was optimistic" from a pay cut into a
wipeout.** At 1:1 those same haircuts barely dent the account. At 4:1 they halve it.

### The credit line

It has exactly one correct job: **it is the thing that lets the $10,000 stay liquid.** Do not
draw it into the market.

Borrowing at 0% to trade converts a drawdown into a **debt** — a balance still owed after the
account is gone, on a clock, owed whether or not the strategy ever works again. Trading losses
don't amortise. Your own condition, *"as long as i make enough money back in 1 month"*, is the
failure mode and not the safeguard: the honest range on month 1 runs from **+$2,058 to
−$5,000**.

### Two things about the timeline you have to plan around

- **Month 1 pays you $0 on every prop path.** Median 24 trading days to pass, first payout
  around day 34–35, plus 3–5 business days to process. Call it **7 weeks to first cash, and
  1 path in 10 takes 9 weeks.** You must be able to eat for two months on something else.
- **Passing is not the risk.** At the natural sizing the $200k FLEX passes **99.7%** of the
  time, and the "your best day can't be more than half your profit" consistency rule breaches
  **0.0%** of the time (`research/g72_consistency_sim.py`, 20,000 paths). Your stated tolerance
  was a 10% failure rate; this is comfortably inside it. *(That rule is a real trap at
  aggressive sizing — on a $50k at $446 a trade it breaches 21–58% of the time. At the sizing
  the account actually permits, it never fires.)*

---

## 5. The bot question — read this before you pay

**Trade The Pool's contract currently says two opposite things, and both are live today. I
read both pages myself on 2026-08-29.**

Their **Program Terms** permit it:

> *"Support for automated trading, including the specific integration with SignalStack, is
> currently in a beta state. As such, its availability is not guaranteed… a rate of no more
> than 2 requests/min should be targeted… the trader is responsible for all trades conducted
> on the account regardless of whether manually or automatically created."*
> — [tradethepool.com/program-terms/](https://tradethepool.com/program-terms/)

Their **Terms & Conditions**, section 11, forbid it:

> *"The User may not use any custom, algorithmic, or other automated trading software
> (collectively, 'Automated Trading Software') to execute trades."*
> — [tradethepool.com/terms-and-conditions/](https://tradethepool.com/terms-and-conditions/)

They also publish video tutorials on building a bot for their platform, which is why I still
rank them first. But **a firm holding both texts can enforce either one at payout time** —
and payout time is after you have already earned the money. Even the permissive text calls it
*"a courtesy (currently in beta) and not a service guarantee"*, revocable at their discretion.

**This is the single largest uncertainty in this document, and it is not a number — it is a
sentence in a contract.** It is also cheap to close: one email (§7). Note that it is a risk to
your *earnings*, never to your buffer — the worst case is a voided month, not a lost $10,000.

Two more practical notes:

- **There is no direct connection.** Trade The Pool has no API. Orders go through SignalStack,
  a paid third-party webhook bridge (~$97/mo), which the robot does not currently know how to
  talk to. That is real work, and it adds a third-party hop that can fail silently between
  your signal and your fill.
- **Two requests a minute is tight.** An entry plus two scale-out exits inside one minute is
  three requests. Ask about this in the same email.

**By contrast, your own account is unambiguous.** tastytrade's API Terms of Service define the
permitted use as *"your use of the API Connection… to facilitate your entry into Transactions
with us in your personal or other account and such use so you can build out your own value-add
front end platform or **algorithmic trading systems**."*
([assets.tastyworks.com API ToS](https://assets.tastyworks.com/production/documents/USA/open_api_terms_and_conditions.pdf),
last updated 2023-05-17, still the current version, read 2026-08-29). No prop-firm rule
applies because there is no prop firm. **Nobody can void a payout over how the orders were
generated, because there is no payout — it is your money.**

---

## 6. What could make this wrong

**1. Trade The Pool answers the §11 question badly, or refuses to answer in writing.**
This is the most likely of the three, and it flips the answer to your own tastytrade account
at $10,000 in **shares** — not options, until the spread is measured. That path earns
$532/month at 1:1 or $1,107 at 2:1 in month one, cannot be blown up by position sizing (the
buying-power cap does the sizing for you — at 4:1 on a typical stop, the risk is $89, under 1%
of the account), and is now legal for a small account for the first time: FINRA eliminated the
pattern-day-trader designation *"and the $25,000 pattern day trader minimum equity
requirement"*, effective **2026-06-04**, with an 18-month phase-in to 2027-10-20
([FINRA Regulatory Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10)).
*(tastytrade advertises this is live; the exact date they turned it on is **UNVERIFIED**, and
what leverage a $10,000 account gets intraday under the new rules is broker-set and also
**UNVERIFIED** — 1:1 and 2:1 are certain, 4:1 is the optimistic rung. Ask them.)*

**2. The backtest is optimistic about fills.** Every number in this file comes from a book
that never loses more than 1.00R, always fills at the midpoint, and never misses a fill.
The §4 table is the honest hedge against that, and it says the prop route survives being
completely wrong while your own account does not. The specific unmeasured number is the
option bid/ask — six-fold swing in month-one profit, from $1,332 down to $219, on a spread
**nobody in this repo has ever observed.**

**3. The robot cannot actually place an order yet — anywhere.** This is not a market risk,
it's a build risk, and it applies to both routes. The repo can *read* live prices from
tastytrade (`dxlink.py`, `tastytrade_feed.py` both work). It cannot *trade*:
`broker/tastytrade.py` is hard-locked to the sandbox, no sandbox account has been created, and
its own header says it has "never actually called over the network." The Trade The Pool path
needs a SignalStack webhook emitter that doesn't exist either. **Whichever route you pick,
order placement is unwritten code**, and no unrun code should be trusted with $1,475 or
$10,000.

**Smaller print, all honest:** the day-by-day model shuffles your trading days randomly, which
destroys the real clustering — actual drawdowns will bunch worse than modelled. The simulation
script has no fixed random seed, so its dollar figures drift a few percent between runs. And
Trade The Pool is a **simulated** trading environment by their own disclaimer — the payouts are
real, the fills are not Interactive Brokers fills.

---

## 7. What only you can do next — each under two minutes

1. **Email Trade The Pool support. Paste this:** *"Your Program Terms say automated trading via
   SignalStack is supported in beta. Your Terms & Conditions section 11 says 'The User may not
   use any custom, algorithmic, or other automated trading software to execute trades.' Which
   governs a funded FLEX account? And is 3 orders inside one minute — one entry, two scale-out
   exits — within the 2 requests/minute guidance?"* **Nothing else on this page should happen
   until that answer arrives in writing.**

2. **Decide the one thing no data can decide for you:** are you willing to trade this setup in
   **shares** instead of options, for 70% of someone else's account? Every R in the two-year
   book is already a share-move R — the backtest *is* the shares version. It's your live habit
   that is options.

3. **Then buy one $200,000 FLEX Day evaluation, $1,475**, at
   [tradethepool.com/the-program/](https://tradethepool.com/the-program/). One account, not
   two — two is copy trading. If you want to see real fills before committing that much, the
   hedge is $285 for a $50k first and $1,475 for the $200k a month later; it costs $1,760 total
   and delays the money by about a month. **Do not run both at once.**

4. **Say yes or no to the $80 ThetaData month.** It is the only way to find out whether the
   options version of this strategy makes $1,332 a month or $219 — and right now that unknown
   is bigger than every other choice on this page.

5. **Confirm you can eat for two months without this.** Month 1 pays $0 on the recommended
   path. That is not a risk, it is a certainty, and it is the only part of this plan that can
   hurt you without anything going wrong.
