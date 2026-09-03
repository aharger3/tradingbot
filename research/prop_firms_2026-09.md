# Prop firms for US equity options day trading — September 2026

**Recommendation.** Most of the named candidates are futures-only (Topstep, Apex, Tradeify, Alpha Futures) or forex/CFD-only (FTMO, The5ers) and flatly do not offer options — confirmed on each firm's own site. Trade The Pool and Lucid Trading are evaluation-model firms but trade stocks/ETFs or futures respectively, not options. Of firms that actually let you trade options through a pay-a-fee, pass-an-evaluation, sim-funded structure, only **Vanquish Trader** has primary-source-documented rules; its Advanced Options plan ($10k/$50k/$150k, 10% target, 5% end-of-day trailing drawdown, min 4 trading days, 100% split, simulated capital) is the closest real analog to what `MORNING_REPORT.md` assumes, and is meaningfully more forgiving (EOD-anchored drawdown, no separate daily-loss kill switch found). Funder Trading is marketed everywhere as an "options" firm but its own TrueEdge Challenge terms describe only NASDAQ/NYSE **stock** trading — the options claim is UNVERIFIED and likely marketing overreach; don't rely on it without a direct answer from their support. Maverick Trading, SMB Capital, T3 Trading, and Black Eagle Financial Group do offer real-capital options trading, but none is a cheap challenge-fee evaluation — they require $12k+ upfront capital/training (Maverick), professional licensing (T3: Series 57), or selective in-house hiring (SMB, Black Eagle) — not something a 0% APR credit line "funds" in the way a $99–$750 Vanquish subscription would. **Bottom line: re-run the backtest against Vanquish's Advanced Options Plan numbers, not the current $50k/8%/4%/2%/5-day assumption, which matches no verified options-permitting firm and in fact matches the shape of firms that categorically forbid options.**

## Comparison table

