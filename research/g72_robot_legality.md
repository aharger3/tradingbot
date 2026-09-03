# G7.2 / robot_legality — may a bot actually trade this account?

Track key: `robot_legality`. Researched **2026-08-29**. Extends `research/g71_propfirm.md`
and `research/g71_instrument.md` — it does not redo them.

Austin: *"you will be trading it not me"* · *"i want trades that can realistically be done by
a robot."* This track applies one filter and it is binary. **If a firm prohibits automated
trading, every other term on that firm's row in every other track is irrelevant.**

Every quote below was read from the firm's own page on **2026-08-29** unless the row says
UNVERIFIED, which means I could only reach third-party write-ups and the firm publishes no
rule text I could retrieve. **Silence is a risk, not a permission** — silent rows are graded
FAIL-by-silence, because a prop firm that has never written the rule down can invent it at
payout time, which is exactly when it costs the most.

---

## 0. The verdict table

| firm | route | robot may trade? | basis |
|---|---|---|---|
| **Topstep** | futures-prop | **PASS** | firm publishes "Yes" in an explicit bot FAQ, and sells the API |
| **MyFundedFutures** | futures-prop | **PASS** | "Traders may make use of automated trading strategies" |
| **T3 Trading Group** | options-prop (first-loss) | **PASS** | markets black-box/algo trading and Instinet API access as a feature |
| **Trade The Pool** | share-prop | **CONDITIONAL** | permitted, but "beta", "a courtesy… not a service guarantee", revocable, 2 req/min, no native API |
| **Tradeify** | futures-prop | **CONDITIONAL** | permitted, but sole-ownership proof + **live video of you enabling the code**, and the bot may not run at another prop firm |
| **Bulenox** | futures-prop | **CONDITIONAL (UNVERIFIED)** | third-party consensus is "allowed, no HFT"; no primary rule page retrievable |
| **OneUp Trader** | futures-prop | **CONDITIONAL (UNVERIFIED)** | third-party: EAs allowed, no sub-10s trades, no martingale; no primary text |
| **Apex Trader Funding** | futures-prop | **FAIL** | "No Automation or Algorithm Usage allowed" |
| **Take Profit Trader** | futures-prop | **FAIL** | "We do not allow any automated or bot trading of any kind" |
| **Earn2Trade** | futures-prop | **FAIL (by silence)** | no affirmative permission anywhere; an anti-"software/AI" clause is the only mention |
| **Maverick Trading** | options-prop (first-loss) | **FAIL (by silence)** | no published rule text on automation at all |
| **Black Eagle Financial** | options-prop | **FAIL (by silence)** | no published rule text on automation at all |
| **tastytrade / IBKR (self-funded)** | broker | **PASS** | it is his own account; tastytrade publishes an Open API with an Orders endpoint |

**Three firms pass cleanly. Two of the three options-capable routes fail on silence, and the
one that passes — T3 — passes emphatically.**

---

## 1. PASS — the rule text, verbatim

### Topstep — the clearest permission in the industry, with one operational catch

