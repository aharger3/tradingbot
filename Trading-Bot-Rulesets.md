# Trading Bot Rulesets — Scarface Trades Framework

**Created:** 2026-05-16  
**Source:** Austin's actual Zella trades + Scarface Trades framework  
**Status:** Foundation for bot automation

---

## Setup 1: Break and Retest (Opening Range)

**What it is:** Price breaks above/below the opening range (first 5-min candle), then retraces back to that level. Bot enters on the retest.

### Entry Conditions
- Identify the 5-minute opening range (first candle of the session, or defined range)
- Wait for price to **break** above the high or below the low with volume/momentum
- Wait for price to **retest** the breakout level (come back and touch it)
- Enter on the retest (when price bounces off the level again in direction of breakout)
- **Confirmation:** Higher timeframe (HTF) trend should align with breakout direction

### Exit Conditions
- **Profit target:** 10:1 risk/reward minimum (mentioned by Austin as important)
- **Stop loss:** Below the retest level or below the opening range low (depending on direction)
- **Time-based:** If setup hasn't triggered by end of day, close position
- **Early exit:** If price moves against you before proper retest, cut immediately

### Risk Management
- Position size: Based on distance to stop loss (fixed risk per trade)
- Max loss per trade: Calculate based on account size
- Don't be too stubborn: Exit if setup breaks before reaching target (Austin's lesson from TSLA)
- Get good fills: Better entry = smaller risk

### Real Example (Austin's Zella Trade)
- TSLAswing from prior day, HTF looked good
- Sold exact bottom, price rallied to ATH
- Mistake: Sold too early, didn't trust the HTF signal
- Chart shows: Opening range break, retest entry point, proper stop/target placement

---

## Setup 2: 5-Minute Opening Range (84% Rule Related)

**What it is:** The first 5-minute candle of the session sets the range. 84% of the time, price will eventually break this range and not come back inside it.

### Entry Conditions
- Define the opening range: High and low of the first 5-minute candle (or first N candles)
- Wait for price to break above the high OR below the low
- **84% rule**: Once broken, price tends to not return, so entry on break is high probability
- Enter at/near the break of the range

### Exit Conditions
- **Profit target:** If 84% rule holds, ride the momentum for 10:1 RR (or market structure target)
- **Stop loss:** Other side of the opening range, or below the swing low/high
- **Early exit:** If price reverses back into range (the 16% of the time it fails), exit immediately

### Risk Management
- This is a higher-probability setup (84% win rate)
- Position size can be slightly larger due to high probability
- Use tight stops to protect the 16% failures
- Combine with HTF confirmation for best results

### Key Learning from Austin
- NVDA trade: "small winner" — needed to aim for at least 10% RR
- Setup was good but needed better execution (fills, exits)
- Good calls at 9:45 would have been the better move (timing matters)

---

## Setup 3: One Candle Rule

**What it is:** [TO BE DOCUMENTED] — Austin's notes reference this but need more detail from Scarface videos.

### Entry Conditions
- [Pending: exact candle pattern to identify]
- [Pending: entry price level]

### Exit Conditions
- [Pending: profit target rules]
- [Pending: stop loss placement]

### Risk Management
- [Pending]

---

## Setup 4: 84% Rule (Full Details)

**What it is:** Extended explanation of the 84% probability rule noted in Austin's charts.

### Core Principle
- When opening range (first 5 minutes) breaks, 84% of the time price doesn't return inside that range
- This is a statistical edge that can be mechanically traded

### Entry Conditions
- [Clarify exact timing and confirmation]

### Exit Conditions
- [Clarify exact targets and stops]

### Risk Management
- [Clarify position sizing for high-probability trades]

---

## Bot Decision Engine (Pseudocode)

```
WHILE market is open:
    
    # Scan for Setup 1: Break and Retest
    IF price breaks opening range high/low:
        IF price retraces back to break level:
            IF HTF trend confirms breakout direction:
                ENTER position
                SET stop_loss = opening_range_opposite_side
                SET profit_target = 10:1 risk_reward_minimum
    
    # Scan for Setup 2: 84% Rule
    IF opening_range is defined:
        IF price breaks opening_range_high OR opening_range_low:
            ENTER (84% probability doesn't return inside)
            SET stop_loss = opening_range_opposite_side
            SET profit_target = 10:1 RR or market structure
    
    # Monitor open positions
    FOR each open_position:
        IF position_hits_profit_target:
            EXIT trade
        IF position_hits_stop_loss:
            EXIT trade (cut early, don't be stubborn)
        IF time_to_end_of_day:
            CLOSE position
```

---

## Austin's Key Lessons (From Zella Trade)

1. **HTF Confirmation is Critical** — Don't trade against the higher timeframe trend
2. **Don't Sell Too Early** — Wait for the full target, not premature profits
3. **Trust Your Setup** — PLTR was a good setup but Austin didn't trust his eyes
4. **Better Fills Matter** — Same setup, different entry price = different risk management
5. **10:1 Risk/Reward** — This is the minimum threshold Austin targets
6. **Cut Early if Wrong** — GOOGL: "Stop Loss Detailed down cut below resistance trade" — know when to exit
7. **Small Wins Are Okay** — Better to take consistent small winners than miss big moves

---

## Next Steps for Bot

1. ✅ Define the 4 setups (3 remaining to be documented from Scarface videos)
2. [ ] Code the setup detection logic (pattern recognition)
3. [ ] Code the entry/exit execution logic
4. [ ] Backtest against historical options data
5. [ ] Paper trade to verify real market conditions
6. [ ] Live trade with bot account (separate from Austin's manual account)

---

## Video References
- Break and Retest: https://youtu.be/5KHVU0zOmks
- [Other setup]: https://youtu.be/dNXhFwy5tjY
- More to gather from Scarface Trades YouTube channel

