# Scarface / J-Dub Trading Rules — YouTube Transcript Extraction (558 files → top 100)

**Extracted 2026-07-13** from `youtube_data/*_transcript.txt` — YouTube livestreams, trade reviews, and coaching sessions.
558 total files → ranked by relevance → **top 100 extracted**. Remaining 458 listed as skipped.

**Source:** `research/youtube_batches/batch_001–019.md` (existing per-topic extraction of all 558 files).
**This document:** consolidates top 100 most relevant YouTube transcripts into canonical rulebook format.

Every rule backed by verbatim quote + (filename, timestamp). "NOT COVERED" = never appeared in sources queried.

---

## HEADLINE FINDINGS (YouTube vs prior rulebooks)

### 1. "ONE CANDLE RULE" naming CONFIRMED in YouTube content — B1 finding #1 partially wrong
B1 concluded OCR name only appeared in accelerator course. **False.** YouTube live sessions use "one candle rule" naming:
- "we wanted to come into the five minute high plus this one candle rule" (7auleEXxAz8, 910s)
- "candle closure below the one candle rule" (7auleEXxAz8, 3046s)
- "The one candle rule Is basically an order block" (AjdBNs8qY7c, 2507s)

OCR ≡ OB equation confirmed across BOTH course and YouTube sources.

### 2. 84% rule: reclaim-based entry, NOT retest-based (new operational detail)
YouTube content is unambiguous: "if you take the 84%, you really honestly don't want to see a retest. You kind of just want to see a reclaim of the key level and then bring it back towards the upside" (c4uNJYskLL4, 3148s). Must wait for candle close above key area — wick above not sufficient (lOKLMktXgY8, 1390s). This conflicts with Omen's RULE84_LESSON firing on close of reclaim candle (Omen does reclaim close, not retest — Omen is correct, matches YouTube source).

### 3. 84% rule: "thesis not broken" invalidation gate (new constraint)
"If the 84% rule is invalidated only if it doesn't break your thesis the first time... if you entered on the 84% rule doesn't really count because it never broke structure to begin with" (7kajZjCStT8, 1298s). If first exit was premature (thesis intact), re-entry isn't an 84% rule — it's just re-entering the same trade. Not coded in Omen.

### 4. 84% rule: multiple tries allowed (no hard 1-and-done)
"sometimes it might take a couple tries... as long as it doesn't invalidate your thesis you can take it a couple of tries" (Mta32jhu44s, 5211s). Omen's single-attempt 84% matches the loose variant; course rulebook says never re-enter after a second failure. This video source allows multiple attempts within the same thesis.

### 5. "84 to the 84" = choppy market diagnostic
"When it's like an 84 to the 84 that just means it's going to be a little bit more consolidation... two or three of the same setups kind of occur that just means it's going to be more of a choppy day" (Se_P4N3u48o, 3095s). If the 84% setup triggers twice in one day, it's a signal to reduce size/stop trading, not re-enter. Not documented in any prior rulebook.

### 6. Stop-after-win: CLOSEST source yet found (still informal)
"if you take one good trade in a day, turn off the computer, turn it off, walk away" (beilNB6V3lM, 2419s). Also: FOMO cessation = "close the screen and take the rest of the day off" (T8leSPV4i7o, 3760s). These are the closest citations found across ALL 558 transcripts. **Still not a hard rule** — more a personal discipline guideline. config.yaml stop_after_win=true remains OURS, not source-mandated. B1 verdict unchanged.

### 7. 0DTE option rules (NEW — no prior rulebook coverage)
YouTube content has extensive 0DTE-specific guidance:
- **New traders should NEVER trade 0DTE**: use next-week contracts to avoid theta decay (_Em7Q3lyrDg, 26s)
- **0DTE must work immediately**: "if you're playing zero days, it basically has to go right away" (4NxKb-yOKxU, 2024s)
- **Fridays: avoid 0DTE after 11am** (AH2mmePrFsE, 3247s)
- **Scaled exits: 80-90% off at key levels** for 0DTE (9te7G9JT1rw, 4183s)
- **Scale on the way up, NOT down** with 0DTE (cfwZUw2UqtQ, 1257s; JQajuUzTn6g, 2342s)
- **Gamma power**: 20% tail can make more than 80% main due to deep ITM gamma (pFjKYfYfP2Tg, 6419s)

