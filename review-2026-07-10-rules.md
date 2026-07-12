# Austin review 2026-07-10 (v5-green artifact, 13 trades) — extracted rules

Verdict: B&R "definitely the best understood." OCR trades 2026-01-14 + 2026-03-20 = "first understanding of the one candle rule I've seen" / "looks great." Hallucination rate way down from 80%.

## Per-trade
| Trade | Verdict | Rule extracted |
|---|---|---|
| 07-30 TSLA B&R B SHORT | no | Level (ORL) already broken w/ immediate retests earlier → dirty level. Also long lower wick on entry candle = bad short entry. |
| 09-05 TSLA B&R A LONG | YES (would take) | Break→displacement→hammer wick touch = textbook. Mgmt: scale HOD / breakeven at post-entry red OB. |
| 10-08 TSLA B&R B SHORT | no | Already below ORL before setup; entry candle bearish but unclear if TOUCHING level — retest must touch. Wants CLEAN look, no previous breaks ("start at the beginning of the day"). |
| 10-09 TSLA B&R B SHORT | no | Broke PML but CLOSED ABOVE it (wick break ≠ break). Entered on weak-PA candle w/ lower wick. Alt read: green candles as OBs → short off OB retest. |
| 11-04 TSLA B&R B LONG | no | Break candle 1 ok but candle 2 closed AT the level → no clear break/displacement. Marginal clears don't count. |
| 11-07 TSLA B&R A SHORT | YES | Below all levels, clean weak-PA break, displacement, tight clear stop. "Can't win them all." |
| 11-06 TSLA B&R B LONG | no | Level already broken w/ immediate retest/quick rejection earlier → don't re-enter (unless armed 84% roll). Visually J-Dub-ish though. |
| 11-21 TSLA B&R B SHORT | YES | Below all levels, 2 bearish candles, 3 green pullback, hammer closes at PML, next candle weak = entry. |
| 12-15 TSLA B&R A LONG | YES-ish | Would classify as OB trade: break ORH, 2 red candles (2nd closed below = break-and-reject), but red candle 5-back = OB → B&R of OB. Stop at OB bottom (wider, harder 2R). "I like what the bot is seeing." |
| 11-07 TSLA OCR A SHORT | YES | Break-displacement-retest w/ weak PA. Stop at OB fine, tighter option = close above ORL. |
| 2026-01-14 TSLA OCR A SHORT | YES (loss ok) | First clear OCR: visible one-candle + stop matches it. Many candles between but acceptable. Below all levels = bearish context. |
| 2026-03-20 TSLA OCR A SHORT | YES (best) | Fewer candles, OB clearly seen, stop clear, weak-PA entry "beautiful." |

## New rules to encode
1. **CLEAN-FIRST-BREAK** (biggest theme: 07-30, 10-08, 11-06, brain dump): if level was already broken earlier in session (break + immediate retest / rejection) before our sequence, entry is "late/dirty" → downgrade (keep in data, A/B test win rates clean vs late). "We like to start at the beginning of the day, without any previous breaks." Exception: armed 84% re-entry.
2. **ENTRY WICK QUALITY**: short entry candle with long lower wick = bad (07-30, 10-09); mirror long w/ upper wick. Downgrade/reject.
3. **CLOSE-THROUGH BREAK** already enforced (10-09 confirms need); keep strict.
4. **MARGINAL CLEAR ≠ DISPLACEMENT** (11-04): close AT level or clear by hair doesn't count. Add displacement buffer.
5. **RETEST MUST TOUCH** the level (10-08).
6. OCR shape confirmed working — keep geometry, current examples good.

## Brain dump directives (overnight loop)
- Reviews like this = his time poorly spent going forward; use transcripts/videos/subagents for ideology questions.
- Goal unchanged: out of alpha → 55% win / $30k-mo backtest, THEN whittle to best-setup selection for live.
- Keep late entries in test data if useful, but he dislikes them.
- Not overtrade; all data, every setup, no hallucinations.
- Research Vanquish Trader platform (his execution venue). Account = **$7,500 drawdown**. Original plan $2k risk/$1k loss; consider $1.5k if risk-of-ruin (P of 5 losing days killing account) acceptable. Model odds; maybe sub-agent + Obsidian check (done: options prop, no API, one account only).
- Live real-time execution = future challenge.

## Today's live examples (2026-07-10 screenshots, 2W 1L)
- MSFT 1m: short zone ~376.5-377.7 (red box above), green zone below to ~375.9 — ORL/PDH area trade after 9:30 pop.
- GOOGL 1m: short ~358 (PDH/PMH cluster 357.77-358.03), ran to ~354 = winner.
- NVDA 1m: short ~202.3 (ORL retest under PML 202.37), ran to 199 = winner.
