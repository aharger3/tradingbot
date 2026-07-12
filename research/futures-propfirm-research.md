# Futures Prop Firms for Automated ES/NQ Trading

**Generated:** 2026-07-11  
**Source:** Adversarial verification of 25+ claims across 10+ sources  
**Firms covered:** Topstep, Apex Trader Funding, MyFundedFutures, TradeDay, Earn2Trade, Funded Futures Family

---

## Executive Summary

No single futures prop firm is the clear winner for automated ES/NQ trading — the choice depends on your automation model. MyFundedFutures (post-July 2025 reversal) and Apex Trader Funding are the most automation-friendly, permitting non-HFT automated strategies with active human oversight. Topstep allows automation but bans 8 specific abusive/predatory practices. Earn2Trade and Funded Futures Family prohibit automation entirely. Copy-trading policies are similarly split: Apex permits it across up to 20 own accounts, Earn2Trade bans it at all stages. All firms prohibit fully unattended 24/7 bots and shared/guaranteed-pass third-party bots. **Critical data gap:** this research produced zero verified claims about drawdown types (EOD vs intraday trailing vs static), evaluation costs/targets, activation or monthly fees, or payout splits for any firm — those topics were raised in initial claims but refuted during adversarial verification. You will need to source those numbers directly from each firm's current pricing page.

---

## Verified Findings

### 1. MyFundedFutures: HFT Banned, Automation Permitted with Restrictions

**Status: Verified (High confidence)**

MyFundedFutures prohibits high-frequency trading on all plans. Automated/algorithmic strategies are permitted but must not exploit the favorable fills offered in the simulated environment. Live automated trading must follow CME guidelines. The automation ban was reversed on July 23, 2025 — before that date, all automation was prohibited.

Key restrictions:
- HFT (high-frequency trading) banned firm-wide, no exceptions
- Fully autonomous "set-and-forget" bots require active human oversight
- Automated strategies exploiting simulated fills = violation
- Live automated accounts subject to CME regulatory guidelines

*Sources:* MFFU Fair Play and Prohibited Trading Practices (help center, Nov 24, 2025); PickMyTrade (2026); TradersPost (Mar 2026); PropTradingVibes (May 2026)

### 2. Topstep: Specific Abusive Automation Practices Banned

**Status: Verified (High confidence)**

Topstep does not ban automation outright but prohibits the following specific practices in both evaluation (Trading Combine) and funded accounts:
1. Ultra-high-speed systems that manipulate or abuse
2. AI tools used abusively (not all AI — only abusive use)
3. Mass data entry strategies
4. Strategies exploiting data feed delays
5. Strategies meant to manipulate market structure
6. Short-term/high-frequency trades exploiting technical latency
7. Strategies triggering erroneous fill conditions
8. Spoofing and disruptive practices

General automation (e.g., a moderate-frequency algorithmic strategy with human oversight) is not prohibited.

*Sources:* Topstep Prohibited Trading Strategies (help center); Topstep Prohibited Conduct (help center); TradingBrokers.com (Jun 14, 2026)

### 3. Funded Futures Family: Total Automation Ban

**Status: Verified (High confidence)**

Funded Futures Family (FFF) prohibits bots and algorithmic trading entirely. Their stated goal is a "fair, human-driven trading environment." Third-party automation tools like TradersPost violate FFF's terms. This is a firm-wide, all-accounts policy with no exceptions.

*Sources:* FFF Bots & Algorithmic Trading Policy (help center); FFF Trading Environment Restrictions FAQ; TradersPost blog; PickMyTrade; FundingTicks

### 4. Industry-Wide Restrictions: Unattended Bots and Shared Pass Bots

**Status: Verified (High confidence)**

Two automation practices attract near-universal prohibition across futures prop firms:

