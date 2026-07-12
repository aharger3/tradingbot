"""Compile all agent outputs into one comprehensive trade-review file + summary."""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r"C:\Users\aharg\tradingbot")
OUT = BASE / "_all_trade_reviews.json"

# Inline results from agents that returned JSON directly
INLINE_BATCHES = []

# --- batch_000 agent (10 reviews) ---
INLINE_BATCHES.append([
    {"ticker": "AMD", "direction": "unknown", "verdict": "good", "reason": "Stuck to plan, executed properly, managed risk perfectly — solid setup that just didn't play out as hoped", "pnl": "N/A", "lesson": "N/A", "author": "Hayden", "timestamp": "2025-07-09T20:37:09", "channel": "options-trade-reviews"},
    {"ticker": "AMD", "direction": "short", "verdict": "mixed", "reason": "Had the right idea that AMD was reversing, but best entry was at the 167 level (PDH/key level). Entry was suboptimal though trade was managed well otherwise", "pnl": "N/A", "lesson": "Be careful shorting in a downtrend if overextended; look for entries at key levels", "author": "Jdub", "timestamp": "2024-05-29T20:20:06", "channel": "trade-feedback"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Great clean retest setup — a textbook entry for the strategy", "pnl": "N/A", "lesson": "N/A", "author": "👑 of Puts", "timestamp": "2024-07-19T17:57:30", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "long", "verdict": "mixed", "reason": "Not a bad long, but there were better names to long (TSLA, AMZN, AAPL) showing more relative strength that day", "pnl": "N/A", "lesson": "N/A", "author": "Jdub", "timestamp": "2024-09-10T21:34:05", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "long", "verdict": "good", "reason": "Re-tested $123.13 which was a prior turning point level from August 29 on the 30-min chart — a solid entry point", "pnl": "N/A", "lesson": "N/A", "author": "RonDo", "timestamp": "2024-09-26T00:58:09", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "short", "verdict": "mixed", "reason": "Not a bad trade and would have worked out, but there were better setups like AAPL. By the time the premarket lows broke on NVDA most of the move was already done", "pnl": "N/A", "lesson": "N/A", "author": "Mar", "timestamp": "2025-01-10T23:53:39", "channel": "trade-feedback"},
    {"ticker": "QQQ", "direction": "long", "verdict": "mixed", "reason": "Textbook 5-min low retest with a nice rejection candle, but stop was way too tight — stopped out just before the flush", "pnl": "N/A", "lesson": "Stop should be placed above the impulsive candle that broke the range", "author": "Mar", "timestamp": "2025-01-11T00:23:13", "channel": "trade-feedback"},
    {"ticker": "AAPL", "direction": "long", "verdict": "bad", "reason": "Low probability trade — volume and price action did not provide confirmation for going long; some FOMO after hesitating", "pnl": "N/A", "lesson": "N/A", "author": "BrokeAintNoJoke", "timestamp": "2025-01-07T21:40:15", "channel": "trade-feedback"},
    {"ticker": "GOOG", "direction": "unknown", "verdict": "bad", "reason": "No valid trade on GOOG until way late in the day — no key levels were retested per strict system using OBs and FVGs", "pnl": "N/A", "lesson": "N/A", "author": "crunchybrewski", "timestamp": "2024-08-23T17:54:49", "channel": "trade-feedback"},
    {"ticker": "QQQ", "direction": "long", "verdict": "good", "reason": "Beautiful entry — retested the 5-min opening range low with confirmation", "pnl": "N/A", "lesson": "N/A", "author": "crunchybrewski", "timestamp": "2024-08-23T17:54:49", "channel": "trade-feedback"},
])

# --- chunk 4 agent (33 reviews) ---
INLINE_BATCHES.append([
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "$250 on 1 contract is solid money", "pnl": "+$250", "lesson": "N/A", "author": "EeveeWinter", "timestamp": "2025-12-16T15:42:43", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "long", "verdict": "mixed", "reason": "Sold too early after the first push, should have held longer for more profit", "pnl": "N/A", "lesson": "Let winners run after a good entry", "author": "FraggDieb", "timestamp": "2025-12-16T20:00:34", "channel": "trading-floor"},
    {"ticker": "META", "direction": "long", "verdict": "bad", "reason": "Took 2 PDH retest entries and both were losers", "pnl": "N/A", "lesson": "N/A", "author": "Jason", "timestamp": "2025-12-22T15:07:13", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "long", "verdict": "bad", "reason": "No alignment with QQQ price action and poor volatility day", "pnl": "N/A", "lesson": "Check broader market alignment and volatility before taking a setup", "author": "Stan", "timestamp": "2025-12-22T18:31:58", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Used strategy from the group and made a quick $350 on 2 contracts", "pnl": "+$350", "lesson": "N/A", "author": "beyim99", "timestamp": "2026-01-05T16:01:53", "channel": "trading-floor"},
    {"ticker": "MU", "direction": "long", "verdict": "bad", "reason": "Bought at the very top and lost $345 in less than 5 minutes", "pnl": "-$345", "lesson": "Don't buy at the top of a move — wait for pullback", "author": "Manny.o", "timestamp": "2026-01-12T19:08:42", "channel": "trading-floor"},
    {"ticker": "GOOGL", "direction": "long", "verdict": "bad", "reason": "Got $100 of slippage on 4 calls due to terrible fill", "pnl": "-$100", "lesson": "Watch fill quality — use limit orders", "author": "jwolfe29", "timestamp": "2026-01-13T14:48:55", "channel": "trading-floor"},
    {"ticker": "MU", "direction": "unknown", "verdict": "good", "reason": "Skipped when something didn't feel right, then watched it take off — good discipline", "pnl": "N/A", "lesson": "Trust intuition — skipping a trade that doesn't feel right is valid", "author": "Huy", "timestamp": "2026-01-29T00:30:19", "channel": "trading-floor"},
    {"ticker": "NVDA", "direction": "unknown", "verdict": "good", "reason": "Avoided NVDA which didn't work out — good discipline to pass", "pnl": "N/A", "lesson": "Sometimes not trading is the best trade", "author": "Huy", "timestamp": "2026-01-29T00:30:19", "channel": "trading-floor"},
    {"ticker": "NVDA", "direction": "long", "verdict": "bad", "reason": "Let it hit full stop even though could have cut earlier — poor active management", "pnl": "-$400", "lesson": "Cut losses early; don't wait for the stop to take you out", "author": "ZTrades", "timestamp": "2026-01-29T00:39:12", "channel": "trading-floor"},
    {"ticker": "AMD", "direction": "long", "verdict": "bad", "reason": "Broke one-trade-per-day rule after NVDA loss and revenge traded AMD — discipline breakdown", "pnl": "N/A", "lesson": "Stick to rules after a loss; don't revenge trade", "author": "ZTrades", "timestamp": "2026-01-29T00:39:12", "channel": "trading-floor"},
    {"ticker": "AMZN", "direction": "unknown", "verdict": "bad", "reason": "Forgot patience and entered a trade too tempting to pass up", "pnl": "N/A", "lesson": "Patience is key — don't let a tempting setup override discipline", "author": "Royal191", "timestamp": "2026-03-17T13:32:23", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "bad", "reason": "Chased a good trade, broke rules, turned a $1500 loss into $3500 trying to make it back", "pnl": "-$3,500", "lesson": "Never revenge trade — accepting a loss is cheaper than chasing it", "author": "Z33TRADES", "timestamp": "2026-04-09T17:40:26", "channel": "trading-floor"},
    {"ticker": "AMD", "direction": "unknown", "verdict": "bad", "reason": "Chased and broke rules trying to recover TSLA loss, compounding damage", "pnl": "N/A", "lesson": "N/A", "author": "Z33TRADES", "timestamp": "2026-04-09T17:40:26", "channel": "trading-floor"},
    {"ticker": "AMD", "direction": "long", "verdict": "bad", "reason": "Got scared when price came back, sold 1 contract, bought back in, sold again — inconsistent management", "pnl": "N/A", "lesson": "Stick to plan; don't panic and flip mid-trade", "author": "JP400", "timestamp": "2026-04-22T01:48:06", "channel": "trading-floor"},
    {"ticker": "INTC", "direction": "long", "verdict": "bad", "reason": "Held through -$1200 drawdown then sold for only $100 profit", "pnl": "-$240", "lesson": "Hold to thesis or cut early — don't sit through massive drawdowns for tiny profits", "author": "Austtinn", "timestamp": "2026-05-01T14:25:54", "channel": "trading-floor"},
    {"ticker": "NVDA", "direction": "long", "verdict": "good", "reason": "PDH reclaim on 5min with unusually high premarket volume (7M vs typical 1.5-3M) signaling institutional buying", "pnl": "N/A", "lesson": "High premarket volume signals institutional interest", "author": "Dice56", "timestamp": "2026-05-13T15:02:23", "channel": "trading-floor"},
    {"ticker": "NVDA", "direction": "long", "verdict": "bad", "reason": "Entered emotionally, got stopped out right before price bounced off PDH for big recovery", "pnl": "N/A", "lesson": "Don't trade emotionally — wait for setup to develop", "author": "JP400", "timestamp": "2026-05-13T21:05:16", "channel": "trading-floor"},
    {"ticker": "NVDA", "direction": "short", "verdict": "bad", "reason": "Looked decent but hit a daily wick zone causing chop instead of continuation", "pnl": "N/A", "lesson": "Avoid daily wick zones — they produce chop", "author": "Moe", "timestamp": "2026-05-15T18:18:24", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "short", "verdict": "bad", "reason": "Looked decent but hit a daily wick zone causing chop", "pnl": "N/A", "lesson": "N/A", "author": "Moe", "timestamp": "2026-05-15T18:18:24", "channel": "trading-floor"},
    {"ticker": "AMZN", "direction": "short", "verdict": "good", "reason": "Beautiful trade entry off previous day low (PDL)", "pnl": "N/A", "lesson": "N/A", "author": "LifeWithMikey", "timestamp": "2026-06-12T01:16:11", "channel": "trading-floor"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Beautiful trade, outlined in premarket prep, +$12K realized intraday plus trailers", "pnl": "+$12,000", "lesson": "N/A", "author": "Jdub", "timestamp": "2024-10-24T20:02:16", "channel": "jdub-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Clear mind after $6K drawdown week, open to both sides, made $16K", "pnl": "+$16,000", "lesson": "Reset mentally after losing week", "author": "Jdub", "timestamp": "2025-02-25T16:59:17", "channel": "jdub-alerts"},
    {"ticker": "MU", "direction": "unknown", "verdict": "bad", "reason": "Deep red in morning on MU trade", "pnl": "N/A", "lesson": "N/A", "author": "Jdub", "timestamp": "2026-01-29T16:36:38", "channel": "jdub-alerts"},
    {"ticker": "NVDA", "direction": "unknown", "verdict": "good", "reason": "Solid trade that turned day from deep red to green", "pnl": "N/A", "lesson": "N/A", "author": "Jdub", "timestamp": "2026-01-29T16:36:38", "channel": "jdub-alerts"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "good", "reason": "Solid trade that helped turn day from red to green", "pnl": "N/A", "lesson": "N/A", "author": "Jdub", "timestamp": "2026-01-29T16:36:38", "channel": "jdub-alerts"},
    {"ticker": "ES", "direction": "long", "verdict": "good", "reason": "Clean level bounce when NQ swept overnight lows — textbook setup", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2025-04-01T14:56:06", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "long", "verdict": "bad", "reason": "Chased the top on NQ and got smoked", "pnl": "N/A", "lesson": "Don't chase tops", "author": "MambaTrades", "timestamp": "2025-07-29T13:49:39", "channel": "futures-alerts"},
    {"ticker": "ES", "direction": "unknown", "verdict": "good", "reason": "Divergence setup between ES and NQ made good trade opportunity", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2025-09-15T13:57:49", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "unknown", "verdict": "good", "reason": "Divergence setup between ES and NQ made good trade opportunity", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2025-09-15T13:57:49", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "short", "verdict": "good", "reason": "Nice short to previous day low, caught 150 points for $5700", "pnl": "+$5,700", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2025-10-16T18:25:51", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "long", "verdict": "good", "reason": "Solid trade to hourly high at 25860", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2025-12-10T20:14:30", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "unknown", "verdict": "mixed", "reason": "Best trade on NQ that day but risky due to red folder news at the time", "pnl": "N/A", "lesson": "Be cautious around red folder news events", "author": "MambaTrades", "timestamp": "2026-01-06T14:58:21", "channel": "futures-alerts"},
])

# --- chunk 5 agent (44 reviews) ---
INLINE_BATCHES.append([
    {"ticker": "ES/NQ", "direction": "short", "verdict": "good", "reason": "Displacement was clear, made $4k on the short", "pnl": "+$4,000", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-02-03T15:18:45", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "short", "verdict": "good", "reason": "Inverse to previous day high was a solid trade setup", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-03-04T15:31:48", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "long", "verdict": "good", "reason": "Best trade so far, 5m gap bounce and displacement out", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-03-05T15:02:25", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "short", "verdict": "good", "reason": "2 best trades of day, 5m gap rejections and displacement", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-03-27T15:29:27", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "long", "verdict": "good", "reason": "Best trade, displacement, 1m gap bounce targeting PDH and daily gap", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-03-31T14:07:47", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "short", "verdict": "good", "reason": "Price respected 1hr bearish gap, solid short to the lows", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-04-28T15:51:59", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "short", "verdict": "good", "reason": "Best trade of day, sell setup to London lows", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-04-30T15:07:53", "channel": "futures-alerts"},
    {"ticker": "NQ", "direction": "unknown", "verdict": "mixed", "reason": "No great setups, only B-grade for eval accounts", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-05-05T15:08:25", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "long", "verdict": "good", "reason": "Solid trade to London highs of the 1m FVG", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-05-07T14:07:10", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "both", "verdict": "good", "reason": "Best setups: long to London lows and short to unfilled 4hr gap", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-05-12T14:46:20", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "unknown", "verdict": "good", "reason": "Solid trade setup that extended to 1:1 RR", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-05-19T14:21:03", "channel": "futures-alerts"},
    {"ticker": "ES/NQ", "direction": "short", "verdict": "good", "reason": "15m gap rejection with divergence targeting Asia lows, 1m gap continuation to PDL", "pnl": "N/A", "lesson": "N/A", "author": "MambaTrades", "timestamp": "2026-06-24T14:00:21", "channel": "futures-alerts"},
    {"ticker": "GOOG", "direction": "long", "verdict": "bad", "reason": "Stopped out, news messed up the 4h buy side liquidity thesis despite sound analysis", "pnl": "N/A", "lesson": "News can disrupt technical setups regardless of thesis quality", "author": "TonyMontana", "timestamp": "2024-04-04T19:00:16", "channel": "scarface-alerts"},
    {"ticker": "AMD", "direction": "long", "verdict": "good", "reason": "Laid out break/retest plan in premarket and executed simply — great trade", "pnl": "N/A", "lesson": "Have a plan and follow it", "author": "TonyMontana", "timestamp": "2024-07-05T14:08:22", "channel": "scarface-alerts"},
    {"ticker": "AMZN", "direction": "short", "verdict": "good", "reason": "Market dropping and AMZN was the best trade to the downside", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2024-08-02T14:16:26", "channel": "scarface-alerts"},
    {"ticker": "AMZN", "direction": "unknown", "verdict": "good", "reason": "Good move even without full displacement", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2024-08-28T13:45:45", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Higher probability day after earnings, used HOD scale to lock profits and let rest run", "pnl": "N/A", "lesson": "Use HOD scale to lock profits then let rest run", "author": "TonyMontana", "timestamp": "2024-10-24T18:59:11", "channel": "scarface-alerts"},
    {"ticker": "GOOGL", "direction": "unknown", "verdict": "mixed", "reason": "Same setup didn't work yesterday but ran nicely today — probabilistic outcomes", "pnl": "N/A", "lesson": "Good setup doesn't always work; don't abandon strategy after one loss", "author": "TonyMontana", "timestamp": "2025-01-31T15:00:51", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "bad", "reason": "Bigger loss than wanted, had thesis but trade played out against him", "pnl": "-$11,000", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2025-02-10T15:45:07", "channel": "scarface-alerts"},
    {"ticker": "AAPL", "direction": "unknown", "verdict": "mixed", "reason": "Good setup right into open with low risk but got stopped for small loss", "pnl": "small loss", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2025-03-11T13:36:42", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "mixed", "reason": "First trade lost -$2,900 because market conditions weren't ready (no SPY break). Second won after waiting for SPY break and re-entering with 84% rule.", "pnl": "-$2,900", "lesson": "Don't freak after loss, zoom out, wait for market confirmation, re-enter", "author": "TonyMontana", "timestamp": "2025-05-01T14:40:27", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "mixed", "reason": "Lost $20k on 3 swings combined but one TSLA swing made $90k+ — risk/reward worked out", "pnl": "+$70,000", "lesson": "Size down on swings, risk/reward works out if trade moves in timely manner", "author": "TonyMontana", "timestamp": "2025-05-21T19:05:21", "channel": "scarface-alerts"},
    {"ticker": "SPY", "direction": "unknown", "verdict": "mixed", "reason": "First one-candle rule trade worked, second 84% rule failed because choppy day", "pnl": "N/A", "lesson": "Market context matters for which setups work", "author": "TonyMontana", "timestamp": "2025-07-31T14:23:52", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Clear thesis TSLA was main focus, relative strength paid off, $60k in record time", "pnl": "+$60,000", "lesson": "Patience and focusing on strongest name pays off", "author": "TonyMontana", "timestamp": "2025-09-12T14:04:46", "channel": "scarface-alerts"},
    {"ticker": "AAPL", "direction": "unknown", "verdict": "good", "reason": "Solid trade achieving 9R multiple on trailers", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2025-09-16T14:10:52", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Perfect move to upside as outlined in premarket gameplan", "pnl": "N/A", "lesson": "Follow your premarket plan", "author": "TonyMontana", "timestamp": "2025-09-29T13:31:58", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "good", "reason": "Followed premarket plan, simple B&R strategy delivered 100%+ on Friday", "pnl": "+$40,000", "lesson": "Keep it simple: follow plan, focus on one name, execute the setup", "author": "TonyMontana", "timestamp": "2025-12-12T15:01:11", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "mixed", "reason": "Great trade but cut late — peaked $45k realized $32k because no continuation at ATH", "pnl": "+$32,000", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2025-12-17T18:47:15", "channel": "scarface-alerts"},
    {"ticker": "GOOGL", "direction": "unknown", "verdict": "good", "reason": "Straight from premarket gameplan, contracts moved nicely, done in 25 minutes on Friday", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-01-09T14:53:24", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "unknown", "verdict": "good", "reason": "Best trade of the day while everything else was untradeable", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-03-03T15:02:58", "channel": "scarface-alerts"},
    {"ticker": "AMD", "direction": "long", "verdict": "good", "reason": "Held through consolidation and it paid off", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-04-01T14:34:53", "channel": "scarface-alerts"},
    {"ticker": "QQQ", "direction": "unknown", "verdict": "bad", "reason": "Emotional mistake caused missing easy trade that would have made $30k+", "pnl": "+$2,700", "lesson": "Emotions can derail even experienced traders", "author": "TonyMontana", "timestamp": "2026-04-15T17:11:53", "channel": "scarface-alerts"},
    {"ticker": "NVDA", "direction": "long", "verdict": "good", "reason": "Main target (premarket high) hit, could scale there and let trailers ride into weekend", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-04-17T14:14:49", "channel": "scarface-alerts"},
    {"ticker": "PLTR", "direction": "unknown", "verdict": "good", "reason": "Great thesis was playing out, solid move", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-05-01T13:41:34", "channel": "scarface-alerts"},
    {"ticker": "MU", "direction": "unknown", "verdict": "good", "reason": "Textbook trade from entry to exit", "pnl": "N/A", "lesson": "N/A", "author": "TonyMontana", "timestamp": "2026-05-04T19:04:27", "channel": "scarface-alerts"},
    {"ticker": "TSLA", "direction": "long", "verdict": "mixed", "reason": "Not best entry for ATH breakout long swing but FOMO made it hard to sit out", "pnl": "N/A", "lesson": "N/A", "author": "mattyice", "timestamp": "2024-12-10T15:16:13", "channel": "swing-ideas"},
    {"ticker": "AAPL", "direction": "long", "verdict": "mixed", "reason": "Good swing but exited and switched to NVDA for better risk-reward given Tim Cook political risk under Trump", "pnl": "N/A", "lesson": "Monitor political/catalyst risk on individual positions", "author": "FierceTiger", "timestamp": "2025-05-18T17:03:49", "channel": "swing-ideas"},
    {"ticker": "AMZN", "direction": "long", "verdict": "good", "reason": "Scaled out 80% for nice quick swing profit", "pnl": "N/A", "lesson": "N/A", "author": "EeveeWinter", "timestamp": "2025-06-09T16:56:35", "channel": "swing-ideas"},
    {"ticker": "AMD", "direction": "long", "verdict": "good", "reason": "Good HTF thesis, sized to zero so could stay stress-free through weeks of drawdown, ended up 500%", "pnl": "+500%", "lesson": "Size to zero so you can hold through drawdown stress-free", "author": "Krypto_Greys", "timestamp": "2025-07-25T23:40:55", "channel": "swing-ideas"},
    {"ticker": "AMZN", "direction": "long", "verdict": "good", "reason": "Higher lows in outer liquidity realm, bounced from SMA 20 retest", "pnl": "N/A", "lesson": "N/A", "author": "305 Trader", "timestamp": "2025-09-18T01:17:04", "channel": "swing-ideas"},
    {"ticker": "QQQ", "direction": "long", "verdict": "good", "reason": "Pure uptrending sentiment", "pnl": "N/A", "lesson": "N/A", "author": "305 Trader", "timestamp": "2025-09-18T01:17:04", "channel": "swing-ideas"},
    {"ticker": "META", "direction": "unknown", "verdict": "mixed", "reason": "Trade looked good but sat too close to stop loss too long, worried about bounce off 760", "pnl": "N/A", "lesson": "N/A", "author": "Soopernoodle", "timestamp": "2025-09-24T20:01:52", "channel": "swing-ideas"},
    {"ticker": "AMD", "direction": "unknown", "verdict": "bad", "reason": "Exited early at small profit after being red many days, should have held per zero-value strategy", "pnl": "small profit", "lesson": "Don't exit swing early just because it's been red; trust thesis", "author": "305 Trader", "timestamp": "2025-10-02T13:39:01", "channel": "swing-ideas"},
    {"ticker": "QQQ", "direction": "short", "verdict": "good", "reason": "Well managed risk, never technically invalidated, good trade even though it took time", "pnl": "N/A", "lesson": "N/A", "author": "DWalt Trades", "timestamp": "2025-12-09T03:30:32", "channel": "backtesting"},
])

# --- chunk 0 agent (22 reviews) ---
INLINE_BATCHES.append([
    {"ticker": "AMD", "direction": "short", "verdict": "mixed", "reason": "Overextended entering short in a downtrend. Best entry at 167/PDH level. Trade management good but entry wrong.", "pnl": "N/A", "lesson": "Don't short when overextended. Wait for entry at key levels like PDH.", "author": "Jdub", "timestamp": "2024-05-29T20:20:06", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "long", "verdict": "mixed", "reason": "Good trade management but NVDA was not best name — TSLA, AMZN, AAPL had better relative strength that day.", "pnl": "N/A", "lesson": "Check relative strength across names before picking which to long.", "author": "Jdub", "timestamp": "2024-09-10T21:34:05", "channel": "trade-feedback"},
    {"ticker": "AAPL", "direction": "long", "verdict": "bad", "reason": "Low probability — volume and price action did not confirm going long.", "pnl": "-$small", "lesson": "Don't take long entries without volume and price confirmation.", "author": "BrokeAintNoJoke", "timestamp": "2025-01-07T21:40:15", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "short", "verdict": "mixed", "reason": "Not bad — would have worked but entry timing was late. By time premarket lows broke, most meat was off bone. AAPL was better setup.", "pnl": "N/A", "lesson": "Enter earlier or find better setups. Late entries leave profit on table.", "author": "Mar", "timestamp": "2025-01-10T23:53:39", "channel": "trade-feedback"},
    {"ticker": "AMD", "direction": "short", "verdict": "mixed", "reason": "Nice concept following NVDA PDL break, but should have taken partials on way to target. AMD had trouble hitting PDL.", "pnl": "N/A", "lesson": "Always take partials on way to target.", "author": "Luke", "timestamp": "2025-01-29T00:27:20", "channel": "trade-feedback"},
    {"ticker": "QQQ", "direction": "short", "verdict": "good", "reason": "After morning chop where BNRs failed, entered on clean break-and-retest of key level. Strong rejection confirmed trend. Scaled at TP1/TP2.", "pnl": "N/A", "lesson": "Wait through morning chop for clean setup. Scale out at targets.", "author": "Lauren (lakatrades)", "timestamp": "2025-03-06T18:58:32", "channel": "trade-feedback"},
    {"ticker": "MSFT", "direction": "long", "verdict": "good", "reason": "Strong BNR at 5-min ORH with clean break/retest. Momentum pushing to fill premarket gap. Managed exit on trendline break.", "pnl": "N/A", "lesson": "Clean BNR at ORH with gap-fill thesis is high-probability.", "author": "Lauren (lakatrades)", "timestamp": "2025-03-06T19:09:21", "channel": "trade-feedback"},
    {"ticker": "QQQ", "direction": "short", "verdict": "bad", "reason": "Setup looked perfect but was chop. 84% rule failed and didn't hit main target. Got stopped out.", "pnl": "N/A", "lesson": "Perfect-looking setups can be chop. Factor in time of day and market context.", "author": "DWC2016", "timestamp": "2025-03-07T03:38:23", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "long", "verdict": "bad", "reason": "Entered 84% rule but shouldn't have because first entry wasn't stopped out yet.", "pnl": "N/A", "lesson": "Don't enter re-entry if original position hasn't been invalidated.", "author": "Luke", "timestamp": "2025-04-28T16:46:59", "channel": "trade-feedback"},
    {"ticker": "PLTR", "direction": "unknown", "verdict": "bad", "reason": "Lousy trade — BnR with only 3/5 confidence. -1R loss.", "pnl": "-1R", "lesson": "Don't take trades when entry confidence is low.", "author": "Kam", "timestamp": "2025-06-26T19:52:29", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "unknown", "verdict": "mixed", "reason": "Good setups but market structure changed causing three consecutive stop-outs.", "pnl": "N/A", "lesson": "Good setups lose when market structure shifts. Adapt sizing or step back.", "author": "neverBackDown", "timestamp": "2025-07-09T15:42:01", "channel": "trade-feedback"},
    {"ticker": "AAPL", "direction": "long", "verdict": "good", "reason": "Good trade — one candle rule retest and internal liquidity break. AAPL lost momentum but setup was correct.", "pnl": "N/A", "lesson": "Trade can be good even when it loses. Focus on setup and execution.", "author": "Nathan", "timestamp": "2025-07-21T15:33:49", "channel": "trade-feedback"},
    {"ticker": "AAPL", "direction": "long", "verdict": "mixed", "reason": "Felt good about 84% rule entry because indices held and momentum was strong, but AAPL died after reclaim and retest.", "pnl": "N/A", "lesson": "Strong entry doesn't guarantee continuation. Watch momentum after initial pop.", "author": "DSmith", "timestamp": "2025-07-21T15:48:18", "channel": "trade-feedback"},
    {"ticker": "NVDA", "direction": "long", "verdict": "mixed", "reason": "Good loser — solid setup with PMH/ATH retest and fib targets but stopped out. Process and risk management correct.", "pnl": "N/A", "lesson": "Judge trades by process, not outcome.", "author": "Dcrouth21", "timestamp": "2025-07-25T15:06:46", "channel": "trade-feedback"},
    {"ticker": "PLTR", "direction": "long", "verdict": "good", "reason": "Planned gap-fill entry before open, PLTR showed relative strength. Captured cleanly despite fast movement.", "pnl": "N/A", "lesson": "Plan entries before open; use relative strength to confirm bias.", "author": "Royal191", "timestamp": "2025-08-20T13:02:11", "channel": "trade-feedback"},
    {"ticker": "ORCL", "direction": "short", "verdict": "good", "reason": "Short targeting gap fill after confirming HTF structure break. Light size, banked $1,000.", "pnl": "+$1,000", "lesson": "Confirm HTF structure break. Size down when catalyst risk present.", "author": "FierceTiger", "timestamp": "2025-09-17T04:44:50", "channel": "trade-feedback"},
    {"ticker": "ORCL", "direction": "short", "verdict": "mixed", "reason": "Perfect entry in hindsight was first red candle after PM high broke, but TikTok news made cautious approach correct.", "pnl": "N/A", "lesson": "News justifies extra caution even if you miss textbook entry.", "author": "FierceTiger", "timestamp": "2025-09-17T04:47:09", "channel": "trade-feedback"},
    {"ticker": "PLTR", "direction": "long", "verdict": "bad", "reason": "FOMO entry when already overextended. Lost $84.", "pnl": "-$84", "lesson": "Never FOMO into overextended move.", "author": "Anne", "timestamp": "2025-09-19T15:25:03", "channel": "trade-feedback"},
    {"ticker": "PLTR", "direction": "long", "verdict": "mixed", "reason": "Setup not bad on 5min but buying 0DTE ruined trade management.", "pnl": "N/A", "lesson": "Match instrument to timeframe. 0DTE cannot be managed on 5min chart.", "author": "Anne", "timestamp": "2025-09-20T03:07:14", "channel": "trade-feedback"},
    {"ticker": "PLTR", "direction": "long", "verdict": "mixed", "reason": "Good thesis at HTF key support but cut too early before it worked out.", "pnl": "N/A", "lesson": "When HTF supports thesis, give trade room to breathe.", "author": "Kash", "timestamp": "2025-11-05T17:33:30", "channel": "trade-feedback"},
    {"ticker": "QQQ", "direction": "short", "verdict": "bad", "reason": "Didn't feel right but took it anyway. Didn't trim at LOD, got hit by huge green candle.", "pnl": "N/A", "lesson": "Trust gut. If it doesn't feel right, don't take it. Trim partials at targets.", "author": "Jay_aye11", "timestamp": "2025-12-16T17:36:58", "channel": "trade-feedback"},
    {"ticker": "AMD", "direction": "long", "verdict": "mixed", "reason": "Sold way too early but accepting early exit because trade could have reversed.", "pnl": "N/A", "lesson": "Don't beat yourself up over early exits. Focus on process.", "author": "Huy", "timestamp": "2026-01-21T16:19:10", "channel": "trade-feedback"},
])

def main():
    all_reviews = []
    for batch in INLINE_BATCHES:
        all_reviews.extend(batch)

    # Also read written files
    written_files = [
        BASE / "trade_reviews_output.json",
        BASE / "_trade_reviews_3.json",
    ]
    for f in written_files:
        if f.exists():
            with open(f, encoding='utf-8') as fh:
                data = json.load(fh)
            if "tradeReviews" in data:
                all_reviews.extend(data["tradeReviews"])
            elif isinstance(data, list):
                all_reviews.extend(data)

    # De-duplicate by (author, timestamp, ticker, channel)
    seen = set()
    deduped = []
    for r in all_reviews:
        key = (r.get("author",""), r.get("timestamp",""), r.get("ticker",""), r.get("channel",""))
        if key not in seen:
            seen.add(key)
            deduped.append(r)
    all_reviews = deduped

    # Normalize ticker
    ticker_counts = Counter()
    verdict_counts = Counter()
    direction_counts = Counter()
    author_counts = Counter()
    channel_counts = Counter()
    by_ticker = defaultdict(lambda: Counter())

    for r in all_reviews:
        t = r.get("ticker", "N/A").upper().replace("/", "-")
        r["ticker"] = t
        ticker_counts[t] += 1
        verdict_counts[r.get("verdict", "unknown")] += 1
        direction_counts[r.get("direction", "unknown")] += 1
        author_counts[r.get("author", "?")] += 1
        channel_counts[r.get("channel", "?")] += 1
        by_ticker[t][r.get("verdict", "unknown")] += 1

    # Build summary
    top_tickers = ticker_counts.most_common(25)
    top_authors = author_counts.most_common(15)
    top_channels = channel_counts.most_common(20)

    output = {
        "summary": {
            "total_reviews": len(all_reviews),
            "by_verdict": dict(verdict_counts),
            "by_direction": dict(direction_counts),
            "top_tickers": [(t, dict(by_ticker[t]), c) for t, c in top_tickers],
            "top_authors": top_authors,
            "top_channels": top_channels,
            "date_range": {
                "earliest": min((r.get("timestamp","") for r in all_reviews if r.get("timestamp")), default=""),
                "latest": max((r.get("timestamp","") for r in all_reviews if r.get("timestamp")), default=""),
            }
        },
        "reviews": all_reviews,
    }

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Total reviews: {len(all_reviews)}")
    print(f"Good: {verdict_counts.get('good',0)}, Bad: {verdict_counts.get('bad',0)}, Mixed: {verdict_counts.get('mixed',0)}")
    print(f"\nTop 15 tickers:")
    for t, c in top_tickers:
        v = by_ticker[t]
        print(f"  {t}: {c} total ({v.get('good',0)}G/{v.get('bad',0)}B/{v.get('mixed',0)}M)")
    print(f"\nTop authors:")
    for a, c in top_authors:
        print(f"  {a}: {c}")
    print(f"\nTop channels:")
    for ch, c in top_channels:
        print(f"  {ch}: {c}")
    print(f"\nDate range: {output['summary']['date_range']['earliest']} to {output['summary']['date_range']['latest']}")
    print(f"\nOutput: {OUT}")

if __name__ == "__main__":
    main()