Omen's SCARFACE_CONTRACT (D1) uses weekly expiry by default. YouTube sources strongly confirm this preference.

### 8. Inside bars as liquidity indicator (NEW pattern)
"I'll use inside bars on the daily chart... If the inside bar, right? That means we haven't taken out liquidity... that means there's a lot of built up liquidity. So whenever you have an inside bar day... a lot of the times the next day will end up having a nice momentum" (4l9AW30-i1o, 3606s). Not coded in Omen. Not in prior rulebooks.

### 9. Morning star / three-candle reversal pattern (NEW)
"I use your three candle morning star reversal strategy... where there's higher time frame higher highs higher lows... that's all you need to get over 80 percent" (p6tEcbCsfjs, 4660s). Mentioned once in YouTube, zero times in course materials. Low-confidence inclusion.

### 10. External vs internal liquidity targeting (refines entry logic)
"our best trades really come from previous day highs and previous day lows" — target EXTERNAL liquidity, not internal range levels (tr_ywYlRvvw, 4362s). If a trade doesn't target external liquidity, "it's not worth taking" (qyDCEwko494, 4419s). This matches Omen's PDH/PDL level targeting but adds a stronger filter.

### 11. Bar-by-bar exit method (NEW — not coded)
"if you're going long on a trade... if you get one big red candle that breaks below the previous green candles low... that's technically the bar by bar and that's where you'd stop out" (qjItmSl400E, 3538s). Used for trailing/final exit after scaling. Not equivalent to Omen's fixed-stop or breakeven.

### 12. 1-2 quality trades/day CONFIRMED across multiple sources
Multiple videos confirm: "I try to focus on the quality of trade every single day, and therefore I only take one to two trades" (multiple sources). "One to two A+ setup trades can make your whole month." Omen's max-2/day tier rule is CONFIRMED by YouTube sources (was previously only in course rulebook). Stop-after-win still separate.

### 13. Win rate claims: 60% long-term (YouTube) vs 50-65% (course)
YouTube trader: "I always say that my win rate is around that 60 mark overall long term" (0QyuYNDoKpY, 155s). Supports the upper end of the course's 50-65% range. Monthly win rate fluctuates 33-60%+.

### 14. Quality > quantity: most profit comes from ~1 month/year
"The majority of the profits that I make during the year come from like a one month really hot span... I'll size up right and we'll have a super hot span or whatever and then right we'll size back down" ( -_dz8WqgRB8, 4728s). This behavioral pattern supports the tier's focus on high-conviction windows.

---

## TOPIC EXTRACTION (consolidated from top 100 YouTube transcripts)

### 1. Break-and-retest (core setup)

- Core definition: break of key level (pre-market high, PDH/PDL, order block, opening candle print) followed by retest for entry. "Very simple break and retest of the pre-market high plus order blocks, right?" ( -_Q_BlPhjhU, 396s)
- Immediate retest on 1-min timeframe counts as valid: "This is technically a retest right It's like an immediate retest right based off the one minute time frame but it still technically counts as a retest" ( -k6ayIaeOzs, 2158s)
- Best entries: level break + strong displacement + confirming candle (e.g., hammer): "the best entry on meta now would be waiting until we break this range or this high of day... retest that" ( -_dz8WqgRB8, 2818s)
- Failed retest: first candle closes below level → wait for second cleaner retest
- 10-15 different B&R subtypes within the system: "order block retest, opening range break retest... about 10 to 15 different types of break and retest actual setups" (0z6KAobsuoX, 3344s)
- Common mistake: entering preemptively before retest occurs
- Break-and-retest works best in trending/continuation markets, not chop or reversals (u9pFlMU2iZM, 5178s)
- Best B&R trades target external liquidity (PDH/PDL), not internal range levels (tr_ywYlRvvw, 4362s)
- Break of momentum can be a valid stop even if structure not broken — "our stop loss will just be at the break of momentum rather than break of structure" (multiple sources)

