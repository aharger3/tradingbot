---
date: 2026-09-03
status: research
type: research
priority: high
version: 1.0.0
---

# Execution prep — per-instrument-angle, manual vs automatic

Extends `t64_execution_venues.md` (Robinhood/Tastytrade venue survey, execution gap list) and
`t65_execution_architecture.md` (state machine, kill switches, gates — not repeated here). Does
not redo `prop_firms_2026-09.md` / `prop_vanquish_terms.md` / `prop_firms_stocks.md` /
`prop_firms_futures.md`'s account-size/target/drawdown tables — this file is execution-mechanics
only, one layer down: platform, API, automation-legality, order types, phone-to-fill path.

## Recommendation

**Only Angle D (personal accounts) can go automatic today; A/B/C are all constrained by
someone else's rulebook.** Tastytrade is the strongest automatic path — a documented,
already-half-wired (`tastytrade_feed.py`, `broker/tastytrade.py`) read+write REST API with a
real sandbox, no firm-imposed bot ban because it's Austin's own account, and OTOCO/bracket
order types confirmed. IBKR is the second automatic path (TWS API and Client Portal Web API
both support a bracket — parent + child stop/target — in one call via `Transmit`/`cOID`), also
unconstrained by anti-bot rules on a standard account. Robinhood's Agentic Trading is officially
*sanctioned* automation (§29 of its Customer Agreement) but is built for a conversational MCP
client with a human able to approve or not approve each trade, in a segregated agentic
sub-account — whether it can be driven headlessly by a cron-scheduled script rather than a chat
session is still open (T64 flagged this; this pass did not find a public headless/programmatic
entry point beyond pointing an MCP-compatible client, which does include CLI tools like Codex
CLI, at `agent.robinhood.com/mcp/trading` — closer to "maybe" than T64's "prototype it," not yet
"yes"). Of the three prop-firm angles: **B (Trade The Pool) is manual-only by explicit written
rule** — its own Terms & Conditions, Section 11, ban "any custom, algorithmic, or other automated
trading software," and its AI-bots page states a person must "personally place and authorize
every single trade" — semi-automated webhook alerts (SignalStack) are advertised but land as a
notification a human then clicks, not an auto-submit. **C (Lucid Trading, MyFundedFutures) is
the one prop angle that explicitly allows bots** ("algorithmic trading, standard automated
strategies, EAs...fully permitted" — Lucid; algo trading permitted on eval+funded per MFF's own
policy per secondary sources, primary page 403'd), which lines up with T65's own observation that
futures is the smaller execution gap (price-level stops, no options-chain problem) — if OMEN
automates anywhere, futures via Lucid/MFF is the cleanest legal-to-do-it path. **A (Vanquish) has
no automation clause on its own terms/help pages** — third-party claims it's conditionally
permissive, unverified against a Vanquish primary source; treat as a support-ticket question
before ever automating it, same status T64/`prop_vanquish_terms.md` already left 0DTE in. No
firm or broker in this survey publishes a pre-fillable trade-ticket deep link (checked Robinhood,
tastytrade, thinkorswim/Schwab explicitly — none found), so **every manual path requires the
human to retype every field**; the push OMEN sends must carry the complete order — symbol,
contract (OCC option symbol or futures code), side, quantity/contracts, limit, stop, target — so
retyping is copy-paste, not lookup.

## Table

| Angle | Platform / official API | Automation allowed? | Order types / bracket-in-one-action | Phone→fill path (est.) | Deep link | Data feed / fill |
|---|---|---|---|---|---|---|
| **A — Vanquish Advanced Options** | DXtrade XT (webtrader `trade.vanquishtrader.com` + "Vanquish XT" iOS/Android app), powered by dxFeed/dxTrade — confirmed via Vanquish's own Help Center article "Platform Accessibility"; no public REST/FIX API found on Vanquish's own pages. **No official API — none.** | **UNVERIFIED on Vanquish's own pages.** No automation clause found in `vanquishtrader.com/terms`. Third-party (uncited-to-Vanquish) claims EAs are allowed if trader-owned/licensed and not latency-exploiting — not primary-sourced, do not build on it without asking support. | DXtrade XT natively supports market/limit/stop/stop-limit/OCO and a one-ticket bracket ("entry, take profit, and stop in one ticket" — DX.trade product page, not Vanquish-specific). Vanquish itself does not document order types on its rules pages. | UNVERIFIED — no deep link found; est. 30-60s (open Vanquish XT app → search symbol → build option leg → set bracket → confirm), slower than a shares app because options require chain navigation. | None found. | Real market data, **simulated fills**; spread-abuse clause bars exploiting sim bid/mid/ask (`prop_vanquish_terms.md` #7). |
| **B — Trade The Pool (shares, IBKR)** | Front-end is **TraderEvolution** (Windows desktop primary, web, mobile) — IBKR is the liquidity provider/custodian behind it, traders do **not** get direct TWS/Client Portal API access; TraderEvolution is the only documented access layer. | **Explicitly banned.** T&C §11: "The User may not use any custom, algorithmic, or other automated trading software... to execute trades." AI-bots page: "A human person must personally place and authorize every single trade... A program that opens or closes positions without requiring a person to give active consent to each trade counts as one." SignalStack webhook integration exists but is "currently in a beta state," rate-limited (2 req/min), and per the ban above still requires the manual click. | Program terms name Market/Stop/Limit orders explicitly ("pending limit," "stop pending"); no bracket-in-one-ticket language found in Trade The Pool's own docs (TraderEvolution the underlying vendor does support bracket-style tickets generally, not confirmed configured for TTP). | UNVERIFIED — no deep link; est. 20-40s (desktop client fastest; mobile TraderEvolution app slower — no timing published). | None found. | IBKR-sourced; IBKR no longer offers delayed U.S. equity quotes to its own clients (regulatory), implying real-time NBBO feeds through the stack — not confirmed as passed through unmodified to Trade The Pool's UI. Evaluation phase runs on simulated/"fictitious funds" (`prop_firms_2026-09.md`); funded-phase capital is real IBKR-routed per `prop_firms_stocks.md` — the two prior files disagree on phrasing, not resolved here. |
| **C1 — Lucid Trading (futures)** | Rithmic and Tradovate (also NinjaTrader, Quantower, Sierra Chart, and others on the Rithmic umbrella) — both have documented third-party APIs (Rithmic R\|API, Tradovate REST/WebSocket API). | **Explicitly allowed.** "Algorithmic trading, standard automated strategies, EAs, and algo systems are fully permitted on all account types" (secondary-sourced summary of Lucid's own FAQ/rules; primary `lucidtrading.com/general-faq/` 403'd on direct fetch this pass). HFT and latency arbitrage remain banned; custom API access in Python/Java/C++ and TradersPost integration both cited as supported. | Tradovate and NinjaTrader both natively support bracket orders (entry+stop+target, one action) and OCO; Rithmic's API exposes the same at the platform layer. | UNVERIFIED exact seconds; Tradovate's mobile app supports one-tap DOM trading with a pre-armed bracket template — likely the fastest manual path in this whole survey (est. 10-20s) once a bracket template is pre-built, because futures need no strike/expiry selection. | None found publicly documented. | Real CME data via Rithmic/CQG feeds per secondary sources; simulated capital, live price action (`prop_firms_futures.md`). Fill convention (bid/ask vs mid) not found on Lucid's own pages — UNVERIFIED. |
| **C2 — MyFundedFutures (futures)** | Tradovate, NinjaTrader, TradingView, Volumetrica, ATAS, Quantower, DEEPCHART (help.myfundedfutures.com platform list). | **Conflicting dates, resolve by asking support before building.** Secondary sources describe a 2025 policy update permitting algo trading on both eval and funded accounts via MFF's own "Bots/Algorithmic Trading Policy" (`intercom.help/funded-futures-family/.../10114863-bots-algorithmic-trading-policy` — **403'd on direct fetch this pass, primary page not independently verified**); older secondary sources describe a blanket ban. HFT/bot misuse and price-discrepancy exploitation are cited as still-prohibited regardless of which version is current. | Not documented on MFF's own platform pages found this pass; Tradovate/NinjaTrader bracket-in-one-action applies the same as C1 if MFF routes through them identically. | UNVERIFIED — same platform stack as C1, similar estimate (10-20s) if algo policy is confirmed current. | None found. | UNVERIFIED — not found on MFF's own pages this pass. |
| **D1 — Tastytrade (personal)** | `api.tastytrade.com` (prod) / `api.cert.tastyworks.com` (sandbox) — official, documented, read+write. Already integrated in this repo (`tastytrade_feed.py` read/quote, `broker/tastytrade.py` sandbox-only order adapter). | **Allowed — personal account, no firm ban.** Ordinary brokerage account terms apply, not a prop-firm anti-bot clause. | `POST /accounts/{account}/orders` (live), `POST /accounts/{account}/orders/dry-run` (validation, no capital risk) — confirmed via `developer.tastytrade.com/docs/guides/place-an-equity-order/`. Equity orders are single-leg only; multi-leg (options spreads) via a separate guide. **OTOCO/OCO (bracket) is supported as a complex order** via `place_complex_order` (confirmed against the community `tastyworks-api` SDK docs, which wrap the same REST surface `broker/tastytrade.py` targets) — one call places entry+stop+target together. | Not deep-link-based; a script hitting the REST API directly is sub-second once a signal is ready — this is the one angle where "phone push → filled order" collapses to "OMEN submits the order itself," no human retyping required, once Section 4 gates (`t65_execution_architecture.md`) are cleared. | None found/needed — API replaces the deep-link path. | Real-time via DXLink (already proven in this repo); sandbox order-routing untested against a live sandbox call as of `broker/tastytrade.py`'s own module docstring (no sandbox credentials provisioned yet). |
| **D2 — Interactive Brokers (personal)** | TWS API (socket) and Client Portal Web API (REST) — both official, both documented (`interactivebrokers.github.io/tws-api`, `interactivebrokers.com/docs/web-api`). | **Allowed — personal account, no firm ban.** Requires TWS/IB Gateway running as the local API bridge (TWS API) or a Client Portal Gateway session (Web API). | TWS API: bracket via the `Transmit=false` parent-then-children pattern (`interactivebrokers.github.io/tws-api/bracket_order.html`). Client Portal Web API: `POST /iserver/account/{accountId}/orders` accepts an **array of parent+child orders in one call** — cOID on the parent, matching `parentId` on children — confirmed native one-call bracket support, plus OCA-group support in the same array shape. | Not deep-link based for automation; for a human, IBKR mobile has no confirmed pre-fill deep link — est. 30-45s market/limit, options need chain navigation similar to Vanquish. | None found. | IBKR is real-time (regulatory: no more delayed U.S. equity quotes to IBKR clients); real broker, real fills — not a sim. |
| **D3 — Robinhood Agentic Trading (personal)** | Official MCP server at `agent.robinhood.com/mcp/trading` — no plain REST order-entry API published outside MCP (`t64_execution_venues.md`). | **Officially sanctioned, but scoped.** Customer Agreement §29.2: "External AI agents can place real trades and access your portfolio," confined to a separately-funded "agentic account." Per-trade or blanket approval is the user's own configuration choice — Robinhood's support page: "if you've asked your agent to take action without asking your approval, it can place trades without your confirmation," i.e. a headless-style unattended mode is at least contemplated, not proven wired to a cron job. | Order types for agentic trades not enumerated on Robinhood's own overview page found this pass — UNVERIFIED. | An MCP client (Claude Desktop, Codex CLI, etc.) issuing the trade is the "phone push" in this angle — the open question (T64, unresolved this pass) is whether that client can be a headless scheduled process rather than an interactive session. | N/A — MCP call replaces deep link if headless works. | UNVERIFIED on Robinhood's own pages this pass; real brokerage, real fills (not simulated) once live. |

