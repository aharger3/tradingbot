# US Stock Prop Firms: Evaluation Programs

**Recommendation**: Trade The Pool is the only firm designed specifically for equities day trading with transparent rules, lowest eval cost ($97), and real Interactive Brokers access. Funder Trading (TrueEdge) is the runner-up for intraday specialists but caps position size at 1,000 shares and their eval cost is not publicly listed. PropShopTrader is viable for swing-to-intraday hybrid traders but requires 6–8 paid benchmarks to reach real prop ($229–$599 total). FTMO supports only CFD stocks, not real US equities. None offer news-trading restrictions typical of forex prop firms.

| Firm | Eval Fee | Account Size | Profit Target | Daily Loss | Max Drawdown | Min Days | Max Position | Payout | Symbols | Intraday | Platform | Real Capital |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Trade The Pool** | $97 | $5k–$200k | 6% | 1–3% | 3–7% | 0 | No cap | 70–80% | 12k+ (all) | Yes | Interactive Brokers | Yes |
| **Funder Trading** | UNVERIFIED | UNVERIFIED | $5k profit | $500/day | $3k | 12 trading days/mo | 1,000 shares | 80% + cost | NYSE/NASDAQ only | Yes* | TradeFundrr | Yes |
| **PropShopTrader** | $229–$599 | $10k–$100k | $1.5–$3k/benchmark | UNVERIFIED | UNVERIFIED | 3 qual. days/benchmark | No cap | $3–$6k signing + 80/20 | US-listed | Yes | Tickblaze | Simulated→Real |

\* All trades must close same market day.

## What a Shares Arm of the Backtest Must Assume

**Position sizing constraint**: R = |entry − stop| × shares. The binding limit for each firm:

- **Trade The Pool** (Interactive Brokers): Typical 4:1 intraday buying power on equities. A $10k account can hold ~$40k notional. Max loss per rule is 1–3% per day ($100–$300 on $10k), binding constraint is typically account balance or buying power before hitting daily loss limit.
  
- **Funder Trading (TrueEdge)**: Hard caps are $500 daily loss + 1,000 shares per symbol. On a $100 stock, 1,000 shares = $100k notional—buying power is the binding constraint, not daily loss. On a $1 stock, 1,000 shares = $1k notional—daily loss ($500) binds first at $0.50R risk per trade with 2 trades allowed.

- **PropShopTrader (Stocks Intraday)**: Daily profit target ($125–$250 on $25k–$50k) is softer than hard drawdown. EOD drawdown rule is the hard constraint. Daily loss limit is not public; assume professional standards (~2–5% for benchmarking).

**Simplified backtest model**: Set daily loss limit at 3% of initial capital, max position size at 1,000 shares or min(account balance / 4, 1,000 shares), whichever binds first. This covers Funder Trading's strictest constraints and resembles a real intraday account.

## Sources

- Trade The Pool: https://tradethepool.com, https://www.quantvps.com/prop-firms/trade-the-pool (fetched 2026-09-03)
- Funder Trading: https://fundertrading.com/trueedge-challenge/ (fetched 2026-09-03)
- PropShopTrader: https://propshoptrader.com, https://proptradingauthority.com/reviews/propshop-trader-review/ (fetched 2026-09-03)
- FTMO: https://ftmo.com/en/challenge/, https://ftmo.com/en/trading-objectives/ (fetched 2026-09-03)