**NOT COVERED in YouTube content:** displacement size quantification (exact %), maximum wait time for retest, first-break-of-day vs later-break treatment (referenced but no hard rule).

### 2. "One candle rule" / opening candle retest

- The opening candle print (first 1-min or 5-min candle) is a critical intraday level for the first retest: "retest opening candle print and then move towards upside" ( -k6ayIaeOzs, 180s)
- Opening range break & retest is a standard setup: "That's technically the opening range break retest" ( -k6ayIaeOzs, 315s)
- Opening candle print used as profit target: "first target was this opening candle print first target opening candle print second target That our pre-market high" (0mUVcHm9WXs, 645s)
- Opening candle print as strength/weakness gauge
- **"One candle rule" naming CONFIRMED in YouTube live sessions**: "the five minute high plus this one candle rule" (7auleEXxAz8, 910s); "one candle rule Is basically an order block" (AjdBNs8qY7c, 2507s); "candle closure below the one candle rule" (7auleEXxAz8, 3046s)
- The opening drive play: market sweeps key level, V-shape recovery, retests opening candle print ( -_dz8WqgRB8, 3583s)
- Opening drive is a specific play-type distinct from standard B&R
- "One candle rule" used as last line of defense: "candle closure below the one candle rule that last level defense" (7auleEXxAz8, 3046s)

### 3. 84% rule / re-entries

- Core definition: re-taking the same trade after a stop-out when thesis remains intact. "If I take a trade I really like it. I stop out but it's still intact then I'm going to be looking for the reclaim and 84 percent rule" (AjdBNs8qY7c, 1138s)
- **Requires trending market (SPY/QQQ).** Not applicable in chop: "Meta doesn't fall into the 84 percent rule because the market's not trending" ( -_dz8WqgRB8, 3173s)
- **Entry = reclaim close, not retest.** "if you take the 84%, you really honestly don't want to see a retest. You kind of just want to see a reclaim of the key level" (c4uNJYskLL4, 3148s)
- Must wait for candle to close above key area — wick above not sufficient (lOKLMktXgY8, 1390s)
- "The 84% rule is taking the same trade essentially twice" (cgUoqp8243I, 1971s)
- **Invalidation condition (NEW):** "The 84% rule is invalidated if it doesn't break your thesis the first time... if you entered on the 84% rule doesn't really count because it never broke structure to begin with" (7kajZjCStT8, 1298s). If your stop was premature (thesis intact), you're just re-entering, not using the 84% rule.
- **Multiple attempts allowed:** "As long as it doesn't invalidate your thesis you can take it a couple of tries" (Mta32jhu44s, 5211s)
- **"84 to the 84" = chop signal:** if 84% triggers twice in one day, means consolidation, not trending — reduces probability (Se_P4N3u48o, 3095s)
- **Sizing:** One source says can add size on clear setups: "if it's a clear as this one... I'll put in a little bit more" (7l8yqcapJ2c, 5713s). Another warns: "if you didn't take a good trade the first trade will absolutely destroy you" sizing up on 84% (teknuA8-LSQ, 5404s). This mirrors the B1 accelerator vs Jack contradiction.
- **Common mistake:** Selling most of position at low of day on 84% → nets only breakeven after first loss (T1ASztwyFcg, 3001s)
- **0DTE caution:** 84% rule "might be a little bit trickier" with 0DTE (4NxKb-yOKxU, 3237s)
- Re-entry can also be simple lower-timeframe B&R after failed first attempt (0dBiWH0sL88, 997s)
- If price is overextended from 5-min/1-min opening ranges, it's not a valid 84% setup (teknuA8-LSQ, 4910s)
- A small loss on first attempt is acceptable if re-entry makes significantly more: "I ended up losing I think 600 dollars on the first position... and I ended up making 3600 on the actual trade" (WV1WsVPahQQ, 1328s)
- After 84% stop-out, do NOT scale at highs — look for next level (g2EC_kt6G3g, 3604s)

### 4. Order blocks