[help.topstep.com/en/articles/11187768-topstepx-api-access](https://help.topstep.com/en/articles/11187768-topstepx-api-access),
read 2026-08-29, page marked "Updated this week":

> **Can I build and use my own custom trading bot with the TopstepX / ProjectX API?**
> Yes. Custom automated strategies and bots are allowed via the TopstepX / ProjectX API,
> subject to standard platform rules and our prohibition on high-frequency trading (HFT).
> You're free to develop your own system without additional restrictions beyond those
> standard rules. You remain the owner of your bot and are solely responsible for its
> design, performance, and behavior — including making sure it operates within all
> applicable rules.

> TopstepX™ API Access lets advanced Traders and developers build automated strategies,
> connect third-party tools, and execute trades directly through TopstepX.

Cost, same page: *"API Access is **$29/month**. Topstep Traders get 50% off with code
`topstep` — that's **$14.50/month**, valid every month with no end date."* Billing shows as
"Sim2Funded Solutions". REST + WebSocket, Python/Java/.NET/JS.

**The catch, and it is the single most important operational finding in this track:**

> **VPNs, VPS, and Remote Servers** — All trading activity must originate from your personal
> device. The use of VPS, VPNs, and remote servers is prohibited by Topstep's Terms of Use.
> Running automation on a VPS can result in account suspension or removal from the program.

The same page draws the line explicitly. Allowed on a private server: historical data
storage, research and backtesting, logging and analytics, a read-only dashboard, receiving
copies of your own fills. **Not** allowed on a private server: placing/modifying/cancelling
orders, *"any automated trigger that can reach the order endpoints"*, routing or relaying
orders. Their summary: *"The line is order transmission: your server can watch and record,
but it cannot trade."*

And [Prohibited Conduct](https://help.topstep.com/en/articles/10296582-prohibited-conduct)
(read 2026-08-29): *"Do not use a VPN. VPNs, proxy services, TOR, geo-location obfuscation,
and other identity-masking services are not permitted at Topstep. If you see an Error 403
Forbidden message, disable your VPN or proxy and try again."*

→ **OMEN must run on Austin's own Windows box, awake and online 09:30–11:00 ET.** No AWS, no
Hetzner, no "deploy it and forget it". That machine becomes a single point of failure with a
funded account behind it.

Two more Topstep clauses worth reading against OMEN specifically, from
[Prohibited Trading Strategies](https://help.topstep.com/en/articles/10305426-prohibited-trading-strategies-at-topstep)
(page dated **June 10, 2026**):

> Examples of exploiting or manipulating the Topstep simulator include, but are not limited
> to: Running scalping algorithms designed to exploit unrealistic SIM fills · Making
> hundreds of rapid trades to take advantage of preferential queue position in SIM ·
> **Using tight brackets or auto-breakeven to take advantage of favorable SIM fills**

That third clause names a mechanic OMEN actually has (R11, be-on-movement, moves the stop to
breakeven on favourable excursion — commit `31f08549`). The page's own qualifier defuses it:
*"The behaviors above are intentional and systematic — usually hundreds or thousands of
trades per day, with average durations measured in seconds, not minutes."* One trade per
day, held minutes to hours, is not what this rule is hunting. **But it is the clause a risk
desk would cite if it wanted to reject a payout**, so keep the R11 trigger honest (real
favourable excursion, not a 1-tick SIM artefact) and keep the trade log.

> Trading Maximum Position Size into Major News Events — Purposefully trading your full
> Maximum Position Size directly into a scheduled major news event.

Not a news-trading ban. Only a max-size-into-news ban. OMEN sizes to risk, not to max. Clear.

### MyFundedFutures — permitted on evaluation *and* funded

[help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices](https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices),
read 2026-08-29, marked "Updated this week":

> **Section 1: Automated Trading Protocols**
> High-frequency Trading is not allowed on our plans.
> Traders may make use of automated trading strategies tailored to their own specific
> settings so long as these automated tools do not aim to exploit the favorable fills
> offered in the Simulated Environment.
> Traders trading live accounts with automated trading must abide by CME guidelines.

No sole-ownership video. No VPS ban published on this page. No multi-firm restriction
published on this page. This is the **least encumbered** written permission of the futures
set.

The adjacent traps on the same page:

> ● **Tier 1 Economic Data Trading**: Engaging in trades during tier 1 economic data releases
> is restricted.
> ● Slippage and Bracket Usage: Exploiting the absence of slippage and utilizing tight
> brackets to gain from favorable fills are not permitted.
> ● **Collaborative Trading**: Collaborating with others to execute identical or opposite
> strategies across unconnected accounts is prohibited.
> **Section 5: Hedging** — MyFunded Futures prohibits hedging of any kind.

"Tier 1 economic data" is the one that bites: **10:00 ET releases (ISM, JOLTS, Consumer
Confidence, UMich) land inside the 09:30–11:00 window.** MFFU does not publish the list or
the buffer on this page. If OMEN goes to MFFU it needs an econ-calendar blackout gate around
10:00 on release days, or a written answer from MFFU support on what "restricted" means.
"Collaborative trading" is about acting *with others*; it does not reach Austin running his
own algo on his own second account.

### T3 Trading Group — the only options-capable route where automation is a selling point

[t3trading.com/trading/](https://t3trading.com/trading/), read 2026-08-29:

> T3 offers API Access to multiple platforms through Instinet and co-location in various
> data centers (Carteret, Great River etc).

The same page cites *"decades of Black Box and Automated Trading Experience"* and *"advanced
algorithmic trading capabilities, including API access to multiple platforms and co-location
in major data centers."* T3 Trading Group, LLC is a **registered broker-dealer, member
FINRA/SIPC** ([t3trading.com/proprietary-trader/](https://t3trading.com/proprietary-trader/)).

This is a categorically different animal from a challenge shop. There is no "prohibited
strategies" page banning bots, because T3 is not a simulated-fill environment gaming out
challenge-farmers — it is a broker-dealer, Austin would be a **registered representative**
(SIE + Series 57, which T3 sponsors), and automation is regulated conduct rather than a terms
violation. Two consequences, and they cut in both directions:

- **Upside:** real fills, real options including 0DTE, real market data, an API that is sold
  rather than tolerated, and no VPS ban — co-location is offered.
- **Cost:** a capital contribution (*"Traders are required to make a capital contribution to
  open an account"*, amount not published; `g71_propfirm.md` recorded ~$7,500 from a
  third-party source, **UNVERIFIED** against T3 directly), plus exam sponsorship, plus the
  compliance overhead of being registered. An automated strategy run by a registered rep at
  a BD is subject to **FINRA supervision and the firm's WSPs**, not just a webpage.

**T3 is the row that fact #1 in the brief — the $10,000 buffer — actually re-opens, and it is
the only options route on this table that survives the robot filter.**

### tastytrade / IBKR self-funded — the control row

His own account, his own money, no prop rules of any kind.
[developer.tastytrade.com/api-overview/](https://developer.tastytrade.com/api-overview/) (read
2026-08-29) documents a public REST API with OAuth2, an **Orders** endpoint, Balances and
Positions, Instruments, Option Chain, and streaming market data — the same surface
`tastytrade_feed.py` and `dxlink.py` already touch in this repo.

**A robot is unambiguously legal here.** This row exists so the other rows are measured
against something: every constraint in this document is a cost the prop route imposes and the
self-funded route does not. It buys none of the leverage, and it is the only route where
nobody can void a payout for how the orders were generated.

---

## 2. FAIL — the rule text, verbatim

### Apex Trader Funding — outright ban, on all account types

[apextraderfunding.com/help-center/getting-started/prohibited-activities/](https://apextraderfunding.com/help-center/getting-started/prohibited-activities/),
read 2026-08-29:

> **No Automation or Algorithm Usage allowed:**
> Rewards are intended to recognize human traders actively participating in the learning
> process, not to reward automated systems executing preprogrammed logic. Please see the
> user agreement for more details, and we encourage you to reach out if you have further
> questions.

Note the framing: the ban is written against **Rewards** — i.e. it is a payout-denial rule.
Apex can let a bot pass the evaluation and then refuse the money. Related clauses from the
same page that compound it:

> **Manipulation of the simulated trading environment:** Apex Trader Funding strictly
> prohibits manipulation or exploitation of the simulation environment in any way, including
> High Frequency Trading (HFT) or any other exploitative strategies.
> **Deviating from Professional Standards** … **No Hedging of Any Kind – Directional Trading
> only.**
> **NEWS TRADING:** Trading during news is allowed for your normal trading strategy.

Third-party write-ups claiming Apex allows "semi-automated" TradingView webhooks, NinjaScript
strategies, or DCA management **contradict this page**, which is Apex's own. Where they
conflict, the firm's page wins. `g71_propfirm.md` ranked Apex highly on economics (one-time
fee, intraday-or-EOD choice, 100% of the first $25k). **Delete the row.**

### Take Profit Trader — outright ban, stated as rule #1

[takeprofittraderhelp.zendesk.com PRO Account Rules](https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules),
authored by "Vlada", dated **November 26, 2025**, read 2026-08-29:

> **1. No Trading bots/Algos**
> We do not allow any automated or bot trading of any kind.
> All trades must be manually executed by the trader.

It is the *first* rule on the funded-account page, and the page says *"This will all be in
the PRO contract we send you as well."* The Test (evaluation) rules page lists only six core
rules and does not repeat it — so the naive read is "bot the eval, hand-trade the PRO". That
is the worst possible plan: it means paying for and passing an evaluation for an account the
robot is contractually barred from touching. **Delete the row.**

TPT's news rule, for the record, would not have bitten: FOMC 2:00 PM ET, NFP and CPI 8:30 AM
ET — all outside 09:30–11:00.

### Earn2Trade — no permission exists, and that is the finding

[help.earn2trade.com Prohibited Conduct](https://help.earn2trade.com/en/articles/9286647-prohibited-conduct-in-earn2trade-evaluations-and-in-the-livesim-live-trading-environment),
written by Angel M., **May 6, 2024**, read 2026-08-29. The only clause that touches software:

> Utilizing software, artificial intelligence, or ultra-fast data entry techniques that could
> potentially manipulate the trading environment or provide an unfair advantage;

That is an anti-exploit clause, not a bot ban — read narrowly, a once-a-day break-and-retest
algo neither manipulates nor gains unfair advantage. **But Earn2Trade publishes no
affirmative permission for automated trading anywhere I could find**, and the consequences
listed on that same page include *"Permanently closing the trader's account"*. A rule that
turns on "could potentially… provide an unfair advantage", with no published carve-out for
ordinary automation, is a clause a firm can point at after the fact.

**Graded FAIL-by-silence.** Not because a bot is banned, but because nobody at Earn2Trade has
ever written down that it isn't, and Austin's downside is a closed account with the profits
in it.

### Maverick Trading and Black Eagle Financial — the two silent options routes

Both are named in `g71_propfirm.md` §0 as options-capable first-loss desks, and both are the
routes fact #1 (the $10k buffer) was supposed to re-open. Neither publishes automation rules.

- **Maverick Trading**: no rule text on bots, EAs, algorithms or APIs on any public page.
  Third-party reviews say only that the firm "emphasizes manual, rule-based trading
  methodologies" and that EA support is "not publicly confirmed" — which is a restatement of
  the silence, not evidence. Membership fee reported at $5,000–$10,000
  ([blackeaglefg.com comparison](https://blackeaglefg.com/black-eagle-and-maverick-trading-options-2026-comparison/),
  read 2026-08-29, and note that is a *competitor's* page — **UNVERIFIED**).
- **Black Eagle Financial Group**: their own
  [Equity Options Prop Firm](https://blackeaglefg.com/equity-options-prop-firm/) page (read
  2026-08-29) describes Greek-based risk limits, drawdown caps, evaluation and instant-funding
  paths, and Sterling Trader Pro as the platform — **and says nothing about automation,
  algorithms, bots, or APIs**. Sterling Trader Pro does have an API (STAPI), but whether Black
  Eagle provisions it at a funded-trader tier is **UNVERIFIED**.

**Graded FAIL-by-silence, and the grade is provisional.** Unlike Apex and TPT, these two are
not refuted — they are unanswered. **Each is one email away from becoming a PASS**, and given
that they are the only other options-capable rows in existence, that email is worth sending.
See §5.

---

## 3. CONDITIONAL — permitted, with a string attached that matters

### Trade The Pool — the incumbent recommendation, and the permission is a courtesy

`g71_propfirm.md` §5 recommended TTP $50k FLEX. It survives the robot filter, but read what
it survives on. [tradethepool.com/program-terms/](https://tradethepool.com/program-terms/),
read 2026-08-29, section **Automated Trading**, in full:

> Support for automated trading, including the specific integration with SignalStack, is
> currently in a beta state. As such, its availability is not guaranteed and the specific
> features and parameters may change. Additional conditions may be required for particular
> accounts, instruments, or strategies at the Company's discretion at any time.
>
> As stated in the overall program terms, the trader is responsible for all trades conducted
> on the account regardless of whether manually or automatically created.
>
> It is important to avoid overloading the server. Therefore, a rate of no more than
> **2 requests/min** should be targeted. Besides the Company's right to reserve approval for
> any algorithm, integration, or client, determination of service load is at the Company's
> judgement; the Company may request or require adjustments to make any automation less
> demanding, whether on an individual basis or across the board.
>
> As noted above, TTP may revoke authorization for automated trading in general as well.
> This is a courtesy (currently in beta) and not a service guarantee (as the funded trader is
> performing services for the Company, the Company is the arbiter of which approaches or
> implementations are of benefit to the Company).

Four things follow.

1. **There is no TTP API.** Automation is a **webhook bridge through SignalStack**, a paid
   third party — TradingView/TrendSpider alert → SignalStack → TTP order. Two free months
   are bundled with an account purchase, then basic membership is reported at ~$149/yr
   ([globenewswire launch release, 2025-08-18](https://www.globenewswire.com/news-release/2025/08/18/3135196/0/en/Trade-The-Pool-Launches-No-Code-Trading-Automation-with-SignalStack-Integration.html),
   read 2026-08-29). **OMEN does not emit TradingView alerts** — it would need a webhook
   emitter written against SignalStack, and the signal path gains a third-party hop that can
   fail silently between OMEN and the fill.
2. **2 requests/min is fine for OMEN** (one trade a day, a handful of order messages) and is
   fatal to anything that polls. Not a constraint here.
3. **"A courtesy… and not a service guarantee"** plus *"TTP may revoke authorization for
   automated trading in general"* means the permission can be withdrawn mid-account, at TTP's
   sole discretion, with no notice period stated. Every other rule TTP publishes is a rule;
   this one is a favour.
4. **Beta.** *"its availability is not guaranteed and the specific features and parameters
   may change."*

Two adjacent TTP rules a robot must be built around, both from the same terms page:

> **Copy trading** is defined as entering any position within 30 minutes of entering the same
> position in another account, regardless of size or entry price. Copy trading is allowed
> only between 2 accounts (not more) that are each Mini BP, Super BP, or MAX/FLEX of the
> following sizes: MAX/FLEX day-trading $5k, $25k, $50k (cannot copy with another $50k; must
> be paired with $25k or $5k) … **Any copying of trades must be performed by the User.**
>
> **Wash trading** is defined as entering any position within 30 minutes of entering the
> opposing position in another account, regardless of size or entry price. Wash trading is
> forbidden.
>
> The volume of any opening trades (opening or adding to a position) must not exceed **5% of
> the trading volume in the previous one-minute candle** for that instrument.

"Any copying of trades must be performed by the User" sits in direct tension with the
Automated Trading section that says the machine may place them. It reads as scoping the
*copy-trading* permission to manual replication rather than banning automation generally, but
that is an interpretation, not a quote. **UNVERIFIED — worth a support ticket** if he ever
runs two TTP accounts.

The 5%-of-previous-minute-volume cap is a real engineering constraint on a share bot: at
09:31 on a thin symbol the previous minute's volume can be small, and OMEN would need to size
against it or have the fill invalidated (*"may be invalidated and could result in additional
restrictions or account review"*).

### Tradeify — permitted, but the proof burden is unusual and one clause is a trap

[help.tradeify.co/en/articles/10468318-guidelines-for-traders](https://help.tradeify.co/en/articles/10468318-guidelines-for-traders),
read 2026-08-29, marked "Updated over 2 weeks ago":

> **Bots/Algorithmic Trading**
> At Tradeify, we allow the use of bots and algorithms under certain conditions:
> **Ownership**: You must be able to prove that you are the sole owner of the bot or
> strategy, and that no one else has access to or is using it. This ensures that the
> bot/algorithm is not being shared with other traders or firms. **We scan to ensure there
> are no similar orders on other accounts. We will also require a live video of you enabling
> the code on your own PC.**
> **Exclusive Use**: While you may use the bot on your personal accounts, using it across
> multiple firms is against Tradeify's policy. The bot should be solely for your own use
> within Tradeify.
> **No High-Frequency Trading (HFT) Bots**: Personal bots are allowed as long as they are not
> high-frequency trading (HFT) bots.
> **Compliance and Verification**: Tradeify reserves the right to request information or
> documentation if our risk measures flag your account.

This is the **only firm on the table that answers the brief's "same algo on a personal account
and a funded account" question in writing**, and it answers it favourably: *"you may use the
bot on your personal accounts."* It then bans the thing that would otherwise be the obvious
diversification play: **OMEN may not run at Tradeify and Topstep at the same time.**

Also from the same page:

> **Microscalping** … applies to funded accounts only … To request a payout on a funded
> account, you must meet BOTH: Over 50% of your trades are longer than 10 seconds; Over 50%
> of your profit must come from trades held longer than 10 seconds.
>
> **News Trading, Dollar Cost Averaging, Flipping, and Scaling** — We do not have any rules
> against or guidelines around trading news events, Dollar Cost Averaging (DCA), flipping, or
> scaling.

OMEN holds minutes to hours: the 10-second floor is met trivially. **No news rule at all** —
the only firm here with none, which matters given the 10:00 ET releases inside his window.

### Bulenox and OneUp Trader — UNVERIFIED, do not act on

Both are reported by multiple independent third-party trackers as bot-friendly (Bulenox:
EAs, NinjaScript, Rithmic API bots, trade copiers, HFT only prohibited; OneUp: EAs allowed,
no trades under 10 seconds, no martingale, news flat 1 min either side). **I could not
retrieve a primary rule page for either** — `bulenox.com/faq` and `oneuptrader.com/faq/`
return JavaScript shells with no rule text in the served HTML.

They are not disqualified. They are **not established**, and this track will not launder a
third-party blog into a PASS. If either becomes economically interesting, get the rule in
writing from the firm first.

---

## 4. The adjacent traps, collected

Every one of these was checked against the OMEN profile — one trade/day, 09:30–11:00 ET,
held minutes to hours, stop-on-close floored at −1.25R, breakeven move on favourable
excursion.

| trap | who has it | does it bite OMEN? |
|---|---|---|
| **VPS / remote-server ban** | **Topstep**, explicitly and at the order-transmission layer | **YES — hardest constraint found.** The bot must run on Austin's own PC. No cloud. |
| **VPN ban** | Topstep (403s at the network layer); Apex bans VPN *used to disguise identity* | yes for Topstep — no VPN at all, ever |
| **Bot may not run at multiple prop firms** | **Tradeify** (explicit) | yes — blocks running two funded accounts in parallel |
| **Same bot on a personal account** | Tradeify explicitly **allows** it; everyone else is silent | no, per Tradeify; **unanswered elsewhere** |
| **Sole-ownership proof / live video** | Tradeify | operational friction, not a blocker |
| **Minimum hold time** | Tradeify (>50% of trades and profit >10s), OneUp (10s) | no — OMEN holds minutes+ |
| **Tier-1 econ data restriction** | **MyFundedFutures** ("restricted", list not published) | **YES** — 10:00 ET releases sit inside the window; needs a blackout gate or a written answer |
| **News flat 1 min either side** | OneUp (UNVERIFIED); TPT (FOMC/NFP/CPI — all outside the window) | OneUp yes if it materialises; TPT moot |
| **Max size into news** | Topstep | no — OMEN sizes to risk |
| **Tight brackets / auto-breakeven as SIM exploit** | **Topstep**, **MFFU** | **watch it** — OMEN's R11 breakeven move is literally named. Defused by trade count and hold time, but it is the clause a payout review would reach for |
| **Hedging ban** | Apex, MFFU, Tradeify, Topstep (cross-account, single-user) | no — OMEN is directional, one position |
| **Gambling / martingale / no-stop** | Apex ("Trading Without Stop Losses… strictly prohibited"; "High-Risk Strategies" = small target, huge stop) | no — OMEN always carries a stop and targets multiples of it |
| **Copy/wash trading across accounts** | TTP (30-min same-position = copy, capped at 2 accounts of specified sizes; 30-min opposite = wash, forbidden); MFFU and Topstep ban coordinated trading *with others* | only if he runs two accounts; solo is clear |
| **Order-volume cap** | TTP: opening trade ≤5% of previous 1-min candle volume | **yes** — a share bot must size against it or risk invalidated fills |
| **Payout-time enforcement** | Apex frames the automation ban around *Rewards*; Tradeify's 10s rule blocks *payout requests* without failing the account | the failure mode is not a rejected order, it is a withheld payout |

---

## 5. What this track hands back

**Rows to delete from every other track, on primary-source rule text:**
**Apex Trader Funding**, **Take Profit Trader**. Both publish an unambiguous ban. Apex in
particular was economically attractive in `g71_propfirm.md` (one-time fee, EOD/intraday
choice since Mar 2026, 100% of the first $25k, best futures pass-rate band at 92.9%) — it is
dead regardless.

**Rows to treat as dead until someone gets it in writing:**
**Earn2Trade**, **Maverick Trading**, **Black Eagle Financial**.

**Rows that survive:**

| rank | firm | why it survives | what it costs |
|---|---|---|---|
| 1 | **Topstep** | explicit written "yes", sold API, $14.50/mo | bot must run on his own PC; index futures only, which `g71_propfirm.md` F2 showed deletes 72% of his trading days |
| 2 | **MyFundedFutures** | least-encumbered written permission; no VPS ban published; NinjaTrader/Tradovate/Rithmic/Quantower all automatable | tier-1 econ-data restriction is undefined and overlaps 10:00 ET; same 72%-of-days futures problem |
| 3 | **T3 Trading Group** | **the only options-capable route that passes**; markets algo/black-box trading and Instinet API + co-lo as features; real fills, not SIM | SIE + Series 57, an unpublished capital contribution, FINRA supervision — and this is precisely the row the $10k buffer re-opens |
| 4 | **Trade The Pool** | permitted — but as a revocable beta courtesy, with no native API, via a paid third-party webhook bridge | the incumbent recommendation now rests on a clause TTP can withdraw at will |
| 5 | **Tradeify** | clear written permission, no news rule at all, personal-account use explicitly blessed | live-video verification; cannot also run at Topstep/MFFU |
| — | **tastytrade / IBKR** | his own account, public Orders API, nobody can void anything | no leverage, all of the capital risk |

**The single sentence this track adds to the recommendation:** `g71_propfirm.md` chose Trade
The Pool on economics, and TTP survives the robot filter — but it survives on the **weakest
permission of the five survivors**, a revocable beta courtesy routed through a third party,
while **Topstep and MyFundedFutures publish real, unconditional written permissions** and
**T3 is the only door to options that a robot may legally walk through**.

**Two emails worth sending before the recommendation is finalised**, because each could
change the answer outright:

1. **Black Eagle Financial** — "Do you permit fully automated order entry on a funded options
   account, and do you provision the Sterling Trader Pro API?" A yes makes it the cheapest
   options-capable robot route on the table ($150–$500 evaluation vs T3's capital
   contribution and exams).
2. **MyFundedFutures** — "Which releases count as tier-1 economic data, and what is the
   blackout window?" The answer determines whether OMEN needs an econ-calendar gate before
   09:30–11:00 is tradeable there.

---

## Sources, all read 2026-08-29

Primary (firm's own page):
[Topstep — TopstepX API Access](https://help.topstep.com/en/articles/11187768-topstepx-api-access) ·
[Topstep — Prohibited Trading Strategies (page dated 2026-06-10)](https://help.topstep.com/en/articles/10305426-prohibited-trading-strategies-at-topstep) ·
[Topstep — Prohibited Conduct](https://help.topstep.com/en/articles/10296582-prohibited-conduct) ·
[Apex — Prohibited Activities](https://apextraderfunding.com/help-center/getting-started/prohibited-activities/) ·
[Take Profit Trader — PRO Account Rules (dated 2025-11-26)](https://takeprofittraderhelp.zendesk.com/hc/en-us/articles/15171769361053-PRO-Account-Rules) ·
[Take Profit Trader — Test Rules](https://takeprofittraderhelp.zendesk.com/hc/en-us/categories/15135982702621-Test-Rules) ·
[MyFundedFutures — Fair Play and Prohibited Trading Practices](https://help.myfundedfutures.com/en/articles/8444599-fair-play-and-prohibited-trading-practices) ·
[Trade The Pool — Program Terms](https://tradethepool.com/program-terms/) ·
[Tradeify — Guidelines for Traders](https://help.tradeify.co/en/articles/10468318-guidelines-for-traders) ·
[Earn2Trade — Prohibited Conduct (dated 2024-05-06)](https://help.earn2trade.com/en/articles/9286647-prohibited-conduct-in-earn2trade-evaluations-and-in-the-livesim-live-trading-environment) ·
[T3 Trading — Trading](https://t3trading.com/trading/) ·
[T3 Trading — Proprietary Trader](https://t3trading.com/proprietary-trader/) ·
[Black Eagle — Equity Options Prop Firm](https://blackeaglefg.com/equity-options-prop-firm/) ·
[tastytrade — API Overview](https://developer.tastytrade.com/api-overview/)

Secondary (marked UNVERIFIED where relied on):
[GlobeNewswire — TTP × SignalStack launch, 2025-08-18](https://www.globenewswire.com/news-release/2025/08/18/3135196/0/en/Trade-The-Pool-Launches-No-Code-Trading-Automation-with-SignalStack-Integration.html) ·
[Black Eagle — Black Eagle and Maverick Trading Options 2026 comparison (a competitor's page)](https://blackeaglefg.com/black-eagle-and-maverick-trading-options-2026-comparison/) ·
[Tradeify Funded Trader Agreement](https://tradeify.co/funded-trader-agreement) ·
[proptradingvibes — Bulenox Permitted Strategies](https://proptradingvibes.com/blog/bulenox-permitted-strategies) ·
[tradingfinder — OneUp Trader Rules](https://tradingfinder.com/props/oneup-trader/rules/)
