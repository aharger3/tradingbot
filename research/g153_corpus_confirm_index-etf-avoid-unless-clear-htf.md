# F4 Corpus Confirmation: Index ETF Avoidance Rule

## Candidate Rule
"Index ETFs (SPY, QQQ) are avoided by default and traded only when the higher-timeframe direction is very clearly bullish or bearish."

## Search Results

| Tag | Quote | Source | Evidence |
|---|---|---|---|
| **contradicted** | "IREN was showing clear direction and momentum compared with SPY or QQQ...as SPY and QQQ were rejecting off a HTF KL or resistance." | Circle post #33494603, Todd Scott (Tito Frescado), 2026-06-10 | Todd trades IREN *relative to* SPY/QQQ HTF direction but does not state that SPY/QQQ themselves are avoided. He actively monitors them as a reference point and exits when they reject off HTF resistance—demonstrating that index ETFs are actively traded and used for bias confirmation, not avoided. The rule suggests avoidance; the evidence shows active engagement. |

## Analysis

The corpus search found 15+ statements mentioning SPY or QQQ in the Circle trader posts and rules.jsonl. Scarface and Jdub both produce rules and setups on SPY/QQQ directly (17 instances in rules.jsonl). The rulebook notes 18 index trades (QQQ 9, IWM 5, SPY 4) across 1,017 total trades in the backtest, and quotes Austin: **"indecies not traded much either everything should be pretty balanced."**

No statement from Scarface or Jdub explicitly says "avoid index ETFs unless clear HTF direction." Instead, the corpus shows:
- Direct trading of SPY and QQQ with specific setups
- Using index HTF direction as a *filter* for single-name trades
- Active management of index positions (e.g., "exiting when SPY/QQQ reject off HTF resistance")

**Verdict:** The rule is **contradicted** by trading activity, not by explicit refusal statements.