- Defined as up-close or down-close candles on a given timeframe: "the order blocks are just up close candles" ( -k6ayIaeOzs, 5216s)
- Strength judged by candle body size — small body = weaker OB
- Higher timeframe OBs (daily, weekly) more significant
- OB break = stop-loss trigger: "I stopped out of Tesla basically right after we broke back below the order block" (0aoKhSUs-LM, 135s)
- "One candle rule Is basically an order block" (AjdBNs8qY7c, 2507s) — OCR ≡ OB confirmed
- "These down close candles in an uptrend. They should be used as what support for a continuation's hire" (3yDUvAjr4TQ, 1927s)
- Weekly order blocks act as major support/resistance ( -_dz8WqgRB8, 97s)
- "Order blocks, you can always go back on the accelerator... I use order blocks quite a bit. I personally use them every single day" (c4uNJYskLL4, 3823s)

### 5. Key levels

- Hierarchy: PDH/PDL > pre-market high/low > opening candle print > gap fills > order blocks > all-time highs/lows
- Gap fills are primary price objective in consolidating markets ( -_dz8WqgRB8, 3351s)
- Confluence of multiple key levels = high-probability area
- Key levels drawn before market open
- External liquidity (PDH/PDL, gap fills) = preferred targets: "I always like to target external equities... if it's not going to target one of these levels, then I'm not going to look to take the trade" (qyDCEwko494, 4419s)
- On volatile days, look beyond PDH/PDL to next external level (xJ521HB06gg, 3651s)
- Inside bars signal built-up liquidity — next day often has large momentum move (4l9AW30-i1o, 3606s)

### 6. Time-of-day + day-of-week rules; news days

- Low-volume weeks (last 2 weeks of December, holiday weeks) = low probability, reduce size
- News events (Powell, FOMC, 10am data) cause consolidation — low probability
- Wait for news to pass before trading
- First day of month / after long weekend = unpredictable
- Market pushes one direction until ~10am, then consolidates (0dBiWH0sL88, 1378s)
- **Fridays:** size down, scalp only, avoid 0DTE after 11am (AH2mmePrFsE, 3247s)
- **Fridays:** use next-week contracts for swing holds (EH6wbbTEIMU, 3446s)
- Summer months (August) typically lower volume and choppier
- "Historically the lowest volume week of the year. Which means it's the lowest probability week of the year" ( -_Q_BlPhjhU, 36s)
- "The first day of the month. So we'll let the price action develop see what happens" (0I1w83eSLyU, 122s)

### 7. Exits

- Standard exit: scale out at key levels. Example: "I took about 20% off here. I took about 40% off here" (0qxxsCC-8kI, 322s)
- Trailers for remaining position to capture extended moves ( -_Q_BlPhjhU, 357s)
- Common mistake: not scaling out → giving back profits
- Cut quickly for small loss if setup not working
- Risk per trade: 10-20% of option premium (0fE8zvzzVZE, 5677s)
- **Bar-by-bar exit (NEW):** "if you get one big red candle that breaks below the previous green candles low... that's technically the bar by bar and that's where you'd stop out" (qjItmSl400E, 3538s). Filter by moving to 5-min to reduce noise.
- **0DTE exits:** take 80-90% off at key levels (9te7G9JT1rw, 4183s)
- **Gamma scaling:** 20% tail can make more than 80% main due to deep ITM gamma (pFjKYfYfP2Tg, 6419s)
- Move underlying stop to breakeven after taking partial profits (7kajZjCStT8, 4110s)
- "if you had three contracts... if you took off two contracts at low of day... even if it goes back up to your full stop loss... you're still gonna be break even or green on that trade" (SeHdVXBf9-k, 277s)
- Profit targets at key levels, aiming for 1:1 or 2:1 R:R minimum

### 8. Higher-timeframe / swing / long-term B&R

