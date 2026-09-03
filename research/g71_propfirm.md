# G7.1 / propfirm — which prop firm, which account, what risk per trade

Researched 2026-08-29. Scripts: `research/g71_propfirm_sim.py` (the sim),
`research/g71_propfirm_daily*.json` (the daily-R series it eats).
Every number below was produced by that script from `research/bt2y_trades.json`.

---

## 0. The fork Austin has to decide, and it is not close

**No prop firm on the challenge model lets him trade SPY / NVDA / TSLA options.**

| route | instrument | options? |
|---|---|---|
| Futures prop (Topstep, Apex, TPT, MFFU, Earn2Trade, OneUp, Bulenox, Tradeify) | CME index futures ES/NQ/RTY + micros | **no** — Topstep's own permitted-products page: "Stocks, options, forex, spot crypto, and CFDs are not available" ([help.topstep.com permitted products](https://help.topstep.com/en/articles/8284224-permitted-products-per-exchange), retrieved 2026-08-29) |
| Stock prop (Trade The Pool) | real US shares + ETFs via Interactive Brokers | **no** — program terms allow "stocks, warrants, exchange-traded notes (ETNs), exchange-traded funds (ETFs), and other exchange-traded products (ETPs)". Options are absent from the list ([tradethepool.com/program-terms/](https://tradethepool.com/program-terms/), retrieved 2026-08-29) |
| CFD prop (FTMO, Hantec, Sure Leverage, Seacrest) | index/FX CFDs — US500, US100 | **no**, and no US stocks either. Hantec = forex/crypto/bullion only. Sure Leverage = TradeLocker FX lots. Both off-target for a US-equity B&R strategy |
| First-loss desks (T3 Trading, Maverick, Black Eagle) | **real equity options, incl. 0DTE** | **yes** — but T3 wants SIE + Series 57 and a ~$7,500 capital contribution; Maverick wants $7,000 lifetime + $5,000 risk deposit + $199/mo, about **$12,200 up front** ([tradersunion.com Maverick](https://tradersunion.com/brokers/prop/view/maverick_trading/), 2026) |

Austin: *"i dont have money just credit line."* That closes the only
options-capable lane. **So the prop route requires him to trade the OMEN signal
in a different instrument than the one the repo models.** `CLAUDE.md` says "the
instrument is options, not shares"; a prop account makes that false. He picks:

- **A — shares on Trade The Pool.** Same tickers, same 09:30–11:00 window, same
  break-and-retest. Loses the options convexity the repo's +1.4988R 0DTE read
  depends on. Keeps the whole 29-symbol universe.
- **B — index futures on Topstep/TPT/MFFU.** Only SPY/QQQ/IWM setups translate
  (MES/MNQ/M2K). NVDA and TSLA have no futures. **This throws away 72% of his
  trading days** (section 2).

The data says A. See section 3.

---

## 1. The firms, as of 2026-08-29

### Futures (index futures only — no options anywhere on this table)

| firm | cost | sizes | target | daily loss | max DD | intraday or EOD | consistency | split | payout | time limit | 1 trade/day OK? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Topstep** Combine | $49 / $99 / $149 per month | 50K / 100K / 150K | 6% ($3k / $6k / $9k) | $1,000 / $2,000 / $3,000 — soft, locks the day, does **not** fail you | $2,000 / $3,000 / $4,500 trailing | **EOD** trailing; stops trailing at the starting balance | best day at or below 50% of the profit target | 90/10 from $1 for sign-ups after 2026-01-12 | on request, 1–2 days | none | yes |
| **Apex** Eval | one-time since Apex 4.0 (Mar 2026); list $390–$1,490 EOD, $199–$599 intraday, 70–90% promos routine; PA activation $69–$149 | 25K–150K | 6% | none | 50K $2,500, 100K $3,000, 150K $5,000 | **choice** of EOD or intraday since Mar 2026 — take **EOD** | 50% since Mar 2026 (was 30%) | 100% of first $25k then 90/10 | automated, about 2x/mo | none | yes |
| **Take Profit Trader** Test | $102 (50K) | 25K–150K | 6% ($3,000 on 50K) | **removed Jan 2025** | $2,000 / $3,000 / $4,500 | **EOD** trailing | best day at or below 50% of net profit | 80/20 | on request | none; 5 min trading days | yes |
| **MyFundedFutures** Rapid | about $80–$150 | 25K / 50K / 100K / 150K | 6% | **none on any plan** | trails to the highest EOD balance; locks at start + $100 after the first payout | **EOD** | best day / total at or below 50% (the Rapid EOD route keeps 30% + 4 min days) | 90/10 Rapid EOD, 80/20 Pro | Rapid EOD daily, $500 min; Pro 14 days, $1,000 min | none | yes |
| **Earn2Trade** TCP 25K | $150 | 25K | $1,750 | $550 | $1,500 | **EOD** | no day above 30% of net profit | up to 80/20 | monthly | none; 10 min days | yes |
| **OneUp** 100K | $105 | up to 250K | $6,000 | none | $3,500 trailing | trailing | 3 best days must total at least 80% of the best day | 90/10 | on request | none; 10 min days | yes |

### Stocks (real shares + ETFs — no options)

| firm | cost | sizes | target | daily pause | max loss | intraday/EOD | consistency | split | payout | time limit | options? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Trade The Pool** MAX Day | $47–$1,100 by size, Advanced tier | $5k / $25k / $50k / $100k / $200k buying power | **6% of balance** | **1%** of BP; auto-liquidates and locks the day | **3%** of BP, static from the initial balance | intraday equity | **best single position at or below 30% of total valid profit** (eval); 70% funded | 70/30 | $300 min ($150 on $5k), 14 days between, 3–5 business days | **60 calendar days**, min 20 positions | **no** |
| **Trade The Pool** FLEX Day | same | same | 6% | **2%** of BP | **4%** of BP | intraday equity | **50%** best position (eval and funded) | 70/30 | same | **unlimited**, min 10 positions | **no** |
| Sure Leverage / Hantec / Seacrest | — | — | — | — | — | — | — | — | — | — | **no, and no US stocks** — FX/CFD shops |

Sources, all retrieved 2026-08-29:
[tradethepool.com/the-program/](https://tradethepool.com/the-program/) ·
[tradethepool.com/program-terms/](https://tradethepool.com/program-terms/) ·
[help.topstep.com permitted products](https://help.topstep.com/en/articles/8284224-permitted-products-per-exchange) ·
[apextraderfunding.com PA payout parameters](https://apextraderfunding.com/help-center/legacy-payouts/legacy-pa-payout-parameters/) ·
[tradecovex.com Topstep sizes and targets 2026](https://tradecovex.com/guides/topstep-combine-account-sizes-profit-targets-2026) ·
[tradecovex.com Take Profit Trader rules 2026](https://tradecovex.com/guides/take-profit-trader-rules-2026) ·
[tradetanto.com My Funded Futures rules](https://tradetanto.com/learn/my-funded-futures-rules-a-trader-s-guide) ·
[tradingfinder.com Earn2Trade rules](https://tradingfinder.com/props/earn2trade/rules/) ·
[tradingfinder.com OneUp rules](https://tradingfinder.com/props/oneup-trader/rules/) ·
[tradingfinder.com Hantec rules](https://tradingfinder.com/props/hantec-trader/rules/) ·
[t3trading.com proprietary trader](https://t3trading.com/proprietary-trader/).

---

## 2. What the futures route actually costs him: 72% of his days

One trade a day, the first traded signal of the session, over the 2-year book:

| universe | sessions that fire | mean R | win % |
|---|---:|---:|---:|
| all 29 symbols | **496 / 500** | +0.5809R | 54.4% |
| SPY + NVDA + TSLA | 232 / 500 | +0.6474R | 53.0% |
| **SPY + QQQ + IWM (what futures gives him)** | **139 / 500 (27.8%)** | +0.7112R | 60.4% |
| SPY alone | 52 / 500 | +1.4158R | 65.4% |

Index setups are the *best* setups and the *rarest*. On a futures account he gets
a trade roughly every 3.6 sessions. That gap is the whole story in section 3.

---

## 3. Risk per trade for a 90% pass rate

`research/g71_propfirm_sim.py` bootstraps the daily-R series over 10,000 paths
per risk level and sweeps risk $50–$3,000. Pass = balance reaches start + target
at an EOD before touching the drawdown floor, inside the day limit. A daily-loss
limit clips the day's loss and does **not** fail the account — that is how all
six futures firms and TTP's pause actually work.

Pass rate is **not** monotone in risk (too small and the clock runs out, too
large and the drawdown gets you), so the table gives the whole 90%-or-better band.

### Trading his own universe (29 symbols, shares, Trade The Pool)

| account | 90%+ risk band | best risk | peak pass | median trading days |
|---|---|---|---:|---:|
| **TTP $50k FLEX Day** | **$100 – $450** | **$150** | **99.6%** | 33 |
| TTP $100k FLEX Day | $150 – $950 | $350 | 99.7% | 28 |
| TTP $200k FLEX Day | $300 – $1,800 | $600 | 99.7% | 33 |
| TTP $50k MAX Day (60-day clock) | $200 – $3,000 (see F3) | $200 | 93.9% | 23 |
| TTP $100k MAX Day | $350 – $650 | $450 | 94.4% | 21 |

Restricting to SPY/NVDA/TSLA only (232 firing sessions): TTP $50k FLEX band
**$200–$400**, best $250, **95.4%**, median 18 trading days.

### Index futures only (SPY/QQQ/IWM to MES/MNQ/M2K, 27.8% of sessions fire)

| account | 90%+ risk band | best risk | peak pass | median opportunities |
|---|---|---|---:|---:|
| Topstep / TPT / MFFU **50K** | **$350 only** | $350 | 90.3% | 12 |
| Apex **50K** EOD | $350 – $550 | $400 | 92.9% | 11 |
| Topstep / TPT / MFFU **100K** | **none** | $650 | 86.2% | 13 |
| Topstep / TPT / MFFU **150K** | **none** | $1,050 | 86.6% | 12 |
| OneUp 100K | **none** | $650 | 88.9% | 13 |
| Earn2Trade 25K | $200 – $3,000 | $250 | 93.1% | 10 |

**The 100K and 150K futures accounts cannot be passed 90% of the time on
index-only signals.** Their 6% target needs more opportunities than SPY/QQQ/IWM
supplies inside 120 sessions. Only the 50K sizes clear, and Topstep's band is a
single $350 point — no margin for error.

### Stress: what if the -1R stop does not hold

The book never books worse than -1.000R (finding F1). Scale every losing day:

| loss size | Topstep 50K band | TTP 50K FLEX band |
|---|---|---|
| -1.00R (as booked) | $100 – $300 | $100 – $450 |
| -1.25R (`CLAUDE.md`'s own floor) | **$100 – $150** | $100 – $300 |
| -2.00R (a gap through the stop) | **none — 74.1% peak** | **none — 77.7% peak** |

At -1.25R the answer survives but the futures band collapses to almost nothing.
At -2.00R no futures account passes 90% at any risk level. **The 90%-pass answer
is only as good as the -1R disaster stop actually filling at -1R.**

---

## 4. Findings

### F1 — the -1.25R floor is dead code in the 2-year book (info, but it is the sizing input)

All 76,019 rows of `research/bt2y_trades.json`, and all 1,222 losing trades, book
**exactly -1.000R or better**. Zero rows worse than -1.0R. 1,210 of 1,222 losses
have `exit == stop` to the cent.

Cause, and it is deliberate: `backtest_week.py:538` tests the R1/R2 resting
disaster stop **before** the close-triggered stop, and
`backtest_week.py:379 _disaster_hit` fills it **on touch** at exactly
`-DISASTER_R`. So `stop_rule.stop_fill_price()`'s -1.25R floor
(`stop_rule.py:61-86`) is unreachable on any trade whose stop has not moved.

Not a bug — it is ratified R1/R2 — but `CLAUDE.md` still states the invariant as
"floored at -1.25R", which now describes a branch that cannot execute for an
original-stop stop-out. **Consequence for this track:** every drawdown number in
section 3 assumes a touch fill holds. It will not on a gap. Size off the -1.25R
column, not the -1.00R column.

### F2 — the futures route deletes 72% of his trading days (high)

139 of 500 sessions produce an index signal
(`research/g71_propfirm_daily_index.json`). That is what pushes the 100K and 150K
futures accounts below a 90% pass rate at every risk level tested. Austin's Q10 —
"is futures what I will be trading or prop firm indices" — answers itself:
futures is the *narrower* product for this strategy, not the wider one.

### F3 — on Trade The Pool the daily pause, not his stop, is his real max loss (medium)

TTP MAX auto-liquidates and locks the day at 1% of buying power. On a $25k
account that is **$250 a day, full stop**, regardless of what he sizes. Any
risk-per-trade above the daily pause is a number that cannot be realised. That is
why the MAX rows show absurd "$3,000" band tops in the raw sim: the model clips
the loss exactly as the pause does. Do not read those tops as advice.

### F4 — TTP's 30% best-position rule is survivable at 1 trade/day, but only just (medium)

Eval rule: "the User's best position cannot be responsible for more than 30% of
the total valid profit." One trade a day means one position a day, so he needs
**at least four winners** and no single day above 30% of gross. Modelled
(`--consistency 0.30`) it costs **0–1 extra trading days** at the recommended
risk — median 24 vs 24 on the $25k MAX. It turns fatal only if he sizes up to
finish fast. FLEX's 50% rule removes the issue entirely.

### F5 — Trade The Pool is a simulated environment (info)

Their own disclaimer: "All trading activities conducted through the Company Hub
are executed in a simulated environment"
([tradethepool.com](https://tradethepool.com/), 2026-08-29). Payouts are real;
the fills are not IB fills. Same for every futures firm on this list. Nobody on
the affordable end of this market gives him a live brokerage account.

---

## 5. Recommendation

**Trade The Pool, $50,000 FLEX Day account, $250 risk per trade.**

- Instrument: **shares**, not options. The signal ports; the convexity does not.
- Risk: **$250/trade** on a SPY/NVDA/TSLA book (95.4% pass, median 18 trading
  days), or **$150/trade** across all 29 symbols (99.6%, median 33 days). At
  -1.25R slippage the $50k FLEX band is $100–$300, so **$250 still sits inside
  it** — which is why FLEX and not MAX.
- Why FLEX over MAX: no 60-day clock, 2%/4% instead of 1%/3%, and a 50%
  consistency rule instead of 30%. The clock is what kills a one-trade-a-day
  trader, not the drawdown.
- Why not futures: section 2. If he insists on futures it is **Apex 50K EOD at
  $400/trade** (92.9%) — never a 100K or 150K, which cannot reach 90%.
- Why not the options route: T3 / Maverick / Black Eagle want $7,500–$12,200 of
  his own capital plus licensing. He has a credit line, not capital.

**Open question, and only Austin can answer it:** he has never traded this signal
in shares. Every R in the book is already a share-move R
(`bt2y_trades.json` carries share prices, `meta.risk_dollars` 1000), so the
backtest *is* the shares version — it is his live habit that is options. Is he
willing to trade the same setup with far less convexity and no defined-risk
premium, for a 70% split on someone else's $50k?
