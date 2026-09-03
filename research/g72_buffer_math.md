# G7.2 / buffer_math — what $10,000 and a 0% APR credit line actually buy

Austin: *"my credit line as long as i make enough money back in 1 month is good enough to
scale and i have 10k of buffer to invest or hold me afloat."*

Scripts, both committed with this file:
`research/g72_buffer_math.py` (the dollar model) and
`research/g72_volume_check.py` (the 5% position-volume test).
Outputs: `research/_g72_buffer_math.json`, `research/_g72_volume_check.json`.
Book: `research/bt2y_trades.json`, generated 2026-08-29T03:14:29, 500 sessions
2024-08-21 → 2026-08-21, 3,294 counted rows over 496 candidate days.
Day policy: **P4** from `research/g71_firsts.md` — first signal, keep trading until the day
is net green, three-loss cap. 861 trades / 496 days = **1.74 trades/day, +0.5166R/trade**.
All web sources retrieved **2026-08-29**.

---

## Headline, four sentences

1. **Risk-per-trade is not a setting he chooses. It is `notional × stop_pct`, and notional is
   capped by the account's buying power.** A Trade The Pool "$50,000" account *is* $50,000 of
   buying power, so on this book's median stop of **0.223%** it can never risk more than
   **$111.50** on one trade. `research/g71_propfirm.md`'s recommendation of "$250/trade on a
   $50k FLEX" needs $112,000 of notional and **cannot be executed on that account.**
2. Income is therefore **linear in buying power**: **$0.0350 of net payout per $1 of BP per
   month**. $5,000/month net needs about **$150,000 of buying power**, and the eval fee is a
   rounding error against that. **The buffer's job is to buy the biggest account he can pass,
   not the cheapest one.**
3. **The PDT rule is gone.** FINRA Regulatory Notice 26-10 eliminated the four-trades-in-five-days
   designation and the $25,000 minimum equity requirement, effective **2026-06-04**; tastytrade
   implemented day one. Every prior analysis that ruled out a $10k self-funded account on PDT
   grounds is out of date. The self-funded paths are now live options.
4. **The two families have opposite ruin shapes and that is the whole decision.** On the prop
   path a strategy that is 100% dead costs **fees** — $5,738 of the buffer over twelve months,
   buffer survives, **0.0% chance of losing it**. On the self-funded 4:1 path a strategy that
   is 100% dead has a **19.9%** chance of taking the account under $5,000, and a **72.5%**
   chance if the strategy is mildly negative.

---

## 0. The bridge from R to dollars

`1R = $1,000` is a *unit of account* in the book, not a position size. What a real account can
actually risk is `notional × stop_pct`, and `stop_pct` is the row's own stop distance:

| percentile | stop_pct | notional needed to risk $1,000 |
|---|---:|---:|
| p10 | 0.1233% | $811,030 |
| p25 | 0.1690% | $591,716 |
| **p50** | **0.2230%** | **$448,430** |
| p75 | 0.3260% | $306,748 |
| p90 | 0.5170% | $193,424 |
| p99 | 1.2181% | $82,092 |

Every dollar figure below is computed **per trade off that row's own stop_pct**, sized to full
buying power with a cap of 0.5% of BP of risk on any one trade — no fixed-$-per-trade fiction.

### Day policies, for reference

| policy | trades | per day | mean R/trade |
|---|---:|---:|---:|
| P1 first signal only | 496 | 1.00 | +0.6115 |
| P2 win = done, 2 losses = done | 705 | 1.42 | +0.5668 |
| P3 until net green, no cap | 972 | 1.96 | +0.4861 |
| **P4 until net green, 3-loss cap** | **861** | **1.74** | **+0.5166** |