- Higher TF analysis (daily, 4-hour) determines overall bias: "We also broke structure on the higher time frames. So I'm looking for a potential move downwards" (0I1w83eSLyU, 225s)
- Swing trades entered on pullbacks to key levels on 1-hour timeframe: "if you're looking to enter swings preferably you want to enter in on pullbacks right any sort of pullbacks the best is on like the one-hour time frame" (0fE8zvzzVZE, 6459s)
- B&R applies to higher TFs the same way: "if you look at the daily chart, it looks like a very clean retest so far" (0I1w83eSLyU, 417s)
- Understand higher TF before trading lower: "stick to the higher time frames first if you can understand what's happening on the higher time frames then you can move to lower time frames" (0mUVcHm9WXs, 1297s)
- Higher TF trending markets are most profitable — allows combining day trades + swing trades (qjItmSl400E, 527s)
- Swing trades should be managed on 5-min timeframe with next-week contracts: "if you have next week's contracts uh you're chilling because you just want to maintain on the five minute time frame" (JQajuUzTn6g, 2286s)
- Inside bars on daily = liquidity buildup, next day often has large move (4l9AW30-i1o, 3606s)
- Morning star reversal on higher TFs is a high-probability setup (p6tEcbCsfjs, 4660s)
- Swing trade risk: technicals should drive exit, not catalysts. "If I was playing strictly the technicals, I would have stopped out of this trade already" ( _22z9rgwvAQ, 180s)

**NOT COVERED in YouTube content:** inside bar specific entry rules, multi-day hold criteria beyond "if higher timeframe thesis intact"

### 9. Trade selection

- Best trades have multiple confluences: key level + order block + relative strength ( -_Q_BlPhjhU, 410s)
- Relative strength/weakness vs QQQ is the key filter for individual names
- Better to be late and wait for confirmation than enter early: "I'd rather be late than early on this name. I'd rather wait for confirmation" (0I1w83eSLyU, 322s)
- OK to sit on sidelines — not every day offers a good setup
- Majority of profits from ~1 month/year of hot trending periods — size up during these, size back down after ( -_dz8WqgRB8, 4728s)
- Avoid names with earnings that day (0I1w83eSLyU, 1079s)
- **1-2 quality trades/day CONFIRMED:** "the fact that I was able to walk away this week with two trades... I think in a testament to quality trades" (qsEvoLppZig, 298s)
- Don't force trades in chop: "I don't even want to force anything today anymore" (V_87OOIoRGw, 4809s)
- If you miss a setup, close the screen and take the day off — no FOMO chasing (T8leSPV4i7o, 3760s)
- **Stop-after-win (closest source):** "if you take one good trade in a day, turn off the computer, turn it off, walk away" (beilNB6V3lM, 2419s)
- The 3-part framework: "number one, narrative. Number two, the location. Number three, which is our execution" (multiple sources)
- Three core entry models: break-and-retest, reclaim, reversal (confirmed from course materials)

### 10. Concrete numbers

- **Win rate:** ~60% long-term, can be 70-80% in favorable conditions, as low as 33% in tough months
- **R:R:** minimum 2:1 aggregate; 1:1 "I would just spend a two to one scalp" ( -_dz8WqgRB8, 2326s)
- **Risk per trade:** 10-20% of option premium; 1% of account capital; $200-$1,000 typical dollar risk
- **Daily P&L examples:** break-even to $17,000-$18,000 for larger days
- **Contract moves:** 100-150% at peak on good trades
- **Account examples:** $4,800 account → $100/trade risk; larger accounts → $1,000-$2,000/trade risk
- **"2-4% is the risk amount for your capital, each trade"** (multiple sources)
- **Monthly trade count:** "only made $20,000 this month... I actually lost more trades than I won this month" — win rate can be below 50% in a month but still profitable due to R:R
- **R:R with 60% win rate = profitable system:** "if you have around a one to two with a 50%... you're going to be a very profitable trader"

---

### 11. QQQ/SPY market-structure alignment

- QQQ/SPY direction is the primary driver
- Relative strength/weakness of individual name vs QQQ is key signal
- Best trades happen when individual names are LEADING the market, not following (0fE8zvzzVZE, 4878s)
- Divergence between strong name and weak QQQ can lead to failed trade: "Tesla did have relative strength However, unfortunately because QQQ was so weak Tesla pushed down as well" (0aoKhSUs-LM, 125s)
- In consolidating market (QQQ range-bound), size down — continuation is difficult ( -_dz8WqgRB8, 4855s)
- "The best trades happen is when the actual individual names are leading the overall market themselves" (0fE8zvzzVZE, 4878s)

