# Scarface / J-Dub Canonical Rules — Accelerator Course (all 29 transcripts, extracted 2026-07-11)

Source: `circle_data\transcripts\the-accelerator-course_*.vtt`, read in full by 5 extraction agents.
Every rule is backed by a verbatim quote + (file, timestamp). "NOT COVERED" = never taught in this source.
**Masterminds (28 files), coaching/bonus (44 files), YouTube (~1300) NOT yet extracted — see deepseek-extraction-spec.md.**

---

## HEADLINE FINDINGS (for the hallucination audit)

1. **"OCR" may be a naming hallucination.** The course never says "one candle rule." The recurring pattern is **"opening candle retest" / "opening candle print"** — retest of the FIRST 1-min candle's range (1450449 [00:25:00], 1450414 [00:31:42]). Verify what our `one_candle_rule` detector actually should be. (Could still be named in masterminds — pending.)
2. **84% rule = SAME size (1×), same setup, same conditions, same stop/targets.** "If I'm risking a thousand dollars on the first trade, I'm gonna risk a thousand dollars on the second trade" (1450449 [00:27:18]). Requires exact-same A-quality setup + confluences; "multiple touches" / broke-structure / no-displacement DISQUALIFY re-entry (1450449 [00:29:09-31:21]). Our 2×-sizing bug fix was correct; our rr-gate is an extra we added.
3. **Targets are LIQUIDITY LEVELS, not blind 2R.** First target = HOD/LOD ("exit some at high of day every single time" 1450421 [00:18:35]), then next draw of liquidity: PDH/PDL, old highs/lows, gap fill, all-time high (1450477 [00:14:14], 1450449 [00:48:01]). 2:1 is the MINIMUM aggregate R:R expectation, not the exit mechanism.
4. **Breakeven rule is conditional:** move stop to BE only AFTER first profit target hits; "you can't move your stop loss to break even if it doesn't hit first profit target — let the trade breathe" (1450449 [00:54:17]). Then trail stop to each hit target. Our backtest "BE at 1R" variants tested a different (stricter) rule than taught.
5. **Break validity = BODIES close through, wicks don't count.** "The wicks do the damage, bodies tell the story" (1450664 [00:04:34]). Displacement required ("strong candle closure," "impulsive move"). Invalidation = close back through level (1450449 [00:56:06]). Levels are ZONES, not ticks (1450660 [00:09:54]).
6. **Trade count: 1-2/day, 3 absolute max** (1450540 [00:17:01]). A+ setups come 1-2×/MONTH (hot markets 1-2×/week) and take max risk; scalps take low risk (1450562, 1450720).
7. **Win-rate math taught:** 40-50%W at 2:1 = profitable; instructor claims ~50%W, 2-3:1 (1450562 [00:13:11], 1450414 [00:27:46]). Our 55% target is ABOVE what the course itself promises.
8. **Time:** trade 9:30–11:00 ET only; 1-min chart valid only in that window (5-min after); Tue–Thu best days; skip FOMC/red-folder days (1450547, 1450609, 1450346, 1450414).

---

## 1. Break-and-retest (core setup)

**Break:**
- Impulsive move / displacement required: "we have our breakout above this resistance line, and then we have a push higher" (1450660 [00:07:30]); "strong candle closure below pre market low" (1450449 [00:24:42]); "As long as we break above with strong displacement... we can use this pre market high as a retest level" (1450660 [00:25:45]).
- Bodies not wicks: "Tries wicking right here... but the very next subsequent candle... very strong 5 minute candle closure... creates a displacement" (1450660 [00:24:29]); "sellers... wick it above, but... push price back down below this key resistance level" (1450664 [00:04:54]).
- No-displacement = no trade: "Really no displacement right here. So not really the greatest trade... it's just wicking around" (1450449 [00:57:55]).

**Retest & entry:**
- Never enter the breakout, only the retest: "We enter the stock on the retest... if we entered into the stock here [breakout] we would have got stopped out" (1450665 [00:03:10]); "We trade the retest because it gives us a higher probability trade with lower risk... it actually held above the level" (1450665 [00:03:33]).
- Entry trigger = strong confirmation candle at the level: hammer (long) / shooting star (short): "This first candle wasn't strong enough, but the second candle, strong hammer candle... We enter in on that level" (1450477 [00:20:10]); "we retested right here with a very weak shooting star candle... we made a strong displacement and then we retested that level. Therefore, we could enter" (1450627 [00:19:57]).
- Wick-under-body-close-above = buyers stepping in (1450689 [00:15:54]).
- Entry timing: "the entry was a close after this candle closed" (1450609 [00:14:03]). Entries can be fleeting — 1 minute (1450378 [00:11:00]).
- HTF confluence wanted: "flag pattern breaks on the 4 hour" (1450477 [00:05:01]); same pattern on 4h + 1m = more emphasis (1450477 [00:30:41]).