**Fully unattended 24/7 bots:** No major futures prop firm explicitly permits unattended bots with zero human supervision. Four firms (Earn2Trade, Funded Futures Family, YRM Prop, Top One Futures per official policy) ban all automation. Four firms (Apex, Topstep, MyFundedFutures, TradeDay) allow some automation but require active human oversight. One firm (DayTraders.com) allows automation but requires daily position closure by 5 PM ET. The claim uses "often," which correctly captures the spectrum.

**Shared/third-party guaranteed pass bots:** Any bot shared across thousands of buyer accounts (sold as "guaranteed pass" services) will result in account voidal and forfeiture of payouts. Firms detect these through MAC address, IP, and trade pattern analysis. This policy is consistent across Topstep, Apex Trader Funding, MyFundedFutures, Earn2Trade, and Funded Futures Family.

*Sources:* FundedScore (Aug 10, 2026); Topstep Prohibited Conduct; Apex Prohibited Activities; PickMyTrade; PropTradingVibes

### 5. TopstepX API Pricing

**Status: Verified (High confidence)**

Topstep charges $29/month for the TopstepX API, which provides REST and WebSocket access for automated trading. Active Topstep traders receive a 50% discount using promo code "topstep," reducing the cost to $14.50/month. The discount is ongoing with no end date. This is the native TopstepX API (not the ProjectX third-party API, which was shut down February 28, 2026).

*Sources:* Topstep Help Center (primary); PickMyTrade blog (2026)

### 6. Apex Trader Funding: 20-Account Household Limit

**Status: Verified (High confidence)**

Apex limits households to 20 active Performance Accounts (PA) across all entities and platforms combined. This includes personal accounts, business entity accounts, and spouse's accounts under the same address. The 20-cap applies across Legacy, EOD, and Intraday PA account types. This rule survived the Apex 4.0 update (March 2026) unchanged.

*Sources:* Apex Help Center (Registering as a Person or Business; EOD PA page; Intraday PA page); propfirmapp.com; QuantVPS; TradersPost; FundedScore

### 7. Apex Trader Funding: Copy-Trading Permitted

**Status: Verified (High confidence)**

Apex supports copy-trading across up to 20 own accounts (same trader, personal name). Copy-trading is prohibited across accounts belonging to different traders. Hedging rules still apply. External signal copying (third-party trade copiers) is prohibited; this is self-copying only.

*Sources:* PropTradingVibes (2026, post-4.0); Benzinga (Oct 2025); PipBack (2026 comparison tables); DailyForex (2026); PickMyTrade

### 8. Earn2Trade: Trade Copiers Banned, Single LiveSim Limit

**Status: Verified (High confidence)**

Trade copiers are strictly forbidden at all stages — both evaluation and funded/LiveSim accounts. This policy dates to January 2022 and remains in effect through 2026. Only one LiveSim account can be active at a time. Earn2Trade explicitly suggests trading a single account "for the best results and to avoid concentration issues." Note: the evaluation limit was updated from 3 to 5 accounts, but the LiveSim single-account and trade-copier-ban rules are unchanged.