### 12. Long vs Short Playbooks

- Longs: look for relative strength, break above key levels (PDH, pre-market high), retest to confirm
- Shorts: look for relative weakness, break below key levels, retest
- Easier to trade longs in uptrend, shorts in downtrend
- Same B&R framework applies to both — direction determined by market structure and relative strength/weakness
- For shorts, wait for confirmation: "I'd rather be late than early on this name" (0I1w83eSLyU, 322s)
- Downside entries are more aggressive — may only offer one opportunity (ItlcnXfF1wE, 4305s)

---

## AMBIGUITIES / GAPS

1. **84% rule sizing:** YouTube sources contradict each other — some say size up on clear 84% setups, others warn against it. Matches existing accelerator vs Jack contradiction. No resolution.

2. **Stop-after-win:** Closest YouTube source ("turn off computer, walk away") is personal discipline, not a hard rule. config.yaml stop_after_win=true remains un-sourced.

3. **Reversal entry model:** Mentioned as a third entry model (Hayden coaching) but YouTube content has no standalone reversal extraction — only scattered references.

4. **Displacement quantification:** YouTube content mentions "strong displacement" qualitatively but never gives exact %, bar count, or FVG size criteria.

5. **First-break-of-day vs later breaks:** YouTube trade reviews discuss both but never formalize a rule distinguishing the two.

6. **Inside bar entry mechanics:** Identified as a liquidity pattern but specific entry/stop/target mechanics not documented.

7. **Number of confluences required for A+ vs A vs B:** YouTube uses "confluence" qualitatively but never defines a checklist. Confirms B1 finding that A/A+ = holistic confluence stacking.

---

## TOP 100 RANKED TRANSCRIPTS (extraction source)

The following 100 YouTube transcripts were ranked most relevant to trading-methodology extraction
(setup/level/entry keywords in title + content frequency). Full extraction content is held in
`research/youtube_batches/batch_001–019.md`.

