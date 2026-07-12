# Trading Bot — Omen Trader Integration

**Date:** 2026-05-16  
**Type:** Trading / Tech  
**Status:** Idea

## What It Is
Build a trading bot that integrates with Omen Trader and runs on Scarface Trades' options trading framework.

## Why It Matters
- Automate execution of professional options trading strategies
- Consolidate trading knowledge from multiple sources (Scarface Trades plans, Notebook LM, research)
- Create a unified system that can make real-time trading decisions
- Scarface Trades expertise → bot intelligence

## Core Trading Setups (Bot Foundation)
Austin backtests these and they work consistently. These are the mechanical rules the bot will execute:

1. **Break and Retest** — Wait for breakout, re-entry on retest
2. **5 Minute Opening Range** — Trade within/off the first 5-min candle range
3. **One Candle Rule** — Specific entry/exit rules based on single candle patterns
4. **84% Rule** — [Specific rules TBD from Scarface videos]

*Discretion/experience elements noted for later — focus on mechanical setups first*

## Key Ideas
- **Omen Trader integration** — API connectivity for live execution
- **4 core setups** — Build bot to execute Break/Retest, 5min OR, One Candle, 84% rule
- **Scarface Trades videos** — Extract exact rules from his YouTube/Discord content
- **Notebook LM** — Austin's outline with sources (at: [link needed])
- **Mechanical execution** — Code the setups so bot can trade without discretion first
- **Options-focused** — Scarface Trades is an options broker firm, so bot specializes in options

## Trading Setup
- **Current:** Trading manually through Omen (options prop firm)
- **Problem:** Emotions/human conditions limiting results
- **Goal:** Bot account (emotion-free mechanical execution) + keep human account (discretion)

## Possible Next Steps
1. **Verify Omen API** — Contact support: Can I automate/use external bot API? (Check FAQ first)
   - If YES → Build Python bot + Omen API
   - If NO → Switch to Interactive Brokers (has solid options + API)
2. Document the 4 setups in vault — exact entry/exit/risk rules + Scarface videos
3. Build trading rules document — mechanical conditions for Break/Retest, 5min OR, One Candle, 84%
4. Design bot logic — simple state machine: scan → identify setup → execute → manage position
5. Build prototype in Python — test against one setup first
6. Backtest against historical options data
7. Paper trade on bot account
8. Live execution (bot account only, human account stays manual)

## Automation Potential
🤖 **High** — This is a perfect candidate for agent automation. Once framework is defined, agents could:
- Scrape and organize trading plan documentation
- Extract strategy rules from Scarface Trades materials
- Monitor Notebook LM for updates
- Test and refine bot logic
- Handle Omen Trader integration code

## Data Sources Available
- **Discord** (premium member access) — daily signals, discussions, strategy breakdowns
- **Circle community** (premium member) — deeper strategy content, community trades
- **YouTube** (public) — free strategy videos, educational content
- **Scarface himself** — looks at/manages the content inside the community

## Notes
- Keep momentum — build something runnable early, even if basic
- Scarface Trades expertise is the competitive advantage here
- Need to be careful with live trading — start with simulation/paper trading
- Key question: How much Discord/Circle content do we need to capture to train the bot effectively? Start by collecting one complete trading plan (entry, exit, risk management) and test that first.