P4 is used throughout: it is his stated rule with a survivable cap, and it has the lowest
drawdown of the four (`research/g71_firsts.md` §2: 12.9R vs the control's 27.8R).

---

## 1. What each account size pays, per month

Trade The Pool FLEX day accounts. The headline number **is the buying power** — *"Once you're
funded, your account will be scaled once you've reached a 10% validated profit target based on
your account's buying power. Example: With a $50,000 funded account, reaching $5,000 in
validated profit qualifies you"* ([tradethepool.com/the-program/](https://tradethepool.com/the-program/)).
Commission modelled at their published *"1/2 cent per share, with a minimum cost of $0.75, per
filled order"* ([program terms](https://tradethepool.com/program-terms/)), three orders per
trade because the book scales out.

| BP | eval fee | max risk/trade (median setup) | gross $/mo | **net 70% $/mo** | daily pause | max loss |
|---|---:|---:|---:|---:|---:|---:|
| $5,000 | $59 | $11 | $179 | **$125** | $100 | $200 |
| $25,000 | $120 | $56 | $1,213 | **$849** | $500 | $1,000 |
| $50,000 | $285 | $112 | $2,497 | **$1,748** | $1,000 | $2,000 |
| $100,000 | $545 | $223 | $5,044 | **$3,531** | $2,000 | $4,000 |
| $200,000 | $1,475 | $446 | $10,111 | **$7,077** | $4,000 | $8,000 |

Prices from [tradethepool.com/the-program/](https://tradethepool.com/the-program/), 2026-08-29
(FLEX day: $59 / $120 / $285 / $545 / $1,475 one-time; MAX day is cheaper — $47 / $97 / $230 /
$435 / $1,100 — but halves the daily pause to 1% and the max loss to 3%, and imposes a 30%
best-position consistency rule instead of 50%).

**Note the correction to `g71_propfirm.md`: the $230 it quotes for a "50k FLEX" is the MAX
price. FLEX 50k is $285.**

### The 5% position-volume rule costs real money above $100k

TTP: *"The volume of any opening trades must not exceed 5% of the trading volume in the previous
one-minute candle for that instrument"* ([program terms](https://tradethepool.com/program-terms/)).
Measured against the actual prior-minute volume at each P4 entry
(`research/g72_volume_check.py`, 861 trades, 0 missing bars):

| BP | trades over the 5% cap | net $/mo uncapped | **net $/mo with the cap as a size limit** | haircut |
|---|---:|---:|---:|---:|
| $50,000 | 12 / 861 (1.4%) | $1,748 | **$1,716** | 1.8% |
| $100,000 | 32 / 861 (3.7%) | $3,531 | **$3,437** | 2.7% |
| $200,000 | 92 / 861 (10.7%) | $7,077 | **$6,611** | 6.6% |
| $450,000 | 218 / 861 (25.3%) | — | — | — |

Worst symbols at $200k notional: **MARA 13/13 blocked, ACHR 15/17, UBER 5/16, CRM 6/21,
COIN 16/79**. The cheap, thin names are the ones that break. Income still clears $5,000/month
at $200k after the haircut.

**So: $5,000/month net needs ≈ $150,000 of buying power** ($5,000 ÷ $0.03306 per $1 of BP).

---

## 2. The five paths, in dollars and months

12 months, 21 trading days/month, 8,000 bootstrap paths per cell over the 496 real days.
"P(buffer gone)" = the path spends more than $10,000 on eval fees inside 12 months.

| path | up-front cash | month-1 dollars | months to first payout | 12-month cash to Austin | months to $5k/mo | **P(lose the $10k)** |
|---|---:|---:|---:|---:|---:|---:|
| **A1** TTP $50k FLEX | $285 | **$0** (still in eval) | ~1.7 | $18,419 | never — $1,716/mo ceiling | **0.00%** |
| **A2** TTP $100k FLEX | $545 | $0 | ~1.6 | $37,096 | never — $3,437/mo ceiling | **0.00%** |
| **A3** TTP $200k FLEX | $1,475 | $0 | ~1.6 | $74,377 | **~2** | **0.00%** |
| **B** N challenges in parallel | $285·N | $0 | ~1.7 | ≈ N × A1, capped by rule | see §4 | **0.00%** |
| **C** self-funded $10k shares, cash 1:1 | $10,000 | +$532 | immediate | equity $18,695 (p10 $16,150) | ~14 (compounding) | 0.0% booked / **19.9% if the edge is zero** |
| **C4** self-funded $10k shares, 4:1 | $10,000 | +$2,058 | immediate | equity $87,422 (p10 $51,651) | ~4 (compounding) | 0.0% booked / **19.9% zero-edge, 72.5% if negative** |
| **D** self-funded $10k 0DTE, 2% risk, $0.02 spread | $10,000 | +$1,014 | immediate | equity $29,615 (p10 $16,635) | ~9 | same shape as C4, fatter tail |
| **E** TTP $50k + $3,000 0DTE sleeve | $3,285 | +$300 (sleeve only) | ~1.7 | $25,049 combined | never on the $50k | **0.00%** on the prop side; $3,000 at risk on the sleeve |

Median pass day is **23 trading days** on every account size (the rules are ratio-invariant),
median first payout **day 34–35**. Add 3–5 business days of processing, and TTP's separate
eligibility condition — *"0.5% of your buying power in profit on 3 separate trading days within
any 14-day period"* — which this book clears **27.2% of days**, so 3 qualifying days land inside
a 14-day window **77.8% of the time**. Call first cash in hand **month 2, occasionally month 3**.

---

## 3. Path A — one challenge, the buffer stays in the bank

**This is the path with no ruin risk in it at all, and it is not close.**

| account | median pass day | median first payout day | 12-mo paid (mean) | p10 | total fees | funded busts | P(buffer gone) |
|---|---:|---:|---:|---:|---:|---:|---:|
| TTP 25k FLEX ($120) | 24 | 36 | $8,896 | $6,673 | $128 | ~0 | 0.00% |
| TTP 50k FLEX ($285) | 23 | 35 | $18,419 | $13,920 | $301 | ~0 | 0.00% |
| TTP 100k FLEX ($545) | 23 | 34 | $37,096 | $28,286 | $573 | ~0 | 0.00% |
| **TTP 200k FLEX ($1,475)** | **23** | **34** | **$74,377** | **$57,092** | **$1,550** | ~0 | **0.00%** |

Stress — 5% of losing trades slip past the stop to between −1.25R and −3.0R (the
`CLAUDE.md` floor and then past it, since `g71_propfirm.md` F1 established the book's −1R
losses are a touch-fill artefact):

| account | median pass day | 12-mo paid | fees |
|---|---:|---:|---:|
| TTP 50k FLEX | 24 (was 23) | $17,552 (was $18,419) | $310 |
| TTP 200k FLEX | 24 (was 23) | $69,632 (was $74,377) | $1,637 |

**Slippage costs about 5–6% of the payout and one extra day. It does not threaten the buffer.**

### What happens in the 10% case where the challenge fails

Nothing structural. The fee is gone; buy another. At $285 the buffer funds **35 consecutive
failures** of a 50k FLEX, at $1,475 it funds **six** of a 200k FLEX. The eval has **no time
limit** on FLEX (min 10 positions), so a failure is a restart, not a deadline miss. The
realistic month-1 outcome on Path A is **$0 income and $285–$1,475 spent** — he must be able to
eat for two months on something other than this.

### And Path A is the one that is verified bot-legal

Trade The Pool is the only firm in `g71_propfirm.md`'s table that **documents** automated
trading rather than banning it: *"Support for automated trading, including the specific
integration with SignalStack, is currently in a beta state… a rate of no more than 2
requests/min should be targeted… the trader is responsible for all trades conducted on the
account regardless of whether manually or automatically created"*
([program terms](https://tradethepool.com/program-terms/)). They publish tutorials titled
"Linking TTP and SignalStack" and "Build a Profitable Trading Bot"
([tradethepool.com/trading-video/how-to-link-ttp-and-signalstack/](https://tradethepool.com/trading-video/how-to-link-ttp-and-signalstack/)).
Two caveats that are his to accept: it is **beta and explicitly not guaranteed**, and
**2 requests/min** is tight for an entry plus two scale-out exits inside one minute.

Contrast, for the record: Topstep permits API access but *"All trading activity must originate
from your personal device. The use of VPS, VPNs, and remote servers is prohibited"*
([help.topstep.com API access](https://help.topstep.com/en/articles/11187768-topstepx-api-access)),
and prohibits *"software, AI, ultra-high speed systems, or mass data entry"* that gives an
unfair advantage ([prohibited strategies](https://help.topstep.com/en/articles/10305426-prohibited-trading-strategies-at-topstep)).
Apex's automation stance is **UNVERIFIED from a primary source** — secondary sources report
bots permitted in evaluation but prohibited in funded PA accounts as of July 2026, which if
true is a payout-voiding trap. That is `g72`'s automation track's call, not this one's.

---

## 4. Path B — several challenges in parallel. The compounding does not exist.

The premise in the brief — *"the buffer buys N attempts; pass probability compounds"* — is
**false for this strategy, and the reason is structural, not statistical.**

N accounts run by one robot on one signal take **the same trades on the same days**. Their
outcomes are the same draw. Correlation is 1.

| N | "independent attempts" fiction `1−(1−p)^N` | correlated reality | fee outlay |
|---|---:|---:|---:|
| 1 | 1.000 | 1.000 | $285 |
| 2 | 1.000 | 1.000 | $570 |
| 3 | 1.000 | 1.000 | $855 |
| 5 | 1.000 | 1.000 | $1,425 |

At the booked edge P(pass) is already ~1.00, so there is nothing to compound. At a degraded
edge (§6) the accounts all fail *together* — parallel copies buy **N× the fee bleed and zero
diversification**. Buying N challenges is buying **size**, and it should be priced as size.

**And TTP caps the size anyway.** Two published rules bind:

- *"Purchasing multiple evaluation accounts is permitted. However, the total base buying power
  of all accounts should not exceed $450K of Buying Power (before scaling)."*
- *"Copy trading is defined as entering any position within 30 minutes of entering the same
  position in another account, regardless of size or entry price. Copy trading is allowed only
  between 2 accounts (not more) that are each Mini BP, Super BP, or MAX/FLEX of the following
  sizes: MAX/FLEX day-trading — $5k, $25k, $50k (cannot copy with another $50k; must be paired
  with $25k or $5k)."*

**A robot firing one signal into two accounts *is* copy trading by that definition.** So the
legal maxima for running this one signal at TTP are:

| configuration | BP on the signal | net $/mo |
|---|---:|---:|
| one $200k FLEX | $200,000 | **$6,611** (after the volume cap) |
| a $50k + $25k permitted pair | $75,000 | $2,621 |
| one $200k + a second, *decorrelated* strategy elsewhere | — | not modelled |

The single $200k FLEX wins outright. **The $450K ceiling is unreachable on one signal.**
Going past $200k means a second prop firm with its own rules and its own automation policy.

---

## 5. Paths C and D — self-funded $10,000

### The PDT rule that used to kill this is gone

> *"new intraday margin standards to replace in their entirety the outdated day trading margin
> requirements"* … replacing *"the day trade count requirements for designating a customer as a
> 'pattern day trader' and the $25,000 pattern day trader minimum equity requirement."*
> Effective **June 4, 2026**, with an 18-month phase-in ending October 20, 2027.
> — [FINRA Regulatory Notice 26-10](https://www.finra.org/rules-guidance/notices/26-10)

tastytrade — the account he already has — implemented on day one: *"THE PDT RULE IS GONE …
Traders of all account sizes now have more flexibility to day trade without the $25K minimum or
the 3-in-5-day rule"* ([tastytrade.com/pdt/](https://tastytrade.com/pdt/)).

**What leverage a $10,000 account now gets intraday is broker-set under the new
intraday-margin-deficit standard and is UNVERIFIED.** 1:1 (cash) and 2:1 (Reg T) are certain.
4:1 is shown as the optimistic rung and should be confirmed with tastytrade before it is
planned on.

| path | month-1 $ | 12-mo equity median | p10 | p90 | P(under $5,000) |
|---|---:|---:|---:|---:|---:|
| C shares, 1:1 cash, $0.01 spread | +$532 | $18,695 | $16,150 | $21,597 | 0.0% |
| C shares, 2:1 | +$1,107 | $33,473 | $25,359 | $44,141 | 0.0% |
| C shares, 4:1 | +$2,058 | $87,422 | $51,651 | $145,757 | 0.0% |
| C shares, 4:1, $0.02 spread | +$1,866 | $73,574 | $43,990 | $122,207 | 0.0% |
| D 0DTE, 2% risk, $0.01 spread | +$1,332 | $40,116 | $22,843 | $71,349 | 0.0% |
| D 0DTE, 2% risk, $0.02 spread | +$1,014 | $29,615 | $16,635 | $52,646 | 0.0% |
| **D 0DTE, 2% risk, $0.05 spread** | **+$219** | **$11,767** | $6,366 | $21,556 | 0.0% |
| D 0DTE, 5% risk, $0.02 spread | +$1,145 | $33,516 | $17,706 | $62,997 | 0.0% |

**Do not read those 12-month equity numbers as forecasts.** A median of $87,422 from $10,000 is
+774%/year. No strategy does that live. What the table is actually good for is the *shape*:

1. **A $10k share account is structurally hard to blow up, because the buying-power cap does the
   position sizing for you.** At 4:1 on the median 0.223% stop, full notional is $40,000 and the
   risk is $89 — **0.89% of equity**, below even a 2% intended risk. He cannot over-size it by
   accident. The corollary is that at 1:1 it is also structurally low-income: **$532 in month 1**.
2. **Options friction is the dominant term and it is not small.** From
   `research/g71_instrument.md`: 0DTE ATM friction is **0.1412R** at a $0.01 round-trip spread,
   **0.2041R** at $0.02, **0.3929R** at $0.05, against P4's booked **+0.5166R/trade**. At a
   nickel of spread the strategy retains **$219 of month-1 profit instead of $1,332** — a **six-fold**
   difference driven entirely by a number **nobody in this repo has ever observed** (that is the
   ThetaData purchase `g71_instrument.md` recommends).
3. **Path D carries a tail Path C does not.** `research/t2_options_tape.md` §4 measured the
   −1.25R floor binding on **4.3% of contract rows against 0% of underlying rows**, worst row
   **−7.9R**, and `paper_trader.py:110` says in its own comment the floor is not applied on the
   premium side. A stop that triggers on the *underlying* does not cap the *contract's* loss.
   That 4.3%/−7.9R tail is modelled above; it is an assumption, not an observation.
4. Sizing is affordable either way: 2% of $10,000 = $200 of risk = **$1,613 of 0DTE debit**
   (`g71_instrument.md`: median $8,068 of debit per $1,000 of risk). 5% risk = $4,034 of debit,
   **40% of the account in one 0DTE position** — that is the point where a single bad gap is a
   40% drawdown.

---

## 6. Ruin, stated bluntly

The zeros in §3 and §5 come from a book that **never books worse than −1.000R, fills at the
mid, and never misses a fill**. Those are the conditions under which nothing can go wrong. The
honest ruin question is not "what does the distribution do" — it is **"what happens when the
backtest is wrong."** Subtract a flat haircut `h` from every trade's R. P4 books +0.5166R, so
`h = 0.52` is a completely dead strategy and `h = 0.65` is a losing one.

| h | live mean R | **PROP $200k FLEX** 12-mo paid | fees | P(reach funded) | **SELF $10k 4:1** median equity | p10 | **P(under $5,000)** |
|---|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | +0.5166 | $74,599 | $1,548 | 100.0% | $87,938 | $53,757 | **0.0%** |
| 0.15 | +0.3666 | $49,542 | $1,908 | 100.0% | $43,480 | $25,557 | **0.0%** |
| 0.30 | +0.2166 | $26,186 | $2,929 | 99.7% | $20,760 | $11,909 | **0.0%** |
| 0.45 | +0.0666 | $9,437 | $4,619 | 92.0% | $9,932 | $5,596 | **6.2%** |
| **0.52** | **0.0000** | **$5,282** | **$5,738** | 81.1% | **$7,279** | $4,118 | **19.9%** |
| 0.65 | −0.1334 | $1,377 | $8,183 | 48.5% | $3,810 | $2,076 | **72.5%** |
| 0.80 | −0.2834 | $220 | $10,023 | 16.9% | $1,869 | $996 | **98.4%** |

**Read the h = 0.52 row twice.** At a strategy with *literally zero edge*:

- The prop path still pays out $5,282 over twelve months (churn through the daily-loss clip and
  the payout ratchet), burns $5,738 of fees, and **leaves $4,262 of the buffer**. He never had
  more than $1,475 exposed at any moment.
- The self-funded path is down to a median $7,279, with a **19.9% chance of being under
  $5,000** — half the buffer gone, and gone in a way that is not recoverable by trading, because
  the account is now too small to earn.

**Leverage is the dial that converts "the backtest was optimistic" from an income problem into a
ruin problem.** At 1:1 the same haircuts barely dent the account; at 4:1 they halve it.

### The failure that actually matters and is not in any table

The prop path's real risk is neither drawdown nor fees. It is **a rule violation that voids a
payout after the money has been earned** — automation on a firm that bans it, copy trading
across two accounts a robot is firing in parallel, or a beta integration withdrawn mid-quarter.
Trade The Pool's automation support is *"a courtesy (currently in beta) and not a service
guarantee."* That is a **100% loss of that month's earnings with a 0% loss of the buffer**, and
it is the single largest uncertainty in this whole document.

---

## 7. The credit line

He is right that the credit line makes the *fees* trivially financeable and wrong if he treats
it as capital. Stated plainly, and this track will not model it further:

- **Borrowing at 0% APR to trade converts a drawdown into a debt.** A $10,000 drawdown on
  borrowed money is a $10,000 balance that is still owed after the account is gone, on a clock
  (the 0% window ends), and it is owed whether or not the strategy ever works again. Trading
  losses do not amortise.
- His own condition — *"as long as i make enough money back in 1 month"* — is the failure mode,
  not the safeguard. It is a promise made to the lender on behalf of a strategy that has never
  traded a live share, and the §6 table says the honest confidence interval on month 1 spans
  **+$2,058 to −$5,000**.
- **The credit line has one correct job in this plan: it is the thing that lets the $10,000 stay
  liquid.** Path A costs $285–$1,475. Everything else stays in cash as living expenses while the
  eval runs, because Path A's month-1 income is **$0** and he needs to eat.

---

## 8. What this track recommends

**A3, and it is a change from `g71_propfirm.md`.**

**Buy one Trade The Pool $200,000 FLEX Day evaluation, $1,475. Keep $8,525 liquid. Do not open
a self-funded trading account with the buffer, and do not draw the credit line into the market.**

Reasons in order:

1. **Income is linear in buying power and the fee is not.** $1,475 buys 4× the monthly income of
   $285 for 5.2× the fee, and the fee is 15% of one month's payout either way. The $50k account
   has a hard **$1,716/month ceiling** — it can never replace a $5,000 income no matter how long
   he runs it. The $200k clears $5,000/month **at the first payout**.
2. **The $10,000 never enters the market**, so no path in this document has more than $1,475 at
   risk at any moment, and P(losing the buffer) is **0.00%** in every prop cell including the
   zero-edge stress.
3. **It is the one route verified to permit a robot** from a primary source.
4. **$200k is the legal ceiling on this signal at TTP anyway** (copy-trading rule), so there is
   no configuration to grow into — start at the ceiling.

**If he wants a hedge against being wrong about the strategy**, the correct hedge is Path E's
shape, not Path B's: **$285 for a $50k FLEX to prove the robot survives real fills for one
month, then $1,475 for the $200k.** That costs $1,760 total, delays the $5,000/month by about a
month, and buys a real observation of the number this whole document is most exposed to — live
slippage. **Do not run both accounts simultaneously; that is copy trading.**

**Reconsider only if** the automation track finds TTP's beta support is not usable for a
09:30–11:00 multi-order robot at 2 requests/min. In that case the fallback is not a futures
firm (it deletes 72% of his days, `g71_propfirm.md` F2) — it is **Path C at 1:1 or 2:1**, which
earns $532–$1,107 in month 1 and cannot be blown up by position sizing.

---

## 9. What did not run, and what is unverified

- **No live fill was ever observed.** Every number here inherits `bt2y_trades.json`'s mid-fill,
  touch-fill assumptions. §6 is the substitute for the measurement, not the measurement.
- **Day-R draws are i.i.d. bootstrap.** This destroys the book's month clustering; the real book
  is 25/25 months green *with* serial structure, and 2025-05/2025-09 are red under every day
  policy (`g71_firsts.md` §3). Real drawdowns will cluster worse than modelled.
- **T3 Trading / Maverick / Black Eagle were not re-priced.** T3 publishes **no** capital-contribution
  figure — *"We'll design a capital contribution and commission structure tailored to your needs"*
  ([t3trading.com/proprietary-trader/](https://t3trading.com/proprietary-trader/)); the
  $7,500 and $12,200 figures in `g71_propfirm.md` are third-party and remain **UNVERIFIED**.
  The buffer-math verdict does not need them: those routes put **his own capital in the
  drawdown seat** (*"Trading involves significant risk and can result in the loss of your invested
  capital"*), which is exactly the property Path A is chosen for. A first-loss desk converts a
  0.00% ruin path into a 75%-of-the-buffer-at-risk path.
- **Intraday buying power for a sub-$25k account post-RN 26-10 is UNVERIFIED** and broker-set.
  The 4:1 rung in §5 is the optimistic case.
- **TTP funded-account rules were modelled as identical to the eval rules** (2% pause, 4% max
  loss). The published funded consistency rule differs by tier; not separately modelled.
- **The 0DTE spread is a swept parameter, not an observation** — the same open question
  `g71_instrument.md` recommends closing with ThetaData Options Standard at $80/month. On this
  document's numbers that $160 purchase is worth **more than the difference between the $50k and
  $200k accounts**, because it decides whether Path D's month-1 is $1,332 or $219.
- **Apex's automation policy** could not be verified from a primary source and is left as
  UNVERIFIED rather than asserted either way.