Rank | Score | Transcript | Title
-----|-------|------------|------
1 | 41.0 | yk0ar-wDMXU | Weekly Trade Recap June 22 (Orderblocks)
2 | 33.0 | tHQRrRV1RGo | November 6th Live Session
3 | 30.2 | 7l8yqcapJ2c | 0921 Weekly Session Order Blocks
4 | 23.4 | 8I6B2HSH-_0 | [0s] I added one simple trick to my trading
5 | 22.2 | S2z11bfqLnw | June 13th Live Session
6 | 19.8 | kxjuZ9bk-F0 | December 16th Trade Review (-$690 SPY)
7 | 19.2 | BdG8dxQ_Hnk | Live Trading Session April 16th
8 | 19.2 | s6z3gy5Uh6c | Weekly Trading Recap August 3rd
9 | 19.2 | QSK5MhgR5r8 | January 9th Trade Review
10 | 18.6 | JrabwKiuJpg | Live Trading Session April 26th
11 | 18.0 | TaAYbe8lt7E | May 23rd Trade Review ($3.7k NVDA)
12 | 17.4 | K_HdP7ALs14 | Live Trading Session May 13th
13 | 17.4 | UPecCxOwC2Y | Live Trading Session May 28th
14 | 17.4 | _CYv86-RoHY | Live Trading Session May 23rd
15 | 17.4 | TquD3EV0EHw | June 26th + 27th Trade Review ($7k TSLA, AAPL)
16 | 17.4 | lI15h_OsYxc | July 19th Trade Review ($1.5k NVDA)
17 | 16.8 | -k6ayIaeOzs | Live Trading Session May 10th
18 | 16.8 | 3o6JJcZoGyw | Live Trading Session April 30th
19 | 16.8 | 4Amt_V1wnAE | March 12th Trade Review ($3.9k TSLA)
20 | 16.8 | JmOyREca-bM | January 18th Weekly Recap
21 | 16.2 | NNLB7z2W1WY | June 11th Live Session
22 | 16.2 | HkxTwWnzzAY | June 17th Trade Review ($11k TSLA A+ Trade)
23 | 16.2 | LY4HpL4kf0w | September 5th Trade Review ($2.9k AAPL)
24 | 16.2 | ngO33mnxhYQ | August 20th Trade Review ($5k AMD & TSLA)
25 | 15.6 | A1out1kXrEc | June 4th Live Session
26 | 15.6 | V_87OOIoRGw | September 13th Live Session
27 | 15.6 | guSdfcVIRck | July 23rd (-$1.6k NVDA)
28 | 15.6 | DYniybwOBAY | May 8th Trade Review (NVDA $3k)
29 | 15.6 | PBgqlCoAGZk | February 28th Trade Review
30 | 15.6 | S7aerujfxtk | March 6th Trade Review (-$4.6k TSLA)
31 | 15.6 | eJPQc_x9Ca8 | February 2nd Trade Review
32 | 15.6 | lJwLmX7kB3g | March 14th Trade Review ($450 NVDA)
33 | 15.6 | leLDZzyTNPs | [0s] Trading with the trend is one of the
34 | 15.0 | 8L2MWHToN_E | Live Trading Session April 24th
35 | 15.0 | F-KV40YE4Nc | April 7th Live Session
36 | 15.0 | XIe0XxNnV90 | December 6th Live Session
37 | 15.0 | TFHJk8_y8RI | November 12th Trade Review ($6.6k NVDA)
38 | 15.0 | Xc1P02mCPco | March 24 & 25 Trade Review ($14k TSLA + AAPL)
39 | 15.0 | adk8ywqcQww | April 11th Trade Review (-$1100 NVDA)
40 | 14.4 | RECUUQZymbo | June 25th Live Session
41 | 14.4 | U9l_3UwDQI8 | Live Trading Session May 2nd
42 | 14.4 | qsspPphDiPE | August 13th Live Session
43 | 14.4 | uK1u4p_MlXg | May 15th Live Session
44 | 14.4 | 9-Y340PyCZ8 | September 23rd Trade Review ($6k TSLA)
45 | 14.4 | AKTOq72_28s | March 27 Trade Review ($3k TSLA)
46 | 14.4 | JVnwuqK0UHo | April 17th Trade Review $5k Meta
47 | 14.4 | Kl6J6tI-3J4 | January 19 Trade Review
48 | 14.4 | RU8zDdT53Ag | February 19th Trade Review ($16k TSLA)
49 | 14.4 | mmXJYCk-nd0 | January 19 Trade Review
50 | 13.8 | 8DmV9UBQq5g | March 7th Trade Review
51 | 13.8 | N2XK-q0oa8I | Weekly Recap February 17th (Mastermind 3)
52 | 13.8 | _qe5pNH9eEY | March 7th Trade Review ($2.2k AAPL)
53 | 13.8 | ffgXS_5BP9s | September 12th Trade Review (-3.8k TSLA)
54 | 13.8 | kfYbz-q0MGE | March 10th Trade Review
55 | 13.8 | uPLuEui0CxU | June 13th Trade Review ($60 AAPL)
56 | 13.8 | 63p-lzRBTf0 | [0s] if you're a new Trader it's very easy to
57 | 13.8 | tr7IdqVgdIg | Weekly Live Session May 25th (Answering Questions)
58 | 13.8 | u9pFlMU2iZM | August 21st Live Session
59 | 13.8 | wT-qWLQ-a5g | Live Trading Session February 23rd
60 | 13.2 | Ie1kUjTj4Jc | July 16th Live Session
61 | 13.2 | _ncf5ULI2Zk | [6s] my check my check good morning
62 | 13.2 | pGLsdLZahVY | Live Trading Session April 29th
63 | 13.2 | qyDCEwko494 | Live Session May 1st
64 | 13.2 | 7DM97TbfgNo | August 16th Trade Review ($6.1k TSLA)
65 | 13.2 | GioAzO16xM4 | February 13th + February 10th Trade Review
66 | 13.2 | Lo5HzRJq9fg | August 14th Trade Review ($5.5k NVDA)
67 | 13.2 | n5a9PDnO83A | June 5th Trade Review (-$2.9k TSLA)
68 | 12.6 | 4YbcS7KpSOs | August 8th Trade Review ($4k QQQ)
69 | 12.6 | K-Y2b9IEbXQ | February 4th Trade Review ($4k NVDA)
70 | 12.6 | xhD_SRbyMNE | March 13th Trade Review ($11.8k TSLA)
71 | 12.6 | 9xPPy7JXJrM | November 21st Live Session
72 | 12.6 | KDtjZmOKjFg | August 1st Live Trading
73 | 12.6 | l6UXxpWsRm0 | March 26th Live Session
74 | 12.6 | pzZ2BaadX-s | April 4th Live Session
75 | 12.0 | 0z6KAobsuoX | June 21st Live Session
76 | 12.0 | 80oEvfFUri8 | Live Trading Session February 20th
77 | 12.0 | 9RWl7x8I_ww | July 3rd Live Session
78 | 12.0 | 9X1stqlKnDw | August 2nd Live Session
79 | 12.0 | DLFwLWVb61U | May 14th Live Session
80 | 12.0 | EiK0Fv4Ox1Q | Live Trading Session May 24th
81 | 12.0 | G00Y6CAdUzY | August 8th Live Session
82 | 12.0 | PJrYv5PkXBc | Live Trading Session May 20th
83 | 12.0 | WB34Q98VCPY | September 19th Live Session
84 | 12.0 | cgUoqp8243I | Live Trading Session January 31st
85 | 12.0 | iRj311b1NJ4 | April 1st Live Session
86 | 12.0 | lgCqWnnqmZ8 | Live Trading Session February 12th
87 | 12.0 | qjSC9FGF0js | May 12th Live Session
88 | 12.0 | tbzktgx46ao | Weekly Trading Recap July 22nd-26th
89 | 12.0 | tuiaMFg7VYY | Live Trading Session January 22nd
90 | 12.0 | wZw4exMyRn0 | Live Trading Session May 6th
91 | 12.0 | 2AFfZOf5qZk | November 18th Trade Review ($10.5k TSLA)
92 | 12.0 | 2teXVtwyYcc | March 2nd Trade Review
93 | 12.0 | 5zhlLPvW_cs | November 19th Trade Review ($9.5k TSLA)
94 | 12.0 | 6eMkQt_XsHk | June 28th Trade Review ($4.7k TSLA)
95 | 12.0 | ClQOGwOmOSk | July 1st Trade Review ($10.3k TSLA)
96 | 12.0 | DvvzpY5OwOU | July 10th Trade Review ($2.4k TSLA)
97 | 12.0 | ELPe7DNAAh8 | September 30th Trade Review ($2k AAPL)
98 | 12.0 | J1E2QdTaG4Y | November 5th Trade Review ($890 NVDA)
99 | 12.0 | ZCB7VOtR-lU | May 13th Trade Review ($3k AAPL)
100 | 12.0 | v0ACy-Gkpy4 | February 7th Trade Review

---

## SKIPPED TRANCHES (remaining 458 files)

The following 458 YouTube transcripts ranked below the top 100 threshold (score < 12.0).
They are LIVE SESSIONS and TRADE REVIEWS with lower methodology content density.
Full extraction content for ALL files is available in `research/youtube_batches/batch_001–019.md`.

### Category: Live Sessions (score 0.0–11.9) — mostly rambling / non-methodology
0z6KAobsuoX, 80oEvfFUri8, 9RWl7x8I_ww, 9X1stqlKnDw, DLFwLWVb61U, EiK0Fv4Ox1Q,
G00Y6CAdUzY, PJrYv5PkXBc, WB34Q98VCPY, cgUoqp8243I, iRj311b1NJ4, lgCqWnnqmZ8,
qjSC9FGF0js, tbzktgx46ao, tuiaMFg7VYY, wZw4exMyRn0, ... [458 files total — see research/b5_ranking.csv for full list]

**Full skip list:** `C:\Users\aharg\tradingbot\research\b5_ranking.csv` (ranks 101–558)
**Content source:** `C:\Users\aharg\tradingbot\research\youtube_batches\batch_001–019.md`

---