**Stop:**
- At break of market structure / the displacement candle / below order block: "your stop loss will always be at a break in structure" (1450477 [00:10:58]); "at the break of the displacement candle" or aggressive = break of entry candle where setup invalidates (1450477 [00:20:29]); "stop loss can simply be below this order block" (1450421 [00:17:49]).
- Early-day PMH/PML trades: stop often = low of day (1450477 [00:10:58]).

**Targets:**
- First = HOD/LOD, then PDH/PDL / old highs-lows / gap fill / ATH (external liquidity): 1450477 [00:04:20], [00:14:14]; 1450449 [00:53:32].
- Only exit at stop or target — in-between is noise; no time-based exits (1450609 [00:13:20]). Counter-quote: momentum trades should "work right away within like 10, 15 minutes" or likely stopped (1450449 [00:58:37]).

**Setup family (playbook):** PMH/PML retest, 5-min opening range break-retest, 1-min opening candle retest, gap fill, opening drive, inside bar, order-block retest, PDH/PDL retest, HOD retest (1450720 [00:03:58], 1450421 [00:25:20], 1450378 [00:17:12]).
- First understanding: choppy market needs MORE confluence (OB + HOD retest); strong momentum market HOD retest alone OK (1450421 [00:25:59]).

## 2. "One candle rule"
NOT NAMED anywhere in 29 files. Only "opening candle retest"/"opening candle print" = retest of first 1-min candle high/low (1450449 [00:25:00-25:20]: "third candle... we see a rejection. That's where we look to enter, right, with stops just to break above"). "OCR" appears once = One-Cancels-Another broker order type (1450486 [00:25:16]). → Check masterminds; else our OCR detector needs re-grounding on opening-candle-retest spec.

## 3. 84% rule
- Statistical claim: same setup, same conditions → works 84% of the time on re-entry (1450449 [00:23:31]).
- Requirements: EXACT same setup + same stop + same targets + confluences + HTF alignment + relative strength/weakness; A-quality only (1450449 [00:23:31], [00:26:16]).
- Sizing: SAME size, never bigger (1450449 [00:27:18-28:25]).
- Disqualified when: broke structure the other way, no displacement, multiple touches, weak/no confluences (1450449 [00:29:09-31:21]).
- Psychology framing: stop loss always taken first; re-entry is separate decision (1450540 [00:16:25]).

## 4. Order blocks
- Definition: down-close candle in uptrend / up-close candle in downtrend; acts as S/R (1450660 [00:12:43]).
- Draw from wick to body ("from the wick, you can draw it to the body," top of wick to top/bottom of body) (1450660 [00:28:02], [00:30:39]).
- Best OBs coincide with key levels + displacement + FVG + break-retest = confluence (1450660 [00:27:40]). Work best in TRENDING markets (1450660 [00:32:07]).
- Uses: entry zone, stop reference (below OB), trailing stop anchor (move stop OB-to-OB as trade runs, 1450449 [01:02:10]).

## 5. Key levels
- Top-down: weekly → daily → 1h → 5m; HTF levels dominate (1450660 [00:20:19], 1450609 [00:06:30]).
- Levels are zones, not ticks (1450609 [00:09:54]).
- PM levels: mark 4:00–9:30am; "majority of people trading the New York session are going to look at that pre market high and low" (1450477 [00:01:43], [00:03:44]). 4 setups off PMH/PML: reversal or continuation at each, depending on HTF (1450477 [00:07:00]).
- Opening range: 1-min (9:30-9:31) and 5-min (9:30-9:35) candle high/low; higher timeframe break = stronger (1450477 [00:02:11], [00:13:19]).
- Gap fill = prev close → today open; next draw on liquidity (1450477 [00:22:07]).
- Liquidity: stops rest above old highs/below old lows; equal highs/lows (2-3 touches) = liquidity pools; psych whole numbers matter (1450660, 1450664). "Look left" for targets (1450664 [00:12:41]).