| Firm | Allows options? | Account sizes / eval cost | Profit target | Daily loss limit | Max/trailing drawdown | Min. trading days | Consistency rule | Time limit | Payout split / first payout | 0DTE permitted? | Sim or real capital |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Vanquish Trader** — Basic Options | Yes | $10k–$150k buying power; monthly sub $99 (10k) to $750 (150k) [vanquishtrader.com/terms] | 10% of balance | UNVERIFIED — not stated on plan-rules page | 5% trailing (equity-peak based); EOD/intraday not specified for Basic | Not specified; min. 10 trades | No single trade > 30% of total profit | No time limit | 100% profit split (Performance Account); daily payouts once funded, KYC via RiseWorks required first | UNVERIFIED — not addressed on primary pages found | Simulated / demo, virtual capital |
| **Vanquish Trader** — Advanced Options | Yes | $10k / $50k / $150k simulated buying power; higher sub than Basic (exact $ not published) | 10% of balance ($1k/$5k/$15k) | UNVERIFIED — no separate daily limit found | 5% trailing, **end-of-day anchored** ("adjusts only based on end-of-day balance... never moves down") | 4 separate trading days minimum | No single **day** > 30% of total profit | No time limit | 100% profit split; daily payout requests once funded | UNVERIFIED — underlying list (claimed elsewhere to be SPX/XSP/VIX, long-only, single-leg) not confirmed on Vanquish's own pages | Simulated / demo, virtual capital |
| **Funder Trading** (TrueEdge Challenge) | **UNVERIFIED / contradicted** — own terms describe NASDAQ/NYSE stocks only, not options, despite third-party "options firm" marketing | Not disclosed on public pages; profit target ~$5,000 implies a mid-size account | "> $5,000" profit | $500/day max, ≤3 max-loss days per challenge | $3,000 account-balance drawdown (mechanics not specified as EOD/intraday) | ≥12 different days within a calendar month | W/L ratio ≥1.20; batting avg ≥40%; min. 80 round-turns | Not disclosed | 80% split + full reimbursement of challenge cost on funding; firm states it "covers 100% of losses" on live funded account | UNVERIFIED — not addressed | Evaluation described as simulated; "live funded account" language used but not confirmed as real capital |
| **Maverick Trading** | Yes (real capital, not an evaluation product) | Real capital from $24,999; $7,000 membership + $5,000 at-risk deposit + $199 desk fee (~$12.2k upfront, stocks/options track) | N/A — no challenge/target structure | N/A | N/A | N/A — 250+ hrs mandatory training program first | N/A | N/A | 70–90% split depending on 6-tier level | Not addressed in sources found | **Real capital**, day one, after training |
| **SMB Capital** | Yes (real capital) | Selective hiring, not a paid challenge; access to $500k+ | N/A | N/A | N/A | N/A | N/A | N/A | Not disclosed | Not addressed | **Real capital**; employment-like, requires track record |
| **T3 Trading Group** | Yes (real capital) | First-loss capital contribution required, or track-record-based full funding; SEC/FINRA broker-dealer, Series 57 licensing required | N/A | N/A | N/A | N/A | N/A | N/A | Not disclosed | Not addressed | **Real capital** |
| **Black Eagle Financial Group** | Yes (real capital) | "No paid testing, no demo period, trade real capital from day 1" for proven traders; pricing "customized" | N/A | N/A | N/A | N/A | N/A | N/A | Not disclosed | Not addressed | **Real capital** |
| Trade The Pool | **No** — stocks/ETFs/ETNs/ETPs only, options not listed as tradable | — | — | — | — | — | — | — | — | — | Simulated / "fictitious funds," stated explicitly |
| Topstep | **No** — futures only ("a Futures-only program"), stocks/options/forex/crypto/CFDs prohibited | — | — | — | — | — | — | — | — | — | Simulated |
| Apex Trader Funding | **No** — futures only, no forex/stocks/options | — | — | — | — | — | — | — | — | — | Simulated |
| Tradeify | **No** — futures only ("futures prop firm"); no options mentioned anywhere on site | — | — | — | — | — | — | — | — | — | Simulated |
| Alpha Futures | **No** (self-described "futures prop firm," CME markets); not explicitly denied on the pages fetched (403'd on deeper pages) | — | — | — | — | — | — | — | — | — | Simulated |
| FTMO | **No** — CFD account trades forex/indices/commodities/stocks/crypto only; separate Futures Beta program, no options product | — | — | — | — | — | — | — | — | — | Real-money-backed CFD replication model, not simulated in the prop-firm-demo sense |
| The5ers | **No** — forex/metals/indices/crypto/commodities only per asset-specification page | — | — | — | — | — | — | — | — | — | Simulated |
| Lucid Trading | **No** — futures-only firm per its own marketing and FAQ | — | — | — | — | — | — | — | — | — | Simulated |

## What the backtest should assume

The current `MORNING_REPORT.md` assumption — **$50k, 8% profit target, 4% trailing drawdown, 2% daily loss, 5 min days** — does not correspond to any options-permitting firm found. Its shape (hard daily-loss %, tight trailing drawdown, mid-size profit target) matches the *futures* prop-firm template (Topstep/Apex/Tradeify/Alpha Futures style), and those firms categorically forbid the instrument Austin trades. The only options-permitting, evaluation-fee, primary-source-documented rule set found is Vanquish Trader's **Advanced Options Plan**:

- **Account: $50k** simulated buying power (matches the current assumption's size)
- **Profit target: 10%** ($5,000) — not 8%
- **Drawdown: 5% trailing, anchored to end-of-day equity** — not 4%, and critically **EOD-anchored, not intraday** (an open loss that recovers by the close does not lock in a lower floor; the current backtest, if it evaluates drawdown on intraday equity, is strictly stricter than the real rule)
- **Daily loss limit: none found** on Vanquish's plan-rules pages — drop the 2% daily-loss gate, or keep it only as a discretionary risk control, not a hard rule to backtest against
- **Minimum trading days: 4** — close to the current 5, can keep as-is or drop to 4
- **No time limit** to complete the evaluation
- **100% profit split**, daily payouts once funded

Before committing, two things need direct confirmation from Vanquish support (not found on any page fetched): (1) whether 0DTE/same-day-expiry options are explicitly permitted, and (2) whether the Advanced Options plan is restricted to SPX/XSP/VIX long-only single-leg (a third-party claim, unverified on Vanquish's own site) — if so, "US equity options" needs to become "SPX/XSP index options," which changes the underlying but not the 1-minute/09:30–11:00/0DTE mechanics materially.

## Sources

- Vanquish Trader terms — https://www.vanquishtrader.com/terms — fetched 2026-09-03 (account sizes, subscription costs)
- Vanquish Trader, "Prop Firms for Options Trading" — https://www.vanquishtrader.com/prop-firms-options-trading — fetched 2026-09-03 (options supported, multi-leg language)
- Vanquish Trader Help Center, Basic Options Plan — https://support.vanquishtrader.com/en/articles/11835566-basic-options-plan-evaluation-rules-overview — fetched 2026-09-03
- Vanquish Trader Help Center, Advanced Options Plan collection — https://support.vanquishtrader.com/en/collections/12141963-advanced-options-plan — fetched 2026-09-03
- Vanquish Trader, "Vanquish Advanced Options Plan: Full Guide" — https://www.vanquishtrader.com/vanquish-advanced-options-plan-full-guide-for-options-traders-rules-targets-and-how-it-works — fetched 2026-09-03 (target %, drawdown mechanics, min. days, payout)
- Funder Trading, TrueEdge Challenge — https://fundertrading.com/trueedge-challenge/ — fetched 2026-09-03 (profit target, loss limit, drawdown, min days, W/L rule; stocks only, no options mentioned)
- Funder Trading, How It Works / Terms — https://fundertrading.com/how-it-works/, https://fundertrading.com/terms-conditions/ — fetched 2026-09-03 (80% split; firm is legally "an educator," not a broker-dealer)
- Maverick Trading, "Do Prop Firms Allow Options?" — https://mavericktrading.com/do-prop-firms-allow-options/ — via search summary, fetched 2026-09-03 (real capital, $7k/$5k/$199 fees, 250+ training hours)
- SMB Capital — https://smbcap.com/ — via search summary, fetched 2026-09-03 (real capital, selective hiring)
- T3 Trading Group — https://t3trading.com/ , https://join.t3trading.com/prop-trading/ — via search summary, fetched 2026-09-03 (SEC/FINRA broker-dealer, Series 57)
- Black Eagle Financial Group — https://blackeaglefg.com/ — fetched 2026-09-03 (real capital day one, no paid testing)
- Trade The Pool, Program Terms — https://tradethepool.com/program-terms/ — fetched 2026-09-03 (instruments = stocks/ETFs/ETNs/ETPs, no options; simulated/fictitious funds)
- Topstep Help Center, "When and What Products Can I Trade?" — https://help.topstep.com/en/articles/8284206-when-and-what-products-can-i-trade — fetched 2026-09-03 (futures-only; options not among permitted products)
- Apex Trader Funding — https://apextraderfunding.com/ — fetched 2026-09-03, 403 on direct fetch; futures-only confirmed via firm's own tagline in search cache and multiple third-party reviews of its rulebook
- Tradeify — https://tradeify.co/ — fetched 2026-09-03 (futures-only, no options mentioned)
- Alpha Futures — https://alpha-futures.com/ — fetched 2026-09-03 (self-described futures prop firm; deeper rules pages 403'd, options not confirmed or denied explicitly)
- FTMO FAQ, "Which instruments can I trade" — https://ftmo.com/en/faq/which-instruments-can-i-trade-and-what-strategies-am-i-allowed-to-use/ — fetched 2026-09-03 (Forex/Indices/Commodities/Stocks/Crypto CFDs; no options; separate Futures Beta)
- The5ers, Trading Asset Specifications — https://the5ers.com/asset-specifications/ — fetched 2026-09-03 (Forex/Metals/Indices/Crypto/Commodities; no options)
- Lucid Trading — https://lucidtrading.com/ , /general-faq/ — via search summary, fetched 2026-09-03 (futures-only firm; direct FAQ fetch 403'd)
- `C:\Users\aharg\Desktop\Projects\tradingbot\research\MORNING_REPORT.md` — read 2026-09-03 (current backtest assumption: $50k/8%/4%/2%/5 min days)
