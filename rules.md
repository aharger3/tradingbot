---
name: vanquish-trading-rules
created: 2026-05-22
status: active
---

# Vanquish Trading Rules

## Core Parameters
- **Timeframe**: 1-minute candles only
- **Trading hours**: 9:30 AM – 11:00 AM ET
- **Stop rule**: 2 consecutive losses = end trading day
- **Risk/reward target**: 2:1 minimum on all trades
- **Max loss per trade**: $1000
- **Bias**: None (trade calls AND puts equally)

## Watchlist
Primary (high options volume, tight spreads): NVDA, TSLA
Secondary: GOOG, AMZN, MSFT, PLTR, AMD, SPY, QQQ, AAPL, META
(More to be added)

---

## Setup 1: Break and Retest

**Entry Conditions**
- Stock breaks key level (5-min opening range, premarket high/low, previous day high/low)
- Closes away from level without touching it
- Retests level with **A+ confirmation** (hammer stick)
  - Hammer = sellers try to break below level → buyers reclaim → close at top
- Only trade when: outside 5-min opening range OR targeting high/low of day
- Entry must be clear/obvious, not random candle

**Exit**
- Stop loss: below breakout level (for long trades)
- Target: 2:1 risk/reward

---

## Setup 2: One Candle Rule

**Entry Conditions**
- Find support candle (red for calls, green for puts)
- Stock breaks away from candle
- Retests candle with strong price action
- **A+ confirmation** = hammer stick on retest
- Only trade when: outside 5-min opening range OR targeting high/low of day
- Must be clear/obvious, not random candle

**Exit**
- Stop loss: below candle (for long trades)
- Target: 2:1 risk/reward

**Bias Flip**
- Red candlestick as support = bullish entry (calls)
- Green candlestick as support = bearish entry (puts)

---

## Setup 3: 84% Rule

**Entry Conditions**
- Initial entry at level (using any valid setup above)
- Get stopped out of first trade
- Stock reclaims **exact entry level** (close at or above for long trades)
- Re-enter with **50% increased position size**
- Statistical edge: 84% win rate on re-entry

**Exit**
- Trigger: Wait for candle close at or above entry level (easier to backtest)
- Stop loss: below entry level
- Target: 2:1 risk/reward

**Caveat**
- If candle already showing strong price action (closing at high of day), risk/reward is poor → skip entry
- Balance between missing entries vs waiting for clean signal
- Using candle close may miss some trades but cleaner for automation

---

---

## Real Example: All Three Setups in One Trade
Screenshot from 2026-05-23:
- Stock breaks above 5-min high (green line), consolidates
- Retests 5-min high with lower wick touching level
- Weak price action but buyers step in = entry taken
- Stop loss: 9:34 candle (one candle rule stop)
- First trade: stopped out
- Later: green candle reclaims exact entry price
- Re-entry (84% rule): hits profit target

---

## Position Sizing

| Rule | Position Size |
|------|---|
| Initial entry | Base (max loss $1000) |
| 84% Rule re-entry | Base + 50% |
| All trades | Target 2:1 risk/reward minimum |

---

## Notes for Bot Implementation
- Calls = bullish setup (break above, hammer up)
- Puts = bearish setup (break below, hammer down)
- 1-min candles only — no mixing timeframes
- Pre-market data needed for "premarket high/low" reference
- Day ends after 2 losses or 11 AM, whichever first

---

## Status (as of 2026-05-24)

**Implemented**:
- Signal detection engine (`vanquish_bot.py`): break-and-retest, one-candle-rule, 84% rule logic
- Mock data generator (`data_loader.py`): realistic test scenarios for all three setups
- Backtester framework (`backtester.py`): validates signal logic on historical/mock data
- Discord webhook integration (`discord_bot.py`): colored embeds, real-time alerts
- CLI signal runner (`signal_runner.py`): reads JSON/CSV/stdin, detects signals, posts to Discord

**Testing**: All three signals fire correctly on break-and-retest mock scenario ✓

**Blockers**:
1. TradeZella backtest results (Austin to screenshot after restart)
2. DX Trade API or CSV export confirmation for live data

**Next**: Validate rules with TradeZella backtest → Build data connector → Hermes 24/7 runner

---

## Scarface Trades Refinements (2026-06-10)

Full synthesis in `strategy-scarface-trades.md`. Highest-impact deltas vs current bot:
1. **Displacement gate** — require a strong-momentum break before accepting a retest
   (skip slow/hesitant breaks). Not yet measured by the bot.
2. **Fair Value Gap (FVG)** — the displacement gap is a valid retest zone in addition
   to the raw level. Missing today.
3. **One Candle Rule** anchors to the *last opposite-close candle immediately before the
   breakout* (bot currently scans the last 10 — looser).
4. **Premarket high/low + prior-day high/low** as breakable levels (OR only today).
5. **Session stop = 1 win / 2 attempts** (bot ends after 2 losses).
6. Contract: first ATM *or* first OTM weekly (bot uses nearest ATM only).