## 6. Time-of-day
- 9:30–11:00 ET trade window; most volatility/money there (1450547 [00:18:24], [00:19:22]; 1450378 [00:13:23]).
- 1-min chart only until 11:00; after that 5-min (too much noise) (1450609 [00:02:30]).
- Tue–Thu statistically best; Monday/Friday avoided (1450547 [00:17:54]).
- Skip FOMC and heavy red-folder-news days, or wait until after release; 8:30am ET = red folder time; 10am reversals common (1450346 [00:13:38], 1450414 [00:23:19-24:28]).

## 7. Exits / trade management
- ALWAYS scale some at HOD/LOD ("lock in cash flow"), then trail rest to liquidity targets (1450540 [00:13:59], 1450421 [00:18:35], 1450562 [00:20:11]).
- Scaling styles: Tony ~80% at first target; J-Dub quarters (25% increments), leaves ~10% trailers (1450449 [00:39:03], 1450547 [00:14:47]).
- BE only after TP1 hits; then stop ratchets to each hit target (1450449 [00:53:51-54:42], [00:45:16]).
- 4-outcomes rule: big win / small win / breakeven / small loss — NEVER big loss (1450449 [00:31:46]).
- Options stops: 10-15% contract loss on scalps, 30-50% wiggle for swings; mental stops, wait for candle CLOSE (1450581 [00:14:37], 1450540 [00:15:46]).
- Avg winner held 39 min, avg loser cut in 8 min (1450547 [00:15:13]).
- Discretionary exits allowed for news/chop (1450449 [00:46:03]).

## 8. Higher-timeframe / swing B&R (Austin's question)
- Explicit: "every single strategy that I talked about so far, you could make it a swing strategy" (1450477 [00:36:40]).
- Top-down: weekly bias → daily/4h pattern (flags, OBs) → 1m/5m entry on retest; "capture higher time frame breakouts... go into the lower time frames to find those nice entries" (1450378 [00:01:10], 1450609 [00:05:50]).
- Inside-bar daily setup = the flagship swing play: enter intraday on break+retest of the daily inside bar, scale at HOD, trailer stop at inside-bar low, min 2:1; intraday 30-40% option gain can be 3-500% swung (1450477 [00:35:48-37:37]).
- A+ HTF setups = 1-2/month, multi-day runners, where most money is made; day-trades in between ≈ staying afloat (1450378 [00:03:00]).
- Swing sizing: smaller size, wider stops (30-50% contract), hold into drawdown (1450421 [00:16:44], 1450565 [00:09:04]).
- Weekly close = directional bias input (1450609 [00:05:02]).

## 9. Selection / discipline
- 1-2 trades/day (3 hard max); both losers = choppy day, stop (1450540 [00:17:01], 1450378 [00:06:22]).
- Size by grade: A+ = max risk; scalp/0DTE = low; "low quality setup, half risk, or no trade" (1450421 [00:25:03], 1450562 [00:20:52]).
- A+ = "when everything aligns" — HTF + level + displacement + confluences (1450720 [00:12:15]).
- Backtest without discretion: take EVERY trade matching criteria (1450721 [00:09:45]). One strategy at a time (1450721 [00:07:41]).
- Journal 3 questions: in system? take again? right size? (1450583 [00:12:48]).
- Stats-derived personal rules example: Tue-Thu only, 9:30-11, contracts >$2, Tesla/NQ focus, <$500 risk/trade (1450547 [00:23:24]).
- Risk: ≤1% of account per trade; new traders max daily loss $100; 10-15% account drawdown normal (1450421, 1450565).

## 10. Instruments / execution details
- Mega caps only for day trades (TSLA NVDA AMD AAPL META); ES/NQ futures; no SPX in course materials reviewed.
- Options: 1 OTM strike, weekly (1DTE+) not 0DTE, volume >1000, IV <60-70, enter on ask, limit orders, 1-3 contracts learning (1450404).
- Indicators: price action first; 9/21 EMA + VWAP only; "no calls under VWAP, no puts above VWAP" for beginners; EMA 9/21 crossover = reversal cue; fib golden pocket 50-61.8% (1450693, 1450464).

## Ambiguities / gaps (for masterminds extraction)
- "One candle rule" naming + exact spec — absent here.
- Exact displacement threshold (how big is "strong") — qualitative only.
- Retest: must it TOUCH the level or just come near zone? (zones language suggests zone-touch OK).
- LATE/first-break-of-day preference — not explicit in course (Austin's rule; masterminds may cover).
- Max wait time for retest after break — not stated.