## What OMEN must emit per angle

Regardless of venue, no deep link exists anywhere in this survey — every push must be a complete,
self-sufficient order so a human copies fields rather than looking them up:

- **Options (Vanquish, personal Tastytrade/IBKR/Robinhood):** underlying symbol, expiration date
  (`YYYY-MM-DD`), strike, right (call/put), OCC-style contract symbol if resolvable
  (`tastytrade_feed.py::_resolve_contract` already does this against Tastytrade's chain), contract
  count (from `options_sizer.py`'s `GRADE_SIZE_PCT` budget), entry limit price, stop premium,
  target premium(s) for the ladder. Vanquish's single-leg-only, no-spreads, no-selling-to-open
  constraint (`prop_vanquish_terms.md` #1) means the emitted order is always a single long
  call/put — no multi-leg field is ever needed for that angle.
- **Shares (Trade The Pool):** symbol, side (buy/sell), share quantity (position-sizing already
  produces this upstream of the options-specific sizer), entry limit price, stop price, target
  price(s). No strike/expiry fields apply.
- **Futures (Lucid, MyFundedFutures):** contract code including month/year (e.g. `ESZ6`), side,
  contract count (already computed in `options_sizer.build_futures_plan`, tick-value-based —
  `research/prop_firms_futures.md`'s tick tables), entry price, stop price (tick-denominated),
  target price(s).
- **Every angle, always:** the grade (S/A/C) and the rulebook's 30/30/30/10 scale-out levels as
  plain numbers, not just a single target — a human executing a ladder by hand needs each tranche
  price up front, not a mental recompute mid-trade.

## Rules that forbid automation

- **Trade The Pool, Terms & Conditions §11:** "The User may not use any custom, algorithmic, or
  other automated trading software (collectively, 'Automated Trading Software') to execute
  trades."
- **Trade The Pool, AI trading bots page:** "A human person must personally place and authorize
  every single trade... A program that opens or closes positions without requiring a person to
  give active consent to each trade counts as one." Also bans copy-trading tools, HFT, and latency
  arbitrage in the same clause set.
- **Trade The Pool, Terms & Conditions §10.1.7** (trading-rule violations, not just §11): bars
  "using any software, artificial intelligence, ultra-high speed, or mass data entry which might
  manipulate, abuse, or give User an unfair advantage," plus specific EA bans (rollover-night
  scalping EAs, shared third-party EAs, EAs whose source the trader doesn't own).
- **Robinhood Customer Agreement §29.1** (context, not a ban — a gate): "You may not use the API
  Package or develop Licensee Products without Robinhood's express written consent (and Robinhood
  may decline any such request for use or development in its sole discretion)" — already quoted
  in `t64_execution_venues.md`, restated here because it applies identically to Angle D3.
- **Vanquish, Lucid, MyFundedFutures:** no primary-sourced prohibition found this pass (Vanquish:
  none found either direction; Lucid and MFF: secondary sources describe automation as explicitly
  *permitted*, not forbidden — included above for contrast, not as a forbidding rule).

## Sources

- `research/t64_execution_venues.md` — read 2026-09-03 (Robinhood Agentic Trading, unofficial-API ToS risk, Tastytrade/Tradier/IBKR/Schwab/Alpaca comparison, PDT elimination, options-approval-level rule, the execution gap list)
- `research/t65_execution_architecture.md` — read 2026-09-03 (state machine, broker interface, gates, kill switches — not restated here)
- `research/prop_vanquish_terms.md` — read 2026-09-03 (Vanquish sim-fill / spread-abuse clause, cited above)
- `research/prop_firms_2026-09.md`, `research/prop_firms_stocks.md`, `research/prop_firms_futures.md` — read 2026-09-03 (account terms, not restated)
- `tastytrade_feed.py`, `broker/tastytrade.py` — read 2026-09-03 (existing repo integration, sandbox host, order-body shape already coded)
- Vanquish, Terms and Conditions — https://www.vanquishtrader.com/terms — fetched 2026-09-03 (no automation clause found)
- Vanquish Help Center, "Platform Accessibility" — https://support.vanquishtrader.com/en/articles/11030489-platform-accessibility — fetched 2026-09-03 (DXtrade XT, webtrader + Vanquish XT app, no API mentioned)
- DX.trade, "Order Management System" — https://dx.trade/dxtrade-xt/order-management-system/ — via search, fetched 2026-09-03 (bracket-in-one-ticket, OCO support — platform-general, not Vanquish-specific)
- Trade The Pool, Program Terms — https://tradethepool.com/program-terms/ — fetched 2026-09-03 (TraderEvolution platform, order types, SignalStack beta + 2 req/min rate limit)
- Trade The Pool, Terms & Conditions — https://tradethepool.com/terms-and-conditions/ — fetched 2026-09-03 (§11 automation ban, §10.1.7 EA/software bans, quoted above)
- Trade The Pool, "AI Trading Bots on Funded Accounts" — https://tradethepool.com/ai/ai-trading-bots-on-funded-accounts/ — fetched 2026-09-03 (human-must-place-every-trade rule, quoted above)
- Trade The Pool, "Interactive Brokers" (technical-skill page) — https://tradethepool.com/technical-skill/interactive-brokers/ — fetched 2026-09-03 (does not confirm direct TWS/CP API access for traders)
- TraderEvolution news release — https://traderevolution.com/news/trade-pool-employs-traderevolutions-software-their-proprietary-trading-project/ — via search, fetched 2026-09-03 (confirms TraderEvolution is the front-end, IBKR is liquidity/custodian)
- Lucid Trading, General FAQ — https://lucidtrading.com/general-faq/ — **403 on direct fetch 2026-09-03; not independently verified**, cited via secondary summaries (TradersPost review, saveonpropfirms.com) of the same page's stated content
- MyFundedFutures, "Bots/Algorithmic Trading Policy" — https://intercom.help/funded-futures-family/en/articles/10114863-bots-algorithmic-trading-policy — **403 on direct fetch 2026-09-03; not independently verified**, cited via secondary summary (quantvps.com blog)
- MyFundedFutures Help Center, Trading Platforms — https://help.myfundedfutures.com/en/collections/5786939-trading-platforms — fetched 2026-09-03 (platform list; no automation policy on this page)
- Tastytrade developer docs, "Place an equity order" guide — https://developer.tastytrade.com/docs/guides/place-an-equity-order/ — fetched 2026-09-03 (POST /accounts/{account}/orders, dry-run endpoint, sandbox host api.cert.tastyworks.com, single-leg-only for equity)
- tastyworks-api (community SDK) docs, Orders — https://tastyworks-api.readthedocs.io/en/latest/orders.html — fetched 2026-09-03 (OTOCOOrder/OCOOrder/OTOOrder via place_complex_order, wraps the same REST surface)
- Interactive Brokers, TWS API Bracket Orders — https://interactivebrokers.github.io/tws-api/bracket_order.html — via search, fetched 2026-09-03 (Transmit flag, parent/child attach)
- Interactive Brokers, Client Portal Web API, Place Order — https://www.interactivebrokers.com/docs/web-api/v1/endpoints/orders/place-order — via search, fetched 2026-09-03 (cOID/parentId array = one-call bracket; OCA group support)
- IBKR, "Receive Delayed Market Data" / market-data-pricing — https://www.interactivebrokers.com/en/pricing/market-data-pricing.php, https://www.ibkrguides.com/traderworkstation/receive-delayed-market-data.htm — via search, fetched 2026-09-03 (no more delayed U.S. equity quotes to IBKR clients)
- Robinhood, Agentic Trading overview — https://robinhood.com/us/en/support/articles/agentic-trading-overview/ — fetched 2026-09-03 (MCP client list, approval-mode language, order-types not enumerated)
- Robinhood Customer Agreement PDF, §29 — https://cdn.robinhood.com/assets/robinhood/legal/Robinhood-Customer-Agreement.pdf — already cited in `t64_execution_venues.md`, restated here for Angle D3
- Web searches for a Robinhood / Tastytrade / thinkorswim-Schwab mobile deep-link / URL-scheme trade ticket — no public documentation found for any of the three, 2026-09-03 (absence noted, not a confirmed non-existence)