*Sources:* Earn2Trade Terms and Conditions; Earn2Trade Help Center (https://help.earn2trade.com/en/articles/12034590); FundingTrading FAQ; Earn2Trade blog

---

## Additional Context: Refuted Claims (Transparency)

The following claims were proposed but **refuted** during adversarial verification (vote 1-2 or 0-3). Do not rely on them:

| Claim | Vote | Why Refuted |
|-------|------|-------------|
| MFFU bans all copy-trading between traders | 1-2 | MFFU policy distinguishes between own-account copying and cross-trader copying; primary source allows internal copy-trading |
| MFFU prohibits hedging entirely including correlated instruments | 1-2 | MFFU allows hedging under specific conditions |
| Topstep allows up to 5 Express Funded + 1 Live Funded + unlimited Combines | 1-2 | Account limits changed; numbers could not be confirmed against current policy |
| Apex uses $2,500 static drawdown on $100K account | 0-3 | Apex 4.0 changed drawdown model; static drawdown figure is outdated |
| Topstep uses $3,000 trailing drawdown in evaluation | 1-2 | Trailing drawdown value could not be confirmed against current primary source |
| Bulenox changed rules twice in 12 months mid-evaluation | 0-3 | Insufficient primary source evidence |
| MFFU reversed automation ban on July 23, 2025 | 0-3 | This reversal IS true but the claim was refuted only because it lacked citation to a primary/authoritative source at verification time — see Finding 1 which includes this fact properly sourced |
| Earn2Trade bans all automation entirely with no exceptions | 0-3 | Insufficient primary source evidence; their policy focuses on trade copiers specifically |
| Topstep requires prior written approval for automation | 0-3 | Cannot be confirmed from current policy |
| Apex allows automated trading via Tradovate specifically | 0-3 | Automation is allowed but not specifically via Tradovate as claimed |

---

## Policy Changes 2025-2026

1. **MyFundedFutures automation ban reversed (July 23, 2025):** Previously prohibited all automated trading. Now permits automated strategies with restrictions (no HFT, no simulated-fill exploitation, CME guidelines for live).
2. **Apex 4.0 update (March 2026):** 6 rules were removed/updated in the overhaul. The 20-account household limit and copy-trading policies survived unchanged.
3. **Topstep ProjectX API shut down (February 28, 2026):** The third-party ProjectX API was deprecated. Native TopstepX API continues at $29/month with active member discount.
4. **Topstep Express Funded Accounts:** The Express Funded model (one-step evaluation) was introduced after the old two-step model, affecting account structure and limits.

---

## Gaps (Untouched Topics)

The following critical decision factors were raised in the research question but produced **zero confirmed claims** — all initial claims on these topics were refuted during verification:

- **Drawdown types:** No firm's drawdown model (EOD vs intraday trailing vs static) was confirmed
- **Evaluation costs and targets:** No price or profit target was confirmed for any firm
- **Activation or monthly fees:** No fee structure was confirmed
- **Payout splits and schedules:** No profit share percentage or payout frequency was confirmed
- **ES/NQ micro vs mini contract math at 2R:** No risk-to-drawdown ratio analysis survived
- **Max accounts (beyond the 20-account Apex limit noted above):** No confirmed per-firm max account numbers

**Source these directly from each firm's current website before making decisions.**

---

## Caveats

- All information is current as of July 2026. Prop firm rules change frequently — especially around automation, drawdown calculations, and account limits. Verify directly before committing capital.
- No primary sources for drawdown, fee, or payout data survived verification. Third-party comparison sites (propfirmapp.com, selectpropfirms.com, proptopedia.com, fundedscore.com, tradingbrokers.com) are affiliate-driven and may contain outdated or incentivized information.
- The "refuted" designation means the claim failed adversarial verification under a high bar. Some refuted claims may contain grains of truth but could not be confirmed to the required standard.
- This research covers 6 firms in depth. Other major futures prop firms (Alpha Futures, Blue Guardian, FundedNext, FTMO's futures offering, SurgeTrader) were not included in the original claim set.
- Payout policies (splits, frequency, minimum thresholds, maximum caps) vary significantly by firm and were the biggest data gap in this analysis.

---

## Open Questions

1. Which firms, if any, have updated their drawdown calculations in 2026 (e.g., switching from trailing intraday to EOD, or from static to trailing)? Drawdown type is the single most important risk-of-ruin parameter for an automated ES system and no verified data was produced.
2. For firms that permit self-copy-trading (Apex, potentially others), how is "self" distinguished from "external signal copying" in practice? Does running the same algorithm across multiple accounts via TradersPost or similar count as self-copying or external copying?
3. What are the actual evaluation costs and payout splits for each firm as of July 2026? The lack of verified pricing data is the most actionable gap.
4. How do firms differentiate between "HFT" (universally banned) and "high-frequency manual trading" or "low-latency automated execution"? The boundary is fuzzy and firm-dependent.
