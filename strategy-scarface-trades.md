---
name: strategy-scarface-trades
created: 2026-06-10
status: research → partially implemented
source: Scarface Trades (YouTube @ScarfaceTrades, "The Accelerator" private Discord)
---

# Scarface Trades Methodology — Synthesis for Omen

Research synthesis from Scarface Trades public content (YouTube, TradeZella/FXReplay
playbooks, X/@ScarfaceTrades_). Goal: tighten Omen detection to match the
mechanical edge Scarface teaches. His approach is **90% mechanical, 10% discretionary**.

Sources:
- https://www.youtube.com/@ScarfaceTrades/videos
- https://www.tradezella.com/strategies/break-retest-strategy
- https://fxreplay.com/strategies/scarface-trades-scalping-strategy
- https://x.com/ScarfaceTrades_/status/1741940812928176286 (84% Rule)
- https://scarface-trades.com/ ("The Boardroom" signals) / "The Accelerator" Discord

---

## Core Framework (matches Omen today)

- **5-min Opening Range (ORB):** mark high/low of first five 1-min candles after 9:30 ET.
- **Window:** trade only 9:30–11:00 AM ET (volume + momentum strongest).
- **Timeframe:** entries on the 1-minute chart only.
- **R:R:** 1:2 minimum. Target = high/low of day or clean whole-number level.
- **Levels:** OR high/low, premarket high/low, prior-day high/low.

## The Three Setups (Scarface's wording)

### 1. Break & Retest
1. Mark a structure level with multiple touches (OR / PMH-PML / PDH-PDL).
2. Wait for a **clean break with displacement** — strong momentum candle away from
   the level. *Slow/hesitant breaks are low probability and skipped.*
3. Price pulls back and **retests** the level (or the Fair Value Gap left by the
   displacement). Enter on a 1-min confirmation candle showing the dominant side
   regaining control (strong wick / absorption back through the level).
- Stop: just beyond the retest level / FVG (mechanical, not arbitrary).
- Target: ≥2R; scale 25–50% at HOD/first major level, leave a runner.

### 2. One Candle Rule (3-step entry — the foundational setup)
1. **Mark the zone:** the *last down-close candle before the breakout* (for longs)
   or *last up-close candle before the breakout* (for shorts). That single candle
   is the micro demand/supply zone.
2. **Wait for retest** of that one candle.
3. **Confirm close** back through the zone (close above for longs / below for shorts)
   = buyer/seller absorption. Enter on that close or the next candle.
- Stop: just below the one-candle zone (longs) / above it (shorts).

### 3. The 84% Rule (re-entry)
- If a valid setup is taken and **does not work the first time**, when price returns
  to that exact level it works ~**84%** of the time on the second attempt.
- Re-enter at the reclaimed level; size up (Omen uses base + 50%).

## Risk / Session Rules (Scarface)
- **A+ setups only.** 2 attempts max per session.
- **Stop after one win** — bank the green, don't give it back. (Omen today ends
  after *2 losses*; Scarface's "1 win and done" is a different, stricter stop.)
- Contract selection: **first ATM or first OTM** weekly. ATM = stability; OTM = bigger
  payoff on continuation. Next-week contracts only when volatility is unusually high.

---

## Alignment vs current Omen bot

| Concept | Omen today | Scarface | Status |
|---|---|---|---|
| 5-min ORB, 1-min entries | yes | yes | ✅ aligned |
| 9:30–11:00 ET window | yes | yes | ✅ aligned |
| 2R target | yes | yes | ✅ aligned |
| B&R retest + wick confirmation | yes (`is_strong_*_price_action`) | yes | ✅ aligned |
| One Candle Rule | any opposite-color candle in last 10 | *last* opposite-close before breakout | ⚠️ looser |
| 84% re-entry | rejection-at-extreme proxy | re-entry at *same failed level* | ⚠️ proxy, not true re-entry |
| **Displacement** (momentum break) | not measured | required | ❌ missing |
| **Fair Value Gap** retest zone | none | core retest zone | ❌ missing |
| Premarket / prior-day levels | OR only | OR + PMH/PML + PDH/PDL | ❌ missing |
| Stop after 1 win | ends after 2 losses | ends after 1 win, 2 attempts | ❌ different |
| Contract: first ATM/OTM | nearest ATM | first ATM or first OTM | ⚠️ ATM only |

## Recommended detection changes (priority order)

1. **Displacement gate (highest edge, low risk):** before accepting a B&R signal,
   require the break candle(s) to show momentum — e.g. break candle body ≥ 1.5×
   average body of the prior N candles, or close ≥ X% beyond the level. Rejects the
   "slow/hesitant break" Scarface explicitly avoids.
2. **FVG retest zone:** detect a 3-candle gap (candle[i].high < candle[i+2].low for
   bullish) created during displacement; treat that gap as a valid retest zone in
   addition to the raw level. This is the biggest structural gap vs Scarface.
3. **One Candle Rule precision:** anchor the zone to the *last opposite-close candle
   immediately before the breakout*, not any of the last 10. Reduces false positives.
4. **Premarket / prior-day levels:** add PMH/PML and PDH/PDL alongside OR high/low as
   breakable structure (needs premarket bar history — see `fetch_recent_bars`).
5. **Session stop = 1 win:** add an optional "stop after first winner" mode to
   `TradingSession` to mirror Scarface's risk discipline.
6. **Contract selection:** allow first-OTM strike (one increment past ATM) as a config
   toggle in `options_sizer.nearest_strike`.

Items 3 and 5 are small/surgical. Items 1, 2, 4 are new detectors — implement behind
tests so the validated B&R / One-Candle / 84% logic stays intact.
