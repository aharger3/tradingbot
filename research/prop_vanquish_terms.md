# Vanquish Trader — options evaluation rules, verified on Vanquish's own pages

Fetched 2026-09-03 by a research agent from vanquishtrader.com and support.vanquishtrader.com.
Prior pass: `research/prop_firms_2026-09.md` (left these items UNVERIFIED). This file settles
nine of ten; 0DTE remains a support question.

| # | item | answer | source (fetched 2026-09-03) |
|---|---|---|---|
| 1 | Allowed underlyings | Both plans: broad single names and ETFs with multi-leg allowed. SPX, XSP, VIX long-only single-leg calls/puts, no spreads, no selling to open. Full symbol list "varies by platform and account type"; SPY/QQQ/IWM not individually confirmed. | vanquishtrader.com/vanquish-advanced-options-plan-full-guide-for-options-traders-rules-targets-and-how-it-works — "SPX, XSP and VIX can only be traded long as single-leg calls/puts, with no spreads and no selling to open" |
| 2 | Same-day expiry (0DTE) | Not stated. Day trading and same-day close expressly permitted. **UNVERIFIED — one support email settles it.** | same page — "You can open and close positions within the same trading day" |
| 3 | Daily loss limit | **None.** | vanquishtrader.com/no-hidden-rules-prop-firm — "There is no daily loss limit. Vanquish doesn't impose this"; support.vanquishtrader.com/en/articles/11585998 |
| 4 | Trailing drawdown | **End-of-day anchored**, never trails down, does not stop at the starting balance. Example given: $50K with $2.5K limit = $47.5K floor; at $53K equity the floor is $50.5K. | vanquishtrader.com/trailing-drawdown — "The high-water mark only updates at the close of each trading day, based on your closing equity" |
| 5 | Minimum days / consistency | Basic: minimum 10 trades, no consistency rule until funded. Advanced: minimum **4 trading days**; **no single day may exceed 30% of total accumulated profit**. | support.vanquishtrader.com/en/articles/11833924 ("minimum of 4 days"); /11835525 ("No single trading day may account for more than 30% of your total accumulated profits"); /11835601 (Basic: 10 trades) |
| 6 | Time of day, news, overnight | 9:30–4:00 ET; all trades closed by **3:59 PM ET**; overnight holding prohibited (violation = suspension/termination). No news blackout found. | advanced-options full guide — "All trades must be closed by 3:59 PM EST and holding positions overnight is not allowed" |
| 7 | Platform / fills | Real market data, **simulated fills**. Spread-abuse rule: fills that exploit simulated bid/mid/ask and would be impossible live are prohibited. | support.vanquishtrader.com/en/articles/11069094 — "account executions are simulated rather than live trades"; help-center spread-abuse clause |
| 8 | Price and reset | Basic: $10K $99/mo, $50K $250, $75K $375, $100K $500, $150K $750; reset ≈ half the monthly fee. Advanced: $10K $199/mo, $50K **$499/mo (reset $249)**, $75K $799, $100K $999, $150K $1,499. No activation fee. | support.vanquishtrader.com/en/articles/11835551 (Basic pricing); /10907997 (Advanced pricing) |
| 9 | Payouts | **100% split**, no tiers; requestable daily once in the Performance Account; $250 minimum; ~48h processing; bank or USDC/USDT. | vanquishtrader.com/what-you-can-expect-when-you-get-funded-by-vanquish; glossary page ($250 minimum, 48h) |
| 10 | Funded account | **Still simulated**, virtual capital, performance-based payouts. No real funds traded, no orders reach a live market. No profit target once funded; drawdown and consistency rules persist. | vanquishtrader.com/what-is-a-funded-trading-account — "All trading activity takes place on demo accounts using virtual capital" |

## What the backtest must assume (Advanced Options, $50K)

- Profit target 10% = $5,000; trailing drawdown 5% = $2,500 floor that rises with each day's close and never falls; no daily loss limit.
- Minimum 4 trading days; no single day over 30% of accumulated profit (at target that caps a day at $1,500; one 2R win at $150 risk is $300, so the one-trade-a-day arm never trips it).
- Flat by 3:59 PM ET, which the 11:00 window already satisfies; no overnight.
- Fee $499/month as a cost line while in evaluation; reset $249 on failure.
- Simulated fills on real data: the honest close-fill convention in `research/MORNING_REPORT.md` is the right model, and the spread-abuse clause means no mid-price fills.
- Open: whether 0DTE is permitted (support question) and the exact single-name list (support question). If index-only turns out to be true for any plan, see the pivot question in the vault's `Projects/AUGUR.md`.
